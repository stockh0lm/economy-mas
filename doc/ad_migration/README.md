# AD Migration Prompt Series
Canonical source overview remains in `doc/ad_migration.md`.
This directory contains standalone prompt files so each prompt can be read independently.
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
## Prompt index
- [00 — Prompt 0: Define Objectives, Losses, Parameter Registry](00_prompt_0_define_objectives_losses_parameter_registry.md)
- [01 — Prompt 1: Extract `SimulationEngine.step()` into Phase Methods](01_prompt_1_extract_simulationengine_step_into_phase_methods.md)
- [02 — Prompt 2: Add Phase Snapshot and Event Trace Types](02_prompt_2_add_phase_snapshot_and_event_trace_types.md)
- [03 — Prompt 3: Replace Hidden Global RNG Mutation with Explicit Injection](03_prompt_3_replace_hidden_global_rng_mutation_with_explicit_injection.md)
- [04 — Prompt 4: Introduce Canonical Balance Operations and Transaction Records](04_prompt_4_introduce_canonical_balance_operations_and_transaction_records.md)
- [05 — Prompt 5: Add Invariant Checker and Failure Precursors](05_prompt_5_add_invariant_checker_and_failure_precursors.md)
- [06 — Prompt 6: Implement Deterministic Replay Mode](06_prompt_6_implement_deterministic_replay_mode.md)
- [07 — Prompt 7: Build Reduced Deterministic AD Core with Torch](07_prompt_7_build_reduced_deterministic_ad_core_with_torch.md)
- [08 — Prompt 8: Add Reduced-Core Parity Harness Against Real Engine](08_prompt_8_add_reduced_core_parity_harness_against_real_engine.md)
- [09 — Prompt 9: Implement Sensitivity Report Tooling](09_prompt_9_implement_sensitivity_report_tooling.md)
- [10 — Prompt 10: Add Gradient-Based Parameter Optimization](10_prompt_10_add_gradient_based_parameter_optimization.md)
- [11 — Prompt 11: Build Hybrid Failure-Window Workflow](11_prompt_11_build_hybrid_failure_window_workflow.md)
- [12 — Prompt 12: Use AD Workflow to Find Structural Flaws](12_prompt_12_use_ad_workflow_to_find_structural_flaws.md)
- [13 — Prompt 13: Extend Registry and Objectives to Difficult Parameters](13_prompt_13_extend_registry_and_objectives_to_difficult_parameters.md)
- [14 — Prompt 14: Final Integration and Documentation Pass](14_prompt_14_final_integration_and_documentation_pass.md)

## Recommended execution order
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
## Definition of done for first meaningful AD release
First meaningful release is done when repo can:

1. reproduce a crash in full engine
2. identify first failure window automatically
3. replay that window deterministically in migrated scope
4. reconstruct a reduced differentiable local model
5. compute ranked sensitivities for selected parameters
6. produce at least one validated optimization candidate or structural flaw hypothesis
7. verify hypothesis or candidate in full engine
8. export machine-readable and human-readable artifacts for review
