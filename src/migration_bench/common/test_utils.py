"""Unit tests for utils.py."""

import logging
import os
import shutil
import tempfile
from typing import Any, Sequence, Tuple
import unittest

from parameterized import parameterized

from migration_bench.common import utils

_PWD = os.path.dirname(os.path.abspath(__file__))

CONTENTS = (
    "# Greetings.",
    "def hello(",
    "    name: str,",
    ") -> str:",
    "return 'hello ' +  name",
    "",
    "",
    "# Other functions.",
)


class TestUtils(unittest.TestCase):
    """Unit tests for utils.py."""

    @parameterized.expand(
        [
            ("ls", True, "utils.py", True, False),
            ("echo 'hello world'", False, "hello world", True, True),
        ]
    )
    def test_run_command_success(
        self, command, enable, expected_output, expected_success, exact
    ):
        """Unit tests run_command and `timeit_seconds`."""
        with utils.TimeItInSeconds(command, enable, logging.info) as timer:
            output, success = utils.run_command(command)

        logging.info("Output:< %s>.", output)
        self.assertIsInstance(output, str)
        if exact:
            self.assertEqual(output, expected_output)
        else:
            self.assertTrue(expected_output in output)

        self.assertEqual(success, expected_success)

        # Check for timeit_seconds.
        for runtime in (timer.seconds, timer.minutes):
            if enable:
                self.assertIsInstance(runtime, float)
                self.assertGreater(runtime, 0)
            else:
                self.assertIsNone(runtime)

    def test_run_command_failure(self):
        """Unit tests run_command."""
        output, success = utils.run_command("nonexistent_command")
        self.assertIsInstance(output, Exception)
        self.assertFalse(success)

    @parameterized.expand(
        (
            (
                "./",
                {},
                None,
                "common",
            ),
            (
                "../eval",
                # `prefix` doesn't seem to work.
                {
                    "prefix": "any-prefix--r-",
                    "suffix": "any-suffix",
                },
                "any-prefix--r-",
                "any-suffix/eval",
            ),
        )
    )
    def test_copy_dir(self, work_dir, kwargs, expected_startswith, expected_endswith):
        """Unit tests copy_dir."""
        os.chdir(_PWD)

        new_dir_00 = utils.copy_dir(work_dir, **kwargs)
        self.assertIsInstance(new_dir_00, str)

        new_dir_01 = utils.copy_dir(work_dir, **kwargs)
        self.assertIsInstance(new_dir_01, str)

        self.assertNotEqual(new_dir_00, new_dir_01)
        for w_dir in (new_dir_00, new_dir_01):
            if expected_startswith:
                self.assertTrue(
                    os.path.basename(os.path.dirname(w_dir)).startswith(
                        expected_startswith
                    )
                )
            if expected_endswith:
                self.assertTrue(w_dir.endswith(expected_endswith))

            shutil.rmtree(w_dir)

    def test_rw_file(self):
        """Unit test for load_file, export_file."""
        line = "Hello, \n world.\n"

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_file = os.path.join(temp_dir, "test.pbtxt")

            # Idempotent.
            for _ in range(2):
                utils.export_file(tmp_file, line)
                self.assertEqual(utils.load_file(tmp_file), line)
                self.assertIsNone(utils.load_file(f"{tmp_file}.not-exists"))

            content = line
            # Not idempotent.
            for _ in range(2):
                utils.export_file(tmp_file, line, "a")
                content += line
                self.assertEqual(utils.load_file(tmp_file), content)

    def test_rw_json_file(self):
        """Unit test for load_json, export_json."""
        data = {
            "str": "Hello World",
            "int": 1,
            "list": ["Any", "list", "is", "fine", 1, 2.0],
            "tuple": ("hello", 888),
        }
        data_copy = {k: list(v) if isinstance(v, tuple) else v for k, v in data.items()}

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_file = os.path.join(temp_dir, "test.json")

            # Idempotent.
            for _ in range(2):
                utils.export_json(tmp_file, data)
                self.assertEqual(utils.load_json(tmp_file), data_copy)

                self.assertIsNone(utils.load_json(f"{tmp_file}.not-exists"))

    _PBTXT_FILES = (
        "testdata/batch.pbtxt",
        "testdata/config.pbtxt",
        "testdata/dataset.pbtxt",
        "testdata/llm_agent.pbtxt",
        "testdata/llm_parser.pbtxt",
        "testdata/model.pbtxt",
    )

    @parameterized.expand(
        (
            (
                "*.xproj",
                (),
            ),
            (
                r"\*.java",
                (),
            ),
            (
                "*.pbtxt",
                _PBTXT_FILES,
            ),
            (
                r"\*.pbtxt",
                _PBTXT_FILES,
            ),
            (
                r"test_\*.py",
                (
                    "test_file_utils.py",
                    "test_git_repo.py",
                    "test_hash_utils.py",
                    "test_hf_utils.py",
                    "test_maven_utils.py",
                    "test_utils.py",
                ),
            ),
        )
    )
    def test_find_file(self, regex, expected_files):
        """Unit test for normalize_file."""
        files = utils.find_files(_PWD, regex)

        self.assertIsInstance(files, tuple)
        self.assertEqual(len(files), len(expected_files))
        for file, expected_file in zip(files, expected_files):
            self.assertTrue(file.startswith(_PWD))
            self.assertTrue(file.endswith(expected_file), f"{file} vs {expected_file}")

    @parameterized.expand(
        (
            # Plain text.
            (
                "hello, world.",
                True,
                False,
                None,
            ),
            (
                "hello, world.",
                False,  # No such file.
                False,
                None,
            ),
            (
                None,  # Filename is None.
                False,  # No such file.
                False,
                None,
            ),
            (
                "hello,\nworld\n",
                True,
                False,
                None,
            ),
            (
                "hello,\nworld\n",
                True,
                False,
                None,
            ),
            # \r.
            (
                "hello,\r world.\r",
                True,
                True,
                "hello, world.",
            ),
            (
                "  hello,\r\nworld.\r test\n",
                True,
                True,
                "  hello,\nworld. test\n",
            ),
        )
    )
    def test_normalize_file(self, content, write, expected_changed, expected_content):
        """Unit test for normalize_file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_file = os.path.join(temp_dir, "test.txt")
            if write:
                utils.export_file(tmp_file, content)
            elif content is None:
                tmp_file = None

            self.assertEqual(utils.normalize_file(tmp_file), expected_changed)
            if write:
                self.assertTrue(os.path.exists(tmp_file))
                maybe_updated_content = utils.load_file(tmp_file)
                self.assertEqual(maybe_updated_content, expected_content or content)
            elif content is None:
                self.assertIsNone(tmp_file)
            else:
                self.assertFalse(os.path.exists(tmp_file))

    @parameterized.expand(
        (
            (
                "/dir/should-not-exist",
                0,
            ),
            (
                _PWD,
                4,
            ),
        )
    )
    def test_count_dirs(self, dirname: str, expected_num_dirs):
        """Unit test for count_dirs."""
        self.assertEqual(utils.count_dirs(dirname), expected_num_dirs)

    @parameterized.expand(
        (
            # Given a valid line number.
            (
                CONTENTS,
                5,
                0,
                0,
                lambda x: f"{x}  # <<< Line with errors",
                (
                    "return 'hello ' +  name  # <<< Line with errors",
                    "return 'hello ' +  name",
                ),
            ),
            (
                CONTENTS,
                5,
                1,
                1,
                lambda x: f"{x}  # <<< Line with errors",
                (
                    ") -> str:\nreturn 'hello ' +  name  # <<< Line with errors\n",
                    "return 'hello ' +  name",
                ),
            ),
            (
                CONTENTS,
                5,
                3,
                3,
                None,
                (
                    "def hello(\n"
                    "    name: str,\n"
                    ") -> str:\n"
                    "return 'hello ' +  name\n"
                    "\n"
                    "\n"
                    "# Other functions.",
                    "return 'hello ' +  name",
                ),
            ),
            (
                CONTENTS,
                5,
                30,
                30,
                lambda x: f"{x}  # <<< Line with errors",
                (
                    "# Greetings.\n"
                    "def hello(\n"
                    "    name: str,\n"
                    ") -> str:\n"
                    "return 'hello ' +  name  # <<< Line with errors\n"
                    "\n"
                    "\n"
                    "# Other functions.",
                    "return 'hello ' +  name",
                ),
            ),
            # Given an invalid line number.
            (
                CONTENTS,
                0,
                0,
                0,
                None,
                ("", ""),
            ),
            (
                CONTENTS,
                100,
                0,
                0,
                None,
                ("", ""),
            ),
        )
    )
    def test_get_snippet(
        self,
        contents: Sequence[str],
        line_number: int,
        before: int,
        after: int,
        line_function: Any,
        expected_content: Tuple[str, str],
    ):
        """Unit test for get_snippet."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_file = os.path.join(temp_dir, "test.txt")
            utils.export_file(tmp_file, utils.NEW_LINE.join(contents))

            logging.info(expected_content)
            self.assertEqual(
                utils.get_snippet(tmp_file, line_number, before, after, line_function),
                expected_content,
            )

    @parameterized.expand(
        (
            # Invalid
            ("https://github.com", False),
            ("https://github.com/", False),
            # Valid
            ("https://github.com/klee-contrib/kinetix", True),
            ("https://github.com/klee-contrib/kinetix/", True),
            # - Redirected
            ("https://github.com/lbruun/Pre-Liquibase", True),
            ("https://github.com/lbruun-net/Pre-Liquibase", True),
            ("https://github.com/maciejwalkowiak/wiremock-spring-boot", True),
            ("https://github.com/wiremock/wiremock-spring-boot", True),
            # Valid => Invalid
            ("https://github.com/klee-contrib-xyz/kinetix", False),
            ("https://github.com/klee-contrib/kinetix-xyz", False),
            ("https://github.com/klee-contrib/kinetix/xyz", False),
        )
    )
    def test_is_valid_github_url(self, url: str, expected_valid: bool):
        """Unit test for is_valid_github_url."""
        self.assertEqual(utils.is_valid_github_url(url), expected_valid)

    _NO_LICENSE = "License not found"

    @parameterized.expand(
        (
            # Invalid
            ("github.com", None),
            ("https://github.com/", _NO_LICENSE),
            # Valid
            ("https://github.com/klee-contrib/kinetix/", "Apache-2.0"),
            # - Redirected
            ("https://github.com/lbruun/Pre-Liquibase", "Apache-2.0"),
            ("https://github.com/maciejwalkowiak/wiremock-spring-boot", "MIT"),
            # Valid => Invalid
            ("https://github.com/klee-contrib-xyz/kinetix", _NO_LICENSE),
        )
    )
    def test_get_github_license(self, url: str, expected_license: str):
        """Unit test for get_github_license."""
        self.assertEqual(utils.get_github_license(url), expected_license)

    @parameterized.expand(
        (
            (
                """
@@ -10,0 +11 @@ llm_agent {
+      temperature: 0.
@@ -44,0 +46 @@ prompt_manager {
+  restart_messages_len_gt: 10
@@ -62 +64 @@ llm_parser_by_group {
-max_iterations: 50
+max_iterations: 60
@@ -53,2 +53,2 @@ class GitRepo
                """,
                (
                    ((10, 10), (11, 12)),
                    ((44, 44), (46, 47)),
                    ((62, 63), (64, 65)),
                    ((53, 55), (53, 55)),
                ),
            ),
            (
                """
@@ -44 +46,0 @@ prompt_manager {
-  restart_messages_len_gt: 10
                """,
                (((44, 45), (46, 46)),),
            ),
        )
    )
    def test_get_git_line_changes(
        self, output: str, expected_line_changes: Tuple[Tuple[int, int]]
    ):
        """Unit test for get_git_line_changes."""
        self.assertEqual(utils.get_git_line_changes(output), expected_line_changes)


class TestUtils2(unittest.TestCase):
    """Unit tests for utils.py."""

    @parameterized.expand(
        (
            (
                (),
                {},
            ),
            (
                (
                    TestUtils,
                    TestUtils,
                ),
                {
                    "TestUtils": TestUtils,
                    "test_utils": TestUtils,
                },
            ),
            (
                (TestUtils,),
                {
                    "TestUtils": TestUtils,
                    "test_utils": TestUtils,
                },
            ),
            (
                (
                    TestUtils,
                    unittest.TestCase,
                ),
                {
                    "TestCase": unittest.TestCase,
                    "TestUtils": TestUtils,
                    "test_case": unittest.TestCase,
                    "test_utils": TestUtils,
                },
            ),
        )
    )
    def test_get_class_names(self, classes, expected_names):
        """Unit test for get_class_names."""
        self.assertEqual(utils.get_class_names(classes), expected_names)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    unittest.main()
