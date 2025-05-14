"""Unit tests for utils.py."""

import logging
import unittest

from parameterized import parameterized

from self_debug.lang.base import utils


class TestUtils(unittest.TestCase):
    """Unit tests for utils.py."""

    _REMOVE_EMPTY_LINES = {
        "remove_empty_lines": True,
        "remove_strip_lines": True,
    }

    @parameterized.expand(
        (
            (
                "",
                {},
                (),
            ),
            (
                "  \n",
                {},
                (),
            ),
            (
                "echo 'hello world'  \nhello   ",
                {},
                (
                    "echo 'hello world'  ",
                    "hello",
                ),
            ),
            (
                "hello\n\n \n hello",
                {},
                (
                    "hello",
                    "",
                    " \n hello",
                ),
            ),
            (
                "hello\n\n \n hello",
                {
                    "remove_empty_lines": True,
                    # "remove_strip_lines": False,
                },
                (
                    "hello",
                    " \n hello",
                ),
            ),
            (
                "hello\n\n \n hello",
                _REMOVE_EMPTY_LINES,
                (
                    "hello",
                    " hello",
                ),
            ),
            (
                "  test  \necho 'hello world'  \n hello\n   \n  hello\nhello, world.",
                {},
                (
                    "test  ",
                    "echo 'hello world'  \n hello\n   \n  hello",
                    "hello, world.",
                ),
            ),
            (
                "  test  \necho 'hello world'  \n hello\n   \n  hello\nhello, world.",
                _REMOVE_EMPTY_LINES,
                (
                    "test  ",
                    "echo 'hello world'  \n hello\n  hello",
                    "hello, world.",
                ),
            ),
        )
    )
    def test_split_errors(self, stdout, kwargs, expected_errors):
        """Unit tests for split_errors."""
        self.assertEqual(utils.split_errors(stdout, **kwargs), expected_errors)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    unittest.main()
