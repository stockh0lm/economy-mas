# Prompt 9: Implement Sensitivity Report Tooling
## Position in series
- Order: 10 of 15
- Depends on: Prompt 7 and Prompt 8.
- Primary goal: Generate interpretable sensitivity reports from reduced core.
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

Once reduced core exists, gradients must become interpretable outputs for humans.
Need ranked sensitivity reports, phase attribution, and warnings about unreliable gradients.

## Task

Add sensitivity analysis tooling on top of reduced core and objective helpers.

### Step 1: create sensitivity runner

Add `scripts/run_ad_sensitivity.py`.
It should:

- load reduced scenario and parameter subset
- run reduced core
- compute gradients of chosen loss terms
- normalize results into elasticities where possible
- export machine-readable report

### Step 2: add structural warnings

Report when gradient reliability is suspect, for example:

- parameter at saturation boundary
- branch or clamp dominating local behavior
- topology-changing rule nearby but disabled in reduced mode
- finite-difference mismatch large

### Step 3: create plotting/report script

Add `scripts/plot_sensitivity_report.py`.
Generate at least:

- ranked parameter importance table
- per-loss sensitivity table
- optional bar plots / heatmaps

### Step 4: add tests

Basic tests should verify scripts run on tiny reduced scenario and export expected columns.

## Deliverables

- `scripts/run_ad_sensitivity.py`
- `scripts/plot_sensitivity_report.py`
- sensitivity output format
- basic script tests if test harness exists for scripts

## Success Criteria

- can generate ranked parameter table for one stable and one unstable scenario
- report explicitly states when gradients are trustworthy or not

## Verification Commands

```bash
python scripts/run_ad_sensitivity.py --help
python scripts/plot_sensitivity_report.py --help
```

---
