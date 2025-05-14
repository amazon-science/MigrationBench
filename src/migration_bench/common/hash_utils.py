"""Hash util functions."""

from collections import defaultdict
import hashlib
import logging
import os
import re
from typing import Tuple

from self_debug.common import git_repo, utils


POM = "pom.xml"
SUBDIR_SRC_TEST = "src/test"

UNKNOWN_COMMIT_ID = ""

JAVA_HOMES = (
    "/usr/lib/jvm/java-1.8.0-amazon-corretto.x86_64",  # Container
    "/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.432.b06-1.amzn2.0.1.x86_64",  # Local
)


def get_num_test_cases(root_dir: str, stdout: str = "") -> int:
    """Get number of test cases."""
    if not stdout and root_dir and os.path.exists(root_dir):
        for java_home in JAVA_HOMES:
            if not os.path.exists(java_home):
                continue

            stdout, success = utils.run_command(
                f"JAVA_HOME={java_home} mvn test -f .", cwd=root_dir, check=False
            )
            logging.warning(
                "Using JAVA_HOME = `%s` to run tests: success = `%s`.",
                java_home,
                success,
            )
            break

    segments = stdout.split("[INFO] Results:\n")
    if len(segments) <= 1:
        return -2

    lines = segments[-1]
    lines = lines.splitlines()
    while lines:
        line = lines[0]
        lines = lines[1:]

        if line.strip() == "[INFO]":
            continue

        match = re.search(r"^\[INFO\]\s+Tests run:\s+(\d+),\s+.*$", line)
        if match:
            return int(match.group(1))

    return -1


def get_hash(string_to_hash: str, encode: bool = True) -> str:
    """Get hash for a string."""
    if string_to_hash is None:
        string = "".encode()
    else:
        string = string_to_hash
        if encode:
            string = string.encode("utf-8")

    return hashlib.sha256(string).hexdigest()


def get_git_commit_ids(repo_obj, num: int = 0, poms=None):
    """Get git commit ids."""
    if isinstance(repo_obj, str):
        repo_obj = git_repo.GitRepo(repo_obj)

    try:
        commit_ids = repo_obj.log(
            num=num, options=["--format='%H'"] + (list(poms or []))
        )[0].splitlines()
        logging.warning(
            "First commit among # = %04d: `%s`.",
            len(commit_ids),
            commit_ids[0] if commit_ids else None,
        )
    except Exception as error:
        logging.exception(
            "Unable to get commit ids for repo `%s`: <<<%s>>>", repo_obj.root_dir, error
        )
        commit_ids = []

    # Commit ids are quoted `'$COMMIT_ID'`.
    commit_ids = [c[1:-1] for c in commit_ids if c]

    return tuple(commit_ids)


def _hash_files(files) -> Tuple[str, int]:
    """Hash files."""
    hashes = []
    loc = 0
    for file in files:
        hashes.append(get_hash(utils.load_file(file, mode="rb"), encode=False))
        loc += len((utils.load_file(file, fix=utils.FIX_UTF8) or "").splitlines())

    return "\n".join(hashes), loc


def get_repo_hash(
    root_dir: str,
    hash_tree: bool = True,
    hash_source: bool = True,
    hash_pom: bool = True,
) -> str:
    """Get repo hash based on (tree strcuture, source file hash, pom.xml content)."""
    root_dir = os.path.abspath(root_dir)

    inputs = []

    metrics = defaultdict(int)
    exist = os.path.exists(root_dir)

    # All output will be hashed, therefore we need to use path relative to `root_dir`.
    loc = 0
    if exist:
        if hash_tree:
            inputs.append(utils.run_command(["tree ."], cwd=root_dir)[0])

        if hash_source:
            src_files = utils.find_files(root_dir, r"\*.java")
            logging.info("# java files: %d.", len(src_files))

            # Hashes only, without filenames
            src_result = _hash_files(src_files)
            inputs.append(src_result[0])
            loc += src_result[-1]

            metrics[f"repo-num-files-java__EQ__{len(src_files):04d}"] += 1
            # *Test.java, *Tests.java
            test_files = [
                1
                for f in src_files
                if f.endswith("Test.java") or f.endswith("Tests.java")
            ]
            metrics[
                f"repo-num-files-root-any-test-java__EQ__{len(test_files):04d}"
            ] += 1

            # src/test/**/*.java
            src_test_files = [
                1
                for f in src_files
                if f.endswith(".java")
                and f.startswith(os.path.join(root_dir, f"{SUBDIR_SRC_TEST}/"))
            ]
            metrics[
                f"repo-num-files-src-test-any-java__EQ__{len(src_test_files):04d}"
            ] += 1

        if hash_pom:
            # Hashes with filenames
            pom_files = utils.find_files(root_dir, POM)
            logging.info("# %s files: %d.", POM, len(pom_files))
            for pom in pom_files:
                pom_rel = os.path.relpath(pom, root_dir)
                inputs.append(pom_rel)
                logging.debug("Hashing pom file: `%s`.", pom_rel)

                inputs.append((utils.load_file(pom, fix=utils.FIX_UTF8) or "").strip())

            metrics[f"repo-num-files-pom-xml__EQ__{len(pom_files):04d}"] += 1

    src_test_exist = os.path.exists(os.path.join(root_dir, SUBDIR_SRC_TEST))
    metrics[f"repo-root-dir-exists__EQ__{exist}"] += 1
    metrics[f"repo-root-src-test-dir-exists__EQ__{src_test_exist}"] += 1
    metrics[f"repo-num-loc__EQ__{loc:06d}"] += 1

    num_tests = get_num_test_cases(root_dir)
    metrics[f"repo-num-test-cases__EQ__{num_tests:04d}"] += 1

    result = get_hash("\n".join(inputs))
    logging.warning("Hash = `%s` (len = %d): `%s`.", result, len(inputs), root_dir)

    return result, metrics


def get_repo_commit_info(
    repo_obj: str, commits=None, first_n: int = 2, last_n: int = 1
) -> Tuple[Tuple[str]]:
    """Get repo commit_ids, given a root_dir or commit ids."""
    if commits is None:
        commits = get_git_commit_ids(repo_obj)
    commits = list(commits)

    if first_n < 1 or last_n < 1:
        raise ValueError(f"Invalid #commits: ({first_n}, {last_n}).")

    first_ids = commits[:first_n]
    if len(first_ids) < first_n:
        first_ids += [UNKNOWN_COMMIT_ID] * (first_n - len(first_ids))

    last_ids = commits[-last_n:]
    if len(last_ids) < last_n:
        last_ids = [UNKNOWN_COMMIT_ID] * (last_n - len(last_ids)) + last_ids

    commit_log = repo_obj.log(num=1, options=["--format='%ci'"])
    if commit_log[-1]:
        commit_time = commit_log[0].splitlines()[0][1:-1]
    else:
        commit_time = ""

    return tuple(first_ids), tuple(last_ids), commit_time


def get_repo_snapshot_info(repo_obj, **kwargs):
    """Get repo snapshot info."""
    first_n, last_n, last_commit_time = get_repo_commit_info(repo_obj, **kwargs)
    all_hash, metrics = get_repo_hash(repo_obj.root_dir)

    # Commit IDs
    for index, commit in enumerate(first_n):
        metrics[f"repo_commit_first_{index:02d}__EQ__{commit}"] += 1
    for index, commit in enumerate(last_n[::-1]):
        metrics[f"repo_commit_last_{index:02d}__EQ__{commit}"] += 1

    # Snapshot: Update time and hash
    metrics[f"repo_snapshot_update_time__EQ__{last_commit_time}"] += 1
    metrics[f"repo_snapshot_hash__EQ__{all_hash}"] += 1

    return {f"RepoSnapshot::{key}": value for key, value in metrics.items()}


def _run():
    logging.info(
        "#test cases = `%d`.", get_num_test_cases("/home/sliuxl/github/xresloader")
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    _run()
