"""Unit tests for repos used in final_eval.py."""

import logging
import unittest

from migration_bench.common import utils
from migration_bench.eval import final_eval


class TestRepos(unittest.TestCase):
    """Unit tests for repos in final_eval.py."""

    def test_repos(self):
        """Unit test for repos."""
        self.assertEqual(
            final_eval.DATASET_COMMIT_IDS.keys(), final_eval.DATASET_NUM_TESTS.keys()
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    unittest.main()
