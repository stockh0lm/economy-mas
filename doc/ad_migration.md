# AD Migration Prompt Series

Standalone prompt files now also exist under `doc/ad_migration/`.
Use that directory when each prompt should be read or handed off independently.

## How to use this file

This file is not generic strategy memo anymore.
It is execution queue.
Each section is a detailed prompt that can be given to coding agent or used by human implementer.
Prompts are ordered.
Later prompts assume earlier prompts landed unless noted.

## Mandatory execution protocol for an LLM agent

This section is intentionally strict.
If an LLM is executing this file autonomously, it must process the prompts **sequentially** and must **not** skip ahead.

For every prompt in this file, the LLM must follow this exact loop:

1. **Solve current prompt fully**
   - Read current prompt carefully.
   - Implement all requested deliverables.
   - Run the required verification commands.
   - Fix all discovered issues that are in scope for the current prompt.
   - Do not start the next prompt while any deliverable of the current prompt is missing, broken, unverified, or only partially implemented.

2. **Stop and verify completion gate**
   - Confirm that the current prompt's deliverables exist.
   - Confirm that they work as specified.
   - Confirm that required tests or verification commands pass.
   - Confirm that the project state is consistent enough to checkpoint.

3. **Clean up project directory**
   - Remove temporary debug files, scratch scripts, partial outputs, and any ad hoc artifacts not intended as deliverables.
   - Keep only real source changes, real documentation, intended configs, intended scripts, intended tests, and intended outputs.
   - Ensure repository is left in a tidy, reviewable state before checkpointing.

4. **Create full project archive**
   - Create a `.zip` archive of the whole project directory after cleanup.
   - Archive should be a checkpoint of the repository at the end of the current prompt.
   - Recommended location: `output/archives/`.
   - Recommended naming pattern: `prompt_<N>_checkpoint_<YYYYMMDD_HHMMSS>.zip`.

5. **Provide archive link**
   - Generate and report an absolute link or URI to the archive.
   - In this workspace, prefer a `file://` URI pointing at the created zip file.
   - The archive link is part of the required completion ritual for every prompt.

6. **Immediately continue to next prompt**
   - After archive creation and link generation, the LLM should immediately start the next prompt in order.
   - Do not pause after a successful prompt unless execution time is exhausted or a hard blocker appears.
   - Repeat the same loop for the next prompt.

### Non-negotiable rule

**Never continue to the next prompt before the current prompt is fully finished, verified, cleaned up, archived, and linked.**

### Intended operating mode

This file is designed for long autonomous runs where the LLM should use the full computation budget of a session.
The correct behavior is:

1. solve prompt
2. clean up and zip project
3. provide archive link
4. immediately start next prompt
5. repeat until time or hard blockers stop execution

### Hard blocker rule

Only two things justify not moving to the next prompt:

- current prompt still not complete or not verified
- a genuine blocker prevents completion and cannot be resolved within the workspace

In all other cases, continue.

Prompt numbering starts at `Prompt 0`.
`Prompt 0` is first prompt, not preface.

Path notation rule:

- use workspace file paths like `agents/household/consumption.py` when referring to files
- use Python import notation only when import behavior itself matters

Primary goals:

1. debug simulation and find algorithmic flaws
2. optimize key parameters
3. learn parameter sensitivities to understand simulation better
4. enforce accounting and flow invariants
5. enable reproducible counterfactual analysis
6. separate structural flaws from policy/config choices
7. create foundation for surrogate models and better experiment design

## Global constraints for all prompts

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

# Prompt 0: Define Objectives, Losses, Parameter Registry

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

# Prompt 1: Extract `SimulationEngine.step()` into Phase Methods

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

# Prompt 2: Add Phase Snapshot and Event Trace Types

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

# Prompt 3: Replace Hidden Global RNG Mutation with Explicit Injection

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

# Prompt 4: Introduce Canonical Balance Operations and Transaction Records

## Context

Balances are mutated ad hoc across many files.
Need canonical money-flow operations before AD can say anything useful about instability.
This is also needed to debug hidden money sources, sinks, and broken repayment paths.

Relevant files:

- `agents/bank.py`
- `agents/company_agent.py`
- `agents/retailer_agent.py`
- `agents/household_agent.py`
- `agents/savings_bank_agent.py`
- `agents/state_agent.py`
- `warengeld_accounting.py`

See also the existing architectural issue in `doc/issues.md` for `warengeld_accounting.py` dead-code decision.
Current source-state reality: file exists, but simulation engine and agents do not use it.

## Task

Create minimal canonical balance/transaction layer and integrate it into highest-value paths first.

### Step 1: create balance ops module

Add `agents/balance_ops.py` or equivalent.
Include helper functions like:

- `get_balance(agent)`
- `credit_balance(agent, amount, reason, trace=None)`
- `debit_balance(agent, amount, reason, trace=None)`
- `transfer_balance(src, dst, amount, reason, trace=None)`

Keep implementation simple.
Do not over-abstract.

### Step 2: create transaction record schema

Add typed transaction record, either in `simulation/trace_types.py` or dedicated module.
Must include:

- step
- phase
- source id
- destination id
- amount
- reason
- mutation kind
- metadata

### Step 3: integrate highest-value flows first

Use canonical operations at least in:

- `WarengeldBank.finance_goods_purchase`
- CC repayment path
- company wage payments
- household retail purchases
- profit distribution if touched

### Step 4: decide relationship to `warengeld_accounting.py`

Do not leave ambiguity.

Recommended path for AD migration:

- do not build a second competing accounting abstraction
- reuse useful ideas from `warengeld_accounting.py` only if they simplify canonical balance ops or transaction records
- prefer integrating minimal double-entry or transaction-record patterns into `agents/balance_ops.py` and trace types
- verify actual usage explicitly, for example with repo search
- if the file remains unused after canonical balance ops land, mark it for deprecation or deletion instead of leaving it in architectural limbo

### Step 5: add invariant-friendly tests

Test:

- financing produces seller credit and retailer debt change as expected
- repayment extinguishes correct exposure
- wage payments transfer funds consistently
- purchase transfers balance correctly

## Deliverables

- `agents/balance_ops.py`
- transaction record support
- integration in priority money-flow paths
- tests for canonical transfers

## Success Criteria

- money-flow mutations in core paths go through one canonical layer
- trace records can reconstruct those mutations
- behavior remains compatible with existing tests

## Verification Commands

```bash
python -m pytest tests -q -k "bank or retailer or company or accounting"
```

---

# Prompt 5: Add Invariant Checker and Failure Precursors

## Context

Need automatic detection of first failure window.
Aggregate macro metrics are too late.
Need precursor metrics and invariant checks per step or per phase.

Relevant files:

- `simulation/engine.py`
- `metrics/collector.py`
- `metrics/calculator.py`
- newly added trace modules

Important architecture note:

- full engine has real multi-region execution
- precursor metrics should preserve region-aware aggregation where region scope matters

Scope note:

Not every invariant has equal value in every mode.
Some checks are only meaningful in the full engine, while others should also run in reduced deterministic cores.

## Task

Add precursor metrics and invariant checks that make instability visible before collapse.

### Step 1: define precursor metrics

Add metrics for at least:

- company wage funding ratio
- count of companies with `last_wage_pay_ratio < 1`
- retailer CC headroom percentile or min
- retailer no-order streak length
- producer no-cash streak length
- issuance minus repayment gap
- inventory starvation indicator
- audit stress count
- unemployment jump indicator
- conservation residual

Classify each precursor or invariant as one of:

- `full_engine_only`
- `reduced_core_capable`
- `shared_but_low_signal_in_reduced_mode`

Where region scope matters, specify whether metric is:

- global aggregate
- per-region
- both

### Step 2: add invariant checker module

Create `simulation/invariant_checks.py`.
Checks should include:

- illegal money creation outside allowed issuance path
- negative inventory below tolerance
- inconsistent CC exposure updates
- production despite impossible funding state if such state occurs
- invalid repayment state transitions

Be explicit that some checks, such as `audit stress count`, may be low-signal or disabled in Prompt 7 reduced mode.
Do not treat absence of those signals in reduced mode as proof of correctness.

### Step 3: record violations in traces and metrics

Invariant violations should show up both in structured trace and in summary outputs.

### Step 4: create instability analyzer script

Add `scripts/analyze_instability_window.py`.
Script should:

- run or load simulation outputs
- find first step where chosen precursor or invariant threshold trips
- print concise diagnosis
- export machine-readable summary

### Step 5: add tests

Tests should verify:

- precursor metrics exist in outputs
- analyzer can run on small scenario
- invariant checker catches at least one synthetic bad state in unit test

Create dedicated test files with stable names, for example:

- `tests/test_invariant_checks.py`
- `tests/test_instability_analyzer.py`

## Deliverables

- `simulation/invariant_checks.py`
- precursor metric additions
- `scripts/analyze_instability_window.py`
- tests for invariant checks and analyzer

## Success Criteria

- repo can identify first failure window, not only end-state collapse
- precursor metrics are available for future AD loss terms

## Verification Commands

```bash
python -m pytest tests/test_invariant_checks.py -q
python -m pytest tests/test_instability_analyzer.py -q
python scripts/analyze_instability_window.py --help
```

---

# Prompt 6: Implement Deterministic Replay Mode

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

# Prompt 7: Build Reduced Deterministic AD Core with Torch

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

# Prompt 8: Add Reduced-Core Parity Harness Against Real Engine

## Context

Reduced AD core is only useful if tied back to real engine behavior.
Need parity harness for short horizon and reduced-mode scenario.

## Task

Create reduced-core parity workflow.

### Step 1: add deterministic reduced scenario config

Create one or more configs under `configs/` or `configs/ad_experiments/` that disable major discrete/stochastic mechanisms and keep system in reduced-core regime.

### Step 2: add adapter from engine state to AD state

Create helper that converts deterministic engine snapshot into reduced tensor state.

### Step 3: compare trajectories

For short horizons compare selected signals:

- retailer inventory trend
- company balance trend
- CC exposure trend
- aggregate household consumption
- price index

### Step 4: define tolerance rules

Exact equality not required.
Need documented tolerances and explanation for acceptable mismatch.

### Step 5: add tests

Add `tests/test_reduced_core_parity.py`.

## Deliverables

- reduced deterministic configs
- engine-to-AD adapter
- parity tests
- short report documenting mismatch sources

## Success Criteria

- reduced core roughly reproduces real deterministic engine in intended regime
- mismatch sources are explicit, not mysterious

## Verification Commands

```bash
python -m pytest tests/test_reduced_core_parity.py -v
```

---

# Prompt 9: Implement Sensitivity Report Tooling

## Context

Once reduced core exists, gradients must become interpretable outputs for humans.
Need ranked sensitivity reports, phase attribution, and warnings about unreliable gradients.

## Task

Add sensitivity analysis tooling on top of reduced core and objective helpers.

### Step 1: create sensitivity runner

Add `scripts/run_ad_sensitivity.py`.
It should:

- load reduced scenario and parameter subset
- run reduced core
- compute gradients of chosen loss terms
- normalize results into elasticities where possible
- export machine-readable report

### Step 2: add structural warnings

Report when gradient reliability is suspect, for example:

- parameter at saturation boundary
- branch or clamp dominating local behavior
- topology-changing rule nearby but disabled in reduced mode
- finite-difference mismatch large

### Step 3: create plotting/report script

Add `scripts/plot_sensitivity_report.py`.
Generate at least:

- ranked parameter importance table
- per-loss sensitivity table
- optional bar plots / heatmaps

### Step 4: add tests

Basic tests should verify scripts run on tiny reduced scenario and export expected columns.

## Deliverables

- `scripts/run_ad_sensitivity.py`
- `scripts/plot_sensitivity_report.py`
- sensitivity output format
- basic script tests if test harness exists for scripts

## Success Criteria

- can generate ranked parameter table for one stable and one unstable scenario
- report explicitly states when gradients are trustworthy or not

## Verification Commands

```bash
python scripts/run_ad_sensitivity.py --help
python scripts/plot_sensitivity_report.py --help
```

---

# Prompt 10: Add Gradient-Based Parameter Optimization

## Context

After sensitivity tooling, next milestone is gradient-based tuning on reduced core.
Need prove value over naive search.

## Task

Implement gradient-based optimization workflow for selected parameter subset.

### Step 1: add optimization script

Create `scripts/optimize_params_ad.py`.
Use reduced core only.
Support:

- chosen objective or weighted objective bundle
- optimizer choice (`SGD`, `Adam`, maybe LBFGS)
- bounded parameter transforms
- logging of objective trajectory
- export of final suggested config patch

### Step 2: add random-search baseline

Within same script or companion helper, compare against equal-budget random search or local perturbation search.
Need empirical comparison, not claims.

### Step 3: export candidate configs

Write candidate YAML overrides under `configs/ad_experiments/`.
Do not overwrite canonical configs.

### Step 4: validate candidates in real engine

Add small validation helper that runs full engine on proposed configs and records objective summary.
May stay script-level.

Use the pure-Python objective helpers from `simulation/ad_objectives.py` for full-engine validation.
Do not make the validation path depend on Torch.

### Step 5: add tests

At minimum verify optimizer runs and objective improves on a tiny reduced toy horizon.

## Deliverables

- `scripts/optimize_params_ad.py`
- exported experiment configs
- comparison output against random search
- tests for reduced optimization smoke path

## Success Criteria

- one gradient-based run improves objective on reduced core
- full-engine validation can be executed on produced candidates

## Verification Commands

```bash
python scripts/optimize_params_ad.py --help
python -m pytest tests -q -k "optimize or ad_core"
```

---

# Prompt 11: Build Hybrid Failure-Window Workflow

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

# Prompt 12: Use AD Workflow to Find Structural Flaws

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

# Prompt 13: Extend Registry and Objectives to Difficult Parameters

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

# Prompt 14: Final Integration and Documentation Pass

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

# Recommended execution order

Run prompts in this order unless strong reason to change:

1. Prompt 0
2. Prompt 3
3. Prompt 1
4. Prompt 2
5. Prompt 4
6. Prompt 5
7. Prompt 6
8. Prompt 7
9. Prompt 8
10. Prompt 9
11. Prompt 10
12. Prompt 11
13. Prompt 12
14. Prompt 13
15. Prompt 14

Reason for promoting Prompt 3:

- explicit RNG injection removes hidden dependencies before phase extraction
- that makes Prompt 1 cleaner and makes replay hooks easier later

## Earliest useful stopping points

### Stop after Prompt 5

(After completing Prompts 0-5.)

You already have:

- phase structure
- traces
- precursor metrics
- invariants
- first-failure localization

Useful for debugging even without Torch.

### Stop after Prompt 8

You already have:

- reduced differentiable core
- parity harness
- credible first AD foundation

Useful for local sensitivity experiments.

### Stop after Prompt 11

You already have:

- hybrid full-engine + reduced-core workflow
- practical AD-assisted diagnosis loop

This is likely first high-value production milestone.

---

# Definition of done for first meaningful AD release

First meaningful release is done when repo can:

1. reproduce a crash in full engine
2. identify first failure window automatically
3. replay that window deterministically in migrated scope
4. reconstruct a reduced differentiable local model
5. compute ranked sensitivities for selected parameters
6. produce at least one validated optimization candidate or structural flaw hypothesis
7. verify hypothesis or candidate in full engine
8. export machine-readable and human-readable artifacts for review






