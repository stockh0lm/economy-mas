# Prompt 3: Replace Hidden Global RNG Mutation with Explicit Injection
## Position in series
- Order: 4 of 15
- Depends on: Prompt 0 preferred. Execute before or together with Prompt 1.
- Primary goal: Make RNG explicit so phase extraction and replay work are not built on hidden globals.
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

`simulation/engine.py` currently mutates module-private RNG references in household modules.
That hurts replay and later pathwise gradient experiments.
Need explicit RNG dependencies.

Precision note:

- the mutation currently happens in `SimulationEngine.reset()`
- household-related modules then read the injected generator state
- fix the mutation site and the read path together

Ordering note:

This prompt should be executed before or together with Prompt 1.
Otherwise extracted phase methods will preserve hidden module-level RNG coupling and make later replay work messier.

Affected paths include:

- `simulation/engine.py`
- `agents/household_agent.py`
- `agents/household/consumption.py`
- any demography helpers using implicit globals

## Task

Remove engine-side mutation of module-private RNG state in migrated paths.
Pass RNG objects explicitly.

### Step 1: identify implicit RNG use

Audit current RNG use in:

- household batch consumption
- household demography decisions
- engine local decisions
- any `np.random` default generator fallbacks in migrated paths

### Step 2: add RNG bundle or protocol

Add one small structure, for example `SimulationRNGs`, containing:

- python RNG
- numpy RNG
- optional replay stream handles later

### Step 3: thread RNG through call sites

Pass RNG dependencies through public and internal APIs where needed.
Avoid touching unrelated files unless necessary.

### Step 4: preserve backward compatibility carefully

If older tests instantiate components directly, keep safe default behavior at outer API boundary, but internal engine path must no longer mutate module globals.

### Step 5: add tests

Add fixed-seed tests proving:

- two runs with same seed and same config produce same outputs
- changing seed changes stochastic outcomes in at least one measurable way
- engine no longer relies on poking module-private RNG vars

## Deliverables

- explicit RNG injection in migrated path
- seed reproducibility tests

## Success Criteria

- deterministic replay groundwork exists
- no direct engine assignment into module-private RNG variables in migrated code path

## Verification Commands

```bash
python -m pytest tests -q -k "seed or rng or household"
```

---
