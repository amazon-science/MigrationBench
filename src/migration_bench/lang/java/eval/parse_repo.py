"""Parse java repo test files."""

import fnmatch
import logging
import os
import subprocess
import sys
from typing import Dict, Iterator, Optional, Sequence

from migration_bench.common import utils
from migration_bench.lang.java.eval import parse_file

TEST_FILES = "*.java"
TEST_SUB_DIR = "src/test"

LHS_BRANCH = "ported"
RHS_BRANCH = None


def _is_test_file(path: str, test_sub_dir: str, test_files: str) -> bool:
    """Whether a repo-relative path is a test file, in the root or any module."""
    return f"/{test_sub_dir}/" in f"/{path}" and fnmatch.fnmatch(
        os.path.basename(path), test_files
    )


def _working_tree_files(root_dir: str) -> Iterator[str]:
    """Repo-relative paths of all files in the working tree, excluding `.git`."""
    for dir_path, dir_names, file_names in os.walk(root_dir):
        dir_names[:] = [d for d in dir_names if d != ".git"]
        for file_name in file_names:
            yield os.path.relpath(os.path.join(dir_path, file_name), root_dir)


def _git_output(root_dir: str, command: Sequence[str]) -> Optional[bytes]:
    """Run a read-only git command, returning stdout or None on failure."""
    try:
        # Ignore `git replace` refs so a branch always resolves to its own objects.
        result = subprocess.run(
            ["git", "--no-replace-objects"] + list(command),
            cwd=root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as error:
        logging.warning("Unable to run git %s in `%s`: `%s`.", command, root_dir, error)
        return None

    if result.returncode != 0:
        logging.warning(
            "Unable to run git %s in `%s`: `%s`.",
            command,
            root_dir,
            result.stderr.decode(errors="ignore").strip(),
        )
        return None

    return result.stdout


def get_repo_test_files(
    root_dir: str,
    branch: str = None,
    test_sub_dir: str = TEST_SUB_DIR,
    test_files: str = TEST_FILES,
) -> Optional[Dict[str, tuple]]:
    """Get test files for their classes and methods.

    With `branch=None`, read the working tree. Otherwise, list and read the files
    committed in `branch` from git objects, without checking it out, so files
    deleted from the working tree are still found. Returns None if `branch`
    cannot be read.
    """
    if branch is None:
        return {
            os.path.join(root_dir, path): parse_file.get_classes_and_methods(
                os.path.join(root_dir, path)
            )
            for path in sorted(_working_tree_files(root_dir))
            if _is_test_file(path, test_sub_dir, test_files)
        }

    listing = _git_output(root_dir, ["ls-tree", "-r", "-z", "--name-only", branch])
    if listing is None:
        return None

    repo_tests = {}
    for path in sorted(listing.decode(errors="ignore").split("\0")):
        if not path or not _is_test_file(path, test_sub_dir, test_files):
            continue

        content = _git_output(root_dir, ["show", f"{branch}:{path}"])
        if content is None:
            return None

        repo_tests[os.path.join(root_dir, path)] = parse_file.get_classes_and_methods(
            path, content=content.decode(errors="ignore")
        )

    return repo_tests


def same_repo_test_files(
    root_dir: str,
    lhs_branch: str = LHS_BRANCH,
    rhs_branch: str = RHS_BRANCH,
    early_stop: bool = True,
    **kwargs,
):
    """Whether it's the same test files based on classes and methods."""
    if lhs_branch is None and rhs_branch is not None:
        lhs_branch, rhs_branch = rhs_branch, lhs_branch

    if lhs_branch == rhs_branch:
        logging.warning(
            "Make sure you use different branch names for lhs vs rhs: `%s` vs `%s`.",
            lhs_branch,
            rhs_branch,
        )
        if early_stop:
            return True, None, None

    rhs_tests = get_repo_test_files(root_dir, rhs_branch, **kwargs)
    lhs_tests = get_repo_test_files(root_dir, lhs_branch, **kwargs)

    if lhs_tests is None or rhs_tests is None:
        logging.warning(
            "Unable to read test files: `%s` (%s) vs `%s` (%s).",
            lhs_branch,
            lhs_tests is not None,
            rhs_branch,
            rhs_tests is not None,
        )
        return False, None, False

    if len(lhs_tests) != len(rhs_tests):
        logging.warning(
            "File count mismatch: %05d => %05d.", len(lhs_tests), len(rhs_tests)
        )
        return False, max(len(lhs_tests), len(rhs_tests)), None

    files = sorted(lhs_tests.keys())
    if files != sorted(rhs_tests.keys()):
        logging.warning("File mismatch: `%s` => `%s`.", files, sorted(rhs_tests.keys()))
        return False, len(lhs_tests), None

    issues = []
    test_issues = []
    for index, file in enumerate(files):
        lhs = lhs_tests[file]
        rhs = rhs_tests[file]
        if parse_file.same_classes_and_methods(lhs, rhs):
            continue

        test_is_ok = parse_file.same_classes_and_methods(
            lhs, rhs, has_test_annotation=True
        )
        logging.info(
            (
                "[test_is_ok=%d] Test mismatch (%03d/%03d out of %03d) for `%s`:\n"
                "    [LHS] <<<%s>>> vs\n"
                "    [RHS] <<<%s>>>"
            ),
            int(test_is_ok),
            len(issues),
            index,
            len(files),
            file,
            lhs,
            rhs,
        )
        issues.append(file)

        if not test_is_ok:
            test_issues.append(file)

    logging.warning(
        "Test mismatch for files (len = %03d/%03d): `%s`\n  test files len = %d: `%s`.",
        len(issues),
        len(files),
        issues,
        len(test_issues),
        test_issues,
    )

    return not bool(issues), len(files), not bool(test_issues)


def main(repos):
    """Main."""
    if len(repos) == 1 and not os.path.exists(os.path.join(repos[0], ".git")):
        home_dir = repos[0]
        repos = [os.path.join(home_dir, d) for d in os.listdir(home_dir)]
        repos = [d for d in repos if os.path.isdir(d)]

        logging.info("Found `%d` repos  in `%s`.", len(repos), home_dir)

    count = 0
    count_test_files = 0
    for root_dir in repos:
        cnt, _, cnt_test_files = same_repo_test_files(root_dir)
        count += cnt
        count_test_files += cnt_test_files

    logging.info(
        "Same tests for (%03d, %03d@Test) out of %03d repos.",
        count,
        count_test_files,
        len(repos),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    main(sys.argv[1:])
