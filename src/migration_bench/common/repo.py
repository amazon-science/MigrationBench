"""Util functions for repo.

# 1. S3
rm -rf /tmp/ported/ozt-ngde--20240620_presd--acrobot.zip
python repo.py s3://ozt-ngde/20240620_presd/acrobot.zip    /tmp/ported/{bucket}--{key}

# 2. Github
rm -rf /tmp/ported/jsafebox
python repo.py https://github.com/0rtis/jsafebox /tmp/ported/{repo}
"""

import abc
import logging
import sys

from self_debug.proto import config_pb2
from self_debug.common import github, s3_data, utils
from self_debug.datasets import dataset


GITHUB_PREFIX = "https://github.com/"
S3_PREFIX = "s3://"


class RepoToDownload(abc.ABC):
    """Repo."""

    def __init__(self, s3_or_github_url: str, **kwargs):
        self.s3_or_github_url = s3_or_github_url
        self.kwargs = kwargs

        logging.debug(
            "[ctor] %s: s3_or_github_url = `%s`.",
            self.__class__.__name__,
            self.s3_or_github_url,
        )

    @classmethod
    def create_from_config(cls, s3_or_github_url: str, **kwargs):
        """Create from config."""
        if s3_or_github_url.startswith(GITHUB_PREFIX):
            return GithubRepo(s3_or_github_url, **kwargs)

        if s3_or_github_url.startswith(S3_PREFIX):
            if s3_or_github_url.endswith(".zip"):
                return S3Zip(s3_or_github_url, **kwargs)

            return S3Folder(s3_or_github_url, **kwargs)

        raise ValueError(f"Unsupported repo to download: `{s3_or_github_url}`.")

    @abc.abstractmethod
    def maybe_download_repo(self, **kwargs):
        """Maybe copy repo."""

    @abc.abstractmethod
    def dataset_config(self) -> str:
        """Dataset config."""

    def maybe_copy_repo(self, **kwargs):
        """Maybe copy repo."""

        # 1. Download
        local_dir = self.maybe_download_repo(**kwargs)
        if not local_dir:
            return local_dir, None

        # 2. Maybe unzip
        zip_dir = self.maybe_unzip(local_dir)
        if not zip_dir:
            return zip_dir, None

        return zip_dir, utils.parse_proto(
            f"""
                dataset {{
                  dataset_repo {{
                    root_dir: "{zip_dir}"
                    project: "pom.xml"
                    ported: true

{self.dataset_config()}

                  }}
                }}
            """,
            config_pb2.Config,
        )

    def maybe_unzip(self, local_dir: str):
        """Maybe unzip."""
        return local_dir


class GithubRepo(RepoToDownload):
    """Github repo."""

    def __init__(self, s3_or_github_url: str, **kwargs):
        self.commit_id = kwargs.pop("commit_id", None)

        super().__init__(s3_or_github_url, **kwargs)

        logging.debug(
            "[ctor] %s: commit_id = `%s`.", self.__class__.__name__, self.commit_id
        )

    def maybe_download_repo(self, **kwargs):
        """Maybe download repo: Download from Github."""

        github_data = dataset.GithubData(
            github_url=self.s3_or_github_url,
            version_and_commit_ids=[{"commit_id": self.commit_id}]
            if self.commit_id
            else [],
        )
        return github.maybe_clone_repo(github_data, **kwargs)

    def dataset_config(self) -> str:
        """Dataset config."""
        return f"""
                github_repo {{
                  github_url: "{self.s3_or_github_url}"
                }}
        """


class S3Folder(RepoToDownload):
    """S3 folder."""

    def maybe_download_repo(self, **kwargs):
        """Maybe download repo: Download from s3."""
        work_dir = kwargs.pop("work_dir", "/tmp/ported/{bucket}--{key}")
        logging.warning(
            "[%s] Downloading to work dir: `%s` ...", self.__class__.__name__, work_dir
        )
        return s3_data.copy_repo(self.s3_or_github_url, work_dir=work_dir, **kwargs)

    def dataset_config(self) -> str:
        """Dataset config."""
        return f"""
                s3_repo {{
                  s3_dir: "{self.s3_or_github_url}"
                }}
        """


class S3Zip(S3Folder):
    """S3 .zip file."""

    def maybe_unzip(self, local_dir: str):
        """Maybe unzip."""
        return s3_data.unzip(local_dir, self.s3_or_github_url)


def run(argv):
    """Run."""
    s3_dir = s3_data.S3_REPO if len(argv) < 1 else argv[0]
    result = RepoToDownload.create_from_config(s3_or_github_url=s3_dir).maybe_copy_repo(
        work_dir="/tmp/ported/{bucket}--{key}" if len(argv) < 2 else argv[1]
    )
    logging.info("Repo is at: `%s`.", result)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    run(sys.argv[1:])
