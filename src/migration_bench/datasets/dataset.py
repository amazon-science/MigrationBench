"""Datasets."""

from dataclasses import dataclass
import logging
from typing import Any, Dict, Optional, Tuple, Union

import numpy
from self_debug.proto import dataset_pb2

from self_debug.common import utils


@dataclass
class GithubData:
    """Github repo data."""

    github_url: str
    star_count: Optional[int] = None
    project_path: Optional[str] = None
    version_and_commit_ids: Any = None


class PortedGithubData(GithubData):
    """Ported repos."""

    s3_dir: str


def _field_value_as_bool(obj, field):
    value = getattr(obj, field)
    return isinstance(value, int) or bool(value)


def prep_github_dataset(
    data: Dict[str, str], field_map: Dict[str, str] = None
) -> GithubData:
    """Load dataset."""
    if field_map is None:
        field_map = {
            "file_path": "project_path",
            "url": "github_url",
            "versions_commits": "version_and_commit_ids",
        }

    return GithubData(**{field_map.get(key, key): value for key, value in data.items()})


def load_github_dataset(
    filename: str, field_map: Dict[str, str] = None
) -> Tuple[GithubData]:
    """Load dataset."""
    logging.info("Loading dataset: `%s` ...", filename)
    dataset = utils.load_json(filename)

    logging.info("Loaded  dataset (len = %d): `%s`.", len(dataset), filename)

    result = []
    for data in dataset:
        result.append(prep_github_dataset(data, field_map))

    return tuple(result)


def load_dataset(
    filename: Union[str, dataset_pb2.Dataset],
) -> Tuple[Union[str, GithubData]]:
    """Load dataset."""
    # `.json` file holding multiple Github repos.
    if isinstance(filename, str):
        return load_github_dataset(filename)

    config = filename

    result = []
    for data in [config.dataset_repo] + list(config.dataset_repos):
        if data.HasField("local_repo"):
            result.append(data.local_repo.root_dir)
        elif data.HasField("s3_repo"):
            result.append(data.s3_repo.s3_dir)
        elif data.HasField("github_repo"):
            if data.github_repo.HasField("filename_json"):
                result += list(load_github_dataset(data.github_repo.filename_json))
            else:
                kwargs = {
                    "github_url": data.github_repo.github_url,
                    "version_and_commit_ids": [data.github_repo.commit_id],
                }
                result.append(GithubData(**kwargs))

    return tuple(result)


def show_stats(dataset) -> Tuple[int]:
    """Show dataset stats."""
    dataset = [d for d in dataset if isinstance(d, GithubData)]

    stats = []
    for field in (
        "github_url",
        "star_count",
        "project_path",
        "version_and_commit_ids",
    ):
        field_count = sum(_field_value_as_bool(x, field) for x in dataset)
        logging.info("%25s: %d", field, field_count)
        stats.append(field_count)

        if field == "version_and_commit_ids":
            total_count = sum(len(getattr(x, field)) for x in dataset)
            stats.append(total_count)

    col = [data.star_count for data in dataset if data.star_count is not None]
    if col:
        logging.info(
            "(len, min, max, avg, med, std) = (%d, %.1f, %.1f, %.1f, %.1f, %.1f)",
            len(col),
            numpy.min(col),
            numpy.max(col),
            numpy.mean(col),
            numpy.median(col),
            numpy.std(col),
        )

    return tuple(stats)


def main():
    """Main."""
    dataset = load_dataset("csharp_00_core-to-core.json")
    show_stats(dataset)

    for repo in dataset[:3]:
        logging.info(repo)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    main()
