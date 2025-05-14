"""Unit tests for cloud_watch.py."""

from datetime import datetime
import logging
import unittest

from parameterized import parameterized

from self_debug.metrics import cloud_watch

METRICS = (
    {
        "MetricName": "num_apples",
        "Value": 1,
        "Unit": cloud_watch.UNIT_COUNT,
    },
    {
        "MetricName": "num_secs",
        "Value": 1.5,
        "Unit": cloud_watch.UNIT_TIME_SECONDS,
        "Dimensions": [
            {
                "Name": "job",
                "Value": "qct",
            }
        ],
    },
)


class TestCloudWatch(unittest.TestCase):
    """Unit tests for cloud_watch.py."""

    @parameterized.expand(
        (
            # Scalar
            (
                "num_apples",
                1,
                cloud_watch.UNIT_COUNT,
                {
                    # "dry_run": False,
                },
                {
                    "MetricName": "num_apples",
                    "Value": 1,
                    "Unit": cloud_watch.UNIT_COUNT,
                },
                True,
            ),
            (
                "num_secs",
                1.5,
                cloud_watch.UNIT_TIME_SECONDS,
                {
                    "Dimensions": [
                        {
                            "Name": "job",
                            "Value": "qct",
                        }
                    ],
                    "dry_run": True,
                },
                METRICS[-1],
                False,
            ),
            # Vector
            (
                "num_apples",
                [],
                cloud_watch.UNIT_COUNT,
                {
                    # "dry_run": False,
                },
                {
                    "MetricName": "num_apples",
                    "Values": [],
                    "Unit": cloud_watch.UNIT_COUNT,
                },
                True,
            ),
            (
                "num_apples",
                [1],
                cloud_watch.UNIT_COUNT,
                {
                    # "dry_run": False,
                },
                {
                    "MetricName": "num_apples",
                    "Values": [1],
                    "Unit": cloud_watch.UNIT_COUNT,
                    "StatisticValues": {
                        "SampleCount": 1,
                        "Sum": 1,
                        "Minimum": 1,
                        "Maximum": 1,
                    },
                },
                True,
            ),
            (
                "num_apples",
                [3, 5, 3, 1],
                cloud_watch.UNIT_COUNT,
                {
                    # "dry_run": False,
                },
                {
                    "MetricName": "num_apples",
                    "Values": [3, 5, 3, 1],
                    "Unit": cloud_watch.UNIT_COUNT,
                    "StatisticValues": {
                        "SampleCount": 4,
                        "Sum": 12,
                        "Minimum": 1,
                        "Maximum": 5,
                    },
                },
                True,
            ),
        )
    )
    def test_build_metric(
        self, name, value, unit, kwargs, expected_metric, expected_timestamp
    ):
        """Unit tests build_metrics."""
        metric = cloud_watch.build_metric(name, value, unit, **kwargs)

        if expected_timestamp:
            self.assertIn(cloud_watch.TIMESTAMP, metric)
            self.assertIsInstance(metric.pop(cloud_watch.TIMESTAMP), datetime)
        else:
            self.assertNotIn(cloud_watch.TIMESTAMP, metric)

        self.assertEqual(metric, expected_metric)

    @parameterized.expand(
        (
            (
                tuple(METRICS),
                {
                    "dry_run": True,
                    # "namespace": "aws",
                },
                {
                    "Namespace": "aws",
                    "MetricData": list(METRICS),
                },
            ),
        )
    )
    def test_publish(self, metrics, kwargs, expected_metrics):
        """Unit tests publish."""
        client = cloud_watch.CloudWatch()
        self.assertEqual(client.publish(metrics, **kwargs), expected_metrics)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    unittest.main()
