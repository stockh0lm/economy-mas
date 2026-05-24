# Prompt 7: Build Reduced Deterministic AD Core with Torch
## Position in series
- Order: 8 of 15
- Depends on: Prompt 0, Prompt 4, Prompt 5.
- Primary goal: Implement first reduced deterministic Torch core.
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

Full engine is too discontinuous and mutable for immediate end-to-end autograd.
Need reduced deterministic core focused on monetary-production circuit.
This is first actual Torch milestone.

Suggested reduced scope:

- retailer restocking
- bank financing / repayment
- company wage funding and production throttle
- household demand aggregate
- price-index feedback

Reduced-mode caveat:

Some Prompt 5 precursor metrics and invariants will lose signal here.
For example, audit-related metrics or some starvation indicators may become trivial when major stochastic and topology-changing mechanisms are frozen.
Carry forward the classification from Prompt 5 and expose which checks are active, inactive, or low-signal in reduced mode.

Also be explicit that reduced-core mode is likely single-region first unless multi-region tensors are intentionally designed.
Do not imply full parity with multi-region engine behavior in the first Torch milestone.

Disable or freeze:

- births and deaths
- founding and mergers
- innovation randomness
- random labor shuffling
- topology changes

## Task

Implement reduced differentiable simulator using Torch.

### Step 1: create state and parameter modules

Add:

- `simulation/ad_state.py`
- `simulation/ad_params.py`
- `simulation/ad_core.py`

### Step 2: define fixed-size tensor state

State should include at least:

- aggregate household balances and demand state
- company balances, inventory, capacity proxies
- retailer balances, inventory, CC state
- bank exposure state
- price index and unemployment proxy if needed

### Step 3: parameter transforms

Use constrained transforms, for example:

- positive via `softplus`
- bounded via `sigmoid`

### Step 4: implement differentiable rollout

Expose API like:

- initialize state from config or reduced snapshot
- run for `N` steps
- return trajectory and objective terms

### Step 5: add smoke tests

Verify:

- forward pass works
- backward pass works
- gradients finite for first parameter subset

### Step 6: add finite-difference sanity test

For at least 2-3 parameters compare autograd direction/magnitude roughly against finite differences.

## Deliverables

- `simulation/ad_state.py`
- `simulation/ad_params.py`
- `simulation/ad_core.py`
- smoke and finite-difference tests

## Success Criteria

- can backpropagate one stability loss through reduced core over multi-step horizon
- gradients are finite and not obviously nonsense on baseline scenario

## Verification Commands

```bash
python -m pytest tests -q -k "ad_core or finite_difference"
```

---
