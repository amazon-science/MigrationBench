"""Maven builder to extract build errors.

Candidate commands:
- mvn clean verify
- mvn clean -pl {module} -am
- mvn clean test -Dtest={test} -DfailIfNoTests=false
"""

from typing import Any, Optional, Sequence, Tuple, Union
import logging
import os
import re

from self_debug.proto import builder_pb2

from self_debug.common import utils
from self_debug.lang.base import builder
from self_debug.lang.java.eval import parse_file
from self_debug.lang.java.maven import maven_utils


BUILD_CMD_KEY_MODULE = "module"
BUILD_CMD_KEY_TEST = "test"

BUILD_FAILURE = "[INFO] BUILD FAILURE"
BUILD_SUCCESS = "[INFO] BUILD SUCCESS"

COMPILATION_ERROR_START = "[ERROR] COMPILATION ERROR :"
COMPILATION_ERROR_END = BUILD_FAILURE


# pylint: disable=line-too-long
# [ERROR] /Users/sliuxl/xmpp-light/src/main/java/ua/tumakha/yuriy/xmpp/light/service/impl/UserServiceImpl.java:[55,31] incompatible types: java.lang.Long cannot be converted to ua.tumakha.yuriy.xmpp.light.domain.User
# [ERROR] /Users/sliuxl/xmpp-light/src/main/java/ua/tumakha/yuriy/xmpp/light/service/impl/UserServiceImpl.java:[60,35] method findOne in interface org.springframework.data.repository.query.QueryByExampleExecutor<T> cannot be applied to given types;

# [javac] /local/home/gargshi/sdk_agent/ironhide-workspaces/ironhide-AmberDynamoDBSupport_development-2024-11-21-22-35-35-614599/src/AmberJobDynamoDBSupport/src/com/amazon/amber/spark/job/SparkJobWithDdbPublisher.java:13: error: package com.amazonaws.services.dynamodbv2.datamodeling does not exist
# pylint: enable=line-too-long

COMPILATION_ERROR_REGEX = r"^\[ERROR\]\s*(.+\.java):\[(\d+),(\d+)\]\s*(.*)$"
# From brazil build: build system is `happytrails`
COMPILATION_ERROR_REGEX_NO_COLUMN = r"^(.+\.java):(\d+):\s+error:(.*)$"
# COMPILATION_ERROR_REGEX_01 = r"^\[ERROR\]\s*(.*)$"


class MavenBuilder(builder.BaseBuilder):
    """Maven builder."""

    def __init__(self, jdk_path: str, root_dir: str, **kwargs):
        # Customized build command.
        build_command = builder.BUILD_COMMAND
        if build_command not in kwargs:
            kwargs.update(
                {
                    build_command: getattr(builder_pb2.MavenBuilder(), build_command),
                }
            )
        kwargs.update(
            {
                build_command: kwargs[build_command].replace(
                    "{JAVA_HOME}", jdk_path or ""
                )
            }
        )

        super().__init__(root_dir, **kwargs)

        logging.debug("[ctor] %s: jdk_path = %s.", self.__class__.__name__, jdk_path)
        self.jdk_path = jdk_path or ""

        self._sanity_check(kwargs)

    def _sanity_check(self, kwargs):
        """Sanity check: Before any iterations."""
        command = kwargs.get(
            builder.BUILD_COMMAND_SANITY_CHECK, "mvn --version"
        ).replace("{JAVA_HOME}", self.jdk_path)
        output, success = utils.run_command(command, check=False)
        logging.warning("Sanity check [%s] `%s`: %s.", success, command, output)

        if success:
            return

        raise ValueError(f"Unable to pass Java sanity check: <<<{output}>>>")

    @property
    def project(self) -> str:
        """Project file."""
        return os.path.join(self.root_dir, "pom.xml")

    @classmethod
    def create_from_config(cls, config: Any, *args, **kwargs):
        """Create from config: `root_dir` from `kwargs` will be plugged into `config.root_dir`.

        Other args are all from `config`.
        """
        del args

        args = (
            kwargs.pop("jdk_path", config.jdk_path),
            config.root_dir.format(root_dir=kwargs.pop("root_dir", "")),
        )
        for field in (
            builder.BUILD_COMMAND,
            builder.BUILD_COMMAND_SANITY_CHECK,
            "require_maven_installed",
            "require_test_class_and_method_invariance",
            "source_branch",
        ):
            if field not in kwargs:
                kwargs.update({field: getattr(config, field)})

        return MavenBuilder(*args, **kwargs)

    @classmethod
    def project_suffix(cls) -> Optional[str]:
        """Suffix for the project file."""
        return "/pom.xml"

    def _run_final_eval(self) -> bool:
        """Run final eval."""
        result = parse_repo.same_repo_test_files(
            self.root_dir, lhs_branch=self.kwargs.get("source_branch")
        )

        # Use annotated test methods only
        return result[-1]

    def run_final_eval(self) -> bool:
        """Run final eval."""
        if self.kawrgs.get("require_test_class_and_method_invariance"):
            return self._run_final_eval()

        return super().run_final_eval()

    def _extract_line_build_error(
        self, line: str, regex=None
    ) -> Optional[builder.BuildData]:
        """Extract build error from line."""
        if regex is None:
            regex = COMPILATION_ERROR_REGEX

        match = re.search(regex, line)
        if not match:
            # logging.debug("NO MATCH: <<<%s>>>", line)
            return None

        filename = match.group(1)
        line_number = int(match.group(2))

        next_index = 3
        if regex == COMPILATION_ERROR_REGEX:
            column_number = int(match.group(next_index))
            next_index += 1
        else:
            column_number = None
        kwargs = {
            "filename": filename,
            "line_number": line_number,
            "column_number": column_number,
            "error_message": match.group(next_index).rstrip(),
        }
        # Attach code snippet.
        # pylint: disable=bad-indentation
        try:
            if column_number is not None:
                code_snippet, line_copy = utils.get_snippet(
                    filename,
                    line_number,
                    min(5, line_number),
                    5,
                    lambda x: f"{x}  //  Compilation error is at this line.",
                )
                kwargs.update(
                    {
                        "code_snippet": code_snippet,
                    }
                )

                lhs, char, rhs = (
                    line_copy[: (column_number - 1)],
                    line_copy[(column_number - 1) : column_number],
                    line_copy[column_number:],
                )
                logging.debug(
                    "Compilation error at <<<%s~~~%s~~~%s>>>.", lhs, char, rhs
                )

                var = ()
                if char == ".":
                    # Function call: A.B(...) => (A, ).
                    match = re.search(r"([a-zA-Z0-9_]+)\s*$", lhs)
                    if match:
                        var = (match.group(1),)
                elif re.search(r"^[a-zA-Z0-9_]$", char):
                    # Variable.
                    # 1: The one generating the error.
                    match = re.search(r"^([a-zA-Z0-9_]+)", rhs)
                    if match:
                        var = (f"{char}{match.group(1)}",)

                    # 0: The main var at line start: [Type var = ] A.B(...).
                    match = re.search(
                        r"^\s*([a-zA-Z0-9_]+)\s*\.[a-zA-Z0-9_]+\s*\(",
                        lhs.split(" = ")[-1],
                    )
                    if match:
                        var = (match.group(1), var)
                else:
                    # Example: ^@Override$
                    #           ^
                    pass
                kwargs.update(
                    {
                        "variables": (var, (lhs, char, rhs)),
                    }
                )
        except Exception as error:
            logging.exception(
                "Unable to get code snippet from `%s`: `%s`.", filename, str(error)
            )
        # pylint: enable=bad-indentation

        build_data = builder.BuildData(**kwargs)
        if not build_data.filename.startswith(self.root_dir):
            logging.warning(
                "File is not in root_dir (%s): <<<%s>>>.", self.root_dir, build_data
            )

        return build_data

    def _extract_compilation_errors(
        self, lines: Sequence[str], regex=None
    ) -> Tuple[builder.BuildData]:
        """Extract compilation errors: By line."""
        errors = []

        append_mode = False
        while lines:
            line = lines[0]
            lines = lines[1:]

            build_data = self._extract_line_build_error(line, regex=regex)
            if build_data is None:
                if errors and line.startswith(" ") and append_mode:
                    errors[-1].error_message += f"\n{line}"
                else:
                    append_mode = False
            else:
                errors.append(build_data)
                append_mode = True

        return tuple(errors)

    def _extract_non_compilation_errors(
        self, lines: Sequence[str]
    ) -> Tuple[builder.BuildData]:
        """Extract non compilation errors: One single error."""
        start = maven_utils.find_first_line_match(lines, BUILD_FAILURE)

        if start is None:
            for index, line in enumerate(lines):
                if line.startswith("[ERROR] [ERROR] ") or line.startswith("[FATAL] "):
                    start = index
                    break

        if start is None:
            for index, line in enumerate(lines[::-1]):
                if line.startswith("[ERROR]"):
                    continue

                if index > 0:
                    start = len(lines) - index

                break

        if start is None:
            return ()

        if lines[start].startswith("[ERROR] [ERROR] ") or lines[start].startswith(
            "[FATAL] "
        ):
            if lines[start].startswith("[FATAL] ") and start != 0:
                start -= 1
            lines = lines[start:]
            msg = "\n".join(lines)
        else:
            lines = lines[start:]
            msg = maven_utils.normalize_maven_output(lines, max_non_error_lines=0)

        build_data = builder.BuildData(
            filename=self.project,
            line_number=None,
            error_message=msg,
        )
        logging.debug(build_data)

        return (build_data,)

    def extract_build_errors(
        self, cmd_data: builder.CmdData, *args, **kwargs
    ) -> Tuple[builder.BuildData]:
        """Extract build errors: By line."""
        del args, kwargs

        lines = maven_utils.maybe_split(cmd_data.stdout)

        # 1. Extract lines between compilation error start and end lines.
        def _get_compilation_lines(lines: Sequence[str]) -> Sequence[str]:
            start = maven_utils.find_first_line_match(lines, COMPILATION_ERROR_START)
            if start is None:
                return ()

            end = maven_utils.find_first_line_match(lines, COMPILATION_ERROR_END, start)
            if end is None:
                return ()

            return lines[start:end]

        compilation_lines = _get_compilation_lines(lines)
        if compilation_lines:
            # Case 1: regex 00
            errors = self._extract_compilation_errors(compilation_lines)
            if errors:
                return errors

            # Case 2: regex 01
            prefix = "[ERROR] "
            errors = []
            for line in compilation_lines[1:]:
                line = line.strip()
                if line.strip().startswith(prefix):
                    errors.append(
                        builder.BuildData(
                            filename=self.project,
                            line_number=None,
                            error_message=line[len(prefix) :],
                        )
                    )
            return tuple(errors)

        return self._extract_non_compilation_errors(lines)

    def build(self, *args, **kwargs) -> Union[Tuple[builder.BuildData], str]:
        """Build: Return structured build data indicating success or str indicating failure."""
        if args:
            module = args[0]
        else:
            module = kwargs.get(BUILD_CMD_KEY_MODULE, "")
        if len(args) > 1:
            test = args[1]
        else:
            test = kwargs.get(BUILD_CMD_KEY_TEST, "")

        command_copy = None
        if module or test:
            command_copy = self.command
            self.command = self.command.format(module=module, test=test)

        errors = super().build(*args, **kwargs)

        for build_data in errors:
            logging.debug("<<<%s>>>", build_data)
            logging.debug(build_data.code_snippet)
            logging.debug("Variables: `%s`.", build_data.variables)

        if command_copy is not None:
            self.command = command_copy
        return errors
