"""Unit tests for utils.py."""

import logging
from typing import Any, Optional, Sequence
import unittest

from parameterized import parameterized

from self_debug.lm import utils


FEEDBACK_FN_00 = lambda x: f"<<{x}>>"  # pylint: disable=unnecessary-lambda-assignment
FEEDBACK_FN_01 = utils.FEEDBACK_MULTI_LINE


class TestUtils(unittest.TestCase):
    """Unit tests for utils.py."""

    @parameterized.expand(
        (
            ("", None, None),
            ("", FEEDBACK_FN_01, None),
            ("\n \t", FEEDBACK_FN_00, None),
            # Non empty.
            ("msg", None, "[Feedback Start]msg[Feedback End]"),
            ("~msg~", FEEDBACK_FN_00, "<<~msg~>>"),
            ("~msg~", FEEDBACK_FN_01, "[Feedback Start]\n~msg~\n[Feedback End]"),
        )
    )
    def test_get_feedback(
        self, msg: str, fmt_fn: Any, expected_feedback: Optional[str]
    ):
        """Unit tests for get_feedback."""
        self.assertEqual(utils.get_feedback(msg, fmt_fn), expected_feedback)

    @parameterized.expand(
        (
            (
                (
                    "",
                    "\n \t",
                    "",
                ),
                None,
                None,
            ),
            # Non empty.
            (
                (
                    "",
                    " hello. \n world ",
                    "",
                ),
                None,
                "[Feedback Start]hello. \n world[Feedback End]",
            ),
            (
                (
                    "",
                    " hello. \n world ",
                    "",
                ),
                FEEDBACK_FN_01,
                "[Feedback Start]\nhello. \n world\n[Feedback End]",
            ),
            (
                (
                    "",
                    " hello. ",
                    "",
                    " world ",
                ),
                FEEDBACK_FN_01,
                "[Feedback Start]\nhello.\n[Feedback End]\n"
                "[Feedback Start]\nworld\n[Feedback End]",
            ),
        )
    )
    def test_collect_feedback(
        self, msgs: Sequence[str], fmt_fn: Any, expected_feedback: Optional[str]
    ):
        """Unit tests for collect_feedback."""
        self.assertEqual(utils.collect_feedback(msgs, fmt_fn), expected_feedback)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    unittest.main()
