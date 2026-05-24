# Prompt 5: Add Invariant Checker and Failure Precursors
## Position in series
- Order: 6 of 15
- Depends on: Prompt 1, Prompt 2, Prompt 4.
- Primary goal: Add invariants, precursor metrics, and first-failure analysis with explicit full-engine vs reduced-core scope.
## Shared constraints for all prompts
- Preserve public behavior unless prompt explicitly allows behavior change.
- Prefer smallest safe refactor.
- Keep current tests passing.
- Add tests for every new structural seam.
- Avoid hidden globals in newly touched paths.
- Do not merge policy changes into defaults unless evidence is strong.
- Separate correctness fixes from tuning changes from diagnostics.
- Use deterministic seeds for any new diagnostic or parity tests.
- Any new scripts must produce machine-readable outputs under `output/` or `tmp_path`.
- Any debug-only code must be removed before completion.
## Global success definition
AD migration is useful only if it produces these intermediate deliverables before full Torch rewrite:

- phase-local traces of simulation transitions
- deterministic replay of failure windows
- precursor metrics that identify first failure
- canonical transaction or event records for money-flow analysis
- reduced differentiable core with finite, interpretable gradients
- sensitivity reports ranking parameter importance
- at least one validated optimization result or structural flaw diagnosis

---

## Context

Need automatic detection of first failure window.
Aggregate macro metrics are too late.
Need precursor metrics and invariant checks per step or per phase.

Relevant files:

- `simulation/engine.py`
- `metrics/collector.py`
- `metrics/calculator.py`
- newly added trace modules

Important architecture note:

- full engine has real multi-region execution
- precursor metrics should preserve region-aware aggregation where region scope matters

Scope note:

Not every invariant has equal value in every mode.
Some checks are only meaningful in the full engine, while others should also run in reduced deterministic cores.

## Task

Add precursor metrics and invariant checks that make instability visible before collapse.

### Step 1: define precursor metrics

Add metrics for at least:

- company wage funding ratio
- count of companies with `last_wage_pay_ratio < 1`
- retailer CC headroom percentile or min
- retailer no-order streak length
- producer no-cash streak length
- issuance minus repayment gap
- inventory starvation indicator
- audit stress count
- unemployment jump indicator
- conservation residual

Classify each precursor or invariant as one of:

- `full_engine_only`
- `reduced_core_capable`
- `shared_but_low_signal_in_reduced_mode`

Where region scope matters, specify whether metric is:

- global aggregate
- per-region
- both

### Step 2: add invariant checker module

Create `simulation/invariant_checks.py`.
Checks should include:

- illegal money creation outside allowed issuance path
- negative inventory below tolerance
- inconsistent CC exposure updates
- production despite impossible funding state if such state occurs
- invalid repayment state transitions

Be explicit that some checks, such as `audit stress count`, may be low-signal or disabled in Prompt 7 reduced mode.
Do not treat absence of those signals in reduced mode as proof of correctness.

### Step 3: record violations in traces and metrics

Invariant violations should show up both in structured trace and in summary outputs.

### Step 4: create instability analyzer script

Add `scripts/analyze_instability_window.py`.
Script should:

- run or load simulation outputs
- find first step where chosen precursor or invariant threshold trips
- print concise diagnosis
- export machine-readable summary

### Step 5: add tests

Tests should verify:

- precursor metrics exist in outputs
- analyzer can run on small scenario
- invariant checker catches at least one synthetic bad state in unit test

Create dedicated test files with stable names, for example:

- `tests/test_invariant_checks.py`
- `tests/test_instability_analyzer.py`

## Deliverables

- `simulation/invariant_checks.py`
- precursor metric additions
- `scripts/analyze_instability_window.py`
- tests for invariant checks and analyzer

## Success Criteria

- repo can identify first failure window, not only end-state collapse
- precursor metrics are available for future AD loss terms

## Verification Commands

```bash
python -m pytest tests/test_invariant_checks.py -q
python -m pytest tests/test_instability_analyzer.py -q
python scripts/analyze_instability_window.py --help
```

---
