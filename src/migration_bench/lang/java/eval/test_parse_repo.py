"""Unit tests for parse_repo.py."""

import logging
import os
import unittest

from parameterized import parameterized

from migration_bench.common import utils
from migration_bench.lang.java.eval import parse_repo

_PWD = os.path.dirname(os.path.abspath(__file__))

_PWD_TEST_SUB_DIR = {
    "test_sub_dir": "testdata",
}


class TestParseRepo(unittest.TestCase):
    """Unit tests for parse_repo.py."""

    @parameterized.expand(
        (
            # Invalid
            (
                os.path.join(_PWD, "test"),
                {},
                {},
            ),
            # Valid
            (
                _PWD,
                {},
                {},
            ),
            (
                _PWD,
                _PWD_TEST_SUB_DIR,
                {
                    os.path.join(_PWD, "testdata/AstParser.java"): (
                        ("class", "AstParser"),
                        ("method", ("main", False)),
                        ("class", "FileAnalyzerVisitor"),
                        ("method", ("addTag", False)),
                        ("method", ("getClassDecSignature", False)),
                        ("method", ("getClassSignature", False)),
                        ("method", ("visit", False)),
                        ("method", ("visit", False)),
                    ),
                    os.path.join(_PWD, "testdata/LabelManager.java"): (
                        ("interface", "LabelManager"),
                        ("method", ("setLocale", False)),
                        ("method", ("get", False)),
                    ),
                },
            ),
        )
    )
    def test_get_repo_test_files(self, filename, kwargs, expected_tests):
        """Unit test for get_repo_test_files."""
        self.assertEqual(
            parse_repo.get_repo_test_files(filename, **kwargs), expected_tests
        )

    _BRANCHES = {
        "lhs_branch": None,
        "rhs_branch": None,
    }

    @parameterized.expand(
        (
            # Invalid
            (
                os.path.join(_PWD, "test"),
                {},
                (True, 0, True),
            ),
            (
                os.path.join(_PWD, "test"),
                _BRANCHES,
                (True, None, None),
            ),
            # Valid
            (
                _PWD,
                {
                    **_BRANCHES,
                    **_PWD_TEST_SUB_DIR,
                    **{
                        "early_stop": False,
                    },
                },
                (True, 2, True),
            ),
        )
    )
    def test_same_repo_test_files(self, root_dir, kwargs, expected_same):
        """Unit test for same_repo_test_files."""
        self.assertEqual(
            parse_repo.same_repo_test_files(root_dir, **kwargs), expected_same
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    unittest.main()
