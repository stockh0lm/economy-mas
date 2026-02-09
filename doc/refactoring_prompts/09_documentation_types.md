# Prompt 9: Documentation and Type Safety

## Context
Public APIs lack consistent docstrings and type hints. We need to improve documentation and introduce type safety **without changing any runtime behavior**. This prompt is documentation-only and type-annotation-only — no logic changes, no refactoring, no performance changes.

**Reference specification**: `doc/specs.md` (Warengeld system rules). Docstrings must accurately describe the Warengeld semantics, not generic descriptions.

**Behavioral truth**: commit `62caa99`. Fixed-seed outputs must remain bit-identical after this prompt.

---

## Behavioral Invariants (MUST NOT Change)

Previous prompts (P04–P06) introduced regressions by making "innocent" changes alongside documentation. This prompt MUST be pure annotation — no behavioral changes at all.

### Forbidden Transformations

1. **Do NOT change any runtime code**: No function body changes, no reordering, no "cleanup" of logic. Only add docstrings and type annotations.

2. **Do NOT change type definitions that affect runtime**:
   - `MetricConfig` MUST remain a `TypedDict` (not `Protocol`, not `dataclass`)
   - `EconomicCycleSnapshot` must keep its current concrete type
   - Do not change `class X(TypedDict)` to `class X(Protocol)` — this changes structural typing behavior

3. **Do NOT change default values or constants**: Even in type annotations, do not add defaults that change behavior. `def f(x: int = 10)` must keep `= 10` if it was `= 10`.

4. **Do NOT change import structure**: Do not reorganize imports, add new re-exports, or change `from X import Y` to `import X`. Import reordering by tools like `isort` is fine only if it does not change resolution order.

5. **Do NOT add `__all__` exports** that differ from current implicit exports. If `__all__` does not exist, do not add it.

6. **Do NOT convert between annotation styles**: If a module uses `# type: ignore`, keep it. If a module uses `Optional[X]`, prefer `Optional[X]` over `X | None` for consistency within that file.

7. **Property semantics in docstrings**: Document `savings_balance` as "local cash buffer (Bargeldpuffer)" — NOT as "bank deposits". These are distinct Warengeld concepts per `doc/specs.md`.

---

## Task

### Step 1: Capture Golden Baseline (Before ANY Changes)

```bash
# Confirm green baseline
python -m pytest -q
python -m pytest tests/test_m6_golden_run_snapshot.py -v

# Capture fixed-seed output hashes
python -c "
import os, hashlib, glob
os.environ['SIM_SEED'] = '42'
os.environ['SIM_CONFIG'] = 'config.yaml'
import main
main.run_simulation(main._resolve_config_from_args_or_env())
for f in sorted(glob.glob('output/*.csv')):
    h = hashlib.sha256(open(f,'rb').read()).hexdigest()
    print(f'{f}: {h}')
" > /tmp/golden_hashes_before_p09.txt
```

### Step 1b: Git Workflow (Required)

- Create a refactoring branch: `git checkout -b refactor/p09-docs-types`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

### Step 2: Add Docstrings to Public APIs

Add docstrings to all public classes and methods in these files (in this order):

1. **`simulation/engine.py`** — `SimulationEngine`, `run()`, `step()`, `reset()`. Document the RNG seeding chain: `SIM_SEED → reset() → _DEFAULT_NP_RNG injection → batch_consume()`.
2. **`metrics/__init__.py`** — Document the eager singleton `metrics_collector = MetricsCollector()` and why it must be eagerly initialized.
3. **`metrics/base.py`** — Document `MetricConfig` (TypedDict), `MIN_GLOBAL_METRICS_POINTS = 10`.
4. **`metrics/collector.py`** — `MetricsCollector` class and key methods.
5. **`metrics/calculator.py`** — Calculation functions.
6. **`metrics/analyzer.py`** — `aggregate_metrics` (document that it ALWAYS includes all 6 category keys, even if empty).
7. **`metrics/exporter.py`** — CSV export functions.
8. **`agents/household_agent.py`** — `Household` class, `batch_step()`, `step()`. Document the `py_rng`/`rng`/`clock` parameters.
9. **`agents/household/consumption.py`** — `ConsumptionComponent`, `batch_consume()`. Document that it uses the canonical `_DEFAULT_NP_RNG` from `household_agent` (not a local copy).
10. **`agents/household/savings.py`** — `SavingsComponent`, `savings_balance` (= local_savings, NOT bank_deposits), `handle_finances` (falls back to `clock.is_month_end()`).
11. **`agents/household/demography.py`** — `DemographyComponent`, fertility cache (dynamic `_fertility_cache_bin_size`, max size `4096`).
12. **`main.py`** — `run_simulation()`, `_resolve_config_from_args_or_env()`.
13. **`metrics.py`** — Document as backward-compatibility wrapper that re-exports real symbols.

Docstring style: Use Google-style docstrings (Args/Returns/Raises sections). Write docstrings in English. For Warengeld-specific concepts, include the German term in parentheses (e.g., "local cash buffer (Bargeldpuffer)").

### Step 3: Add Type Hints

Add type annotations to public function signatures that lack them. Rules:

- Use `from __future__ import annotations` at the top of each modified file (if not already present) for forward reference support.
- Use standard typing: `Optional`, `Mapping`, `Sequence`, `list`, `dict`, `tuple`.
- For complex return types, prefer existing type aliases or TypedDicts already defined in the codebase.
- Do NOT introduce new TypedDicts, Protocols, or dataclasses. Only annotate with existing types.
- Do NOT change any function's actual return value or parameter default — only add annotations.
- If a function currently returns an untyped `dict`, annotate it as `dict[str, Any]` — do NOT create a new TypedDict for it.

### Step 4: Verify No Behavioral Change

```bash
# 1. Compile check
python -m compileall .

# 2. All tests must pass
python -m pytest -q

# 3. Golden test
python -m pytest tests/test_m6_golden_run_snapshot.py -v

# 4. Fixed-seed output must be bit-identical
python -c "
import os, hashlib, glob
os.environ['SIM_SEED'] = '42'
os.environ['SIM_CONFIG'] = 'config.yaml'
import main
main.run_simulation(main._resolve_config_from_args_or_env())
for f in sorted(glob.glob('output/*.csv')):
    h = hashlib.sha256(open(f,'rb').read()).hexdigest()
    print(f'{f}: {h}')
" > /tmp/golden_hashes_after_p09.txt

diff /tmp/golden_hashes_before_p09.txt /tmp/golden_hashes_after_p09.txt
```

If `diff` shows ANY difference, a "documentation-only" change introduced a behavioral regression. Revert and investigate.

---

## Pre-Commit Checklist (Reviewer MUST Verify)

Before approving any commit, the reviewer must confirm:

- [ ] `diff /tmp/golden_hashes_before_p09.txt /tmp/golden_hashes_after_p09.txt` produces no output
- [ ] `python -m pytest -q` shows all 279+ tests passing
- [ ] `git diff` shows ONLY additions of docstrings and type annotations — no logic changes
- [ ] `git diff` contains no removed lines of code (only added lines)
- [ ] `git diff` shows NO changes to any constant, default value, or threshold
- [ ] `git diff` shows NO changes to `TypedDict` → `Protocol` or similar type definition changes
- [ ] `git diff` shows NO changes to import structure (beyond `from __future__ import annotations`)
- [ ] `git diff` shows NO changes to singleton initialization in `metrics/__init__.py`
- [ ] Docstrings for `savings_balance` describe it as "local cash buffer", not "bank deposits"
- [ ] Docstrings for `aggregate_metrics` mention it always returns all 6 category keys
- [ ] `python -m compileall .` passes (no syntax errors in annotations)

---

## Controlled Diagnostics (Required)

- Use only existing tests and temporary files under `tmp_path` or `output/` with clear naming
- If a debug script is necessary, it must be named `debug_*.py` and deleted after use
- Do not add permanent debug tests

---

## Success Criteria
- ✅ Docstrings added to all public APIs in the 13 files listed above
- ✅ Type hints added to public function signatures without runtime changes
- ✅ All 279+ tests pass
- ✅ Golden test passes
- ✅ Fixed-seed output hashes are bit-identical before and after
- ✅ `python -m compileall .` passes
- ✅ `git diff` shows zero logic changes (docstrings and annotations only)

---

## Files to Modify (NO new files)
- `simulation/engine.py`
- `metrics/__init__.py`
- `metrics/base.py`
- `metrics/collector.py`
- `metrics/calculator.py`
- `metrics/analyzer.py`
- `metrics/exporter.py`
- `agents/household_agent.py`
- `agents/household/consumption.py`
- `agents/household/savings.py`
- `agents/household/demography.py`
- `main.py`
- `metrics.py`

---

## Verification Commands
```bash
python -m compileall .
python -m pytest -q
python -m pytest tests/test_m6_golden_run_snapshot.py -v
diff /tmp/golden_hashes_before_p09.txt /tmp/golden_hashes_after_p09.txt
```

---

## Expected Timeline
3-4 hours
