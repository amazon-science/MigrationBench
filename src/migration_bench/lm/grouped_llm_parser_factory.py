"""Parse LLM responses by group e.g. code change block per file."""

import abc
import logging
import os
import re
from typing import Any, Dict, Optional, Sequence, Tuple

from self_debug.common import utils
from self_debug.lm import llm_parser_factory, utils as llm_utils


MatchBlock = llm_parser_factory.MatchBlock
MAYBE_REWRITE_GROUP_AS_FILE = "maybe_rewrite_group_as_file"
NEW_LINE = llm_parser_factory.NEW_LINE


BaseLlmParser = llm_parser_factory.BaseLlmParser
FindReplacePair = llm_parser_factory.FindReplacePair

GROUP = "Change"
# pylint: disable=anomalous-backslash-in-string
REGEX_GROUP_START = "\\[{regex} Start [^\]]+\\]"
REGEX_GROUP_END = "\\[{regex} End [^\]]+\\]"
# pylint: enable=anomalous-backslash-in-string


class BaseLlmParserByGroup(abc.ABC):
    """Base LLM parser by group."""

    def __init__(self, block_parser: BaseLlmParser, **kwargs):
        super().__init__()
        logging.debug("[ctor] %s.", self.__class__.__name__)

        self.group_parser = None
        self.block_parser = block_parser
        self.kwargs = kwargs

        self.enable_feedback = kwargs.get(llm_utils.ENABLE_FEEDBACK, True)
        self.feedback = []

        self.maybe_rewrite_group_as_file = kwargs.get(MAYBE_REWRITE_GROUP_AS_FILE, True)

    def _warning(self, msg: str, append: bool = True):
        logging.warning(msg)
        if append and self.enable_feedback:
            self.feedback.append(msg)

    def _reset_feedback(self, reset: bool = True):
        """Reset feedback."""
        for obj in (self.group_parser, self.block_parser):
            obj._reset_feedback(reset=reset)

        if reset:
            self.feedback = []

    def collect_feedback(self, reset: bool = True) -> Optional[str]:
        """Feedback based on previous parsing."""
        feedback = []
        for obj in (self.group_parser, self.block_parser):
            feedback.append(obj.collect_feedback(reset=reset) or "")

        feedback.append(llm_utils.collect_feedback(self.feedback) or "")
        feedback = llm_utils.NEW_LINE.join(feedback).strip()

        self._reset_feedback(reset=reset)

        if feedback:
            return feedback

        return None

    @abc.abstractmethod
    def get_group_name(self, group_start: str, group_end: str) -> str:
        """Parse the group name."""

    @abc.abstractmethod
    def extract_grouped_blocks(self, llm_output: str, **kwargs) -> Sequence[MatchBlock]:
        """Extract grouped blocks from LLM output: (group_start, block, group_end)."""

    def _maybe_rewrite_group_as_file(self, group: str) -> str:
        """Maybe rewrite group as a valid filename."""
        if not self.maybe_rewrite_group_as_file or os.path.exists(group):
            return group

        path = os.path.dirname(group)
        # TODO(sliuxl): Need a better way to incorporate new paths and files.
        if os.path.exists(path):
            return group

        new_group = os.path.join(
            path.replace(".", os.path.sep), os.path.basename(group)
        )
        if os.path.exists(new_group):
            logging.warning(
                "Rewrite as an existing filename: `%s` <= `%s`.", new_group, group
            )
            return new_group

        logging.warning("Group as a filename doesn't exist: `%s`.", group)
        return group

    def parse_llm(
        self, llm_output: str, **kwargs
    ) -> Tuple[Dict[str, Tuple[FindReplacePair]], str]:
        """Parse from LLM output."""
        # 1. By the current group parser.
        grouped_blocks = self.extract_grouped_blocks(llm_output, **kwargs)
        if not grouped_blocks:
            self._warning(
                "Unable to get any file to change, please double check the formats for filenames."
            )

        # 2. By self.block_parser for each grouped block.
        result = {}
        parsed_content = ""
        for grouped_block in grouped_blocks:
            group_start, group_end = grouped_block.start, grouped_block.end
            group = self.get_group_name(group_start, group_end)
            if group is None:
                if len(grouped_block.content) > 10:
                    self._warning(
                        "Unable to get same filename from\n"
                        f"[Start]\n{group_start}\n[End]\n"
                        "and\n"
                        f"[Start]\n{group_end}\n[End]\n"
                        f"with the content\n"
                        f"[Start]\n{grouped_block.content}\n[End]\n"
                    )
                else:
                    logging.debug(
                        "Skip grouped block, a spec in the constaint or requirement section: "
                        "<<<%s>>>",
                        grouped_block,
                    )
                continue

            group = self._maybe_rewrite_group_as_file(group)
            block = grouped_block.content
            blocks = self.block_parser.parse_llm(block)
            if blocks:
                result[group] = blocks
                parsed_content += "\n".join(["", group_start, block, group_end])
            else:
                self._warning(
                    f"Unable to parse correctly for file `{group}`: Skip parsing\n"
                    f"[Start]\n{block}\n[End]\n"
                )

        return result, parsed_content

    def run(self, *args, **kwargs) -> Tuple[Dict[str, Tuple[FindReplacePair]], str]:
        """Parse LLM response."""
        self._reset_feedback()
        return self.parse_llm(*args, **kwargs)


class RegexLlmParserByGroup(BaseLlmParserByGroup):
    """Format of LLM suggestion:

    [Change Start $FILENAME]
    ...
    [Change End $FILENAME]
    """

    def __init__(
        self,
        block_parser: BaseLlmParser,
        group: str = GROUP,
        regex_group_start: str = REGEX_GROUP_START,
        regex_group_end: str = REGEX_GROUP_END,
        **kwargs,
    ):
        logging.debug(
            "RegexLlmParserByGroup ctor: (group, start, end) = (%s, %s, %s).",
            group,
            regex_group_start,
            regex_group_end,
        )
        super().__init__(block_parser, **kwargs)
        logging.debug(
            "[ctor] %s: (group, regex_start, regex_end) = (%s, %s, %s).",
            self.__class__.__name__,
            group,
            regex_group_start,
            regex_group_end,
        )

        self.group_parser = llm_parser_factory.RegexLlmParserHelper(
            group, regex_group_start, regex_group_end
        )

    @classmethod
    def create_from_config(cls, config: Any, *args, **kwargs):
        """Create from config."""
        config_kwargs = {}
        for field in (
            "group",
            "regex_group_end",
            "regex_group_start",
        ):
            config_kwargs[field] = getattr(config, field)
        config_kwargs.update(kwargs)

        if not args:
            raise ValueError("Please provide the `block_parser` in args.")
        block_parser, args = args[0], args[1:]
        block_parser = llm_parser_factory.create_llm_parser(block_parser)

        return RegexLlmParserByGroup(block_parser, *args, **config_kwargs)

    def _get_group(self, group: str) -> str:
        """Parse the group name."""
        # TODO(sliuxl): Find out more robust way to do this.
        group = group.rstrip().split(" ")[-1]
        group = re.sub(r"^[`\[<|\(]+", "", group)
        group = re.sub(r"[`\]>|\)]+$", "", group)
        return group

    def get_group_name(self, group_start: str, group_end: str) -> str:
        """Parse the group name."""
        names = set()
        for group in (group_start, group_end):
            group = self._get_group(group)
            names.add(group if "." in group else None)

        message = None
        if len(names) == 1:
            name = next(iter(names))
            if name is not None:
                return name
            message = f"Both group names are `None`: `{group_start}` vs `{group_end}`."

        if message is None:
            message = f"Mismatching group names in Start vs End (len = {len(names)}): {names}."
        logging.info(message)
        return None

    def extract_grouped_blocks(self, llm_output: str, **kwargs) -> Sequence[MatchBlock]:
        """Extract grouped blocks from LLM output: (group_start, block, group_end)."""
        del kwargs

        # It has a match block only, and the other one is missing.
        return self.group_parser.extract_paired_blocks(llm_output)[0]


def create_grouped_llm_parser(option: str, *args, **kwargs) -> BaseLlmParser:
    """Create grouped llm parser based on its name."""
    logging.info("[factory] Create grouped llm parser: `%s`.", option)

    classes = (RegexLlmParserByGroup,)

    if isinstance(option, str):
        new_kwargs = kwargs
    else:
        args = ("parser", option.block_parser) + args

        new_kwargs = {}
        for field in (
            llm_utils.ENABLE_FEEDBACK,
            MAYBE_REWRITE_GROUP_AS_FILE,
        ):
            new_kwargs.update(
                {
                    field: getattr(option, field),
                }
            )
        new_kwargs.update(kwargs)

    return utils.create_instance(option, classes, *args, **new_kwargs)
