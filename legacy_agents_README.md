# Legacy top-level agent modules

This repository contains a historical set of agent modules at the repository root (e.g. `household_agent.py`, `company_agent.py`, `retailer_agent.py`, etc.) alongside the canonical implementations in the `agents/` package.

## Canonical rule

- **Runtime + tests must import agents from `agents/` only.**
- Top-level agent modules exist only for historical reference and should be treated as deprecated.

## Why this file exists

A previous partial "refactor" duplicated implementations and caused the live simulation to quietly lose lifecycle features (splits/bankruptcies/turnover), leading to flat metrics.

We are migrating missing behavior into the canonical `agents/` implementations and keeping the simulation loop wired to those.

## Next cleanup step (safe but breaking)

Once we confirm no external users import the top-level modules, we can:

- delete the top-level agent duplicates, or
- replace them with thin re-exports that `raise DeprecationWarning` on import.
