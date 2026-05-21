"""Common git operations with a repo."""

import logging
import os
from typing import Sequence, Tuple

from migration_bench.common import utils


ALL = "."

GIT_NA = "git: N.A. for the dir"

GIT_STATUS_CLEAN = "nothing to commit, working tree clean"

GIT_STATUS_STAGED = "Changes to be committed:"
GIT_STATUS_UNSTAGED = "Changes not staged for commit:"
GIT_STATUS_UNTRACKED = "Untracked files:"

GIT_STATUS_REGEX = (
    GIT_STATUS_CLEAN,
    GIT_STATUS_STAGED,
    GIT_STATUS_UNSTAGED,
    GIT_STATUS_UNTRACKED,
)

POM = "pom.xml"


class GitRepo:
    """A class to perform git operations on a repo.

    - Read only ops (branch, diff, log, status, etc) return raw output.
    - Write ops (checkout, new_branch, add, commit) return bool status indicating success or not.
    """

    def __init__(self, root_dir: str, ground_truth=None):
        """A git repo instance with the given root dir, also the work dir."""
        logging.debug("[ctor] Git repo: path = %s.", root_dir)
        self.root_dir = root_dir
        self.ground_truth = ground_truth

    def _git_command(self, command: Sequence[str], **kwargs):
        """Run git command."""
        shell = kwargs.pop("shell", False)

        return utils.run_command(
            ["git"] + command, cwd=self.root_dir, shell=shell, **kwargs
        )

    def _read_cmd(self, *args, **kwargs):
        """Run git read only command."""
        return self._git_command(*args, **kwargs)

    def _write_cmd(self, *args, **kwargs):
        """Run git write command."""
        result = self._git_command(*args, **kwargs)
        logging.debug("Write cmd: `%s`", result)
        return result[-1]

    def initialize(self) -> bool:
        """Initialize a new git repo at the given path."""
        return self._write_cmd(["init"])

    ### READ ONLY ops.
    def branch(self) -> Tuple[str, bool]:
        """Get branches.
        ec2-user@ip-172-31-67-47.ec2.internal 20:29 /home/sliuxl/self-dbg/src/migration_bench/common $ git branch
          amlc
        * csharp

        ec2-user@ip-172-31-67-47.ec2.internal 20:28 /tmp $ git branch
        fatal: detected dubious ownership in repository at '/tmp'
        To add an exception for this directory, call:

                git config --global --add safe.directory /tmp
        """

        return self._read_cmd(["branch"])

    def diff(self, files: str = ALL, **kwargs) -> Tuple[str, bool]:
        """Get diff for the git repo."""

        def _diff(use_kwargs):
            return self._read_cmd(
                ["diff"] + ([files] if isinstance(files, str) else files), **use_kwargs
            )

        stdout = "stdout"
        if stdout in kwargs and isinstance(kwargs[stdout], str):
            with open(kwargs[stdout], "w") as ofile:  # pylint: disable=unspecified-encoding
                kwargs.update(
                    {
                        stdout: ofile,
                    }
                )
                return _diff(kwargs)

        return _diff(kwargs)

    def log(self, num: int = 3, options=None):
        """Display the commit log for the git repo."""
        return self._read_cmd(["log"] + ([f"-{num}"] if num else []) + (options or []))

    def status(self, *args) -> Tuple[str, bool]:
        """Display the current status of the git repo."""
        return self._read_cmd(["status"] + list(args))

    def get_github_url(self, *args) -> Tuple[str, bool]:
        """Get github url: git remote get-url origin."""
        return self._read_cmd(["remote", "get-url", "origin"] + list(args))

    def show_staged(self, filename: str, option="-U0") -> Tuple[Tuple[int, int]]:
        """Show file in the staging area."""
        output, _ = self._read_cmd(
            ["diff", "--staged"] + option.split(" ") + [filename]
        )
        return utils.get_git_line_changes(output)

    def show_untracked(self) -> Tuple[str]:
        """Show untracked files: `git status --porcelain | grep '^??'`."""
        question = "??"

        git_status = self.status("--porcelain")
        lines = [l.strip() for l in git_status[0].splitlines()]
        lines = [
            l.replace(question + " ", "") for l in lines if l and l.startswith(question)
        ]
        lines = [os.path.join(self.root_dir, l) for l in lines]

        return tuple(lines)

    ### WRITE ops.
    def checkout(self, branch: str, option: str = "", force: bool = True) -> bool:
        """Checkout to a given branch."""
        force_option = ["-f"] if force else []
        result = self._write_cmd(
            ["checkout"] + force_option + ([option] if option else []) + [branch]
        )

        if force:
            self.clean()
            self.restore()

        return result

    def clean(self, option: str = "-df") -> bool:
        """Clean up the repo."""
        return self._write_cmd(["clean"] + ([option] if option else []))

    def delete_branch(self, branch: str, option="-d") -> bool:
        """Create a new branch from a given one."""
        return self._write_cmd(["branch", option, branch])

    def new_branch(
        self, branch: str, source_branch: str = "", checkout: bool = True
    ) -> bool:
        """Create a new branch from source."""
        # Target is the same to source.
        if branch == source_branch:
            logging.warning("Creating a branch from itself (%s): Skip.", branch)
            return False

        # Source branch does not exist.
        if source_branch and not self.checkout(source_branch):
            return False

        if not self._write_cmd(["branch", "-f", branch]):
            return False

        if checkout:
            return self.checkout(branch)

        return True

    def rename_branch(self, branch: str, source_branch: str) -> bool:
        """Rename a branch from a given one."""
        if self.new_branch(branch, source_branch, checkout=True):
            return self.delete_branch(source_branch)

        return False

    def apply(self, diff_filename: str) -> bool:
        """Apply a diff file."""
        return self._write_cmd(["apply", diff_filename])

    def add_all(self, *args) -> bool:
        """Add files to the git staging area."""
        return self._write_cmd(["add"] + list(args) + [ALL])

    def commit(self, commit_message: str) -> bool:
        """Commit staged changes with the specified commit message."""
        return self._write_cmd(["commit", "-m", commit_message])

    def commit_all(self, commit_message: str, *args) -> bool:
        """Commit all changes with the specified commit message."""
        success = True

        try:
            success = self.add_all(*args) and success
            success = self.commit(commit_message) and success
        except Exception as error:
            logging.warning("Unable to commit all: %s.", str(error))
            return False

        return success

    def restore(self, restore_staged=True, restore_unstaged=True) -> bool:
        """Restore to previous state.

        If restore_staged is True, staged changes will be restored.
        If restore_unstaged is True, unstaged changes will be restored.
        """
        if not any([restore_staged, restore_unstaged]):
            raise ValueError(
                "At least one of 'restore_staged' or 'restore_unstaged' must be True."
            )

        if restore_staged:
            self._write_cmd(["restore", "--staged", ALL])

        return self._write_cmd(["restore", ALL])


def main():
    """Main."""
    url = GitRepo(".").get_github_url()
    logging.info("URL for .: `%s`.", url)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    main()
