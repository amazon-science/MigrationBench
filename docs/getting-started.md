# Getting Started

MigrationBench supports two evaluation modes:

1. **Docker Mode (Recommended)**: Runs in isolated containers, no local Java/Maven needed
2. **Local Mode**: Runs directly on your machine with Java 17 and Maven 3.9.6

---

## Docker Mode (Recommended)

### Benefits

- ✅ No local Java/Maven installation needed
- ✅ Consistent environment across machines
- ✅ Parallel execution support
- ✅ Easy setup and onboarding

### Setup

**1. Install Docker**

Follow the official Docker installation guide for your platform:

- [macOS](https://docs.docker.com/desktop/install/mac-install/)
- [Windows](https://docs.docker.com/desktop/install/windows-install/)
- [Linux](https://docs.docker.com/engine/install/)

**2. Verify Docker**

```bash
docker --version
```

**3. Install MigrationBench**

```bash
git clone https://github.com/amazon-science/MigrationBench.git
cd MigrationBench

pip install -r requirements.txt -e .
```

That's it! The Docker image will be built automatically on first run.

### Single Repository Evaluation

```bash
GITHUB_URL=https://github.com/0xShamil/java-xid
GIT_DIFF_FILE=/path/to/java-xid.diff

python run_eval.py --github_url $GITHUB_URL --git_diff_filename $GIT_DIFF_FILE --use_docker
```

**Evaluate with migrated repository:**

```bash
MIGRATED_DIR=/path/to/migrated/repo
python run_eval.py --github_url $GITHUB_URL --migrated_root_dir $MIGRATED_DIR --use_docker
```

**Force rebuild Docker image:**

```bash
python run_eval.py --github_url $GITHUB_URL --git_diff_filename $GIT_DIFF_FILE --use_docker --build_docker_image
```

### Batch Evaluation

```bash
PREDICTIONS=predictions.json

# Sequential processing
python run_eval.py --predictions_filename $PREDICTIONS --use_docker

# Parallel processing (8 containers)
python run_eval.py --predictions_filename $PREDICTIONS --use_docker --max_workers 8
```

**Important:** File paths in the predictions file should be absolute paths on your host system.

---

## Local Mode

### Prerequisites

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
java --version  # Should show version 17
mvn --version   # Should show version 3.9.6
```

### Setup

```bash
git clone https://github.com/amazon-science/MigrationBench.git
cd MigrationBench

pip install -r requirements.txt -e .
```

### Single Repository Evaluation

```bash
GITHUB_URL=https://github.com/0xShamil/java-xid
GIT_DIFF_FILE=/path/to/java-xid.diff

python run_eval.py --github_url $GITHUB_URL --git_diff_filename $GIT_DIFF_FILE
```

### Batch Evaluation

```bash
PREDICTIONS=predictions.json

# Sequential processing
python run_eval.py --predictions_filename $PREDICTIONS

# Parallel processing (8 workers)
python run_eval.py --predictions_filename $PREDICTIONS --max_workers 8
```

---

## Predictions File Format

For batch evaluation, provide a JSON file with repository information. Each entry must include:

- `github_url`: Repository URL
- **One** of the following:
    - `git_diff_file`: Path to diff file
    - `git_diff`: Diff content as string
    - `migrated_root_dir`: Path to migrated repository

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

---

## Next Steps

- [View the Leaderboard](leaderboard.md) to see top-performing models
- [Explore Datasets](datasets.md) to understand available benchmarks
- Submit your results to appear on the leaderboard!
