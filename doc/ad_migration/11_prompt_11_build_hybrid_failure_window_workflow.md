# Prompt 11: Build Hybrid Failure-Window Workflow
## Position in series
- Order: 12 of 15
- Depends on: Prompt 5, Prompt 6, Prompt 7, Prompt 9.
- Primary goal: Connect full-engine failure windows to local reduced-core sensitivities.
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

Most value likely comes from hybrid workflow, not full end-to-end differentiable engine.
Need connect full-engine crash traces to local reduced-core sensitivity analysis.

## Task

Create workflow that extracts local failure window from real engine and reconstructs reduced-core neighborhood around it.

### Step 1: implement window extraction

From full-engine traces and metrics, extract:

- pre-failure state window
- relevant agent subset or aggregates
- relevant events and precursor metrics

### Step 2: initialize reduced core from extracted window

Create adapter that builds reduced tensor state from extracted data.

### Step 3: compute local sensitivities

Run reduced core from extracted window and compute local sensitivities of chosen instability losses.

### Step 4: compare prediction with real-engine perturbation

Perturb top-ranked parameters slightly in full engine and compare whether direction of effect matches reduced-core sensitivity sign.

### Step 5: export hybrid report

Create machine-readable and human-readable outputs summarizing:

- first failure window
- dominant precursor signals
- top local sensitivities
- recommended next actions

## Deliverables

- local-window extractor
- full-engine to reduced-core adapter
- hybrid report workflow

## Success Criteria

- one real crash scenario can be analyzed end-to-end via hybrid path
- reduced-core sensitivities predict full-engine improvement direction better than chance for at least top candidates

## Verification Commands

```bash
python scripts/analyze_instability_window.py --help
python scripts/run_ad_sensitivity.py --help
```

---
