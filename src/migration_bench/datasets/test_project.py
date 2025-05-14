"""Unit tests for project."""

import logging
import os
import unittest

from parameterized import parameterized
from self_debug.proto import dataset_pb2

from self_debug.common import utils
from self_debug.datasets import project as ds_project


LOCAL_PROJECT_PBTXT = """
  local_repo {
    root_dir: "/datasets/csharp--error-code-examples"
  }
"""

S3_PROJECT_PBTXT = """
  s3_repo {
    s3_dir: "s3://self-dbg-plus/datasets/csharp--framework-to-core--v0-20240516/PROJECT/"
  }
"""


class TestProject(unittest.TestCase):
    """Unit tests for project."""

    @parameterized.expand(
        (
            (
                LOCAL_PROJECT_PBTXT,
                ds_project.LocalProject,
                "/datasets/csharp--error-code-examples",
                "/datasets/csharp--error-code-examples",
                True,
                None,
            ),
            (
                S3_PROJECT_PBTXT,
                ds_project.S3Project,
                "s3://self-dbg-plus/datasets/csharp--framework-to-core--v0-20240516/PROJECT/",
                # "/tmp/ported/self-dbg-plus--PROJECT",
                None,
                False,
                None,
            ),
        )
    )
    def test_project(
        self,
        proto,
        expected_type,
        expected_ground_truth,
        expected_init_dir,
        expected_ported,
        expected_prefix,
    ):
        """Unit test for project."""
        proto = utils.parse_proto(proto, dataset_pb2.DatasetRepo)

        project = ds_project.Project.create_from_config(proto)
        self.assertIsInstance(project, expected_type)

        project.maybe_init_root_dir()
        self.assertEqual(project.ground_truth, expected_ground_truth)
        self.assertEqual(project.init_dir, expected_init_dir)
        self.assertEqual(project.ported, expected_ported)

        new_dir = project.new_copy(none_is_ok=True)
        if expected_prefix is None:
            self.assertIsNone(new_dir)
        else:
            logging.debug("New dir: `%s`.", new_dir)
            self.assertTrue(
                os.path.basename(new_dir).startswith(
                    os.path.basename(expected_init_dir)
                )
            )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
