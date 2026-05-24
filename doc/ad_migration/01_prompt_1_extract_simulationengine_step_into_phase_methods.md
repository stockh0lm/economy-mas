# Prompt 1: Extract `SimulationEngine.step()` into Phase Methods
## Position in series
- Order: 2 of 15
- Depends on: Prompt 0 and Prompt 3 preferred first.
- Primary goal: Split `SimulationEngine.step()` into behavior-preserving phase seams with correct demography and founding/merger ordering.
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

`simulation/engine.py` contains a giant `SimulationEngine.step()` method.
This blocks diagnosis, replay, sensitivity attribution, and reduced-core extraction.
Need explicit phase boundaries before AD.

This prompt directly implements the P0 backlog item "SimulationEngine.step() Method Refactoring" from `doc/issues.md`.
After completion, that backlog item should be updated or marked resolved.

Current codebase note:

- the `step()` method in `simulation/engine.py` is still roughly 500 lines long in the current source state
- treat line numbers in older notes as historical, not canonical

## Task

Refactor `SimulationEngine.step()` into explicit private phase methods without changing behavior.

### Required phase split

Extract at least these methods:

- `_step_demography()`
- `_step_company_founding_mergers()`
- `_step_labor_posting()`
- `_step_labor_matching()`
- `_step_retail_restocking()`
- `_step_company_operations()`
- `_step_household_consumption()`
- `_step_retail_settlement()`
- `_step_retailer_insolvency()`
- `_step_monthly_policy()`
- `_step_monthly_sight_decay()`
- `_step_audits()`
- `_step_environment()`
- `_step_metrics()`
- `_step_progress_reporting()`

If `_step_labor_posting()` and `_step_labor_matching()` are temporarily wrapped by a convenience `_step_labor_market()` coordinator, keep the two internal seams explicit.

If `company founding` and `mergers` remain temporarily coupled to demography because of shared counters or shared local state, make that coupling explicit in comments and temporary adapters.
Do not silently bury them inside `_step_demography()` without naming the seam.

### Requirements

- preserve exact ordering semantics
- preserve current seeding behavior
- preserve side effects and return values
- preserve current metrics export behavior
- avoid introducing extra full copies of state
- preserve multi-region behavior and per-region dispatch semantics
- any extracted phase that currently operates per-region must keep region iteration explicit rather than accidentally collapsing behavior to single-region assumptions
- preserve actual ordering semantics from current engine, specifically:
  - demography and household death handling
  - company founding and merger handling
  - labor posting
  - labor matching
  - retail restocking
  - company operations
  - household consumption
  - retail settlement
  - retailer insolvency
- note that the current engine interleaves demography, founding, and merger logic tightly; the first refactor may need a coordinator seam before fully independent phase bodies are possible
- document in code comments that the monetary-production loop is not just `bank -> retailer -> company -> household -> retailer`, but also depends on labor allocation as the staffing mechanism that lets companies convert financing into output
- treat `_step_metrics()` and `_step_progress_reporting()` as observer phases that should be easy to no-op or replace in reduced modes

Recommended comment to preserve in the refactored engine near the ordering seam:

```text
Circular flow: Bank ->(CC)-> Retailer ->(retailer purchases goods from company)-> Company
  ->(labor matching / staffed production)-> Worker ->(wages)-> Household
  ->(consumption)-> Retailer ->(CC repayment / write-down / correction path)-> Bank
```

### Add minimal per-phase return summaries

Each phase method should return a small structured summary or write into a step-local summary object.
Do not build full trace system yet.
Just establish seam.

Examples of summary fields:

- counts of births/deaths/company events
- counts of foundings/mergers
- counts of restocks/insolvencies
- whether monthly policy ran
- whether sight decay ran
- whether audits ran

### Add tests

Add parity tests for fixed seed:

- same number of steps
- same exported global metrics rows
- same final counts of households/companies/retailers
- same or equivalent key macro outputs for fixed short run

## Deliverables

- refactored `simulation/engine.py`
- new tests for engine-phase parity

## Success Criteria

- `SimulationEngine.step()` becomes coordinator, not god method
- phase methods exist and are individually testable
- fixed-seed behavior preserved on short deterministic regression runs

## Verification Commands

```bash
python -m pytest tests/test_golden_run_comprehensive.py -v
python -m pytest tests -q -k "simulation_engine or golden_run"
```

---
