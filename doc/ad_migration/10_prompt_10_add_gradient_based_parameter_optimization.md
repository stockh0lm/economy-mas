# Prompt 10: Add Gradient-Based Parameter Optimization
## Position in series
- Order: 11 of 15
- Depends on: Prompt 9 and Prompt 0.
- Primary goal: Run bounded gradient-based tuning and compare with random search.
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
