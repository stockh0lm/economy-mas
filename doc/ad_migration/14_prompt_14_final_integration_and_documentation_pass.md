# Prompt 14: Final Integration and Documentation Pass
## Position in series
- Order: 15 of 15
- Depends on: Prompts 0-13 as applicable.
- Primary goal: Finalize runbooks, docs, output layout, and contributor workflow.
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

After enough infrastructure exists, need coherent docs and user workflows.
Documentation should let future contributors run AD diagnostics without reverse-engineering the architecture.

## Task

Create final documentation pass after main AD scaffolding lands.

### Step 1: update docs

Add or update:

- `doc/as_objectives.md`
- `doc/as_invariants.md`
- `doc/as_bug_patterns.md`
- `doc/as_hybrid_workflow.md`
- `doc/as_optimization_results.md` once results exist

### Step 2: add simple runbook

Create small runbook section showing typical sequence:

1. run baseline crash reproduction
2. analyze instability window
3. replay window
4. run reduced-core sensitivities
5. perturb top parameters
6. validate in full engine

### Step 3: ensure outputs are organized

Standardize output layout under `output/` for:

- traces
- sensitivity tables
- optimization logs
- hybrid reports
- flaw reports

## Deliverables

- coherent AD docs set
- standardized output layout
- concise user runbook

## Success Criteria

- contributor can follow docs and reproduce one AD-assisted diagnosis from scratch

## Verification Commands

```bash
python -m pytest -q
```

---
