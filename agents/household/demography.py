"""Demographic behavior for households.

This module handles:
- Household splitting (older growth mechanism)
- Births and fertility calculations
- Aging and lifecycle management
- Growth state tracking
- Household formation events

Referenz: doc/issues.md Abschnitt 4 – Refactoring Household.step
"""

from __future__ import annotations

import random as _random_module
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from logger import log
from sim_clock import SimulationClock

if TYPE_CHECKING:
    from agents.household_agent import Household
    from agents.savings_bank_agent import SavingsBank


class _RNG(Protocol):
    """Minimal RNG protocol used for deterministic unit tests.

    We accept either `random` module or an instance of `random.Random`.
    """

    def random(self) -> float:  # pragma: no cover - protocol
        ...

    def choice(self, seq: Sequence[object]) -> object:  # pragma: no cover - protocol
        ...


@dataclass(frozen=True, slots=True)
class HouseholdFormationEvent:
    """Deferred demographic event describing household formation."""

    kind: str  # "split" | "birth"


def split_household(
    household: Household,
    *,
    savings_bank: SavingsBank,
) -> Household | None:
    """Create a new household (child) funded from this household's savings.

    This is the canonical replacement for the legacy top-level `household_agent.py`
    behavior. It is designed to be Warengeld-consistent:
    - No money creation: funding comes from withdrawing existing savings OR
      splitting existing sight balances.

    Returns the new Household instance if a split happened, else None.
    """

    # Total savings = local + SavingsBank deposits
    bank_savings = float(savings_bank.savings_accounts.get(household.unique_id, 0.0))
    local_savings = float(household.local_savings)
    total_savings = bank_savings + local_savings

    # If we don't have savings, we can still split by allocating part of our
    # disposable sight balance to the child (this is a pure transfer).
    if total_savings <= 0:
        disposable = max(
            0.0,
            float(household.sight_balance) - float(household.config.household.transaction_buffer),
        )
        if disposable <= 0:
            return None
        transfer = 0.5 * disposable
        if transfer <= 0:
            return None
        # Deduct from parent sight balance.
        household.sight_balance -= transfer

        from agents.household_agent import Household as HH

        child = HH(
            unique_id=f"{household.unique_id}_child_{household.generation + 1}",
            income=household.income,
            land_area=household.land_area,
            environmental_impact=household.environmental_impact,
            config=household.config,
        )
        child.region_id = household.region_id
        child.generation = int(household.generation + 1)
        child.sight_balance = float(transfer)

        household.growth_phase = False
        household.growth_counter = 0
        household.child_cost_covered = False
        return child

    transfer = 0.8 * total_savings
    if transfer <= 0:
        return None

    # Withdraw preferentially from SavingsBank, then from local.
    from_bank = 0.0
    if bank_savings > 0:
        from_bank = savings_bank.withdraw_savings(household, min(bank_savings, transfer))

    remaining = max(0.0, transfer - from_bank)
    from_local = min(remaining, max(0.0, local_savings))
    household.local_savings = max(0.0, local_savings - from_local)

    from agents.household_agent import Household as HH

    child = HH(
        unique_id=f"{household.unique_id}_child_{household.generation + 1}",
        income=household.income,
        land_area=household.land_area,
        environmental_impact=household.environmental_impact,
        config=household.config,
    )
    child.region_id = household.region_id
    child.generation = int(household.generation + 1)
    child.sight_balance = float(from_bank + from_local)

    # Reset parent's growth bookkeeping
    household.growth_phase = False
    household.growth_counter = 0
    household.child_cost_covered = False

    return child


def fertility_probability_daily(household: Household, *, savings_bank: SavingsBank) -> float:
    """Compute daily probability of a birth/household-formation event.

    Expliziter Bezug:
    - doc/issues.md Abschnitt 4) → "Einfaches Wachstums- und Sterbe-Verhalten" (Demografie)
    - doc/issues.md Abschnitt 5) → Performance-Optimierung: Cache im daily-Hotpath

    The model is intentionally simple and bounded:
    - Eligible age window: [fertility_age_min, fertility_age_max]
    - Age factor peaks at fertility_peak_age (triangular shape)
    - Income and wealth act as multiplicative elasticities
    - Converted from annual to daily probability using the global calendar
    """

    cfg = household.config.household
    base_annual = float(cfg.fertility_base_annual)
    if base_annual <= 0.0:
        return 0.0

    age = int(household.age)
    amin = int(cfg.fertility_age_min)
    amax = int(cfg.fertility_age_max)
    if age < amin or age > amax:
        return 0.0

    bank_savings = float(savings_bank.savings_accounts.get(household.unique_id, 0.0))
    wealth = float(household.sight_balance) + float(household.local_savings) + bank_savings

    # Cache: (age_years, income_bin, wealth_bin)
    bin_size = float(household._fertility_cache_bin_size)
    wealth_bin = int(wealth / bin_size) if bin_size > 0 else int(wealth)
    income_bin = int(float(household.income) * 10.0)  # 0.1 precision
    key = (age, income_bin, wealth_bin)
    cached = household._fertility_p_daily_cache.get(key)
    if cached is not None:
        return cached

    # Age factor: triangular around the peak.
    peak = int(cfg.fertility_peak_age)
    if peak < amin:
        peak = amin
    elif peak > amax:
        peak = amax

    if age <= peak:
        denom = peak - amin
        age_factor = (age - amin) / denom if denom > 0 else 1.0
    else:
        denom = amax - peak
        age_factor = (amax - age) / denom if denom > 0 else 1.0
    if age_factor < 0.0:
        age_factor = 0.0
    elif age_factor > 1.0:
        age_factor = 1.0

    base_income = float(cfg.base_income) if float(cfg.base_income) > 0 else 1.0
    income_rel = float(household.income) / base_income
    income_elasticity = float(cfg.fertility_income_sensitivity)
    income_factor = income_rel**income_elasticity if income_elasticity != 0.0 else 1.0
    if income_factor < 0.25:
        income_factor = 0.25
    elif income_factor > 4.0:
        income_factor = 4.0

    trigger = float(cfg.savings_growth_trigger) if float(cfg.savings_growth_trigger) > 0 else 1.0
    wealth_rel = wealth / trigger
    wealth_elasticity = float(cfg.fertility_wealth_sensitivity)
    wealth_factor = wealth_rel**wealth_elasticity if wealth_elasticity != 0.0 else 1.0
    if wealth_factor < 0.25:
        wealth_factor = 0.25
    elif wealth_factor > 4.0:
        wealth_factor = 4.0

    days_per_year = float(household.config.time.days_per_year)
    annual = base_annual * age_factor * income_factor * wealth_factor
    daily = annual / days_per_year if days_per_year > 0 else annual
    if daily < 0.0:
        daily = 0.0
    elif daily > 1.0:
        daily = 1.0

    cache = household._fertility_p_daily_cache
    if len(cache) > household._fertility_cache_max_size:
        cache.clear()
    cache[key] = daily
    return daily


def birth_new_household(household: Household, *, savings_bank: SavingsBank) -> Household | None:
    """Create a newborn household funded by a transfer from the parent.

    The transfer follows a strict *no money creation* rule:
    - take from disposable sight first
    - then local savings
    - finally withdraw from SavingsBank deposits
    """

    cfg = household.config.household
    share = float(cfg.birth_endowment_share)
    if share <= 0:
        return None

    bank_savings = float(savings_bank.savings_accounts.get(household.unique_id, 0.0))
    wealth = float(household.sight_balance) + float(household.local_savings) + bank_savings

    buffer = float(cfg.transaction_buffer)
    # Do not drain the household below a small transactional buffer.
    transferable_total = max(0.0, wealth - buffer)
    desired = share * transferable_total
    if desired <= 0:
        return None

    remaining = desired

    # 1) Sight balance (keep buffer)
    disposable_sight = max(0.0, float(household.sight_balance) - buffer)
    from_sight = min(disposable_sight, remaining)
    if from_sight > 0:
        household.sight_balance -= from_sight
        remaining -= from_sight

    # 2) Local savings
    from_local = min(max(0.0, float(household.local_savings)), remaining)
    if from_local > 0:
        household.local_savings -= from_local
        remaining -= from_local

    # 3) SavingsBank deposits (withdraw -> sight -> transfer)
    if remaining > 0 and bank_savings > 0:
        withdrawn = savings_bank.withdraw_savings(household, min(bank_savings, remaining))
        if withdrawn > 0:
            # withdraw_savings already credited our sight_balance; transfer it out.
            household.sight_balance -= withdrawn
            remaining -= withdrawn

    transferred = desired - max(0.0, remaining)
    if transferred <= 0:
        return None

    from agents.household_agent import Household as HH

    child = HH(
        unique_id=f"{household.unique_id}_child_{household.generation + 1}",
        income=household.income,
        land_area=household.land_area,
        environmental_impact=household.environmental_impact,
        config=household.config,
    )
    child.region_id = household.region_id
    child.generation = int(household.generation + 1)
    child.sight_balance = float(transferred)
    child.age_days = 0

    return child


def advance_age(household: Household) -> None:
    household.age_days += 1
    days_per_year = int(household.config.time.days_per_year)
    household.age = household.age_days // max(1, days_per_year)


def update_growth_state(household: Household, *, savings_bank: SavingsBank) -> None:
    # Primary trigger: total savings (local + SavingsBank account).
    bank_savings = float(savings_bank.savings_accounts.get(household.unique_id, 0.0))
    total_savings = float(household.local_savings) + bank_savings

    # Secondary trigger: sustained disposable sight balances when saving is low.
    # This prevents a systemic "no growth" outcome when savings_rate=0.
    disposable_sight = max(
        0.0, float(household.sight_balance) - float(household.config.household.transaction_buffer)
    )
    wealth_trigger = float(household.config.household.sight_growth_trigger)
    if wealth_trigger <= 0:
        # Default heuristic: 5x base_income
        wealth_trigger = 5.0 * float(household.config.household.base_income)

    household.growth_phase = bool(
        total_savings >= float(household.config.household.savings_growth_trigger)
        or disposable_sight >= wealth_trigger
    )
    if household.growth_phase:
        household.child_cost_covered = False


def update_growth_counter_and_buffer_child_cost(
    household: Household, *, savings_bank: SavingsBank
) -> None:
    if not household.growth_phase:
        household.growth_counter = 0
        return

    household.growth_counter += 1
    # Align with tests: withdraw the child-rearing amount into checking and
    # mark the cost as covered, but don't spend it here.
    cost = float(household.config.household.child_rearing_cost)
    if cost > 0 and not household.child_cost_covered:
        _ = savings_bank.withdraw_savings(household, cost)
        household.child_cost_covered = True


def decide_household_formation_event(
    household: Household,
    *,
    savings_bank: SavingsBank,
    rng: _RNG,
) -> HouseholdFormationEvent | None:
    if household.growth_phase and household.growth_counter >= household.growth_threshold:
        # Limit generations if configured.
        if int(household.generation) < int(household.max_generation):
            return HouseholdFormationEvent(kind="split")

    # Natural births: probabilistic household-formation based on age,
    # income and savings/wealth.
    if int(household.generation) >= int(household.max_generation):
        return None

    p_daily = fertility_probability_daily(household=household, savings_bank=savings_bank)
    if p_daily > 0 and rng.random() < p_daily:
        return HouseholdFormationEvent(kind="birth")
    return None


def apply_household_formation_event(
    household: Household,
    event: HouseholdFormationEvent | None,
    *,
    savings_bank: SavingsBank,
) -> Household | None:
    if event is None:
        return None
    if event.kind == "split":
        return split_household(household=household, savings_bank=savings_bank)
    if event.kind == "birth":
        return birth_new_household(household=household, savings_bank=savings_bank)
    raise ValueError(f"Unknown HouseholdFormationEvent.kind: {event.kind!r}")


def handle_demographics(
    household: Household,
    current_step: int,
    *,
    clock: SimulationClock,
    savings_bank: SavingsBank,
    rng: _RNG,
) -> HouseholdFormationEvent | None:
    """Demographics pipeline: aging + lifecycle state + birth decisions.

    The returned event is *deferred* and must be applied after month-end
    bookkeeping, to preserve the legacy ordering (saving happens before
    household formation).

    Referenz: doc/issues.md Abschnitt 4 → "Gründliches Refaktorieren kritischer Stellen".
    """

    _ = clock  # keep explicit in the public interface (future-proof)
    _ = current_step

    advance_age(household=household)
    update_growth_state(household=household, savings_bank=savings_bank)
    update_growth_counter_and_buffer_child_cost(household=household, savings_bank=savings_bank)

    event = decide_household_formation_event(
        household=household, savings_bank=savings_bank, rng=rng
    )

    # Aging / lifecycle end (handled by scheduler; we only log here)
    if household.age_days >= household.max_age_days:
        log(f"Household {household.unique_id}: reached max age.", level="INFO")

    return event


# ---------------------------------------------------------------------------
# Class-based wrapper (used by household_agent.py component delegation)
# ---------------------------------------------------------------------------


class DemographyComponent:
    """Wraps the function-based demography logic as a component attached to a Household."""

    __slots__ = ("_household",)

    def __init__(self, household: Household) -> None:
        self._household = household
        # Ensure demographic state attributes exist on the household
        if not hasattr(household, "growth_phase"):
            household.growth_phase = False
        if not hasattr(household, "growth_counter"):
            household.growth_counter = 0
        if not hasattr(household, "growth_threshold"):
            household.growth_threshold = int(
                getattr(household.config.household, "growth_threshold", 12)
            )
        if not hasattr(household, "_fertility_p_daily_cache"):
            household._fertility_p_daily_cache = {}
        if not hasattr(household, "_fertility_cache_bin_size"):
            household._fertility_cache_bin_size = float(
                getattr(household.config.household, "fertility_cache_bin_size", 100.0)
            )
        if not hasattr(household, "_fertility_cache_max_size"):
            household._fertility_cache_max_size = int(
                getattr(household.config.household, "fertility_cache_max_size", 1000)
            )

    def split_household(self, *, savings_bank: SavingsBank) -> Household | None:
        return split_household(self._household, savings_bank=savings_bank)

    def _fertility_probability_daily(self, *, savings_bank: SavingsBank) -> float:
        return fertility_probability_daily(self._household, savings_bank=savings_bank)

    def _birth_new_household(self, *, savings_bank: SavingsBank) -> Household | None:
        return birth_new_household(self._household, savings_bank=savings_bank)

    def _decide_household_formation_event(
        self,
        *,
        savings_bank: SavingsBank,
        rng: _RNG = _random_module,
    ) -> HouseholdFormationEvent | None:
        return decide_household_formation_event(self._household, savings_bank=savings_bank, rng=rng)

    def _apply_household_formation_event(
        self,
        event: HouseholdFormationEvent | None,
        *,
        savings_bank: SavingsBank,
    ) -> Household | None:
        return apply_household_formation_event(self._household, event, savings_bank=savings_bank)

    def handle_demographics(
        self,
        current_step: int,
        *,
        clock: SimulationClock,
        savings_bank: SavingsBank,
        rng: _RNG = _random_module,
    ) -> HouseholdFormationEvent | None:
        return handle_demographics(
            self._household,
            current_step,
            clock=clock,
            savings_bank=savings_bank,
            rng=rng,
        )
