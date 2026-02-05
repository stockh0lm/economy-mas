# Prompt 10: Comprehensive Regression Testing

## Context
After refactoring, we need a final regression pass to ensure compatibility, performance, and correctness across the whole system.

---

## Task

### Step 1: Full Test Suite
Run all tests with verbosity and capture logs.

### Step 1b: Git Workflow (Required)

- Create a refactoring branch (example): `git checkout -b refactor/p10-regression`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

### Step 2: Golden Suite
Run the golden test suite and compare against baselines.

### Step 3: Performance Verification
Re-run 1000-step performance benchmark and ensure >=20% improvement remains.

### Step 4: Compatibility Checks
Ensure public APIs and scripts (especially `plot_metrics.py`) still work.

---

## Success Criteria
- ✅ All tests pass (250+ tests)
- ✅ Golden suite passes with no regressions
- ✅ Performance improvement persists
- ✅ `scripts/plot_metrics.py` runs successfully

---

## Files to Create/Modify
- `doc/final_regression_report.md`

---

## Verification Commands
```bash
python -m pytest -v
python -m pytest tests/test_m6_golden_run_snapshot.py -v
python scripts/plot_metrics.py --help
```

---

## Expected Timeline
2-3 hours
