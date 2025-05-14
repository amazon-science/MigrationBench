"""Unit test for llm_parser_factory.py."""

import logging
import unittest

from parameterized import parameterized
from self_debug.proto import llm_parser_pb2

from self_debug.common import utils
from self_debug.lm import llm_parser_factory

FindReplacePair = llm_parser_factory.FindReplacePair


TEXT_PROTO = """
  regex_llm_parser {
  }
"""


class TestRegexLlmParser(unittest.TestCase):
    """Unit test for RegexLlmParser."""

    @parameterized.expand(
        (
            (
                TEXT_PROTO,
                {},
                llm_parser_factory.RegexLlmParser,
                (
                    r"\[Find Start\]",
                    r"\[Replace Start\]",
                ),
            ),
            (
                TEXT_PROTO,
                {
                    "find": "$find",
                },
                llm_parser_factory.RegexLlmParser,
                (
                    r"\[$find Start\]",
                    r"\[Replace Start\]",
                ),
            ),
        )
    )
    def test_create_llm_parser_from_config(
        self, config, kwargs, expected_class, expected_starts
    ):
        """Unit test for create_llm_parser with a config."""
        config = utils.parse_proto(config, llm_parser_pb2.LlmParser)
        parser = llm_parser_factory.create_llm_parser(config, **kwargs)

        self.assertIsInstance(parser, llm_parser_factory.BaseLlmParser)
        self.assertIsInstance(parser, expected_class)

        self.assertEqual(len(parser.parsers), len(expected_starts))
        for block_parser, expected_start in zip(parser.parsers, expected_starts):
            self.assertEqual(block_parser.match_s, expected_start)

    @parameterized.expand(
        (
            ### [{Find, Replace} {Start, End}]
            # Only find block is found.
            (
                """
[Find Start]
find
[Find End]
                """,
                {},
                False,
                (),
                (
                    "[Feedback Start]"
                    "Number of find vs replace blocks are not the same 1 != 0:\n"
                    "[Find Block Start]\n"
                    "[MatchBlock(content='\\nfind\\n', start='[Find Start]', end='[Find End]')]\n"
                    "[Find Block End]\n"
                    "[Replace Block Start]\n"
                    "[]\n"
                    "[Replace Block End]"
                    "[Feedback End]"
                ),
            ),
            (
                """
[Find Start]
find
[Find End]
                """,
                {
                    "require_same_num_blocks": False,
                },
                False,
                (FindReplacePair(find="find", replace=None),),
                None,
            ),
            (
                """
[Replace Start]
replace
[Replace End]
                """,
                {
                    "require_same_num_blocks": False,
                },
                False,
                (FindReplacePair(find=None, replace="replace"),),
                None,
            ),
            (
                """
[Find Start]
find
[Find End]
[Replace Start]
[Replace End]
[Find Start]

  find
[Find End]
[Replace Start]
find

[Replace End]
                """,
                {
                    "strip": True,
                },
                False,
                (FindReplacePair(find="find", replace=""),),
                (
                    "[Feedback Start]"
                    "Find and replace blocks are the same:\n"
                    "[Find Start]\n"
                    "\n"
                    "\n"
                    "  find\n"
                    "\n"
                    "[Find End]\n"
                    "vs\n"
                    "[Replace Start]\n"
                    "\n"
                    "find\n"
                    "\n"
                    "\n"
                    "[Replace End]"
                    "[Feedback End]"
                ),
            ),
            (
                """
[FIND Start]
find
[FIND End]

[REPLACE Start]
replace
[REPLACE End]
                """,
                {
                    "find": "FIND",
                    "replace": "REPLACE",
                },
                True,
                (FindReplacePair(find="find", replace="replace"),),
                None,
            ),
            (
                """
[Find Start]

  find
[Find End]
[Replace Start]
replace

[Replace End]
                """,
                {
                    "strip": False,
                },
                True,
                (FindReplacePair(find="\n  find", replace="replace"),),
                None,
            ),
            (
                """
[Find Start]

  find
[Find End]
[Replace Start]
replace

[Replace End]
                """,
                {
                    "strip": False,
                    "rstrip": False,
                },
                True,
                (FindReplacePair(find="\n  find\n", replace="replace\n\n"),),
                None,
            ),
            (
                """
[Find Start]

find1
[Find End]
[Replace Start]
replace1
[Replace End]
[Find Start]

find2
[Find End]
[Replace Start]
replace2
[Replace End]
                """,
                {
                    "strip": True,
                },
                True,
                (
                    FindReplacePair(find="find1", replace="replace1"),
                    FindReplacePair(find="find2", replace="replace2"),
                ),
                None,
            ),
        )
    )
    def test_parse_llm(
        self, input_str, kwargs, reset, expected_output, expected_feedback
    ):
        """Unit test for parse_llm."""
        parser = llm_parser_factory.create_llm_parser("RegexLlmParser", **kwargs)
        self.assertEqual(parser.parse_llm(input_str), expected_output)

        self.assertEqual(parser.collect_feedback(reset), expected_feedback)
        self.assertEqual(parser.collect_feedback(reset=True), expected_feedback)
        self.assertIsNone(parser.collect_feedback())
        self.assertIsNone(parser.collect_feedback())


class TestXmlLlmParser(unittest.TestCase):
    """Unit test for XmlLlmParser."""

    @parameterized.expand(
        (
            (
                """
<replace>
replace
</replace>
                """,
                {
                    "strip": True,
                },
                (),
            ),
            # Only find block is found.
            (
                """
<root>
<find>
find
</find>
</root>
                """,
                {
                    "strip": True,
                },
                (),
            ),
            (
                # pylint: disable=trailing-whitespace
                """
<root>
<find>

  find
</find>

<changed>
replace 

</changed>
</root>
                """,
                # pylint: enable=trailing-whitespace
                {
                    "replace": "changed",
                    "strip": True,
                },
                (FindReplacePair(find="find", replace="replace"),),
            ),
            (
                # pylint: disable=trailing-whitespace
                """
<root>
<find>

  find
</find>

<changed>
replace 

</changed>
</root>
                """,
                # pylint: enable=trailing-whitespace
                {
                    "replace": "changed",
                    "strip": False,
                },
                (FindReplacePair(find="\n  find", replace="replace"),),
            ),
            (
                """
<code_change_blocks>
<find>
find
</find>
<replace>
replace
</replace>
</code_change_blocks>
                """,
                {
                    "strip": True,
                },
                (FindReplacePair(find="find", replace="replace"),),
            ),
            (
                """
<root>
<find>
find1
</find>
<replace>
replace1
</replace>

<find>
find2
</find>
<replace>
replace2
</replace>
</root>
                """,
                {
                    "strip": True,
                },
                (
                    FindReplacePair(find="find1", replace="replace1"),
                    FindReplacePair(find="find2", replace="replace2"),
                ),
            ),
        )
    )
    def test_parse_llm(self, input_str, kwargs, expected_output):
        """Unit test for parse_llm."""
        parser = llm_parser_factory.create_llm_parser("xml_llm_parser", **kwargs)
        self.assertEqual(parser.parse_llm(input_str), expected_output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
