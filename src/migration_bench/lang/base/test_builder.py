"""Unit test for builder.py."""

from collections import defaultdict
import logging
from typing import Tuple
import unittest

from parameterized import parameterized
from self_debug.proto import builder_pb2

from self_debug.common import utils
from self_debug.lang.base import builder


BUILD_DATA_00 = {
    # "code_snippet": None,
    "column_number": 2,
    "error_message": "<error msg>",
    # "error_code": None,
    "filename": "<filename>",
    "line_number": 1,
}

BUILD_DATA_00_AGAIN = {
    **BUILD_DATA_00,
    **{
        "code_snippet": "ANY CODE SNIPPET, DOESN'T AFFECT EQUALITY",
        "error_code": None,
        "project": None,
        "root_dir": None,
    },
}

# Line number: Type change only.
BUILD_DATA_01 = {
    **BUILD_DATA_00,
    **{
        "line_number": "1",
    },
}

# Line and column number changes.
BUILD_DATA_02 = {
    **BUILD_DATA_00,
    **{
        "column_number": 20,
        "line_number": 10,
    },
}

BUILD_DATA_03 = {
    **BUILD_DATA_00,
    **{
        "column_number": None,
        "error_code": "CS0123",
        "filename": "test03.py",
        "project": "*.csproj",
        "root_dir": "/tmp",
    },
}

BUILD_DATA_04 = {
    **BUILD_DATA_00,
    **{
        "column_number": None,
        "error_code": "CS0123",
        "filename": None,
    },
}

# pylint: disable=line-too-long
FEEDBACK_ERRORS_INCREASING = "[Feedback Start]There are more build errors, after applying the suggested changes, therefore the changes are reverted.[Feedback End]"
FEEDBACK_ERRORS_NO_CHANGE = "[Feedback Start]The build errors are all the same as before, after applying the suggested changes, therefore the changes are reverted.[Feedback End]"
FEEDBACK_ERRORS_NON_DECREASING = "[Feedback Start]The build errors don't decrease, after applying the suggested changes, therefore the changes are reverted.[Feedback End]"
# pylint: enable=line-too-long


class Builder(builder.BaseBuilder):
    """Builder."""

    def extract_build_errors(
        self, cmd_data: builder.CmdData, *args, **kwargs
    ) -> Tuple[builder.BuildData]:
        """Extract build errors: By line."""
        del args, kwargs
        del cmd_data
        return ()


class TestBuilder(unittest.TestCase):
    """Unit test for Builder."""

    @parameterized.expand(
        (
            (
                BUILD_DATA_00,
                "<filename>@(1, 2): [None] <error msg>.",
                "<filename>: [None] <error msg>.",
            ),
            (
                BUILD_DATA_00_AGAIN,
                "<filename>@(1, 2): [None] <error msg>.",
                "<filename>: [None] <error msg>.",
            ),
            (
                BUILD_DATA_01,
                "<filename>@(1, 2): [None] <error msg>.",
                "<filename>: [None] <error msg>.",
            ),
            (
                BUILD_DATA_03,
                "test03.py@(1, None): [CS0123] <error msg>.",
                "test03.py: [CS0123] <error msg>.",
            ),
        )
    )
    def test_repr(self, kwargs, expected_str: str, expected_short_str: str):
        """Unit test for create_builder."""
        data = builder.BuildData(**kwargs)
        self.assertEqual(str(data), expected_str)
        self.assertEqual(data.str_wo_line_column(), expected_short_str)

    @parameterized.expand(
        (
            (
                BUILD_DATA_00,
                BUILD_DATA_00,
                True,
                True,
            ),
            (
                BUILD_DATA_00,
                BUILD_DATA_00_AGAIN,
                True,
                True,
            ),
            (
                BUILD_DATA_00,
                BUILD_DATA_01,
                False,
                True,
            ),
            (
                BUILD_DATA_00,
                BUILD_DATA_02,
                False,
                True,
            ),
            (
                BUILD_DATA_01,
                BUILD_DATA_02,
                False,
                True,
            ),
            (
                BUILD_DATA_00,
                BUILD_DATA_03,
                False,
                False,
            ),
        )
    )
    def test_build_data(self, lhs, rhs, expected_equal, expected_equal2):
        """Unit test for create_builder."""
        lhs = builder.BuildData(**lhs)
        rhs = builder.BuildData(**rhs)

        self.assertEqual(lhs == rhs, expected_equal)
        self.assertEqual(rhs == lhs, expected_equal)

        # pylint: disable=singleton-comparison
        self.assertFalse(lhs == None)
        self.assertTrue(lhs != None)
        # pylint: enable=singleton-comparison

        self.assertNotEqual(lhs, None)
        self.assertNotEqual(None, lhs)

        # Symmetric.
        self.assertEqual(lhs.equal_wo_line_column(rhs), expected_equal2)
        self.assertEqual(rhs.equal_wo_line_column(lhs), expected_equal2)

    @parameterized.expand(
        (
            # With feedback.
            (
                (BUILD_DATA_00,),
                (BUILD_DATA_00_AGAIN,),
                {
                    "enable_feedback": True,
                },
                FEEDBACK_ERRORS_NO_CHANGE,
            ),
            (
                (BUILD_DATA_00_AGAIN,),
                (BUILD_DATA_00,),
                {
                    "enable_feedback": True,
                },
                FEEDBACK_ERRORS_NO_CHANGE,
            ),
            (
                (BUILD_DATA_00,),
                (BUILD_DATA_01,),
                {
                    "enable_feedback": True,
                },
                FEEDBACK_ERRORS_NO_CHANGE,
            ),
            (
                (
                    BUILD_DATA_00,
                    BUILD_DATA_03,
                ),
                (
                    BUILD_DATA_03,
                    BUILD_DATA_00,
                ),
                {
                    "enable_feedback": True,
                },
                FEEDBACK_ERRORS_NO_CHANGE,
            ),
            (
                (
                    BUILD_DATA_00,
                    BUILD_DATA_03,
                ),
                (
                    BUILD_DATA_02,
                    BUILD_DATA_03,
                ),
                {
                    "enable_feedback": True,
                },
                FEEDBACK_ERRORS_NO_CHANGE,
            ),
            (
                (
                    BUILD_DATA_03,
                    BUILD_DATA_00,
                ),
                (
                    BUILD_DATA_04,
                    BUILD_DATA_03,
                    BUILD_DATA_00,
                ),
                {
                    "build_error_change_option": (
                        builder_pb2.Builder.BuildErrorChangeOption.ERRORS_NON_INCREASING
                    ),
                    "enable_feedback": True,
                },
                FEEDBACK_ERRORS_INCREASING,
            ),
            (
                (
                    BUILD_DATA_03,
                    BUILD_DATA_00,
                ),
                (
                    # A new error.
                    BUILD_DATA_04,
                    BUILD_DATA_00,
                ),
                {
                    "build_error_change_option": (
                        builder_pb2.Builder.BuildErrorChangeOption.ERRORS_DECREASING
                    ),
                    "enable_feedback": True,
                },
                FEEDBACK_ERRORS_NON_DECREASING,
            ),
            # Without feedback.
            (
                # Turned off.
                (BUILD_DATA_00,),
                (BUILD_DATA_00,),
                {
                    # "enable_feedback": False,
                },
                None,
            ),
            (
                (BUILD_DATA_00,),
                (BUILD_DATA_03,),
                {
                    "enable_feedback": True,
                },
                None,
            ),
            (
                (
                    BUILD_DATA_03,
                    BUILD_DATA_00,
                ),
                (
                    BUILD_DATA_04,
                    BUILD_DATA_00_AGAIN,
                ),
                {
                    "build_error_change_option": (
                        builder_pb2.Builder.BuildErrorChangeOption.ERRORS_NON_INCREASING
                    ),
                    "enable_feedback": True,
                },
                None,
            ),
            (
                (
                    BUILD_DATA_00,
                    BUILD_DATA_03,
                ),
                (
                    # Fixed: BUILD_DATA_00,
                    BUILD_DATA_03,
                ),
                {
                    "build_error_change_option": (
                        builder_pb2.Builder.BuildErrorChangeOption.ERRORS_DECREASING
                    ),
                    "enable_feedback": True,
                },
                None,
            ),
        )
    )
    def test_update_feedback(self, lhs, rhs, kwargs, expected_feedback):
        """Unit test for create_builder."""
        lhs = tuple(builder.BuildData(**kwargs) for kwargs in lhs)
        rhs = tuple(builder.BuildData(**kwargs) for kwargs in rhs)

        bld = Builder("root_dir", **kwargs)
        bld._update_feedback(lhs, rhs)
        self.assertEqual(bld.collect_feedback(), expected_feedback)

    def test_run_metrics(self):
        """Unit test for run_metrics."""
        kwargs_list = (
            BUILD_DATA_00,
            BUILD_DATA_03,
            BUILD_DATA_04,
        )
        build_errors = tuple(builder.BuildData(**kwargs) for kwargs in kwargs_list)

        bld = Builder("root_dir")
        # No build errors.
        metrics = bld.run_metrics(())
        self.assertIsInstance(metrics, defaultdict)
        expected_metrics = defaultdict(
            int,
            {
                "Builder::00-start": 1,
                "Builder::01-filter--dir-does-not-exist": 1,
                "Builder::02-build-errors--01--len-dir=<000,root_dir>": 1,
                "Builder::02-build-errors--len=000": 1,
                "Builder::02-finish--early": 1,
                "Builder::06-finish": 1,
            },
        )
        self.assertEqual(metrics, expected_metrics)

        # Run with build errors.
        metrics = bld.run_metrics(build_errors, aggregate=True)
        self.assertIsInstance(metrics, defaultdict)
        for name, count in sorted(metrics.items()):
            logging.debug('"%s": %d,', name, count)

        expected_metrics = defaultdict(
            int,
            {
                "Builder::00-start": 1,
                "Builder::01-filter--dir-does-not-exist": 1,
                "Builder::02-build-errors--len=003": 1,
                "Builder::02-build-errors--01--len-dir=<003,root_dir>": 1,
                "Builder::02-finish--early": 1,
                "Builder::03-00-build-error--code=<CS0123>": 2,
                "Builder::03-00-build-error--code=<None>": 1,
                "Builder::03-01-build-error--lines=001": 3,
                "Builder::04-00-build-error--line00=[CS0123]<<<<error msg>>>>": 2,
                "Builder::04-00-build-error--line00=[None]<<<<error msg>>>>": 1,
                "Builder::05-00-build-error--file=<<filename>>": 1,
                "Builder::05-00-build-error--file=<test03.py>": 1,
                "Builder::05-00-build-error--file=NONE": 1,
                "Builder::05-01-build-error--file-suffix=<<filename>>": 1,
                "Builder::05-01-build-error--file-suffix=<py>": 1,
                "Builder::05-02-build-error--file-suffix-code=<<filename>,None>": 1,
                "Builder::05-02-build-error--file-suffix-code=<py,CS0123>": 1,
                "Builder::05-03-build-error-code-count--~998~<##002##CS0123>": 1,
                "Builder::05-03-build-error-code-count--~999~<##001##None>": 1,
                "Builder::05-04-build-error-count--~998~<##002##[CS0123]<error msg>>": 1,
                "Builder::05-04-build-error-count--~999~<##001##[None]<error msg>>": 1,
                "Builder::06-finish": 1,
            },
        )
        self.assertEqual(metrics, expected_metrics)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format=utils.LOGGING_FORMAT)
    logging.info(BUILD_DATA_00)
    logging.info(BUILD_DATA_00_AGAIN)
    logging.info(BUILD_DATA_01)
    logging.info(BUILD_DATA_02)
    logging.info(BUILD_DATA_03)
    unittest.main()
