# pylint: disable=too-many-lines
"""Using Spark to get stats: Util function to get projects from a dataset, etc."""

from collections import defaultdict

# import fcntl
import datetime
import functools
import logging
import os
import shutil
import tempfile
from typing import Any, Dict, List, Sequence, Tuple, Union

import boto3
from self_debug.proto import batch_pb2, config_pb2, metrics_pb2
from pytz import timezone

from self_debug.common import git_repo, s3_data, send_email, utils
from self_debug.datasets import project as ds_project
from self_debug.lang.base import ast_parser_factory, builder_factory
from self_debug.metrics import cloud_watch, utils as metric_utils
from self_debug import self_debugging


# Probably no need for all lines, if it's too long.
BUILD_ERROR_CUTOFF_LINES = 10

CW_NAME = "Name"
CW_VALUE = "Value"

CW_LATENCY_SECONDS = "latency_seconds"
CW_NUM_ERRORS_FACTOR = "NUM_ERRORS_FACTOR"
CW_WALLTIME_SECONDS = "walltime_seconds"

JOB_AST = "ast"
JOB_BUILDER = "builder"
JOB_DEBUGGER = "debugger"
JOB_PROJECT = "project"
JOB_REPO = "repo"

PARSED_ARGS = "parsed_args"

PROJECT = "project"
PROJECT_INDEX = "project_index"
ROOT_DIR = "root_dir"
PROJECT_OBJECT = "project_object"

QNET_PORTING_DIR = "MidTransformCode"


CMD_CONTENT = """set -ex

unzip {zip_filename}

# {project}
cd {project_dir}


# git checkout ported
git checkout {branch}

git branch
git status
git log -3

# git diff ported..HEAD --name-only


dotnet build


cd -
"""

CMD_FILENAME = "self-debugging.sh"
ZIP_FILENAME = "self-debugging.zip"

UNKNOWN = "?"

_FORMAT_TIMESTAMP = "%Y%m%d-%H%M%S"

AWS_ACCESS_KEY_ID = "AWS_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY = "AWS_SECRET_ACCESS_KEY"
AWS_SESSION_TOKEN = "AWS_SESSION_TOKEN"


# pylint: disable=broad-except,no-member


def load_credentials():
    """Get credentials from sts."""
    try:
        credentials = boto3.Session().get_credentials().get_frozen_credentials()
        credentials = {
            AWS_ACCESS_KEY_ID: credentials.access_key,
            AWS_SECRET_ACCESS_KEY: credentials.secret_key,
            AWS_SESSION_TOKEN: credentials.token,
        }
        credentials = {
            key: value for key, value in credentials.items() if value is not None
        }
        return credentials
    except Exception as error:
        logging.warning("Error loading credentials from session: `%s`.", error)

    return None


def load_profile(credentials=None):
    """Get the current AWS profile."""
    del credentials

    profile_name = boto3.Session().profile_name
    if profile_name:
        logging.warning("The current AWS profile is: `%s`.", profile_name)

        home_dir = os.path.expanduser("~")
        logging.warning("Home dir: `%s`.", home_dir)
        logging.warning(utils.run_command(f"ls -lah {home_dir}"))

        filename = os.path.join(home_dir, ".aws/credentials")
        logging.warning(utils.run_command(f"ls -lah {os.path.dirname(filename)}"))

        # if credentials:
        #     content = "\n".join([
        #         "",
        #         "",
        #         f"[{profile_name}]",
        #         f"aws_access_key_id = {credentials[AWS_ACCESS_KEY_ID]}",
        #         f"aws_secret_access_key = {credentials[AWS_SECRET_ACCESS_KEY]}",
        #         f"aws_session_token = {credentials[AWS_SESSION_TOKEN]}",
        #         "",
        #         "",
        #     ])
        #
        #     file_path = pathlib.Path(filename)
        #     file_path.parent.mkdir(parents=True, exist_ok=True)
        #     file_path.touch(exist_ok=True)
        #     with open(file_path, "a") as file:
        #         fcntl.flock(file, fcntl.LOCK_EX)
        #         try:
        #             file.write(content)
        #         finally:
        #             fcntl.flock(file, fcntl.LOCK_UN)
        #     logging.warning("Appended to: `%s`.", filename)
        logging.warning(utils.run_command(f"grep -nv = {filename}"))

        return profile_name

    logging.warning("No AWS profile is set `%s`.", profile_name)
    return None


def show_args(args, logging_fn=logging.info):
    """Show args."""
    count = len(args.__dict__)
    logging_fn("Arguments: len = %d.", count)

    for index, (key, value) in enumerate(sorted(args.__dict__.items())):
        logging_fn("Arguments [%03d/%03d] %-30s: `%s`", index, count, key, value)


def get_timestamp(tz_name="America/Los_Angeles"):
    """Get timestamp."""
    return datetime.datetime.now(timezone(tz_name)).strftime(_FORMAT_TIMESTAMP)


def tee_output(pipe, log_file, index: int, logging_fn=logging.warning):
    """Tee output to file and logging."""
    with open(log_file, "w") as log:  # pylint: disable=unspecified-encoding
        for line in iter(pipe.readline, b""):
            if not line:
                break
            line = line.rstrip()
            logging_fn(f"[QNET{index}] {line}")
            log.write(line + "\n")


def _do_repartition(projects, partitions: int, nodes: int):
    projects.cache()
    count = projects.count()
    if not count:
        # Nothing to do.
        return projects

    nums = [partitions, count]
    if nodes > 0:
        nums.append(nodes)

    partitions = min(nums)
    logging.info("Repartition: # = %d from `%s` ...", partitions, nums)

    # Evenly partitioned among nodes.
    return (
        projects.zipWithIndex()
        .map(lambda p: (p[1], p[0]))  # (index, $element)
        .partitionBy(partitions, lambda index: index % partitions)
        .values()
    )


def _repartition_projects(projects, partitions: int, nodes: int):
    """Repartition projects."""
    projects = _do_repartition(projects, partitions, nodes)
    projects.cache()

    metrics = {
        "#partitions-01-new": projects.getNumPartitions(),
        "#repos_01_exists": projects.filter(
            lambda x: all(
                map(
                    os.path.exists,
                    [
                        x[ROOT_DIR],
                        x[PROJECT].format(root_dir=x[ROOT_DIR]),
                    ],
                )
            )
        ).count(),
    }
    return projects, metrics


def run_spark_projects(  # pylint: disable=too-many-branches,too-many-locals
    spark,
    datasets: Sequence[str],
    config: config_pb2.Config,
    dry_run: bool = False,
    args: Any = None,
) -> Tuple[Any, Dict[str, Any]]:
    """Get projects."""
    del dry_run

    logging.info("Total number of datasets: # = %d.", len(datasets))

    datasets_rdd = spark.parallelize(datasets)
    if (
        config.dataset.HasField("dataset_partition")
        and config.dataset.dataset_partition.partition_repos
    ):
        datasets_rdd = _do_repartition(
            datasets_rdd, config.dataset.dataset_partition.partition_repos, args.nodes
        )

    # 1. Filter repos.
    #    - Filter by valid repos.
    datasets_local_exist = (
        datasets_rdd.map(
            lambda dataset_config: (
                ds_project.Project.create_from_config(
                    dataset_config, readonly=not hasattr(args, "dry_run_debugger")
                )
            )
        )
        # Remove datasets that do not exist at all: Reduce work load.
        .filter(
            lambda base_project: (
                base_project is not None
                and base_project.init_dir is not None
                and os.path.exists(base_project.init_dir)
            )
        )
    )
    datasets_local_exist.cache()

    datasets_ported = datasets_local_exist.filter(lambda x: x.ported)
    datasets_ported.cache()

    #    - Find projects in repo.
    if "c_sharp_builder" in dir(config.builder) and config.builder.HasField(
        "c_sharp_builder"
    ):
        pass
    else:
        repo_projects = datasets_ported.map(
            lambda x: (
                # Project: Absolute path.
                x,
                [os.path.join("{root_dir}", "pom.xml")],
            )
        )

    if config.dataset.HasField("dataset_filter"):
        ds_filter = config.dataset.dataset_filter
        if ds_filter.first_n or ds_filter.last_n:
            # Filter by projects.
            pass

        if ds_filter.filter_by_project_name:
            # TODO(sliuxl): Assuming unique project names in a repo.
            if "c_sharp_builder" in dir(config.builder) and config.builder.HasField(
                "c_sharp_builder"
            ):
                project_name = ""
            elif config.builder.HasField("maven_builder"):
                project_name = config.builder.maven_builder.project
            project_name = project_name.replace("//", "/").replace("{root_dir}/", "")
            if project_name:
                repo_projects = repo_projects.map(
                    lambda xy: (
                        xy[0],
                        [
                            x
                            for x in xy[1]
                            if x.endswith(
                                xy[0].project.replace("{root_dir}/", "") or project_name
                            )
                        ],
                    )
                )
    repo_projects.cache()

    metrics = repo_projects.mapValues(len).values().countByValue()
    metrics = {f"#projects-in-repo={key:05d}": count for key, count in metrics.items()}
    for key, key_projs in repo_projects.collect():
        if key_projs:
            continue
        logging.warning("%s: projects is empty.", key.ground_truth)

    projects = (
        repo_projects.map(
            lambda row: (
                # (config, [(index, project)])
                row[0],
                list(enumerate(row[-1])),
            )
        )
        # (config, (index, project))
        .flatMapValues(lambda x: x)
        # (config, index, project)
        .map(lambda xy: (xy[0],) + tuple(xy[-1]))
        .map(
            lambda xyz: {
                ROOT_DIR: xyz[0].init_dir,
                PROJECT_INDEX: xyz[1],
                PROJECT: xyz[-1],
                PARSED_ARGS: args,
                PROJECT_OBJECT: xyz[0],
            }
        )
    )
    projects.cache()
    count = projects.count()
    if count < 10:
        raw_show_projects = projects.collect()
        show_projects = []
        for raw_proj in raw_show_projects:
            proj = raw_proj.copy()
            key = "parsed_args"
            if key in proj:
                args = proj[key]
                for aws in (
                    AWS_ACCESS_KEY_ID,
                    AWS_SECRET_ACCESS_KEY,
                    AWS_SESSION_TOKEN,
                ):
                    setattr(args, aws, "<***>")
                proj[key] = args
            show_projects.append(proj)
        logging.info(show_projects)

    metrics.update(
        {
            # Add initial count of datasets.
            "#repos": len(datasets),
            "#repos_00_exists": datasets_local_exist.count(),
            "#repos_01_ported": datasets_ported.count(),
            "#projects": count,
            "#partitions-00-raw": projects.getNumPartitions(),
        }
    )

    # Repartition.
    if (
        config.dataset.HasField("dataset_partition")
        and config.dataset.dataset_partition.partition_projects
    ):
        projects, repartition_metrics = _repartition_projects(
            projects, config.dataset.dataset_partition.partition_projects, args.nodes
        )
        projects.cache()
        metrics.update(repartition_metrics)

    return projects, metrics


def _get_metrics_from_project(config: config_pb2.Config, *args) -> Dict[str, int]:
    """Get metrics from git project: Args is dict with keys of `root_dir` & `proejct`."""
    del config

    kwargs = args[0]
    project_obj = kwargs.get(PROJECT_OBJECT)

    raw_pgs = project_obj.ground_truth
    if isinstance(raw_pgs, str):
        pgs = raw_pgs
    else:
        pgs = raw_pgs[0]

    metrics = {
        f"SparkUtils::Project::{utils.SKIP_SPARK_PREFIX}ground_truth__EQ__{pgs}": 1,
    }

    parsed_args = kwargs.get(PARSED_ARGS)
    if parsed_args.upload_project_to_s3 and not isinstance(raw_pgs, str):
        uploaded = 1
        # commit id is not used
        url, _ = raw_pgs

        # https://github.com/AnLiGentile/cLODg
        github_user = os.path.basename(os.path.dirname(url))
        github_repo = os.path.basename(url)
        github_user_initial = github_user[0].lower() if github_user else "UNKNOWN"

        input_root_dir = kwargs.get(ROOT_DIR)
        root_dir, download = project_obj.maybe_init_root_dir(input_root_dir)

        timestamp = get_timestamp()
        # Upload to s3: As a zip file.
        s3_full_filename = parsed_args.upload_project_to_s3.format(
            application=parsed_args.application,
            config_file=os.path.basename(parsed_args.config_file).replace(".", "--"),
            job_name=parsed_args.job_name,
            github_user_initial=github_user_initial,
            github_user=github_user,
            github_repo=github_repo,
            timestamp=timestamp,
        )

        s3_data.zip_and_upload_to_s3(root_dir, s3_full_filename)

        metrics.update(
            {
                f"SparkUtils::Project::Download={download}": 1,
                f"SparkUtils::Project::upload-github-initial={github_user_initial}": 1,
            }
        )
    else:
        uploaded = 0

    metrics.update(
        {
            f"SparkUtils::Project::upload-to-s3={uploaded}": 1,
        }
    )

    return True, metrics


def _get_metrics_from_repo(config: config_pb2.Config, *args) -> Dict[str, int]:
    """Get metrics from git repo: Args is dict with keys of `root_dir` & `proejct`."""
    kwargs = args[0]
    project_obj = kwargs.get(PROJECT_OBJECT)

    input_root_dir = kwargs.get(ROOT_DIR)
    root_dir, download = project_obj.maybe_init_root_dir(input_root_dir)
    if input_root_dir != root_dir:
        kwargs.update(
            {
                ROOT_DIR: root_dir,
            }
        )

    is_java = config.builder.HasField("maven_builder")
    if is_java:
        cfg = config.builder.maven_builder
        java_home = cfg.jdk_path
        mvn_command = kwargs.get(
            "mvn_command",
            cfg.build_command.replace("mvn clean compile", "mvn clean verify"),
        ).replace("{JAVA_HOME}", java_home)
    else:
        java_home = None
        mvn_command = None
    metrics = git_repo.GitRepo(
        kwargs.get(ROOT_DIR), project_obj.ground_truth
    ).run_metrics(
        java_versions=is_java and config.repo.run_java_metrics,
        timeout_minutes=config.repo.timeout_minutes,
        java_home=java_home,
        max_mvn_iterations=(
            config.repo.max_mvn_iterations
            if config.repo.HasField("max_mvn_iterations")
            else None
        ),
        mvn_command=mvn_command,
        run_java_base_commit_search=is_java and config.repo.run_java_base_commit_search,
        run_java_base_commit_search_no_maven=is_java
        and config.repo.run_java_base_commit_search_no_maven,
        run_java_hash=is_java and config.repo.run_java_hash,
        run_repo_license=config.repo.run_repo_license,
    )
    metrics[f"SparkUtils::Repo::Download={download}"] += 1

    return True, metrics


def _get_metrics_from_ast_parser(config: config_pb2.Config, *args) -> Dict[str, int]:
    """Get metrics from builder: Args is dict with keys of `root_dir` & `proejct`."""
    kwargs = args[0]

    ast_parser = ast_parser_factory.create_ast_parser(config.ast_parser, **kwargs)
    return True, ast_parser.run_metrics()


def _get_metrics_from_builder(
    config: config_pb2.Config, *args
) -> Tuple[metrics_pb2.Metrics, Dict[str, int]]:
    """Get metrics from builder: Args is dict with keys of `root_dir` & `project`."""
    kwargs = args[0]
    parsed_args = kwargs.get(PARSED_ARGS)

    input_root_dir = kwargs.get(ROOT_DIR)
    root_dir, download = kwargs.get(PROJECT_OBJECT).maybe_init_root_dir(input_root_dir)
    if input_root_dir != root_dir:
        kwargs.update(
            {
                ROOT_DIR: root_dir,
            }
        )

    run_metrics = defaultdict(int)
    with utils.TimeItInSeconds("Builder", logging_fn=logging.warning) as timer:
        builder = builder_factory.create_builder(config.builder, **kwargs)
        if parsed_args.apply_rules:
            config.repo.root_dir = root_dir
            if "c_sharp_builder" in dir(config.builder) and config.builder.HasField(
                "c_sharp_builder"
            ):
                pass

            self_debugging_runner = self_debugging.SelfDebugging.create_from_config(
                config, ground_truth=kwargs.get(PROJECT_OBJECT).ground_truth
            )
            self_debugging_runner.repo = None
            _ = self_debugging_runner.run(max_iterations=0)
            run_metrics = self_debugging_runner.builder.rule_metrics
        build_errors = builder.run()

    metrics = metrics_pb2.Metrics()
    metrics.initial_state_metrics.success = not bool(build_errors)
    metrics.initial_state_metrics.num_errors = len(build_errors)
    metrics.latency.seconds = timer.seconds

    run_metrics.update(
        builder.run_metrics(
            build_errors,
            BUILD_ERROR_CUTOFF_LINES,
            aggregate=not hasattr(parsed_args, "dry_run_debugger"),
        )
    )
    run_metrics[f"SparkUtils::Builder::Download={download}"] += 1

    return metrics, run_metrics


def str_to_int(value: str):
    """String back to int."""
    if value is None:
        return None
    return int(value)


def _load_batch_config(batch_config: str, parsed_args):
    """Load batch config."""
    logging.debug("Batch config: <<<%s>>>", batch_config)

    batch_cfg = None
    if ":" in batch_config or "{" in batch_config:
        # Textproto: Quoted in str.
        batch_cfg = utils.parse_proto(batch_config[1:-1], batch_pb2.BatchJob)
    elif os.path.exists(batch_config):
        # Config file
        batch_cfg = utils.load_proto(batch_config, batch_pb2.BatchJob)
    else:
        logging.warning("Unable to parse batch config: <<<%s>>>", batch_config)
        return batch_cfg

    if batch_cfg.emr_serverless.application.monitor.HasField("cloud_watch_metrics"):
        name_kwargs = (
            "base_config_file",
            "batch_config",
            "config_file",
            "max_iterations",
            "user",
        )
        name_kwargs = {field: str(getattr(parsed_args, field)) for field in name_kwargs}

        cwm = batch_cfg.emr_serverless.application.monitor.cloud_watch_metrics
        for dims in [cwm.shared_cw_dimensions] + list(cwm.extra_cw_dimensions):
            for key, value in dims.dimension_map.items():
                if value.upper() == value:
                    # Plug-in will be in the actual script instead.
                    continue
                dims.dimension_map[key] = value.format(**name_kwargs)

    return batch_cfg


def get_multi_batch_dimensions(
    cfg, extra_dimensions: Dict[str, str] = None
) -> Tuple[List[Dict[str, str]]]:
    """Get dimension vars for the batch job."""
    shared_dims = dict(cfg.shared_cw_dimensions.dimension_map)

    prefixes = []
    multi_dims = []
    for extra_cw in cfg.extra_cw_dimensions:
        prefix = extra_cw.prefix

        dims = {
            key: value.format(PREFIX=prefix)
            for key, value in dict(extra_cw.dimension_map).items()
        }
        dims.update(shared_dims)

        if extra_dimensions:
            dims.update(extra_dimensions)

        dimensions = []
        # Sort dimensions by its name.
        for key, value in sorted(dims.items()):
            dimensions.append(
                {
                    CW_NAME: key,
                    CW_VALUE: value or UNKNOWN,
                }
            )

        prefixes.append(prefix)
        multi_dims.append(dimensions)

    return tuple(prefixes), tuple(multi_dims)


def publish_metrics(  # pylint: disable=too-many-locals
    project: str,
    proto: metrics_pb2.Metrics,
    parsed_args,
    dry_run: bool,
):
    """Publish metrics to cloud watch."""
    if not parsed_args.batch_config:
        logging.info("Skip metrics without a `batch_config`.")
        return

    batch_cfg = _load_batch_config(parsed_args.batch_config, parsed_args)
    if batch_cfg is None:
        logging.info("Unable to process batch config: Skip.")
        return

    if not proto.HasField("final_state_metrics"):
        logging.warning("Unable to go through for project: Skip `%s`.", project)
        return

    monitor_cfg = batch_cfg.emr_serverless.application.monitor
    if not monitor_cfg.HasField("cloud_watch_metrics"):
        logging.info("Not configured to process batch config: Skip.")
        return

    cfg = monitor_cfg.cloud_watch_metrics

    prefixes, multi_dimensions = get_multi_batch_dimensions(
        cfg,
        {
            "project": project or UNKNOWN,
        },
    )
    for prefix, dimensions in zip(prefixes, multi_dimensions):
        logging.warning(
            "Dimensions for prefix = `%s`, len = %d: <<<\n%s\n>>>",
            prefix,
            len(dimensions),
            dimensions,
        )

        metrics = []
        s_errors = proto.initial_state_metrics.num_errors
        e_errors = proto.final_state_metrics.state.num_errors
        for name, value, unit in (
            # #success
            ("success_rules_00", int(proto.initial_state_metrics.success), None),
            ("success", int(proto.final_state_metrics.state.success), None),
            # #errors
            ("n_errors_start", s_errors, cloud_watch.UNIT_COUNT),
            ("n_errors_end", e_errors, cloud_watch.UNIT_COUNT),
            (
                "n_errors_delta_decrease",
                max(s_errors - e_errors, 0),
                cloud_watch.UNIT_COUNT,
            ),
            (
                "n_errors_delta_increase",
                max(e_errors - s_errors, 0),
                cloud_watch.UNIT_COUNT,
            ),
            # Latency
            (
                "iterations",
                max(proto.final_state_metrics.iterations, 0),
                cloud_watch.UNIT_COUNT,
            ),
            (
                "max_iterations",
                proto.final_state_metrics.max_iterations,
                cloud_watch.UNIT_COUNT,
            ),
            (CW_LATENCY_SECONDS, proto.latency.seconds, cloud_watch.UNIT_TIME_SECONDS),
            # Project and job info: `str` doesn't seem to work.
            # ("application", parsed_args.application or UNKNOWN, None),
            # ("job_name", parsed_args.job_name or UNKNOWN, None),
        ):
            metrics.append(
                cloud_watch.build_metric(f"{prefix}{name}", value, unit=unit)
            )
        logging.warning(
            "Metrics for `%s` with prefix = `%s`: <<<%s>>>", project, prefix, metrics
        )

        for metric in metrics:
            metric.update({"Dimensions": dimensions})

        client = cloud_watch.CloudWatch(
            region=parsed_args.region, namespace=cfg.namespace
        )
        client.publish(
            metrics,
            dry_run=not (cfg.enable_cloud_watch and monitor_cfg.debugger) or dry_run,
        )


def publish_batch_metrics(
    summary: Dict[str, Union[int, Sequence[Any]]],
    parsed_args,
    dry_run: bool = False,
):
    """Publish batch metrics to cloud watch."""
    batch_cfg = _load_batch_config(parsed_args.batch_config, parsed_args)
    if batch_cfg is None:
        logging.info("Unable to process batch config: Skip.")
        return

    monitor_cfg = batch_cfg.emr_serverless.application.monitor
    if not monitor_cfg.HasField("cloud_watch_metrics"):
        logging.info("Not configured to process batch config: Skip.")
        return

    cfg = monitor_cfg.cloud_watch_metrics

    prefixes, multi_dimensions = get_multi_batch_dimensions(cfg)
    for prefix, dimensions in zip(prefixes, multi_dimensions):
        logging.info(
            "Dimensions for prefix = `%s`, len = %d: <<<\n%s\n>>>",
            prefix,
            len(dimensions),
            dimensions,
        )

        metrics = []
        for name, value in sorted(summary.items()):
            metrics.append(
                cloud_watch.build_metric(
                    f"{prefix}{name}",
                    value,
                    unit=(
                        None
                        if name.startswith("p_")
                        else {
                            CW_LATENCY_SECONDS: cloud_watch.UNIT_TIME_SECONDS,
                            CW_NUM_ERRORS_FACTOR: None,
                            CW_WALLTIME_SECONDS: cloud_watch.UNIT_TIME_SECONDS,
                        }.get(name, cloud_watch.UNIT_COUNT)
                    ),
                )
            )
        logging.info("Batch metrics with prefix = `%s`: <<<%s>>>", prefix, metrics)

        for metric in metrics:
            metric.update({"Dimensions": dimensions})

        client = cloud_watch.CloudWatch(
            region=parsed_args.region, namespace=cfg.namespace
        )
        client.publish(
            metrics,
            dry_run=not (cfg.enable_cloud_watch and monitor_cfg.debugger) or dry_run,
        )


def _load_credentials(parsed_args, qnet_env: int = -1):
    """Load new credentials each time to run QNetCLI."""
    credentials = load_credentials() or {}

    keys = sorted(credentials.keys())
    logging.warning("Credential keys: `%s`.", keys)

    env = os.environ.copy()
    if qnet_env == -1:
        env = {}
    elif qnet_env == 0:
        pass
    elif qnet_env == 1:
        # Use executor credentials.
        if credentials:
            logging.warning("env keys (extra): `%s`.", keys)
            env.update(credentials)
    elif qnet_env == 2:
        # Use driver credentials.
        for key in keys:
            if hasattr(parsed_args, key):
                old_value = credentials[key]
                new_value = getattr(parsed_args, key)
                credentials[key] = new_value
                logging.warning(
                    "env keys (extra) update for `%s` from driver: same = `%s`.",
                    key,
                    old_value == new_value,
                )
        env.update(credentials)

    logging.warning("env keys: `%s`.", sorted(env.keys()))

    return ({"env": env} if env else {}), credentials


def _get_metrics_from_debugger(  # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    config: config_pb2.Config, *args
) -> Tuple[metrics_pb2.Metrics, Dict[str, int]]:
    kwargs = args[0]

    project_obj = kwargs.get(PROJECT_OBJECT)
    _, download = project_obj.maybe_init_root_dir(kwargs.get(ROOT_DIR))
    root_dir = project_obj.new_copy(none_is_ok=False)
    logging.warning("Local copy: %s.", root_dir)

    kwargs.update(
        {
            ROOT_DIR: root_dir,
        }
    )

    parsed_args = kwargs.get(PARSED_ARGS)
    project = kwargs.get(PROJECT)

    # 0.5 Constructor.
    config.repo.root_dir = root_dir
    if "c_sharp_builder" in dir(config.builder) and config.builder.HasField(
        "c_sharp_builder"
    ):
        pass
    self_debugging_runner = self_debugging.SelfDebugging.create_from_config(
        config,
        min_iterations=parsed_args.min_iterations,
        n_errors=parsed_args.n_errors,
        region=parsed_args.region,
        ground_truth=project_obj.ground_truth,
    )

    max_iterations = parsed_args.max_iterations or config.max_iterations
    repo = self_debugging_runner.repo
    # 1. Save a snapshot if s3.
    metrics = {}
    if not parsed_args.dry_run_debugger and isinstance(
        project_obj, ds_project.S3Project
    ):
        git_status = repo.status()[0]
        key = ""
        if isinstance(git_status, str):
            if git_repo.GIT_STATUS_CLEAN in git_status:
                key = "00--00--git-clean"
            else:
                port_branch = config.repo.source_branch or "ported"

                commit_msg = f"Auto PORTING for s3 repos: branch = `{port_branch}`."
                json_file = os.path.join(
                    os.path.dirname(project_obj.init_dir), "porting_result.json"
                )
                json_content = utils.load_file(json_file)
                if json_content is not None:
                    commit_msg += (
                        f"\n\n{os.path.basename(json_file)}:\n{json_content}\n\n"
                    )
                success_0 = repo.commit_all(commit_msg, "-u")
                success = repo.new_branch(port_branch, source_branch="") and success_0

                key = f"00--00--git-unclean--port-success=<{port_branch},{success_0},{success}>"
        else:
            key = "00--00--git-n.a."

        metrics.update(
            {
                "Debugger::00--00--s3--attemped": 1,
                f"Debugger::{key}": 1,
            }
        )

    # 1.5 Create a new branch as needed.
    branch = None
    if (
        config.repo.source_branch or config.repo.branch
    ) and not parsed_args.dry_run_debugger:
        if config.repo.git_clean:
            repo.clean()
        if config.repo.git_restore:
            repo.restore()

        branch_kwargs = {
            "source_branch": config.repo.source_branch,
            "timestamp": datetime.datetime.now().strftime(_FORMAT_TIMESTAMP),
            "max_iterations": max_iterations,
        }
        branch = config.repo.branch.format(**branch_kwargs)
        repo.new_branch(branch, config.repo.source_branch, checkout=True)

    logging.info("git log: %s.", repo.log(2))
    logging.info("git branch: %s.", repo.branch())
    logging.info("git status: %s.", repo.status())

    # 2. Run debugging.
    qnet_dir = None
    qnet_logs = None
    try:
        proto = metrics_pb2.Metrics()
        build_errors = None
        with utils.TimeItInSeconds("Debugger", logging_fn=logging.warning) as timer:
            logging.warning("Using qnet: `%s`.", parsed_args.qnet_bin)
            if parsed_args.qnet_bin:
                n_deprecated_api = None
            else:
                proto, build_errors = self_debugging_runner.run(
                    max_iterations, dry_run=parsed_args.dry_run_debugger
                )
                logging.warning("Python result: <<<\n%s\n>>>", proto)

                iteration, dbg_success, init_errors, used_max, n_deprecated_api = (
                    proto.final_state_metrics.iterations,
                    proto.final_state_metrics.state.success,
                    proto.initial_state_metrics.num_errors,
                    proto.final_state_metrics.max_iterations,
                    proto.final_state_metrics.deprecated_api,
                )

            iteration = f"{iteration:03d}"
            init_errors = f"{init_errors:03d}"
    except Exception as error:
        logging.exception("Job failed with error: <<<%s>>>", error)
        (
            iteration,
            dbg_success,
            build_errors,
            init_errors,
            used_max,
            n_deprecated_api,
        ) = ("unknown", False, None, None, None, -1)
        metrics.update(
            {
                f"Debugger::01--00--error--{project.format(root_dir=kwargs.get(ROOT_DIR))}--{error}": 1,
            }
        )

        proto = metrics_pb2.Metrics()
    proto.latency.seconds = timer.seconds

    # Rename to a different branch.
    if branch:
        i_errors = "-u" if init_errors is None else init_errors
        f_errors = "-u" if build_errors is None else f"{len(build_errors):03d}"

        success_str = "success" if dbg_success else "fail"
        new_branch = f"{branch}--{success_str}-at{iteration}-of-{used_max}--init{i_errors}--final{f_errors}"
        success = repo.rename_branch(new_branch, branch)
        logging.info("git rename = %s: %s <== %s.", success, new_branch, branch)
    else:
        new_branch = "ported"

    # 3. Upload to s3.
    if not parsed_args.dry_run_debugger and parsed_args.upload_to_s3:
        metrics.update(
            {
                "Debugger::00--00--s3-upload-00--attemped": 1,
            }
        )
        try:
            upload_to_s3 = parsed_args.upload_to_s3
            if qnet_dir:
                root_dir = qnet_dir
                for qnet_log in qnet_logs or ():
                    utils.run_command(["mv", qnet_log, qnet_dir], shell=False)

                # Not uploading parent dir, as it's always making a copy.
                upload_to_s3 = upload_to_s3.replace("{root_dir_parent}", "{root_dir}")

            # All relative to `root_dir`: (`zip_from`, `root_dir_to_s3`, `local_raw_dir`)
            # - zip_from: The dir to upload to s3
            #   * ==> zip ... -r zip_from
            #
            # - root_dir_to_s3: The dir with the zipped file
            #   * ==> zip root_dir_to_s3/*.zip ...
            # - local_raw_dir:
            #   * An alias for `root_dir_to_s3` to tag multi projects in a repo, which may not exist
            #     locally before, and will be used in remote s3 filename.
            if "{root_dir_parent}" in upload_to_s3:
                # Local ==> Parent
                zip_from = root_dir_to_s3 = os.path.dirname(root_dir)
                local_raw_dir = root_dir_to_s3

                cmd_filename = os.path.join(root_dir_to_s3, CMD_FILENAME)
                utils.export_file(
                    cmd_filename,
                    CMD_CONTENT.format(
                        branch=new_branch,
                        project=os.path.basename(project),
                        project_dir=os.path.dirname(
                            os.path.relpath(
                                project.format(root_dir=root_dir), root_dir_to_s3
                            )
                        ),
                        zip_filename=ZIP_FILENAME,
                    ),
                )
                utils.run_command(["chmod", "+x", cmd_filename], shell=False)
            else:
                index = kwargs.get(PROJECT_INDEX) or 0
                zip_from = root_dir
                local_raw_dir = root_dir_to_s3 = tempfile.mkdtemp(
                    prefix=f"{os.path.basename(root_dir)}-{index:03d}-{os.path.basename(project)}-{get_timestamp()}-"  # pylint: disable=line-too-long
                )
            if zip_from.endswith(os.path.sep):
                zip_from = zip_from[:-1]
            logging.warning(
                "ZIP: `%s` ==> `%s::%s`.", zip_from, root_dir_to_s3, ZIP_FILENAME
            )
            utils.run_command(
                [
                    "zip",
                    os.path.join(root_dir_to_s3, ZIP_FILENAME),
                    "-r",
                    os.path.basename(zip_from),
                ],
                cwd=os.path.dirname(zip_from),
                shell=False,
            )

            # - Clean up: Remove local, and the .zip file is in a different dir.
            shutil.rmtree(root_dir)

            upload_to_s3 = upload_to_s3.format(
                application=parsed_args.application or f"local/{get_timestamp()}",
                job_name=parsed_args.job_name,
                config_file=os.path.basename(parsed_args.config_file).replace(
                    ".", "--"
                ),
                root_dir=os.path.basename(local_raw_dir),
                root_dir_parent=os.path.basename(local_raw_dir),
                # Based on initial and final migration states.
                init_status=(
                    "green"
                    if (isinstance(init_errors, str) and not str_to_int(init_errors))
                    else (
                        "yellow"
                        if (iteration == "unknown" or str_to_int(iteration))
                        else "green--extra-rules"
                    )
                ),
                success=str(dbg_success).lower(),
            )
            s3_data.upload_to_s3(root_dir_to_s3, upload_to_s3)

            metrics.update(
                {
                    "Debugger::00--00--s3-upload-01--success": 1,
                }
            )
        except Exception as error:
            logging.exception("Unable to upload to s3: <<<%s>>>", error)
            metrics.update(
                {
                    "Debugger::00--00--s3-upload-01--failure": 1,
                }
            )

    try:
        pgs = project_obj.ground_truth
        publish_metrics(
            pgs if isinstance(pgs, str) else pgs[0],
            proto,
            parsed_args,
            parsed_args.dry_run_debugger,
        )
        cw_status = "success"
    except Exception as error:
        logging.exception("Unable to publish metrics: `%s`.", error)
        cw_status = "failure"
    metrics.update(
        {
            "Debugger::00--00--metrics--attempted": 1,
            f"Debugger::00--00--metrics--{cw_status}": 1,
        }
    )

    success = dbg_success
    max_iterations = f"{max_iterations if used_max is None else used_max:03d}"
    n_errors = "?" if build_errors is None else f"{len(build_errors):03d}"
    # Using raw dir, not the copied dir for aggregation.
    project = f"{project_obj.ground_truth}#={init_errors}"
    metrics.update(
        {
            "Debugger::00--00--attemped": 1,
            f"Debugger::00--01--project=<{project}>": 1,
            f"Debugger::00--02--project-iter=<{project}, {max_iterations}>": 1,
            # Final states.
            f"Debugger::01--00--success=<{success}>": 1,
            f"Debugger::01--01--#deprecation=<{n_deprecated_api}>": 1,
            f"Debugger::01--02--success-iter=<{success},{iteration}>": 1,
            f"Debugger::01--03--success-#errors=<{success},{n_errors}>": 1,
            f"Debugger::01--04--success-#deprecation=<{success},{n_deprecated_api}>": 1,
            f"Debugger::01--05--success-iter/max=<{success},{iteration}/{max_iterations}>": 1,
            # - Project.
            f"Debugger::01--10--success-project=<{success},{project}>": 1,
            f"Debugger::01--11--success-project-iter=<{success},{project},{iteration}>": 1,
            f"Debugger::01--12--success-project-#errors=<{success},{project},{n_errors}>": 1,
            f"Debugger::01--13--success-project-#deprecation=<{success},{project},{n_deprecated_api}>": 1,
            (
                f"Debugger::01--13--success-project-iter/max="
                f"<{success},{project},{iteration}/{max_iterations}>"
            ): 1,
            f"SparkUtils::Debugger::Download={download}": 1,
        }
    )

    return proto, metrics


def _aggregate_metrics(protos):
    n_total = len(protos)

    ported_protos = [res[0] for res in protos if res[0].HasField("final_state_metrics")]
    if not ported_protos:
        return {}

    iterations = [proto.final_state_metrics.iterations for proto in ported_protos]

    s_errors = [p.initial_state_metrics.num_errors for p in ported_protos]
    # Build errors at iteration = 0
    m_errors = []
    for proto in ported_protos:
        if (
            proto.intermediate_state_metrics
            and proto.intermediate_state_metrics[0].iteration == 0
        ):
            num = proto.intermediate_state_metrics[0].num_errors
        else:
            num = proto.initial_state_metrics.num_errors
        m_errors.append(num)
    e_errors = [p.final_state_metrics.state.num_errors for p in ported_protos]

    # Ideally all positive: Error count decrease.
    delta = [s - e for (s, e) in zip(s_errors, e_errors)]

    demo_proto = ported_protos[0]
    metrics = {
        # Scalar
        # - #success: `n_total`, `n_success`
        "n_success_rules_00": sum(i == -1 for i in iterations),
        "n_success_rules_01": sum(i <= 0 for i in iterations),
        "n_projects_errors_decrease": sum(i > 0 for i in delta),
        "n_projects_errors_increase": sum(i < 0 for i in delta),
        "n_projects_errors_non_increase": sum(i >= 0 for i in delta),
        # Vector
        # - #errors
        "n_errors_start": s_errors,
        "n_errors_end": e_errors,
        "n_errors_delta_decrease": [max(i, 0) for i in delta],
        "n_errors_delta_increase": [max(-i, 0) for i in delta],
        "n_errors_rules_00": s_errors,
        "n_errors_rules_01": m_errors,
        # - Latency
        "iterations": [max(i, 0) for i in iterations],
        "max_iterations": [p.final_state_metrics.max_iterations for p in ported_protos],
        "MIN_ITERATIONS": demo_proto.final_state_metrics.h_min_iterations,
        "MAX_ITERATIONS": demo_proto.final_state_metrics.h_max_iterations,
        CW_LATENCY_SECONDS: [p.latency.seconds for p in ported_protos],
    }

    metrics.update(
        {
            "p_success_rules_00": metrics["n_success_rules_00"] * 1.0 / n_total,
            "p_success_rules_01": metrics["n_success_rules_01"] * 1.0 / n_total,
        }
    )

    if demo_proto.final_state_metrics.HasField("h_num_errors_factor"):
        metrics.update(
            {
                CW_NUM_ERRORS_FACTOR: demo_proto.final_state_metrics.h_num_errors_factor,
            }
        )

    return metrics


def _get_metrics(
    projects,
    config,
    map_fn,
    job: str,
    dry_run: bool = False,
    proto: bool = False,
) -> Tuple[int, int, Dict[str, int]]:
    """Get metrics."""
    if dry_run or projects.isEmpty():
        return (
            {
                "n_total": 0,
                "n_success": 0,
            },
            {},
        )

    projects.cache()
    args = projects.first()[PARSED_ARGS]

    # Tuple[Union[bool, proto], metrics]
    total = projects.map(functools.partial(map_fn, config))
    total.cache()
    logging.info("Total = <<<\n%s\n>>>", total.collect())

    # 0. Raw
    if args.upload_raw_metrics_to_s3:
        # Conver to a list of dict.
        summary_raw_metrics = (
            total
            # dict
            .map(lambda x: x[-1])
            .filter(lambda x: x)
            .map(lambda x: [x])
            .reduce(lambda x, y: x + y)
        )

        timestamp = get_timestamp()

        # Upload to s3.
        s3_filename = args.upload_raw_metrics_to_s3.format(
            application=args.application or f"local/{timestamp}",
            config_file=os.path.basename(args.config_file).replace(".", "--"),
            count=f"{len(summary_raw_metrics):04d}",
            job=job,
            job_name=args.job_name,
            timestamp=timestamp,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            # To a local file.
            local_filename = os.path.join(temp_dir, os.path.basename(s3_filename))
            logging.warning(
                "Exporting len = %04d: `%s`.", len(summary_raw_metrics), local_filename
            )
            utils.export_json(local_filename, summary_raw_metrics)

            # Upload to s3.
            s3_data.upload_to_s3(temp_dir, os.path.dirname(s3_filename))

    # 1. Reduced
    if proto:
        success = total.filter(
            lambda x: (
                # Builder.
                not x[0].HasField("final_state_metrics")
                and x[0].HasField("initial_state_metrics")
                and x[0].initial_state_metrics.success
            )
            or (
                # Debugger.
                x[0].HasField("final_state_metrics")
                and x[0].final_state_metrics.state.success
            )
        )
    else:
        success = total.filter(lambda x: x[0])

    metrics = total.map(lambda x: x[-1]).reduce(metric_utils.reduce_by_key)

    summary = {
        "n_total": total.count(),
        "n_success": success.count(),
        "p_success": success.count() * 1.0 / total.count(),
    }
    if proto:
        summary.update(_aggregate_metrics(total.collect()))

    return summary, metrics


def get_project_metrics(projects, config: config_pb2.Config, dry_run: bool = False):
    """Get project metrics."""
    return _get_metrics(
        projects, config, _get_metrics_from_project, job=JOB_PROJECT, dry_run=dry_run
    )


def get_repo_metrics(projects, config: config_pb2.Config, dry_run: bool = False):
    """Get repo metrics."""
    return _get_metrics(
        projects, config, _get_metrics_from_repo, job=JOB_REPO, dry_run=dry_run
    )


# pylint: disable=line-too-long
def get_builder_metrics(projects, config: config_pb2.Config, dry_run: bool = False):
    """Get builder metrics."""
    return _get_metrics(
        projects,
        config,
        _get_metrics_from_builder,
        job=JOB_BUILDER,
        dry_run=dry_run,
        proto=True,
    )


def get_ast_metrics(projects, config: config_pb2.Config, dry_run: bool = False):
    """Get AST metrics."""
    return _get_metrics(
        projects, config, _get_metrics_from_ast_parser, job=JOB_AST, dry_run=dry_run
    )


def get_debugger_metrics(projects, config: config_pb2.Config, dry_run: bool = False):
    """Get debugger metrics."""
    return _get_metrics(
        projects,
        config,
        _get_metrics_from_debugger,
        job=JOB_DEBUGGER,
        dry_run=dry_run,
        proto=True,
    )


# pylint: enable=line-too-long


def email(
    metrics: Dict[str, Any],
    user: str = "",
    tag: str = "",
    filename: str = "",
    region: str = None,
):
    """Send email."""
    if not filename:
        filename = os.path.abspath(__file__)

    # Exclude some metrics.
    metrics = {
        key: value
        for key, value in metrics.items()
        if (
            # common/file_utils.py
            ("-keep-repo-base-commit-id__EQ__" not in key)
            and ("-keep-repo-url__EQ__" not in key)
            and ("-keep-repo-index__EQ__" not in key)
            and ("-keep-repo-total-len__EQ__" not in key)
            and
            # common/hash_utils.py
            (not key.startswith("GitRepo::RepoSnapshot::repo_commit_first_00__EQ__"))
            and (
                not key.startswith("GitRepo::RepoSnapshot::repo_commit_first_01__EQ__")
            )
            and (not key.startswith("GitRepo::RepoSnapshot::repo_commit_last_00__EQ__"))
            and (
                not key.startswith(
                    "GitRepo::RepoSnapshot::repo_snapshot_update_time__EQ__"
                )
            )
            and (not key.startswith("GitRepo::RepoSnapshot::repo_snapshot_hash__EQ__"))
            and (utils.SKIP_SPARK_PREFIX not in key)
        )
    }

    def _is_git_branch_metric(key: str):
        return key.startswith("GitRepo::01-") and (
            "--branch=" in key or "--branches=" in key
        )

    git_branch = 0
    for key, value in metrics.items():
        git_branch += _is_git_branch_metric(key)

    if git_branch > 2000:
        metrics = {
            key: value
            for key, value in metrics.items()
            if not _is_git_branch_metric(key)
        }

    info = [f"Stats from `{filename}`: {tag}."]
    info += ["", "Results 00: Unsorted"]
    info += list(
        f"{name}: {count}" for name, count in metric_utils.show_metrics(metrics)
    )
    # info += ["", "Results 01: Sorted"]
    # info += list(
    #     f"{name}: {count}" for name, count in metric_utils.show_metrics(metrics, sort=True)
    # )

    return send_email.email(
        "<br>".join(f.replace("<", "&lt;").replace(">", "&gt;") for f in info),
        user,
        f"{os.path.basename(filename)} stats {tag}",
        region=region,
    )
