# Prompt 4: Introduce Canonical Balance Operations and Transaction Records
## Position in series
- Order: 5 of 15
- Depends on: Prompt 1 and Prompt 2 preferred.
- Primary goal: Centralize money-flow mutations and transaction records in core paths.
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
