"""LEGACY (removed): EconomicAgent

This file previously contained a dummy agent that mutated `balance` and printed to stdout.
It was not used anywhere in the simulation or tests and conflicted with the project goal
of having explicit, spec-aligned monetary primitives.

If we ever need a shared base for economically active agents, we should define it in terms
of explicit balance-sheet accounts (e.g., `sight_balance`) and keep it side-effect free.
"""

# Intentionally left without runtime symbols.
