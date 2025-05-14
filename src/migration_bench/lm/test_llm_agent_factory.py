"""Unit test for llm_agent_factory.py."""

import logging
import unittest

from parameterized import parameterized
from self_debug.proto import llm_agent_pb2

from self_debug.common import utils
from self_debug.lm import llm_agent_factory


TEXT_PROTO_00 = """
  bedrock_runtime_llm_agent {
    region {
      # region_option: US_EAST_1
    }
    model {
    }
  }
"""

TEXT_PROTO_01 = """
  bedrock_runtime_llm_agent {
    region {
      region_option: US_EAST_2
    }
    model {
    }
  }
"""


class TestBedrockRuntimeLlmAgent(unittest.TestCase):
    """Unit test for BedrockRuntimeLlmAgent."""

    @parameterized.expand(
        (
            (
                {},
                "us-east-1",
            ),
            (
                {
                    "region": "us-west-2",
                },
                "us-west-2",
            ),
        )
    )
    def test_create_llm_agent(self, kwargs, expected_region):
        """Unit test for create_llm_agent."""
        kwargs.update(
            {
                "model_id": "$MODEL_ID",
            }
        )
        agent = llm_agent_factory.create_llm_agent(
            "bedrock_runtime_llm_agent", **kwargs
        )

        self.assertIsInstance(agent, llm_agent_factory.BedrockRuntimeLlmAgent)
        self.assertIsNone(agent.runtime)
        self.assertEqual(agent.region, expected_region)

    @parameterized.expand(
        (
            (
                TEXT_PROTO_00,
                "us-east-1",
            ),
            (
                TEXT_PROTO_01,
                "us-east-2",
            ),
        )
    )
    def test_create_llm_agent_from_config(self, text_proto, expected_region):
        """Unit test for create_llm_agent with a config."""
        config = utils.parse_proto(text_proto, llm_agent_pb2.LlmAgent)
        agent = llm_agent_factory.create_llm_agent(config)

        self.assertIsInstance(agent, llm_agent_factory.BedrockRuntimeLlmAgent)
        self.assertIsNone(agent.runtime)
        self.assertEqual(agent.region, expected_region)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
