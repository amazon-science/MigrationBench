"""Base builder and structured build data as output."""

import abc
from collections import defaultdict
from dataclasses import dataclass
import logging
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from self_debug.proto import builder_pb2

from self_debug.common import utils
from self_debug.lang.base import ast_parser
from self_debug.lm import utils as llm_utils
from self_debug.metrics import utils as metric_utils

CmdData = utils.CmdData

BASE_CONFIG = "base_config"

BUILD_COMMAND = "build_command"
BUILD_COMMAND_SANITY_CHECK = "build_command_sanity_check"

BUILD_ERROR_CHANGE_OPTIONS = "build_error_change_option"

#
# Build errors comparison.
#
BUILD_ERRORS_REVERTED = (
    "after applying the suggested changes, therefore the changes are reverted."
)

# - Project file (e.g. `.csproj`) new errors: Will be reverted.
BUILD_ERRORS_NEW_PROJECT_ERRORS_FEEDBACK = (
    f"There are errors in the project file {BUILD_ERRORS_REVERTED}"
)

# - Source code (e.g. `.cs`) error feedback.
BUILD_ERRORS_DO_NOT_CHANGE_AS_FEEDBACK = (
    f"The build errors are all the same as before, {BUILD_ERRORS_REVERTED}"
)
# BUILD_ERRORS_SUPERSET_AS_FEEDBACK = (
#     f"The build errors are not fixed at all and it introduces new errors, {BUILD_ERRORS_REVERTED}"
# )
BUILD_ERRORS_FROM_NEW_CODE_AS_FEEDBACK = (
    f"There are build errors from newly added lines based on the suggested code change, "
    f"{BUILD_ERRORS_REVERTED}"
)
BUILD_ERRORS_INCREASING_AS_FEEDBACK = (
    f"There are more build errors, {BUILD_ERRORS_REVERTED}"
)
BUILD_ERRORS_NON_DECREASING_AS_FEEDBACK = (
    f"The build errors don't decrease, {BUILD_ERRORS_REVERTED}"
)

ENABLE_FEEDBACK = utils.ENABLE_FEEDBACK


@dataclass
class BuildData:
    """Build error data."""

    filename: str
    line_number: int

    error_message: str
    error_code: Optional[str] = None
    column_number: Optional[int] = None
    code_snippet: Optional[str] = None

    root_dir: Optional[str] = None
    project: Optional[str] = None
    variables: Tuple[str] = ()

    requirements: Optional[str] = None
    related_files: Optional[List[str]] = None
    context: Optional[str] = None

    def __repr__(self):
        return (
            f"{self.filename}@({self.line_number}, {self.column_number}): "
            f"[{self.error_code}] {self.error_message}."
        )

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, self.__class__)
            and self.filename == other.filename
            and self.line_number == other.line_number
            and self.column_number == other.column_number
            and self.error_message == other.error_message
            and self.error_code == other.error_code
            and
            # self.code_snippet == other.code_snippet and
            self.root_dir == other.root_dir
            and self.project == other.project
            and self.related_files == other.related_files
            and self.context == other.context
        )

    def str_wo_line_column(self) -> str:
        """Get str excluding line or column numbers."""
        return f"{self.filename}: [{self.error_code}] {self.error_message}."

    def equal_wo_line_column(self, other) -> bool:
        """Compare build errors excluding line or column numbers."""
        return (
            isinstance(other, self.__class__)
            and self.filename == other.filename
            and
            # self.line_number == other.line_number and
            # self.column_number == other.column_number and
            self.error_message == other.error_message
            and self.error_code == other.error_code
            and
            # self.code_snippet == other.code_snippet and
            self.root_dir == other.root_dir
            and self.project == other.project
        )


class BaseBuilder(abc.ABC):
    """Base Builder."""

    def __init__(self, root_dir: str, **kwargs):
        """Constructor for the base builder.

        kwargs:
        - BUILD_COMMAND
        - BUILD_ERROR_CHANGE_OPTIONS: Back up from `config` in `kwargs`
        - ENABLE_FEEDBACK: Back up from `config` in `kwargs`
        """
        super().__init__()

        self.root_dir = root_dir
        self.command = kwargs.get(BUILD_COMMAND)
        if isinstance(self.command, str):
            self.command = self.command.format(root_dir=root_dir)

        # Will use default field values when triggered.
        config = kwargs.get(BASE_CONFIG, builder_pb2.Builder())
        self.enable_feedback = kwargs.get(
            ENABLE_FEEDBACK, getattr(config, ENABLE_FEEDBACK)
        )
        self.build_error_change_option = kwargs.get(
            BUILD_ERROR_CHANGE_OPTIONS, getattr(config, BUILD_ERROR_CHANGE_OPTIONS)
        )

        self.feedback = []
        # Cache previous build errors.
        self.previous_build_errors = ()

        logging.debug(
            "[ctor] %s: (root_dir, cmd) = (%s, %s) with (feedback, option) = (%s, %s).",
            self.__class__.__name__,
            root_dir,
            self.command,
            self.enable_feedback,
            self.build_error_change_option,
        )

        self.kwargs = kwargs
        self.repo = self.kwargs.get("repo")
        self._metrics = defaultdict(int)
        self._rule_metrics = defaultdict(int)

    def run_final_eval(self) -> bool:
        """Run final eval."""
        return True

    def run_metrics(
        self,
        build_errors: Tuple[BuildData],
        build_error_cutoff_lines: int = 20,
        aggregate: bool = False,
        max_count: int = 1000,
    ):
        """Get metrics."""
        self._metrics = defaultdict(int)

        root_dir = self.root_dir
        if not root_dir.endswith(os.path.sep):
            root_dir += os.path.sep

        self._metrics["00-start"] += 1
        # self._metrics[f"01-filter--{root_dir}"] += 1

        if os.path.exists(root_dir):
            self._metrics["01-filter--dir-exists"] += 1
        else:
            self._metrics["01-filter--dir-does-not-exist"] += 1
            self._metrics["02-finish--early"] += 1
            # return self.metrics

        self._metrics[f"02-build-errors--len={len(build_errors):03d}"] += 1
        self._metrics[
            f"02-build-errors--01--len-dir=<{len(build_errors):03d},{self.root_dir}>"
        ] += 1

        error_code_counts = defaultdict(int)
        error_counts = defaultdict(int)
        for build_error in build_errors:
            code = build_error.error_code
            self._metrics[f"03-00-build-error--code=<{code}>"] += 1

            if aggregate:
                error_code_counts[code] += 1
                error_counts[f"[{code}]{build_error.error_message}"] += 1

            lines = [
                line
                for line in build_error.error_message.split(os.linesep)
                if line.strip()
            ]
            self._metrics[f"03-01-build-error--lines={len(lines):03d}"] += 1
            if len(lines) > build_error_cutoff_lines:
                self._metrics[
                    f"03-02-build-error--lines={len(lines):03d}--file=<{build_error.filename}>"
                ] += 1
                lines = lines[:build_error_cutoff_lines]

            for index, line in enumerate(lines):
                self._metrics[
                    f"04-{index:02d}-build-error--line{index:02d}=[{code}]<<<{line.strip()}>>>"
                ] += 1

            if build_error.filename is None:
                self._metrics["05-00-build-error--file=NONE"] += 1
            else:
                filename = build_error.filename.replace(root_dir, "")
                suffix = filename.split(".")[-1]

                self._metrics[f"05-00-build-error--file=<{filename}>"] += 1
                self._metrics[f"05-01-build-error--file-suffix=<{suffix}>"] += 1
                self._metrics[
                    f"05-02-build-error--file-suffix-code=<{suffix},{code}>"
                ] += 1

        for code, count in error_code_counts.items():
            self._metrics[
                f"05-03-build-error-code-count--~{max_count - count:03d}~<##{count:03d}##{code}>"
            ] += 1
        for error, count in error_counts.items():
            self._metrics[
                f"05-04-build-error-count--~{max_count - count:03d}~<##{count:03d}##{error}>"
            ] += 1

        self._metrics["06-finish"] += 1
        return self.metrics

    @property
    def metrics(self):
        """Get metrics."""
        return metric_utils.reformat_metrics(self, self._metrics)

    @property
    def rule_metrics(self):
        """Get rule metrics."""
        return metric_utils.reformat_metrics(self, self._rule_metrics)

    @abc.abstractmethod
    def extract_build_errors(
        self, cmd_data: CmdData, *args, **kwargs
    ) -> Tuple[BuildData]:
        """Extract structured build errors."""

    @classmethod
    def create_from_config(cls, config: Any, *args, **kwargs):
        """Create from config."""
        raise NotImplementedError("")

    @classmethod
    def project_suffix(cls) -> Optional[str]:
        """Suffix for the project file if applicable."""
        return None

    @classmethod
    def is_project_file(cls, filename: str) -> Optional[bool]:
        """Suffix for the project file if applicable."""
        suffix = cls.project_suffix()
        if suffix is None:
            return None

        return filename is not None and any(
            filename.endswith(s) for s in suffix.split(",")
        )

    def _reset_feedback(self, reset: bool = True):
        """Reset feedback."""
        if reset:
            self.feedback = []

    def collect_feedback(self, reset: bool = True) -> Optional[str]:
        """Feedback based on comparison with previous parsing."""
        feedback = llm_utils.collect_feedback(self.feedback)
        self._reset_feedback(reset=reset)

        return feedback

    def reject_patch(self, build_errors: Tuple[BuildData]) -> bool:
        """Reject patch."""
        del build_errors
        return False

    def maybe_apply_oneoff_rules(
        self, build_errors: Tuple[BuildData], **kwargs
    ) -> bool:
        """Maybe apply oneoff rules: Default is no op."""
        del build_errors
        del kwargs

        return False

    def maybe_apply_rules(
        self, build_errors: Tuple[BuildData], packages, **kwargs
    ) -> bool:
        """Maybe apply rules: Default is no op."""
        del build_errors
        del kwargs
        del packages

        return False

    def maybe_upgrade_packages(
        self,
        build_errors: Tuple[BuildData],
        packages: Tuple[ast_parser.PackageData],
        **kwargs,
    ) -> bool:
        """Maybe upgrade packages: Default is no op."""
        del build_errors
        del kwargs
        del packages

        return False

    def build(self, *args, **kwargs) -> Union[Tuple[BuildData], str]:
        """Build: Return structured build data indicating success or str indicating failure."""
        cmd_data = utils.do_run_command(self.command, check=False)

        # Skip parsing when it's OK.
        if cmd_data.return_code == 0:
            return ()

        if cmd_data.return_code == 1 and not cmd_data.stdout:
            return (
                BuildData(filename="", line_number=-1, error_message=cmd_data.stderr),
            )

        if cmd_data.error is None:
            success = cmd_data.return_code == 0
            errors = self.extract_build_errors(cmd_data, *args, **kwargs)

            logging.debug("Number of build errors: %d.", len(errors))
            if (success and errors) or (not success and not errors):
                msg = "\n".join(
                    [
                        f"Success status ({success}) doesn't match with errors: len = {len(errors)}.",
                        f"    (root_dir, project) = ({self.root_dir}, {self.project})",
                        "    <<<",
                        f"    {cmd_data}",
                        "    >>>",
                    ]
                )

                logging.warning(msg)
                raise ValueError(msg)

            return errors

        raise ValueError(f"Unable to build successfully: <<<{cmd_data}>>>")

    def _update_feedback_errors_different_from_before(
        self,
        previous_build_errors: Tuple[BuildData],
        latest_build_errors: Tuple[BuildData],
        previous_grouped_errors: Dict[str, List[BuildData]],
        latest_grouped_errors: Dict[str, List[BuildData]],
        update_feedback: bool = True,
    ) -> bool:
        """Compare build errors and see whether they change: Return bool of feedback is updated."""
        if (
            len(previous_build_errors) != len(latest_build_errors)
            or len(previous_grouped_errors) != len(latest_grouped_errors)
            or sorted(previous_grouped_errors.keys())
            != sorted(latest_grouped_errors.keys())
        ):
            return False

        # Assuming both are sorted for a given file.
        for filename, previous_file_errors in previous_grouped_errors.items():
            latest_file_errors = latest_grouped_errors[filename]

            for prev_error, curr_error in zip(previous_file_errors, latest_file_errors):
                if not prev_error.equal_wo_line_column(curr_error):
                    return False

        if update_feedback:
            self.feedback.append(BUILD_ERRORS_DO_NOT_CHANGE_AS_FEEDBACK)
        return True

    @classmethod
    def _errors_to_str(
        cls, errors: Sequence[BuildData], prefix="{index}/{count}: "
    ) -> str:
        return "\n".join(
            [
                f"{prefix.format(index=index, count=len(errors))}{str(error)}"
                for index, error in enumerate(errors)
            ]
        )

    def _update_feedback_errors_non_increasing(
        self,
        previous_build_errors: Tuple[BuildData],
        latest_build_errors: Tuple[BuildData],
        previous_grouped_errors: Dict[str, List[BuildData]],
        latest_grouped_errors: Dict[str, List[BuildData]],
    ):
        """Compare build errors and they should be non-increasing."""
        self._update_feedback_errors_decreasing(
            previous_build_errors,
            latest_build_errors[1:],
            previous_grouped_errors,
            latest_grouped_errors,
            BUILD_ERRORS_INCREASING_AS_FEEDBACK,
        )

    def _update_feedback_errors_decreasing(
        self,
        previous_build_errors: Tuple[BuildData],
        latest_build_errors: Tuple[BuildData],
        previous_grouped_errors: Dict[str, List[BuildData]],
        latest_grouped_errors: Dict[str, List[BuildData]],
        error_msg: str = BUILD_ERRORS_NON_DECREASING_AS_FEEDBACK,
    ):
        """Compare build errors and they should decrease."""
        del previous_grouped_errors
        del latest_grouped_errors

        if len(previous_build_errors) <= len(latest_build_errors):
            self.feedback.append(error_msg)
            return

        # TODO(sliuxl): A better way is to implement a hash function for `BuildData`.
        def _to_str(error):
            return error.str_wo_line_column()

        prev_errors = set()
        for prev_error in previous_build_errors:
            prev_errors.add(_to_str(prev_error))

        for curr_error in latest_build_errors:
            if _to_str(curr_error) not in prev_errors:
                self.feedback.append(error_msg)
                return

    def group_errors_by_file(
        self, build_errors: Tuple[BuildData]
    ) -> Dict[str, List[BuildData]]:
        """Group errors by file."""
        file_errors = defaultdict(list)
        for build_error in build_errors:
            # TODO(sliuxl): Double check when filename is `None`.
            file_errors[build_error.filename].append(build_error)

        # Sort by line, column number given a file.
        def _sorted(errors):
            errors = [
                (
                    error.filename,
                    error.project,
                    None if error.line_number is None else -int(error.line_number),
                    None if error.column_number is None else -int(error.column_number),
                    error.error_code,
                    error.error_message,
                    error,
                )
                for error in errors
            ]

            errors = sorted(errors)
            return [error[-1] for error in errors]

        file_errors = {f: _sorted(errors) for f, errors in file_errors.items()}
        return file_errors

    def _update_feedback(
        self,
        previous_build_errors: Tuple[BuildData],
        latest_build_errors: Tuple[BuildData],
    ):
        """Compare build errors and see whether they change."""
        # Also skip for the first iteration when there is nothing to compare with.
        if not self.enable_feedback or not previous_build_errors:
            return

        candidates = {
            builder_pb2.Builder.BuildErrorChangeOption.ERRORS_DIFFERENT_FROM_BEFORE: (
                self._update_feedback_errors_different_from_before
            ),
            builder_pb2.Builder.BuildErrorChangeOption.ERRORS_NON_INCREASING: (
                self._update_feedback_errors_non_increasing
            ),
            builder_pb2.Builder.BuildErrorChangeOption.ERRORS_DECREASING: (
                self._update_feedback_errors_decreasing
            ),
        }

        candidate = candidates.get(self.build_error_change_option)
        if candidate is None:
            return

        previous_group_errors = self.group_errors_by_file(previous_build_errors)
        latest_group_errors = self.group_errors_by_file(latest_build_errors)

        # Step 1: Project errors.
        if self.project_suffix() and not self.project_suffix().endswith("pom.xml"):

            def _get_projects(group_errors):
                return [
                    file
                    for file in sorted(group_errors.keys())
                    if self.is_project_file(file)
                ]

            previous_projects = _get_projects(previous_group_errors)
            latest_projects = _get_projects(latest_group_errors)
            if not previous_projects and latest_projects:
                feedback = []
                for project in latest_projects:
                    project_errors = latest_group_errors[project]
                    feedback.append(
                        f"Project {project}:\n{self._errors_to_str(project_errors)}"
                    )
                feedback = "\n".join(feedback)

                feedback = (
                    f"{BUILD_ERRORS_NEW_PROJECT_ERRORS_FEEDBACK}```\n{feedback}\n```"
                )
                self.feedback.append(feedback)
                return

        # Step 2: Source code errors.
        candidate(
            previous_build_errors,
            latest_build_errors,
            previous_group_errors,
            latest_group_errors,
        )

    def run(self, *args, **kwargs) -> Union[Tuple[BuildData], str]:
        """Apply patches by file."""
        update_errors = kwargs.get("update_errors", True)
        if update_errors:
            self._reset_feedback()
            previous_build_errors = self.previous_build_errors[:]

        latest_build_errors = self.build(*args, **kwargs)

        if update_errors:
            self._update_feedback(previous_build_errors, latest_build_errors)
            self.previous_build_errors = latest_build_errors

        return latest_build_errors
