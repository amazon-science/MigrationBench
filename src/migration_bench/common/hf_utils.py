"""Import dataset from huggingface."""

import datasets

# https://huggingface.co/datasets/AmazonScience/migration-bench-java-full
JAVA_FULL = "AmazonScience/migration-bench-java-full"
JAVA_SELECTED = "AmazonScience/migration-bench-java-selected"
JAVA_UTG = "AmazonScience/migration-bench-java-utg"

COLUMN_REPO = "repo"
COLUMN_COMMIT = "base_commit"
COLUMN_NUM_TEST_CASES = "num_test_cases"
COLUMNS = (COLUMN_REPO, COLUMN_COMMIT)

GITHUB_URL_PREFIX = "https://github.com"


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
