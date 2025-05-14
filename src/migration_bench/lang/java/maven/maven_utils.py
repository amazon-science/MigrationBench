"""Maven log utils."""

from typing import Optional, Sequence, Tuple, Union
import logging


MAVEN_LOG_LONG_LINE_MAX_CHARACTERS = 1250

MAVEN_ERROR_EXCLUDE_LINES_STARTS_WITH = (
    "NOTE:",
    "WARNING:",
    "Progress",
    "Downloaded",
    "Downloading",
    "[ERROR] WARNING: Unknown module:",
)

MAVEN_ERROR_LINE_STARTS_WITH = "[ERROR]"
MAVEN_NON_ERROR_LINES_MAX = 400

NEW_LINE = "\n"


def maybe_split(lines: Union[str, Sequence[str]], rstrip: bool = True) -> Tuple[str]:
    """Filter maven error from its log."""
    if isinstance(lines, str):
        lines = [(line.rstrip() if rstrip else line) for line in lines.splitlines()]

    return tuple(lines)


def find_first_line_match(
    lines: Sequence[str], match: str, start: Optional[int] = None
) -> Optional[int]:
    """Find the first line's index matching `match`."""
    if start is None:
        start = 0

    for index in range(start, len(lines)):
        if lines[index] == match:
            return index

    return None


def _filter_maven_error(lines: Union[str, Sequence[str]]) -> Tuple[str]:
    """Filter maven error from its log."""
    lines = maybe_split(lines)

    updated_lines = []
    for line in lines:
        if line.startswith(MAVEN_ERROR_EXCLUDE_LINES_STARTS_WITH):
            continue
        updated_lines.append(line)

    return tuple(updated_lines)


def _shorten_logs(
    lines: Union[str, Sequence[str]], max_non_error_lines: Optional[int] = None
) -> Tuple[str]:
    """Shortern logs."""
    lines = maybe_split(lines)

    error_lines, non_error_lines = [], []
    for line in lines:
        if line.startswith(MAVEN_ERROR_LINE_STARTS_WITH):
            error_lines.append(line)
        else:
            non_error_lines.append(line)

    if max_non_error_lines is not None:
        non_error_lines = non_error_lines[:max_non_error_lines]

    return tuple(error_lines + non_error_lines)


def _remove_empty_lines(lines: Sequence[str]) -> Tuple[str]:
    return tuple(s for s in lines if s.strip())


def _remove_long_lines(lines: Sequence[str], max_line_len: int) -> Tuple[str]:
    """Remove long lines based on the threshold."""
    if not max_line_len:
        return lines

    return tuple(line for line in lines if len(line) <= max_line_len)


def normalize_maven_output(
    std_out: str,
    std_err: str = "",
    remove_empty: bool = True,
    max_line_len: Optional[int] = MAVEN_LOG_LONG_LINE_MAX_CHARACTERS,
    max_non_error_lines: Optional[int] = None,
) -> str:
    """Normalize maven output.

    - Filter lines starting with "[ERROR]"
    - Show lines starting with "[ERROR]" first
    - Remove empty lines
    - Remove very long lines
    """

    summary = []
    for text in (std_out, std_err):
        lines = maybe_split(text)
        message = f"Normalize maven output: lines = {len(lines)}"

        lines = _filter_maven_error(lines)
        message = f"{message} => {len(lines)} "
        lines = _shorten_logs(lines, max_non_error_lines)
        message = f"{message} => {len(lines)} "
        if remove_empty:
            lines = _remove_empty_lines(lines)
            message = f"{message} => {len(lines)} "
        lines = _remove_long_lines(lines, max_line_len)

        message = f"{message} => {len(lines)}."
        logging.debug(message)

        text = NEW_LINE.join(lines)
        if text:
            summary.append(text)

    logging.debug(summary)
    if len(summary) == 1:
        return summary[0]
    return NEW_LINE.join(summary)
