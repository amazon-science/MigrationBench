# Rosetta Skillweb with Codex

Rosetta passed 260 of 300 repositories in the MigrationBench selected maximal-migration track when evaluated with the official MigrationBench scorer, for an efficacy score of 86.67 percent.

## What Rosetta Does

Rosetta is a system-translation method delivered through a skill web. A top-level coding agent receives the ordinary migration request, automatically selects Rosetta, studies the source repository and target requirements, performs the migration, and proves the result against the requested build and behavior.

The working pattern is:

1. Understand the requested outcome.
2. Inspect the unchanged source repository.
3. Establish and observe the original build and behavior when possible.
4. Recover the behavior and compatibility requirements that must survive.
5. Translate the repository into the target environment.
6. Run a clean target build and verification sequence.
7. Compare the result with the source behavior and original request.
8. Repair grounded failures, then package the complete result.

## Run Configuration

- Dataset: `AmazonScience/migration-bench-java-selected`
- Dataset revision: `9ef0d9cefc1382fa5d639452a155b6137f55bbff`
- Repositories: 300
- Migration track: maximal migration
- Target: Java 17 with compatible dependency updates
- Agent: Codex
- Model: GPT-5.6-Sol
- Reasoning effort: xhigh
- Skillweb checkpoint: `compact004`
- Skillweb checkpoint manifest SHA-256: `0fe2f7bce4529a093e1433600a8f268034b5faa900377fb265b3884944c5f515`
- Rosetta skill SHA-256: `1eb350ece1c1d20401d3f37668be7dbd48dec18640047fb63a77f0d076dd39ca`
- Auto-planner skill SHA-256: `c7f3fa11c9707ed5bfd60d96b9fc9732cde05bb9e7fe2b5d4bd1ac855719f0a9`

The same frozen Skillweb checkpoint was used for the entire cohort. No Rosetta or Skillweb changes were made during the run.

## Result

- Passed: 260
- Failed: 40
- Official scorer efficacy reproduced locally: 86.67 percent
- Invalid scorer runs: 0

Every repository includes its submitted Git diff and one text-based JSON trajectory containing the original prompts and the agent's recorded migration steps.
