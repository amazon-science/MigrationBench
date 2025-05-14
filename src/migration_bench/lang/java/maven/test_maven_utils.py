"""Unit tests for maven_utils.py."""

import logging
import os
from typing import Optional, Sequence, Union
import unittest

from parameterized import parameterized

from self_debug.common import utils
from self_debug.lang.java.maven import maven_utils


NEW_LINE = maven_utils.NEW_LINE


TEXTS = (
    " Hello  ",  # Will be appended.
    "Claude 3",  # Will be appended.
    "[ERROR]    World. ",
    "[ERROR] More than 30 chars line.",
    "[ERROR] Very long text here with more than 50 chars.",
    # Will be removed.
    "          ",
    "NOTE: <any text>",
    "WARNING: <any text>",
    "Progress<any text>",
    "Downloaded<any text>",
    "Downloading<any text>",
    "[ERROR] WARNING: Unknown module:<any text>",
)

EXPECTED_TEXTS_MAX_30 = (
    "[ERROR]    World.",
    " Hello",
    "Claude 3",
)

EXPECTED_TEXTS_MAX_50 = (
    "[ERROR]    World.",
    "[ERROR] More than 30 chars line.",
    " Hello",
    "Claude 3",
)

EXPECTED_TEXTS_MAX_100 = (
    "[ERROR]    World.",
    "[ERROR] More than 30 chars line.",
    "[ERROR] Very long text here with more than 50 chars.",
    " Hello",
    "Claude 3",
)


class TestMavenUtils(unittest.TestCase):
    """Unit tests for maven_utils.py."""

    @parameterized.expand(
        (
            # Show up 0 times.
            (
                TEXTS,
                "Line doesn't exist at all",
                {},
                None,
            ),
            # Show up 0 times: No multi line support.
            (
                TEXTS,
                " Hello  \nClaude 3",
                {},
                None,
            ),
            # Show up once.
            (
                TEXTS,
                " Hello  ",
                {},
                0,
            ),
            # Show up twice.
            (
                TEXTS + ("Claude 3",),
                "Claude 3",
                {},
                1,
            ),
            ### Start from non zero index.
            # Show up once.
            (
                TEXTS,
                " Hello  ",
                {"start": 1},
                None,
            ),
            # Show up twice.
            (
                TEXTS + ("Claude 3",),
                "Claude 3",
                {"start": 2},
                len(TEXTS),
            ),
        )
    )
    def test_find_first_line_match(
        self,
        lines: Sequence[str],
        match: str,
        kwargs,
        expected_index: Optional[int],
    ):
        """Unit tests for find_first_line_match."""
        self.assertEqual(
            maven_utils.find_first_line_match(lines, match, **kwargs), expected_index
        )

    @parameterized.expand(
        (
            (
                TEXTS,
                (),
                30,
                EXPECTED_TEXTS_MAX_30,
            ),
            (
                (),
                TEXTS,
                50,
                EXPECTED_TEXTS_MAX_50,
            ),
            (
                (),
                TEXTS,
                100,
                EXPECTED_TEXTS_MAX_100,
            ),
            (
                (),
                TEXTS,
                0,
                EXPECTED_TEXTS_MAX_100,
            ),
            # Actual data.
            (
                "./testdata/xmpp-light-00.txt",
                (),
                0,
                "./testdata/normalized__xmpp-light-00.txt",
            ),
            (
                "./testdata/xmpp-light-01.txt",
                (),
                0,
                "./testdata/normalized__xmpp-light-01.txt",
            ),
        )
    )
    def test_normalize_maven_output(
        self,
        std_out: Union[Sequence[str], str],
        std_error: Sequence[str],
        max_line_len: int,
        expected_text: Sequence[str],
    ):
        """Unit tests for normalize_maven_output."""

        def _maybe_load(filename):
            if isinstance(filename, str):
                pwd = os.path.dirname(os.path.abspath(__file__))
                return maven_utils.maybe_split(
                    utils.load_file(os.path.join(pwd, filename))
                )
            return filename

        self.assertEqual(
            maven_utils.normalize_maven_output(
                NEW_LINE.join(_maybe_load(std_out)),
                NEW_LINE.join(std_error),
                max_line_len=max_line_len,
            ),
            NEW_LINE.join(_maybe_load(expected_text)),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    unittest.main()
