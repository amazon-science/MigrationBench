# pylint: disable=line-too-long
"""Using Spark to run self debugging.

Sample command:
```
export BASE_CONFIG=../configs/csharp_config.pbtxt

export S3_DIR=s3://self-dbg-plus--logs/dev/{application}/{job_name}/{config_file}/init-{init_status}--success-{success}/{root_dir_parent}/

export CONFIG=../datasets/configs/dataset_csharp_demo--net48.pbtxt
export S3_DIR=s3://self-dbg-plus--logs/dev/{application}/{job_name}/{config_file}/init-{init_status}--success-{success}/{root_dir}/

export S3_DIR=

export BATCH_CONFIG="emr_serverless { application { monitor { enable_cloud_watch: true prefix: 'dev-' } } }"
export BATCH_CONFIG=

echo "(BASE_CONFIG, CONFIG, S3_DIR, BATCH) = ($BASE_CONFIG, $CONFIG, $S3_DIR, $BATCH_CONFIG)"

python spark_debug.py --base_config_file=$BASE_CONFIG --config_file=$CONFIG \
    --batch_config="$BATCH_CONFIG" --user=sliuxl \
    --upload_to_s3=$S3_DIR --max_iterations=1 --min_iterations=0 \
    --qnet_args="--llm-client:bedrock::-w:debugging::--sdk-root-folder:/home/sliuxl/SDKAssemblies/" \
    --dry_run_debugger=1
```

"""
# pylint: enable=line-too-long

import argparse
import logging
import os
from typing import Any, Sequence

import boto3
from self_debug.proto import config_pb2
from pyspark import SparkContext

from self_debug.common import utils
from self_debug.metrics import utils as metric_utils
from self_debug.datasets import hf_utils

from self_debug.batch import utils as spark_utils

# Probably no need for all lines, if it's too long.
BUILD_ERROR_CUTOFF_LINES = 10

FIELD = "apply_seed_changes"
# Used to test for latency with multiple workers.
REPEAT = 1


def get_cd():
    """Get credentials."""
    try:
        sts_client = boto3.client("sts")
        response = sts_client.assume_role(
            RoleArn="arn:aws:iam::552793110740:role/EMRServerlessS3RuntimeRoleSelfDbg",
            RoleSessionName="MySparkAppSession",
            DurationSeconds=12 * 60 * 60,  # 12 hours
        )
        logging.info(type(response))
        logging.info(response.keys())
        logging.info(response["Credentials"].keys())
    except Exception as error:
        logging.exception(error)


def get_cd2():
    """Get credentials."""
    try:
        sts_client = boto3.client("sts")
        response = sts_client.get_session_token(
            DurationSeconds=12 * 60 * 60
        )  # 12 hours
        logging.info(type(response))
        logging.info(response.keys())
        logging.info(response["Credentials"].keys())
    except Exception as error:
        logging.exception(error)


def _parse_args():
    """Parse args."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base_config_file", type=str, default=None, help="Base config file."
    )
    parser.add_argument(
        "--config_file", type=str, default=None, help="Config file with dataset."
    )
    parser.add_argument("--first_n", type=int, default=0, help="Run dataset first_n.")

    parser.add_argument(
        "--batch_config", type=str, default=None, help="Batch config file pbtxt."
    )

    parser.add_argument(
        "--dry_run_builder", type=int, default=0, help="Dry run builder."
    )
    parser.add_argument(
        "--apply_rules",
        type=int,
        default=0,
        help="Apply rules before collecting builder stats.",
    )
    parser.add_argument(
        "--dry_run_debugger", type=int, default=0, help="Dry run debugger."
    )

    parser.add_argument(
        "--min_iterations", type=int, default=10, help="Min iterations."
    )
    parser.add_argument(
        "--max_iterations", type=int, default=None, help="Max iterations."
    )
    parser.add_argument(
        "--n_errors", type=float, default=None, help="Iterations = #erros * x."
    )
    parser.add_argument(
        "--upload_raw_metrics_to_s3", type=str, default=None, help="Upload to s3."
    )
    # s3://$BUCKET/$PREFIX/{root_dir_parent}
    parser.add_argument("--upload_to_s3", type=str, default=None, help="Upload to s3.")

    parser.add_argument("--nodes", type=int, default=0, help="Number of nodes.")
    parser.add_argument(
        "--application", type=str, default="", help="Application id or name."
    )
    parser.add_argument("--job_name", type=str, default="", help="Job name.")
    parser.add_argument(
        "--apply_seed_changes",
        type=int,
        default=None,
        help="Whether to apply seed changes.",
    )
    parser.add_argument("--skip_projects", type=str, default="", help="Skip projects.")
    parser.add_argument(
        "--find_projects", type=str, default="*.csproj,*.sln", help="Project suffixes."
    )

    parser.add_argument("--region", type=str, default="", help="AWS region.")
    parser.add_argument(
        "--qnet_bin",
        type=str,
        default="/home/sliuxl/dotnet/src/QnetTransformCLI/QnetTransform.CLI",
        help="Use qnet repo: dir containing `./bin/`.",
    )
    # 1. Self-debugging only:
    #    `--enable-llm-retry::--llm-client:bedrock::-w:porting,debugging`
    # 2. Porting + self-debugging:
    #    `-b:qnet-porting::--enable-llm-retry::--llm-client:bedrock::--sdk-root-folder:/SDK/SDKAssemblies::-w:porting,debugging`  # pylint: disable=line-too-long
    #    Note:
    #      * Extra args:     `-b`, `--sdk-root-folder`
    #      * Change in args: `-w`
    # 3. Optional args:
    #    `--enable-llm-positive-feedback[=true]`
    parser.add_argument(
        "--qnet_args",
        type=str,
        default="--enable-llm-retry::--llm-client:bedrock::-w:debugging",
        help="Cmd args for QNet.",
    )
    parser.add_argument("--qnet_runs", type=int, default=4, help="QNet runs.")
    # Setup qnet env vars:
    # -1: Nothing
    #  0: os.env
    #  1: os.env + executor credential
    #  2: os.env + driver   credential
    parser.add_argument("--qnet_env", type=int, default=1, help="QNet env vars.")

    # The user running this job, and to send summary email to.
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="User running the job, without @amazon.com.",
    )

    return parser.parse_known_args()


def spark_main(
    spark,
    datasets: Sequence[str],
    config: config_pb2.Config,
    args: Any = None,
):
    """Spark main: Return contains metrics and `send_email`."""
    dry_run_builder = args.dry_run_builder
    dry_run_debugger = args.dry_run_debugger

    if args.qnet_bin and args.application:
        # To run QNetCLI jobs.
        driver_credentials = spark_utils.load_credentials()
        logging.info("Keys: `%s`", sorted(driver_credentials.keys()))

        args = argparse.Namespace(**vars(args))
        for key, value in sorted(driver_credentials.items()):
            setattr(args, key, value)

        get_cd()
        get_cd2()
        logging.info("env keys: `%s`.", sorted(os.environ.keys()))

    with utils.TimeItInSeconds("Spark", logging_fn=logging.warning) as batch_timer:
        # 1. Filter repos and projects.
        with utils.TimeItInSeconds(
            "Spark::Projects", logging_fn=logging.warning
        ) as projects_timer:
            projects, metrics = spark_utils.run_spark_projects(
                spark, datasets, config, dry_run_builder and dry_run_debugger, args
            )

        reduce_metrics = []
        # 2. Run self debugging.
        with utils.TimeItInSeconds(
            "Spark::Repo", logging_fn=logging.warning
        ) as repo_timer:
            reduce_metrics.append(spark_utils.get_repo_metrics(projects, config)[-1])

        with utils.TimeItInSeconds(
            "Spark::Build", logging_fn=logging.warning
        ) as builder_timer:
            reduce_metrics.append(
                spark_utils.get_builder_metrics(projects, config, dry_run_builder)[-1]
            )

        with utils.TimeItInSeconds(
            "Spark::Debug", logging_fn=logging.warning
        ) as debugger_timer:
            batch_summary, dbg_metrics = spark_utils.get_debugger_metrics(
                projects, config, dry_run_debugger
            )
            reduce_metrics.append(dbg_metrics)

        for iter_metrics in reduce_metrics:
            metrics = metric_utils.reduce_by_key(metrics, iter_metrics)

    batch_summary.update(
        {
            spark_utils.CW_WALLTIME_SECONDS: batch_timer.seconds,
        }
    )
    # 3. Collect metrics.
    spark_utils.publish_batch_metrics(
        batch_summary,
        args,
        dry_run=dry_run_debugger,
    )

    for name, seconds in (
        ("builder", builder_timer.seconds),
        ("debugger", debugger_timer.seconds),
        ("projects", projects_timer.seconds),
        ("repo", repo_timer.seconds),
        ("total", batch_timer.seconds),
    ):
        metrics.update(
            {
                f"#seconds::{name}": seconds,
                f"#minutes::{name}": seconds / 60.0,
            }
        )

    # 4. Send email.
    tag = f"(`{args.application}`, `{args.job_name}`)"
    email_result = spark_utils.email(
        metrics,
        args.user,
        tag=tag,
        filename=os.path.abspath(__file__),
        region=args.region,
    )
    logging.info("Done.")

    return metrics, email_result


def main(args):
    """Main."""
    spark_utils.show_args(args, logging.warning)

    config = utils.load_proto(args.base_config_file, config_pb2.Config)
    if args.config_file:
        ds_config = utils.load_proto(args.config_file, config_pb2.Config)
        logging.info("Merge from dataset config: <<<%s>>>", ds_config)
        config.MergeFrom(ds_config)
    hf_utils.resolve_hf_dataset(config.dataset)
    logging.info("Config: <<<%s>>>", config)

    spark = SparkContext()

    # Create RDD from list of files.
    datasets = tuple(config.dataset.dataset_repos)
    if datasets and not datasets[0].HasField(FIELD):
        if args.apply_seed_changes is None:
            value = getattr(config.dataset, FIELD)
        else:
            value = args.apply_seed_changes
        logging.info("Set `%s` to be `%s` for all datasets.", FIELD, value)
        for i in range(len(datasets)):
            setattr(datasets[i], FIELD, value)

    logging.info("Taking first n: `%d` out of `%d`.", args.first_n, len(datasets))
    if args.first_n > 0:
        datasets = datasets[: args.first_n]
    elif args.first_n < 0:
        datasets = datasets[args.first_n :]
    datasets = tuple(datasets)

    if args.first_n != 0:
        logging.info("Set datasets: <<<%s>>>", datasets)

    if args.skip_projects:
        skip_projects = [p.strip() for p in args.skip_projects.split(",")]
        datasets = [
            d
            for d in datasets
            if ((not d.HasField("s3_repo")) or (d.s3_repo.s3_dir not in skip_projects))
        ]
        datasets = tuple(datasets)

    spark_result = spark_main(spark, datasets * REPEAT, config, args=args)

    spark.stop()

    return spark_result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    main(_parse_args()[0])
