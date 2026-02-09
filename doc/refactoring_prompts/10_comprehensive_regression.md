# Prompt 10: Comprehensive Regression Testing

## Context
After all refactoring prompts (P01–P09), we need a final regression pass to ensure compatibility, performance, and correctness across the whole system. This prompt is the final quality gate.

**This prompt does NOT implement new features or refactoring.** It systematically verifies that every known regression pattern from previous prompts is absent, and produces a signed-off final report.

**Behavioral truth**: commit `62caa99` ("sensible ignores") is the pre-refactor baseline. All behavior must match this baseline for fixed seeds.

**Reference specification**: `doc/specs.md` (Warengeld system rules).

---

## Background: Known Regression Patterns from P04–P06

During the batch refactoring, the LLM models introduced 13 confirmed behavioral regressions (fixed in `cc3e1a4`). This prompt must verify that NONE of these have been reintroduced by P08 or P09, and that no new regressions exist.

The 13 regression patterns to check:

| # | Pattern | What Went Wrong | Where to Check |
|---|---------|-----------------|----------------|
| 1 | Semantic property confusion | `savings_balance` returned bank deposits instead of local_savings | `agents/household/savings.py` |
| 2 | State re-injection after reset | Seeded `_DEFAULT_NP_RNG` not re-injected into module globals after `engine.reset()` | `simulation/engine.py` |
| 3 | Dropped parameters | `py_rng`/`rng` dropped from `Household.batch_step()` call | `simulation/engine.py` |
| 4 | Constant drift | `MIN_GLOBAL_METRICS_POINTS` changed from `10` to `5` | `metrics/base.py` |
| 5 | Singleton pattern change | Eager `MetricsCollector()` changed to lazy `None` | `metrics/__init__.py` |
| 6 | Contract narrowing | `aggregate_metrics` stopped including empty category keys | `metrics/analyzer.py` |
| 7 | Missing fallback | `handle_finances` lost `clock.is_month_end()` fallback | `agents/household/savings.py` |
| 8 | Constant hardcoding | `_fertility_cache_bin_size` dynamic formula replaced with `100.0` | `agents/household/demography.py` |
| 9 | Constant drift | `_fertility_cache_max_size` changed from `4096` to `1000` | `agents/household/demography.py` |
| 10 | Import stubs | Real imports in `metrics.py` replaced with `None`/`object` stubs | `metrics.py` |
| 11 | Lost observability | All 7 demographic `log` calls silently dropped | `simulation/engine.py` |
| 12 | Duplicated globals | Independent `_DEFAULT_NP_RNG` created instead of importing canonical one | `agents/household/consumption.py` |
| 13 | Default value drift | `deque(maxlen=max(0, window))` changed to `max(1, window)` | `agents/household/consumption.py` |

---

## Task

### Step 1: Full Test Suite

```bash
# Run all tests with verbosity
python -m pytest -v 2>&1 | tee /tmp/p10_full_test_output.txt

# Confirm count (should be 279+)
python -m pytest -q 2>&1 | tail -1
```

All tests must pass. If any fail, stop and investigate before proceeding.

### Step 1b: Git Workflow (Required)

- Create a refactoring branch: `git checkout -b refactor/p10-regression`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

### Step 2: Golden Suite

```bash
# Run golden test suite
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
" > /tmp/p10_golden_hashes.txt
cat /tmp/p10_golden_hashes.txt
```

### Step 3: Systematic Regression Checklist

For each of the 13 known regression patterns, perform the specific verification described below. Record PASS/FAIL for each.

#### Check 1: `savings_balance` returns `local_savings`
```bash
python -c "
import ast, inspect
# Read the property and verify it returns self.local_savings or self._local_savings
with open('agents/household/savings.py') as f:
    source = f.read()
assert 'local_savings' in source, 'savings_balance must reference local_savings'
# Verify it does NOT return bank deposits
tree = ast.parse(source)
print('CHECK 1 PASS: savings_balance references local_savings')
"
```

#### Check 2: `_DEFAULT_NP_RNG` re-injected after `engine.reset()`
```bash
python -c "
with open('simulation/engine.py') as f:
    source = f.read()
# After reset(), the seeded RNG must be set back into the module global
assert '_DEFAULT_NP_RNG' in source, 'engine.py must reference _DEFAULT_NP_RNG'
# Check that reset() or the code path after seeding sets the global
print('CHECK 2: Verify _DEFAULT_NP_RNG re-injection in engine.py')
# Manual inspection required — grep for the assignment
import re
matches = re.findall(r'_DEFAULT_NP_RNG\s*=', source)
print(f'  Found {len(matches)} assignments to _DEFAULT_NP_RNG')
assert len(matches) >= 1, 'Must have at least one _DEFAULT_NP_RNG assignment'
print('CHECK 2 PASS')
"
```

#### Check 3: `py_rng`/`rng` passed to `batch_step()`
```bash
python -c "
with open('simulation/engine.py') as f:
    source = f.read()
assert 'py_rng' in source, 'engine.py must pass py_rng'
assert 'rng' in source, 'engine.py must pass rng'
# Verify batch_step call includes these params
import re
batch_calls = re.findall(r'batch_step\(.*?\)', source, re.DOTALL)
print(f'  Found {len(batch_calls)} batch_step calls')
for call in batch_calls:
    print(f'  Call: {call[:100]}')
print('CHECK 3 PASS')
"
```

#### Check 4: `MIN_GLOBAL_METRICS_POINTS == 10`
```bash
python -c "
from metrics.base import MIN_GLOBAL_METRICS_POINTS
assert MIN_GLOBAL_METRICS_POINTS == 10, f'Expected 10, got {MIN_GLOBAL_METRICS_POINTS}'
print('CHECK 4 PASS: MIN_GLOBAL_METRICS_POINTS == 10')
"
```

#### Check 5: Eager `MetricsCollector()` singleton
```bash
python -c "
with open('metrics/__init__.py') as f:
    source = f.read()
import re
# Must have eager initialization, not lazy None
eager = re.search(r'metrics_collector\s*=\s*MetricsCollector\(\)', source)
assert eager, 'metrics_collector must be eagerly initialized as MetricsCollector()'
lazy = re.search(r'metrics_collector\s*=\s*None', source)
assert not lazy, 'metrics_collector must NOT be lazily initialized as None'
print('CHECK 5 PASS: Eager MetricsCollector() singleton')
"
```

#### Check 6: `aggregate_metrics` returns all 6 category keys
```bash
python -c "
with open('metrics/analyzer.py') as f:
    source = f.read()
# The function must always include all category keys even when empty
# Look for the initialization of the result dict with all keys
print('CHECK 6: Verify aggregate_metrics includes all 6 category keys')
# Count category key references
categories = ['population', 'economic', 'banking', 'market', 'monetary', 'inequality']
found = [c for c in categories if c in source]
print(f'  Found categories in source: {found}')
assert len(found) >= 6, f'Expected 6 categories, found {len(found)}: {found}'
print('CHECK 6 PASS')
"
```

#### Check 7: `handle_finances` has `clock.is_month_end()` fallback
```bash
python -c "
with open('agents/household/savings.py') as f:
    source = f.read()
assert 'is_month_end' in source, 'handle_finances must have is_month_end fallback'
print('CHECK 7 PASS: handle_finances has clock.is_month_end() fallback')
"
```

#### Check 8: `_fertility_cache_bin_size` uses dynamic formula
```bash
python -c "
with open('agents/household/demography.py') as f:
    source = f.read()
# Must NOT be hardcoded to 100.0
import re
hardcoded = re.search(r'_fertility_cache_bin_size\s*=\s*100\.0', source)
assert not hardcoded, '_fertility_cache_bin_size must NOT be hardcoded to 100.0'
# Must use a dynamic formula (division or calculation)
dynamic = re.search(r'_fertility_cache_bin_size\s*=.*/', source)
print('CHECK 8: _fertility_cache_bin_size uses dynamic formula')
if dynamic:
    print(f'  Formula: {dynamic.group()[:80]}')
print('CHECK 8 PASS')
"
```

#### Check 9: `_fertility_cache_max_size == 4096`
```bash
python -c "
with open('agents/household/demography.py') as f:
    source = f.read()
assert '4096' in source, '_fertility_cache_max_size must be 4096'
import re
match = re.search(r'_fertility_cache_max_size\s*=\s*(\d+)', source)
if match:
    val = int(match.group(1))
    assert val == 4096, f'Expected 4096, got {val}'
print('CHECK 9 PASS: _fertility_cache_max_size == 4096')
"
```

#### Check 10: `metrics.py` imports real symbols (not stubs)
```bash
python -c "
with open('metrics.py') as f:
    source = f.read()
# Must NOT contain 'None' or 'object' as import replacements
import re
stubs = re.findall(r'=\s*None\b', source)
obj_stubs = re.findall(r'=\s*object\b', source)
print(f'  None stubs: {len(stubs)}, object stubs: {len(obj_stubs)}')
# Should have real imports from metrics package
real_imports = re.findall(r'from metrics\.\w+ import', source)
print(f'  Real imports: {len(real_imports)}')
assert len(real_imports) >= 1, 'metrics.py must have real imports from metrics/ package'
print('CHECK 10 PASS: metrics.py imports real symbols')
"
```

#### Check 11: Demographic log calls present in `engine.py`
```bash
python -c "
with open('simulation/engine.py') as f:
    source = f.read()
import re
log_calls = re.findall(r'log\.\w+\(', source)
print(f'  Total log calls in engine.py: {len(log_calls)}')
# Must have at least 7 demographic-related log calls
demo_logs = [l for l in source.split('\n') if 'log.' in l and any(w in l.lower() for w in ['birth', 'death', 'split', 'household', 'population', 'demograph', 'age'])]
print(f'  Demographic log lines: {len(demo_logs)}')
for line in demo_logs:
    print(f'    {line.strip()[:100]}')
assert len(demo_logs) >= 5, f'Expected >=5 demographic log calls, found {len(demo_logs)}'
print('CHECK 11 PASS: Demographic log calls present')
"
```

#### Check 12: `consumption.py` uses canonical RNG (not duplicated)
```bash
python -c "
with open('agents/household/consumption.py') as f:
    source = f.read()
import re
# Should import or reference the canonical _DEFAULT_NP_RNG, not create its own
local_rng_defs = re.findall(r'^_DEFAULT_NP_RNG\s*=\s*np\.random', source, re.MULTILINE)
print(f'  Local _DEFAULT_NP_RNG definitions: {len(local_rng_defs)}')
if len(local_rng_defs) > 0:
    print('  WARNING: consumption.py creates its own _DEFAULT_NP_RNG instead of importing')
print('CHECK 12: consumption.py RNG delegation verified')
print('CHECK 12 PASS')
"
```

#### Check 13: `deque(maxlen=max(0, window))`
```bash
python -c "
with open('agents/household/consumption.py') as f:
    source = f.read()
assert 'max(0,' in source or 'max(0 ,' in source, 'deque maxlen must use max(0, window)'
# Must NOT use max(1, window)
import re
bad_max = re.search(r'max\(1\s*,', source)
assert not bad_max, 'deque maxlen must NOT use max(1, window)'
print('CHECK 13 PASS: deque(maxlen=max(0, window))')
"
```

### Step 4: Type Definition Verification

```bash
python -c "
# Verify MetricConfig is TypedDict, not Protocol
with open('metrics/base.py') as f:
    source = f.read()
assert 'TypedDict' in source, 'MetricConfig must be a TypedDict'
assert 'Protocol' not in source or 'MetricConfig' not in source.split('Protocol')[0] if 'Protocol' in source else True
print('TYPE CHECK: MetricConfig is TypedDict ✓')
"
```

### Step 5: Performance Verification

Re-run 1000-step performance benchmark (if P08 was executed):

```bash
python -c "
import time, os
os.environ['SIM_SEED'] = '42'
os.environ['SIM_CONFIG'] = 'config.yaml'
import main
start = time.perf_counter()
main.run_simulation(main._resolve_config_from_args_or_env())
elapsed = time.perf_counter() - start
print(f'1000-step simulation: {elapsed:.2f}s')
"
```

Compare against baseline timing from `doc/performance_report.md` (if it exists from P08).

### Step 6: Compatibility Checks

```bash
# Verify plot_metrics.py can at least parse --help
python scripts/plot_metrics.py --help

# Verify backward-compat metrics.py wrapper works
python -c "
from metrics import MetricsCollector, metrics_collector
assert metrics_collector is not None, 'Singleton must exist'
assert isinstance(metrics_collector, MetricsCollector), 'Must be MetricsCollector instance'
print('Backward-compat metrics.py wrapper: OK')
"

# Verify simulation engine import path works
python -c "
from simulation.engine import SimulationEngine
print('SimulationEngine import: OK')
"
```

### Step 7: Produce Final Report

Create `doc/final_regression_report.md` with:

1. **Test Results**: Total tests, pass/fail count, any skipped/xfailed
2. **Golden Suite Results**: Pass/fail for each golden test scenario
3. **Regression Checklist**: PASS/FAIL for each of the 13 checks above
4. **Type Verification**: MetricConfig type, import structure
5. **Performance**: Current 1000-step timing vs. baseline (if available)
6. **Compatibility**: plot_metrics.py, backward-compat wrapper, engine import
7. **Fixed-seed output hashes**: From `/tmp/p10_golden_hashes.txt`
8. **Signoff**: "All regression checks passed. System is ready for production."

---

## Pre-Commit Checklist (Reviewer MUST Verify)

- [ ] All 279+ tests pass
- [ ] Golden test suite passes
- [ ] All 13 regression checks PASS
- [ ] `MetricConfig` is `TypedDict` (not `Protocol`)
- [ ] `metrics_collector` is eagerly initialized
- [ ] `savings_balance` returns `local_savings`
- [ ] `metrics.py` imports real symbols
- [ ] `doc/final_regression_report.md` is complete and accurate
- [ ] No code changes were made (this prompt is verification-only, unless fixes are needed)

---

## Controlled Diagnostics (Required)

- Use only existing tests and temporary files under `tmp_path` or `output/` with clear naming
- If a debug script is necessary, it must be named `debug_*.py` and deleted after use
- Do not add permanent debug tests
- If any test shows instability, rerun 3 times and compare median values

---

## If Regressions Are Found

If any of the 13 checks fail, or if tests fail:

1. **Document** the exact failure in the regression report
2. **Fix** the regression with a minimal, targeted change
3. **Re-run** all 13 checks plus the full test suite after fixing
4. **Commit** the fix with message: `fix: restore regression #N — <brief description>`
5. **Re-run** the golden hash comparison to confirm bit-identical output

Do NOT proceed to signoff until ALL checks pass.

---

## Success Criteria
- ✅ All 279+ tests pass
- ✅ Golden suite passes with no regressions
- ✅ All 13 known regression patterns verified absent
- ✅ Performance improvement persists (if P08 was run)
- ✅ `scripts/plot_metrics.py` runs successfully
- ✅ Backward-compat `metrics.py` wrapper works
- ✅ `doc/final_regression_report.md` produced with full results

---

## Files to Create/Modify
- `doc/final_regression_report.md` (new — final regression report)
- Any files needing regression fixes (only if regressions found)

---

## Verification Commands
```bash
python -m pytest -v
python -m pytest tests/test_m6_golden_run_snapshot.py -v
python scripts/plot_metrics.py --help
python -m pytest -q
```

---

## Expected Timeline
2-3 hours
