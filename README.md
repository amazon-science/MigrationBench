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
      <a href="https://github.com/amazon-science/SDFeedback">
        <img src="https://img.shields.io/badge/SDFeedback-000000?style=flatten&logo=github&logoColor=white" alt="SDFeedback (GitHub)">
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

<!-- toc -->

- [1. 📖 Overview](#1--overview)
  * [1.1 MigrationBench: Evaluation Framework](#11-migrationbench-evaluation-framework)
  * [1.2 SDFeedback: Migration with LLMs](#12-sdfeedback-migration-with-llms)
- [2. Datasets](#2--migration-benchmark-datasets)
- [3. Code Migration Evaluation](#3-code-migration-evaluation)
  * [3.1 Get Started](#31-get-started)
    + [3.1.1 Basic Setup](#311-basic-setup)
    + [3.1.2 Install MigrationBench](#312-install-migrationbench)
  * [3.1 Single Eval](#31-single-eval)
    + [3.1.1 Unsuccessful Eval](#311-unsuccessful-eval)
    + [3.1.2 Successful Eval](#312-successful-eval)
  * [3.2 Batch Eval](#32-batch-eval)
    + [3.2.1 Sample Predictions File](#321-sample-predictions-file)
    + [3.2.2 Run Batch Eval](#322-run-batch-eval)
- [4. 📚 Citation](#4--citation)

<!-- tocstop -->

## 1. 📖 Overview

### 1.1 [MigrationBench](https://github.com/amazon-science/MigrationBench): Evaluation Framework

[MigrationBench](https://github.com/amazon-science/MigrationBench)
(current Github package)
is the **evaluation framework** to assess code migration success,
from `java 8` to `17` or any other long-term support versions.

- [🤗 MigrationBench](https://huggingface.co/collections/AmazonScience/migrationbench-68125452fc21a4564b92b6c3)
is a large-scale code migration **benchmark dataset** at the **repository** level,
across multiple programming languages.
    * Current and initial release includes `java 8` repositories with the `maven` build system, as of May 2025.

The evaluation is an *approximation* for functional equivalence by checking the following:
1. The repo is able to build and pass all tests
1. Compiled classes' major versions are consistent with the target `java` version
   - `52` and `61` for `java 8` and `17` respectively
1. Test methods are invariant after code migration
1. Number of test cases is non-decreasing after code migration
1. The repo' dependency libraries match their *latest* major versions
   - Optional for **minimal migration** by definition, while
   - Required for **maximal migration**


### 1.2 [SDFeedback](https://github.com/amazon-science/SDFeeback): Migration with LLMs

[SDFeedback](https://github.com/amazon-science/SDFeeback)
is a separate Github package to conduct code migration with LLMs as a baseline solution,
and it relies on the current package for the final evaluation.
- It builds an ECR image and then
- It runs both code migration and final evaluation with Elastic Map Reduce (EMR) Serverless in a scalable way.


## 2. 🤗 MigrationBench Datasets

There are three datasets in [🤗 MigrationBench](https://huggingface.co/collections/AmazonScience/migrationbench-68125452fc21a4564b92b6c3):
- All repositories included in the datasets are available on GitHub, under the `MIT` or `Apache-2.0` license.

| Index | Dataset                                       | Size  | Notes                                                                                               |
|-------|-----------------------------------------------|-------|-----------------------------------------------------------------------------------------------------|
| 1     | [🤗 `AmazonScience/migration-bench-java-full`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-full)         | 5,102 | Each repo has a test directory or at least one test case                              |
| 2     | [🤗 `AmazonScience/migration-bench-java-selected`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-selected) |   300 | A **subset** of [🤗 `migration-bench-java-full`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-full)                                          |
| 3     | [🤗 `AmazonScience/migration-bench-java-utg`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-utg)           | 4,814 | The unit test generation (utg) dataset, **disjoint** with [🤗 `migration-bench-java-full`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-full)|


## 3. Code Migration Evaluation

We support running code migration evaluation for MigrationBench in two modes:
1. Single eval mode: For a single repository and
2. Batch eval mode: For multiple repositories


### 3.1 Get Started

To get started with code migration evaluate from `java 8` to `17`,
under either minimal migration or maximal migration
(See the [arXiv paper](https://arxiv.org/abs/2505.09569) for the definition):

#### 3.1.1 Basic Setup

Verify you have `java 17`, `maven 3.9.6` and `conda` (optional) locally:

```
# java
~ $ java --version
openjdk 17.0.15 2025-04-15 LTS
OpenJDK Runtime Environment Corretto-17.0.15.6.1 (build 17.0.15+6-LTS)
OpenJDK 64-Bit Server VM Corretto-17.0.15.6.1 (build 17.0.15+6-LTS, mixed mode, sharing)
```

```
# maven
~ $ mvn --version
Apache Maven 3.9.6 (bc0240f3c744dd6b6ec2920b3cd08dcc295161ae)
Maven home: /usr/local/bin/apache-maven-3.9.6
Java version: 17.0.15, vendor: Amazon.com Inc., runtime: /usr/lib/jvm/java-17-amazon-corretto.x86_64
Default locale: en_US, platform encoding: UTF-8
OS name: "linux", version: "5.10.236-208.928.amzn2int.x86_64", arch: "amd64", family: "unix"
```

```
# conda (Optional)
$ conda --version
conda 25.1.1
```

#### 3.1.2 Install [MigrationBench](https://github.com/amazon-science/MigrationBench)

```
git clone https://github.com/amazon-science/MigrationBench.git

cd MigrationBench

# They're optional if one doesn't need a conda env
# export CONDA_ENV=migration-bench
# conda create -n $CONDA_ENV python=3.9
# conda activate $CONDA_ENV

pip install -r requirements.txt -e .
```

Next,
to run a single job or a batch of jobs,
refer to file level comments in `src/migraiton_bench/run_eval.py`.


### 3.1 Single Eval

To run eval for a single repository,
provide the Github url,
a git diff file and optionally more flags:


#### 3.1.1 Unsuccessful Eval
```
# cd .../src/migraiton_bench

GITHUB_URL=https://github.com/0xShamil/java-xid
GIT_DIFF_FILE=...

python run_eval.py --github_url $GITHUB_URL --git_diff_filename $GIT_DIFF_FILE
```

One may see the following output,
as the git diff file is invalid:

```
...
[single] Migration success (count) `False`: `('https://github.com/0xShamil/java-xid', '...')`.
...
```

#### 3.1.2 Successful Eval

```
python run_eval.py --github_url $GITHUB_URL --require_compiled_java_major_version 52
```

By redirecting the code migration target to `java 8`
(through `require_compiled_java_major_version = 52`),
it should succeed without any code changes:

```
...
[single] Migration success (count) `True`: `('https://github.com/0xShamil/java-xid', None)`.
...
```


### 3.2 Batch Eval

To run eval for in batch mode for multiple repositories,
one can provide a `predictions` file in the `json` format.


#### 3.2.1 Sample Predictions File

For each repo,
one needs to provide the Github url and the git diff content or file:


```
$ cat predictions.json
[
  {
      "github_url": "https://github.com/0xShamil/java-xid",
      "git_diff_file": "eval/testdata/java-xid.diff"
  },
  {
      "github_url": "https://github.com/0xShamil/java-xid",
      "git_diff": ""
  }
]
```

#### 3.2.2 Run Batch Eval
```
# cd .../src/migraiton_bench

PREDICTIONS=predictions.json
python run_eval.py --predictions_filename $PREDICTIONS  # --require_compiled_java_major_version 52
```

One may see the following output,
without valid git diff content or file:

```
...
[batch] Final eval result: Success = 0 out of 2.
...
```


## 4. 📚 Citation

```bibtex
@misc{liu2025migrationbenchrepositorylevelcodemigration,
      title={MIGRATION-BENCH: Repository-Level Code Migration Benchmark from Java 8},
      author={Linbo Liu and Xinle Liu and Qiang Zhou and Lin Chen and Yihan Liu and Hoan Nguyen and Behrooz Omidvar-Tehrani and Xi Shen and Jun Huan and Omer Tripp and Anoop Deoras},
      year={2025},
      eprint={2505.09569},
      archivePrefix={arXiv},
      primaryClass={cs.SE},
      url={https://arxiv.org/abs/2505.09569},
}
```
