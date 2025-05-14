"""Maven util functions."""

import logging
import os
import time

from self_debug.common import utils


MAVEN_DEP_LINE_START = "[INFO] The following files have been resolved:"
MAVEN_DEP_LINE_END = "[INFO] BUILD SUCCESS"

ARG_TIME_OUT_SECONDS = "timeout"

# pylint: disable=broad-exception-caught,too-many-branches,too-many-locals,too-many-nested-blocks,too-many-return-statements
MVN__MAX_ATTEMPTS = 10
MVN__SLEEP_SECONDS = 30


MVN_CLEAN_COMPILE = "cd {root_dir}; mvn clean compile"
MVN_CLEAN_VERIFY = "cd {root_dir}; mvn clean verify"
MVN_NUM_TESTS = "cd {root_dir}; mvn test -f ."

MVN_DEPENDENCY_DOWNLOADING_PREFIX = "\nDownloading from "
MVN_DEPENDENCY_DOWNLOADED_PRFEIX = "\nDownloaded from "

MVN_DEPENDENCY_RESOLVE = "mvn dependency:resolve"
MVN_DEPENDENCY_RESOLVE_MAX_ATTEMPTS = MVN__MAX_ATTEMPTS
MVN_DEPENDENCY_RESOLVE_SLEEP_SECONDS = MVN__SLEEP_SECONDS

MVN_EFFECTIVE_POM = "mvn help:effective-pom"
MVN_EFFECTIVE_POM_TO_FILE = "mvn help:effective-pom -Doutput={POM}"
MVN_EFFECTIVE_POM_MAX_ATTEMPTS = 2
MVN_EFFECTIVE_POM_SLEEP_SECONDS = 2

MVN_TIMEOUT_SECONDS = 300  # 5 min


def replace_maven_command(
    command: str, new_partial_command: str = MVN_DEPENDENCY_RESOLVE
):
    """Replace maven command."""
    if not isinstance(command, str):
        raise ValueError(f"Mvn command is not a str: `{command}`.")

    segments = command.split("mvn ")
    if len(segments) <= 1:
        logging.warning("No `mvn ` in command: `{command}`.")
        return command, False

    cmd = "mvn ".join(segments[:-1])
    cmd += new_partial_command

    replaced = cmd != command
    if replaced:
        logging.info("Run `%s` before `%s`.", cmd, command)

    return cmd, replaced


def do_run_maven_command(command: str, **kwargs):
    """Run maven."""
    start_time = time.time()

    max_attempts = kwargs.pop(
        "MVN_DEPENDENCY_RESOLVE_MAX_ATTEMPTS", MVN_DEPENDENCY_RESOLVE_MAX_ATTEMPTS
    )

    # Run dependency command.
    cmd, replaced = replace_maven_command(command, MVN_DEPENDENCY_RESOLVE)
    for index in range(max_attempts if replaced else 0):
        run_kwargs = dict(kwargs)
        if ARG_TIME_OUT_SECONDS in kwargs:
            runtime_seconds = time.time() - start_time
            run_kwargs[ARG_TIME_OUT_SECONDS] -= runtime_seconds
            if run_kwargs[ARG_TIME_OUT_SECONDS] <= 0:
                logging.warning(
                    "[%d] Unable to finish running `%s` before timeout `%s`.",
                    index,
                    cmd,
                    kwargs[ARG_TIME_OUT_SECONDS],
                )
                break

        result = utils.do_run_command(cmd, **run_kwargs)
        if result.return_code == 0:
            break

        wip = False
        for std in (result.stdout, result.stderr):
            if not std:
                continue

            if (
                MVN_DEPENDENCY_DOWNLOADING_PREFIX in std
                or MVN_DEPENDENCY_DOWNLOADED_PRFEIX in std
            ):
                wip = True

        msg = "" if wip else "[FINAL]"
        msg = f"[{index}/{max_attempts}]{msg} Unable to resolve maven dependency ({cmd}): <<<{result}>>>"
        logging.warning(msg)

        if not wip:
            break

        if index < max_attempts - 1:
            time.sleep(MVN_DEPENDENCY_RESOLVE_SLEEP_SECONDS)

    run_kwargs = dict(kwargs)
    if ARG_TIME_OUT_SECONDS in kwargs:
        runtime_seconds = time.time() - start_time
        run_kwargs[ARG_TIME_OUT_SECONDS] -= runtime_seconds
        run_kwargs[ARG_TIME_OUT_SECONDS] = max(
            MVN_TIMEOUT_SECONDS, run_kwargs[ARG_TIME_OUT_SECONDS]
        )

    # Run the given command.
    return utils.do_run_command(command, **run_kwargs)


def parse_maven_dependency(filename: str):
    """Parse maven dependencies."""
    content = utils.load_file(filename)
    if content is None:
        return None

    segments = content.split(f"\n{MAVEN_DEP_LINE_START}\n")
    if len(segments) < 2:
        return None

    content = segments[-1]
    segments = content.split(f"\n{MAVEN_DEP_LINE_END}\n")
    if len(segments) < 2:
        return None

    content = segments[0]
    lines = content.splitlines()[:-1]

    deps = set()
    short_deps = set()
    for line in lines:
        if not line.startswith("[INFO] "):
            continue

        dep = line[6:].strip()
        if not dep:
            break

        logging.debug("Dep: `%s`", dep)
        deps.add(dep)
        short_deps.add(dep.split()[0])

    return deps, short_deps


def _run():
    java_homes = (
        "/usr/lib/jvm/java-1.8.0-amazon-corretto.x86_64",
        "/usr/lib/jvm/java-1.8.0-amazon-corretto.x86_64/jre",
        "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.432.b06-1.amzn2.0.1.x86_64",
        "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.432.b06-1.amzn2.0.1.x86_64/jre",
        "/usr/lib/jvm/java-17-amazon-corretto.x86_64",
    )
    java_dir = "/home/sliuxl/github/xresloader"

    from self_debug.common import hash_utils

    for java_home in java_homes:
        if not os.path.exists(java_home):
            continue

        logging.info(
            utils.run_command(f"JAVA_HOME={java_home} mvn --version", check=False)
        )
        for cmd in (
            MVN_EFFECTIVE_POM,
            MVN_EFFECTIVE_POM_TO_FILE.format(POM="/tmp/effective-pom.xml"),
        ):
            logging.info(
                utils.run_command(
                    f"JAVA_HOME={java_home} {cmd}", cwd=java_dir, check=False
                )
            )

        result = do_run_maven_command(
            MVN_NUM_TESTS.replace(" mvn ", f" JAVA_HOME={java_home} mvn ").format(
                root_dir=java_dir
            ),
            check=False,
            # MVN_DEPENDENCY_RESOLVE_MAX_ATTEMPTS=1,
        )
        logging.info(
            "#tests = %d: `%s`.",
            hash_utils.get_num_test_cases(java_dir, result.stdout),
            result,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    _run()
