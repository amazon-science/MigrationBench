"""Util functions."""

import logging
from typing import Tuple


def split_errors(
    stdout: str, remove_empty_lines: bool = False, remove_strip_lines: bool = False
) -> Tuple[str]:
    """Split errors."""
    if isinstance(stdout, str):
        lines = (stdout or "").strip().splitlines()
    else:
        lines = stdout

    remove_empty_lines = remove_empty_lines or remove_strip_lines

    errors = []
    while lines:
        line, lines = lines[0], lines[1:]
        if not line:
            return (
                tuple(errors)
                + (() if remove_empty_lines else ("",))
                + split_errors(lines, remove_empty_lines, remove_strip_lines)
            )

        logging.debug("`%s` ==> `%s`, `%s` ...", line, remove_strip_lines, line.strip())
        if remove_strip_lines and not line.strip():
            continue

        if line.startswith(" "):
            if errors:
                errors[-1] += f"\n{line}"
            else:
                errors.append(line)
        else:
            errors.append(line)

    return tuple(errors)
