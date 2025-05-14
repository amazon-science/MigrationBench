"""Filesystem writer factory."""

import abc
import logging
import re
from typing import Dict, Optional, Sequence, Tuple

from self_debug.lm import llm_parser_factory, utils as llm_utils
from self_debug.common import utils


ENABLE_FEEDBACK = utils.ENABLE_FEEDBACK
FindReplacePair = llm_parser_factory.FindReplacePair


class BaseFileSystemWriter(abc.ABC):
    """Base class for file system."""

    def __init__(self, **kwargs):
        super().__init__()

        self.enable_feedback = kwargs.get(ENABLE_FEEDBACK, True)
        self.feedback = []

        logging.debug("[ctor] %s.", self.__class__.__name__)

        self.kwargs = kwargs

    def _warning(self, msg: str, append: bool = True):
        logging.warning(msg)
        if append and self.enable_feedback:
            self.feedback.append(msg)

    def _reset_feedback(self, reset: bool = True):
        """Reset feedback."""
        if reset:
            self.feedback = []

    def collect_feedback(self, reset: bool = True) -> Optional[str]:
        """Feedback based on previous parsing."""
        feedback = llm_utils.collect_feedback(self.feedback)
        self._reset_feedback(reset=reset)

        return feedback

    @abc.abstractmethod
    def patch(self, *args, **kwargs) -> Dict[str, Optional[bool]]:
        """Apply patches by file."""

    def run(self, *args, **kwargs) -> Dict[str, Optional[bool]]:
        """Apply patches by file."""
        self._reset_feedback()

        return self.patch(*args, **kwargs)


class PairedFileSystemWriter(BaseFileSystemWriter):
    """Single file to apply patches."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logging.debug("[ctor] %s.", self.__class__.__name__)

    def _apply_single_patch(
        self, content: str, find_replace_pair: FindReplacePair
    ) -> Tuple[str, bool]:
        """Patch with match up to optional white space on both left and right hand sides."""
        logging.debug("Try to match find block.")

        find, replace = find_replace_pair.find, find_replace_pair.replace

        lines = [line.strip() for line in find.splitlines()]
        lines = [re.escape(line) for line in lines if line]

        pattern = r"\s*".join(lines)
        logging.debug("Pattern: <<<%s>>>", pattern)
        compiled_pattern = re.compile(pattern, re.MULTILINE)

        CHAR = "\\"

        def _escape(value: str, n: int = 4) -> str:
            new_value = value.replace(CHAR, CHAR * n)
            logging.debug("ESCAPE: <<<%s>>>", value)
            logging.debug("ESCAPE: <<<%s>>>", new_value)
            return new_value

        def _escape_back(value: str, n: int = 4) -> str:
            n //= 2
            new_value = value.replace(CHAR * n, CHAR)
            logging.debug("ESCAPE 2: <<<%s>>>", value)
            logging.debug("ESCAPE 2: <<<%s>>>", new_value)
            return new_value

        try:
            if compiled_pattern.search(content) is not None:
                logging.debug("Matching is successful: %s.", find)

                if CHAR in replace:
                    for n in range(2, 100):
                        if (CHAR * n) not in content:
                            break
                    else:
                        raise ValueError(f"Too many {CHAR} in file: <<<{content}>>>")

                    # Make sure they're all escaped.
                    n *= 2

                    def _replace_fn(value: str):
                        return _escape_back(
                            compiled_pattern.sub(_escape(value, n=n), content), n=n
                        )
                else:

                    def _replace_fn(value: str):
                        return compiled_pattern.sub(value, content)

                return _replace_fn(replace), True
        except Exception as error:
            self._warning(
                "Replacing block raises an error\n"
                f"[Error Start]\n{str(error)}\n[Error End]\n"
                "when trying to replace block\n"
                f"[Find Start]\n{find}\n[Find End]\n"
                "with block"
                f"[Replace Start]\n{replace}\n[Replace End]\n"
            )

        return content, False

    def patch_file(
        self, filename: str, find_replace_pairs: Sequence[FindReplacePair], **kwargs
    ) -> Optional[bool]:
        """Patch a single file."""
        del kwargs

        content = utils.load_file(filename)
        # TODO(sliuxl): Revisit whether and when we do need to create new files, might be OK
        #               when there is one single find block, and it's empty.
        if content is None:
            self._warning(f"File to patch doesn't exist: `{filename}`.")
            return None

        find_blocks = {}
        success = False
        for pair in find_replace_pairs:
            find, replace = pair.find, pair.replace
            if find in find_blocks:
                if find_blocks[find] == replace:
                    logging.debug("Dedup find & replace pairs, skip. `%s`", find)
                else:
                    self._warning(
                        "\n".join(
                            [
                                "Same find block with different replace block!",
                                f"[Find Start]\n{pair.find}\n[Find End]",
                                "==>",
                                f"[Replace Start]\n{find_blocks[pair.find]}\n[Replace End]"
                                "vs",
                                f"[Replace Start]\n{pair.replace}\n[Replace End]",
                            ]
                        )
                    )
                continue

            content, block_success = self._apply_single_patch(content, pair)
            success = success or block_success

        if success:
            utils.export_file(filename, content)
        else:
            self._warning(
                f"Find blocks are not found at all for `{filename}`: "
                f"For all find blocks count = {len(find_replace_pairs)}."
            )

        return success

    def patch(  # pylint: disable=arguments-differ
        self, find_replace_pairs: Dict[str, Sequence[FindReplacePair]], **kwargs
    ) -> Dict[str, Optional[bool]]:
        """Apply patches by file."""
        result = {}
        for filename, pairs in sorted(find_replace_pairs.items()):
            result[filename] = self.patch_file(filename, pairs)

        return result


def create_filesystem_writer(option: str, *args, **kwargs) -> BaseFileSystemWriter:
    """Create filesystem writer based on its name."""
    logging.info("[factory] Create filesytem writer: `%s`.", option)

    class_names = utils.get_class_names((PairedFileSystemWriter,))

    cls = class_names[option]
    return cls(*args, **kwargs)
