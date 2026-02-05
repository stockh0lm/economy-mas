# Prompt 8: Performance Optimization Profiling

## Context
We need a 20%+ performance improvement on a 1000-step simulation without changing outputs. Profiling and targeted optimizations are required.

---

## Task

### Step 1: Baseline Profile
Use `cProfile` to measure baseline performance for a 1000-step run. The current CLI does not expose `--steps`, so use a small runner script or set config via `SIM_CONFIG`. Ensure `config.yaml` has `simulation_steps: 1000` for this profile.

```bash
python -m cProfile -o /tmp/sim_profile.prof -c "import os; os.environ['SIM_CONFIG']='config.yaml'; import main; main.run_simulation(main._resolve_config_from_args_or_env())"
python -m pstats /tmp/sim_profile.prof
```

### Step 1b: Git Workflow (Required)

- Create a refactoring branch (example): `git checkout -b refactor/p08-performance`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

### Step 2: Identify Hotspots
Look for:
- Tight loops in metrics collection
- Excessive object creation
- Repeated computations per step

### Step 3: Optimize
Apply optimizations such as:
- Caching repeated calculations
- Reducing list/dict allocations
- Pre-allocating structures

### Step 4: Validate Behavior
Ensure the same outputs are produced for a fixed seed and that golden tests pass.

---

## Success Criteria
- ✅ 20%+ speed improvement on 1000-step run
- ✅ All golden tests still pass
- ✅ Outputs unchanged for fixed seed

---

## Files to Create/Modify
- Any performance hot-spot modules identified
- `doc/performance_report.md` (add before/after profiling results)

---

## Verification Commands
```bash
python -m cProfile -o /tmp/sim_profile_after.prof -c "import os; os.environ['SIM_CONFIG']='config.yaml'; import main; main.run_simulation(main._resolve_config_from_args_or_env())"
python -m pytest tests/test_m6_golden_run_snapshot.py -v
python -m pytest -q
```

---

## Expected Timeline
4-6 hours
