# Prompt 8: Performance Optimization Profiling

## Context
We need a 20%+ performance improvement on a 1000-step simulation **without changing any simulation outputs**. Profiling and targeted optimizations are required. The behavioral truth is commit `62caa99` — every fixed-seed output must remain bit-identical after optimization.

**Reference specification**: `doc/specs.md` (Warengeld system rules). No optimization may violate spec invariants.

---

## Behavioral Invariants (MUST NOT Change)

These were violated during previous refactoring prompts (P04–P06) and must be preserved here:

1. **Constants and defaults**: Do not change any magic number, default value, cache size, deque maxlen, or threshold. Examples of values that must stay exactly as-is:
   - `MIN_GLOBAL_METRICS_POINTS = 10` (not 5, not 20)
   - `_fertility_cache_max_size = 4096` (not 1000)
   - `deque(maxlen=max(0, window))` (not `max(1, window)`)
   - `_fertility_cache_bin_size` dynamic formula (not hardcoded `100.0`)

2. **RNG seeding chain**: The deterministic seeding path `SIM_SEED → engine.reset() → _DEFAULT_NP_RNG → batch_consume()` must remain intact. Do not duplicate RNG globals, skip re-injection after reset, or drop `py_rng`/`rng` parameters from call sites.

3. **Singleton patterns**: `metrics_collector = MetricsCollector()` is eagerly initialized at module level in `metrics/__init__.py`. Do not change to lazy initialization.

4. **Type definitions**: `MetricConfig` is a `TypedDict`, not a `Protocol`. `EconomicCycleSnapshot` is a concrete type, not `dict`. Do not weaken types.

5. **Log calls**: All `log.info()`, `log.debug()`, and `log.warning()` calls in `simulation/engine.py` (especially the 7 demographic log calls) must remain. Do not silently drop logging.

6. **Import structure**: `metrics.py` (root-level backward-compat wrapper) imports real symbols from `metrics/` subpackage. Do not replace with `None` or `object` stubs.

7. **Property semantics**: `savings_balance` returns `local_savings` (the local cash buffer), NOT `bank_deposits`. These are two distinct Warengeld accounting concepts.

---

## Task

### Step 1: Capture Golden Baseline (Before ANY Changes)

```bash
# Run golden test and full suite to confirm green baseline
python -m pytest tests/test_m6_golden_run_snapshot.py -v
python -m pytest -q

# Capture fixed-seed output snapshot
python -c "
import os, json, hashlib
os.environ['SIM_SEED'] = '42'
os.environ['SIM_CONFIG'] = 'config.yaml'
import main
result = main.run_simulation(main._resolve_config_from_args_or_env())
# Hash the metrics output for comparison
import glob
for f in sorted(glob.glob('output/*.csv')):
    h = hashlib.sha256(open(f,'rb').read()).hexdigest()
    print(f'{f}: {h}')
" > /tmp/golden_hashes_before.txt
cat /tmp/golden_hashes_before.txt
```

### Step 1b: Git Workflow (Required)

- Create a refactoring branch: `git checkout -b refactor/p08-performance`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

### Step 2: Profile Baseline

```bash
python -m cProfile -o /tmp/sim_profile_before.prof -c "
import os
os.environ['SIM_SEED'] = '42'
os.environ['SIM_CONFIG'] = 'config.yaml'
import main
main.run_simulation(main._resolve_config_from_args_or_env())
"

python -c "
import pstats
p = pstats.Stats('/tmp/sim_profile_before.prof')
p.sort_stats('cumulative')
p.print_stats(30)
"
```

Record the total runtime and top-30 functions in `doc/performance_report.md`.

### Step 3: Identify Hotspots

Look for:
- Tight loops in metrics collection (`metrics/collector.py`, `metrics/calculator.py`)
- Excessive object creation per step
- Repeated computations that can be cached
- Unnecessary list/dict copies
- String formatting in hot paths (e.g., f-strings in tight loops)
- Redundant attribute lookups in inner loops

### Step 4: Optimize (Behavior-Preserving ONLY)

Apply optimizations such as:
- Caching repeated calculations (use `functools.lru_cache` or manual caching)
- Reducing list/dict allocations in hot paths
- Pre-allocating structures where sizes are known
- Moving invariant computations outside loops
- Using `__slots__` on frequently-instantiated classes
- Replacing `.append()` loops with list comprehensions where safe

**FORBIDDEN optimizations** (these caused regressions in P04–P06):
- Do NOT change any constant, default value, or threshold
- Do NOT change function signatures (adding/removing parameters)
- Do NOT change the order of operations in simulation steps
- Do NOT change singleton initialization patterns
- Do NOT change type definitions (TypedDict, dataclass, etc.)
- Do NOT remove or reduce logging calls
- Do NOT change import structure or replace real imports with stubs
- Do NOT introduce new module-level globals that shadow existing ones
- Do NOT change RNG usage patterns or seeding behavior

### Step 5: Validate Behavior Preservation

```bash
# 1. All tests must pass
python -m pytest -q

# 2. Golden test must pass
python -m pytest tests/test_m6_golden_run_snapshot.py -v

# 3. Fixed-seed output must be bit-identical
python -c "
import os, json, hashlib
os.environ['SIM_SEED'] = '42'
os.environ['SIM_CONFIG'] = 'config.yaml'
import main
result = main.run_simulation(main._resolve_config_from_args_or_env())
import glob
for f in sorted(glob.glob('output/*.csv')):
    h = hashlib.sha256(open(f,'rb').read()).hexdigest()
    print(f'{f}: {h}')
" > /tmp/golden_hashes_after.txt

# 4. Compare hashes — must be identical
diff /tmp/golden_hashes_before.txt /tmp/golden_hashes_after.txt
```

If `diff` shows ANY difference, the optimization changed behavior. Revert and try a different approach.

### Step 6: Profile After and Measure Improvement

```bash
python -m cProfile -o /tmp/sim_profile_after.prof -c "
import os
os.environ['SIM_SEED'] = '42'
os.environ['SIM_CONFIG'] = 'config.yaml'
import main
main.run_simulation(main._resolve_config_from_args_or_env())
"

python -c "
import pstats
p = pstats.Stats('/tmp/sim_profile_after.prof')
p.sort_stats('cumulative')
p.print_stats(30)
"
```

Update `doc/performance_report.md` with before/after comparison.

---

## Pre-Commit Checklist (Reviewer MUST Verify)

Before approving any commit, the reviewer must confirm:

- [ ] `diff /tmp/golden_hashes_before.txt /tmp/golden_hashes_after.txt` produces no output
- [ ] `python -m pytest -q` shows all 279+ tests passing
- [ ] `python -m pytest tests/test_m6_golden_run_snapshot.py -v` passes
- [ ] `git diff` shows NO changes to any constant, default value, or threshold
- [ ] `git diff` shows NO changes to function signatures
- [ ] `git diff` shows NO removed `log.*()` calls
- [ ] `git diff` shows NO changes to type definitions (TypedDict, Protocol, dataclass)
- [ ] `git diff` shows NO changes to import structure in `metrics.py` or `metrics/__init__.py`
- [ ] `git diff` shows NO new module-level `_DEFAULT_*` globals
- [ ] Performance improvement is ≥20% (document exact numbers)

---

## Controlled Diagnostics (Required)

- Use only existing profiling tools and temporary files under `/tmp`
- If a debug script is necessary, it must be named `debug_*.py` and deleted after use
- Do not add permanent debug tests
- Use fixed seed `42` for all before/after comparisons

---

## Success Criteria
- ✅ 20%+ speed improvement on 1000-step run (measured with `cProfile`)
- ✅ All 279+ tests pass
- ✅ Golden test suite passes with no regressions
- ✅ Fixed-seed output CSV hashes are bit-identical before and after
- ✅ No behavioral invariants violated (see list above)

---

## Files to Create/Modify
- Performance hot-spot modules identified by profiling (likely `metrics/collector.py`, `metrics/calculator.py`, `simulation/engine.py`)
- `doc/performance_report.md` (before/after profiling results with exact timings)

---

## Verification Commands
```bash
python -m pytest -q
python -m pytest tests/test_m6_golden_run_snapshot.py -v
diff /tmp/golden_hashes_before.txt /tmp/golden_hashes_after.txt
```

---

## Expected Timeline
4-6 hours
