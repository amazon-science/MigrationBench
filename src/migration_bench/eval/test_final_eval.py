"""Unit tests for final_eval.py."""

import logging
import os
import unittest

from parameterized import parameterized

from self_debug.common import utils
from self_debug.eval import final_eval

_PWD = os.path.dirname(os.path.abspath(__file__))

STATS = {
    "GitRepo::00-start": 1,
    "GitRepo::01--00--branch=<* s0-pom-try000-idx0000--4a9caf847b9488e9d3ff55f90d5071a1904ece28>": 1,
    "GitRepo::01--01--branch-len=<004>": 1,
    "GitRepo::01--02--branches=<mainline--self-debugging-plus,master,ported,* s0-pom-try000-idx0000--4a9caf847b9488e9d3ff55f90d5071a1904ece28>": 1,
    "GitRepo::02--status--<nothing to commit, working tree clean>": 1,
    "GitRepo::03--untracked--len=<000>": 1,
    "GitRepo::03--untracked-01--dir-count=<000>": 1,
    "GitRepo::04-finish": 1,
    "GitRepo::BaseCommit::00-start": 1,
    "GitRepo::BaseCommit::00-start-at-commit-index__EQ__0000": 1,
    "GitRepo::BaseCommit::00-start-at-commit-index__EQ__0000-0004": 1,
    "GitRepo::BaseCommit::00-start-num-commits__EQ__0004": 1,
    "GitRepo::BaseCommit::10-keep-repo__EQ__True": 1,
    "GitRepo::BaseCommit::11-keep-repo-base-commit-id__EQ__4a9caf847b9488e9d3ff55f90d5071a1904ece28": 1,
    "GitRepo::BaseCommit::11-keep-repo-index__EQ__0000": 1,
    "GitRepo::BaseCommit::11-keep-repo-total-len__EQ__0004": 1,
    "GitRepo::BaseCommit::11-keep-repo-url__EQ__https://github.com/danielprinz/jacoco-maven-multi-module____4a9caf847b9488e9d3ff55f90d5071a1904ece28": 1,
    "GitRepo::RepoSnapshot::repo-num-files-java__EQ__0004": 1,
    "GitRepo::RepoSnapshot::repo-num-files-pom-xml__EQ__0004": 1,
    "GitRepo::RepoSnapshot::repo-num-files-root-any-test-java__EQ__0002": 1,
    "GitRepo::RepoSnapshot::repo-num-files-src-test-any-java__EQ__0000": 1,
    "GitRepo::RepoSnapshot::repo-num-loc__EQ__000083": 1,
    "GitRepo::RepoSnapshot::repo-num-test-cases__EQ__-002": 1,
    "GitRepo::RepoSnapshot::repo-root-dir-exists__EQ__True": 1,
    "GitRepo::RepoSnapshot::repo-root-src-test-dir-exists__EQ__False": 1,
    "GitRepo::RepoSnapshot::repo_commit_first_00__EQ__4a9caf847b9488e9d3ff55f90d5071a1904ece28": 1,
    "GitRepo::RepoSnapshot::repo_commit_first_01__EQ__3e6273597be39aa3372e8a136ad7de25e8c272aa": 1,
    "GitRepo::RepoSnapshot::repo_commit_last_00__EQ__fb46de97a791d855d2364559bc5f2b535012279c": 1,
    "GitRepo::RepoSnapshot::repo_snapshot_hash__EQ__61a2b845d52cb095d9c30ba0f93ae6155ba15271a41b4b821c0c60ada2c1d4d0": 1,
    "GitRepo::RepoSnapshot::repo_snapshot_update_time__EQ__2018-04-14 22:35:55 +0200": 1,
    "GitRepo::java_version-none": 1,
    "GitRepo::num_pom_xml": 4,
    "GitRepo::num_pom_xml__EQ__004": 1,
    "SparkUtils::Repo::Download=False": 1,
}

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
                final_eval.KEY_PREFIX_GITHUB_URL,
                "https://github.com/danielprinz/jacoco-maven-multi-module____4a9caf847b9488e9d3ff55f90d5071a1904ece28",
            ),
            (
                final_eval.KEY_PREFIX_NUM_TESTS,
                "-002",
            ),
        )
    )
    def test_get_key(self, prefix, expected_value):
        """Unit test for `get_key`."""
        self.assertEqual(final_eval.get_key(STATS, prefix), expected_value)

    @parameterized.expand(
        (
            (
                "https://github.com/danielprinz/jacoco-maven-multi-module",
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
    def test_run_eval(self, url, git_diff_file, kwargs, expected_success):
        """Unit test for `run_eval`."""
        self.assertEqual(
            final_eval.run_eval(url, git_diff_file, **kwargs), expected_success
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    unittest.main()
