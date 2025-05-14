"""Using Apache Spark with custom metrics."""

from collections import defaultdict
import logging
from typing import Any, Dict

from pyspark import SparkContext


METRIC_00 = "metric_00"
METRIC_01 = "metric_01"

LOGGING_FORMAT = "%(asctime)s [%(filename)s:%(lineno)d] %(levelname)s - %(message)s"


class CustomizedMetrics:
    """Process with customized metrics."""

    def __init__(self):
        self.metrics = defaultdict(int)

    def process(self, file):
        """Update metrics for f1."""
        self.metrics[METRIC_00] += 1
        # Conditional update.
        if file.startswith("file"):
            self.metrics[METRIC_01] += 1

        return file, self.metrics


def reduce_dict_count(lhs: Dict[str, int], rhs: Dict[str, int], reduce_fn: Any = None):
    """Reduce dicts."""
    result = {}

    if reduce_fn is None:
        reduce_fn = sum

    keys = set(lhs.keys()) | set(rhs.keys())
    for key in keys:
        result[key] = reduce_fn((lhs.get(key, 0), rhs.get(key, 0)))

    return result


def main():
    """Main."""
    spark = SparkContext("local", "Metrics Example")

    # Create RDD from list of files.
    files_rdd = spark.parallelize(["file1", "file2", "file3", "file10", "xyz"])

    files_processed_rdd = files_rdd.map(lambda file: CustomizedMetrics().process(file))
    files_processed_rdd.count()

    # Aggregate metrics from the RDD
    total_metrics = files_processed_rdd.map(lambda x: x[1]).reduce(reduce_dict_count)
    logging.info(total_metrics)

    spark.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
    main()
