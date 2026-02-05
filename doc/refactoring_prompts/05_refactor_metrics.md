# Prompt 5: Refactor MetricsCollector into Sub-modules

## Context
`metrics.py` is 1,426 lines and mixes collection, calculation, analysis, and export logic. We need to split it into focused modules without breaking public interfaces.

---

## Task

### Step 1: Create Metrics Package Structure
Create `metrics/` package with:
- `metrics/__init__.py`
- `metrics/collector.py`
- `metrics/calculator.py`
- `metrics/analyzer.py`
- `metrics/exporter.py`

### Step 1b: Git Workflow (Required)

- Create a refactoring branch (example): `git checkout -b refactor/p05-metrics-split`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

---

### Step 2: Move Responsibilities
- **collector.py**: MetricsCollector class, data gathering logic
- **calculator.py**: metric calculations (global money, price indexes)
- **analyzer.py**: analysis functions used by plots or tests
- **exporter.py**: CSV and pickle export, file naming

### Step 3: Preserve Public API
Keep original imports working via re-exports in `metrics/__init__.py` and thin wrappers in `metrics.py`.
Do not change existing import paths in tests or runtime code. Avoid circular imports by keeping shared constants/types in a small internal module if needed.

### Step 4: Add Targeted Tests
Create tests to ensure:
- Exported file formats and names unchanged
- Key calculations return identical results for a fixed simulation seed

---

## Success Criteria
- ✅ All existing tests pass
- ✅ Metrics outputs unchanged for a fixed seed
- ✅ metrics.py reduced to thin compatibility layer
- ✅ No external import paths broken

---

## Files to Create/Modify
- `metrics/__init__.py`
- `metrics/collector.py`
- `metrics/calculator.py`
- `metrics/analyzer.py`
- `metrics/exporter.py`
- `metrics.py`
- `tests/test_metrics_refactor.py`

---

## Verification Commands
```bash
python -m pytest tests/test_metrics_refactor.py -v
python -m pytest tests/test_metrics_global.py -v
python -m pytest -q
```

---

## Expected Timeline
3-4 hours
