# Prompt 13: Extend Registry and Objectives to Difficult Parameters
## Position in series
- Order: 14 of 15
- Depends on: Prompt 0 and Prompt 9.
- Primary goal: Expand registry to difficult and partially differentiable parameters.
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

After core loop works, next challenge is broader parameter space including piecewise, stochastic, and near-discrete parameters.
Need disciplined expansion, not uncontrolled tuning mess.

## Task

Extend registry and objective framework to difficult parameter classes.

### Include categories

- demography sensitivities
- founding and merger rates
- audit cadence and thresholds
- liquidation rules
- dynamic pricing clamps

### Requirements

For each new parameter classify whether recommended method is:

- direct autograd in reduced core
- replay-based finite difference
- surrogate model only
- do not optimize automatically

### Add documentation

Update `doc/as_objectives.md` and registry comments with rationale.

## Deliverables

- expanded registry
- method recommendation per parameter
- tests for registry consistency

## Success Criteria

- repo distinguishes trainable parameters from inspect-only parameters explicitly

## Verification Commands

```bash
python -m pytest tests -q -k "ad_registry"
```

---
