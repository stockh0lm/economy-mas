# Prompt 2: Add Phase Snapshot and Event Trace Types
## Position in series
- Order: 3 of 15
- Depends on: Prompt 1.
- Primary goal: Add typed phase and event trace records on top of extracted phase seams.
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

Phase extraction alone is not enough.
Need structured records of what each phase changed.
These records are foundation for failure localization and later reduced-core reconstruction.

## Task

Introduce typed phase snapshots and event records.

### Step 1: Create trace types module

Create `simulation/trace_types.py`.
Add dataclasses or typed structures for:

- `PhaseName`
- `StepPhaseSummary`
- `PhaseDelta`
- `SimulationEvent`
- `StepTrace`

Each event should support fields like:

- `step`
- `phase`
- `event_type`
- `agent_ids`
- `region_id`
- `amount`
- `metadata`

### Step 2: Add engine collection hooks

Add optional trace collection to `SimulationEngine`.
Design must allow tracing to be disabled by default for performance.
When enabled, engine should record per-phase summaries and event lists.

### Step 3: Capture initial event families

Add at least these event types:

- `birth`
- `death`
- `founding`
- `merger`
- `restock`
- `wage_payment`
- `wage_underfunded`
- `retailer_insolvency`
- `sight_decay`
- `audit`
- `cc_repayment`

### Step 4: Add export path

Add helper to export traces as JSONL or CSV-friendly form under `output/`.

### Step 5: Add tests

Verify:

- trace objects are produced when enabled
- event ordering follows phase ordering
- trace disabled mode does not change behavior

## Deliverables

- `simulation/trace_types.py`
- engine trace hooks
- trace export helper
- tests for trace generation

## Success Criteria

- one simulation step can be described as sequence of phase deltas and events
- trace system is opt-in
- trace output is machine-readable and stable enough for scripts

## Verification Commands

```bash
python -m pytest tests -q -k "trace or simulation_engine"
```

---
