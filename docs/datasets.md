# 🤗 Datasets

MigrationBench provides three datasets on [Hugging Face](https://huggingface.co/collections/AmazonScience/migrationbench). 

All repositories are available on GitHub under `MIT` or `Apache-2.0` licenses.

---

## Available Datasets

| Dataset | Size | Description |
|---------|------|-------------|
| **[MigrationBench-Full](https://huggingface.co/datasets/AmazonScience/migration-bench-java-full)** | 5,102  | Full dataset. Each repo has unit test.|
| **[MigrationBench-Selected](https://huggingface.co/datasets/AmazonScience/migration-bench-java-selected)** | 300  | Curated challenging subset from Full |
| **[MigrationBench-UTG](https://huggingface.co/datasets/AmazonScience/migration-bench-java-utg)** | 4,814  | Unit test generation dataset. Each repo doesn't have unit test. Disjoint with java-full |


---

## Metadata

1. `repo (str)`: The original repo URL without the `https://github.com/` prefix
1. `base_commit (str)`: Base commit id
    - At this commit with `java 8` and `maven 3.9.6`, the repository is able to (1) compile and (2) pass existing unit tests and integration tests if any
    - It is the starting point for code migration from `java 8` to LTS versions
1. `num_java_files (int)`: Number of `*.java` files in the repository at `base_commit`, similarly for all other `num_*` columns
1. `num_loc (int)`: Lines of code for the repository
1. `num_pom_xml (int)`: Number of modules (`pom.xml` files) in the repository
1. `num_src_test_java_files (int)`: Number of `*.java` files in the dedicated `src/test/` directory
1. `num_test_cases (int)`: Number of test cases, based on running the `mvn -f test .` command in the root directory
    - Non negative values indicate number of test cases is parsed correctly from the output
    - Negative values means it's unable to parse the output: `[INFO] Results:` (`-2`) or `[INFO] Tests run:` (`-1`) regex is missing
1. `license (str)`: The license of the repository, either `MIT` or `Apache2.0` for the whole dataset

---

## Loading Datasets

**Install Hugging Face Datasets library:**

```bash
pip install datasets
```

**Load and use the datasets:**

```python
from datasets import load_dataset

# Load java-selected dataset
dataset = load_dataset("AmazonScience/migration-bench-java-selected")

# Iterate through repositories
for item in dataset['test']:
    print(f"Repository: {item['repo']}")
```


---


Stay tuned for updates!
