"""Final eval."""

import logging
import os
import sys
import tempfile

import git

from migration_bench.common import (
    eval_utils,
    git_repo,
    hash_utils,
    hf_utils,
    maven_utils,
    utils,
)
from migration_bench.lang.java.eval import parse_repo


# When running a batch job, we need the github url and git diff file or its content.
KEY_GITHUB_URL = "github_url"
# - Only one is needed
KEY_GIT_DIFF_CONTENT = "git_diff"
KEY_GIT_DIFF_FILE = "git_diff_file"


_JAVA_FULL = hf_utils.load_hf_dataset(
    columns=(
        hf_utils.COLUMN_REPO,
        hf_utils.COLUMN_COMMIT,
        hf_utils.COLUMN_NUM_TEST_CASES,
    )
)

DATASET_COMMIT_IDS = {
    os.path.join(hf_utils.GITHUB_URL_PREFIX, repo_name): commit_id
    for repo_name, commit_id in zip(
        _JAVA_FULL[hf_utils.COLUMN_REPO], _JAVA_FULL[hf_utils.COLUMN_COMMIT]
    )
}

DATASET_NUM_TESTS = {
    os.path.join(hf_utils.GITHUB_URL_PREFIX, repo_name): num_test_cases
    for repo_name, num_test_cases in zip(
        _JAVA_FULL[hf_utils.COLUMN_REPO], _JAVA_FULL[hf_utils.COLUMN_NUM_TEST_CASES]
    )
}


LHS_BRANCH = "SELF_DEBUG__FINAL_EVAL"


def alias(url: str) -> str:
    """Alias for github URL."""
    if url.endswith(".git"):
        return url[:-4]

    return f"{url}.git"


def local_final_eval(
    github_url: str,
    root_dir: str,
    git_diff_file: str,
    commit_id: str,
    # Which cmd to run
    maven_command: str = maven_utils.MVN_CLEAN_VERIFY,
    # Which set of evals to run
    eval_build_success: bool = True,
    require_compiled_java_major_version: int = 61,
    require_maximal_migration: bool = True,
    eval_num_tests: bool = True,
    eval_list_tests: bool = True,
) -> bool:
    """Run final eval given a local dir (To be modified, not read only) and git diff file.

    eval_build_success: Eval `mvn clean verify`
    eval_num_tests: Eval `mvn test -f .` and extract #tests
       - In case `eval_list_tests` are disabled e.g. some java modules are commented in pom.xml
    eval_list_tests: Static eval for the list of tests
    """
    repo = git_repo.GitRepo(root_dir)

    # 1. LHS: Before migration
    if not repo.new_branch(LHS_BRANCH):
        logging.warning(
            "Unable to checkout branch `%s`: From commit id `%s`.",
            LHS_BRANCH,
            commit_id,
        )

    # 2. Verify commit id
    commit_ids = repo.log(num=1, options=["--format='%H'"])[0].splitlines()
    if commit_ids != [f"'{commit_id}'"]:
        logging.warning(
            "Commit id mismatch for `%s`: `%s` vs `%s`.",
            root_dir,
            commit_ids,
            commit_id,
        )
        return False

    # 3. Apply diff
    if git_diff_file:
        if not os.path.exists(git_diff_file):
            logging.warning("Unable to find file: `%s`.", git_diff_file)
            return False

        repo.apply(git_diff_file)

    # 4. RHS: After migration
    #    - Build success
    #      1. mvn clean verify
    #      2. Compiled java version
    #      3. [optional] Maximal migration
    build_success = (
        eval_build_success
        and (
            maven_utils.do_run_maven_command(
                maven_command.format(root_dir=root_dir), check=False
            ).return_code
            == 0
        )
        and (
            (require_compiled_java_major_version is None)
            or (
                utils.get_compiled_java_major_versions(root_dir)
                == {require_compiled_java_major_version}
            )
        )
        and ((not require_maximal_migration) or eval_utils.check_version(root_dir))
    )

    if eval_num_tests:
        require_num_tests = DATASET_NUM_TESTS.get(
            github_url, DATASET_NUM_TESTS.get(alias(github_url), -10)
        )
        if require_num_tests < 0:
            logging.warning(
                "Required #tests = `%d`: `%s`.", require_num_tests, github_url
            )

        mvn_tests = maven_utils.do_run_maven_command(
            maven_utils.MVN_NUM_TESTS.format(root_dir=root_dir), check=False
        )
        num_tests = hash_utils.get_num_test_cases(root_dir, mvn_tests.stdout)
    else:
        require_num_tests = -10
        num_tests = None

    logging.warning(
        "Repo (Build success, #tests) = (%s, %s): `%s`.",
        build_success,
        num_tests,
        root_dir,
    )

    return (
        # Build success
        build_success
        # Num of tests
        and (
            (not eval_num_tests)
            or (require_num_tests < 0)
            or (num_tests is not None and num_tests >= require_num_tests)
        )
        # Tests: Will **revert** all changes from the git diff file
        and (
            (not eval_list_tests)
            or parse_repo.same_repo_test_files(root_dir, lhs_branch=LHS_BRANCH)[-1]
        )
    )


def run_eval(
    github_url: str, git_diff_file: str, commit_id: str = None, **kwargs
) -> bool:
    """Run final eval, given github url and git diff file."""
    if commit_id is None:
        commit_id = DATASET_COMMIT_IDS.get(
            github_url, DATASET_COMMIT_IDS.get(alias(github_url))
        )

    if commit_id is None:
        logging.warning("Invalid commit id (None) for repo: `%s`.", github_url)
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            local_repo = git.Repo.clone_from(github_url, temp_dir)
        except Exception as error:
            logging.warning("Unable to clone `%s`: `%s`.", github_url, error)
            return False

        try:
            local_repo.git.checkout(commit_id)
        except Exception as error:
            logging.warning(
                "Unable to checkout id for `%s@%s`: `%s`.", github_url, commit_id, error
            )

        try:
            success = local_final_eval(
                github_url, temp_dir, git_diff_file, commit_id, **kwargs
            )
        except Exception as error:
            logging.warning(
                "Unable to run local_final_eval for `%s@%s`: `%s`.",
                github_url,
                commit_id,
                error,
            )
            success = False

        logging.warning(
            "Final eval for `%s` (%s): Success = %s.",
            github_url,
            git_diff_file,
            success,
        )

        return success


def run_batch_eval(predictions, **kwargs) -> int:
    """Run batch eval.

    `predictions` could be:
    1. A list of `dict` with keys:
       - `github_url`: Github url for the repo
       - `git_diff`: Git diff content
       - `git_diff_file`: A file containing `git_diff`
    1. A json file containing a list as #1

    """
    if isinstance(predictions, str):
        predictions = utils.load_json(predictions) or []

    count = 0
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = os.path.join(temp_dir, "predictions.json")

        for pred in predictions:
            github_url = pred.get(KEY_GITHUB_URL)

            git_diff_file = pred.get(KEY_GIT_DIFF_FILE)
            if git_diff_file is None:
                git_diff = pred.get(KEY_GIT_DIFF_CONTENT)
                if git_diff is not None:
                    utils.export_file(temp_file, git_diff)
                    git_diff_file = temp_file

            count += run_eval(github_url, git_diff_file, **kwargs)

    logging.info(
        "[batch] Final eval result: Success = %d out of %d.", count, len(predictions)
    )
    return count


def _run(github_url: str, git_diff_file: str = None):
    predictions = [
        {
            KEY_GITHUB_URL: github_url,
            KEY_GIT_DIFF_FILE: git_diff_file,
        },
    ]

    logging.info("Final eval: success = `%s`.", run_batch_eval(predictions))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    _run(*(sys.argv[1:]))
