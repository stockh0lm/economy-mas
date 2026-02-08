"""Household agent.

Warengeld specification alignment:
- Households do **not** create money by themselves.
- Household income is a **transfer** (e.g., wages) from other agents.
- Households buy *goods* from Retailers; these purchases are transfers.
- Savings move sight balances into the SavingsBank pool (no money creation).

This module keeps some legacy features (growth_phase, child costs, savings-bank loans)
used by existing scenarios/tests, but avoids endogenous money creation.
"""

from __future__ import annotations

import os
import random
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import numpy as np

from config import CONFIG_MODEL, SimulationConfig
from logger import log
from sim_clock import SimulationClock

from .base_agent import BaseAgent
from .household.consumption import ConsumptionComponent, ConsumptionPlan
from .household.savings import SavingsComponent
from .household.demography import DemographyComponent, HouseholdFormationEvent

_DEFAULT_NP_RNG = None


def _get_default_np_rng():
    global _DEFAULT_NP_RNG
    if _DEFAULT_NP_RNG is None:
        env_seed = os.getenv("SIM_SEED")
        if env_seed is not None and env_seed != "":
            _DEFAULT_NP_RNG = np.random.default_rng(int(env_seed))
        else:
            _DEFAULT_NP_RNG = np.random.default_rng()
    return _DEFAULT_NP_RNG


if TYPE_CHECKING:
    from .retailer_agent import RetailerAgent
    from .savings_bank_agent import SavingsBank


class _RNG(Protocol):
    """Minimal RNG protocol used for deterministic unit tests.

    We accept either `random` module or an instance of `random.Random`.
    """

    def random(self) -> float:  # pragma: no cover - protocol
        ...

    def choice(self, seq: Sequence[object]) -> object:  # pragma: no cover - protocol
        ...


class Household(BaseAgent):
    def __init__(
        self,
        unique_id: str,
        config: SimulationConfig | None = None,
        income: float | None = None,
        land_area: float | None = None,
        environmental_impact: float | None = None,
    ) -> None:
        super().__init__(unique_id)
        self.config: SimulationConfig = config or CONFIG_MODEL

        # --- Accounts ---
        # Canonical: sight_balance (Sichtguthaben). Keep `checking_account` as a backwards-compatible alias.
        self._sight_balance: float = 0.0

        # Local cash-like savings buffer (should not represent debt).
        # In the Warengeld model, savings are primarily held at the SavingsBank.
        self.local_savings: float = 0.0

        # --- Household attributes ---
        self.income: float = float(
            income if income is not None else self.config.household.base_income
        )
        self.land_area: float = float(land_area if land_area is not None else 0.0)
        self.environmental_impact: float = float(
            environmental_impact if environmental_impact is not None else 0.0
        )

        # Lifecycle
        # Internal time-base: simulation steps are days.
        self.age_days: int = 0
        self.max_age_years: int = int(self.config.household.max_age)
        self.max_age_days: int = int(self.max_age_years * int(self.config.time.days_per_year))

        # Backwards-compatible: expose age as whole years.
        self.age: int = 0
        self.max_age: int = self.max_age_years
        # Generation bookkeeping: start at 1 for initial households.
        self.generation: int = 1
        self.max_generation: int = self.config.household.max_generation

        # Labor
        self.employed: bool = False
        self.current_wage: float | None = None
        # Optional backlink used by the main loop to remove workers cleanly on death.
        self.employer_id: str | None = None

        # Child cost handling
        self.child_cost_covered: bool = False

        # Optional reference used only for reporting aggregate household savings.
        # The authoritative deposits live inside the SavingsBank.
        self._savings_bank_ref: SavingsBank | None = None

        # Monthly accounting (authoritative)
        self.income_received_this_month: float = 0.0
        self.consumption_this_month: float = 0.0

        # Backwards-compatible aliases (deprecated)
        self.last_income_received: float = 0.0
        self.last_consumption: float = 0.0

        # Month-end snapshots (after month counters are reset)
        self.last_month_income: float = 0.0
        self.last_month_consumption: float = 0.0
        self.last_month_saved: float = 0.0

        # Component delegation
        self.consumption_component = ConsumptionComponent(self)
        self.savings_component = SavingsComponent(self)
        self.demography_component = DemographyComponent(self)

        # Legacy properties (deprecated, kept for backwards compatibility)
        self.investments: float = 0.0
        self.assets: float = 0.0

    @property
    def consumption(self) -> float:
        """Backwards-compatible consumption property."""
        return self.consumption_component.consumption

    @consumption.setter
    def consumption(self, value: float) -> None:
        self.consumption_component.consumption = value

    @property
    def consumption_history(self):
        """Backwards-compatible consumption_history property."""
        return self.consumption_component.consumption_history

    @consumption_history.setter
    def consumption_history(self, value):
        self.consumption_component.consumption_history = value

    # --- Balance-sheet vocabulary ---
    @property
    def sight_balance(self) -> float:
        return float(self._sight_balance)

    @sight_balance.setter
    def sight_balance(self, value: float) -> None:
        self._sight_balance = float(value)

    # Backwards-compatible alias
    @property
    def checking_account(self) -> float:
        return float(self._sight_balance)

    @checking_account.setter
    def checking_account(self, value: float) -> None:
        self._sight_balance = float(value)

    @property
    def savings(self) -> float:
        """Backwards-compatible 'savings' metric."""
        return self.savings_component.savings

    @savings.setter
    def savings(self, value: float) -> None:
        # Setter kept only for older tests; it maps to local_savings.
        self.savings_component.savings = value

    @property
    def savings_balance(self) -> float:
        """Balance of savings deposits at the SavingsBank."""
        return self.savings_component.savings_balance

    @property
    def balance(self) -> float:
        """Legacy: total wealth proxy (not a money supply measure)."""
        return float(self.sight_balance + self.local_savings + self.assets)

    # --- Payments ---
    def pay(self, amount: float) -> float:
        """Pay from sight balances, without overdraft.

        Returns the actually paid amount (<= requested).
        """
        if amount <= 0:
            return 0.0
        paid = min(self.sight_balance, amount)
        self.sight_balance -= paid
        return paid

    def receive_income(self, amount: float) -> None:
        """Receive income as a transfer.

        IMPORTANT: This method does not create money by itself; the caller
        must book the corresponding debit on the payer side.

        Note: `self.income` is treated as a baseline/structural income parameter
        (used as household type/template). Wage payments are recorded via
        `self.current_wage` and increases in `sight_balance`, not by mutating
        `self.income` each step.
        """
        if amount <= 0:
            return
        self.sight_balance += amount
        self.income_received_this_month += float(amount)
        self.last_income_received += float(amount)
        log(f"Household {self.unique_id}: received income {amount:.2f}.", level="INFO")

    # --- Component delegation methods ---
    def save(self, savings_bank: SavingsBank | None) -> float:
        """Delegate to savings component."""
        return self.savings_component.save(savings_bank)

    def _repay_savings_loans(self, savings_bank: SavingsBank | None) -> float:
        """Delegate to savings component."""
        return self.savings_component._repay_savings_loans(savings_bank)

    def _handle_childrearing_costs(self, savings_bank: SavingsBank | None) -> float:
        """Delegate to savings component."""
        return self.savings_component._handle_childrearing_costs(savings_bank)

    def build_consumption_plan(
        self,
        *,
        consumption_rate: float,
        retailers: Sequence[RetailerAgent],
        rng: _RNG = random,
    ) -> ConsumptionPlan:
        """Delegate to consumption component."""
        return self.consumption_component.build_consumption_plan(
            consumption_rate=consumption_rate,
            retailers=retailers,
            rng=rng,
        )

    def _execute_consumption_plan(self, plan: ConsumptionPlan) -> float:
        """Delegate to consumption component."""
        return self.consumption_component._execute_consumption_plan(plan)

    def consume(
        self,
        consumption_rate: float,
        retailers: Sequence[RetailerAgent],
        *,
        rng: _RNG = random,
    ) -> float:
        """Delegate to consumption component."""
        return self.consumption_component.consume(consumption_rate, retailers, rng=rng)

    @staticmethod
    def batch_consume(
        households: Sequence[Household],
        retailers: Sequence[RetailerAgent],
        *,
        rng: np.random.Generator | None = None,
    ) -> list[float]:
        """Vectorized consumption execution for many households."""
        # Convert households to consumption components
        consumption_components = [h.consumption_component for h in households]
        return ConsumptionComponent.batch_consume(consumption_components, retailers, rng=rng)

    @staticmethod
    def batch_step(
        households: Sequence[Household],
        current_step: int,
        *,
        clock: SimulationClock,
        savings_bank: SavingsBank,
        retailers: Sequence[RetailerAgent],
        rng: np.random.Generator | None = None,
        py_rng: _RNG = random,
    ) -> list[Household]:
        """Run one full step for a *group* of households sharing the same market."""

        if not households:
            return []

        # Precompute per-day constants once.
        is_month_end = clock.is_month_end(current_step)

        events: list[HouseholdFormationEvent | None] = [None] * len(households)
        for i, h in enumerate(households):
            h._savings_bank_ref = savings_bank
            events[i] = h.handle_demographics(
                current_step,
                clock=clock,
                savings_bank=savings_bank,
                rng=py_rng,
            )
            h.handle_finances(
                current_step,
                clock=clock,
                savings_bank=savings_bank,
                stage="pre",
            )

        Household.batch_consume(households, retailers, rng=rng)

        # Month-end saving happens after consumption (same as `step`).
        if is_month_end:
            for h in households:
                h.save(savings_bank)

        newborns: list[Household] = []
        for h, ev in zip(households, events, strict=False):
            if ev is None:
                continue
            nb = h._apply_household_formation_event(ev, savings_bank=savings_bank)
            if nb is not None:
                newborns.append(nb)

        return newborns

    def split_household(self, *, savings_bank: SavingsBank) -> Household | None:
        """Delegate to demography component."""
        return self.demography_component.split_household(savings_bank=savings_bank)

    def _fertility_probability_daily(self, *, savings_bank: SavingsBank) -> float:
        """Delegate to demography component."""
        return self.demography_component._fertility_probability_daily(savings_bank=savings_bank)

    def _birth_new_household(self, *, savings_bank: SavingsBank) -> Household | None:
        """Delegate to demography component."""
        return self.demography_component._birth_new_household(savings_bank=savings_bank)

    def _decide_household_formation_event(
        self,
        *,
        savings_bank: SavingsBank,
        rng: _RNG = random,
    ) -> HouseholdFormationEvent | None:
        """Delegate to demography component."""
        return self.demography_component._decide_household_formation_event(
            savings_bank=savings_bank, rng=rng
        )

    def _apply_household_formation_event(
        self,
        event: HouseholdFormationEvent | None,
        *,
        savings_bank: SavingsBank,
    ) -> Household | None:
        """Delegate to demography component."""
        return self.demography_component._apply_household_formation_event(
            event, savings_bank=savings_bank
        )

    def handle_demographics(
        self,
        current_step: int,
        *,
        clock: SimulationClock,
        savings_bank: SavingsBank,
        rng: _RNG = random,
    ) -> HouseholdFormationEvent | None:
        """Delegate to demography component."""
        return self.demography_component.handle_demographics(
            current_step, clock=clock, savings_bank=savings_bank, rng=rng
        )

    def handle_finances(
        self,
        current_step: int,
        *,
        clock: SimulationClock,
        savings_bank: SavingsBank,
        stage: str,
        is_month_end: bool | None = None,
    ) -> None:
        """Delegate to savings component."""
        return self.savings_component.handle_finances(
            current_step,
            clock=clock,
            savings_bank=savings_bank,
            stage=stage,
            is_month_end=is_month_end,
        )

    def handle_consumption(
        self,
        *,
        retailers: Sequence[RetailerAgent],
        rng: _RNG = random,
    ) -> float:
        """Delegate to consumption component."""
        return self.consumption_component.handle_consumption(retailers=retailers, rng=rng)

    def step(
        self,
        current_step: int,
        *,
        clock: SimulationClock,
        savings_bank: SavingsBank,
        retailers: list[RetailerAgent] | None = None,
        is_month_end: bool | None = None,
        rng: _RNG = random,
    ) -> Household | None:
        """Run one household step.

        Returns:
            - A newly created Household when a split occurs.
            - None otherwise.
        """
        retailers_seq: Sequence[RetailerAgent] = retailers or []

        event = self.handle_demographics(
            current_step,
            clock=clock,
            savings_bank=savings_bank,
            rng=rng,
        )
        self.handle_finances(current_step, clock=clock, savings_bank=savings_bank, stage="pre")
        self.handle_consumption(retailers=retailers_seq, rng=rng)

        month_end = is_month_end
        if month_end is None:
            month_end = clock.is_month_end(current_step)
        if month_end:
            # Avoid per-day post-processing overhead (doc/issues.md Abschnitt 5).
            self.handle_finances(
                current_step,
                clock=clock,
                savings_bank=savings_bank,
                stage="post",
                is_month_end=True,
            )

        if event is None:
            return None
        # Apply household formation after bookkeeping.
        return self._apply_household_formation_event(event, savings_bank=savings_bank)
