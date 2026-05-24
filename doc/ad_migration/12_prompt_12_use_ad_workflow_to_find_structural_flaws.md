# Prompt 12: Use AD Workflow to Find Structural Flaws
## Position in series
- Order: 13 of 15
- Depends on: Prompt 5, Prompt 9, Prompt 11.
- Primary goal: Turn AD outputs plus traces into structural flaw hypotheses.
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

End goal is not only parameter tuning.
Need AD-assisted debugging of algorithmic flaws.
This prompt converts earlier infrastructure into bug-finding workflow.

## Task

Build script and report format that turns gradients + invariants + traces into structural flaw hypotheses.

### Step 1: define flaw heuristics

Create `doc/as_bug_patterns.md` and code-side heuristics.
Examples:

- gradient mass concentrated on workaround parameter instead of causal mechanism
- sign flips across nearly identical seeds
- zero gradient despite large macro effect because hard branch masks mechanism
- invariant residual precedes crash consistently
- tiny perturbations trigger insolvency cliffs or topology cliffs

### Step 2: implement flaw finder

Add `scripts/find_structural_flaws.py`.
It should combine:

- precursor metrics
- invariants
- trace events
- reduced-core sensitivities
- reliability warnings

Output should rank likely structural issues by evidence strength.

### Step 3: tie findings to source locations

Where possible, map finding classes to files and symbols, for example:

- `SimulationEngine._step_retail_restocking`
- `WarengeldBank.finance_goods_purchase`
- `Company.pay_wages`
- `RetailerAgent.restock_goods`

### Step 4: require regression outcome

For any verified flaw, add one of:

- regression test
- invariant check
- trace assertion

## Deliverables

- `doc/as_bug_patterns.md`
- `scripts/find_structural_flaws.py`
- workflow for turning finding into regression guardrail

## Success Criteria

- tool can produce nontrivial ranked flaw hypotheses on crash scenario
- at least one finding can be confirmed and guarded by test or invariant

## Verification Commands

```bash
python scripts/find_structural_flaws.py --help
```

---
