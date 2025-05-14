"""Using Apache Spark with custom metrics."""

from collections import defaultdict
import itertools
import logging
import os
import sys
from typing import Any, Dict, Tuple

from self_debug.proto import config_pb2
from pyspark import SparkContext

from self_debug.common import utils
from self_debug.lang.base import ast_parser_factory, builder_factory
from self_debug.metrics import utils as metric_utils


# Probably no need for all lines, if it's too long.
BUILD_ERROR_CUTOFF_LINES = 10

CONFIG_TEXT_PROTO_JAVA = """
  builder {
    maven_builder {
      root_dir: "{root_dir}"
      # build_command: "cd {root_dir}; mvn clean verify"
    }
    enable_feedback: true  # Strongly recommended to be turned on.
    build_error_change_option: ERRORS_DECREASING
  }
  ast_parser {  # Comment the whole section if to disable.
    java_ast_parser {
      root_dir: "{root_dir}"  # Copy from repo.root_dir
      # mvn_path: "mvn"
    }
  }
"""

# Default is to use C# config.
CONFIG_TEXT_PROTO = CONFIG_TEXT_PROTO_C_SHARP


class BuilderMetrics:
    """Process with customized metrics."""

    def __init__(self):
        self.metrics = defaultdict(int)

        self.config = utils.parse_proto(CONFIG_TEXT_PROTO, config_pb2.Config)

    def process(self, root_dir: str) -> Tuple[Tuple[Any], Dict[str, int]]:
        """Update metrics for f1."""
        if not root_dir.endswith(os.path.sep):
            root_dir += os.path.sep

        self.metrics["00-start"] += 1
        # self.metrics[f"01-filter--{root_dir}"] += 1

        if os.path.exists(root_dir):
            self.metrics["01-filter--dir-exists"] += 1
        else:
            self.metrics["01-filter--dir-does-not-exist"] += 1
            self.metrics["02-finish--early"] += 1
            return (), metric_utils.reformat_metrics(self, self.metrics)

        builder = builder_factory.create_builder(self.config.builder, root_dir=root_dir)
        build_errors = builder.run()

        self.metrics[f"02-build-errors--len={len(build_errors):03d}"] += 1
        for build_error in build_errors:
            self.metrics[f"03-build-error--code=<{build_error.error_code}>"] += 1

            lines = [
                line
                for line in build_error.error_message.split(os.linesep)
                if line.strip()
            ]
            self.metrics[f"03-build-error--lines={len(lines):03d}"] += 1
            if len(lines) > BUILD_ERROR_CUTOFF_LINES:
                self.metrics[
                    f"03-build-error--lines={len(lines):03d}--file=<{build_error.filename}>"
                ] += 1
                lines = lines[:BUILD_ERROR_CUTOFF_LINES]

            for index, line in enumerate(lines):
                self.metrics[
                    f"04-build-error--line{index:02d}=<<<{line.strip()}>>>"
                ] += 1

            if build_error.filename is None:
                self.metrics["05-build-error--file=NONE"] += 1
            else:
                filename = build_error.filename.replace(root_dir, "")
                suffix = filename.split(".")[-1]

                self.metrics[f"05-build-error--file=<{filename}>"] += 1
                self.metrics[f"05-build-error--file-suffix=<{suffix}>"] += 1

        self.metrics["06-finish"] += 1
        return build_errors, metric_utils.reformat_metrics(self, self.metrics)


def main(args):
    """Main."""
    if args:
        option = args[0].lower()
        if option == "c#":
            logging.info("Using C# config.")
            config_text_proto = CONFIG_TEXT_PROTO_C_SHARP
        elif option == "java":
            logging.info("Using Java config.")
            config_text_proto = CONFIG_TEXT_PROTO_JAVA
        else:
            raise ValueError(
                f"Please provide a valid option for lang = `{option}`, not in (C#, Java)."
            )
    else:
        logging.info("Using default config.")
        config_text_proto = CONFIG_TEXT_PROTO

    spark = SparkContext("local", "Metrics Example")

    # Create RDD from list of files.
    if config_text_proto == CONFIG_TEXT_PROTO_JAVA:
        dataset_templates = (
            # Local.
            "/home/ec2-user/datasets/benchmark-datasets--xmpp-light/xmpp-light--success--rm-iter{commit}",  # pylint: disable=line-too-long
            # Container.
            "/datasets/benchmark-datasets--xmpp-light/xmpp-light--success--rm-iter{commit}",
        )
        datasets = list(
            itertools.chain(
                tmpl.format(commit=c) for c in range(4) for tmpl in dataset_templates
            )
        )
    logging.info("Total number of datasets: # = %d.", len(datasets))

    datasets_rdd_transformation = (
        spark.parallelize(datasets)
        # Remove datasets that do not exist at all: Reduce work load.
        .filter(os.path.exists)
    )

    # *****************************
    # Self contained in this file.
    # *****************************
    def demo():
        """A self-contained demo."""
        datasets_rdd = datasets_rdd_transformation.map(
            lambda dataset: BuilderMetrics().process(dataset)
        )
        datasets_rdd.count()

        # Aggregate metrics from RDD.
        metrics = datasets_rdd.map(lambda x: x[1]).reduce(metric_utils.reduce_by_key)
        metrics.update(
            {
                # Add initial count of datasets.
                "#datasets": len(datasets),
            }
        )
        metric_utils.show_metrics(metrics)

    # ******************************
    # Reusing metrics in `Builder`.
    # ******************************
    def demo_again():
        """Another demo."""

        def _get_metrics_from_builder(root_dir):
            config = utils.parse_proto(CONFIG_TEXT_PROTO, config_pb2.Config)
            builder = builder_factory.create_builder(config.builder, root_dir=root_dir)
            build_errors = builder.run()

            return builder.run_metrics(build_errors, BUILD_ERROR_CUTOFF_LINES)

        def _get_metrics_from_ast_parser(root_dir):
            config = utils.parse_proto(CONFIG_TEXT_PROTO, config_pb2.Config)
            ast_parser = ast_parser_factory.create_ast_parser(
                config.ast_parser, root_dir=root_dir
            )
            return ast_parser.run_metrics()

        def _get_metrics(map_fn):
            datasets_rdd = datasets_rdd_transformation.map(map_fn)
            datasets_rdd.count()
            return datasets_rdd.reduce(metric_utils.reduce_by_key)

        builder_metrics = _get_metrics(_get_metrics_from_builder)
        ast_parser_metrics = _get_metrics(_get_metrics_from_ast_parser)
        metrics = metric_utils.reduce_by_key(builder_metrics, ast_parser_metrics)
        metrics.update(
            {
                # Add initial count of datasets.
                "#datasets": len(datasets),
            }
        )
        metric_utils.show_metrics(metrics)
        metric_utils.show_metrics(metrics, sort=True)

    demo()
    demo_again()

    spark.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    main(sys.argv[1:])
