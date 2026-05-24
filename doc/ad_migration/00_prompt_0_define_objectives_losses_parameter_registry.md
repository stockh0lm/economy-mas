# Prompt 0: Define Objectives, Losses, Parameter Registry
## Position in series
- Order: 1 of 15
- Depends on: None. Entry point.
- Primary goal: Define losses, invariants, registry paths, and evaluation helpers before any refactor or Torch work.
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

Current parameter search is mostly brute-force.
Need explicit objectives before implementing AD.
Without loss functions and parameter registry, gradients have no meaning.

Current relevant files:

- `config.py`
- `metrics/collector.py`
- `metrics/calculator.py`
- `doc/golden_run.md`
- `doc/long_running_investigation_prompt.md`
- `tests/test_golden_run_comprehensive.py`
- `simulation/engine.py`

## Task

Create formal objective definitions and initial AD parameter registry.

### Step 1: Add objective document

Create `doc/as_objectives.md`.
Define at minimum four loss families:

1. `L_instability`
2. `L_invariant`
3. `L_realism`
4. `L_target`

For each loss family include:

- motivation
- exact candidate terms
- expected units
- normalization approach
- known failure modes
- whether term is suitable for gradient descent, finite differences, or replay analysis only

### Step 2: Add machine-readable parameter registry

Create `simulation/ad_registry.py` or similar.
Add data structure for tunable parameters with fields like:

- canonical name
- config path
- subsystem
- units
- default value
- lower and upper bounds
- transform type
- differentiability class (`smooth`, `piecewise`, `stochastic`, `discrete_gate`, `surrogate_only`)
- comments

Start with a deliberately small high-value subset, such as:

- `company.production_target_stock_days`
- `company.production_ramp_sensitivity`
- `company.price_inventory_sensitivity`
- `retailer.reorder_point_ratio`
- `retailer.restock_target_stock_days`
- `retailer.restock_flow_replenishment_multiple`
- `bank.cc_limit_multiplier`
- `bank.cc_limit_audit_risk_penalty`
- `market.price_index_sensitivity`
- `labor_market.wage_unemployment_sensitivity`

Before finalizing the initial registry, verify every example path against the real `SimulationConfig` shape.
Recommended check:

```bash
python -c "from config import SimulationConfig; c = SimulationConfig(); print(c.model_dump().keys())"
```

This command only confirms top-level nested structure.
It does **not** validate dot-path resolution by itself.

Add a real resolution helper in the registry layer.
Document how a path like `company.production_target_stock_days` resolves to `config.company.production_target_stock_days`.
Then test that helper against real nested attributes from `SimulationConfig()` rather than trusting handwritten strings.

### Step 3: Add objective helpers

Create lightweight helper module, for example `simulation/ad_objectives.py`, that computes named objective terms from existing metrics snapshots or traces.
Do not add Torch yet.
Pure Python first.

### Step 4: Add tests

Create tests that verify:

- registry entries reference real config paths
- bounds and transforms are valid
- objective helpers return finite values on a short simulation run

Recommended test files:

- `tests/test_ad_registry.py`
- `tests/test_ad_objectives.py`

## Deliverables

- `doc/as_objectives.md`
- `simulation/ad_registry.py`
- `simulation/ad_objectives.py`
- tests for registry and objective helpers

## Success Criteria

- every initial AD experiment can refer to explicit loss names
- every initial trainable parameter has explicit bounds and classification
- objective helpers run on existing engine outputs without modifying behavior

## Verification Commands

```bash
python -m pytest tests/test_ad_registry.py -q
python -m pytest tests/test_ad_objectives.py -q
```

---
