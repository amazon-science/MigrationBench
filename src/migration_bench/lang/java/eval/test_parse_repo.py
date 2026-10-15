"""Unit tests for parse_repo.py."""

import logging
import os
import shutil
import subprocess
import tempfile
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
            # Invalid: The lhs branch cannot be read.
            (
                os.path.join(_PWD, "test"),
                {},
                (False, None, False),
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


_TEST_FILE = """package a;

import org.junit.Test;

public class {name} {{
    @Test
    public void testOne() {{}}

    @Test
    public void testTwo() {{}}
}}
"""

_SINGLE_MODULE = ("src/test/java/a/FooTest.java", "src/test/java/a/BarTest.java")
_MULTI_MODULE = (
    "core/src/test/java/a/FooTest.java",
    "web/src/test/java/a/BarTest.java",
)

_GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@test"]


def _write_test_file(root_dir, path, content=None):
    abs_path = os.path.join(root_dir, path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    if content is None:
        content = _TEST_FILE.format(name=os.path.basename(path)[: -len(".java")])

    utils.export_file(abs_path, content)


def _remove_test_methods(root_dir, path):
    _write_test_file(root_dir, path, "package a;\n\npublic class Gutted {}\n")


class TestSameRepoTestFilesGit(unittest.TestCase):
    """Compare the working tree against test files committed in a git repo."""

    def _repo(self, paths):
        temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(temp_dir.cleanup)
        root_dir = temp_dir.name

        for path in paths:
            _write_test_file(root_dir, path)

        for command in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "base"]):
            subprocess.run(_GIT + command, cwd=root_dir, check=True)

        commit_id = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root_dir,
                check=True,
                stdout=subprocess.PIPE,
            )
            .stdout.decode()
            .strip()
        )
        return root_dir, commit_id

    @parameterized.expand(
        (
            ("single_module_unchanged", _SINGLE_MODULE, (), (), True),
            ("multi_module_unchanged", _MULTI_MODULE, (), (), True),
            (
                "single_module_methods_removed",
                _SINGLE_MODULE,
                (),
                _SINGLE_MODULE[:1],
                False,
            ),
            (
                "multi_module_methods_removed",
                _MULTI_MODULE,
                (),
                _MULTI_MODULE[:1],
                False,
            ),
            (
                "single_module_file_deleted",
                _SINGLE_MODULE,
                _SINGLE_MODULE[1:],
                (),
                False,
            ),
            ("single_module_all_deleted", _SINGLE_MODULE, _SINGLE_MODULE, (), False),
            ("multi_module_file_deleted", _MULTI_MODULE, _MULTI_MODULE[1:], (), False),
            ("multi_module_all_deleted", _MULTI_MODULE, _MULTI_MODULE, (), False),
        )
    )
    def test_same_repo_test_files(self, _, paths, deleted, gutted, expected_same):
        """Unit test for same_repo_test_files against a base commit."""
        root_dir, commit_id = self._repo(paths)
        for path in deleted:
            os.remove(os.path.join(root_dir, path))
        for path in gutted:
            _remove_test_methods(root_dir, path)

        # A file count or name mismatch returns None, which callers treat as False.
        self.assertEqual(
            bool(parse_repo.same_repo_test_files(root_dir, lhs_branch=commit_id)[-1]),
            expected_same,
        )

    def test_working_tree_unchanged(self):
        """The working tree is not checked out or cleaned."""
        root_dir, commit_id = self._repo(_SINGLE_MODULE)
        _remove_test_methods(root_dir, _SINGLE_MODULE[0])

        parse_repo.same_repo_test_files(root_dir, lhs_branch=commit_id)

        self.assertIn(
            "Gutted", utils.load_file(os.path.join(root_dir, _SINGLE_MODULE[0]))
        )

    def test_added_test_file(self):
        """A new test file is a mismatch."""
        root_dir, commit_id = self._repo(_SINGLE_MODULE)
        _write_test_file(root_dir, "src/test/java/a/NewTest.java")

        self.assertFalse(
            parse_repo.same_repo_test_files(root_dir, lhs_branch=commit_id)[-1]
        )

    def test_missing_git_dir(self):
        """Without git history, the base commit cannot be read."""
        root_dir, commit_id = self._repo(_SINGLE_MODULE)
        _remove_test_methods(root_dir, _SINGLE_MODULE[0])
        shutil.rmtree(os.path.join(root_dir, ".git"))

        self.assertEqual(
            parse_repo.same_repo_test_files(root_dir, lhs_branch=commit_id),
            (False, None, False),
        )

    def test_unknown_commit(self):
        """An unknown base commit cannot be read."""
        root_dir, _ = self._repo(_SINGLE_MODULE)

        self.assertEqual(
            parse_repo.same_repo_test_files(root_dir, lhs_branch="0" * 40),
            (False, None, False),
        )

    def test_replace_ref_ignored(self):
        """A `git replace` ref does not substitute the base commit's test files."""
        root_dir, commit_id = self._repo(_SINGLE_MODULE)
        os.remove(os.path.join(root_dir, _SINGLE_MODULE[1]))
        subprocess.run(
            _GIT + ["commit", "-q", "-a", "-m", "fake"], cwd=root_dir, check=True
        )
        subprocess.run(_GIT + ["replace", commit_id, "HEAD"], cwd=root_dir, check=True)

        self.assertFalse(
            parse_repo.same_repo_test_files(root_dir, lhs_branch=commit_id)[-1]
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    unittest.main()
