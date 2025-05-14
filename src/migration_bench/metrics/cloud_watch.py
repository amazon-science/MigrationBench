"""Publish metrics to Cloud Watch."""

import copy
from datetime import datetime
import logging
import sys
from typing import Any, Dict, Sequence

import boto3

from self_debug.common import send_email, utils

DEFAULT_NAMESPACE = "aws"
NAMESPACE = "namespace"

UNIT_COUNT = "Count"
UNIT_DOLLAR = "$"

UNIT_MEMORY_B = "Bytes"
UNIT_MEMORY_KB = "Kilobytes"
UNIT_MEMORY_MB = "Megabytes"
UNIT_MEMORY_GB = "Gigabytes"
UNIT_MEMORY_TB = "Teraytes"

UNIT_MILLION = "M"
UNIT_NONE = "None"
UNIT_PERCENT = "Percent"

UNIT_TIME_MICRO_SECONDS = "Microseconds"
UNIT_TIME_MILLI_SECONDS = "Milliseconds"
UNIT_TIME_MINUTES = "Minutes"
UNIT_TIME_SECONDS = "Seconds"


TIMESTAMP = "Timestamp"


def _maybe_update(kwargs: Dict[str, Any], field: str, value: Any):
    if value is None:
        return
    kwargs.update({field: value})


def build_metric(name: str, value: Any, unit: str = None, **kwargs) -> Dict[str, Any]:
    """Build metric."""
    dry_run = kwargs.pop("dry_run", False)

    metric = copy.deepcopy(kwargs)
    metric.update(
        {
            "MetricName": name,
        }
    )

    if isinstance(value, (list, tuple)):
        _maybe_update(metric, "Values", value)

        if len(value):
            metric.update(
                {
                    "StatisticValues": {
                        "SampleCount": len(value),
                        "Sum": sum(value),
                        "Minimum": min(value),
                        "Maximum": max(value),
                    },
                }
            )
    else:
        _maybe_update(metric, "Value", value)

    _maybe_update(metric, "Unit", unit)

    if TIMESTAMP not in metric and not dry_run:
        metric.update(
            {
                TIMESTAMP: datetime.now(),
            }
        )

    return metric


# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch/client/put_metric_data.html
class CloudWatch:
    """Publish cloud watch metrics."""

    def __init__(
        self,
        region: str = None,
        namespace: str = None,
        client: str = "cloudwatch",
        **kwargs,
    ):
        """Constructor."""
        self.region = region or send_email.AWS_REGION
        self.namespace = namespace or DEFAULT_NAMESPACE

        self._client = client
        self.kwargs = kwargs

    @property
    def client(self):
        """Boto3 Client."""
        if isinstance(self._client, str):
            self._client = boto3.client(self._client, region_name=self.region)

        return self._client

    def publish(self, metrics: Sequence[Dict], dry_run: bool = False):
        """Publish custom metric to CloudWatch."""
        kwargs = {
            "Namespace": self.namespace,
            "MetricData": list(metrics),
        }

        if dry_run:
            logging.info("Skip publish <<<%s>>>", kwargs)
        else:
            self.client.put_metric_data(**kwargs)

        return kwargs


def main(dry_run: bool):
    """Main."""
    metric = build_metric(name="Count000", value=10, unit=UNIT_COUNT)
    cloud_watch = CloudWatch()
    cloud_watch.publish((metric,), dry_run=dry_run)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    main(True if len(sys.argv) < 2 else int(sys.argv[1]))
