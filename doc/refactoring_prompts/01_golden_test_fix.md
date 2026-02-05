# Prompt 1: Analyze and Fix Golden Test Failure

## Context
The golden test `test_m6_golden_run_snapshot` is failing with M1 proxy at 161.56 (expected 180-220). This is a regression that happened recently.

---

## Task

### Step 1: Run the Golden Test and Capture Diagnostics
Run the golden test with full diagnostic output:

```bash
cd /home/andreas/src/Wirtschaftssimulation
python -m pytest tests/test_m6_golden_run_snapshot.py::test_golden_run_snapshot -xvs --tb=long
```

### Step 2: Examine Simulation Trajectory
Modify the test to print detailed metrics at each step to understand why M1 is lower than expected:

Key metrics to examine:
- M1 proxy over time (money supply)
- Retailer inventory values
- CC exposure (Kontokorrent credit)
- Number of agents (households, companies, retailers)
- Employment rate

### Step 3: Check for Parameter Changes
Examine if the regression is due to:
- **Changed parameter defaults in SimulationConfig**: Check `config.py` for recent changes
- **Modified agent behavior**: Check `agents/*.py` for behavior changes that reduce money creation
- **Timing issues**: Check if something in the simulation loop changed flow calculation
- **Recent refactors**: Check git history for last 5 commits affecting main.py, agents, or metrics

### Step 4: Investigate Git History
Check recent commits:

```bash
git log --oneline --all -10
git log -p --all main.py agents/ metrics.py | head -200
```

### Step 5: Determine Root Cause
After examining all evidence, determine if:
- **The code is correct** and the expected band (180-220) needs adjustment
- **There's a bug** introduced recently that needs fixing

### Step 6: Fix or Document
- If it's a bug: Fix the underlying issue causing the regression
- If the expectation is wrong: Update the test expectation with proper justification

### Step 7: Update Documentation
If adjusting expectations, document the economic reasoning in `doc/golden_run.md`

---

## Success Criteria

- ✅ Golden test passes with reasonable expectation bands
- ✅ M1 proxy falls within expected range for seeded 30-step run
- ✅ All other tests that previously passed still pass (222+ tests)
- ✅ If expectations changed, documentation updated with economic justification

---

## Files Potentially to Modify

Based on analysis results:
- `tests/test_m6_golden_run_snapshot.py` (if adjusting expectations)
- Any agent/metric file if bug is found
- `doc/golden_run.md` (if documenting expectation change)

---

## Git Workflow (Required)

- Create a refactoring branch (example): `git checkout -b refactor/p01-golden-test-fix`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

---

## Verification Commands

```bash
# Run the golden test
python -m pytest tests/test_m6_golden_run_snapshot.py -xvs

# Ensure no other tests broke
python -m pytest tests/test_metrics_global.py -xvs
python -m pytest tests/test_global_money_metrics.py -xvs

# Quick check of overall test suite
python -m pytest --tb=line -q
```

---

## Notes

- The golden test is critical: it's our primary regression detection for economic behavior
- M1 (money supply) is calculated as sum of sight balances across households, companies, retailers, and state
- Money in this system comes from:
  - **Money Creation**: Retailer Kontokorrent (CC) credit when purchasing goods from companies
  - **Money Destruction**: Retailer CC repayment from sales revenue
- Any change affecting the balance of these flows will affect M1

---

## Expected Timeline

1-2 hours for thorough analysis and fix
