"""Unit tests for final_eval.py."""

import logging
import os
import unittest

from parameterized import parameterized

from migration_bench.common import utils
from migration_bench.eval import final_eval

_PWD = os.path.dirname(os.path.abspath(__file__))

URL_0 = "https://github.com/0xShamil/java-xid"
URL_1 = "https://github.com/0xShamil/java-xid.git"


class TestFinalEval(unittest.TestCase):
    """Unit tests for final_eval.py."""

    @parameterized.expand(
        (
            (
                URL_0,
                URL_1,
            ),
            (
                URL_1,
                URL_0,
            ),
        )
    )
    def test_alias(self, url, expected_url):
        """Unit test for `alias`."""
        self.assertEqual(final_eval.alias(url), expected_url)

    @parameterized.expand(
        (
            (
                "https://github.com/0000005/sync2any",
                -2,
            ),
            (
                URL_0,
                21,
            ),
        )
    )
    def test_get_key_loaded(self, url, expected_num_tests):
        """Unit test for `get_key`."""
        self.assertEqual(final_eval.DATASET_NUM_TESTS[url], expected_num_tests)

    @parameterized.expand(
        (
            (
                URL_1 + URL_1,
                None,
                {},
                False,
            ),
            (
                URL_0,
                None,
                {},
                False,
            ),
            (
                URL_1,
                None,
                {
                    "require_compiled_java_major_version": 52,
                    "maven_command": "cd {root_dir}; mvn clean compile",
                },
                True,
            ),
            (
                URL_1,
                None,
                {
                    "require_compiled_java_major_version": 52,
                },
                True,
            ),
            (
                URL_1,
                os.path.join(_PWD, "testdata/java-xid.diff"),
                {
                    "require_compiled_java_major_version": 52,
                },
                False,
            ),
            (
                URL_1,
                None,
                {
                    "commit_id": "commit-id-does-not-exist",
                    "require_compiled_java_major_version": 52,
                },
                False,
            ),
        )
    )
    def test_run_batch_eval(self, url, git_diff_file, kwargs, expected_success):
        """Unit test for `run_batch_eval`."""
        git_diff_content = utils.load_file(git_diff_file or "")

        predictions = [
            {
                final_eval.KEY_GITHUB_URL: url,
                final_eval.KEY_GIT_DIFF_CONTENT: git_diff_content,
            },
        ]
        count = final_eval.run_batch_eval(predictions, **kwargs)

        self.assertIsInstance(count, int)
        self.assertEqual(bool(count), expected_success)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    unittest.main()
