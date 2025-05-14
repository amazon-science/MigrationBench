"""Unit tests for clean_up.py."""

import logging
import os
import unittest

from parameterized import parameterized

from self_debug.common import clean_up, utils

_PWD = os.path.dirname(os.path.abspath(__file__))


class TestCleanUp(unittest.TestCase):
    """Unit tests for clean_up.py."""

    def test_aws_internal_begin(self):
        """Unit test for global var: aws_internal_begin."""
        self.assertEqual(
            clean_up.AWS_INTERNAL_BEGIN,
            (
                "# AWS_INTERNAL_ONLY: BEGIN",
                "// AWS_INTERNAL_ONLY: BEGIN",
            ),
        )

    def test_aws_internal_end(self):
        """Unit test for global var: aws_internal_end."""
        self.assertEqual(
            clean_up.AWS_INTERNAL_END,
            (
                "# AWS_INTERNAL_ONLY: END",
                "// AWS_INTERNAL_ONLY: END",
            ),
        )

    @parameterized.expand(
        (
            (
                "Hello, world\nHi",
                "Hello, world\nHi",
            ),
            # Internal only
            (
                "\n".join(
                    (
                        "Hello, world",
                        "# AWS_INTERNAL_ONLY: BEGIN",
                        "Hi",
                        "To be removed",
                        "# AWS_INTERNAL_ONLY: END",
                    )
                ),
                "Hello, world",
            ),
            (
                "\n".join(
                    (
                        "# AWS_INTERNAL_ONLY: BEGIN",
                        "Hi",
                        "To be removed",
                        "# AWS_INTERNAL_ONLY: END",
                        "Hello, world",
                        "# AWS_INTERNAL_ONLY: BEGIN",
                        "Hi",
                        "To be removed",
                        "# AWS_INTERNAL_ONLY: END",
                        "Hi",
                    )
                ),
                "Hello, world\nHi",
            ),
            # - With exernal only
            (
                "\n".join(
                    (
                        "Hello, world",
                        "# AWS_INTERNAL_ONLY: BEGIN",
                        "xyz",
                        "# AWS_EXTERNAL_ONLY: BEGIN",
                        "# Hi  # Real comment",
                        "##  Another real comment",
                        "#     pass",
                        "# AWS_EXTERNAL_ONLY: END",
                        "# AWS_INTERNAL_ONLY: END",
                        "extra",
                    )
                ),
                "Hello, world\nHi  # Real comment\n# Another real comment\n    pass\nextra",
            ),
            (
                "\n".join(
                    (
                        "Hello, world",
                        "# AWS_INTERNAL_ONLY: BEGIN",
                        "xyz",
                        "# AWS_EXTERNAL_ONLY: BEGIN",
                        "# Hi  # Real comment",
                        "##  Another real comment",
                        "#     pass",
                        "# AWS_EXTERNAL_ONLY: END",
                        "removed",
                        "# AWS_INTERNAL_ONLY: END",
                        "extra",
                    )
                ),
                "Hello, world\nHi  # Real comment\n# Another real comment\n    pass\nextra",
            ),
        )
    )
    def test_cleanup_file(self, content, expected_content):
        """Unit test for cleanup_file."""
        self.assertEqual(
            clean_up.cleanup_file(None, content=content), (None, expected_content)
        )
        self.assertEqual(
            clean_up.cleanup_file("", content=content), ("", expected_content)
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    unittest.main()
