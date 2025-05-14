"""Unit tests for utils.py."""

from collections import defaultdict
import logging
import unittest

import numpy as np
from parameterized import parameterized

from self_debug.common import utils as common_utils
from self_debug.metrics import utils


class TestUtils(unittest.TestCase):
    """Unit tests for utils.py."""

    @parameterized.expand(
        [
            (
                None,
                None,
                defaultdict(int, {}),
            ),
            (
                None,
                {
                    "hello": 1,
                    "test": 0,
                },
                defaultdict(
                    int,
                    {
                        "TestUtils::hello": 1,
                        "TestUtils::test": 0,
                    },
                ),
            ),
            (
                unittest.TestCase(),
                {
                    "hello": 1,
                },
                defaultdict(
                    int,
                    {
                        "TestCase::hello": 1,
                    },
                ),
            ),
        ]
    )
    def test_reformat_metric(self, obj, input_metrics, expected_metrics):
        """Unit tests for reformat_metrics."""
        metrics = utils.reformat_metrics(obj or self, input_metrics)

        self.assertIsInstance(metrics, defaultdict)
        self.assertEqual(metrics, expected_metrics)

    @parameterized.expand(
        [
            (
                None,
                None,
                (None,),
                defaultdict(int),
            ),
            # Metrics in lhs only.
            (
                defaultdict(
                    int,
                    {
                        "lhs": 11,
                    },
                ),
                {},
                (None,),
                defaultdict(
                    int,
                    {
                        "lhs": 11,
                    },
                ),
            ),
            # Metrics in rhs only.
            (
                defaultdict(int),
                {
                    "rhs": 22,
                },
                (None,),
                defaultdict(
                    int,
                    {
                        "rhs": 22,
                    },
                ),
            ),
            (
                {
                    "hello": 1,
                    "lhs": 11,
                },
                {
                    "hello": 2,
                    "rhs": 22,
                },
                (None,),
                defaultdict(
                    int,
                    {
                        "hello": 3,
                        "lhs": 11,
                        "rhs": 22,
                    },
                ),
            ),
            # Customized reduce function.
            (
                {
                    "hello": 1,
                },
                {
                    "hello": 2,
                    "rhs": 22,
                },
                (min,),
                defaultdict(
                    int,
                    {
                        "hello": 1,
                        "rhs": 22,
                    },
                ),
            ),
            (
                {
                    "lhs": 11,
                },
                None,
                (np.mean,),
                defaultdict(
                    int,
                    {
                        "lhs": 11,
                    },
                ),
            ),
            (
                None,
                {
                    "rhs": 22,
                },
                (np.median,),
                defaultdict(
                    int,
                    {
                        "rhs": 22,
                    },
                ),
            ),
            (
                {
                    "hello": 1,
                    "lhs": 11,
                },
                {
                    "hello": 2,
                    "rhs": 22,
                },
                (max,),
                defaultdict(
                    int,
                    {
                        "hello": 2,
                        "lhs": 11,
                        "rhs": 22,
                    },
                ),
            ),
        ]
    )
    def test_reduce_by_key(self, lhs, rhs, args, expected_metrics):
        """Unit tests for reformat_metrics."""
        metrics = utils.reduce_by_key(lhs, rhs, *args)
        utils.show_metrics(metrics)

        self.assertIsInstance(metrics, defaultdict)
        self.assertEqual(metrics, expected_metrics)

    @parameterized.expand(
        [
            (
                {
                    "hello": 10,
                    "AClass::a--any": 2,
                    "AClass::a--other": 2,
                    "AClass::a--zz": 3,
                    "BClass::b-anything": 3,
                },
                {},
                (
                    ("AClass::a--any", 2),
                    ("AClass::a--other", 2),
                    ("AClass::a--zz", 3),
                    ("BClass::b-anything", 3),
                    ("hello", 10),
                ),
            ),
            (
                {
                    "#datasets": 100,
                    "hello": 10.1,
                    "AClass::a--00--any": 2,
                    "AClass::a--00--other": 2,
                    "AClass::a--01--zz": 3,
                    "BClass::b--anything": 30,
                    "CClass::anything": 4,
                },
                {
                    "sort": True,
                },
                (
                    ("#datasets", 100),
                    ("AClass::a--00--any", 2),
                    ("AClass::a--00--other", 2),
                    ("AClass::a--01--zz", 3),
                    ("BClass::b--anything", 30),
                    ("CClass::anything", 4),
                    ("hello", 10.1),
                ),
            ),
        ]
    )
    def test_show_metrics(self, metrics, kwargs, expected_items):
        """Unit tests for show_metrics."""
        metrics = utils.show_metrics(metrics, **kwargs)
        self.assertIsInstance(metrics, tuple)
        self.assertEqual(metrics, expected_items)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=common_utils.LOGGING_FORMAT)
    unittest.main()
