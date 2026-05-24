# Prompt 8: Add Reduced-Core Parity Harness Against Real Engine
## Position in series
- Order: 9 of 15
- Depends on: Prompt 7 and Prompt 1.
- Primary goal: Compare reduced core against deterministic real-engine behavior.
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

Reduced AD core is only useful if tied back to real engine behavior.
Need parity harness for short horizon and reduced-mode scenario.

## Task

Create reduced-core parity workflow.

### Step 1: add deterministic reduced scenario config

Create one or more configs under `configs/` or `configs/ad_experiments/` that disable major discrete/stochastic mechanisms and keep system in reduced-core regime.

### Step 2: add adapter from engine state to AD state

Create helper that converts deterministic engine snapshot into reduced tensor state.

### Step 3: compare trajectories

For short horizons compare selected signals:

- retailer inventory trend
- company balance trend
- CC exposure trend
- aggregate household consumption
- price index

### Step 4: define tolerance rules

Exact equality not required.
Need documented tolerances and explanation for acceptable mismatch.

### Step 5: add tests

Add `tests/test_reduced_core_parity.py`.

## Deliverables

- reduced deterministic configs
- engine-to-AD adapter
- parity tests
- short report documenting mismatch sources

## Success Criteria

- reduced core roughly reproduces real deterministic engine in intended regime
- mismatch sources are explicit, not mysterious

## Verification Commands

```bash
python -m pytest tests/test_reduced_core_parity.py -v
```

---
