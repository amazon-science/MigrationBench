"""Cleanup functions."""

import logging
import sys
from typing import Tuple

from self_debug.common import utils


AWS_EXTERNAL_ONLY = "AWS_EXTERNAL_ONLY"
AWS_INTERNAL_ONLY = "AWS_INTERNAL_ONLY"

_BEGIN = "BEGIN"
_END = "END"


AWS_EXTERNAL_BEGIN = (
    f"# {AWS_EXTERNAL_ONLY}: {_BEGIN}",
    f"// {AWS_EXTERNAL_ONLY}: {_BEGIN}",
)

AWS_EXTERNAL_END = (
    f"# {AWS_EXTERNAL_ONLY}: {_END}",
    f"// {AWS_EXTERNAL_ONLY}: {_END}",
)

AWS_INTERNAL_BEGIN = (
    f"# {AWS_INTERNAL_ONLY}: {_BEGIN}",
    f"// {AWS_INTERNAL_ONLY}: {_BEGIN}",
)

AWS_INTERNAL_END = (
    f"# {AWS_INTERNAL_ONLY}: {_END}",
    f"// {AWS_INTERNAL_ONLY}: {_END}",
)


def cleanup_file(
    filename: str, export_filename: str = None, content: str = None
) -> Tuple[str, str]:
    """Clean up a file."""
    if content is None:
        content = utils.load_file(filename)

    lines = content.splitlines()

    keep_lines = []
    index = 0
    max_index = len(lines)
    while index < max_index:
        line = lines[index]
        if line.strip() in AWS_INTERNAL_BEGIN:
            index += 1
            while index < max_index and lines[index].strip() not in AWS_INTERNAL_END:
                if lines[index].strip() in AWS_EXTERNAL_BEGIN:
                    index += 1
                    while (
                        index < max_index
                        and lines[index].strip() not in AWS_EXTERNAL_END
                    ):
                        keep_lines.append(lines[index].replace("# ", "", 1))
                        index += 1

                index += 1
        else:
            keep_lines.append(line)

        index += 1

    logging.debug(keep_lines)
    content = "\n".join(keep_lines)

    if export_filename is None:
        export_filename = filename
    if export_filename:
        utils.export_file(export_filename, content)

    return export_filename, content


def _run(filenames):
    for filename in filenames:
        cleanup_file(filename)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    _run(sys.argv[1:])
