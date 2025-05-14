"""Unit test for ast_parser_factory.py."""

import logging
import unittest

from parameterized import parameterized
from self_debug.proto import ast_parser_pb2

from self_debug.common import utils
from self_debug.lang.base import ast_parser_factory
from self_debug.lang.java import ast_parser as java_ast_parser


JAVA_AST_PARSER_ARGS = ("root_dir",)
JAVA_AST_PARSER_KWARGS = {"mvn_path": "mvn"}


JAVA_TEXT_PROTO = """
  java_ast_parser {
    root_dir: "/tmp/java/projects/xmpp-light"
  }
"""


class TestAstParser(unittest.TestCase):
    """Unit test for AstParser."""

    @parameterized.expand(
        (
            # From args, kwargs.
            (
                ("JavaAstParser",) + JAVA_AST_PARSER_ARGS,
                JAVA_AST_PARSER_KWARGS,
                java_ast_parser.JavaAstParser,
            ),
            (
                ("java_ast_parser",) + JAVA_AST_PARSER_ARGS,
                JAVA_AST_PARSER_KWARGS,
                java_ast_parser.JavaAstParser,
            ),
            # From config.
            (
                (utils.parse_proto(JAVA_TEXT_PROTO, ast_parser_pb2.AstParser),),
                {},
                java_ast_parser.JavaAstParser,
            ),
        )
    )
    def test_create_ast_parser(self, args, kwargs, expected_class):
        """Unit test for create_ast_parser."""
        ast_parser = ast_parser_factory.create_ast_parser(*args, **kwargs)

        self.assertIsInstance(ast_parser, ast_parser_factory.BaseAstParser)
        self.assertIsInstance(ast_parser, expected_class)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format=utils.LOGGING_FORMAT)
    unittest.main()
