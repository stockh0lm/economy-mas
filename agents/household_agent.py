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

import random
from collections import deque
import numpy as np


_DEFAULT_NP_RNG = np.random.default_rng()
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, Sequence

from config import CONFIG_MODEL, SimulationConfig
from logger import log
from sim_clock import SimulationClock

from .base_agent import BaseAgent

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


@dataclass(frozen=True, slots=True)
class ConsumptionPlan:
    """Pure consumption plan (no side-effects).

    This object is intentionally small and stable so it can be unit-tested
    in isolation (Ref: doc/issues.md Abschnitt 4 – Refactoring Household.step).
    """

    budget: float
    retailer: "RetailerAgent | None"


@dataclass(frozen=True, slots=True)
class HouseholdFormationEvent:
    """Deferred demographic event describing household formation."""

    kind: str  # "split" | "birth"


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

        # Consumption / phase
        self.growth_phase: bool = False
        self.growth_counter: int = 0
        self.growth_threshold: int = self.config.household.growth_threshold
        self.consumption: float = 0.0
        # Rolling consumption window used by `metrics.apply_sight_decay`.
        # Performance: deque avoids per-step list slicing.
        # Referenz: doc/issues.md Abschnitt 5 → Performance-Optimierung nach Profiling-Analyse
        window = int(self.config.clearing.sight_allowance_window_days)
        self.consumption_history = deque(maxlen=max(0, window))

        # Fertility probability cache (daily hotpath).
        # Keyed by (age_years, income_bin, wealth_bin) to keep cache hits high.
        self._fertility_p_daily_cache: dict[tuple[int, int, int], float] = {}
        self._fertility_cache_bin_size: float = max(
            10.0,
            0.05 * float(self.config.household.savings_growth_trigger),
        )
        self._fertility_cache_max_size: int = 4096
        self.investments: float = 0.0
        self.assets: float = 0.0

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
        """Backwards-compatible 'savings' metric.

        Returns total household savings = local_savings + SavingsBank deposits
        (if we have a SavingsBank reference attached by the scheduler).

        This keeps household_metrics meaningful when savings are held at the bank
        (which is the Warengeld-consistent model).
        """
        bank_part = 0.0
        if self._savings_bank_ref is not None:
            bank_part = float(self._savings_bank_ref.savings_accounts.get(self.unique_id, 0.0))
        return float(self.local_savings + bank_part)

    @savings.setter
    def savings(self, value: float) -> None:
        # Setter kept only for older tests; it maps to local_savings.
        self.local_savings = float(value)

    @property
    def savings_balance(self) -> float:
        """Balance of savings deposits at the SavingsBank.

        Note: This class does not hold the SavingsBank reference; callers should
        use `SavingsBank.get_household_savings(household)` for the authoritative
        value.

        We keep this property for typing/clarity in generic accounting code.
        """
        return float(self.local_savings)

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

    # --- Savings bank interactions ---

    def save(self, savings_bank: SavingsBank | None) -> float:
        """Move part of monthly surplus into savings.

        We interpret saving as allocating a fraction of the *monthly surplus*
        (income received during the month minus consumption during the month)
        into SavingsBank deposits at month-end.

        The scheduler controls *when* this method is allowed to save (month-end).
        """
        save_rate = float(self.config.household.savings_rate)
        save_rate = max(0.0, min(1.0, save_rate))

        income = float(self.income_received_this_month)
        consumption = float(self.consumption_this_month)

        # Month-end snapshot (kept after we reset the counters)
        self.last_month_income = income
        self.last_month_consumption = consumption

        # Monthly surplus = income received - consumption during month.
        surplus = max(0.0, income - consumption)

        # Reset counters for the next month.
        self.income_received_this_month = 0.0
        self.consumption_this_month = 0.0
        self.last_income_received = 0.0
        self.last_consumption = 0.0

        if save_rate <= 0 or surplus <= 0:
            self.last_month_saved = 0.0
            return 0.0

        # Keep a small liquid buffer.
        buffer = float(self.config.household.transaction_buffer)
        max_affordable = max(0.0, float(self.sight_balance) - buffer)
        if max_affordable <= 0:
            self.last_month_saved = 0.0
            return 0.0

        saved_amount = min(max_affordable, surplus * save_rate)
        if saved_amount <= 0:
            self.last_month_saved = 0.0
            return 0.0

        deposited: float
        if savings_bank is None:
            # Cash-at-home savings.
            self.sight_balance -= saved_amount
            self.local_savings += saved_amount
            deposited = float(saved_amount)
        else:
            # Banked savings: cap may bind, so only deduct what was actually booked.
            deposited = float(savings_bank.deposit_savings(self, saved_amount))
            self.sight_balance -= deposited

        self.last_month_saved = float(deposited)
        log(f"Household {self.unique_id}: Saved {deposited:.2f}.", level="INFO")
        return float(deposited)

    def _repay_savings_loans(self, savings_bank: SavingsBank | None) -> float:
        """Repay part of outstanding savings-bank loans from checking."""
        if savings_bank is None:
            return 0.0

        if self.unique_id not in savings_bank.active_loans:
            return 0.0
        outstanding = float(savings_bank.active_loans.get(self.unique_id, 0.0))
        if outstanding <= 0:
            return 0.0

        repay_budget = max(0.0, self.sight_balance) * float(
            self.config.household.loan_repayment_rate
        )
        paid = savings_bank.receive_loan_repayment(self, repay_budget)
        if paid > 0:
            log(f"Household {self.unique_id}: Repaid {paid:.2f}.", level="INFO")
        return paid

    def _handle_childrearing_costs(self, savings_bank: SavingsBank | None) -> float:
        """Withdraw savings to cover a one-off child cost during growth.

        Preference order:
        1) SavingsBank (if provided)
        2) local savings (`self.savings`)
        """
        if not self.growth_phase or self.child_cost_covered:
            return 0.0

        cost = float(self.config.household.child_rearing_cost)
        if self.sight_balance >= cost:
            self.sight_balance -= cost
            self.child_cost_covered = True
            return 0.0

        need = cost - self.sight_balance
        withdrawn = 0.0
        if savings_bank is not None:
            withdrawn = savings_bank.withdraw_savings(self, need)
        else:
            withdrawn = min(need, max(0.0, self.local_savings))
            self.local_savings -= withdrawn
            self.sight_balance += withdrawn

        # If bank withdrawal happened, SavingsBank already credited checking via withdraw_savings()
        if self.sight_balance >= cost:
            self.sight_balance -= cost
            self.child_cost_covered = True

        return withdrawn

    # --- Consumption ---
    def _push_consumption_history(self, spent: float) -> None:
        """Append to the rolling consumption history.

        Performance note:
        - With a deque this is O(1) and avoids per-step list slicing.
        """

        window = int(self.config.clearing.sight_allowance_window_days)
        if window <= 0:
            return

        ch = self.consumption_history
        # If someone replaced the deque with a list in a test, stay compatible.
        if isinstance(ch, deque):
            if ch.maxlen != window:
                ch = deque(ch, maxlen=window)
                self.consumption_history = ch
            ch.append(spent)
            return

        # List fallback
        ch.append(spent)
        if len(ch) > window:
            del ch[:-window]

    def _record_consumption(self, spent: float) -> None:
        """Centralized bookkeeping for consumption side-effects."""

        spent_f = float(spent)
        self.consumption = spent_f
        self.consumption_this_month += spent_f
        self.last_consumption += spent_f
        self._push_consumption_history(spent_f)

    def build_consumption_plan(
        self,
        *,
        consumption_rate: float,
        retailers: Sequence["RetailerAgent"],
        rng: _RNG = random,
    ) -> ConsumptionPlan:
        """Create a pure consumption plan.

        This method is intentionally side-effect free so it can be unit-tested
        in isolation.

        Referenz: doc/issues.md Abschnitt 4 → "Gründliches Refaktorieren".
        """

        if consumption_rate <= 0 or not retailers:
            return ConsumptionPlan(budget=0.0, retailer=None)

        budget = float(self.sight_balance) * float(consumption_rate)
        if budget <= 0:
            return ConsumptionPlan(budget=0.0, retailer=None)

        # Keep selection deterministic for tests by allowing an injected RNG.
        retailer = rng.choice(retailers)
        return ConsumptionPlan(budget=float(budget), retailer=retailer)

    def _execute_consumption_plan(self, plan: ConsumptionPlan) -> float:
        """Execute a previously created consumption plan (with side effects)."""

        if plan.budget <= 0 or plan.retailer is None:
            self._record_consumption(0.0)
            return 0.0

        result = plan.retailer.sell_to_household(self, plan.budget)
        spent = float(result.sale_value)
        self._record_consumption(spent)
        return spent

    def consume(
        self,
        consumption_rate: float,
        retailers: Sequence["RetailerAgent"],
        *,
        rng: _RNG = random,
    ) -> float:
        """Spend on goods from retailers.

        The heavy logic is split into:
        - `build_consumption_plan` (pure)
        - `_execute_consumption_plan` (side effects)
        """

        # Fast-path: avoid per-step plan creation when no consumption is possible.
        if consumption_rate <= 0 or not retailers:
            self._record_consumption(0.0)
            return 0.0

        plan = self.build_consumption_plan(
            consumption_rate=consumption_rate,
            retailers=retailers,
            rng=rng,
        )
        return self._execute_consumption_plan(plan)

    @staticmethod
    def batch_consume(
        households: Sequence["Household"],
        retailers: Sequence["RetailerAgent"],
        *,
        rng: "np.random.Generator | None" = None,
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
                h._record_consumption(0.0)
            return [0.0] * n

        gen = rng or _DEFAULT_NP_RNG

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
                h._record_consumption(0.0)
                continue
            retailer = retailers[int(idxs[i])]
            sale = retailer.sell_to_household(h, budget)
            spent = float(sale.sale_value)
            h._record_consumption(spent)
            spent_out[i] = spent

        return spent_out

    @staticmethod
    def batch_step(
        households: Sequence["Household"],
        current_step: int,
        *,
        clock: "SimulationClock",
        savings_bank: "SavingsBank",
        retailers: Sequence["RetailerAgent"],
        rng: "np.random.Generator | None" = None,
        py_rng: _RNG = random,
    ) -> list["Household"]:
        """Run one full step for a *group* of households sharing the same market.

        Keeps semantics aligned with `Household.step`, but uses `batch_consume`
        to remove the biggest per-agent overhead in the daily hot loop.

        Referenz (explizit): doc/issues.md Abschnitt 5 → Performance-Optimierung
        nach Profiling-Analyse.
        """

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
        for h, ev in zip(households, events):
            if ev is None:
                continue
            nb = h._apply_household_formation_event(ev, savings_bank=savings_bank)
            if nb is not None:
                newborns.append(nb)

        return newborns

    # --- Household splitting ---
    def split_household(self, *, savings_bank: "SavingsBank") -> "Household | None":
        """Create a new household (child) funded from this household's savings.

        This is the canonical replacement for the legacy top-level `household_agent.py`
        behavior. It is designed to be Warengeld-consistent:
        - No money creation: funding comes from withdrawing existing savings OR
          splitting existing sight balances.

        Returns the new Household instance if a split happened, else None.
        """

        # Total savings = local + SavingsBank deposits
        bank_savings = float(savings_bank.savings_accounts.get(self.unique_id, 0.0))
        local_savings = float(self.local_savings)
        total_savings = bank_savings + local_savings

        # If we don't have savings, we can still split by allocating part of our
        # disposable sight balance to the child (this is a pure transfer).
        if total_savings <= 0:
            disposable = max(
                0.0,
                float(self.sight_balance)
                - float(self.config.household.transaction_buffer),
            )
            if disposable <= 0:
                return None
            transfer = 0.5 * disposable
            if transfer <= 0:
                return None
            # Deduct from parent sight balance.
            self.sight_balance -= transfer

            child = Household(
                unique_id=f"{self.unique_id}_child_{self.generation + 1}",
                income=self.income,
                land_area=self.land_area,
                environmental_impact=self.environmental_impact,
                config=self.config,
            )
            child.region_id = self.region_id
            child.generation = int(self.generation + 1)
            child.sight_balance = float(transfer)

            self.growth_phase = False
            self.growth_counter = 0
            self.child_cost_covered = False
            return child

        transfer = 0.8 * total_savings
        if transfer <= 0:
            return None

        # Withdraw preferentially from SavingsBank, then from local.
        from_bank = 0.0
        if bank_savings > 0:
            from_bank = savings_bank.withdraw_savings(self, min(bank_savings, transfer))

        remaining = max(0.0, transfer - from_bank)
        from_local = min(remaining, max(0.0, local_savings))
        self.local_savings = max(0.0, local_savings - from_local)

        child = Household(
            unique_id=f"{self.unique_id}_child_{self.generation + 1}",
            income=self.income,
            land_area=self.land_area,
            environmental_impact=self.environmental_impact,
            config=self.config,
        )
        child.region_id = self.region_id
        child.generation = int(self.generation + 1)
        child.sight_balance = float(from_bank + from_local)

        # Reset parent's growth bookkeeping
        self.growth_phase = False
        self.growth_counter = 0
        self.child_cost_covered = False

        return child

    # --- Fertility / household formation ---
    def _fertility_probability_daily(self, *, savings_bank: "SavingsBank") -> float:
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

        cfg = self.config.household
        base_annual = float(cfg.fertility_base_annual)
        if base_annual <= 0.0:
            return 0.0

        age = int(self.age)
        amin = int(cfg.fertility_age_min)
        amax = int(cfg.fertility_age_max)
        if age < amin or age > amax:
            return 0.0

        bank_savings = float(savings_bank.savings_accounts.get(self.unique_id, 0.0))
        wealth = float(self.sight_balance) + float(self.local_savings) + bank_savings

        # Cache: (age_years, income_bin, wealth_bin)
        bin_size = float(self._fertility_cache_bin_size)
        wealth_bin = int(wealth / bin_size) if bin_size > 0 else int(wealth)
        income_bin = int(float(self.income) * 10.0)  # 0.1 precision
        key = (age, income_bin, wealth_bin)
        cached = self._fertility_p_daily_cache.get(key)
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
        income_rel = float(self.income) / base_income
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

        days_per_year = float(self.config.time.days_per_year)
        annual = base_annual * age_factor * income_factor * wealth_factor
        daily = annual / days_per_year if days_per_year > 0 else annual
        if daily < 0.0:
            daily = 0.0
        elif daily > 1.0:
            daily = 1.0

        cache = self._fertility_p_daily_cache
        if len(cache) > self._fertility_cache_max_size:
            cache.clear()
        cache[key] = daily
        return daily

    def _birth_new_household(self, *, savings_bank: "SavingsBank") -> "Household | None":
        """Create a newborn household funded by a transfer from the parent.

        The transfer follows a strict *no money creation* rule:
        - take from disposable sight first
        - then local savings
        - finally withdraw from SavingsBank deposits
        """

        cfg = self.config.household
        share = float(cfg.birth_endowment_share)
        if share <= 0:
            return None

        bank_savings = float(savings_bank.savings_accounts.get(self.unique_id, 0.0))
        wealth = float(self.sight_balance) + float(self.local_savings) + bank_savings

        buffer = float(cfg.transaction_buffer)
        # Do not drain the household below a small transactional buffer.
        transferable_total = max(0.0, wealth - buffer)
        desired = share * transferable_total
        if desired <= 0:
            return None

        remaining = desired

        # 1) Sight balance (keep buffer)
        disposable_sight = max(0.0, float(self.sight_balance) - buffer)
        from_sight = min(disposable_sight, remaining)
        if from_sight > 0:
            self.sight_balance -= from_sight
            remaining -= from_sight

        # 2) Local savings
        from_local = min(max(0.0, float(self.local_savings)), remaining)
        if from_local > 0:
            self.local_savings -= from_local
            remaining -= from_local

        # 3) SavingsBank deposits (withdraw -> sight -> transfer)
        if remaining > 0 and bank_savings > 0:
            withdrawn = savings_bank.withdraw_savings(self, min(bank_savings, remaining))
            if withdrawn > 0:
                # withdraw_savings already credited our sight_balance; transfer it out.
                self.sight_balance -= withdrawn
                remaining -= withdrawn

        transferred = desired - max(0.0, remaining)
        if transferred <= 0:
            return None

        child = Household(
            unique_id=f"{self.unique_id}_child_{self.generation + 1}",
            income=self.income,
            land_area=self.land_area,
            environmental_impact=self.environmental_impact,
            config=self.config,
        )
        child.region_id = self.region_id
        child.generation = int(self.generation + 1)
        child.sight_balance = float(transferred)
        child.age_days = 0

        return child

    # --- Lifecycle / step ---
    def _advance_age(self) -> None:
        self.age_days += 1
        days_per_year = int(self.config.time.days_per_year)
        self.age = self.age_days // max(1, days_per_year)

    def _update_growth_state(self, *, savings_bank: "SavingsBank") -> None:
        # Primary trigger: total savings (local + SavingsBank account).
        bank_savings = float(savings_bank.savings_accounts.get(self.unique_id, 0.0))
        total_savings = float(self.local_savings) + bank_savings

        # Secondary trigger: sustained disposable sight balances when saving is low.
        # This prevents a systemic "no growth" outcome when savings_rate=0.
        disposable_sight = max(
            0.0, float(self.sight_balance) - float(self.config.household.transaction_buffer)
        )
        wealth_trigger = float(self.config.household.sight_growth_trigger)
        if wealth_trigger <= 0:
            # Default heuristic: 5x base_income
            wealth_trigger = 5.0 * float(self.config.household.base_income)

        self.growth_phase = bool(
            total_savings >= float(self.config.household.savings_growth_trigger)
            or disposable_sight >= wealth_trigger
        )
        if self.growth_phase:
            self.child_cost_covered = False

    def _update_growth_counter_and_buffer_child_cost(self, *, savings_bank: "SavingsBank") -> None:
        if not self.growth_phase:
            self.growth_counter = 0
            return

        self.growth_counter += 1
        # Align with tests: withdraw the child-rearing amount into checking and
        # mark the cost as covered, but don't spend it here.
        cost = float(self.config.household.child_rearing_cost)
        if cost > 0 and not self.child_cost_covered:
            _ = savings_bank.withdraw_savings(self, cost)
            self.child_cost_covered = True

    def _decide_household_formation_event(
        self,
        *,
        savings_bank: "SavingsBank",
        rng: _RNG = random,
    ) -> HouseholdFormationEvent | None:
        if self.growth_phase and self.growth_counter >= self.growth_threshold:
            # Limit generations if configured.
            if int(self.generation) < int(self.max_generation):
                return HouseholdFormationEvent(kind="split")

        # Natural births: probabilistic household-formation based on age,
        # income and savings/wealth.
        if int(self.generation) >= int(self.max_generation):
            return None

        p_daily = self._fertility_probability_daily(savings_bank=savings_bank)
        if p_daily > 0 and rng.random() < p_daily:
            return HouseholdFormationEvent(kind="birth")
        return None

    def _apply_household_formation_event(
        self,
        event: HouseholdFormationEvent | None,
        *,
        savings_bank: "SavingsBank",
    ) -> "Household | None":
        if event is None:
            return None
        if event.kind == "split":
            return self.split_household(savings_bank=savings_bank)
        if event.kind == "birth":
            return self._birth_new_household(savings_bank=savings_bank)
        raise ValueError(f"Unknown HouseholdFormationEvent.kind: {event.kind!r}")

    def handle_demographics(
        self,
        current_step: int,
        *,
        clock: SimulationClock,
        savings_bank: "SavingsBank",
        rng: _RNG = random,
    ) -> HouseholdFormationEvent | None:
        """Demographics pipeline: aging + lifecycle state + birth decisions.

        The returned event is *deferred* and must be applied after month-end
        bookkeeping, to preserve the legacy ordering (saving happens before
        household formation).

        Referenz: doc/issues.md Abschnitt 4 → "Gründliches Refaktorieren kritischer Stellen".
        """

        _ = clock  # keep explicit in the public interface (future-proof)
        _ = current_step

        self._advance_age()
        self._update_growth_state(savings_bank=savings_bank)
        self._update_growth_counter_and_buffer_child_cost(savings_bank=savings_bank)

        event = self._decide_household_formation_event(savings_bank=savings_bank, rng=rng)

        # Aging / lifecycle end (handled by scheduler; we only log here)
        if self.age_days >= self.max_age_days:
            log(f"Household {self.unique_id}: reached max age.", level="INFO")

        return event

    def handle_finances(
        self,
        current_step: int,
        *,
        clock: SimulationClock,
        savings_bank: "SavingsBank",
        stage: str,
        is_month_end: bool | None = None,
    ) -> None:
        """Finance pipeline: repayments + month-end saving.

        stage:
            - "pre": before consumption (repay loans)
            - "post": after consumption (save at month-end)

        Referenz: doc/issues.md Abschnitt 4 → "Gründliches Refaktorieren".
        """

        if stage == "pre":
            self._repay_savings_loans(savings_bank)
            return

        if stage == "post":
            month_end = is_month_end if is_month_end is not None else clock.is_month_end(current_step)
            if month_end:
                self.save(savings_bank)
            return

        raise ValueError(f"Unknown stage for handle_finances: {stage!r}")

    def handle_consumption(
        self,
        *,
        retailers: Sequence["RetailerAgent"],
        rng: _RNG = random,
    ) -> float:
        """Consumption decision pipeline."""

        rate = (
            self.config.household.consumption_rate_growth
            if self.growth_phase
            else self.config.household.consumption_rate_normal
        )
        return self.consume(rate, retailers, rng=rng)

    def step(
        self,
        current_step: int,
        *,
        clock: SimulationClock,
        savings_bank: "SavingsBank",
        retailers: list["RetailerAgent"] | None = None,
        is_month_end: bool | None = None,
        rng: _RNG = random,
    ) -> "Household | None":
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
