"""Using Spark to get build stats.

Sample command:
```
export BASE_CONFIG=../configs/java_config.pbtxt

# Demo: From local/ container
export CONFIG=../datasets/configs/java/java__v01_zhouqia_or_20241030.pbtxt

echo "(BASE_CONFIG, CONFIG) = ($BASE_CONFIG, $CONFIG)"; ls $BASE_CONFIG; ls $CONFIG

python spark_build.py --base_config_file=$BASE_CONFIG --config_file=$CONFIG --user=sliuxl \
    --dry_run_builder=1
```

"""

import argparse
import logging
import os
from typing import Any, Sequence

from self_debug.proto import config_pb2
from pyspark import SparkContext

from self_debug.common import utils

from self_debug.datasets import hf_utils
from self_debug.metrics import utils as metric_utils

from self_debug.batch import utils as spark_utils


FIELD = "apply_seed_changes"
# Used to test for latency with multiple workers.
REPEAT = 1


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
        "--dry_run_project", type=int, default=0, help="Dry run project."
    )
    parser.add_argument("--dry_run_repo", type=int, default=0, help="Dry run repo.")
    parser.add_argument(
        "--dry_run_ast", type=int, default=0, help="Dry run AST parser."
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
        "--upload_project_to_s3", type=str, default=None, help="Upload project to s3."
    )
    parser.add_argument(
        "--upload_raw_metrics_to_s3", type=str, default=None, help="Upload to s3."
    )

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
    dry_run_project = args.dry_run_project
    dry_run_repo = args.dry_run_repo
    dry_run_ast = args.dry_run_ast
    dry_run_builder = args.dry_run_builder

    with utils.TimeItInSeconds("Spark", logging_fn=logging.warning) as batch_timer:
        # 1. Filter repos and projects.
        with utils.TimeItInSeconds(
            "Spark::Projects", logging_fn=logging.warning
        ) as projects_timer:
            projects, metrics = spark_utils.run_spark_projects(
                spark, datasets, config, dry_run_ast and dry_run_builder, args
            )

        reduce_metrics = []
        # 2. Run AST parser and builder.
        with utils.TimeItInSeconds(
            "Spark::Project", logging_fn=logging.warning
        ) as project_timer:
            reduce_metrics.append(
                spark_utils.get_project_metrics(
                    projects, config, dry_run=dry_run_project
                )[-1]
            )

        with utils.TimeItInSeconds(
            "Spark::Repo", logging_fn=logging.warning
        ) as repo_timer:
            reduce_metrics.append(
                spark_utils.get_repo_metrics(projects, config, dry_run=dry_run_repo)[-1]
            )

        with utils.TimeItInSeconds(
            "Spark::Ast", logging_fn=logging.warning
        ) as ast_timer:
            reduce_metrics.append(
                spark_utils.get_ast_metrics(projects, config, dry_run_ast)[-1]
            )

        with utils.TimeItInSeconds(
            "Spark::Build", logging_fn=logging.warning
        ) as builder_timer:
            reduce_metrics.append(
                spark_utils.get_builder_metrics(projects, config, dry_run_builder)[-1]
            )

        for iter_metrics in reduce_metrics:
            metrics = metric_utils.reduce_by_key(metrics, iter_metrics)

    # 3. Collect metrics.
    for name, seconds in (
        ("ast_parser", ast_timer.seconds),
        ("builder", builder_timer.seconds),
        ("projects", projects_timer.seconds),
        ("project", project_timer.seconds),
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
    result = spark_utils.email(
        metrics,
        args.user,
        tag=tag,
        filename=os.path.abspath(__file__),
        region=args.region,
    )
    logging.info("Done.")

    return metrics, result


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

    spark_result = spark_main(spark, datasets * REPEAT, config, args=args)

    spark.stop()

    return spark_result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    main(_parse_args()[0])
