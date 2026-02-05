# Prompt 6: Extract Household Behavior into Smaller Components

## Context
`agents/household_agent.py` is ~1,000 lines and mixes consumption, savings, and demography logic. We need to decompose it into smaller modules while preserving behavior.

---

## Task

### Step 1: Create Household Package
Create `agents/household/` with:
- `agents/household/__init__.py`
- `agents/household/consumption.py`
- `agents/household/savings.py`
- `agents/household/demography.py`

### Step 1b: Git Workflow (Required)

- Create a refactoring branch (example): `git checkout -b refactor/p06-household-components`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

---

## Controlled Diagnostics (Required)

- Use only existing tests and temporary files under `tmp_path` or `output/` with clear naming
- If a debug script is necessary, it must be named `debug_*.py` and deleted after use
- Do not add permanent debug tests
- Validate behavior using fixed seeds and existing metrics CSVs

---

### Step 2: Move Logic
- **consumption.py**: consumption decision and purchase logic
- **savings.py**: savings rate, portfolio, deposits
- **demography.py**: births, deaths, household split logic

### Step 3: Preserve Public API
`HouseholdAgent` remains in `agents/household_agent.py` and delegates to components.
No external call sites or imports should change.

### Step 4: Add Component Tests
Create `tests/test_household_components.py`:
- Test that consumption totals match pre-refactor behavior for a fixed seed
- Test that savings evolution is unchanged
- Test that demography events are consistent

---

## Success Criteria
- ✅ All existing tests pass
- ✅ Household behavior unchanged in golden test
- ✅ `household_agent.py` reduced and delegates to components

---

## Files to Create/Modify
- `agents/household/__init__.py`
- `agents/household/consumption.py`
- `agents/household/savings.py`
- `agents/household/demography.py`
- `agents/household_agent.py`
- `tests/test_household_components.py`

---

## Verification Commands
```bash
python -m pytest tests/test_household_components.py -v
python -m pytest tests/test_m6_golden_run_snapshot.py -v
python -m pytest -q
```

---

## Expected Timeline
3-4 hours
