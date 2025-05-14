"""Projects in local dirs, s3 or github."""

import abc
import glob
import logging
import os
from typing import Optional, Tuple
from pathlib import Path

from self_debug.common import pom_utils, repo as common_repo, s3_data, utils
from self_debug.common.git_repo import GitRepo
from self_debug.proto import dataset_pb2

ROOT_DIR = "root_dir"
PROJECT = "project"

RANDOM_LEN = 6


class Project(abc.ABC):
    """A class to hold a project.

    ground_truth: Local path, s3, github urls.
    init_dir: Local path, downloaded path for s3/ github.
    """

    def __init__(
        self, config: dataset_pb2.DatasetRepo, readonly: bool = False, **kwargs
    ):
        logging.debug("[ctor] Project: config = <<<\n%s\n>>>.", config)

        self.config = config

        self.readonly = readonly
        self.kwargs = kwargs

        self.root_dir = kwargs.pop(ROOT_DIR, None)
        self.project = kwargs.pop(PROJECT, "")

        self._ground_truth = None
        self._init_dir = None
        self.ported = None

    def maybe_update_jdk_version_and_commit(self, local_dir):
        """Maybe update JDK version and commit."""
        if not self.config.apply_seed_changes:
            return

        # update JDK version
        if not Path(os.path.join(local_dir, "pom.xml")).exists():
            raise ValueError(
                f"No `pom.xml` file found in repository root dir {local_dir}."
            )
        pom_files = glob.glob(os.path.join(local_dir, "**", "pom.xml"), recursive=True)
        logging.warning(
            "Number of pom.xml files to update = %d: `%s`.", len(pom_files), pom_files
        )
        for pom_file in pom_files:
            pom_utils.update_jdk_related(pom_file, pom_file)
        # commit changes
        git_repo = GitRepo(local_dir)
        git_repo.commit_all("set JDK version to 17 in pom.xml")

    @classmethod
    def create_from_config(cls, config: dataset_pb2.DatasetRepo, **kwargs):
        """Create from config."""
        if config.HasField("local_repo"):
            return LocalProject(config, **kwargs)

        if config.HasField("s3_repo"):
            return S3Project(config, **kwargs)

        if config.HasField("github_repo"):
            return GithubProject(config, **kwargs)

        raise Exception(f"Unsupported dataset <<<\n{config}\n>>>")

    @property
    def ground_truth(self):
        """Get single source of ground truth: e.g. local or s3 dirs."""
        if self._ground_truth is None:
            self._init_ground_truth()

        return self._ground_truth

    @property
    def init_dir(self) -> str:
        """Init dir (Read only): Local dir as is, or download from s3 to local."""
        if (
            self._init_dir is None or not os.path.exists(self._init_dir)
        ) and self.ported is not False:
            self._init_root_dir()

        return self._init_dir

    def maybe_init_root_dir(
        self, root_dir: Optional[str] = None
    ) -> Tuple[Optional[str], bool]:
        """Maybe init root dir: Return root_dir and whether it's re-setup (bool)."""
        if root_dir and os.path.exists(root_dir):
            return root_dir, False

        # `root_dir` is invalid.
        logging.info("Init root dir: `%s` (~~`%s`~~) ...", self.ground_truth, root_dir)
        return self.init_dir, True

    def local_upload_dir(self, repo_dir: str) -> str:
        """Local dir to upload to s3, given a `repo_dir`."""
        return repo_dir

    def _local_upload_repo(self, local_dir: str) -> str:
        """Local repo dir in the upload dir."""
        return local_dir

    def new_copy(self, none_is_ok: bool = True):
        """Make a new copy: For write purposes."""
        if self.readonly:
            raise Exception("This is a readonly projects, not supporting new copies!")

        source = self.local_upload_dir(self.init_dir)
        if source is None or not os.path.exists(source):
            if none_is_ok:
                return None
            raise Exception("Unable to make a new copy for `%s`.", self.ground_truth)

        return self._local_upload_repo(
            utils.copy_dir(source, prefix=f"{os.path.basename(source)}--r-")
        )

    @abc.abstractmethod
    def _init_ground_truth(self):
        """Init ground truth."""

    @abc.abstractmethod
    def _init_root_dir(self) -> str:
        """Init root dir."""


class LocalProject(Project):
    """Local project."""

    def _init_ground_truth(self):
        """Init ground truth."""
        if self._ground_truth is None:
            self._ground_truth = self.config.local_repo.root_dir

    def _init_root_dir(self):
        """Init root dir: No op."""
        self.ported = True
        self._init_dir = self.ground_truth
        self.maybe_update_jdk_version_and_commit(self._init_dir)


class GithubProject(Project):
    """Github project."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.github_config = None

    def _init_ground_truth(self):
        """Init ground truth."""
        if self._ground_truth is None:
            repo = self.config.github_repo
            self._ground_truth = (repo.github_url, repo.commit_id)

    def _init_root_dir(self):
        """Init root dir: Download from Github."""
        try:
            # `name` is unqiue across the dataset.
            result = common_repo.RepoToDownload.create_from_config(
                s3_or_github_url=self.ground_truth[0], commit_id=self.ground_truth[-1]
            ).maybe_copy_repo(work_dir=f"/tmp/ported/{self.config.github_repo.name}")

            if result is not None and result[-1] is not None:
                local_dir, github_config = result

                # update JDK version
                self.maybe_update_jdk_version_and_commit(local_dir)

                self.project = github_config.dataset.dataset_repo.project
                self.github_config = github_config
                self.ported = github_config.dataset.dataset_repo.ported

                self._init_dir = local_dir
                logging.warning("Local copy: %s.", local_dir)
                return
        except Exception as error:
            logging.exception(
                "Unable to download from `%s`: `%s`.", self.ground_truth, error
            )

        self.ported = False
        self._init_dir = None


class S3Project(Project):
    """Local project."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.s3_config = None

    def _init_ground_truth(self):
        """Init ground truth."""
        if self._ground_truth is None:
            self._ground_truth = self.config.s3_repo.s3_dir

    def _init_root_dir(self):
        """Init root dir: Download from s3."""
        try:
            if self.ground_truth.startswith("s3://self-dbg-plus/datasets/"):
                result = s3_data.maybe_copy_repo(self.ground_truth)
            else:
                result = common_repo.RepoToDownload.create_from_config(
                    s3_or_github_url=self.ground_truth
                ).maybe_copy_repo(
                    # work_dir="tmp/ported/{bucket}--{key}"
                )

            if result is not None:
                local_dir, s3_config = result
                self.maybe_update_jdk_version_and_commit(local_dir)

                self.project = s3_config.dataset.dataset_repo.project
                self.s3_config = s3_config
                self.ported = s3_config.dataset.dataset_repo.ported

                self._init_dir = local_dir
                logging.warning("Local copy: %s.", local_dir)
                return
        except Exception as error:
            logging.exception(
                "Unable to download from `%s`: `%s`.", self.ground_truth, error
            )

        self.ported = False
        self._init_dir = None

    def local_upload_dir(self, repo_dir: str) -> str:
        """`repo_dir` has the repo only, and its parent has relevant metadata."""
        if repo_dir is None:
            return repo_dir

        return os.path.dirname(repo_dir)

    def _local_upload_repo(self, local_dir: str) -> str:
        """Local repo dir in the upload dir."""
        if local_dir is None:
            return local_dir

        return os.path.join(local_dir, os.path.basename(self.init_dir))
