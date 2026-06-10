<div class="leaderboard-page" markdown="1">

# 🏆 Leaderboard

This page tracks the performance of various models and approaches on the MigrationBench.

## Java 8 to Java 17 Migration

### Columns

- **Model**: The LLM model used (e.g., Claude Sonnet 4.5, Qwen3-32B)
- **Approach**: Migration methodology (e.g., Self-debugging, Agentic workflow, Static tool, Hybrid)
- **Agent Framework**: Framework/runtime used for agents (e.g., Strands Agent, Claude Agent SDK, LangGraph)
- **Minimal Migration**: Success rate for minimal migration
- **Maximal Migration**: Success rate for maximal migration
- **Avg # LLM Calls**: Average number of LLM API calls per repository

---

### 🥇 Max Migration - java-selected (300 repos)

| Rank | Model | Approach | Agent Framework | Max Migration | Avg # LLM Calls | Date |
|------|-------|----------|-----------------|-------------------|-----------------|------|
| 1 | Claude Sonnet 4.5 | Hybrid | Strands | 53.33 | 52.55 | 02/2026 |
| 2 | Claude Sonnet 4.5 | Agentic | Strands | 53.33 | 59.22 | 02/2026 |
| 3 | GLM-5 | Hybrid | Strands | 45.33 | 47.20 | 04/2026 |
| 4 | Qwen3-Coder-480B | Hybrid | Strands | 22.33 | 50.27 | 04/2026 |
| 5 | DeepSeek-V3.1  | Hybrid | Strands | 6.33 |  45.93 | 04/2026 |


---

### 🥇 Min Migration - java-selected (300 repos)

| Rank | Model | Approach | Agent Framework | Max Migration | Avg # LLM Calls | Date |
|------|-------|----------|-----------------|-------------------|-----------------|------|
| 1 | Claude Sonnet 4.5 | Agentic | Strands | 71.67 | 33.68 | 02/2026 |
| 2 | Qwen3-Coder-30B-A3B-Instruct | Agentic | Strands | 44.14 | - | 05/2026 |


---

## Submission Guidelines

For detailed submission instructions and templates, please visit:
[https://github.com/amazon-science/MigrationBench/tree/submission](https://github.com/amazon-science/MigrationBench/tree/submission)


---

## Migration Categories

### Minimal Migration
Focuses on essential code changes to make the repository compatible with the target Java version. Dependencies remain at their original versions unless strictly necessary for compatibility.

**Evaluation Criteria:**

- ✅ Repository builds successfully
- ✅ All tests pass
- ✅ Compiled classes match target Java version
- ✅ Test methods remain invariant
- ✅ Number of test cases is non-decreasing

### Maximal Migration
Includes both code migration and dependency updates to their latest major versions, providing a more comprehensive modernization.

**Evaluation Criteria:**

- ✅ All criteria from Minimal Migration
- ✅ Dependencies updated to latest major versions

---

</div>
