"""Util functions for github."""

import logging
import os
import random
import shutil
import string
import sys
import time
from typing import Optional, Union

import git

from self_debug.datasets.dataset import GithubData
from self_debug.common import utils


# Branch names.
GITHUB_MAIN_BRANCH = "mainline--self-debugging-plus"
GITHUB_PORTED_BRANCH = "ported"

GITHUB_URL_SUFFIX = ".git"

# Sample repo.
GITHUB_URL = "https://github.com/klee-contrib/kinetix"
GITHUB_URL = "https://github.com/minatisleeping/Spring-security-login-system"
GITHUB_COMMIT_ID = "4068be9"

GIT_CLONE_MAX_ATTEMPTS = 10
GIT_CLONE_SLEEP_SECONDS = 5


def get_random_string(length: int) -> str:
    """Get a random string from all lowercase letters and numbers."""
    pool = string.ascii_lowercase + string.digits
    return "".join(random.choice(pool) for i in range(length))


"""
[0/10] Unable to clone repo `https://github.com/minatisleeping/Spring-security-login-system.git`: `Cmd('git') failed due to: exit code(128)
  cmdline: git clone -v -- https://github.com/minatisleeping/Spring-security-login-system.git /tmp/ported/minatisleeping__Spring-security-login-system
  stderr: 'Cloning into '/tmp/ported/minatisleeping__Spring-security-login-system'...
fatal: could not read Username for 'https://github.com': No such device or address
'`.
Traceback (most recent call last):
  File "/self-dbg/src/self_debug/common/github.py", line 66, in _clone_repo
    local_repo = git.Repo.clone_from(github_url, work_dir)
  File "/usr/local/lib/python3.9/site-packages/git/repo/base.py", line 1525, in clone_from
    return cls._clone(
  File "/usr/local/lib/python3.9/site-packages/git/repo/base.py", line 1396, in _clone
    finalize_process(proc, stderr=stderr)
  File "/usr/local/lib/python3.9/site-packages/git/util.py", line 504, in finalize_process
    proc.wait(**kwargs)
  File "/usr/local/lib/python3.9/site-packages/git/cmd.py", line 834, in wait
    raise GitCommandError(remove_password_if_present(self.args), status, errstr)
git.exc.GitCommandError: Cmd('git') failed due to: exit code(128)
  cmdline: git clone -v -- https://github.com/minatisleeping/Spring-security-login-system.git /tmp/ported/minatisleeping__Spring-security-login-system
  stderr: 'Cloning into '/tmp/ported/minatisleeping__Spring-security-login-system'...
fatal: could not read Username for 'https://github.com': No such device or address
"""


def _clone_repo(
    github_url: str,
    commit_hash: Optional[str] = None,
    work_dir: Optional[str] = None,
    branch_name: str = GITHUB_PORTED_BRANCH,
    dry_run: bool = False,
    random_len: int = 0,
) -> Optional[str]:
    """Clone repo at given commit id."""
    default_dir = os.path.basename(github_url).replace(GITHUB_URL_SUFFIX, "")
    if work_dir:
        work_dir = work_dir.format(
            repo=default_dir,
            commit_id=commit_hash or "",
            random=get_random_string(random_len) if random_len else "",
        )
    else:
        work_dir = os.path.join(os.path.abspath("./"), default_dir)

    # if not github_url.endswith(GITHUB_URL_SUFFIX):
    #     github_url += GITHUB_URL_SUFFIX

    logging.info("Clone github repo `%s`: `%s` ...", github_url, work_dir)
    if dry_run:
        return work_dir

    for index in range(GIT_CLONE_MAX_ATTEMPTS):
        try:
            local_repo = git.Repo.clone_from(github_url, work_dir)
            logging.info(
                "  Checkout branch (%s): `%s` ...", GITHUB_MAIN_BRANCH, github_url
            )
            local_repo.git.checkout("-b", GITHUB_MAIN_BRANCH)

            if commit_hash:
                logging.info(
                    "  Checkout commit (%s): `%s` ...", commit_hash, github_url
                )
                local_repo.git.checkout(commit_hash)
            if branch_name:
                logging.info(
                    "  Checkout branch (%s): `%s` ...", branch_name, github_url
                )
                local_repo.git.checkout("-b", branch_name)

            logging.info("Clone github repo `%s`: Done.", github_url)
            return work_dir
        except Exception as error:
            logging.exception(
                "[%d/%d] Unable to clone repo `%s`: `%s`.",
                index,
                GIT_CLONE_MAX_ATTEMPTS,
                github_url,
                error,
            )

            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)

            if str(error).strip().endswith("No such device or address"):
                break

            if index < GIT_CLONE_MAX_ATTEMPTS - 1:
                time.sleep(GIT_CLONE_SLEEP_SECONDS)

    return None


def maybe_clone_repo(github_data: Union[str, GithubData], **kwargs) -> str:
    """Clone repo at given commit id."""
    if not isinstance(github_data, GithubData):
        return github_data

    # TODO(sliuxl): Check out all commit ids, now using the first one.
    commit_id = None
    if github_data.version_and_commit_ids:
        commit_id = github_data.version_and_commit_ids[0].get("commit_id")

    # Early stop for invalid Github URLs.
    if not utils.is_valid_github_url(github_data.github_url):
        return None

    work_dir = kwargs.pop("work_dir", "/tmp/ported/{repo}")
    return _clone_repo(github_data.github_url, commit_id, work_dir, **kwargs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    logging.info(
        "Repo is at: `%s`.",
        maybe_clone_repo(
            GithubData(
                github_url=GITHUB_URL,
                version_and_commit_ids=[
                    {
                        "version": "",
                        "commit_id": GITHUB_COMMIT_ID,
                    }
                ],
            ),
            work_dir="/tmp/ported/{repo}" if len(sys.argv) < 2 else sys.argv[1],
        ),
    )
