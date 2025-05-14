"""Run self debugging."""

from collections import defaultdict
import itertools
import logging
import tempfile
import glob
import os
import re
import time
from pathlib import Path

from typing import Any, Dict, List, Optional, Sequence, Tuple
from self_debug.proto import config_pb2, llm_parser_pb2, metrics_pb2, trajectory_pb2

from self_debug.common import (
    eval_utils,
    filesystem_writer_factory,
    git_repo,
    maven_utils,
    pom_utils,
    prompt_manager_factory,
    utils,
)
from self_debug.eval import final_eval
from self_debug.lang.base import ast_helper, ast_parser_factory, builder_factory
from self_debug.lm import (
    grouped_llm_parser_factory,
    llm_agent_factory,
    llm_parser_factory,
    utils as llm_utils,
)

BuildData = builder_factory.BuildData


_APPLY_RULES = True

_KEY_CONTEXT_FILE = "ContextFile"
_KEY_CONTEXT_FILE_CONTENT = "optional__FILE__context_files_content"

TEXT_PROTO_CONTEXT_FILE = """
  regex_llm_parser {
    find: "CONTEXT_FILE"
    replace: "OriginalFile"  # NOT used
    require_same_num_blocks: false
  }
"""


FILE_PREFIX = "FILE__"

ROOT_DIR = "root_dir"
PROJECT = "project"
SOURCE_BRANCH = "source_branch"

VALIDATION_PATH = os.path.join(Path(__file__).parent, "reference/validate.sh")
DEBUG_TIMEOUT = 1.5 * 60 * 60


def prepare_prompt(
    root_dir: str,
    prompt_manager: prompt_manager_factory.BasePromptManager,
    build_data: builder_factory.BuildData,
    project: str,
    last_prompt_messages: Optional[Sequence[str]],
    last_llm_response: str,
    feedback: Sequence[str],
    restart_messages_len_gt: int,
    context_files=None,
    context_kwargs: Dict[str, str] = None,
    reflection: Optional[str] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """LLM prompt."""
    if feedback:
        if (
            restart_messages_len_gt
            and len(last_prompt_messages) > restart_messages_len_gt
        ):
            logging.warning(
                "Retried too many times with len(msgs) = %d > %d, restarting a new one.",
                len(last_prompt_messages),
                restart_messages_len_gt,
            )

            # Continue as if there is no feedback.
        else:
            logging.info("Using feedback to get a new response ...")

            messages = (last_prompt_messages or []) + [
                {
                    "role": "assistant",
                    "content": last_llm_response,
                },
            ]

            msg = (
                "The response is incorrect, as it doesn't fix the build error. "
                "Please generate a full solution again.\n"
                "Below are details:"
            )
            return f"{msg}\n{llm_utils.collect_feedback(feedback)}", messages

    logging.debug("Code snippet: <<<%s>>>", build_data.code_snippet)
    kwargs = {
        "file_path": build_data.filename or "",
        "FILE__file_content": build_data.filename or "",
        "error_code": build_data.error_code,
        "compile_error": build_data.error_message,
        "line_number": "" if build_data.line_number is None else build_data.line_number,
        "column_number": ""
        if build_data.column_number is None
        else build_data.column_number,
        "code_snippet": ""
        if build_data.code_snippet is None
        else build_data.code_snippet,
        "root_dir": root_dir,
        "optional_context": build_data.context or "",
        "requirement_contents": build_data.requirements,
        "reflection": reflection,
        _KEY_CONTEXT_FILE_CONTENT: "",
    }

    if build_data.context:
        logging.info("Attaching context:\n<<<%s>>>", build_data.context)

    project = build_data.project or project
    if project:
        kwargs.update(
            {
                "project_path": project,
                "FILE__project_content": project,
            }
        )

    keys = sorted(kwargs.keys())
    for key in keys:
        if (
            key.startswith(FILE_PREFIX)
            and f"{{{key}}}" in prompt_manager.template_prompt
        ):
            filename = kwargs[key].replace(FILE_PREFIX, "")
            try:
                if filename:
                    content = utils.load_file(filename)
                    kwargs[key] = content
            except Exception as error:
                logging.exception(
                    "Unable to read file `%s`: <<<%s>>>", filename, str(error)
                )
    if context_kwargs:
        # e.g. `optional_examples`
        kwargs.update(context_kwargs)

    if isinstance(context_files, str):
        opt = "optional_context"
        if kwargs.get(opt):
            kwargs[opt] += "\n\n{context_files}"
        else:
            kwargs[opt] = context_files

        context_files = None

    # Add related files if exists
    if build_data.related_files or context_files:
        for file in sorted(
            list(set(list(build_data.related_files or ()) + list(context_files or ())))
        ):
            if file in (build_data.filename, build_data.project):
                continue

            try:
                content = utils.load_file(file)
                logging.info("Attaching `%s` ...", file)
                if content:
                    kwargs[_KEY_CONTEXT_FILE_CONTENT] += (
                        f"File `{file}`:```\n{content}\n```\n"
                    )
                else:
                    logging.info("Attaching a file but invalid content: `%s`.", file)
            except Exception as error:
                logging.exception(
                    "Unable to read file `%s`: <<<%s>>>", file, str(error)
                )
                logging.warning("Attaching a file but unable to read: `%s`.", file)

        if kwargs[_KEY_CONTEXT_FILE_CONTENT]:
            kwargs[_KEY_CONTEXT_FILE_CONTENT] = f"""
Here is more context:

<context_files>
{kwargs[_KEY_CONTEXT_FILE_CONTENT]}
</context_files>
            """.strip()

    return prompt_manager.get(**kwargs)[0], []


class SelfDebugging:
    """Self debugging runner."""

    INVALID_DEPRECATED_API_COUNT = -1

    def __init__(
        self,
        llm_agent: llm_agent_factory.BaseLlmAgent,
        grouped_llm_parser: grouped_llm_parser_factory.BaseLlmParserByGroup,
        prompt_manager: prompt_manager_factory.BasePromptManager,
        repo: git_repo.GitRepo,
        builder: builder_factory.BaseBuilder,
        ast_parser: ast_parser_factory.BaseAstParser,
        file_writer: filesystem_writer_factory.BaseFileSystemWriter,
        config: Optional[config_pb2.Config] = None,
        min_iterations: int = 10,
        n_errors: Optional[float] = None,
        max_n_examples: int = 0,
        max_migration: bool = False,
        enable_reflection: bool = False,
    ):
        self.config = config
        self.min_iterations = min_iterations
        self.n_errors = n_errors
        self.max_n_examples = max_n_examples

        self.llm_agent = llm_agent
        self.grouped_llm_parser = grouped_llm_parser
        self.context_file_llm_parser = llm_parser_factory.create_llm_parser(
            utils.parse_proto(
                TEXT_PROTO_CONTEXT_FILE.replace("CONTEXT_FILE", _KEY_CONTEXT_FILE),
                llm_parser_pb2.LlmParser,  # pylint: disable=no-member
            )
        )
        self.prompt_manager = prompt_manager

        self.repo = repo
        self.builder = builder
        self.ast_parser = ast_parser
        self.ast_helper = ast_helper.AstHelper(
            ast_parser,
            root_dirs=(repo.root_dir,),
            config=config.ast_parser if config else None,
        )
        self.file_writer = file_writer

        # Historical prompts, responses.
        self.last_prompt_messages = None
        self.last_llm_response = None
        self.feedback = []

        # {error_code: {error_msg: list($FIND_REPLACE)}}: The list is dedupped/ essentially a set.
        self.examples_by_code = defaultdict(lambda: defaultdict(list))
        self.traj = trajectory_pb2.Trajectory()
        self.eval_cmd = f"cp {VALIDATION_PATH} {self.repo.root_dir} && cd {self.repo.root_dir} && bash ./validate.sh && rm validate.sh"
        self.max_migration = max_migration
        self.enable_reflection = enable_reflection
        self.show_deprecation_cmd = "mvn clean compile -Dmaven.compiler.showDeprecation=true -Dmaven.compiler.showWarnings=true"
        self.warning_pattern = r"\[WARNING\].*has been deprecated"

    @classmethod
    def create_from_config(
        cls,
        config: config_pb2.Config,
        min_iterations: int = 10,
        n_errors: Optional[float] = None,
        region: str = None,
        **kwargs,
    ):
        """Create from config."""
        ground_truth = "ground_truth"
        if ground_truth in kwargs and not isinstance(kwargs[ground_truth], str):
            github_url, base_commit_id = kwargs[ground_truth]
            config.repo.github_url = github_url
            config.repo.base_commit_id = base_commit_id
            logging.warning("Set repo references: <<<%s>>>", config.repo)

        llm_agent = llm_agent_factory.create_llm_agent(config.llm_agent, region=region)
        llm_parser = grouped_llm_parser_factory.create_grouped_llm_parser(
            config.llm_parser_by_group
        )

        prompt_manager = prompt_manager_factory.create_prompt_manager(
            config.prompt_manager
        )

        new_kwargs = {
            ROOT_DIR: kwargs.get(ROOT_DIR, config.repo.root_dir),
            SOURCE_BRANCH: kwargs.get(SOURCE_BRANCH, config.repo.source_branch),
        }
        if PROJECT in kwargs:
            new_kwargs.update({PROJECT: kwargs.get(PROJECT)})

        repo = git_repo.GitRepo(new_kwargs.get(ROOT_DIR))
        builder = builder_factory.create_builder(
            config.builder, repo=repo, **new_kwargs
        )
        if PROJECT not in kwargs:
            new_kwargs.update(
                {
                    PROJECT: builder.project,
                }
            )

        if config.HasField("ast_parser"):
            ast_parser = ast_parser_factory.create_ast_parser(
                config.ast_parser, **new_kwargs
            )
        else:
            ast_parser = None
        file_writer = filesystem_writer_factory.create_filesystem_writer(
            "PairedFileSystemWriter"
        )

        if config.max_migration:
            max_migration = config.max_migration
        else:
            max_migration = False

        if config.builder.HasField("enable_reflection"):
            enable_reflection = config.builder.enable_reflection
        else:
            enable_reflection = False

        return SelfDebugging(
            llm_agent,
            llm_parser,
            prompt_manager,
            repo,
            builder,
            ast_parser,
            file_writer,
            config,
            min_iterations=min_iterations,
            n_errors=n_errors,
            max_n_examples=config.max_n_examples,
            max_migration=max_migration,
            enable_reflection=enable_reflection,
        )

    def _show_single_ast_info(self, build_error: BuildData):
        """Show AST info based on build error."""
        if self.ast_parser is None or not self.ast_helper.enabled:
            return

        if not build_error.filename or build_error.line_number is None:
            return

        filename = build_error.filename
        cls = self.ast_parser.parse_classes(filename)
        var = self.ast_parser.parse_variables(
            filename, cls, line_number=build_error.line_number
        )
        logging.info(
            "AST for `%s`:\nClasses len = %d:<<<\n%s>>>\nVariables len = %d:<<<\n%s>>>.",
            build_error.filename,
            len(cls),
            cls,
            sum(len(v) for v in var),
            var,
        )

    def _show_ast_info(self, build_errors: Tuple[BuildData]):
        """Show AST info based on build error."""
        if self.ast_parser is None or not self.ast_helper.enabled:
            return

        for build_error in build_errors:
            self._show_single_ast_info(build_error)

    def _update_build_action(
        self, traj, iteration: int, build_errors: Tuple[BuildData]
    ):
        step = traj.steps.add()

        step.iteration = iteration
        step.action.build_action.num_errors = len(build_errors)
        if not build_errors:
            return traj

        first_error = step.action.build_action.first_error
        error = build_errors[0]
        if error.filename:
            first_error.filename = error.filename
        if error.line_number is not None:
            first_error.line_number = error.line_number
        if error.column_number is not None:
            first_error.column_number = error.column_number
        if error.error_code is not None:
            first_error.error_code = error.error_code
        first_error.error_message = error.error_message

        return traj

    def _update_git_commit_action(self, traj, iteration: int, commit_msg: str):
        step = traj.steps.add()

        step.iteration = iteration
        step.action.git_action.git_option = trajectory_pb2.GitAction.COMMIT_ALL
        step.action.git_action.commit_message = commit_msg

        return traj

    def _update_git_revert_action(self, traj, iteration: int, revert_msg: str):
        step = traj.steps.add()

        step.iteration = iteration
        step.action.git_action.git_option = trajectory_pb2.GitAction.REVERT
        step.action.git_action.revert_message = revert_msg

        return traj

    def update_jdk_related(self):
        root_dir = self.repo.root_dir
        if not Path(os.path.join(root_dir, "pom.xml")).exists():
            raise ValueError(
                f"No `pom.xml` file found in repository root dir {root_dir}."
            )

        pom_files = sorted(
            glob.glob(os.path.join(root_dir, "**", "pom.xml"), recursive=True)
        )
        logging.warning(
            "Number of pom.xml files to update = %d: `%s`.", len(pom_files), pom_files
        )
        for pom_file in pom_files:
            pom_utils.update_jdk_related(pom_file, pom_file)

    def update_dependency_version(self):
        root_dir = self.repo.root_dir
        dependency_version = utils.load_json(eval_utils.DEPENDENCY_VERSION)

        if not Path(os.path.join(root_dir, "pom.xml")).exists():
            raise ValueError(
                f"No `pom.xml` file found in repository root dir {root_dir}."
            )

        pom_files = sorted(
            glob.glob(os.path.join(root_dir, "**", "pom.xml"), recursive=True)
        )
        logging.warning(
            "Number of pom.xml files to update = %d: `%s`.", len(pom_files), pom_files
        )
        for pom_file in pom_files:
            pom_utils.apply_selected_notes(pom_file, dependency_version)

    def run(
        self, max_iterations: int = 1, dry_run: bool = False
    ) -> Tuple[metrics_pb2.Metrics, Tuple[BuildData]]:
        """Run llm until success or reaching max iterations."""
        self.traj = trajectory_pb2.Trajectory()

        proto = metrics_pb2.Metrics()
        proto.final_state_metrics.h_min_iterations = self.min_iterations
        proto.final_state_metrics.h_max_iterations = max_iterations
        if self.n_errors is not None:
            proto.final_state_metrics.h_num_errors_factor = self.n_errors

        input_iterations = max_iterations

        iteration = -1
        if self.max_migration:
            self.update_dependency_version()
            self.repo.commit_all("update dependency versions")
        # **NOT** applying any rules.
        build_errors = self._pre_llm(
            max_iterations, iteration, max_rounds=0, update_errors=False
        )[0]
        self.traj = self._update_build_action(self.traj, iteration, build_errors)
        proto.initial_state_metrics.success = not bool(build_errors)
        proto.initial_state_metrics.num_errors = len(build_errors)
        proto.initial_state_metrics.iteration = iteration

        if not proto.initial_state_metrics.success:
            # Rules to be applied only once.
            if self.builder.maybe_apply_oneoff_rules(build_errors):
                logging.info("One off rules are applied.")
                if self.repo:
                    commit_msg = (
                        f"Iteration {iteration} (one-off): "
                        "Apply rules before running any other rules or LLMs."
                    )
                    self.repo.commit_all(commit_msg)
                    self.traj = self._update_git_commit_action(
                        self.traj, iteration, commit_msg
                    )

            # Rules to be applied at the beginning or could be anytime during the iterations.
            build_errors, rules_applied = self._pre_llm(
                max_iterations, iteration, update_errors=False
            )
            self.traj = self._update_build_action(self.traj, iteration, build_errors)

            if rules_applied and self.repo:
                commit_msg = (
                    f"Iteration {iteration} (again): Apply rules before running LLMs. "
                    f"Build errors # = {len(build_errors)} <== "
                    f"{proto.initial_state_metrics.num_errors}."
                )
                self.repo.commit_all(commit_msg)
                self.traj = self._update_git_commit_action(
                    self.traj, iteration, commit_msg
                )

            iteration = 0

            state = proto.intermediate_state_metrics.add()
            state.success = not bool(build_errors)
            state.num_errors = len(build_errors)
            state.iteration = iteration
        else:
            # No op at all.
            pass

        max_iterations = min(
            (
                max_iterations,
                max_iterations
                if self.n_errors is None
                else max(
                    (
                        self.min_iterations,
                        int(len(build_errors) * self.n_errors),
                    )
                ),
            )
        )
        self.traj.root_dir = self.builder.root_dir
        if self.builder.project:
            self.traj.project = self.builder.project
        self.traj.max_iterations = max_iterations

        proto.final_state_metrics.max_iterations = max_iterations
        logging.info(
            "Max iterations = %d: (min, max, #, factor) = (%d, %d, %d, %f)",
            max_iterations,
            self.min_iterations,
            input_iterations,
            len(build_errors),
            -1 if self.n_errors is None else self.n_errors,
        )

        if dry_run:
            self._show_ast_info(build_errors)
            for error in build_errors:
                self.ast_helper.run(error)

        success = not bool(build_errors)
        start_time = time.time()
        while not success and iteration < max_iterations:
            if time.time() - start_time > DEBUG_TIMEOUT:
                break
            if iteration == 0:
                self.builder.previous_build_errors = build_errors

            iteration += 1

            logging.info(
                "Migration iteration %d: errors = %d ...", iteration, len(build_errors)
            )
            build_errors, iter_success = self.run_iteration(
                build_errors, max_iterations, iteration, dry_run
            )
            self.traj = self._update_build_action(self.traj, iteration, build_errors)

            if not isinstance(build_errors, (tuple, list)):
                copy_errors = build_errors
                build_errors = self._pre_llm(max_iterations, iteration)[0]
                self.traj = self._update_build_action(
                    self.traj, iteration, build_errors
                )

                # Unrecoverable errors.
                if isinstance(copy_errors, Exception):
                    success = not bool(build_errors)
                    break

            if iter_success:
                success = True
                break

            if iteration >= max_iterations:
                logging.warning(
                    "Job is unable to finish successfully, ending with %d errors: <<<%s>>>",
                    len(build_errors),
                    build_errors,
                )
                for index, build_error in enumerate(build_errors):
                    logging.info(
                        "[%02d/%02d] Build Error: <<<%s>>",
                        index,
                        len(build_errors),
                        build_error,
                    )
                break

        # validate class file is of version 61
        java_job = self.config.builder.HasField("maven_builder")
        if success and java_job:
            logging.info("Migration finished. Evaluating...")
            cmd_data = utils.do_run_command(self.eval_cmd)
            logging.info(cmd_data.stdout)
            if cmd_data.return_code != 0:
                logging.warning(
                    "Migration failed and it's inconsistent with SD reporetd success: `%s`.",
                    self.repo.root_dir,
                )
                success = False

        # Final eval for success
        final_success = success
        if java_job:
            github_url = self.config.repo.github_url
            if not github_url:
                github_url = self.repo.get_github_url()
                logging.warning(
                    "Inferred github url: `%s` <= `%s`.", github_url, self.repo.root_dir
                )

                if github_url[-1]:
                    github_url = github_url[0]
                else:
                    github_url = None

            base_commit_id = (
                self.config.repo.base_commit_id or self.config.repo.source_branch
            )
            if base_commit_id:
                with tempfile.TemporaryDirectory() as temp_dir:
                    git_diff_file = os.path.join(temp_dir, "git.diff")
                    self.repo.diff(stdout=git_diff_file, files=[base_commit_id, "."])
                    logging.warning(
                        "Export `git diff %s` to file: `%s` for `%s`.",
                        base_commit_id,
                        git_diff_file,
                        github_url,
                    )

                    if (
                        self.config.builder.HasField("maven_builder")
                        and self.config.builder.maven_builder.build_command.strip().endswith(
                            " compile"
                        )
                    ):
                        maven_command = maven_utils.MVN_CLEAN_COMPILE
                        eval_kwargs = {
                            "eval_num_tests": False,
                            "eval_list_tests": False,
                        }
                    else:
                        maven_command = maven_utils.MVN_CLEAN_VERIFY
                        eval_kwargs = {}
                    final_success = (not java_job) or final_eval.run_eval(
                        github_url,
                        git_diff_file,
                        require_maximal_migration=self.max_migration,
                        maven_command=maven_command,
                        **eval_kwargs,
                    )
            else:
                logging.warning(
                    "Unable to get the right commit id from `%s`.", self.config.repo
                )
                final_success = False

        # count deprecated api
        deprecated_api = self.count_deprecated_apis() if java_job else -1

        proto.final_state_metrics.state.success = final_success
        proto.final_state_metrics.state.num_errors = len(build_errors)
        proto.final_state_metrics.iterations = iteration
        proto.final_state_metrics.deprecated_api = deprecated_api

        if self.repo:
            _, filename = tempfile.mkstemp(
                dir=self.builder.root_dir, prefix="trajectory--", suffix=".pbtxt"
            )
        else:
            filename = None
        try:
            if self.repo:
                utils.export_proto(self.traj, filename)

                commit_msg = (
                    f"nit: Add trajectory file at iteration {iteration} {filename}."
                )
                self.repo.commit_all(commit_msg)
        except Exception as error:
            logging.exception("Unable to export to file `%s`: `%s`.", filename, error)

        return proto, tuple(build_errors)

    def max_migration_evaluate(self) -> bool:
        dep_meet_requirement = eval_utils.check_version(self.repo.root_dir)
        if not dep_meet_requirement:
            logging.warning(
                "Unable to pass max migration for: `%s`.", self.repo.root_dir
            )

        return dep_meet_requirement

    def count_deprecated_apis(self):
        result = utils.do_run_command(self.show_deprecation_cmd, cwd=self.repo.root_dir)
        mvn_build_log = result.stdout
        if mvn_build_log is not None:
            matches = re.findall(self.warning_pattern, mvn_build_log)
        else:
            matches = []
        if result.return_code == 0 or len(matches) > 0:
            return len(matches)
        return self.INVALID_DEPRECATED_API_COUNT

    def _pre_llm(
        self,
        max_iterations: int,
        iteration: int,
        max_rounds: int = 10,
        update_errors: bool = True,
    ) -> Tuple[Tuple[Any], bool]:
        """Before LLM: Build."""
        if iteration <= 0 and max_rounds != 10:
            logging.info(
                "Rerun build (iteration, max_rounds) = (%d, %d).", iteration, max_rounds
            )

        rules_applied = False
        if _APPLY_RULES:
            build_errors = self.builder.run(update_errors=False)
            # Maybe upgrade packages.
            if self.ast_helper and self.ast_helper.enabled_for_package_upgrade:

                def get_packages():
                    return self.ast_helper.parser.parse_packages()

                while max_rounds > 0 and self.builder.maybe_apply_rules(
                    build_errors, get_packages
                ):
                    rules_applied = True
                    build_errors, _ = self._pre_llm(
                        max_iterations, iteration, max_rounds - 1, update_errors=False
                    )

        # TODO(sliuxl): Dedup `build` runs.
        build_errors = self.builder.run(update_errors=update_errors)
        if isinstance(build_errors, str):
            logging.fatal("Failing with: %s.", build_errors)
            raise ValueError(build_errors)

        if not build_errors:
            logging.info(
                "Job finishes successfully, at iteration %d/ %d.",
                iteration,
                max_iterations,
            )

        return tuple(build_errors), rules_applied

    def _llm(
        self, iteration: int, build_data: builder_factory.BuildData, context_files=None
    ) -> str:
        """Call LLM."""
        # Normalize file before sending to LLM.
        normalized_files = []
        for filename in (build_data.filename, self.builder.project) + tuple(
            (() if isinstance(context_files, str) else (context_files or ()))
        ):
            if utils.normalize_file(filename):
                normalized_files.append(filename)
        if normalized_files:
            commit_msg = (
                f"nit: Normalize files at iteration {iteration}: {normalized_files}."
            )
            self.repo.commit_all(commit_msg)
            self.traj = self._update_git_commit_action(self.traj, iteration, commit_msg)

        context_kwargs = (
            {} if self.ast_helper is None else self.ast_helper.run(build_data)
        )

        # Add positive examples in previous iterations.
        optional_examples = ""
        if build_data.error_code in self.examples_by_code:
            # 1. Exact error messages.
            optional_examples = self.examples_by_code[build_data.error_code][
                build_data.error_message
            ]
            # 2. Same error code with different error messages.
            if len(optional_examples) < self.max_n_examples:
                for index in range(self.max_n_examples):
                    updated = False
                    for e_msg, e_patches in sorted(
                        self.examples_by_code[build_data.error_code].items()
                    ):
                        # Skip exact error messages: Added before.
                        if e_msg == build_data.error_message:
                            continue
                        if (
                            len(e_patches) > index
                            and e_patches[index] not in optional_examples
                        ):
                            optional_examples.append(e_patches[index])
                            updated = True

                    # Enough examples are added, or there are no other examples to add.
                    if len(optional_examples) >= self.max_n_examples or not updated:
                        break
            optional_examples = optional_examples[: self.max_n_examples]
            if optional_examples:
                n_examples = len(optional_examples)
                logging.info(
                    "Add `%d` examples for error code: `%s`.",
                    n_examples,
                    build_data.error_code,
                )
                optional_examples = "\n\n".join(
                    [f"<example>\n{ex}\n</example>" for ex in optional_examples]
                )
                optional_examples = f"The following are a few examples for the same error code ({build_data.error_code}):\n{optional_examples}"  # pylint: disable=line-too-long
                optional_examples = f"<examples>\n{optional_examples}\n</examples>"
                logging.debug(
                    "Add `%d` examples for error code `%s`: <<<\n%s\n>>>",
                    n_examples,
                    build_data.error_code,
                    optional_examples,
                )
            else:
                optional_examples = ""
        context_kwargs.update(
            {
                "optional_examples": optional_examples,
            }
        )

        # Add reflection if error appeared before
        reflection = None
        if self.enable_reflection:
            from common.reflection import ReflectiveDebugger, error_in_traj

            llm_fix = error_in_traj(build_data, self.traj)
            if llm_fix:
                logging.info("Error appeared before, add reflection.")
                debugger = ReflectiveDebugger(llm_agent=self.llm_agent)
                reflection = debugger.analyze_fix(
                    build_data.filename, build_data.error_message, llm_fix
                )
                reflection = f"You've tried a fix before and was incorrect. Below are the feedbacks\n<feedback>\n{reflection}\n</feedback>"

        prompt, self.last_prompt_messages = prepare_prompt(
            self.builder.root_dir,
            self.prompt_manager,
            build_data,
            self.builder.project,
            self.last_prompt_messages,
            self.last_llm_response,
            self.feedback,
            self.config.prompt_manager.restart_messages_len_gt,
            context_files or (),
            context_kwargs,
            reflection,
        )
        response = self.llm_agent.run(prompt, messages=self.last_prompt_messages[:])

        # Update  trajectory.
        llm_step = self.traj.steps.add()
        llm_step.iteration = iteration
        llm_ac = llm_step.action.llm_action
        if self.last_prompt_messages:
            llm_ac.prompt.prompt_messages.role = self.last_prompt_messages[0].get(
                "role", "user"
            )
            llm_ac.prompt.prompt_messages.messages.extend(
                [
                    self._extract_string_from_content(msg.get("content", ""))
                    for msg in self.last_prompt_messages
                ]
                + [prompt]
            )
        else:
            llm_ac.prompt.prompt = prompt
        llm_ac.response = response

        self.last_prompt_messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )
        self.last_llm_response = response

        # Check for requests for context.
        if self.config.builder.max_context_files:
            context_files = self.context_file_llm_parser.parse_llm(response)
            if context_files:
                logging.debug("Context files (raw) : <<<%s>>>", context_files)

                context_files = sorted(
                    list(
                        set(
                            itertools.chain.from_iterable(
                                c.find.strip().splitlines()
                                for c in context_files
                                if c.find
                            )
                        )
                    )
                )
                logging.debug("Context files (parsed) : <<<%s>>>", context_files)

                raw_context_files = context_files
                context_files = [c for c in context_files if os.path.exists(c)]

                if not context_files and len(raw_context_files) == 1:
                    fn = raw_context_files[0]
                    rel_dir = os.path.relpath(fn, self.repo.root_dir)

                    short_d = os.path.join(
                        self.repo.root_dir, rel_dir.split(os.path.sep)[0]
                    )
                    short_f = os.path.basename(fn)
                    context_files = utils.find_files(short_d, short_f)
                    logging.warning(
                        "Unable to get `%s`: Try with the same filename instead ==> len = %02d (%s).",
                        fn,
                        len(context_files),
                        context_files,
                    )

                    if context_files:
                        context_files = "\n".join(
                            f"{index}. {f}" for index, f in enumerate(context_files)
                        )

                        context_files = f"""
There is not such a file `{fn}`, but I provide all files with the same names under `{short_d}`:

{context_files}
                        """.strip()

            else:
                logging.info("No requests for context files.")

            if context_files:
                logging.info(
                    "Context files: <<<%s>>> from <<<%s>>>.", context_files, response
                )
                return self._llm(iteration, build_data, context_files)

        return response

    def _extract_string_from_content(self, content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return content[0]["text"]

        raise ValueError(
            f"Not sure how to extract context from `{type(content)}`: <<<{content}>>>"
        )

    def _post_llm(
        self,
        build_data: builder_factory.BuildData,
        max_iterations: int,
        iteration: int,
        llm_response: str,
        build_errors: Tuple[BuildData],
    ) -> Tuple[BuildData]:
        """After LLM: Patch changes if any."""
        # Parse changes.
        grouped_changes, parsed_llm_response = self.grouped_llm_parser.run(llm_response)
        logging.info("Files to change: # = %d.", len(grouped_changes))
        feedback = self.grouped_llm_parser.collect_feedback(reset=True)
        if feedback is not None:
            self.feedback.append(feedback)
            logging.warning(
                "Feedback from LLM parser, skip to next. <<<%s>>>", feedback
            )
            return build_errors

        # Patch changes.
        patched = self.file_writer.run(grouped_changes)
        feedback = self.file_writer.collect_feedback(reset=True)
        if any(patched.values()):
            if feedback is not None:
                logging.warning(
                    "Feedback from LLM response patcher will be ignored, "
                    "as other files are patched: <<<%s>>>",
                    feedback,
                )
            self.repo.add_all()
        else:
            if feedback is None:
                logging.warning(
                    "Unable to get feedback from LLM patches, though it didn't succeed."
                    "Setting it to be generic."
                )
                feedback = "Unable to parse the response and patch relevant files."
            self.feedback.append(feedback)
            logging.warning(
                "Feedback from LLM response patcher, skip to next. <<<%s>>>", feedback
            )
            return build_errors

        new_build_errors = self._pre_llm(max_iterations, iteration)[0]

        feedback = self.builder.collect_feedback()
        # Build errors change.
        if feedback is None:
            self.feedback = []

            # Git commit.
            commit_msg = (
                f"Iteration {iteration}: "
                f"Build errors # = {len(new_build_errors)} <== {len(build_errors)}.\n\n"
                f"{str(build_data)}"
            )
            self.repo.commit_all(commit_msg)

            # Add positive examples: Up to 3 per (error code, error message).
            example_list = self.examples_by_code[build_data.error_code][
                build_data.error_message
            ]
            if (
                len(example_list) < self.max_n_examples
                and parsed_llm_response not in example_list
            ):
                example_list.append(parsed_llm_response)
            self.traj = self._update_git_commit_action(self.traj, iteration, commit_msg)

            return new_build_errors

        # Use the parsed content only.
        self.last_llm_response = parsed_llm_response

        self.feedback.append(feedback)
        logging.warning(
            "Feedback from builder: Revert LLM changes. <<<%s>>>@%d",
            feedback,
            iteration,
        )

        self.repo.restore()
        self.traj = self._update_git_revert_action(self.traj, iteration, feedback)

        # TODO(sliuxl): Find out whether we need to rebuild again, probably not needed.
        self.builder.previous_build_errors = build_errors
        self.builder._reset_feedback()

        return build_errors

    def run_iteration(
        self,
        build_errors: Tuple[BuildData],
        max_iterations: int,
        iteration: int,
        dry_run: bool = False,
    ) -> Tuple[Tuple[BuildData], bool]:
        """Run llm iteration."""
        maybe_error = None
        try:
            # 1. Interaction with LLM: Get a new prompt and response for the first build error.
            build_data = build_errors[0]
            logging.info("==============================")
            logging.info(
                "Addressing build error@%d: <<<%s>>>.", iteration, str(build_data)
            )
            logging.info("==============================")

            if dry_run:
                logging.debug("LLM call is skipped with dry run mode @%d.", iteration)
                llm_response = ""
            else:
                llm_response = self._llm(iteration, build_data)
            logging.info("LLM response @%d: <<<%s>>>.", iteration, llm_response)
            self.last_llm_response = llm_response

            # 2. Post processing.
            build_errors = self._post_llm(
                build_data, max_iterations, iteration, llm_response, build_errors
            )

            return build_errors, not bool(build_errors)
        except Exception as error:
            logging.exception("Unable to run iteration successfully: <<<%s>>>", error)
            maybe_error = error

        return maybe_error if maybe_error else None, False
