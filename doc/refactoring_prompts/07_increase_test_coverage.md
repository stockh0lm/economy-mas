# Prompt 7: Increase Test Coverage to 90%+

## Context
Current coverage is ~80%. We need targeted tests for low-coverage modules and improve robustness without changing behavior.

---

## Task

### Step 1: Identify Gaps
Use coverage report to find low-coverage modules, especially:
- `agents/financial_manager.py` (69%)
- `agents/savings_bank_agent.py` (73%)

### Step 1b: Git Workflow (Required)

- Create a refactoring branch (example): `git checkout -b refactor/p07-coverage`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

## Controlled Diagnostics (Required)

- Use only existing tests and temporary files under `tmp_path` or `output/` with clear naming
- If a debug script is necessary, it must be named `debug_*.py` and deleted after use
- Do not add permanent debug tests
- Keep new tests deterministic via fixed seeds where applicable

### Step 2: Add Tests
Create targeted tests for:
- Loan cap enforcement
- Deposit cap enforcement
- Edge cases in credit clearing

### Step 3: Improve Plot Metrics Coverage
Ensure `scripts/plot_metrics.py` is covered via integration tests added in Prompt 3.

---

## Success Criteria
- ✅ Coverage >= 90%
- ✅ All tests pass
- ✅ No behavior changes

---

## Files to Create/Modify
- `tests/test_financial_manager.py`
- `tests/test_savings_bank_agent.py`
- Any existing test fixtures if needed

---

## Verification Commands
```bash
python -m pytest tests/test_financial_manager.py -v
python -m pytest tests/test_savings_bank_agent.py -v
python -m pytest --cov=. -q
```

---

## Expected Timeline
2-3 hours
