"""Import dataset from huggingface."""

import os

import datasets

from migration_bench.proto import dataset_pb2

# https://huggingface.co/datasets/AmazonScience/migration-bench-java-full
JAVA_FULL = "AmazonScience/migration-bench-java-full"
JAVA_SELECTED = "AmazonScience/migration-bench-java-selected"
JAVA_UTG = "AmazonScience/migration-bench-java-utg"

COLUMN_REPO = "repo"
COLUMN_COMMIT = "base_commit"
COLUMNS = (COLUMN_REPO, COLUMN_COMMIT)

DATASET_NAME_OPTIONS = {
    dataset_pb2.Dataset.HuggingfaceOption.MIGRATION_BENCH_JAVA_FULL: JAVA_FULL,
    dataset_pb2.Dataset.HuggingfaceOption.MIGRATION_BENCH_JAVA_SELECTED: JAVA_SELECTED,
    dataset_pb2.Dataset.HuggingfaceOption.MIGRATION_BENCH_JAVA_UTG: JAVA_UTG,
}


def load_hf_dataset(
    name: str = JAVA_FULL, split: str = "test", columns=None, first_n: int = None
):
    """Load HF dataset by name, taking given `columns` and `first_n` rows only."""
    hf_ds = datasets.load_dataset(name, split=split)

    if columns is None:
        columns = list(hf_ds.column_names)

    values = {}
    for col in columns:
        loaded = list(hf_ds[col])
        if first_n is not None:
            if first_n > 0:
                loaded = loaded[:first_n]
            elif first_n < 0:
                loaded = loaded[first_n:]

        values[col] = loaded

    return values


def resolve_hf_dataset(ds_config, **kwargs):
    """Resolve HF dataset by name."""
    if (
        (not ds_config.HasField("hf_option"))
        or len(ds_config.dataset_repos)
        or ds_config.hf_option not in DATASET_NAME_OPTIONS
    ):
        return ds_config

    kwargs.update(
        {
            "name": DATASET_NAME_OPTIONS[ds_config.hf_option],
        }
    )

    rows = load_hf_dataset(**kwargs)
    for row in zip(rows[COLUMN_REPO], rows[COLUMN_COMMIT]):
        repo, commit = row
        cfg = ds_config.dataset_repos.add()
        cfg.github_repo.github_url = os.path.join("https://github.com", repo)
        cfg.github_repo.commit_id = commit

    return ds_config
