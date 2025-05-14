"""Parse java repo test files."""

import logging
import os
import sys

from migration_bench.common import git_repo, utils
from migration_bench.lang.java.eval import parse_file

TEST_FILES = r"\*.java"
TEST_SUB_DIR = "src/test"

LHS_BRANCH = "ported"
RHS_BRANCH = None


def get_repo_test_files(
    root_dir: str,
    branch: str = None,
    test_sub_dir: str = TEST_SUB_DIR,
    test_files: str = TEST_FILES,
):
    """Get test files for their classes and methods."""
    test_files = utils.find_files(os.path.join(root_dir, test_sub_dir), test_files)

    repo = git_repo.GitRepo(root_dir)
    if branch is not None:
        repo.checkout(branch)

        repo.clean()
        repo.restore()

    logging.info(repo.branch())
    logging.info(repo.status())

    repo_tests = {}
    for test_file in test_files:
        # Without line no by default
        repo_tests[test_file] = parse_file.get_classes_and_methods(test_file)

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

    # NOTE: Run rhs first, as the branch name might be None.
    rhs_tests = get_repo_test_files(root_dir, rhs_branch, **kwargs)

    lhs_tests = get_repo_test_files(root_dir, lhs_branch, **kwargs)

    if len(lhs_tests) != len(rhs_tests):
        logging.warning(
            "File count mismatch: %05d => %05d.", len(lhs_tests), len(rhs_tests)
        )
        return False, max(len(lhs_tests), len(rhs_tests)), None

    files = sorted(lhs_tests.keys())
    if files != sorted(rhs_tests.keys()):
        logging.warning("File mismatch: `%s` => `%s`.", files, sorted(rhs_tests.keys()))
        return False, len(lhs_tests)

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
