"""Unit tests for github.py."""

import logging
import unittest

from parameterized import parameterized

from self_debug.datasets.dataset import GithubData
from self_debug.common import github, utils


GITHUB_URL = "https://github.com/klee-contrib/kinetix"


_REPO_00 = "/tmp/repo"
_REPO_01 = "s3:/$BUCKET/$PATH"

_REPO_02 = GithubData(
    github_url=GITHUB_URL,
    version_and_commit_ids=[
        {
            "version": "",
            "commit_id": github.GITHUB_COMMIT_ID,
        },
        {},
    ],
)

INVALID_GITHUB_URL = "https://github.com/URL-does-not-exist--should-raise-an-error"
_REPO_03 = GithubData(github_url=INVALID_GITHUB_URL)


class TestGithub(unittest.TestCase):
    """Unit tests for github.py."""

    @parameterized.expand(
        (
            # str: non-s3 & s3.
            (_REPO_00, False, {}, _REPO_00),
            (_REPO_00, True, {}, _REPO_00),
            (_REPO_01, False, {}, _REPO_01),
            (_REPO_01, True, {}, _REPO_01),
            # Github.
            (
                _REPO_02,
                True,
                {},
                "/tmp/ported/kinetix",
            ),
            (
                _REPO_02,
                True,
                {
                    "work_dir": "/tmp/ported/{repo}--{commit_id}",
                },
                "/tmp/ported/kinetix--4068be9",
            ),
            (
                _REPO_02,
                True,
                {
                    "work_dir": "/tmp/ported/{repo}--{commit_id}--random={random}",
                    "random_len": 8,
                },
                "/tmp/ported/kinetix--4068be9--random=",
            ),
            (
                _REPO_02,
                True,
                {
                    "work_dir": "/tmp/ported/{repo}--{commit_id}--random={random}",
                    "random_len": 20,
                },
                "/tmp/ported/kinetix--4068be9--random=",
            ),
            # Unable to checkout.
            (
                _REPO_03,
                True,
                {},
                None,  # "/tmp/ported/URL-does-not-exist--should-raise-an-error",
            ),
            (
                _REPO_03,
                False,
                {},
                None,
            ),
        )
    )
    def test_maybe_clone_repo(self, repo, dry_run, kwargs, expected_work_dir):
        """Unit tests run_command."""
        work_dir = github.maybe_clone_repo(repo, dry_run=dry_run, **kwargs)

        random_len = kwargs.get("random_len", 0)
        if random_len:
            logging.info("Random dir (len = %d): `%s`.", random_len, work_dir)
            work_dir = work_dir[:-random_len]
        self.assertEqual(work_dir, expected_work_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    unittest.main()
