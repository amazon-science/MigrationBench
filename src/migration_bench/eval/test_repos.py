"""Unit tests for repos used in final_eval.py."""

import logging
import os
import unittest

from parameterized import parameterized

from self_debug.common import utils
from self_debug.eval import final_eval
from self_debug.proto import config_pb2


_PWD = os.path.dirname(os.path.abspath(__file__))

_LICENSE = "../reference/license/license__java__v05.6_20250321.json"


class TestRepos(unittest.TestCase):
    """Unit tests for repos in final_eval.py."""

    @parameterized.expand(
        (
            (
                "../datasets/configs/java/java__v05.7-full_20250324.pbtxt",
                True,
                False,  # Skip license
            ),
            (
                "../datasets/configs/java/java__v05.8-full_20250429.pbtxt",
                False,
                True,
            ),
            (
                "../datasets/configs/java/java__selected_combined_fast2_20250428.pbtxt",
                False,
                True,
            ),
            (
                "../datasets/configs/java/java__selected_final_20250429.pbtxt",
                False,
                True,
            ),
        )
    )
    def test_commit_ids(self, filename: str, exact: bool, check_license: bool):
        """Unit test for DATASET_COMMIT_ID and valid licenses."""
        commit_ids = final_eval.DATASET_COMMIT_IDS
        licenses = utils.load_json(os.path.join(_PWD, _LICENSE))

        filename = os.path.join(_PWD, filename)
        config = utils.load_proto(filename, config_pb2.Config)

        if exact:
            self.assertEqual(len(config.dataset.dataset_repos), len(commit_ids))
        else:
            self.assertLessEqual(len(config.dataset.dataset_repos), len(commit_ids))

        for raw_repo in config.dataset.dataset_repos:
            repo = raw_repo.github_repo

            self.assertIn(repo.github_url, commit_ids)
            self.assertEqual(
                commit_ids[repo.github_url],
                repo.commit_id,
                f"Mismatch id for `{repo.github_url}`",
            )

            if check_license:
                self.assertIn(repo.github_url, licenses)

    def test_repos(self):
        """Unit test for repos."""
        self.assertLess(
            len(final_eval.DATASET_COMMIT_IDS), len(final_eval.DATASET_NUM_TESTS)
        )

        lhs = sorted(final_eval.DATASET_COMMIT_IDS.keys())
        rhs = sorted(final_eval.DATASET_NUM_TESTS.keys())
        for key in lhs:
            self.assertIn(key, rhs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    unittest.main()
