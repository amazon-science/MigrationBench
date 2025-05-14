"""Common git operations with a repo."""

from collections import defaultdict
import logging
import os
from typing import Dict, Sequence, Tuple

from self_debug.metrics import utils as metric_utils
from self_debug.common import file_utils, hash_utils, utils


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

        self._metrics = defaultdict(int)

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
        ec2-user@ip-172-31-67-47.ec2.internal 20:29 /home/sliuxl/self-dbg/src/self_debug/common $ git branch
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
        """Display the current status of the git repo.

        ### Sample 0: Clean
        ec2-user@ip-172-31-67-47.ec2.internal 19:16 /home/sliuxl/github/self-dbg $ git status
        On branch mainline
        Your branch is up to date with 'origin/mainline'.

        nothing to commit, working tree clean

        ### Sample 1: Not clean
        ec2-user@ip-172-31-67-47.ec2.internal 19:15 /home/sliuxl/self-dbg/src/self_debug/common $ git status
        On branch csharp
        Changes to be committed:
          (use "git restore --staged <file>..." to unstage)
                modified:   git_repo.py

        Changes not staged for commit:
          (use "git add <file>..." to update what will be committed)
          (use "git restore <file>..." to discard changes in working directory)
                modified:   ../configs/csharp_config.pbtxt

        Untracked files:
          ...

        ### Sample 2: No a git dir
        ec2-user@ip-172-31-67-47.ec2.internal 20:28 /tmp $ git status
        fatal: detected dubious ownership in repository at '/tmp'
        To add an exception for this directory, call:

                git config --global --add safe.directory /tmp
        """
        return self._read_cmd(["status"] + list(args))

    def get_github_url(self, *args) -> Tuple[str, bool]:
        """Get github url: git remote get-url origin."""
        return self._read_cmd(["remote", "get-url", "origin"] + list(args))

    def show_staged(self, filename: str, option="-U0") -> Tuple[Tuple[int, int]]:
        """Show file in the staging area.

        /home/sliuxl/self-dbg/src/self_debug/common $ git diff --staged -U0 ../configs/csharp_config.pbtxt
        diff --git a/src/configs/csharp_config.pbtxt b/src/configs/csharp_config.pbtxt
        index 3853bc1..327a02e 100644
        --- a/src/configs/csharp_config.pbtxt
        +++ b/src/configs/csharp_config.pbtxt
        @@ -10,0 +11 @@ llm_agent {
        +      temperature: 0.
        @@ -44,0 +46 @@ prompt_manager {
        +  restart_messages_len_gt: 10
        @@ -62 +64 @@ llm_parser_by_group {
        -max_iterations: 50
        +max_iterations: 60
        """
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

    def run_java_metrics(self, **kwargs) -> Dict[str, int]:
        """Collect Java metrics."""
        poms = utils.find_files(self.root_dir, POM)

        metrics = defaultdict(int)
        metrics["num_pom_xml"] = len(poms)
        metrics[f"num_pom_xml__EQ__{len(poms):03d}"] += 1

        versions = file_utils.get_java_versions(poms, self.root_dir)
        if versions is None:
            # Invalid xml
            metrics["java_version-invalid-xml"] += 1
        else:
            versions, version_dict = versions
            if versions is None:
                # Still valid xml
                metrics["java_version-none"] += 1
            else:
                # Count
                metrics[f"java_version-unique-count__EQ__{len(versions):03d}"] += 1
                # Value(s)
                for version in versions:
                    metrics[f"java_version-value__EQ__{version}"] += 1
                versions = "|".join(sorted(list(versions)))
                metrics[f"java_version-values__EQ__{versions}"] += 1
                # Key
                metrics[f"java_version-count-keys__EQ__{len(version_dict):03d}"] += 1
                for version_key, _ in version_dict.items():
                    metrics[f"java_version-key__EQ__{version_key}"] += 1

        java_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k
            in ("java_home", "max_mvn_iterations", "mvn_command", "timeout_minutes")
        }

        run_java_hash = kwargs.get("run_java_hash", False)
        java_kwargs.update(
            {
                "max_attempts": None,
                "ground_truth": self.ground_truth,
                "do_search": not run_java_hash,
            }
        )

        base_commit = kwargs.get("run_java_base_commit_search")
        base_commit_no_maven = (
            kwargs.get("run_java_base_commit_search_no_maven") and not base_commit
        )
        if base_commit or base_commit_no_maven:
            metrics.update(
                file_utils.keep_java_repo_with_history(
                    self.root_dir, self, no_maven=base_commit_no_maven, **java_kwargs
                )[-1]
            )

        if run_java_hash:
            metrics.update(hash_utils.get_repo_snapshot_info(self))

        return metrics

    def run_metrics(self, java_versions: bool = False, **kwargs) -> Dict[str, int]:
        """Collect metrics."""
        self._metrics = defaultdict(int)

        def _init_metrics():
            self._metrics["00-start"] += 1

            if kwargs.get("add_ground_truth", True):
                gs = self.ground_truth or self.root_dir
                self._metrics[
                    f"ground_truth__EQ__{gs[0] if isinstance(gs, (list, tuple)) else gs}"
                ] += 1

        _init_metrics()
        if self.root_dir is None or not os.path.exists(self.root_dir):
            self._metrics["00--01--dir-not-exists-finish-early"] += 1
            return self.metrics

        if java_versions:
            self._metrics = self.run_java_metrics(**kwargs)
            _init_metrics()  # NOTE the reset right above

        if kwargs.get("run_repo_license") and not isinstance(self.ground_truth, str):
            url = self.ground_truth[0]
            self._metrics[f"00-license__EQ__{utils.get_github_license(url)}"] += 1

        # Branch
        git_branch = self.branch()[0]
        if isinstance(git_branch, str):
            lines = [l.strip() for l in self.branch()[0].splitlines()]
            lines = [l for l in lines if l]

            curr = ",".join([l for l in lines if l.startswith("*")])
            if len(lines) > 5:
                lines = lines[:5]
                if curr not in lines:
                    lines = [curr] + lines
            self._metrics[f"01--00--branch=<{curr}>"] += 1
            self._metrics[f"01--01--branch-len=<{len(lines):03d}>"] += 1
            self._metrics[f"01--02--branches=<{','.join(lines)}>"] += 1
        else:
            self._metrics[f"01--10--finish-early-branch=<{GIT_NA}>"] += 1
            return self.metrics

        # A valid git dir below.
        # Status
        git_status = self.status()[0]
        if isinstance(git_status, str):
            lines = [l.strip() for l in self.status()[0].splitlines()]
            lines = [l for l in lines if l and l in GIT_STATUS_REGEX]
            for line in lines:
                self._metrics[f"02--status--<{line}>"] += 1

        git_untracked = self.show_untracked()
        self._metrics[f"03--untracked--len=<{len(git_untracked):03d}>"] += 1
        count = 0
        for ufile in git_untracked:
            if os.path.isdir(ufile):
                count += 1
            else:
                suffix = ufile.split(".")[-1]
                self._metrics[f"03--untracked-00--suffix=<{suffix}>"] += 1
        self._metrics[f"03--untracked-01--dir-count=<{count:03d}>"] += 1

        self._metrics["04-finish"] += 1
        return self.metrics

    @property
    def metrics(self):
        """Get metrics."""
        return metric_utils.reformat_metrics(self, self._metrics)

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
