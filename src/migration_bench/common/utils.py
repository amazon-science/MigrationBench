"""Util functions."""

from contextlib import ContextDecorator
from dataclasses import dataclass
import glob
import json
import logging
import os
import re
import subprocess
import tempfile
import time
from typing import Any, Dict, Optional, Sequence, Tuple, Union

from google.protobuf import text_format
import requests


SKIP_SPARK_PREFIX = "SKIP-SPARK-METRICS-"


BRAZIL_SRC = "src"
FIX_UTF8 = "ignore"

ENABLE_FEEDBACK = "enable_feedback"
GIT_LINE_CHANGES_PATTERN = r"^@@\s+-(\d+)(,(\d+))?\s+\+(\d+)(,(\d+))?\s+@@.*$"
LOGGING_FORMAT = "%(asctime)s [%(filename)s:%(lineno)d] %(levelname)s - %(message)s"

NEW_LINE = os.linesep
WINDOWS_NEWLINE_BR = b"\r"

# 301: Moved Permanently redirection
GITHUB_VALID_CODES = (200, 301)
GITHUB_INVALID_CODES = (404,)

GITHUB_URL = "https://github.com/klee-contrib/kinetix"

_PWD = os.path.dirname(os.path.abspath(__file__))


@dataclass
class CmdData:
    """Build error data."""

    stdout: Optional[str]
    return_code: int

    stderr: str = ""
    error: Any = None


def do_run_command(command: Union[str, Sequence[str]], **kwargs) -> CmdData:
    """
    Runs a command and returns the output and success status.

    Args:
        command (str): The command to run.

    Returns:
        Tuple[Union[str, Exception], bool]: A tuple containing the output (either a string or an
            Exception) and a boolean indicating whether the command was successful.
    """
    try:
        logging.info("CMD: %s", command)
        result = subprocess.run(
            command,
            stdout=kwargs.pop("stdout", subprocess.PIPE),
            stderr=subprocess.PIPE,
            shell=kwargs.pop("shell", True),
            check=kwargs.pop("check", True),
            **kwargs,
        )

        stdout = result.stdout.decode().strip()
        stderr = result.stderr.decode().strip()
        code = result.returncode

        logging.debug("CMD: %s => STDOUT: %s", command, stdout)
        logging.debug("CMD: %s => STDERR: %s", command, stderr)
        logging.debug(
            "CMD: %s => RETURN CODE: `%s` (type `%s`)", command, code, type(code)
        )
        return CmdData(
            stdout=stdout,
            stderr=stderr,
            return_code=code,
        )
    except Exception as error:
        logging.warning("CMD: %s => ERROR: %s", command, str(error))

        return CmdData(
            stdout=None,
            return_code=None,
            error=error,
        )


def run_command(*args, **kwargs) -> Tuple[Union[str, Exception], int]:
    """Run command."""
    result = do_run_command(*args, **kwargs)

    if result.error is None:
        return result.stdout, result.return_code == 0

    return result.error, result.return_code == 0


def copy_dir(root_dir: str, **kwargs) -> str:
    """Get a new root dir: cp -r $FROM $TO."""
    root_dir = os.path.abspath(root_dir)
    logging.debug("Copy from dir: `%s` (%s).", root_dir, os.path.exists(root_dir))

    if root_dir.endswith(os.path.sep):
        root_dir.pop(-1)

    basename = os.path.basename(root_dir)

    temp_dir = tempfile.mkdtemp(**kwargs)
    logging.info("Created new dir: `%s`.", temp_dir)

    run_command(["cp", "-r", root_dir, temp_dir], shell=False)

    new_root_dir = os.path.join(temp_dir, basename)
    if not os.path.exists(new_root_dir):
        raise ValueError(f"Unable to cp to `{new_root_dir}` from `{root_dir}`.")

    return new_root_dir


def load_file(
    filename: str, mode: str = "r", log: bool = True, fix: str = "ignore"
) -> str:
    """Load content from a file."""
    if log:
        logging.info("Reading `%s`.", filename)

    if not os.path.exists(filename):
        return None

    try:
        with open(filename, mode) as ifile:  # pylint: disable=unspecified-encoding
            return ifile.read()
    except Exception as error:
        logging.exception("Unable to load file `%s`: <<<%s>>>", filename, error)
        if "b" in mode or not fix:
            return None

    try:
        with open(filename, f"{mode}b") as ifile:  # pylint: disable=unspecified-encoding
            data = ifile.read()
            if fix == "latin-1":
                text = data.decode("latin-1")
            else:
                if fix != "ignore":
                    logging.warning(
                        "Unknown fix mode = `%s`, using ignore instead.", fix
                    )
                text = data.decode("utf-8", errors="ignore")
            return text
    except Exception as error:
        logging.exception("[Retry] Unable to load file `%s`: <<<%s>>>", filename, error)

    return None


def export_file(filename: str, content: str, mode: str = "w", log: bool = True):
    """Export proto to a file."""
    if log:
        logging.info("Writing `%s`.", filename)

    dirname = os.path.dirname(os.path.abspath(filename))
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    with open(filename, mode) as ofile:  # pylint: disable=unspecified-encoding
        ofile.write(content)


def load_json(filename: str, mode: str = "r", log: bool = True) -> Dict[Any, Any]:
    """Load json file."""
    if log:
        logging.info("Reading `%s`.", filename)

    if not os.path.exists(filename):
        return None

    with open(filename, mode) as ifile:  # pylint: disable=unspecified-encoding
        return json.load(ifile)


def export_json(
    filename: str, data: Dict[Any, Any], mode: str = "w", log: bool = True, **kwargs
):
    """Load json file."""
    if log:
        logging.info("Writting `%s`.", filename)

    # json_data = json.dumps(data)
    sort_keys = kwargs.pop("sort_keys", True)
    indent = kwargs.pop("indent", 2)
    with open(filename, mode) as ofile:  # pylint: disable=unspecified-encoding
        json.dump(data, ofile, sort_keys=sort_keys, indent=indent, **kwargs)
        # ofile.write(json_data)


def parse_proto(text_proto: str, proto_type):
    """Parse text proto."""
    return text_format.Parse(text_proto, proto_type())


def load_proto(filename: str, proto_type):
    """Load proto from a file."""
    return parse_proto(load_file(filename), proto_type)


def str_proto(proto: Any):
    """Export proto to a file."""
    return text_format.MessageToString(proto)


def export_proto(proto: Any, filename: str):
    """Export proto to a file."""
    export_file(filename, str_proto(proto))


def find_files(root_dir: str, filename: str) -> Tuple[str]:
    """Find file by name."""
    files, success = run_command(f"find {root_dir} -name {filename}")
    if not success:
        return ()

    files = files.split(NEW_LINE)
    return tuple(sorted(os.path.abspath(os.path.join(root_dir, f)) for f in files if f))


def normalize_file(filename: Optional[str]) -> bool:
    """Normalize content in a file, removing ^M."""
    if not filename or not os.path.exists(filename):
        return False

    bin_content = load_file(filename, "rb")

    bin_content_update = bin_content.replace(b"\r", b"")

    changed = bin_content != bin_content_update
    if changed:
        export_file(filename, bin_content_update, "wb")

    return changed


def count_dirs(dirname: str):
    """Count dirs."""
    try:
        os_walk = list(
            1
            for root, dirs, _ in os.walk(dirname)
            if (
                not root.endswith("__pycache__")
                and "/__pycache__/" not in root
                and dirs not in ("__pycache__",)
            )
        )

        return len(os_walk)
    except Exception as error:
        logging.warning("Unable to count dirs for `%s`: <<<%s>>>", dirname, str(error))
        return 0


def count_java_files(
    dirname: str, exclude_test_files: bool = False
) -> Tuple[int, int, int]:
    """Count java files: (#.java, #dir, #.java non-test)."""
    files = glob.glob(f"{dirname}/**/*.java", recursive=True)
    total = len(files)

    dirs_00 = count_dirs(dirname)
    dirs_01 = len(set(os.path.dirname(f) for f in files))

    if exclude_test_files:
        files = [
            f
            for f in files
            if not f.endswith("Test.java") and not f.endswith("Tests.java")
        ]

    return total, dirs_00, dirs_01, len(files)


def count_py_files(
    dirname: str, exclude_test_files: bool = False
) -> Tuple[int, int, int]:
    """Count py files: (#.py, #dir, #.py non-test)."""
    files = glob.glob(f"{dirname}/**/*.py", recursive=True)
    total = len(files)

    dirs_00 = count_dirs(dirname)
    dirs_01 = len(set(os.path.dirname(f) for f in files))

    if exclude_test_files:
        files = [
            f
            for f in files
            if not f.endswith("_test.py")
            and not os.path.basename(f).startswith("test_")
        ]

    return total, dirs_00, dirs_01, len(files)


def _parse_compiled_java_major_versions(output: str):
    """Parse compiled java major versions."""
    lines = set(l.strip() for l in output.splitlines() if l.strip())

    versions = set()
    for line in lines:
        match = re.match(r"\s*major version:\s+(\d+)\s*$", line)
        if match:
            versions.add(int(match.group(1)))
        else:
            logging.warning("Unable to resolve compiled Java version: <<<%s>>>", line)
    return versions


def get_compiled_java_major_versions(
    root_dir: str, num_options=2, java_home: str = None
):
    """Get compiled java major versions, after `mvn clean verify` is a success."""
    if not os.path.exists(root_dir):
        return None

    for index, class_regex in enumerate(
        (
            "*/target/classes/*.class",
            # There might be customized class dir specified in `pom.xml` files.
            "*.class",
        )[:num_options]
    ):
        if index == 1:
            # Exclude test folders.
            extra_cmd = " | grep -v -i test"
        else:
            extra_cmd = ""

        if java_home:
            java_home = os.path.join(java_home, "bin/")
        else:
            java_home = ""

        cmd = f"find {root_dir} -type f -path '{class_regex}'{extra_cmd} | xargs {java_home}javap -verbose | grep 'major version: '"  # pylint: disable=line-too-long
        output, success = run_command(cmd)

        if success:
            return _parse_compiled_java_major_versions(output)

        logging.warning(
            "[%d] Unable to get *.classes files with regex `%s`: `%s`.",
            index,
            class_regex,
            root_dir,
        )

    return None


def get_snippet(
    filename: str,
    line_number: int,
    before: int = 5,
    after: int = 5,
    line_function: Any = None,
) -> Tuple[str, str]:
    """Get code snippet for line."""
    line_number -= 1  # Index starts from 0 now.

    if line_number < 0:
        return "", ""

    content = load_file(filename)
    lines = content.splitlines()

    if line_number >= len(lines):
        return "", ""

    line_copy = lines[line_number]
    if line_function is not None and len(lines) > line_number:
        lines[line_number] = line_function(lines[line_number])

    start = max(line_number - before, 0)
    return NEW_LINE.join(lines[start : (line_number + max(after, 0) + 1)]), line_copy


def is_valid_github_url(url: str, timeout_seconds: int = 30) -> bool:
    """Given a github url, see whether it's valid."""
    prefix = "https://github.com/"
    if not url.startswith(prefix) or len(url) <= len(prefix):
        return False

    try:
        status_code = requests.head(url, timeout=timeout_seconds).status_code
    except Exception as error:
        logging.warning(
            "Unable to get Github url (%s) status code: <<<%s>>>.", url, error
        )
        status_code = -1

    msg = f"Status code for Github url is `{status_code}`: `{url}`."
    if status_code in GITHUB_VALID_CODES:
        logging.info(msg)
    else:
        logging.warning(msg)

    return status_code not in GITHUB_INVALID_CODES


def get_github_license(
    github_url,
    api_url: str = "https://api.github.com/repos/{user}/{repo}/license",
    token=None,
):
    """Get license for a Github repo, e.g. "MIT", "Apache-2.0"."""
    parts = github_url.rstrip("/").split("/")
    if len(parts) < 2:
        logging.warning("Unable to get license for `%s`: Double check URL.", github_url)
        return None
    user, repo = parts[-2], parts[-1]

    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    response = requests.get(api_url.format(user=user, repo=repo), headers=headers)

    if response.status_code in GITHUB_VALID_CODES:
        try:
            data = response.json()
            return data["license"]["spdx_id"]
        except Exception as error:
            logging.warning(
                "Unable to get license for `%s`: <<<%s>>>", github_url, str(error)
            )
            return None

    logging.warning(
        "Unable to get license for `%s`: Status code `%s`.",
        github_url,
        response.status_code,
    )
    if response.status_code in GITHUB_INVALID_CODES:
        return "License not found"

    return None


def get_git_line_changes(output: str) -> Tuple[Tuple[int, int]]:
    """Get git line changes:

    lhs (--): [start, end)
    rhs (++): [start, end)

    Example:
    @@ -10,0 +11 @@ llm_agent {
    +      temperature: 0.
    @@ -44,0 +46 @@ prompt_manager {
    +  restart_messages_len_gt: 10
    @@ -62 +64 @@ llm_parser_by_group {
    -max_iterations: 50
    +max_iterations: 60
    @@ -53,2 +53,2 @@ class GitRepo
    - ...
    - ...
    + ...
    + ...
    """
    lines = [l for l in output.splitlines() if l.startswith("@@ ")]

    line_changes = []
    for line in lines:
        match = re.search(GIT_LINE_CHANGES_PATTERN, line)
        if not match:
            continue

        lhs_s, _, lhs_delta, rhs_s, _, rhs_delta = match.groups()

        # How many lines changed:
        # - `0`: Explicit
        # - `1`: Implicit
        map_delta = {
            None: "1",
        }
        lhs_delta = map_delta.get(lhs_delta, lhs_delta)
        rhs_delta = map_delta.get(rhs_delta, rhs_delta)

        lhs_s = int(lhs_s)
        rhs_s = int(rhs_s)
        line_changes.append(
            (
                (lhs_s, lhs_s + int(lhs_delta)),
                (rhs_s, rhs_s + int(rhs_delta)),
            )
        )

    return tuple(line_changes)


class TimeItInSeconds(ContextDecorator):
    """Measure the runtime of a process."""

    def __init__(self, name: str, enabled: bool = True, logging_fn=logging.info):
        self.name = name
        self.enabled = enabled
        self.logging_fn = logging_fn

        self.start_time = None
        self.runtime = None

    def __enter__(self):
        if self.enabled:
            self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.enabled:
            return

        self.runtime = time.time() - self.start_time
        self.logging_fn("Runtime for %s: %f seconds.", self.name, self.runtime)

    @property
    def seconds(self) -> Optional[float]:
        """Get runtime."""
        return self.runtime

    @property
    def minutes(self) -> Optional[float]:
        """Get runtime."""
        return None if self.runtime is None else self.runtime / 60.0


def get_class_names(classes: Sequence[Any]) -> Dict[str, Any]:
    """Get class by name: Both `CamelCase` and `snake_case`."""
    names = {}
    for cls in set(classes):
        cls_name = cls.__name__
        for name in (cls_name, re.sub(r"(?<!^)(?=[A-Z])", "_", cls_name).lower()):
            if name in names:
                raise ValueError(f"{name} is already processed: %s.", classes)
            names[name] = cls

    return names


def create_instance(
    option: Any, candidate_classes: Sequence[Any], *args, **kwargs
) -> Any:
    """Create an instance from candidate classes.

    When option is str: To create from class constructor directly, based on its name.
    When option is a config: It's to call class static method `create_from_config`.
    """
    class_names = get_class_names(candidate_classes)

    if isinstance(option, str):
        config = None
    else:
        if not args:
            raise ValueError(
                "Please provide an name for config attribute: len(args) = 0."
            )

        config_case = args[0]
        args = args[1:]

        config = option
        # Option is the class name as well: Should be the snake case.
        option = config.WhichOneof(config_case)
    cls = class_names[option]

    if config is None:
        return cls(*args, **kwargs)

    logging.debug("[factory] Create `%s` from config: `%s`.", config_case, config)
    return cls.create_from_config(getattr(config, option), *args, **kwargs)


def _run():
    filename = "/tmp/test.txt"
    for suffix in ("", ".copy"):
        export_file(f"{filename}{suffix}", "hello,\rworld\r\nShould be shared.\n")
    logging.info(normalize_file(filename))

    run_command(["zip", "/tmp/testdata.zip", "-r", "./testdata"], shell=False)
    # run_command(["chmod", "+x", "/tmp/testdata.zip"], shell=False)

    run_command(["rm", "/tmp/TinyPng.xproj"], shell=False)


def _main():
    logging.info(run_command(["sleep 1; ls"], timeout=0.5))
    logging.info(run_command(["sleep 1; ls"], timeout=5))
    logging.info(run_command(["tree", "testdata/subdir"]))  # DO NOT USE
    logging.info(run_command(["tree testdata/subdir"]))
    logging.info(run_command(["tree ."], cwd=os.path.join(_PWD, "testdata/subdir")))

    # logging.info(run_command(["rm", "-rf", "testdata"], shell=False))
    # logging.info(run_command(["git", "checkout", "testdata"], shell=False))

    github_urls = (
        GITHUB_URL,
        GITHUB_URL + "-xyz",
        GITHUB_URL.replace("contrib", "contrib-xyz"),
    )

    for github_url in github_urls:
        logging.info(
            "`%s` => valid = `%s`", github_url, is_valid_github_url(github_url)
        )

    java_homes = (
        "/usr/lib/jvm/java-1.8.0-amazon-corretto.x86_64",
        "/usr/lib/jvm/java-1.8.0-amazon-corretto.x86_64/jre",
        "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.432.b06-1.amzn2.0.1.x86_64",
        "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.432.b06-1.amzn2.0.1.x86_64/jre",
        "/usr/lib/jvm/java-17-amazon-corretto.x86_64",
    )
    java_dir = "/home/sliuxl/github/xresloader"
    for java_home in java_homes:
        if not os.path.exists(java_home):
            continue

        logging.info(run_command(f"JAVA_HOME={java_home} mvn --version", check=False))
        logging.info(
            run_command(
                f"JAVA_HOME={java_home} mvn dependency:resolve",
                cwd=java_dir,
                check=False,
            )
        )
        logging.info(
            run_command(
                f"JAVA_HOME={java_home} mvn test -f .", cwd=java_dir, check=False
            )
        )

    """
    for github_url in github_urls:
        logging.info(
            run_command(["git", "ls-remote", github_url], shell=False, timeout=30)
        )
    """
    _run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
    _main()
