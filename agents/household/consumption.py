"""Consumption logic for households.

This module handles:
- Consumption plan creation (pure functions)
- Consumption execution with side effects
- Batch consumption for performance
- Consumption history tracking

Referenz: doc/issues.md Abschnitt 4 – Refactoring Household.step
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

import numpy as np

if TYPE_CHECKING:
    from agents.household_agent import Household
    from agents.retailer_agent import RetailerAgent


class _RNG(Protocol):
    """Minimal RNG protocol used for deterministic unit tests.

    We accept either `random` module or an instance of `random.Random`.
    """

    def random(self) -> float:  # pragma: no cover - protocol
        ...

    def choice(self, seq: Sequence[object]) -> object:  # pragma: no cover - protocol
        ...


_DEFAULT_NP_RNG = None


def _get_default_np_rng():
    # Delegate to the canonical RNG in household_agent to ensure a single
    # seeded generator is shared across all household numpy operations.
    from agents.household_agent import _get_default_np_rng as _canonical_get

    return _canonical_get()


@dataclass(frozen=True, slots=True)
class ConsumptionPlan:
    """Pure consumption plan (no side-effects).

    This object is intentionally small and stable so it can be unit-tested
    in isolation (Ref: doc/issues.md Abschnitt 4 – Refactoring Household.step).
    """

    budget: float
    retailer: RetailerAgent | None


def push_consumption_history(household: Household, spent: float) -> None:
    """Append to the rolling consumption history.

    Performance note:
    - With a deque this is O(1) and avoids per-step list slicing.
    """
    window = int(household.config.clearing.sight_allowance_window_days)
    if window <= 0:
        return

    ch = household.consumption_history
    # If someone replaced the deque with a list in a test, stay compatible.
    if isinstance(ch, deque):
        if ch.maxlen != window:
            ch = deque(ch, maxlen=window)
            household.consumption_history = ch
        ch.append(spent)
        return

    # List fallback
    ch.append(spent)
    if len(ch) > window:
        del ch[:-window]


def record_consumption(household: Household, spent: float) -> None:
    """Centralized bookkeeping for consumption side-effects."""

    spent_f = float(spent)
    household.consumption = spent_f
    household.consumption_this_month += spent_f
    household.last_consumption += spent_f
    push_consumption_history(household, spent_f)


def build_consumption_plan(
    household: Household,
    *,
    consumption_rate: float,
    retailers: Sequence[RetailerAgent],
    rng: _RNG,
) -> ConsumptionPlan:
    """Create a pure consumption plan.

    This method is intentionally side-effect free so it can be unit-tested
    in isolation.

    Referenz: doc/issues.md Abschnitt 4 → "Gründliches Refaktorieren".
    """

    if consumption_rate <= 0 or not retailers:
        return ConsumptionPlan(budget=0.0, retailer=None)

    budget = float(household.sight_balance) * float(consumption_rate)
    if budget <= 0:
        return ConsumptionPlan(budget=0.0, retailer=None)

    # Keep selection deterministic for tests by allowing an injected RNG.
    retailer = rng.choice(retailers)
    return ConsumptionPlan(budget=float(budget), retailer=retailer)


def execute_consumption_plan(household: Household, plan: ConsumptionPlan) -> float:
    """Execute a previously created consumption plan (with side effects)."""

    if plan.budget <= 0 or plan.retailer is None:
        record_consumption(household, 0.0)
        return 0.0

    result = plan.retailer.sell_to_household(household, plan.budget)
    spent = float(result.sale_value)
    record_consumption(household, spent)
    return spent


def consume(
    household: Household,
    consumption_rate: float,
    retailers: Sequence[RetailerAgent],
    *,
    rng: _RNG,
) -> float:
    """Spend on goods from retailers.

    The heavy logic is split into:
    - `build_consumption_plan` (pure)
    - `execute_consumption_plan` (side effects)
    """

    # Fast-path: avoid per-step plan creation when no consumption is possible.
    if consumption_rate <= 0 or not retailers:
        record_consumption(household, 0.0)
        return 0.0

    plan = build_consumption_plan(
        household=household,
        consumption_rate=consumption_rate,
        retailers=retailers,
        rng=rng,
    )
    return execute_consumption_plan(household, plan)


def batch_consume(
    households: Sequence[Household],
    retailers: Sequence[RetailerAgent],
    *,
    rng: np.random.Generator | None = None,
) -> list[float]:
    """Vectorized consumption execution for many households.

    This method is intentionally pragmatic:
    - budgets are computed via numpy arrays
    - retailer selection is sampled via numpy RNG
    - sales are still executed per household (side effects), but without
      per-household ConsumptionPlan allocations.

    Referenz (explizit): doc/issues.md Abschnitt 5 → Performance-Optimierung
    nach Profiling-Analyse (Household.consume Hotspot).
    """

    n = len(households)
    if n == 0:
        return []

    if not retailers:
        for h in households:
            record_consumption(household=h, spent=0.0)
        return [0.0] * n

    gen = rng or _get_default_np_rng()

    # Build arrays (n is typically small, but this avoids Python math per agent)
    balances = np.fromiter((float(h.sight_balance) for h in households), dtype=np.float64, count=n)
    growth_mask = np.fromiter((bool(h.growth_phase) for h in households), dtype=np.bool_, count=n)

    cfg = households[0].config.household
    rate_normal = float(cfg.consumption_rate_normal)
    rate_growth = float(cfg.consumption_rate_growth)
    rates = np.where(growth_mask, rate_growth, rate_normal)
    budgets = balances * rates

    idxs = gen.integers(0, len(retailers), size=n, dtype=np.int32)

    spent_out: list[float] = [0.0] * n
    for i, h in enumerate(households):
        budget = float(budgets[i])
        if budget <= 0.0:
            record_consumption(household=h, spent=0.0)
            continue
        retailer = retailers[int(idxs[i])]
        sale = retailer.sell_to_household(h, budget)
        spent = float(sale.sale_value)
        record_consumption(household=h, spent=spent)
        spent_out[i] = spent

    return spent_out


def handle_consumption(
    household: Household,
    *,
    retailers: Sequence[RetailerAgent],
    rng: _RNG,
) -> float:
    """Consumption decision pipeline."""

    rate = (
        household.config.household.consumption_rate_growth
        if household.growth_phase
        else household.config.household.consumption_rate_normal
    )
    return consume(
        household=household,
        consumption_rate=rate,
        retailers=retailers,
        rng=rng,
    )


# ---------------------------------------------------------------------------
# Class-based wrapper (used by household_agent.py component delegation)
# ---------------------------------------------------------------------------


class ConsumptionComponent:
    """Wraps the function-based consumption logic as a component attached to a Household."""

    __slots__ = ("_household", "_consumption", "_consumption_history")

    def __init__(self, household: Household) -> None:
        self._household = household
        self._consumption: float = 0.0
        window = int(household.config.clearing.sight_allowance_window_days)
        self._consumption_history: deque[float] = deque(maxlen=max(0, window))

    # --- properties delegated from Household ---

    @property
    def consumption(self) -> float:
        return self._consumption

    @consumption.setter
    def consumption(self, value: float) -> None:
        self._consumption = float(value)

    @property
    def consumption_history(self):
        return self._consumption_history

    @consumption_history.setter
    def consumption_history(self, value) -> None:
        self._consumption_history = value

    # --- Proxy attributes so module-level functions can access h.consumption / h.consumption_history ---
    # The module-level functions write to `household.consumption` and
    # `household.consumption_history`. The Household class defines these as
    # properties that delegate to the component. That works because the
    # property setter on Household sets `self.consumption_component.consumption`.

    # --- delegated methods ---

    def build_consumption_plan(
        self,
        *,
        consumption_rate: float,
        retailers: Sequence[RetailerAgent],
        rng: _RNG,
    ) -> ConsumptionPlan:
        return build_consumption_plan(
            self._household,
            consumption_rate=consumption_rate,
            retailers=retailers,
            rng=rng,
        )

    def _execute_consumption_plan(self, plan: ConsumptionPlan) -> float:
        return execute_consumption_plan(self._household, plan)

    def consume(
        self,
        consumption_rate: float,
        retailers: Sequence[RetailerAgent],
        *,
        rng: _RNG,
    ) -> float:
        return consume(
            self._household,
            consumption_rate,
            retailers,
            rng=rng,
        )

    def handle_consumption(
        self,
        *,
        retailers: Sequence[RetailerAgent],
        rng: _RNG,
    ) -> float:
        return handle_consumption(self._household, retailers=retailers, rng=rng)

    @staticmethod
    def batch_consume(
        components: Sequence[ConsumptionComponent],
        retailers: Sequence[RetailerAgent],
        *,
        rng: np.random.Generator | None = None,
    ) -> list[float]:
        """Vectorized batch consumption over a list of ConsumptionComponents."""
        households = [c._household for c in components]
        return batch_consume(households, retailers, rng=rng)

    # --- household-like accessors used by module-level functions ---
    # Module functions access h.sight_balance, h.growth_phase, h.config etc.
    # Those go through the real Household instance, so no extra proxying needed.
