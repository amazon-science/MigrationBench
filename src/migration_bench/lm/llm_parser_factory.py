"""Parse LLM responses."""

import abc
from dataclasses import dataclass
import logging
import os
import re
from typing import Any, Optional, Sequence, Tuple
import xml.etree.ElementTree as ET

from pydantic import BaseModel

from self_debug.common import utils
from self_debug.lm import utils as llm_utils


NEW_LINE = os.linesep

FIND = "Find"
REPLACE = "Replace"

REGEX_START = "\\[{regex} Start\\]"
REGEX_END = "\\[{regex} End\\]"


@dataclass
class MatchBlock:
    """Match block for LLM responses."""

    content: str
    start: Optional[str] = None
    end: Optional[str] = None


class FindReplacePair(BaseModel):
    """Find replace pair."""

    find: Optional[str]
    replace: Optional[str]

    def __str__(self) -> str:
        """Representation of the pair."""
        return f"""
<change_block>
[Find Start]
{self.find}
[Find End]

[Replace Start]
{self.replace}
[Replace End]
</change_block>
        """


class BaseLlmParser(abc.ABC):
    """Base class to parse LLM responses."""

    def __init__(self, **kwargs):
        super().__init__()

        self.strip = kwargs.get("strip", True)
        self.rstrip = kwargs.get("rstrip", True)
        self.require_same_num_blocks = kwargs.get("require_same_num_blocks", True)

        self.enable_feedback = kwargs.get(llm_utils.ENABLE_FEEDBACK, True)
        self.feedback = []

        logging.debug(
            "[ctor] %s: (strip, rstrip) = (%s, %s).",
            self.__class__.__name__,
            self.strip,
            self.rstrip,
        )

    def maybe_strip(self, value: str) -> str:
        """Maybe strip."""

        if self.strip:
            return value.strip()

        if value.startswith("\n"):
            value = value[1:]

        if self.rstrip:
            return value.rstrip()

        return value

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
    def extract_paired_blocks(
        self, llm_output: str, **kwargs
    ) -> Tuple[Sequence[MatchBlock], Sequence[MatchBlock]]:
        """Extract paired blocks from LLM output."""

    def parse_blocks(
        self,
        find_blocks: Sequence[MatchBlock],
        replace_blocks: Sequence[MatchBlock],
        **kwargs,
    ) -> Tuple[FindReplacePair]:
        """Parse from LLM output blocks."""
        del kwargs

        logging.debug(
            "Number of find vs replace blocks: %d vs %d.",
            len(find_blocks),
            len(replace_blocks),
        )

        if len(find_blocks) != len(replace_blocks):
            if self.require_same_num_blocks:
                self._warning(
                    f"Number of find vs replace blocks are not the same "
                    f"{len(find_blocks)} != {len(replace_blocks)}:\n"
                    f"[Find Block Start]\n{find_blocks}\n[Find Block End]\n"
                    f"[Replace Block Start]\n{replace_blocks}\n[Replace Block End]\n"
                )
                return ()

            max_len = max(len(find_blocks), len(replace_blocks))
            find_blocks += [None] * (max_len - len(find_blocks))
            replace_blocks += [None] * (max_len - len(replace_blocks))

        pairs = []
        for find, replace in zip(find_blocks, replace_blocks):
            pair = FindReplacePair(
                find=None if find is None else self.maybe_strip(find.content),
                replace=None if replace is None else self.maybe_strip(replace.content),
            )

            if pair.find == pair.replace:
                self._warning(
                    f"Find and replace blocks are the same:\n"
                    f"[Find Start]\n{find.content}\n[Find End]\n"
                    "vs\n"
                    f"[Replace Start]\n{replace.content}\n[Replace End]\n"
                )
                continue
            pairs.append(pair)

        return tuple(pairs)

    def parse_llm(self, llm_output: str, **kwargs) -> Tuple[FindReplacePair]:
        """Parse from LLM output."""
        self._reset_feedback(True)

        blocks = self.extract_paired_blocks(llm_output, **kwargs)
        return self.parse_blocks(*blocks)


class RegexLlmParserHelper(BaseLlmParser):
    """Format of LLM response:

    [$MATCH Start]
    ...
    [$MATCH End]
    """

    def __init__(
        self,
        match: str,
        regex_start: str = REGEX_START,
        regex_end: str = REGEX_END,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.match_s = regex_start.format(regex=match)
        self.match_e = regex_end.format(regex=match)
        logging.debug(
            "[ctor] %s: (match_s, match_e) = (%s, %s).",
            self.__class__.__name__,
            self.match_s,
            self.match_e,
        )

    def extract_paired_blocks(
        self, llm_output: str, **kwargs
    ) -> Tuple[Sequence[MatchBlock], Sequence[MatchBlock]]:
        """Extract blocks from LLM output: (1, 2, 3) = (BEGIN, match, END)."""
        pattern = re.compile(rf"({self.match_s})(.*?)({self.match_e})", re.DOTALL)
        blocks = pattern.findall(llm_output)
        blocks = [
            MatchBlock(start=block[0], content=block[1], end=block[2])
            for block in blocks
        ]

        # It has a match block only, and the other one is missing.
        return (blocks, None)


class RegexLlmParser(BaseLlmParser):
    """Format of LLM response:

    [Find Start]
    ...
    [Find End]
    ***
    [Replace Start]
    ...
    [Replace End]
    """

    def __init__(
        self,
        find: str = FIND,
        replace: str = REPLACE,
        regex_start: str = REGEX_START,
        regex_end: str = REGEX_END,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.parsers = (
            RegexLlmParserHelper(find, regex_start, regex_end),
            RegexLlmParserHelper(replace, regex_start, regex_end),
        )

        logging.debug(
            "[ctor] %s: (find, replace, regex_s, regex_e) = (%s, %s, %s, %s).",
            self.__class__.__name__,
            find,
            replace,
            regex_start,
            regex_end,
        )

    @classmethod
    def create_from_config(cls, config: Any, *args, **kwargs):
        """Create from config."""
        config_kwargs = {}

        renamed_fileds = {
            "block_start": "regex_start",
            "block_end": "regex_end",
        }
        for field in (
            "block_end",
            "block_start",
            "find",
            "replace",
            "require_same_num_blocks",
            "rstrip",
            "strip",
        ):
            config_kwargs[renamed_fileds.get(field, field)] = getattr(config, field)

        if config_kwargs:
            config_kwargs.update(kwargs)
        else:
            config_kwargs = kwargs

        logging.debug("Config kwargs: `%s`.", config_kwargs)
        return cls(*args, **config_kwargs)

    def extract_paired_blocks(
        self, llm_output: str, **kwargs
    ) -> Tuple[Sequence[MatchBlock], Sequence[MatchBlock]]:
        """Extract blocks from LLM responses."""
        blocks = []
        for parser in self.parsers:
            # First element is the matched block.
            blocks.append(parser.extract_paired_blocks(llm_output)[0])

        return tuple(blocks)

    def parse_llm(self, llm_output: str, **kwargs) -> Tuple[FindReplacePair]:
        """Parse from LLM output."""
        for parser in self.parsers:
            parser._reset_feedback()

        return super().parse_llm(llm_output, **kwargs)


class XmlLlmParser(BaseLlmParser):
    """Format of LLM response:

    <root>
    <code_changes>
        <find>print("Hello, World!")</find>
        <find>x = 5</find>
    </code_changes>
    <code_changes>
        <find>y = 10</find>
        <find>print(x + y)</find>
    </code_changes>
    </root>
    """

    def __init__(
        self,
        find: str = "find",
        replace: str = "replace",
        **kwargs,
    ):
        super().__init__(**kwargs)

        logging.debug(
            "[ctor] %s: (find, replace) = (%s, %s).",
            self.__class__.__name__,
            find,
            replace,
        )

        self.find = find
        self.replace = replace

    def extract_paired_blocks(
        self, llm_output: str, **kwargs
    ) -> Tuple[Sequence[MatchBlock], Sequence[MatchBlock]]:
        """Extract blocks from LLM output."""
        logging.debug(llm_output)
        root = ET.fromstring(llm_output, parser=ET.XMLParser(encoding="utf-8"))

        blocks = [[], []]
        for index, regex in enumerate(
            (
                self.find,
                self.replace,
            )
        ):
            for tag in root.findall(regex):
                blocks[index].append(MatchBlock(content=tag.text))

        return tuple(blocks)


def create_llm_parser(option: str, *args, **kwargs) -> BaseLlmParser:
    """Create llm parser based on its name."""
    logging.info("[factory] Create llm parser: `%s`.", option)

    classes = (
        RegexLlmParser,
        XmlLlmParser,
    )

    if not isinstance(option, str):
        args = ("parser",) + args
        kwargs.update(
            {
                llm_utils.ENABLE_FEEDBACK: option.enable_feedback,
            }
        )

    return utils.create_instance(option, classes, *args, **kwargs)
