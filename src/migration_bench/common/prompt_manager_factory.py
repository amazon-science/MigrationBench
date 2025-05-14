"""Prompt manager.

TemplatePrompt have an optional required fields in its ctor.
- required_fields: Sequence[str] = None

"""

import abc
import logging
import os
from typing import Any, Sequence, Tuple

from self_debug.common import utils


FILENAME = "file_path"
TEMPLATE_PROMPT_FILE_FOR_PROJECT = "template_prompt_file_for_project"


class BasePromptManager(abc.ABC):
    """Base prompt manager."""

    def __init__(self, **kwargs):
        logging.debug("[ctor] %s.", self.__class__.__name__)
        self.kwargs = kwargs

    @abc.abstractmethod
    def get(self, *args, **kwargs) -> Tuple[str, bool]:
        """Get prompt."""


class TemplatePromptManager(BasePromptManager):
    """Template prompt."""

    def __init__(
        self, template_prompt: str, template_prompt_file: str = None, **kwargs
    ):
        super().__init__(**kwargs)
        self.required_fields: Sequence[str] = kwargs.get("required_fields")
        if self.required_fields is not None:
            self.required_fields = sorted(list(set(self.required_fields)))

        logging.debug(
            "[ctor] %s: template (prompt len, file) = (%d, %s), requiring fields `%s`.",
            self.__class__.__name__,
            -1 if template_prompt is None else len(template_prompt),
            template_prompt_file,
            self.required_fields,
        )

        def _try_load_file(filename: str):
            for pwd in ("", os.path.dirname(os.path.dirname(__file__))):
                try_file = os.path.join(pwd, filename) if pwd else filename
                content = utils.load_file(try_file)
                if content is not None:
                    return content

                logging.warning("Load file is None: `%s`.", try_file)

            return None

        if template_prompt_file:
            self.template_prompt = _try_load_file(template_prompt_file)
        else:
            self.template_prompt = template_prompt

        template_project_file = kwargs.get(TEMPLATE_PROMPT_FILE_FOR_PROJECT)
        if template_project_file:
            self.template_prompt_for_project = _try_load_file(template_project_file)
        else:
            self.template_prompt_for_project = None

    @classmethod
    def create_from_config(cls, config: Any, *args, **kwargs):
        """Create from config."""
        del args

        return TemplatePromptManager(
            config.template_prompt,
            config.template_prompt_file,
            required_fields=tuple(config.required_fields),
            **kwargs,
        )

    def get(self, *args, **kwargs) -> Tuple[str, bool]:
        """Get prompt."""
        del args

        try:
            # TODO(sliuxl): Find out better ways to deal with multiple templates.
            if kwargs.get(FILENAME) or not self.template_prompt_for_project:
                return self.template_prompt.format(**kwargs).strip(), True

            return self.template_prompt_for_project.format(**kwargs).strip(), True
        except Exception as error:
            logging.warning(
                "Unable to instantiate from template prompt: `%s`, required fields are `%s`.",
                str(error),
                self.required_fields,
            )

        return None, False


def create_prompt_manager(option: str, *args, **kwargs) -> BasePromptManager:
    """Create prompt manager based on its name."""
    logging.info("[factory] Create prompt manager: `%s`.", option)

    classes = (TemplatePromptManager,)

    if not isinstance(option, str):
        args = ("prompt_manager",) + args
    return utils.create_instance(option, classes, *args, **kwargs)
