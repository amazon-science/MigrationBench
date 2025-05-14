"""LLM agent: Interact with LLM taking prompts and provide responses."""

import abc
import json
import logging
import time
from typing import Any, Tuple

import boto3
import botocore
from self_debug.proto import llm_agent_pb2, model_pb2

from self_debug.common import utils


# https://aws.amazon.com/blogs/aws/amazon-bedrock-now-provides-access-to-anthropics-latest-model-claude-2-1/
AWS_CLAUDE_2 = "anthropic.claude-v2"
AWS_CLAUDE_2D1 = "anthropic.claude-v2:1"

# https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html
AWS_CLAUDE_3_SONNET = "anthropic.claude-3-sonnet-20240229-v1:0"
# https://aws.amazon.com/blogs/aws/anthropics-claude-3-haiku-model-is-now-available-in-amazon-bedrock
# TODO(sliuxl): Not working yet.
# A client error occurred: `You don't have access to the model with the specified model ID.` for (anthropic.claude-3-haiku-20240307-v1:0, us-east-1).  # pylint: disable=line-too-long
AWS_CLAUDE_3_HAIKU = "anthropic.claude-3-haiku-20240307-v1:0"
# https://docs.anthropic.com/claude/reference/client-sdks
# TODO(sliuxl): Not working yet.
# A client error occurred: `The provided model identifier is invalid.` for (claude-3-opus-20240229, us-east-1).  # pylint: disable=line-too-long
AWS_CLAUDE_3_OPUS = "anthropic.claude-3-opus-20240229-v1:0"
AWS_CLAUDE_3 = AWS_CLAUDE_3_SONNET
AWS_CLAUDE_35_SONNET = "anthropic.claude-3-5-sonnet-20240620-v1:0"
AWS_CLAUDE_35_HAIKU = "anthropic.claude-3-5-haiku-20241022-v1:0"
AWS_CLAUDE_35_V2_SONNET = "anthropic.claude-3-5-sonnet-20241022-v2:0"
# Cross-region
US_AWS_CLAUDE_35_V2_SONNET = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

# Amazon models
AWS_NOVA_PRO = "amazon.nova-pro-v1:0"

# Meta models
AWS_LLAMA_31_70B = "meta.llama3-1-70b-instruct-v1:0"
US_AWS_LLAMA_31_70B = "us.meta.llama3-1-70b-instruct-v1:0"

# Mistral models
AWS_MISTRAL_LARGE_2 = "mistral.mistral-large-2407-v1:0"

OPTIONAL_FIELDS = ("top_k", "top_p", "temperature")
REGION = "us-east-1"


MODEL_OPTIONS = {
    # Claude 2.
    model_pb2.Model.ModelOption.AWS_CLAUDE_2: AWS_CLAUDE_2,
    model_pb2.Model.ModelOption.AWS_CLAUDE_2D1: AWS_CLAUDE_2D1,
    # Claude 3.
    model_pb2.Model.ModelOption.AWS_CLAUDE_3: AWS_CLAUDE_3,
    model_pb2.Model.ModelOption.AWS_CLAUDE_3_HAIKU: AWS_CLAUDE_3_HAIKU,
    model_pb2.Model.ModelOption.AWS_CLAUDE_3_OPUS: AWS_CLAUDE_3_OPUS,
    model_pb2.Model.ModelOption.AWS_CLAUDE_3_SONNET: AWS_CLAUDE_3_SONNET,
    model_pb2.Model.ModelOption.AWS_CLAUDE_35_SONNET: AWS_CLAUDE_35_SONNET,
    model_pb2.Model.ModelOption.AWS_CLAUDE_35_V2_SONNET: AWS_CLAUDE_35_V2_SONNET,
    model_pb2.Model.ModelOption.AWS_CLAUDE_35_HAIKU: AWS_CLAUDE_35_HAIKU,
    # Cross-region
    model_pb2.Model.ModelOption.US_AWS_CLAUDE_35_V2_SONNET: US_AWS_CLAUDE_35_V2_SONNET,
    # NOVA
    model_pb2.Model.ModelOption.AWS_NOVA_PRO: AWS_NOVA_PRO,
    # LLAMA
    model_pb2.Model.ModelOption.AWS_LLAMA_31_70B: AWS_LLAMA_31_70B,
    model_pb2.Model.ModelOption.US_AWS_LLAMA_31_70B: US_AWS_LLAMA_31_70B,
    # Mistral
    model_pb2.Model.ModelOption.AWS_MISTRAL_LARGE_2: AWS_MISTRAL_LARGE_2,
}

REGION_OPTIONS = {
    llm_agent_pb2.Region.RegionOption.US_EAST_1: "us-east-1",
    llm_agent_pb2.Region.RegionOption.US_EAST_2: "us-east-2",
    llm_agent_pb2.Region.RegionOption.US_WEST_1: "us-west-1",
    llm_agent_pb2.Region.RegionOption.US_WEST_2: "us-west-2",
}


class BaseLlmAgent(abc.ABC):
    """Base LLM agent: Interact with LLM taking prompts and provide responses."""

    def __init__(self, **kwargs):
        self.region = kwargs.get("region", REGION)

        # Optional fields.
        # - temperature
        # - top_k
        # - top_p
        self.kwargs = kwargs
        logging.warning("[ctor] %s: region = %s.", self.__class__.__name__, self.region)

    @classmethod
    def create_from_config(cls, config: Any, *args, **kwargs):
        """Create from config."""
        raise NotImplementedError("")

    @abc.abstractmethod
    def run(
        self, prompt: str, system_prompt: str = "", messages: Tuple[Any] = None
    ) -> str:
        """LLM call."""


class BedrockRuntimeLlmAgent(BaseLlmAgent):
    """Bedrock runtime LLM agent."""

    def __init__(self, model_id: str, max_tokens: int = 4096, **kwargs):
        super().__init__(**kwargs)
        logging.warning(
            "[ctor] %s: (model_id, max_tokens) = (%s, %d).",
            self.__class__.__name__,
            model_id,
            max_tokens,
        )

        self.model_id = model_id
        self.max_tokens = max_tokens
        if self.model_id.split(".")[0] == "us":
            self.model_catalog = self.model_id.split(".")[1]
        else:
            self.model_catalog = self.model_id.split(".")[0]
        # Optional field: "anthropic_version".

        self.retry_policy = kwargs.pop(
            "retry_policy",
            utils.parse_proto("max_attempts: 1", llm_agent_pb2.RetryPolicy),
        )

        self.runtime = None

    @classmethod
    def create_from_config(cls, config: Any, *args, **kwargs):
        """Create from config."""
        model = config.model

        if model.HasField("model_option"):
            model_id = MODEL_OPTIONS[model.model_option]
        else:
            model_id = model.model_id

        if kwargs.get("region"):
            region = kwargs["region"]
        elif config.region.HasField("region_option"):
            region = REGION_OPTIONS[config.region.region_option]
        else:
            region = config.region.region

        kwargs = {
            "model_id": model_id,
            "max_tokens": model.max_tokens,
        }
        if region:
            kwargs.update(
                {
                    "region": region,
                }
            )
        if "CONFIG" in kwargs:
            kwargs.update(
                {
                    "retry_policy": kwargs["CONFIG"].retry_policy,
                }
            )

        for field in OPTIONAL_FIELDS:
            if model.HasField(field):
                kwargs.update(
                    {
                        field: getattr(model, field),
                    }
                )

        return BedrockRuntimeLlmAgent(**kwargs)

    def _init_runtime(self):
        """Init runtime."""
        endpoint_url = f"https://bedrock-runtime.{self.region}.amazonaws.com"

        session = boto3.Session()
        self.runtime = session.client(
            # https://github.com/boto/boto3/issues/3881
            service_name="bedrock-runtime",
            region_name=self.region,
            endpoint_url=endpoint_url,
        )

    def _parse_body(self, body):
        if self.model_catalog == "anthropic":
            return body

        # if self.model_catalog in ["meta", "amazon"]:
        del body["anthropic_version"]
        del body["max_tokens"]
        del body["system"]

        if self.model_catalog == "mistral":
            return body

        messages = body["messages"]
        if self.model_catalog == "amazon":
            for message in messages:
                prompt = message["content"]
                if isinstance(prompt, str):
                    message["content"] = [
                        {
                            "text": prompt,
                        }
                    ]
            return body

        if self.model_catalog == "meta":
            body = {}
            prompt = "\n".join([message["content"] for message in messages])
            body["prompt"] = prompt
            return body

    def run(
        self, prompt: str, system_prompt: str = "", messages: Tuple[Any] = None
    ) -> str:
        """LLM Call."""
        if self.runtime is None:
            self._init_runtime()

        if messages is None:
            messages = []
        messages += [
            {
                "role": "user",
                "content": prompt,
            },
        ]
        if len(messages) != 1:
            logging.info("Messages len = %d.", len(messages))

        body = {
            "anthropic_version": self.kwargs.get("anthropic_version", ""),
            "max_tokens": self.max_tokens,
            "messages": messages,
            "system": system_prompt,
        }
        body = self._parse_body(body)

        for field in OPTIONAL_FIELDS:
            value = self.kwargs.get(field)
            if value is not None:
                body[field] = value
        body = json.dumps(body)
        logging.debug("[USER INPUT]: <<<%s>>> with `%s`.", messages, self.model_id)
        logging.debug("[USER IBODY]: <<<%s>>>.", body)

        seconds_factor = 1
        if self.retry_policy.HasField("every_n_seconds"):
            seconds = self.retry_policy.every_n_seconds
        elif self.retry_policy.HasField("every_n_seconds_x2"):
            seconds = self.retry_policy.every_n_seconds_x2
            seconds_factor = 2
        else:
            seconds = 0
        seconds = max(seconds, self.retry_policy.min_seconds, 0)

        max_attempts = max(self.retry_policy.max_attempts, 1)
        for index in range(max_attempts):
            try:
                response = self.runtime.invoke_model(body=body, modelId=self.model_id)
                response_body = json.loads(response.get("body").read())

                logging.debug("[MODEL OUTPUT]: <<<%s>>>.", response)
                logging.debug(
                    "[MODEL OUTPUT BODY]: <<<%s>>>.",
                    json.dumps(response_body, indent=4),
                )
                if self.model_catalog == "amazon":
                    return response_body["output"]["message"]["content"][0]["text"]
                if self.model_catalog == "anthropic":
                    return response_body["content"][0]["text"]
                if self.model_catalog == "meta":
                    return response_body["generation"]
                if self.model_catalog == "mistral":
                    return response["choices"][0]["message"]["content"]
            except botocore.exceptions.ClientError as error:
                msg = str(error)
                logging.exception(
                    "Unable to get LLM response: <<<%s>>>. `%s`", msg, type(error)
                )
                if msg.startswith(
                    "An error occurred (ExpiredTokenException) when calling the InvokeModel operation: The security token included in the request is expired"
                ) or msg.startswith(
                    "An error occurred (ValidationException) when calling the InvokeModel operation: Malformed input request: "
                ):
                    # Unrecoverable errors, finish early.
                    raise error
            except Exception as error:
                logging.exception(
                    "Unable to get LLM response: <<<%s>>>. `%s`",
                    str(error),
                    type(error),
                )

            if index == max_attempts - 1:
                break

            # Wait a few seconds, and retry.
            logging.warning("Wait %f seconds ...", seconds)
            if seconds > 0:
                time.sleep(seconds)

            # What to use in the next round.
            seconds *= seconds_factor
            seconds = min(seconds, max(self.retry_policy.max_seconds, 0))

        return ""


def create_llm_agent(option: Any, *args, **kwargs) -> BaseLlmAgent:
    """Create llm agent based on its name: Option can be a string (infer class name) or a config."""
    logging.info("[factory] Create llm agent: `%s`.", option)

    classes = (BedrockRuntimeLlmAgent,)

    if isinstance(option, str):
        extra_kwargs = {}
    else:
        args = ("agent",) + args
        extra_kwargs = {"CONFIG": option}
    return utils.create_instance(option, classes, *args, **kwargs, **extra_kwargs)


def main():
    """Main."""
    llm = BedrockRuntimeLlmAgent("anthropic.claude-3-sonnet-20240229-v1:0")
    llm.run("Hello, what's your name?")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format=utils.LOGGING_FORMAT)
    main()
