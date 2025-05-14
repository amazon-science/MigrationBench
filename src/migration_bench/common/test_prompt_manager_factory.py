"""Unit test for prompt_manager_factory.py."""

import os
import unittest

from parameterized import parameterized
from self_debug.proto import config_pb2

from self_debug.common import prompt_manager_factory, utils


TEMPLATE_PROMPT = """
Hello, what's your name?

{optional_examples}

                    """

TEMPLATE_PROMPT_FILE = "./testdata/template_prompt.txt"

TEXT_PROTO = """
  template_prompt_manager {
    template_prompt: "Hello, what's your name?"
  }
"""


class TestPromptManagerFactory(unittest.TestCase):
    """Unit test for prompt_manager_factory.py."""

    def test_create_from_config(self):
        """Unit tests for create_from_config."""
        config = utils.parse_proto(TEXT_PROTO, config_pb2.PromptManager)
        tmpl_prompt_manager = prompt_manager_factory.create_prompt_manager(config)

        self.assertIsInstance(
            tmpl_prompt_manager, prompt_manager_factory.BasePromptManager
        )
        self.assertIsInstance(
            tmpl_prompt_manager, prompt_manager_factory.TemplatePromptManager
        )

    @parameterized.expand(
        (
            # Template string.
            (
                TEMPLATE_PROMPT,
                None,
                {},
                {
                    "optional_examples": "<examples></examples>",
                },
                (
                    """
Hello, what's your name?

<examples></examples>

                    """,
                    True,
                ),
            ),
            (
                TEMPLATE_PROMPT,
                None,
                {},
                {
                    # Missing `optional_examples`.
                    "examples": "<examples></examples>",
                },
                (
                    None,
                    False,
                ),
            ),
            (
                """
                    {optional}
                    {optional_examples}
                """,
                None,
                {
                    "required_fields": ["optional_examples", "optional", "optional"],
                },
                {
                    # Missing `optional_examples`.
                    "examples": "<examples></examples>",
                },
                (
                    None,
                    False,
                ),
            ),
            # Template file.
            (
                None,
                TEMPLATE_PROMPT_FILE,
                {},
                {
                    "optional_examples": "<examples></examples>",
                },
                (
                    ("Hello, what's your name?\n\n<examples></examples>\n"),
                    True,
                ),
            ),
        )
    )
    def test_get_prompt(
        self, template_prompt, template_file, kwargs, i_kwargs, expected_output
    ):
        """Unit test for get prompt."""
        if template_file:
            pwd = os.path.dirname(os.path.abspath(__file__))
            template_file = os.path.join(pwd, template_file)

        args = () if template_file is None else (template_file,)
        manager = prompt_manager_factory.create_prompt_manager(
            "TemplatePromptManager", template_prompt, *args, **kwargs
        )
        self.assertIsInstance(manager, prompt_manager_factory.TemplatePromptManager)

        output = manager.get(**i_kwargs)
        self.assertIsInstance(output, tuple)
        self.assertEqual(len(output), 2)
        if expected_output[0] is None:
            self.assertEqual(output[0], expected_output[0])
        else:
            self.assertEqual(output[0].strip(), expected_output[0].strip())
        self.assertEqual(output[1], expected_output[1])


if __name__ == "__main__":
    unittest.main()
