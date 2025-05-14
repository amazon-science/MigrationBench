"""Metrics util functions."""

from collections import defaultdict
import logging
from typing import Any, Dict, Tuple

import numpy


METRICS_FORMAT = "format"
METRICS_SEP = "--"
METRICS_SORT = "sort"

SEP_AT_INDEX = -1


def reformat_metrics(obj: Any, metrics: Dict[str, int]):
    """Reformat metrics."""
    if metrics is None:
        metrics = {}
    result = defaultdict(
        int, {f"{obj.__class__.__name__}::{k}": v for k, v in metrics.items()}
    )

    # Uncomment for debugging.
    # show_metrics(result, format="\"{name}\": {count},")
    return result


def reduce_by_key(lhs: Dict[str, int], rhs: Dict[str, int], reduce_fn: Any = None):
    """Reduce dicts: Counts are grouped by key."""
    if lhs is None:
        lhs = {}
    if rhs is None:
        rhs = {}

    result = {}

    if reduce_fn is None:
        reduce_fn = sum

    keys = set(lhs.keys()) | set(rhs.keys())
    for key in keys:
        if reduce_fn in (min, numpy.mean, numpy.median) and (
            key not in lhs or key not in rhs
        ):
            # When one of them is missing: Use the other one.
            use_fn = sum
        else:
            use_fn = reduce_fn

        result[key] = use_fn((lhs.get(key, 0), rhs.get(key, 0)))

    return defaultdict(int, result)


def show_metrics(metrics: Dict[str, int], **kwargs) -> Tuple[str, int]:
    """Show metrics."""
    fmt = kwargs.get(METRICS_FORMAT, "  # = {count:04d}: `{name}`.")

    sort = kwargs.get(METRICS_SORT, False)
    logging.info("Metrics: # = %d%s.", len(metrics), " (sorted)" if sort else "")

    items = tuple(sorted(metrics.items()))
    if sort:
        sorted_items = []
        for item in items:
            key, count = item
            segments = key.split(METRICS_SEP)
            if len(segments) <= 1:
                sep_at_index = 1
            else:
                sep_at_index = SEP_AT_INDEX
            prefix, suffix = (
                segments[:sep_at_index],
                METRICS_SEP.join(segments[sep_at_index:]),
            )

            # To sort by count: Need to use `-count`, so that it's decreasing order.
            sorted_items.append((prefix, -count, suffix) + item)

        # Note that do NOT use generator here, otherwise return value will be empty.
        items = tuple(item[-2:] for item in sorted(sorted_items))
        logging.debug(items)

    for name, count in items:
        msg = fmt.format(name=name, count=int(count))
        logging.info(msg)

    return items
