# MigrationBench Submission

This branch contains the prediction files, evaluation results, and migration trajectories of all leaderboard submissions. We follow a similar procedure to [SWE-bench](https://www.swebench.com/submit.html) with adaptations for code migration tasks. To submit your results, please follow the procedure below:

## Submission Procedure

### 1. Fork the Repository

Fork the MigrationBench repository to your GitHub account.

### 2. Clone the Repository

Clone your forked repository:

```sh
git clone https://github.com/YOUR_USERNAME/MigrationBench.git
cd MigrationBench
```

### 3. Checkout the Submission Branch

```sh
git checkout submission
```

### 4. Create Your Submission Folder

Copy the template folder and rename it with your submission date and agent name:

```sh
# Copy the template folder
cp -r evaluation/TEMPLATE_YYYYMMDD_agent_name evaluation/full/20260609_your_agent_name

# Or for selected dataset:
cp -r evaluation/TEMPLATE_YYYYMMDD_agent_name evaluation/selected/20260609_your_agent_name

# Navigate to your submission folder
cd evaluation/full/20260609_your_agent_name  # or evaluation/selected/...
```

**Format**: `YYYYMMDD_agent_name`
- Example: `20260609_javamigration_claude-opus48`
- `full` is for the full dataset ([🤗 `migration-bench-java-full`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-full) - 5,102 repositories)
- `selected` is for the selected dataset ([🤗 `migration-bench-java-selected`](https://huggingface.co/datasets/AmazonScience/migration-bench-java-selected) - 300 repositories)

### 5. Include Required Files

Within your submission folder, please include the following files:

#### Required Files

##### Predictions Files

MigrationBench supports two types of migrations:
- **Minimal Migration**: Only update Java version and minimal necessary changes
- **Maximal Migration**: Update Java version + all dependencies to latest versions

You can submit one or both migration types:

- **`min_migration_predictions.json`** 
- **`max_migration_predictions.json`** 

For the format of `predictions.json` file, we encourage either `git_diff` or `git_diff_file`:
```json
[
  {
    "github_url": "https://github.com/0xShamil/java-xid",
    "git_diff": "diff --git a/pom.xml b/pom.xml\nsome git diff content..."
  },
  {
    "github_url": "https://github.com/another/repository",
    "git_diff_file": "/path/to/another-repository.diff"
  }
]
```
If using `git_diff_file`, these diff files must be uploaded as well.

##### `metadata.yaml`
Metadata for how your result is shown on the website. Include the following fields:

```yaml
name: Your Agent Name
oss: true  # or false if closed-source
site: https://github.com/your-org/your-system  # Optional
approach: agentic  # e.g., agentic, hybrid, deterministic, etc.
max_migration_efficacy: XX.XX%  # Optional - efficacy on maximal migration
min_migration_efficacy: XX.XX%  # Optional - efficacy on minimal migration
description: Brief one-line description of your approach (optional)
model: Model name if applicable (e.g., "Claude Opus 4.5", "GPT-5")
logo:
  - https://link-to-your-logo.png  # optional
```


##### `trajs/`
Migration trajectories showing how your system solved each migration task:

The `trajs/` directory should be organized by migration type:

```
trajs/
├── min_migration/          # Trajectories for minimal migration
│   ├── owner__repo1.json
│   ├── owner__repo2.json
│   └── ...
└── max_migration/          # Trajectories for maximal migration
    ├── owner__repo1.json
    ├── owner__repo2.json
    └── ...
```

**Trajectory Requirements**:
- Submit one trajectory file per repository instance
- The trajectory should show all steps your system took during migration
- Include any reasoning, thoughts, or intermediate decisions made by your system
- File format can be any text-based format (`.md`, `.json`, `.yaml`, `.txt`)

**Note**: Only include trajectories for the migration type(s) you evaluated.

##### `README.md`
Optionally include information about your migration system in `README.md`:

- System architecture and approach
- Model(s) used
- Key techniques or strategies
- Any special preprocessing or postprocessing
- Computational resources used
- Any other relevant details

### 6. Create a Pull Request

Add your submission and create a pull request to the `submission` branch:

```sh
git add .
git commit -m "Add submission: YYYYMMDD_your_agent_name"
git push origin submission
```

## Citation

If you use MigrationBench in your research or are citing numbers from the leaderboard, please cite:

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
