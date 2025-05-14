"""Unit test for grouped_llm_parser_factory.py."""

import logging
import unittest

from parameterized import parameterized
from self_debug.proto import llm_parser_pb2

from self_debug.common import utils
from self_debug.lm import grouped_llm_parser_factory, llm_parser_factory


FindReplacePair = llm_parser_factory.FindReplacePair


TEXT_PROTO = """
  regex_llm_parser_by_group {
    group: "<GROUP>"
  }
  block_parser {
    regex_llm_parser {
    }
  }
"""


class TestRegexLlmParserByGroup(unittest.TestCase):
    """Unit test for grouped_llm_parser_factory.py."""

    @parameterized.expand(
        (
            (
                TEXT_PROTO,
                {},
                grouped_llm_parser_factory.RegexLlmParserByGroup,
                r"\[<GROUP> Start [^\]]+\]",
                r"\[<GROUP> End [^\]]+\]",
            ),
            (
                TEXT_PROTO,
                {
                    "group": "$find",
                },
                grouped_llm_parser_factory.RegexLlmParserByGroup,
                r"\[$find Start [^\]]+\]",
                r"\[$find End [^\]]+\]",
            ),
        )
    )
    def test_create_grouped_llm_parser_from_config(
        self, config, kwargs, expected_class, expected_start, expected_end
    ):
        """Unit test for create_grouped_llm_parser with a config."""
        config = utils.parse_proto(config, llm_parser_pb2.LlmParserByGroup)
        parser = grouped_llm_parser_factory.create_grouped_llm_parser(config, **kwargs)

        self.assertIsInstance(parser, grouped_llm_parser_factory.BaseLlmParserByGroup)
        self.assertIsInstance(parser, expected_class)

        parser = parser.group_parser
        self.assertIsInstance(parser, llm_parser_factory.BaseLlmParser)
        self.assertEqual(parser.match_s, expected_start)
        self.assertEqual(parser.match_e, expected_end)

    @parameterized.expand(
        (
            # pylint: disable=line-too-long
            ### [{Find, Replace} {Start, End}]
            # Unable to get correct filename.
            (
                """
<Change Start test.py>
ANY CONTENT
<Change End test.py>
                """,
                {},
                {},
                {},
                "",
                (
                    "[Feedback Start]Unable to get any file to change, please double check the formats for filenames.[Feedback End]"
                ),
            ),
            (
                """
[Change Start test.py]
ANY CONTENT
[Change End test2.py]
                """,
                {},
                {},
                {},
                "",
                (
                    "[Feedback Start]"
                    "Unable to get same filename from\n"
                    "[Start]\n[Change Start test.py]\n[End]\n"
                    "and\n"
                    "[Start]\n[Change End test2.py]\n[End]\n"
                    "with the content\n"
                    "[Start]\n\nANY CONTENT\n\n[End]"
                    "[Feedback End]"
                ),
            ),
            # Only find block is found.
            (
                """
[Change Start test.py]
[Find Start]
find
[Find End]
[Change End test.py]
                """,
                {},
                {},
                {},
                "",
                (
                    # 1st.
                    "[Feedback Start]Number of find vs replace blocks are not the same 1 != 0:\n"
                    "[Find Block Start]\n"
                    "[MatchBlock(content='\\nfind\\n', start='[Find Start]', end='[Find End]')]\n"
                    "[Find Block End]\n"
                    "[Replace Block Start]\n"
                    "[]\n"
                    "[Replace Block End]"
                    "[Feedback End]\n"
                    # 2nd.
                    "[Feedback Start]Unable to parse correctly for file `test.py`: Skip parsing\n"
                    "[Start]\n"
                    "\n"
                    "[Find Start]\n"
                    "find\n"
                    "[Find End]\n"
                    "\n"
                    "[End]"
                    "[Feedback End]"
                ),
            ),
            (
                """
[Change Start test2.py]
[FIND Start]
find
[FIND End]

[REPLACE Start]
replace
[REPLACE End]
[FIND Start]
find2
[FIND End]

[REPLACE Start]
[REPLACE End]
[Change End test2.py]

[Change Start $FILEPATH]
and
[Change End $FILEPATH]
                """,
                {},
                {
                    "find": "FIND",
                    "replace": "REPLACE",
                },
                {
                    "test2.py": (
                        FindReplacePair(find="find", replace="replace"),
                        FindReplacePair(find="find2", replace=""),
                    ),
                },
                "\n".join(
                    [
                        "",
                        "[Change Start test2.py]",
                        "",
                        "[FIND Start]",
                        "find",
                        "[FIND End]",
                        "",
                        "[REPLACE Start]",
                        "replace",
                        "[REPLACE End]",
                        "[FIND Start]",
                        "find2",
                        "[FIND End]",
                        "",
                        "[REPLACE Start]",
                        "[REPLACE End]",
                        "",
                        "[Change End test2.py]",
                    ]
                ),
                None,
            ),
            (
                """
[Change Start <test.py>]
[Find Start]

  find
[Find End]
[Replace Start]
replace

[Replace End]
[Change End <test.py>]
[Change Start <test2.py>]
[Find Start]

  find
[Find End]
[Replace Start]
replace

[Replace End]
[Find Start]
find2
[Find End]
[Replace Start]
replace2
[Replace End]
[Change End <test2.py>]
                """,
                {
                    "regex_group_start": "\\[{regex} Start <[^>]+>\\]",
                    "regex_group_end": "\\[{regex} End <[^>]+>\\]",
                },
                {
                    "strip": False,
                },
                {
                    "test.py": (FindReplacePair(find="\n  find", replace="replace"),),
                    "test2.py": (
                        FindReplacePair(find="\n  find", replace="replace"),
                        FindReplacePair(find="find2", replace="replace2"),
                    ),
                },
                "\n".join(
                    [
                        "",
                        "[Change Start <test.py>]",
                        "",
                        "[Find Start]",
                        "",
                        "  find",
                        "[Find End]",
                        "[Replace Start]",
                        "replace",
                        "",
                        "[Replace End]",
                        "",
                        "[Change End <test.py>]",
                        "[Change Start <test2.py>]",
                        "",
                        "[Find Start]",
                        "",
                        "  find",
                        "[Find End]",
                        "[Replace Start]",
                        "replace",
                        "",
                        "[Replace End]",
                        "[Find Start]",
                        "find2",
                        "[Find End]",
                        "[Replace Start]",
                        "replace2",
                        "[Replace End]",
                        "",
                        "[Change End <test2.py>]",
                    ]
                ),
                None,
            ),
            # pylint: enable=line-too-long
        )
    )
    def test_run(
        self,
        input_str,
        grouped_kwargs,
        kwargs,
        expected_output,
        expected_parsed_content,
        expected_feedback,
    ):
        """Unit test for parse_llm."""
        parser = grouped_llm_parser_factory.create_grouped_llm_parser(
            "RegexLlmParserByGroup",
            llm_parser_factory.create_llm_parser("RegexLlmParser", **kwargs),
            **grouped_kwargs,
        )

        result = parser.run(input_str)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], expected_output)
        self.assertEqual(result[-1], expected_parsed_content)

        self.assertEqual(parser.collect_feedback(reset=False), expected_feedback)
        self.assertEqual(parser.collect_feedback(reset=True), expected_feedback)
        self.assertIsNone(parser.collect_feedback())
        self.assertIsNone(parser.collect_feedback())

    @parameterized.expand(
        (
            (
                {},
                "[Change Start test]",
                "[Change End test]",
                None,
            ),
            (
                {
                    # pylint: disable=anomalous-backslash-in-string
                    "regex_group_start": "\\[{regex} Start [^\]]+\\]",
                    "regex_group_end": "\\[{regex} End [^\]]+\\]",
                    # pylint: enable=anomalous-backslash-in-string
                },
                "[Change Start <test.py>]",
                "[Change End <|test2.py|>]",
                None,
            ),
            # Valid group names.
            (
                {},
                "[Change start  `<<test2.py>>`]  ",
                "[Change end      <|`test2.py`|>] ",
                "test2.py",
            ),
            (
                {
                    "group": "File",
                    "regex_group_start": "<{regex} start [^>]+\\>",
                    "regex_group_end": "<{regex} end [^>]+\\>",
                },
                "<File start |([[test2.py|)]]>",
                "<File end [|test2.py|]>",
                "test2.py",
            ),
        )
    )
    def test_get_group_name(self, kwargs, group_start, group_end, expected_name):
        """Unit test for get_group_name."""
        parser = grouped_llm_parser_factory.create_grouped_llm_parser(
            "regex_llm_parser_by_group", None, **kwargs
        )

        self.assertEqual(parser.get_group_name(group_start, group_end), expected_name)

    @parameterized.expand(
        (
            # Neither file does exists.
            (
                {},
                None,
                "/tmp/unit/tests/dir/does/not/exist/filename.txt",
                "/tmp/unit/tests/dir/does.not.exist/filename.txt",
                "/tmp/unit/tests/dir/does.not.exist/filename.txt",
            ),
            (
                {},
                None,
                "/tmp/unit/tests/dir/does.not.exist/filename.txt",
                "/tmp/unit/tests/dir/does/not/exist/filename.txt",
                "/tmp/unit/tests/dir/does/not/exist/filename.txt",
            ),
            # One file exists.
            (
                {},
                False,
                "/tmp/unit/tests/dir01/does/not/exist/filename.txt",
                "/tmp/unit/tests/dir01/does.not.exist/filename.txt",
                "/tmp/unit/tests/dir01/does/not/exist/filename.txt",
            ),
            (
                {
                    "maybe_rewrite_group_as_file": False,
                },
                False,
                "/tmp/unit/tests/dir01/does/not/exist/filename.txt",
                "/tmp/unit/tests/dir01/does.not.exist/filename.txt",
                "/tmp/unit/tests/dir01/does.not.exist/filename.txt",
            ),
            # Both file exist.
            (
                {},
                True,
                "/tmp/unit/tests/dir02/does/exist/filename.txt",
                "/tmp/unit/tests/dir02/does.exist/filename.txt",
                "/tmp/unit/tests/dir02/does.exist/filename.txt",
            ),
            (
                {
                    "maybe_rewrite_group_as_file": False,
                },
                True,
                "/tmp/unit/tests/dir02/does/exist/filename.txt",
                "/tmp/unit/tests/dir02/does.exist/filename.txt",
                "/tmp/unit/tests/dir02/does.exist/filename.txt",
            ),
        )
    )
    def test_maybe_rewrite_group_as_file(
        self, kwargs, write, group, query, expected_group
    ):
        """Unit test for get_group_name."""
        config = utils.parse_proto(TEXT_PROTO, llm_parser_pb2.LlmParserByGroup)
        parser = grouped_llm_parser_factory.create_grouped_llm_parser(config, **kwargs)

        if write is not None:
            utils.export_file(group, "Any group content")
            if write:
                utils.export_file(query, "Any query content")

        self.assertEqual(parser._maybe_rewrite_group_as_file(query), expected_group)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    unittest.main()
