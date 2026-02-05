# Prompt 4: Extract Simulation Loop into Dedicated Module

## Context
`main.py` contains the simulation loop inline, making it hard to test and extend. We need to extract a `SimulationEngine` that encapsulates run, step, and reset logic while preserving existing behavior.

---

## Task

### Step 1: Create Simulation Module Skeleton
Create `simulation/` package and add:
- `simulation/__init__.py`
- `simulation/engine.py`

Define a `SimulationEngine` class with:
- `__init__(self, config: SimulationConfig)`
- `run(self) -> dict[str, Any]` or the current return type of `run_simulation`
- `step(self) -> None`
- `reset(self) -> None`

### Step 1b: Git Workflow (Required)

- Create a refactoring branch (example): `git checkout -b refactor/p04-simulation-engine`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

---

### Step 2: Move Simulation Loop
Extract the loop from `main.py` into `SimulationEngine.run()` and `SimulationEngine.step()`.
Preserve:
- Exact `run_simulation(config)` return value (dict with agents)
- Side effects (logging, metrics export, randomness)
- Current seeding behavior (SIM_SEED / SIM_SEED_FROM_CONFIG)
- Performance characteristics (avoid extra copies)

### Step 3: Preserve Public API
Update `main.py` so `run_simulation(cfg)` constructs and delegates to `SimulationEngine`.
No call sites should change.

### Step 4: Add Minimal Engine Tests
Create `tests/test_simulation_engine.py`:
- Test that `SimulationEngine.run()` produces the same metrics export files as `run_simulation`
- Test that `step()` advances time by one step
- Test that `reset()` returns state to the initial configuration
Include a fixed-seed test that compares a few key metrics (from global_metrics CSV) before/after engine refactor.

---

## Success Criteria
- ✅ `run_simulation` behavior unchanged (same outputs for fixed seed)
- ✅ All existing tests pass
- ✅ Engine tests pass
- ✅ `main.py` reduced in size by removing loop implementation

---

## Files to Create/Modify
- `simulation/__init__.py`
- `simulation/engine.py`
- `main.py`
- `tests/test_simulation_engine.py`

---

## Verification Commands
```bash
python -m pytest tests/test_simulation_engine.py -v
python -m pytest tests/test_m6_golden_run_snapshot.py -v
python -m pytest -q
```

---

## Expected Timeline
2-3 hours
