"""Unit tests for hash_utils.py."""

from collections import defaultdict
import logging
import os
import re
import unittest

from parameterized import parameterized

from self_debug.common import git_repo, hash_utils, utils


_EMPTY_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
_EMPTY_02_HASH = "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b"

_JAVA_FILE_UTF8_ISSUE = "testdata/WebsocketPingPongSchedulerService.java.utf8-issue"
_JAVA_FILE_UTF8_FIX = "testdata/WebsocketPingPongSchedulerService.java.utf8-fix"
_JAVA_FILE_UTF8_SKIP = "testdata/WebsocketPingPongSchedulerService.java.utf8-skip"

_PWD = os.path.dirname(os.path.abspath(__file__))


class TestHashUtils(unittest.TestCase):
    """Unit tests for hash_utils.py."""

    @parameterized.expand(
        (
            (
                "testdata/mvn_clean_test_00.txt",
                1,
            ),
            (
                "testdata/mvn_clean_test_01.txt",
                -2,
            ),
            (
                "testdata/mvn_clean_test_02.txt",
                32,
            ),
        )
    )
    def test_get_num_test_cases(self, filename, expected_num_test_cases):
        """Unit tests get_num_test_cases."""
        self.assertEqual(
            hash_utils.get_num_test_cases(
                "", utils.load_file(os.path.join(_PWD, filename))
            ),
            expected_num_test_cases,
        )

    _HASH_TESTDATA_POM_XML = (
        "ae5ff85007d4c320336a004f1dcf5199704a55293e678fc0c59d51a86a16f5b1"
    )

    _HASH_TESTDATA_JAVA_FILE_UTF8_FIX = (
        "2a857ae1abf27344b2e02f849040cc7ee61e2494857da1d76e1058875747743e"
    )
    _HASH_TESTDATA_JAVA_FILE_UTF8_SKIP = (
        "e9ad5d33c457797f87ff8834732c47808f5f249ff8472a6ceb24afe24cf7bde0"
    )

    @parameterized.expand(
        (
            (
                "",
                {},
                _EMPTY_HASH,
            ),
            (
                None,
                {},
                _EMPTY_HASH,
            ),
            (
                "".encode(),
                {
                    "encode": False,
                },
                _EMPTY_HASH,
            ),
            (
                "\n",
                {},
                _EMPTY_02_HASH,
            ),
            (
                " ",
                {},
                "36a9e7f1c95b82ffb99743e0c5c4ce95d83c9a430aac59f84ef3cbfab6145068",
            ),
            (
                "hello, world",
                {},
                "09ca7e4eaa6e8ae9c7d261167129184883644d07dfba7cbfbc4c8a2e08360d5b",
            ),
            (
                "Hello, world",
                {},
                "4ae7c3b6ac0beff671efa8cf57386151c06e58ca53a78d83f36107316cec125f",
            ),
            # Read a file
            (
                utils.load_file(os.path.join(_PWD, "testdata/pom.xml")),
                {},
                _HASH_TESTDATA_POM_XML,
            ),
            (
                utils.load_file(os.path.join(_PWD, "testdata/pom.xml"), mode="rb"),
                {
                    "encode": False,
                },
                _HASH_TESTDATA_POM_XML,
            ),
            # UTF-8 issue
            (
                utils.load_file(os.path.join(_PWD, _JAVA_FILE_UTF8_ISSUE), mode="rb"),
                {
                    "encode": False,
                },
                "31bbe802ad851063553e9e097c2c8efa7f567daba14938126be1d0e70a5ff0af",
            ),
            (
                utils.load_file(os.path.join(_PWD, _JAVA_FILE_UTF8_FIX)),
                {},
                _HASH_TESTDATA_JAVA_FILE_UTF8_FIX,
            ),
            (
                utils.load_file(os.path.join(_PWD, _JAVA_FILE_UTF8_SKIP)),
                {},
                _HASH_TESTDATA_JAVA_FILE_UTF8_SKIP,
            ),
            # - Fix on the fly
            (
                utils.load_file(os.path.join(_PWD, _JAVA_FILE_UTF8_ISSUE)),
                {},
                _HASH_TESTDATA_JAVA_FILE_UTF8_SKIP,
            ),
            (
                utils.load_file(os.path.join(_PWD, _JAVA_FILE_UTF8_ISSUE), fix=""),
                {},
                _EMPTY_HASH,
            ),
            (
                utils.load_file(
                    os.path.join(_PWD, _JAVA_FILE_UTF8_ISSUE), fix="ignore"
                ),
                {},
                _HASH_TESTDATA_JAVA_FILE_UTF8_SKIP,
            ),
            (
                utils.load_file(os.path.join(_PWD, _JAVA_FILE_UTF8_ISSUE), fix="utf-8"),
                {},
                _HASH_TESTDATA_JAVA_FILE_UTF8_SKIP,
            ),
            (
                utils.load_file(
                    os.path.join(_PWD, _JAVA_FILE_UTF8_ISSUE), fix="latin-1"
                ),
                {},
                "8d310349397d51f6326fe82203737f6273b5b8b9e54d4790f297223b89507918",
            ),
        )
    )
    def test_get_hash(self, info, kwargs, expected_hash):
        """Unit tests get_hash."""
        self.assertEqual(hash_utils.get_hash(info, **kwargs), expected_hash)

    @parameterized.expand(
        (
            (
                _PWD,
                {
                    "num": 1,
                },
                1,
            ),
            (
                _PWD,
                {
                    "num": 2,
                },
                2,
            ),
            (
                _PWD,
                {
                    "num": 10,
                },
                10,
            ),
        )
    )
    def test_get_git_commit_ids(self, root_dir, kwargs, expected_len):
        """Unit tests get_git_commit_ids."""
        output = hash_utils.get_git_commit_ids(git_repo.GitRepo(root_dir), **kwargs)

        self.assertIsInstance(output, tuple)
        self.assertEqual(len(output), expected_len)

        for cid in output:
            self.assertGreater(len(cid), 0)
            self.assertTrue(re.match(r"^[0-9a-f]{40}$", cid))

    _TEST_DATA_HASH = "0891f0cf886cb524a71bd6a8332b75ed6b00d88d009e3375a508d48383b22712"

    _TEST_DATA_METRICS = defaultdict(
        int,
        {
            "repo-num-files-java__EQ__0000": 1,
            "repo-num-loc__EQ__000000": 1,
            "repo-num-test-cases__EQ__-002": 1,
            "repo-num-files-pom-xml__EQ__0003": 1,
            "repo-num-files-root-any-test-java__EQ__0000": 1,
            "repo-num-files-src-test-any-java__EQ__0000": 1,
            "repo-root-dir-exists__EQ__True": 1,
            "repo-root-src-test-dir-exists__EQ__False": 1,
        },
    )

    @parameterized.expand(
        (
            (
                _PWD,
                {
                    "hash_tree": False,
                    "hash_source": False,
                    "hash_pom": False,
                },
                (
                    _EMPTY_HASH,
                    defaultdict(
                        int,
                        {
                            "repo-num-loc__EQ__000000": 1,
                            "repo-num-test-cases__EQ__-002": 1,
                            "repo-root-dir-exists__EQ__True": 1,
                            "repo-root-src-test-dir-exists__EQ__False": 1,
                        },
                    ),
                ),
            ),
            (
                _PWD,
                {
                    "hash_tree": False,
                    "hash_source": True,
                    "hash_pom": False,
                },
                (
                    _EMPTY_HASH,
                    defaultdict(
                        int,
                        {
                            "repo-num-loc__EQ__000000": 1,
                            "repo-num-test-cases__EQ__-002": 1,
                            "repo-root-dir-exists__EQ__True": 1,
                            "repo-root-src-test-dir-exists__EQ__False": 1,
                            "repo-num-files-java__EQ__0000": 1,
                            "repo-num-files-root-any-test-java__EQ__0000": 1,
                            "repo-num-files-src-test-any-java__EQ__0000": 1,
                        },
                    ),
                ),
            ),
            (
                os.path.join(_PWD, "subdir-does-not-exist"),
                {
                    "hash_tree": True,
                    "hash_source": True,
                    "hash_pom": False,
                },
                (
                    _EMPTY_HASH,
                    defaultdict(
                        int,
                        {
                            "repo-num-loc__EQ__000000": 1,
                            "repo-num-test-cases__EQ__-002": 1,
                            "repo-root-dir-exists__EQ__False": 1,
                            "repo-root-src-test-dir-exists__EQ__False": 1,
                        },
                    ),
                ),
            ),
            # Non-empty
            (
                os.path.join(_PWD, "testdata"),
                {
                    "hash_tree": False,
                    "hash_source": True,
                    "hash_pom": True,
                },
                (
                    "1de86b870566acd469b206dda0f371c83d19a34713be1a549bcd523e638636cf",
                    _TEST_DATA_METRICS,
                ),
            ),
            (
                os.path.join(_PWD, "testdata"),
                {},
                (
                    _TEST_DATA_HASH,
                    _TEST_DATA_METRICS,
                ),
            ),
            (
                os.path.join(_PWD, "testdata"),
                {
                    "hash_tree": True,
                    "hash_source": True,
                    "hash_pom": True,
                },
                (
                    _TEST_DATA_HASH,
                    _TEST_DATA_METRICS,
                ),
            ),
        )
    )
    def test_get_repo_hash(self, root_dir, kwargs, expected_hash):
        """Unit tests get_repo_hash."""
        self.assertEqual(hash_utils.get_repo_hash(root_dir, **kwargs), expected_hash)

    @parameterized.expand(
        (
            (
                _PWD,
                (),
                {},
                (
                    (
                        "",
                        "",
                    ),
                    ("",),
                    "2025-01-26 19:44:48 +0000",
                ),
            ),
            (
                _PWD,
                (),
                {
                    "first_n": 1,
                    "last_n": 2,
                },
                (
                    ("",),
                    (
                        "",
                        "",
                    ),
                    "2025-01-26 19:44:48 +0000",
                ),
            ),
        )
    )
    def test_get_repo_commit_info(self, root_dir, commits, kwargs, expected_result):
        """Unit tests get_repo_commit_info."""
        output = hash_utils.get_repo_commit_info(
            git_repo.GitRepo(root_dir), commits=commits, **kwargs
        )
        logging.info(output)

        self.assertIsInstance(output, tuple)
        self.assertEqual(len(output), len(expected_result))

        self.assertEqual(output[:-1], expected_result[:-1])
        self.assertGreaterEqual(output[-1], expected_result[-1])

    _NUM_FILES_METRICS = 8

    @parameterized.expand(
        (
            (
                _PWD,
                {},
                5 + _NUM_FILES_METRICS,
            ),
            (
                _PWD,
                {
                    "first_n": 3,
                    "last_n": 2,
                },
                7 + _NUM_FILES_METRICS,
            ),
        )
    )
    def test_get_repo_snapshot_info(self, root_dir, kwargs, expected_len):
        """Unit tests get_repo_snapshot_info."""
        output = hash_utils.get_repo_snapshot_info(git_repo.GitRepo(root_dir), **kwargs)
        logging.info(output)

        self.assertIsInstance(output, dict)
        self.assertEqual(len(output), expected_len)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    unittest.main()
