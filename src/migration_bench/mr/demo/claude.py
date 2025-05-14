"""Demo to show how to generate a message with Anthropic Claude (on demand).

Reference:
https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html

Sample command:
python claude.py  # --model_name claude-3
"""

import argparse
import json
import logging
import re
import time
from typing import Any, Dict, Sequence, Tuple

import boto3
from botocore.exceptions import ClientError
import pyspark

# https://aws.amazon.com/blogs/aws/amazon-bedrock-now-provides-access-to-anthropics-latest-model-claude-2-1/
_CLAUDE_2D1 = "anthropic.claude-v2:1"

# https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html
_CLAUDE_3_SONNET = "anthropic.claude-3-sonnet-20240229-v1:0"
# https://aws.amazon.com/blogs/aws/anthropics-claude-3-haiku-model-is-now-available-in-amazon-bedrock
# TODO(sliuxl): Not working yet.
# A client error occurred: `You don't have access to the model with the specified model ID.` for (anthropic.claude-3-haiku-20240307-v1:0, us-east-1).  # pylint: disable=line-too-long
_CLAUDE_3_HAIKU = "anthropic.claude-3-haiku-20240307-v1:0"
# https://docs.anthropic.com/claude/reference/client-sdks
# TODO(sliuxl): Not working yet.
# A client error occurred: `The provided model identifier is invalid.` for (claude-3-opus-20240229, us-east-1).  # pylint: disable=line-too-long
_CLAUDE_3_OPUS = "anthropic.claude-3-opus-20240229"

_CLAUDE_35_SONNET = "anthropic.claude-3-5-sonnet-20240620-v1:0"
_CLAUDE_36_SONNET = "anthropic.claude-3-5-sonnet-20241022-v2:0"
_CLAUDE_37_SONNET = "anthropic.claude-3-7-sonnet-20250219-v1:0"

_CLAUDE_3 = _CLAUDE_3_SONNET
_DS_R1 = "deepseek.r1-v1:0"

_MAPPING_MODEL_NAME_TO_ID = {
    # V2
    "claude-2.1": _CLAUDE_2D1,
    # V3
    "claude": _CLAUDE_3,
    "claude-3": _CLAUDE_3,
    "claude-3-haiku": _CLAUDE_3_HAIKU,
    "claude-3-sonnet": _CLAUDE_3_SONNET,
    "claude-3-opus": _CLAUDE_3_OPUS,
    "claude-3-5-sonnet": _CLAUDE_35_SONNET,
    "claude-3-6-sonnet": _CLAUDE_36_SONNET,
    "claude-3-7-sonnet": _CLAUDE_37_SONNET,
    "ds": _DS_R1,
    "ds_r1": _DS_R1,
}

_REGION = "us-east-1"


def parse_args():
    """Parse args."""
    parser = argparse.ArgumentParser()

    # Model args.
    model_grp = parser.add_argument_group(
        title="model", description="arguments for model"
    )
    model_grp.add_argument("--model_id", type=str, default=None, help="Model id.")
    model_grp.add_argument(
        "--model_name", type=str, default="claude-3", help="Model name."
    )
    model_grp.add_argument("--max_tokens", type=int, default=1000, help="Max #tokens")

    # Other args.
    parser.add_argument("--region", type=str, default=_REGION, help="Region.")

    return parser.parse_known_args()[0]


def generate_message(
    bedrock_runtime: Any,
    model_id: str,
    system_prompt: str,
    messages: Sequence[Dict[str, Any]],
    max_tokens: int,
) -> Dict[str, Any]:
    """Generate message."""
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": messages,
            "system": system_prompt,
        }
    )

    response = bedrock_runtime.invoke_model(body=body, modelId=model_id)
    response_body = json.loads(response.get("body").read())

    logging.debug("Types = (%s, %s).", type(response), type(response_body))

    logging.info("[USER INPUT]: <<<%s>>>.", messages)
    logging.info("[MODEL OUTPUT]: <<<%s>>>.", response)
    logging.info("[MODEL OUTPUT BODY]: <<<%s>>>.", json.dumps(response_body, indent=4))

    return response_body


def _extract_text_from_response(response) -> str:
    return response["content"][0].get("text")


def run_model(
    model_id: str, region: str, max_tokens: int = 1000, **kwargs
) -> Tuple[Dict[str, Any]]:
    """Run a given model."""
    endpoint_url = f"https://bedrock-runtime.{region}.amazonaws.com"
    session = boto3.Session()
    bedrock_runtime = session.client(
        # https://github.com/boto/boto3/issues/3881
        service_name="bedrock-runtime",
        # service_name="bedrock",
        region_name=region,
        endpoint_url=endpoint_url,
    )

    system_prompt = "I'm familiar with the C++ and Python programming lanuages."

    # 1. Prompt with user turn only.
    question = f"Compute sum of all integers from 1 to {kwargs.pop('sum_to', 100)} inclusive on both sides.\n- Give me the number only."
    user_message = {"role": "user", "content": question}

    # 2. Prompt with both user turn and prefilled assistant response.
    # Anthropic Claude continues by using the prefilled assistant text.
    assistant_message = {"role": "assistant", "content": "<emoji>"}
    messages_01 = [user_message, assistant_message]

    responses = []
    for messages in (messages_01,):
        response = generate_message(
            bedrock_runtime, model_id, system_prompt, messages, max_tokens, **kwargs
        )
        responses.append(response)
        logging.info("Result = `%s`.", _extract_text_from_response(response))

    return tuple(responses)


def main(**kwargs) -> str:
    """Entrypoint for Anthropic Claude message example."""
    args = parse_args()
    if args.model_id is None:
        args.model_id = _MAPPING_MODEL_NAME_TO_ID.get(
            args.model_name.lower().replace("_", "-")
        )
        logging.info(
            "Using model id `%s` from its name `%s`.", args.model_id, args.model_name
        )

    try:
        return _extract_text_from_response(
            run_model(args.model_id, args.region, args.max_tokens, **kwargs)[0]
        )
    except ClientError as error:
        message = error.response["Error"]["Message"]
        logging.exception(
            "A client error occurred for (%s, %s): <<<%s>>>.",
            args.model_id,
            args.region,
            message,
        )

    return ""


def maybe_extract_int(value: str) -> int:
    """Maybe extract int."""
    if isinstance(value, str):
        match = re.match(r"^(\d+)\D*", value)
        if match:
            return int(match.group(1))
    else:
        logging.warning(
            "Getting unexpected type (`%s`) as input: <%s>.", type(value), str(value)
        )

    return 0


def spark_main():
    """Entry point for Apache Spark."""
    # Local run is OK.
    main()
    # return
    logging.info("Sleep ...")

    time.sleep(3)

    # Local run is not OK, without a container.
    spark_context = pyspark.SparkContext()
    result = (
        spark_context.parallelize(range(1, 10))
        .map(lambda x: main(sum_to=x))
        .map(maybe_extract_int)
        .reduce(lambda x, y: x + y)
    )

    logging.info("Final result: `%s`.", result)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s,%(msecs)03d %(levelname)-8s "
        "[%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d:%H:%M:%S",
        level=logging.INFO,
    )

    spark_main()
