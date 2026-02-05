# Wirtschaftssimulation Refactoring Plan

## Executive Summary

This document outlines a comprehensive, step-by-step refactoring plan for the Wirtschaftssimulation codebase. Each step contains a detailed, independent prompt that can be executed to achieve a specific refactoring goal.

## Current State Analysis

### Project Overview
- **Total Lines of Code**: 19,284 lines across 94 Python files
- **Test Coverage**: 80% (222 passing tests, 2 failing, 1 xfailed, 1 xpassed)
- **Largest Files**:
  - `metrics.py`: 1,426 lines
  - `main.py`: 1,217 lines
  - `agents/household_agent.py`: 997 lines
  - `agents/company_agent.py`: 754 lines
  - `agents/retailer_agent.py`: 665 lines

### Dependency Stack
- Core: pydantic>=2.7.4, PyYAML>=6.0.2
- Data: pandas>=2.0.0, numpy>=1.24.0
- Viz: matplotlib>=3.7.0
- Testing: pytest>=7.0.0

### Current Issues
1. **Golden Test Failing**: `test_m6_golden_run_snapshot` fails with M1 proxy at 161.56 (expected 180-220)
2. **Test Coverage**: 80% is good but not excellent for critical economic simulation
3. **Large Files**: metrics.py (1426 lines) and main.py (1217 lines) are too large
4. **scripts/plot_metrics.py**: NOT included in test suite
5. **Missing Integration Tests**: Current tests are mostly unit tests, lack end-to-end validation

---

## Refactoring Strategy

### Core Principles
1. **Preserve Compatibility**: All refactoring must maintain backward compatibility
2. **Incremental Progress**: Each prompt stands alone and produces a verifiable result
3. **Test First**, Refactor Second: Ensure tests pass before and after each step
4. **Golden Test Protection**: Maintain golden test to catch regressions
5. **Include Visualization**: Ensure scripts/plot_metrics.py remains functional

---

## Refactoring Prompts

Each refactoring step is documented in the `refactoring_prompts/` directory as an independent, executable prompt. Execute them in numerical order (1-10):

1. **[Prompt 1](refactoring_prompts/01_golden_test_fix.md)**: Analyze and Fix Golden Test Failure
2. **[Prompt 2](refactoring_prompts/02_golden_test_suite.md)**: Create Enhanced Golden Test Suite
3. **[Prompt 3](refactoring_prompts/03_plot_metrics_tests.md)**: Integration Test for scripts/plot_metrics.py
4. **[Prompt 4](refactoring_prompts/04_extract_simulation_engine.md)**: Extract Simulation Loop into Dedicated Module
5. **[Prompt 5](refactoring_prompts/05_refactor_metrics.md)**: Refactor MetricsCollector into Sub-modules
6. **[Prompt 6](refactoring_prompts/06_extract_household_components.md)**: Extract Household Behavior into Smaller Components
7. **[Prompt 7](refactoring_prompts/07_increase_test_coverage.md)**: Increase Test Coverage to 90%+
8. **[Prompt 8](refactoring_prompts/08_performance_optimization.md)**: Performance Optimization Profiling
9. **[Prompt 9](refactoring_prompts/09_documentation_types.md)**: Documentation and Type Safety
10. **[Prompt 10](refactoring_prompts/10_comprehensive_regression.md)**: Comprehensive Regression Testing

---

## Execution Order

Execute prompts in numeric order (1-10). Each prompt is designed to be:
- **Independent**: Can be executed on its own
- **Verifiable**: Has clear success criteria
- **Testable**: Can be validated automatically
- **Safe**: Preserves backward compatibility

---

## Dual-Model Batch Execution Scheme (Devstral + GLM 4.7)

This plan is designed to run in batch mode without human interaction using two local LightLLM models that cross-check each step. The workflow uses one model as the implementer (Devstral) and the other as the reviewer (GLM 4.7).

### Roles
1. **Devstral (Implementer)**: Executes the prompt, edits code, runs tests.
2. **GLM 4.7 (Reviewer)**: Reviews the diff, validates correctness, reruns targeted tests, and proposes fixes if needed.

### Per-Prompt Gate
1. **Snapshot**: Save baseline state (git status, diff, and optional metrics snapshots).
2. **Implement**: Devstral applies changes and runs the verification commands in the prompt.
3. **Review**: GLM 4.7 reviews diffs against prompt requirements, checks for regressions or style issues, and runs the same or stricter verification commands.
4. **Repair Loop**: If GLM 4.7 finds issues, it prepares a patch or specific fixes; Devstral applies them and re-runs verification.
5. **Signoff**: Both models report pass/fail and attach logs.

### Git Discipline
1. **Branching**: Create a dedicated refactoring branch per prompt.
2. **Review**: Use `git diff --stat` and `git show` as mandatory review checkpoints.
3. **Commits**: Commit after each logical step with clear messages.
4. **Rollback**: Use `git restore <files>` (uncommitted) or `git revert <commit>` (committed). Avoid destructive resets.

### Batch Execution Harness (CLI-Agnostic)
Use a wrapper script that calls your CLI (opencode or Cline) in non-interactive mode. The exact flags vary by tool, so keep the structure but adapt the CLI arguments.

For a concrete example, see: `tools/run_refactor_batch.sh`

```bash
# Pseudocode template (adjust CLI flags for your tool)
PROMPTS=(doc/refactoring_prompts/01_golden_test_fix.md \
         doc/refactoring_prompts/02_golden_test_suite.md \
         doc/refactoring_prompts/03_plot_metrics_tests.md \
         doc/refactoring_prompts/04_extract_simulation_engine.md \
         doc/refactoring_prompts/05_refactor_metrics.md \
         doc/refactoring_prompts/06_extract_household_components.md \
         doc/refactoring_prompts/07_increase_test_coverage.md \
         doc/refactoring_prompts/08_performance_optimization.md \
         doc/refactoring_prompts/09_documentation_types.md \
         doc/refactoring_prompts/10_comprehensive_regression.md)

for PROMPT in "${PROMPTS[@]}"; do
  # Implementer pass
  cli run --model devstral --prompt-file "$PROMPT" --workspace /home/andreas/src/Wirtschaftssimulation --non-interactive \
    --log-file "doc/refactoring_reports/$(basename "$PROMPT" .md)_devstral.log"

  # Reviewer pass
  cli run --model glm-4.7 --prompt-file "$PROMPT" --workspace /home/andreas/src/Wirtschaftssimulation --non-interactive \
    --log-file "doc/refactoring_reports/$(basename "$PROMPT" .md)_glm47.log" \
    --review-diff "doc/refactoring_reports/$(basename "$PROMPT" .md)_diff.patch"
done
```

### Comparison and Quality Gates
- **Diff checks**: Capture `git diff` before/after each prompt and store it in `doc/refactoring_reports/`.
- **Regression checks**: Run the prompt-specific test commands and ensure no drop in coverage.
- **Style checks**: Run `python -m compileall .` and `pytest -q` at minimum; add linters if present.
- **Cross-validation**: Reviewer reruns the commands and confirms outputs match expected behavior.

---

## Batch Non-Interactive Safety Notes
1. **Preflight**: Every prompt must list any functions or files it assumes already exist.
2. **Baseline Capture**: For prompts that change behavior, store a snapshot of metrics CSVs for a fixed seed and compare after changes.
3. **Fail Fast**: If reviewer fails a gate, do not proceed to the next prompt.

---

---

## Appendix: Test Coverage by Module (Current)

| Module | Lines | Coverage | Missing |
|--------|-------|----------|---------|
| main.py | 624 | 80% | Progress bars, edge cases |
| metrics.py | 677 | 90% | Some calculations |
| agents/household_agent.py | 468 | 80% | Birth/split logic |
| agents/company_agent.py | 332 | 84% | Growth/split logic |
| agents/bank.py | 290 | 89% | Clearing, enforcement |
| agents/retailer_agent.py | 317 | 86% | Inventory valuations |
| agents/financial_manager.py | 130 | 69% | Loan cap enforcement |
| agents/savings_bank_agent.py | 157 | 73% | Deposit caps |

---

## Risk Mitigation

- **Golden Tests**: Protect core economic invariants
- **Baseline Snapshots**: Enable regression detection
- **Test Coverage**: 90%+ target catches regressions
- **Incremental PRs**: Each prompt produces a pull request-sized change
- **Backward Compatible**: No breaking API changes

## Completion Criteria

The refactoring is complete when:
1. ✅ All 10 prompts have been executed successfully
2. ✅ Test coverage >90%
3. ✅ All 250+ tests pass
4. ✅ Golden test suite passes all scenarios
5. ✅ Performance improved by 20%+ on 1000-step simulation
6. ✅ Documentation complete and up-to-date
7. ✅ Type safety with `mypy` passing
8. ✅ No regressions in economic behavior (within 5% tolerance)
9. ✅ Dual-model batch execution logs captured for each prompt
10. ✅ Each prompt has a reviewer signoff (GLM 4.7) and implementer signoff (Devstral)
