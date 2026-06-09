# MigrationBench

<div class="badges">
  <a href="https://huggingface.co/collections/AmazonScience/migrationbench-68125452fc21a4564b92b6c3">
    <img src="https://img.shields.io/badge/-🤗 MigrationBench-4d5eff?style=flat&labelColor" alt="MigrationBench (Hugging Face)">
  </a>
  <a href="https://github.com/amazon-science/MigrationBench">
    <img src="https://img.shields.io/badge/MigrationBench-000000?style=flat&logo=github" alt="MigrationBench (GitHub)">
  </a>
  <a href="https://github.com/amazon-science/JavaMigration">
    <img src="https://img.shields.io/badge/JavaMigration-000000?style=flat&logo=github&logoColor=white" alt="JavaMigration (GitHub)">
  </a>
  <a href="https://arxiv.org/abs/2505.09569">
    <img src="https://img.shields.io/badge/arXiv-2505.09569-b31b1b.svg?style=flat" alt="MigrationBench (arXiv)">
  </a>
</div>

## 📰 News

- **[05/20/2025]** Docker evaluation mode is now supported! Run evaluations in isolated containers without local Java/Maven installation.
- **[05/16/2025]** Paper "[MigrationBench: Repository-Level Code Migration Benchmark from Java 8](https://arxiv.org/abs/2505.09569)" accepted to **Proceedings of the 32nd ACM SIGKDD Conference on Knowledge Discovery and Data Mining**! 🎉
- **[02/24/2025]** Training Java migration agents with RL is now supported by [Amazon Bedrock AgentCore](https://github.com/awslabs/agentcore-rl-toolkit/tree/main/examples/strands_migration_agent).

---

## Overview

**MigrationBench** is a large-scale benchmark for repository-level code migration from Java 8 to long-term support versions such as Java 17/21. It also provides an automated and robust framework for evaluating code migration success at the repository level.


## Evaluation Criteria

The evaluation approximates functional equivalence by checking:

1. ✅ Repository builds successfully
2. ✅ All tests pass
3. ✅ Compiled classes' major versions match target Java version (e.g. `61` for Java `17`)
4. ✅ Test methods remain invariant after migration
5. ✅ Number of test cases is non-decreasing
6. ✅ (Optional) Dependency libraries match their latest major versions

Checkout the [paper](https://arxiv.org/abs/2505.09569) for more details.

## Related Projects

- **[JavaMigration](https://github.com/amazon-science/JavaMigration)** - A package for conducting code migration with LLMs, including self-debugging style and LLM agents built on [Strands Agent](https://strandsagents.com/).

- **[AgentCore RL Toolkit (ART)](https://github.com/awslabs/agentcore-rl-toolkit)** - A toolkit using Amazon Bedrock AgentCore as a runtime for scalable long-horizon agentic RL workloads. MigrationBench is included as a [training example](https://github.com/awslabs/agentcore-rl-toolkit/tree/main/examples/strands_migration_agent). 

## Quick Links

- [View Leaderboard](leaderboard.md) - See top-performing models
- [Getting Started](getting-started.md) - Set up and run evaluations
- [Datasets](datasets.md) - Explore available benchmark datasets

## Citation

```bibtex
@article{liu2025migrationbench,
  title={MigrationBench: Repository-Level Code Migration Benchmark from Java 8},
  author={Liu, Linbo and Liu, Xinle and Zhou, Qiang and Chen, Lin and Liu, Yihan and Nguyen, Hoan and Omidvar-Tehrani, Behrooz and Shen, Xi and Huan, Jun and Tripp, Omer and others},
  journal={arXiv preprint arXiv:2505.09569},
  year={2025}
}
```

