"""Util functions."""

import logging
import os
from typing import Any, Optional, Sequence

from self_debug.common import utils


ENABLE_FEEDBACK = utils.ENABLE_FEEDBACK

# pylint: disable=unnecessary-lambda-assignment
FEEDBACK_SINGLE_LINE = lambda x: f"[Feedback Start]{x}[Feedback End]"
FEEDBACK_MULTI_LINE = lambda x: f"[Feedback Start]\n{x}\n[Feedback End]"
# pylint: enable=unnecessary-lambda-assignment

NEW_LINE = os.linesep
WINDOWS_NEWLINE_BR = b"\r"


def _default_feedback_fn(msg: str) -> str:
    """Defautl feedback fn."""
    return FEEDBACK_SINGLE_LINE(msg)


def get_feedback(msg: str, msg_fn: Any = None) -> Optional[str]:
    """Get one single feedback."""
    msg = msg.strip()

    if not msg:
        return None

    if msg_fn is None:
        msg_fn = _default_feedback_fn

    msg = msg_fn(msg)
    logging.debug(msg)

    return msg


def collect_feedback(msgs: Sequence[str], msg_fn: Any = None) -> Optional[str]:
    """Get multiple feedback."""
    if msg_fn is None:
        msg_fn = _default_feedback_fn

    feedbacks = []
    for msg in msgs:
        feedback = get_feedback(msg, msg_fn)
        if feedback is not None:
            feedbacks.append(feedback)

    if feedbacks:
        return NEW_LINE.join(feedbacks)

    return None
