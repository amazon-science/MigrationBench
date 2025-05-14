"""Unit tests for parse_file.py."""

import logging
import os
import unittest

from parameterized import parameterized

from migration_bench.common import utils
from migration_bench.lang.java.eval import parse_file

_PWD = os.path.dirname(os.path.abspath(__file__))

INVALID_FILE_00 = "./file_does_not_exist.java"
INVALID_FILE_01 = "./unknown.java"

FILE_00 = "../native/src/main/java/qct/AstParser.java"
FILE_00_LINE_NO_CHANGE = "./testdata/AstParser.java"

FILE_01 = "../native/src/main/java/qct/XmlBeautifier.java"
FILE_02 = "./testdata/LabelManager.java"


class TestParseFile(unittest.TestCase):
    """Unit tests for parse_file.py."""

    @parameterized.expand(
        (
            # Invalid
            (
                INVALID_FILE_00,
                {},
                None,
            ),
            # Valid
            (
                FILE_00,
                {},
                (
                    ("class", "AstParser"),
                    ("method", ("main", False)),
                    ("class", "FileAnalyzerVisitor"),
                    ("method", ("addTag", False)),
                    ("method", ("getClassDecSignature", False)),
                    ("method", ("getClassSignature", False)),
                    ("method", ("visit", False)),
                    ("method", ("visit", False)),
                ),
            ),
            # - Without line
            (
                FILE_01,
                {},
                (
                    ("class", "XmlBeautifier"),
                    ("method", ("main", False)),
                    ("method", ("writeXmlToFile", False)),
                ),
            ),
            # - With line
            (
                FILE_01,
                {
                    "add_line": True,
                },
                (
                    ("class", "XmlBeautifier"),
                    ("method", ("main", False, 22)),
                    ("method", ("writeXmlToFile", False, 38)),
                ),
            ),
            (
                FILE_02,
                {},
                (
                    ("interface", "LabelManager"),
                    ("method", ("setLocale", False)),
                    ("method", ("get", False)),
                ),
            ),
        )
    )
    def test_get_classes_and_methods(self, filename, kwargs, expected_nodes):
        """Unit test for get_classes_and_methods."""
        nodes = parse_file.get_classes_and_methods(
            os.path.join(_PWD, filename), **kwargs
        )
        logging.debug(nodes)

        self.assertEqual(nodes, expected_nodes)

    @parameterized.expand(
        (
            # Invalid
            (
                INVALID_FILE_00,
                INVALID_FILE_01,
                {},
                {},
                True,
            ),
            (
                INVALID_FILE_00,
                FILE_00,
                {},
                {},
                False,
            ),
            # Valid
            (
                FILE_00,
                FILE_00,
                {},
                {},
                True,
            ),
            (
                FILE_00,
                FILE_00_LINE_NO_CHANGE,
                {
                    "add_line": True,
                },
                {},
                False,
            ),
            (
                FILE_00,
                FILE_00_LINE_NO_CHANGE,
                {
                    "add_line": True,
                },
                {
                    "ignore_line_no": True,
                },
                True,
            ),
            (
                FILE_00,
                FILE_00_LINE_NO_CHANGE,
                {},
                {},
                True,
            ),
            (
                FILE_00,
                FILE_01,
                {},
                {},
                False,
            ),
        )
    )
    def test_same_classes_and_methods(
        self, lhs, rhs, get_kwargs, kwargs, expected_same
    ):
        """Unit test for same_classes_and_methods."""
        lhs = parse_file.get_classes_and_methods(os.path.join(_PWD, lhs), **get_kwargs)
        rhs = parse_file.get_classes_and_methods(os.path.join(_PWD, rhs), **get_kwargs)

        logging.debug(lhs)
        logging.debug(rhs)

        self.assertEqual(
            parse_file.same_classes_and_methods(lhs, rhs, **kwargs), expected_same
        )

    _LHS = (
        ("class", "XmlBeautifier"),
        ("method", ("main", False, 22)),
        ("method", ("writeXmlToFile", True, 38)),
    )

    _RHS = (
        ("class", "XmlBeautifier"),
        ("method", ("main", False, 22)),
        ("method", ("main2", False, 25)),
        ("method", ("writeXmlToFile", True, None)),
    )

    @parameterized.expand(
        (
            # Invalid
            (
                None,
                None,
                {},
                True,
            ),
            # Valid
            (
                _LHS,
                _RHS,
                {},
                False,
            ),
            (
                _LHS,
                _RHS,
                {
                    "ignore_line_no": True,
                },
                False,
            ),
            (
                _LHS,
                _RHS,
                {
                    "has_test_annotation": True,
                },
                False,
            ),
            (
                _LHS,
                _RHS,
                {
                    "has_test_annotation": True,
                    "ignore_line_no": True,
                },
                True,
            ),
        )
    )
    def test_same_classes_and_methods_hard_coded(self, lhs, rhs, kwargs, expected_same):
        """Unit test for same_classes_and_methods."""
        self.assertEqual(
            parse_file.same_classes_and_methods(lhs, rhs, **kwargs), expected_same
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    unittest.main()
