"""Unit tests for ./configs/ pbtxt files."""

import logging
import os
from typing import Any
import unittest

from parameterized import parameterized
from migration_bench.proto import batch_pb2

from migration_bench.common import utils


def load(filename, proto_type=batch_pb2.BatchJob):
    """Load pbtxt file."""
    pwd = os.path.dirname(os.path.abspath(__file__))
    return utils.load_proto(os.path.join(pwd, filename), proto_type)


class TestConfigs(unittest.TestCase):
    """Unit tests for proto."""

    def compare(self, lhs: str, rhs: str, function: Any):
        """Unit test for proto."""
        lhs = load(lhs)
        rhs = load(rhs)

        if function is None:
            self.assertEqual(lhs, rhs)
            return

        self.assertNotEqual(lhs, rhs)

        function(lhs)
        function(rhs)
        self.assertEqual(lhs, rhs)

    @parameterized.expand(
        (
            # Java
            (
                "configs/batch_java__v00_ozt_ngde_20240620__first10.pbtxt",
                "configs/batch_java__v01_zhouqia_or_20241030__first10.pbtxt",
            ),
            (
                "configs/batch_java__v01_zhouqia_or_20241030.pbtxt",
                "configs/batch_java__v01_zhouqia_or_20241030__first10.pbtxt",
            ),
            (
                "configs/batch_java__v01_zhouqia_or_20241030.pbtxt",
                "configs/batch_java__v01_zhouqia_or_20241030__first100.pbtxt",
            ),
            (
                "configs/batch_java__v05_raw_20250113.pbtxt",
                "configs/batch_java__v05_raw_20250113__first100.pbtxt",
            ),
            (
                "configs/batch_java__v05_raw_20250113.pbtxt",
                "configs/batch_java__v05_raw_20250113__first1k.pbtxt",
            ),
        )
    )
    def test_compare_dataset_configs(self, lhs: str, rhs: str):
        """Unit test for configs for the same dataset."""

        def _clear(proto):
            # CW
            monitor = proto.emr_serverless.application.monitor
            monitor.ClearField("enable_cloud_watch")
            monitor.ClearField("prefix")
            monitor.ClearField("cloud_watch_metrics")

            proto.emr_serverless.job.name = "<job>"
            proto.emr_serverless.job.time_out_minutes = 0
            # Driver.
            driver = proto.emr_serverless.job.driver
            driver.cores = 0
            driver.memory = ""
            driver.disk = ""
            worker = proto.emr_serverless.job.worker
            worker.disk = ""

            # Script: config_file, EC2.
            config_files = set()
            for script in proto.emr_serverless.scripts:
                args = script.args

                elements = list(a for a in args if a.startswith("--config_file="))
                self.assertEqual(len(elements), 1)
                args.remove(elements[0])
                config_files.add(elements[0])

                elements = list(a for a in args if a.startswith("--skip_projects="))
                self.assertLessEqual(len(elements), 1)
                if elements:
                    args.remove(elements[0])

                script.ec2.instances = 0
                script.ec2.min_instances = 0

            # Build and debug configs are consistent.
            self.assertEqual(len(config_files), 1)

        self.compare(lhs, rhs, _clear)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
