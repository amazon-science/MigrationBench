# MigrationBench
<table>
  <tr>
    <td style="padding: 0;">
      <a href="https://huggingface.co/collections/AmazonScience/migrationbench-68125452fc21a4564b92b6c3">
        <img src="https://img.shields.io/badge/-🤗 MigrationBench-4d5eff?style=flatten&labelColor" alt="MigrationBench (Hugging Face)">
      </a>
    </td>
    <td style="padding: 0;">
      <a href="https://github.com/amazon-science/MigrationBench">
        <img src="https://img.shields.io/badge/MigrationBench-000000?style=flatten&logo=github" alt="MigrationBench (GitHub)">
      </a>
    </td>
    <td style="padding: 0;">
      <a href="https://github.com/amazon-science/JavaMigration">
        <img src="https://img.shields.io/badge/JavaMigration-000000?style=flatten&logo=github&logoColor=white" alt="JavaMigration (GitHub)">
      </a>
    </td>
    <td style="padding: 0;">
      <a href="https://arxiv.org/abs/2505.09569">
        <img src="https://img.shields.io/badge/arXiv-2505.09569-b31b1b.svg?style=flatten" alt="MigrationBench (arXiv)">
      </a>
    </td>
    <td style="padding: 0; padding-left: 10px; vertical-align: middle;">
      <a href="https://huggingface.co/datasets/AmazonScience/migration-bench-java-full">
        <img src="https://img.shields.io/badge/-🤗 java--full-8a98ff?style=flat&labelColor" alt="java-full">
      </a>
    </td>
    <td style="padding: 0; vertical-align: middle;">
      <a href="https://huggingface.co/datasets/AmazonScience/migration-bench-java-selected">
        <img src="https://img.shields.io/badge/-🤗 java--selected-8a98ff?style=flat&labelColor" alt="java-selected">
      </a>
    </td>
    <td style="padding: 0; vertical-align: middle;">
      <a href="https://huggingface.co/datasets/AmazonScience/migration-bench-java-utg">
        <img src="https://img.shields.io/badge/-🤗 java--utg-8a98ff?style=flat&labelColor" alt="java-utg">
      </a>
    </td>
  </tr>
</table>

<!--
npm install -g markdown-toc
markdown-toc -i README.md
-->

<!-- toc -->

- [1. 📖 Overview](#1--overview)
  * [1.1 MigrationBench: Dataset and Evaluation Framework](#11-migrationbench-dataset-and-evaluation-framework)
  * [1.2 JavaMigration: Migration with LLMs](#12-javamigration-migration-with-llms)
- [2. 🤗 MigrationBench Datasets](#2--migrationbench-datasets)
- [3. Code Migration Evaluation](#3-code-migration-evaluation)
  * [3.1 Docker Mode (Recommended)](#31-docker-mode-recommended)
    + [3.1.1 Setup Docker](#311-setup-docker)
    + [3.1.2 Single Repository Evaluation](#312-single-repository-evaluation)
    + [3.1.3 Batch Evaluation](#313-batch-evaluation)
  * [3.2 Local Mode](#32-local-mode)
    + [3.2.1 Install Java and Maven](#321-install-java-and-maven)
    + [3.2.2 Install MigrationBench](#322-install-migrationbench)
    + [3.2.3 Single Repository Evaluation](#323-single-repository-evaluation)
    + [3.2.4 Batch Evaluation](#324-batch-evaluation)
  * [3.3 Predictions File Format](#33-predictions-file-format)
- [4. 📚 Citation](#4--citation)

<!-- tocstop -->

## 1. 📖 Overview

[MigrationBench](https://github.com/amazon-science/MigrationBench)
provides an automated and robust framework for evaluating code migration success.

- Reference paper: [MigrationBench: Repository-Level Code Migration Benchmark from Java 8](https://arxiv.org/abs/2505.09569)

### 1.1 [MigrationBench](https://github.com/amazon-science/MigrationBench): Dataset and Evaluation Framework

The name **MigrationBench** is used for both the dataset and the evaluation framework for code migration success:

1. [🤗 MigrationBench](https://huggingface.co/collections/AmazonScience/migrationbench-68125452fc21a4564b92b6c3)
is a large-scale code migration **benchmark dataset** at the **repository** level,
across multiple programming languages.
    - Current and initial release includes `java 8` repositories with the `maven` build system, as of May 2025.
2. [MigrationBench](https://github.com/amazon-science/MigrationBench)
(current Github package)
is the **evaluation framework** to assess code migration success,
from `java 8` to `17` or any other long-term support (LTS) versions.


The evaluation is an *approximation* for functional equivalence by checking the following:
1. The repo is able to build and pass all tests
1. Compiled classes' major versions are consistent with the target `java` version
   - `52` and `61` for `java 8` and `17` respectively
1. Test methods are invariant after code migration
1. Number of test cases is non-decreasing after code migration
1. The repos' dependency libraries match their *latest* major versions
   - Optional for **minimal migration** by definition, while
   - Required for **maximal migration**


### 1.2 [JavaMigration](https://github.com/amazon-science/JavaMigration): Migration with LLMs

[JavaMigration](https://github.com/amazon-science/JavaMigration)
is a separate Github package to conduct code migration with LLMs as a baseline solution, and it relies on the current package for the final evaluation.


## 2. [🤗 MigrationBench](https://huggingface.co/collections/AmazonScience/migrationbench-68125452fc21a4564b92b6c3) Datasets

There are three datasets in [🤗 MigrationBench](https://huggingface.co/collections/AmazonScience/migrationbench-68125452fc21a4564b92b6c3):
- All repositories included in the datasets are available on GitHub, under the `MIT` or `Apache-2.0` license.

| Index | Dataset                                       | Size  | Notes                                                                                               |
|-------|-----------------------------------------------|-------|-----------------------------------------------------------------------------------------------------|
| 1     | [🤗 `AmazonScience/migration-bench-java-full`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-full)         | 5,102 | Each repo has a test directory or at least one test case                              |
| 2     | [🤗 `AmazonScience/migration-bench-java-selected`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-selected) |   300 | A **subset** of [🤗 `migration-bench-java-full`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-full)                                          |
| 3     | [🤗 `AmazonScience/migration-bench-java-utg`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-utg)           | 4,814 | The unit test generation (utg) dataset, **disjoint** with [🤗 `migration-bench-java-full`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-full)|


## 3. Code Migration Evaluation

MigrationBench supports two evaluation modes:

1. **Docker Mode (Recommended)**: Runs evaluations in isolated Docker containers. No need to install Java or Maven locally.
2. **Local Mode**: Runs evaluations directly on your machine. Requires Java 17 and Maven 3.9.6 installed locally.

### 3.1 Docker Mode (Recommended)

Docker mode provides a consistent evaluation environment without requiring local Java/Maven installation. Each evaluation runs in an isolated container, making it ideal for batch processing and reproducible results.

**Benefits:**
- ✅ No local Java/Maven installation needed
- ✅ Consistent environment across different machines
- ✅ Parallel execution (multiple containers)
- ✅ Easy setup and onboarding

#### 3.1.1 Setup

**1. Install Docker:**

Follow the official Docker installation guide:
- **macOS**: https://docs.docker.com/desktop/install/mac-install/
- **Windows**: https://docs.docker.com/desktop/install/windows-install/
- **Linux**: https://docs.docker.com/engine/install/

**2. Verify Docker:**
```bash
docker --version
```

**3. Install MigrationBench:**
```bash
git clone https://github.com/amazon-science/MigrationBench.git
cd MigrationBench

pip install -r requirements.txt -e .
```

**That's it!** The Docker image will be built automatically on first run.


#### 3.1.2 Single Repository Evaluation

To run a single repository evaluation in Docker:

```bash
GITHUB_URL=https://github.com/0xShamil/java-xid
GIT_DIFF_FILE=/path/to/java-xid.diff

python run_eval.py --github_url $GITHUB_URL --git_diff_filename $GIT_DIFF_FILE --use_docker
```

**Evaluate with a migrated repository directory:**
```bash
MIGRATED_DIR=/path/to/migrated/repo
python run_eval.py --github_url $GITHUB_URL --migrated_root_dir $MIGRATED_DIR --use_docker
```

**Force rebuild the Docker image:**
```bash
python run_eval.py --github_url $GITHUB_URL --git_diff_filename $GIT_DIFF_FILE --use_docker --build_docker_image
```

#### 3.1.3 Batch Evaluation

To run batch evaluations in Docker:

```bash
PREDICTIONS=predictions.json

# Run batch evaluation in Docker
python run_eval.py --predictions_filename $PREDICTIONS --use_docker
```

**With parallel processing (recommended for large batches):**
```bash
# Run 8 Docker containers in parallel (each evaluates one repo)
python run_eval.py --predictions_filename $PREDICTIONS --use_docker --max_workers 8
```

**Important Notes:**
- File paths in the predictions file should be **absolute paths** on your host system
- The Docker container will automatically mount these paths as read-only volumes
- Each repository is evaluated in its own isolated container
- Docker mode automatically handles environment isolation and cleanup

### 3.2 Local Mode

Local mode runs evaluations directly on your machine. This requires Java 17 and Maven 3.9.6 installed locally.

#### 3.2.1 Install Java and Maven

**Install Java 17:**

```
# Install OpenJDK 17
sudo apt update
sudo apt install -y openjdk-17-jdk

# Verify installation
java --version
```

**Install Maven 3.9.6:**

```
# Download and install Maven
curl -O https://archive.apache.org/dist/maven/maven-3/3.9.6/binaries/apache-maven-3.9.6-bin.zip
unzip apache-maven-3.9.6-bin.zip
sudo mv apache-maven-3.9.6 /opt/

# Create symlinks
sudo ln -s /opt/apache-maven-3.9.6 /opt/maven # for MAVEN_HOME
sudo ln -s /opt/apache-maven-3.9.6/bin/mvn /usr/local/bin/mvn # so mvn works without PATH setup

# Clean up
rm apache-maven-3.9.6-bin.zip

# Verify installation
mvn --version
```


**Verify installations:**
```bash
java -version  # Should show version 17
mvn -version   # Should show version 3.9.6
```

#### 3.2.2 Install MigrationBench

```bash
git clone https://github.com/amazon-science/MigrationBench.git
cd MigrationBench

pip install -r requirements.txt -e .
```

#### 3.2.3 Single Repository Evaluation

```bash
GITHUB_URL=https://github.com/0xShamil/java-xid
GIT_DIFF_FILE=/path/to/java-xid.diff

python run_eval.py --github_url $GITHUB_URL --git_diff_filename $GIT_DIFF_FILE
```


#### 3.2.4 Batch Evaluation

```bash
PREDICTIONS=predictions.json

# Sequential processing
python run_eval.py --predictions_filename $PREDICTIONS

# Parallel processing (8 workers)
python run_eval.py --predictions_filename $PREDICTIONS --max_workers 8
```

### 3.3 Predictions File Format

For batch evaluation (both Docker and Local modes), provide a predictions file in JSON format.

For each repository, specify the GitHub URL and **one** of the following:

1. **`git_diff_file`**: Path to a file containing the git diff
2. **`git_diff`**: Git diff content as a string (can be empty for no changes)
3. **`migrated_root_dir`**: Absolute path to the migrated repository directory

**Example `predictions.json`:**

```json
[
  {
    "github_url": "https://github.com/0xShamil/java-xid",
    "git_diff_file": "/absolute/path/to/java-xid.diff"
  },
]
```
or
```json
[
  {
    "github_url": "https://github.com/0xShamil/java-xid",
    "git_diff": "diff --git a/pom.xml b/pom.xml\n--- a/pom.xml\n+++ b/pom.xml\n..."
  },
]
```
or
```json
[
  {
    "github_url": "https://github.com/0xShamil/java-xid",
    "migrated_root_dir": "/absolute/path/to/migrated/java-xid"
  },
]
```


## 4. 📚 Citation

```bibtex
@misc{liu2025migrationbenchrepositorylevelcodemigration,
      title={MigrationBench: Repository-Level Code Migration Benchmark from Java 8},
      author={Linbo Liu and Xinle Liu and Qiang Zhou and Lin Chen and Yihan Liu and Hoan Nguyen and Behrooz Omidvar-Tehrani and Xi Shen and Jun Huan and Omer Tripp and Anoop Deoras},
      year={2025},
      eprint={2505.09569},
      archivePrefix={arXiv},
      primaryClass={cs.SE},
      url={https://arxiv.org/abs/2505.09569},
}
```
