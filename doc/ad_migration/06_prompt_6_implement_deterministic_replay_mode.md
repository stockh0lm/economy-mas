# Prompt 6: Implement Deterministic Replay Mode
## Position in series
- Order: 7 of 15
- Depends on: Prompt 3 and Prompt 2. Prompt 5 preferred.
- Primary goal: Record and replay stochastic decisions in migrated scope.
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

Need fair A/B comparisons and local sensitivity studies.
Same sampled randomness must be replayable.
This is required even before Torch.

## Task

Implement deterministic replay mode for selected migrated paths.

### Step 1: define replay artifact

Create replay artifact format capturing enough stochastic decisions to reproduce run in migrated scope.
Can be JSONL, compact arrays, or structured binary later.
Initial version may capture sampled random draws and chosen indices.

### Step 2: add replay hooks

Allow engine to run in:

- normal stochastic mode
- record mode
- replay mode

### Step 3: limit scope if needed

First replay implementation only needs to support migrated high-value stochastic paths.
Document unsupported stochastic decisions explicitly.

### Step 4: add tests

Verify:

- record then replay reproduces same selected outputs
- replay mismatch is surfaced clearly

## Deliverables

- replay artifact format
- replay-capable engine hooks
- replay tests

## Success Criteria

- same crash window can be replayed exactly in migrated scenario
- replay provides stable base for parameter A/B and later local sensitivities

## Verification Commands

```bash
python -m pytest tests -q -k "replay or seed"
```

---
