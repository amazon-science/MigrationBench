"""Unit tests for the git_repo.py."""

from collections import defaultdict
import logging
import os
import shutil
import tempfile
import unittest

from parameterized import parameterized

from self_debug.common import git_repo, utils


GIT_CLEAN = git_repo.GIT_STATUS_CLEAN

GIT_NA = git_repo.GIT_NA

GIT_STAGED = git_repo.GIT_STATUS_STAGED
GIT_UNSTAGED = git_repo.GIT_STATUS_UNSTAGED
GIT_UNTRACKED = git_repo.GIT_STATUS_UNTRACKED

BRANCH_00 = "new-branch-name-created"
BRANCH_01 = "new-branch-name-other"
BRANCH_NOT_WORKING = "branch-name-not-working-at-all:"

KWARGS_METRICS = {
    "add_ground_truth": False,
}

MASTER = "master"


METRICS_CLEAN = defaultdict(
    int,
    {
        "GitRepo::00-start": 1,
        "GitRepo::01--00--branch=<* master>": 1,
        "GitRepo::01--01--branch-len=<001>": 1,
        "GitRepo::01--02--branches=<* master>": 1,
        f"GitRepo::02--status--<{GIT_CLEAN}>": 1,
        "GitRepo::03--untracked--len=<000>": 1,
        "GitRepo::03--untracked-01--dir-count=<000>": 1,
        "GitRepo::04-finish": 1,
    },
)

METRICS_EMPTY = defaultdict(int, {})

METRICS_UNTRACKED = defaultdict(
    int,
    {
        "GitRepo::00-start": 1,
        "GitRepo::01--00--branch=<* master>": 1,
        "GitRepo::01--01--branch-len=<001>": 1,
        "GitRepo::01--02--branches=<* master>": 1,
        f"GitRepo::02--status--<{GIT_UNTRACKED}>": 1,
        "GitRepo::03--untracked--len=<001>": 1,
        "GitRepo::03--untracked-00--suffix=<new>": 1,
        "GitRepo::03--untracked-01--dir-count=<000>": 1,
        "GitRepo::04-finish": 1,
    },
)

METRICS_UNSTAGED = defaultdict(
    int,
    {
        "GitRepo::00-start": 1,
        "GitRepo::01--00--branch=<* master>": 1,
        "GitRepo::01--01--branch-len=<001>": 1,
        "GitRepo::01--02--branches=<* master>": 1,
        f"GitRepo::02--status--<{GIT_UNSTAGED}>": 1,
        f"GitRepo::02--status--<{GIT_UNTRACKED}>": 1,
        "GitRepo::03--untracked--len=<001>": 1,
        "GitRepo::03--untracked-00--suffix=<new>": 1,
        "GitRepo::03--untracked-01--dir-count=<000>": 1,
        "GitRepo::04-finish": 1,
    },
)

_GIT_DIFF_FILE = """
diff --git a/test_file.txt b/test_file.txt
index c631a45..75c74bd 100644
--- a/test_file.txt
+++ b/test_file.txt
@@ -1,2 +1,3 @@
 Hello, world
 Test content
+Additional content""".lstrip()

_GIT_DIFF_FILE__MASTER = """
diff --git a/test_file.txt b/test_file.txt
index a5c1966..75c74bd 100644
--- a/test_file.txt
+++ b/test_file.txt
@@ -1 +1,3 @@
 Hello, world
+Test content
+Additional content""".lstrip()


class TestGitRepo(unittest.TestCase):
    """Unit tests for the git_repo.py."""

    def setUp(self):
        """Set up a temp dir for tests."""
        self.root_test_dir = tempfile.mkdtemp()

        self.work_dir = os.path.join(self.root_test_dir, "repo")
        os.makedirs(self.work_dir, exist_ok=True)

        self.repo = git_repo.GitRepo(self.work_dir)
        self.repo.initialize()

        self.file_path = os.path.join(self.work_dir, "test_file.txt")
        utils.export_file(self.file_path, "Hello,\nWorld.\n")

        commit_message = "Initial commit"
        self.repo.commit_all(commit_message)

    def tearDown(self):
        """Clean up the temp dir."""
        shutil.rmtree(self.root_test_dir)

    def test_clean(self):
        """Test for git clean."""
        self.assertNotIn("Untracked", self.repo.status()[0])
        self.assertEqual(self.repo.run_metrics(**KWARGS_METRICS), METRICS_CLEAN)

        utils.export_file(f"{self.file_path}.new", "Test content")
        self.assertIn("Untracked", self.repo.status()[0])
        self.assertEqual(self.repo.run_metrics(**KWARGS_METRICS), METRICS_UNTRACKED)

        # Clean up: Idempotent.
        for _ in range(2):
            self.assertTrue(self.repo.clean())
            self.assertNotIn("Untracked", self.repo.status()[0])
            self.repo.run_metrics(**KWARGS_METRICS)
            self.assertEqual(self.repo.metrics, METRICS_CLEAN)

    @parameterized.expand(
        (
            # Dir does not exist.
            (
                "{root_dir}/file-should-not-exist--very-long/could-be/nested",
                {},
                {},
                defaultdict(
                    int,
                    {
                        "GitRepo::00-start": 1,
                        "GitRepo::00--01--dir-not-exists-finish-early": 1,
                    },
                ),
            ),
            # Dir is not a git dir.
            (
                "/tmp",
                {},
                {},
                defaultdict(
                    int,
                    {
                        "GitRepo::00-start": 1,
                        f"GitRepo::01--10--finish-early-branch=<{GIT_NA}>": 1,
                    },
                ),
            ),
            (
                "/tmp",
                {},
                {
                    "java_versions": True,
                    # "run_java_hash": False,
                },
                defaultdict(
                    int,
                    {
                        "GitRepo::00-start": 1,
                        f"GitRepo::01--10--finish-early-branch=<{GIT_NA}>": 1,
                        "GitRepo::java_version-none": 1,
                        "GitRepo::num_pom_xml": 0,
                        "GitRepo::num_pom_xml__EQ__000": 1,
                    },
                ),
            ),
            (
                "/tmp",
                {},
                {
                    "java_versions": True,
                    "run_java_hash": True,
                },
                defaultdict(
                    int,
                    {
                        "GitRepo::00-start": 1,
                        f"GitRepo::01--10--finish-early-branch=<{GIT_NA}>": 1,
                        "GitRepo::java_version-none": 1,
                        "GitRepo::num_pom_xml": 0,
                        "GitRepo::num_pom_xml__EQ__000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-java__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-root-any-test-java__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-src-test-any-java__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-pom-xml__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-root-dir-exists__EQ__True": 1,
                        "GitRepo::RepoSnapshot::repo-root-src-test-dir-exists__EQ__False": 1,
                        "GitRepo::RepoSnapshot::repo-num-loc__EQ__000000": 1,
                        "GitRepo::RepoSnapshot::repo-num-test-cases__EQ__-002": 1,
                        "GitRepo::RepoSnapshot::repo_commit_first_00__EQ__": 1,
                        "GitRepo::RepoSnapshot::repo_commit_first_01__EQ__": 1,
                        "GitRepo::RepoSnapshot::repo_commit_last_00__EQ__": 1,
                        "GitRepo::RepoSnapshot::repo_snapshot_update_time__EQ__": 1,
                        # "GitRepo::RepoSnapshot::repo_snapshot_hash__EQ__*": 1,
                    },
                ),
            ),
            (
                "/tmp",
                {},
                {
                    "java_versions": True,
                    "run_java_base_commit_search": True,
                    "run_java_base_commit_search_no_maven": True,  # Rewrite to `False`
                    "run_java_hash": True,
                },
                defaultdict(
                    int,
                    {
                        "GitRepo::00-start": 1,
                        f"GitRepo::01--10--finish-early-branch=<{GIT_NA}>": 1,
                        "GitRepo::java_version-none": 1,
                        "GitRepo::num_pom_xml": 0,
                        "GitRepo::num_pom_xml__EQ__000": 1,
                        "GitRepo::BaseCommit::00-start": 1,
                        "GitRepo::BaseCommit::00-start-num-commits__EQ__0000": 1,
                        "GitRepo::BaseCommit::00-start-at-commit-index__EQ__0000": 1,
                        "GitRepo::BaseCommit::00-start-at-commit-index__EQ__0000-0000": 1,
                        "GitRepo::BaseCommit::09-00-reject-repo-initial-index-eq-total-len": 1,
                        "GitRepo::BaseCommit::09-01-REJECT-REPO-final-index-eq-total-len": 1,
                        "GitRepo::BaseCommit::10-keep-repo__EQ__False": 1,
                        "GitRepo::BaseCommit::11-keep-repo-base-commit-id__EQ__None": 1,
                        "GitRepo::BaseCommit::11-keep-repo-url__EQ__": 1,
                        "GitRepo::BaseCommit::11-keep-repo-index__EQ__0000": 1,
                        "GitRepo::BaseCommit::11-keep-repo-total-len__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-java__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-root-any-test-java__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-src-test-any-java__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-pom-xml__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-root-dir-exists__EQ__True": 1,
                        "GitRepo::RepoSnapshot::repo-root-src-test-dir-exists__EQ__False": 1,
                        "GitRepo::RepoSnapshot::repo-num-loc__EQ__000000": 1,
                        "GitRepo::RepoSnapshot::repo-num-test-cases__EQ__-002": 1,
                        "GitRepo::RepoSnapshot::repo_commit_first_00__EQ__": 1,
                        "GitRepo::RepoSnapshot::repo_commit_first_01__EQ__": 1,
                        "GitRepo::RepoSnapshot::repo_commit_last_00__EQ__": 1,
                        "GitRepo::RepoSnapshot::repo_snapshot_update_time__EQ__": 1,
                        # "GitRepo::RepoSnapshot::repo_snapshot_hash__EQ__*": 1,
                    },
                ),
            ),
            (
                "/tmp",
                {
                    "ground_truth": ("github.com", "BASE_COMMIT_ID"),
                },
                {
                    "java_versions": True,
                    # "run_java_base_commit_search": True,
                    "run_java_base_commit_search_no_maven": True,
                    "run_java_hash": True,
                    "run_repo_license": True,
                },
                defaultdict(
                    int,
                    {
                        "GitRepo::00-start": 1,
                        "GitRepo::00-license__EQ__None": 1,
                        f"GitRepo::01--10--finish-early-branch=<{GIT_NA}>": 1,
                        "GitRepo::ground_truth__EQ__github.com": 1,
                        "GitRepo::java_version-none": 1,
                        "GitRepo::num_pom_xml": 0,
                        "GitRepo::num_pom_xml__EQ__000": 1,
                        "GitRepo::BaseCommit::00-start": 1,
                        "GitRepo::BaseCommit::00-start-num-commits__EQ__0000": 1,
                        "GitRepo::BaseCommit::00-start-at-commit-index__EQ__0000": 1,
                        "GitRepo::BaseCommit::00-start-at-commit-index__EQ__0000-0000": 1,
                        "GitRepo::BaseCommit::09-00-reject-repo-initial-index-eq-total-len": 1,
                        ### "GitRepo::BaseCommit::09-01-REJECT-REPO-final-index-eq-total-len": 1,
                        "GitRepo::BaseCommit::10-keep-repo__EQ__False": 1,
                        "GitRepo::BaseCommit::11-keep-repo-base-commit-id__EQ__None": 1,
                        "GitRepo::BaseCommit::11-keep-repo-url__EQ__github.com____BASE_COMMIT_ID": 1,
                        "GitRepo::BaseCommit::11-keep-repo-index__EQ__0000": 1,
                        "GitRepo::BaseCommit::11-keep-repo-total-len__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-java__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-root-any-test-java__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-src-test-any-java__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-num-files-pom-xml__EQ__0000": 1,
                        "GitRepo::RepoSnapshot::repo-root-dir-exists__EQ__True": 1,
                        "GitRepo::RepoSnapshot::repo-root-src-test-dir-exists__EQ__False": 1,
                        "GitRepo::RepoSnapshot::repo-num-loc__EQ__000000": 1,
                        "GitRepo::RepoSnapshot::repo-num-test-cases__EQ__-002": 1,
                        "GitRepo::RepoSnapshot::repo_commit_first_00__EQ__": 1,
                        "GitRepo::RepoSnapshot::repo_commit_first_01__EQ__": 1,
                        "GitRepo::RepoSnapshot::repo_commit_last_00__EQ__": 1,
                        "GitRepo::RepoSnapshot::repo_snapshot_update_time__EQ__": 1,
                        # "GitRepo::RepoSnapshot::repo_snapshot_hash__EQ__*": 1,
                    },
                ),
            ),
        )
    )
    def test_run_metrics(self, root_dir, repo_kwargs, kwargs, expected_metrics):
        """Test for run_metrics."""
        root_dir = root_dir.format(root_dir=self.root_test_dir)

        repo = git_repo.GitRepo(root_dir, **repo_kwargs)
        self.assertEqual(repo.metrics, METRICS_EMPTY)

        metrics = repo.run_metrics(**kwargs)
        logging.warning(metrics)
        self.assertEqual(metrics, repo.metrics)
        self.assertIn(len(metrics) - len(expected_metrics), (0, 1, 2))

        # Remove hash
        keys = sorted(metrics.keys())
        for key in keys:
            if key.startswith("GitRepo::ground_truth__EQ__"):
                if not repo_kwargs:
                    metrics.pop(key)
            elif key.startswith("GitRepo::RepoSnapshot::repo_snapshot_hash__EQ__"):
                metrics.pop(key)

        self.assertEqual(metrics, expected_metrics)

    @parameterized.expand(
        (
            (
                BRANCH_00,
                MASTER,
                False,
                "-d",
                True,
            ),
            (
                BRANCH_00,
                MASTER,
                True,
                "-d",
                False,  # Checked out to the new branch and unable to delete.
            ),
            (
                BRANCH_00,
                MASTER,
                False,
                "-D",
                True,
            ),
            (
                BRANCH_00,
                MASTER,
                True,
                "-D",
                False,  # Checked out to the new branch and unable to delete.
            ),
        )
    )
    def test_delete_branch(self, branch, master, checkout, option, expected_success):
        """Test for git delete a branch."""
        self.repo.new_branch(branch, master, checkout)
        output, success = self.repo.branch()
        self.assertIn(branch, output)
        self.assertTrue(success)

        # Idempotent.
        for _ in range(2):
            self.repo.delete_branch(branch, option)

            output, success = self.repo.branch()
            if expected_success:
                self.assertNotIn(branch, output)
            else:
                self.assertIn(branch, output)
            self.assertTrue(success)

    @parameterized.expand(
        (
            (
                BRANCH_00,
                MASTER,
                False,
                BRANCH_00,
                f"* {MASTER}",
            ),
            (
                BRANCH_00,
                MASTER,
                True,
                f"* {BRANCH_00}",
                MASTER,
            ),
        )
    )
    def test_new_branch(
        self, branch, master, checkout, expected_branch, expected_master
    ):
        """Test creating a new git branch."""
        # Idempotent.
        for _ in range(2):
            self.assertTrue(self.repo.new_branch(branch, master, checkout))

            output, success = self.repo.branch()
            logging.debug("git branch: <<<%s>>>", output)
            for name in (expected_branch, expected_master):
                self.assertIn(name, output)
            self.assertTrue(success)

    @parameterized.expand(
        (
            # Same branch to itself, no matter it exists or not.
            (
                MASTER,
                MASTER,
            ),
            (
                BRANCH_00,
                BRANCH_00,
            ),
            # Source branch doesn't exist.
            (
                BRANCH_00,
                BRANCH_01,
            ),
            (
                MASTER,
                BRANCH_01,
            ),
            # Target branch is invalid.
            (
                BRANCH_NOT_WORKING,
                MASTER,
            ),
        )
    )
    def test_new_branch_fail(self, branch, master):
        """Test creating a new git branch: Failing cases."""
        for _ in range(2):
            self.assertFalse(self.repo.new_branch(branch, master))

    @parameterized.expand(
        (
            (
                BRANCH_00,
                MASTER,
            ),
            (
                BRANCH_01,
                MASTER,
            ),
        )
    )
    def test_rename_branch(self, branch, source_branch):
        """Test renaming a git branch."""
        self.assertIn(source_branch, self.repo.branch()[0])

        self.assertTrue(self.repo.rename_branch(branch, source_branch))

        output, success = self.repo.branch()
        self.assertIn(branch, output)
        self.assertNotIn(source_branch, output)
        self.assertTrue(success)

        # Not idempotent.
        self.assertFalse(self.repo.rename_branch(branch, source_branch))

    @parameterized.expand(
        (
            # Same branch to itself.
            (
                MASTER,
                MASTER,
            ),
            (
                BRANCH_00,
                BRANCH_00,
            ),
            # Source branch doesn't exist.
            (
                BRANCH_01,
                BRANCH_00,
            ),
            (
                MASTER,
                BRANCH_00,
            ),
            # Target is invalid.
            (
                BRANCH_NOT_WORKING,
                MASTER,
            ),
        )
    )
    def test_rename_branch_fail(self, branch, source_branch):
        """Test renaming a git branch: Failing cases."""
        self.assertFalse(self.repo.rename_branch(branch, source_branch))

        output, _ = self.repo.branch()
        self.assertIn(MASTER, output)
        if source_branch != MASTER:
            self.assertNotIn(source_branch, output)

    def test_add_all(self):
        """Test if files are correctly added to the Git staging area."""
        utils.export_file(self.file_path, "Test content")

        self.repo.add_all()

        output = self.repo.show_staged(self.file_path)
        logging.info("git staged: <<<%s>>>", output)

        output, success = self.repo.status()
        logging.debug("git status: <<<%s>>>", output)
        self.assertIn(os.path.basename(self.file_path), output)
        self.assertTrue(success)

    @parameterized.expand(
        (
            ((), METRICS_CLEAN),
            # Exclude untracked files.
            (("-u",), METRICS_UNTRACKED),
        )
    )
    def test_commit_all(self, args, expected_metrics):
        """Test if changes are correctly committed with the specified commit message."""
        self.assertEqual(self.repo.run_metrics(**KWARGS_METRICS), METRICS_CLEAN)

        utils.export_file(self.file_path, "Hello,\nWorld.\n", "a")
        new_file = f"{self.file_path}.new"
        utils.export_file(new_file, "Hello,\nWorld.\n", "a")
        self.assertEqual(self.repo.run_metrics(**KWARGS_METRICS), METRICS_UNSTAGED)
        self.assertEqual(self.repo.show_untracked(), (new_file,))

        commit_message = "New <commit message>."
        self.assertTrue(self.repo.commit_all(commit_message, *args))
        url = self.repo.get_github_url()
        logging.warning("URL = %s.", url)
        self.assertFalse(url[-1])
        self.assertEqual(self.repo.run_metrics(**KWARGS_METRICS), expected_metrics)

        # git log ...
        output, success = self.repo.log()
        logging.info("git log: <<<%s>>>", output)
        self.assertIn(commit_message, output)
        self.assertTrue(success)

        # git log ...
        short_output, success = self.repo.log(num=0, options=["--format='%H'"])
        logging.info("git log: <<<%s>>>", short_output)
        self.assertNotIn(commit_message, short_output)
        self.assertTrue(success)

        commit_ids = short_output.splitlines()
        self.assertEqual(len(commit_ids), 2)
        for commit_id in commit_ids:
            self.assertTrue(commit_id.startswith("'"))
            self.assertTrue(commit_id.endswith("'"))

            cid = commit_id[1:-1]
            self.assertIn(f"commit {cid}\nAuthor: ", output)

    @parameterized.expand(
        (
            (False, True, True),
            (True, False, False),
            (True, True, False),
        )
    )
    def test_restore(
        self, restore_staged: bool, restore_unstaged: bool, expected_apply_success: int
    ):
        """Test if files are correctly restored to their previous state."""
        utils.export_file(self.file_path, "Hello, world\n")
        self.repo.commit_all("Initial commit.")

        utils.export_file(self.file_path, "Test content\n", "a")
        self.repo.add_all()

        # Modify the file again.
        utils.export_file(self.file_path, "Additional content\n", "a")

        # 0. Initial state.
        output, success = self.repo.status()
        logging.debug("[0] git status: <<<%s>>>", output)
        self.assertIn(GIT_STAGED, output)
        self.assertIn(GIT_UNSTAGED, output)
        self.assertTrue(success)

        output, success = self.repo.diff()
        self.assertIn("+Additional content", output)
        self.assertEqual(output, _GIT_DIFF_FILE)
        self.assertTrue(success)

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_file = os.path.join(temp_dir, "git.diff")

            for index in range(2):
                if index:
                    kwargs = {}
                else:
                    kwargs = {
                        "files": ["master", "."],
                    }
                output, success = self.repo.diff(stdout=tmp_file, **kwargs)
                self.assertEqual(
                    utils.load_file(tmp_file),
                    (_GIT_DIFF_FILE if index else _GIT_DIFF_FILE__MASTER) + "\n",
                )
                self.assertFalse(success)

            # 1. Restore the changes.
            self.repo.restore(
                restore_staged=restore_staged, restore_unstaged=restore_unstaged
            )
            output, success = self.repo.status()
            logging.info(
                "[1] git status (%s, %s): <<<%s>>>",
                restore_staged,
                restore_unstaged,
                output,
            )
            if restore_staged:
                self.assertNotIn(GIT_STAGED, output)
            else:
                self.assertIn(GIT_STAGED, output)
            self.assertNotIn(GIT_UNSTAGED, output)

            output, success = self.repo.diff()
            self.assertEqual("", output)

            # 2. Apply the changes
            success = self.repo.apply(tmp_file)
            self.assertEqual(success, expected_apply_success)

            if success:
                output, success = self.repo.diff()
                self.assertIn("+Additional content", output)
                self.assertEqual(output, _GIT_DIFF_FILE)
                self.assertTrue(success)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    unittest.main()
