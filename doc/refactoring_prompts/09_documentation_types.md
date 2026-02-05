# Prompt 9: Documentation and Type Safety

## Context
Public APIs lack consistent docstrings and type hints. We need to improve documentation and introduce type safety without changing behavior.

---

## Task

### Step 1: Add Docstrings
Add docstrings to all public classes and methods, focusing on:
- `main.py`
- `metrics.py` and new `metrics/` modules
- `agents/` classes

### Step 1b: Git Workflow (Required)

- Create a refactoring branch (example): `git checkout -b refactor/p09-docs-types`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

### Step 2: Add Type Hints
Introduce type hints for public functions and class methods.
Use standard typing: `Optional`, `Mapping`, `Sequence`, `list`, `dict`.

### Step 3: Run Type Checker
If `mypy` config exists, run it. Otherwise, ensure `python -m compileall .` passes. Do not introduce mypy configuration unless explicitly required.

---

## Success Criteria
- ✅ Docstrings added to public APIs
- ✅ Type hints added without runtime changes
- ✅ All tests still pass

---

## Files to Create/Modify
- `main.py`
- `metrics.py` and `metrics/*.py`
- `agents/*.py`
- Any new typing support files

---

## Verification Commands
```bash
python -m compileall .
python -m pytest -q
```

---

## Expected Timeline
3-4 hours
