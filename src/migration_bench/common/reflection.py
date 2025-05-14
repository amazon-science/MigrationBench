from self_debug.lm import llm_agent_factory
from self_debug.lang.base import builder_factory
from self_debug.proto import config_pb2, metrics_pb2, trajectory_pb2
from fuzzywuzzy import fuzz
from typing import Optional
import logging
import re


def fun_remove_line_number(input_string):
    # Use regex to match ", line <number>,"
    output_string = re.sub(r", line \d+,", ", line ,", input_string)
    return output_string


def error_in_traj(
    build_data: builder_factory.BuildData,
    traj: trajectory_pb2.Trajectory(),
    remove_line_number: bool = True,
) -> Optional[str]:
    """
    Checks if there is an error in the trajectory.

    :param build_data: The build data object.
    :param traj: The trajectory object.
    :return: original reponse
    """
    error_traj = {}
    llm_traj = {}

    for step in traj.steps:
        iteration = step.iteration
        if iteration == -1:
            iteration = 0

        if (
            step.action
            and step.action.build_action
            and step.action.build_action.num_errors
            and step.action.build_action.first_error
        ):
            error_traj[iteration + 1] = (
                step.action.build_action.first_error.error_message
            )

        if step.action and step.action.llm_action and step.action.llm_action.response:
            llm_traj[iteration] = step.action.llm_action.response

    for iteration in sorted(error_traj, reverse=True):
        if iteration not in llm_traj:
            continue
        if remove_line_number:
            similarity_score = fuzz.ratio(
                fun_remove_line_number(build_data.error_message),
                fun_remove_line_number(error_traj[iteration]),
            )
        else:
            similarity_score = fuzz.ratio(
                build_data.error_message, error_traj[iteration]
            )
        logging.info("Similarity score: %d", similarity_score)
        if similarity_score > 98:
            logging.info(f"==build_data.error_message==\n{build_data.error_message}\n")
            logging.info(f"==error_traj==\n{error_traj[iteration]}\n")
            logging.info(f"==llm_traj==\n{llm_traj[iteration]}\n")
            return llm_traj[iteration]

    return None


class ReflectiveDebugger:
    def __init__(self, llm_agent: llm_agent_factory.BaseLlmAgent):
        """
        Initializes the ReflectiveDebugger with an LLM agent and the desired model.

        :param llm_agent: An LLM agent object with a `run()` method for generating responses.
        """
        self.llm_agent = llm_agent

    def analyze_fix(
        self, original_code: str, bug_description: str, attempted_fix: str
    ) -> str:
        """
        Analyzes the attempted fix using the LLM agent to understand why it failed and suggests improvements.

        :param original_code: The original buggy code.
        :param bug_description: A description of the bug in the original code.
        :param attempted_fix: The modified code that attempted to fix the bug.
        :return: Analysis and suggestions from the LLM agent.
        """
        prompt = f"""
You are a reflective debugging assistant. A developer has attempted to fix a bug, but the issue persists. 
Your task is to analyze why the fix didn't work and suggest improvements.

<Original Code>
{original_code}
</Original Code>

<Bug Description>
{bug_description}
</Bug Description>

<Failed Attempted Fix>
{attempted_fix}
</Failed Attempted Fix>

Provide a detailed explanation of why the fix failed, and what other alternative solutions are available. 

<explanation>
[your explanation why the fix didn't work]
</explanation>

Finally, provide a high-level and concise suggestion on the improvement.

<suggestions>
[your concise suggestions for improvements]
</suggestions>
        """

        try:
            # Generate response using the llm_agent
            response = self.llm_agent.run(prompt)
            return response.strip()
        except Exception as e:
            return f"Error during LLM interaction: {e}"


# Example usage
if __name__ == "__main__":
    # Example llm_agent setup (replace this with your actual LLM agent)
    class MockLLMAgent:
        def run(self, prompt, messages=[]):
            return "This is a mock response analyzing the attempted fix and suggesting improvements."

    llm_agent = MockLLMAgent()

    # Initialize debugger
    debugger = ReflectiveDebugger(llm_agent=llm_agent)

    # Example data
    original_code = """
    def divide(a, b):
        return a / b
    """
    bug_description = "The function raises a ZeroDivisionError when b is 0."
    attempted_fix = """
    def divide(a, b):
        if b == 0:
            return None
        return a / b
    """

    # Analyze the fix
    result = debugger.analyze_fix(original_code, bug_description, attempted_fix)
    print(result)
