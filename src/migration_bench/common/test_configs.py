"""Unit tests for proto/*.proto and testdata/*.pbtxt."""

import logging
import os
import tempfile
import unittest

from parameterized import parameterized
from self_debug.proto import (
    batch_pb2,
    config_pb2,
    dataset_pb2,
    model_pb2,
    llm_agent_pb2,
    llm_parser_pb2,
)

from self_debug.common import utils


class TestConfigs(unittest.TestCase):
    """Unit tests for proto."""

    @parameterized.expand(
        (
            (
                "./testdata/batch.pbtxt",
                batch_pb2.BatchJob,
            ),
            (
                "./testdata/config.pbtxt",
                config_pb2.Config,
            ),
            (
                "./testdata/dataset.pbtxt",
                dataset_pb2.Dataset,
            ),
            (
                "./testdata/model.pbtxt",
                model_pb2.Model,
            ),
            (
                "./testdata/llm_agent.pbtxt",
                llm_agent_pb2.LlmAgent,
            ),
            (
                "./testdata/llm_parser.pbtxt",
                llm_parser_pb2.LlmParserByGroup,
            ),
            (
                "../configs/java_config.pbtxt",
                config_pb2.Config,
            ),
            (
                "../configs/java_compile_config.pbtxt",
                config_pb2.Config,
            ),
            (
                "../configs/java_compile_config_08.pbtxt",
                config_pb2.Config,
            ),
            # Other dirs.
            (
                "../datasets/configs/dataset_java_demo--xmpp-light.pbtxt",
                config_pb2.Config,
            ),
            # Other dirs.
            (
                "../batch/configs/batch_java__v00_ozt_ngde_20240620__first10.pbtxt",
                batch_pb2.BatchJob,
            ),
            (
                "../batch/configs/batch_java__v01_zhouqia_or_20241030.pbtxt",
                batch_pb2.BatchJob,
            ),
            (
                "../batch/configs/batch_java__v01_zhouqia_or_20241030__first10.pbtxt",
                batch_pb2.BatchJob,
            ),
            (
                "../batch/configs/batch_java__v01_zhouqia_or_20241030__first100.pbtxt",
                batch_pb2.BatchJob,
            ),
            (
                "../datasets/configs/java/dataset_java_unittest.pbtxt",
                config_pb2.Config,
            ),
        )
    )
    def test_export_load_proto(self, filename, expected_proto_type):
        """Unit test for proto."""
        pwd = os.path.dirname(os.path.abspath(__file__))

        proto = utils.load_proto(os.path.join(pwd, filename), expected_proto_type)
        logging.debug("PROTO: <<<%s>>>.", proto)
        self.assertIsInstance(proto, expected_proto_type)

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_file = os.path.join(temp_dir, "test.pbtxt")
            utils.export_proto(proto, tmp_file)
            loaded_proto = utils.load_proto(tmp_file, expected_proto_type)
            self.assertEqual(proto, loaded_proto)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
