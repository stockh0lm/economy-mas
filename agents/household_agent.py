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
from typing import TYPE_CHECKING

from config import CONFIG_MODEL, SimulationConfig
from logger import log
from sim_clock import SimulationClock

from .base_agent import BaseAgent

if TYPE_CHECKING:
    from .retailer_agent import RetailerAgent
    from .savings_bank_agent import SavingsBank


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
        self.income: float = float(income if income is not None else self.config.household.base_income)
        self.land_area: float = float(land_area if land_area is not None else 0.0)
        self.environmental_impact: float = float(environmental_impact if environmental_impact is not None else 0.0)

        # Lifecycle
        # Internal time-base: simulation steps are days.
        self.age_days: int = 0
        self.max_age_years: int = int(self.config.household.max_age)
        self.max_age_days: int = int(self.max_age_years * getattr(self.config.time, "days_per_year", 360))

        # Backwards-compatible: expose age as whole years.
        self.age: int = 0
        self.max_age: int = self.max_age_years
        # Generation bookkeeping: start at 1 for initial households.
        self.generation: int = 1
        self.max_generation: int = self.config.household.max_generation

        # Labor
        self.employed: bool = False
        self.current_wage: float | None = None

        # Consumption / phase
        self.growth_phase: bool = False
        self.growth_counter: int = 0
        self.growth_threshold: int = self.config.household.growth_threshold
        self.consumption: float = 0.0
        self.consumption_history: list[float] = []  # rolling window
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
        save_rate = float(getattr(self.config.household, "savings_rate", 0.0))
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
        buffer = float(getattr(self.config.household, "transaction_buffer", 0.0))
        max_affordable = max(0.0, float(self.sight_balance) - buffer)
        if max_affordable <= 0:
            self.last_month_saved = 0.0
            return 0.0

        saved_amount = min(max_affordable, surplus * save_rate)
        if saved_amount <= 0:
            self.last_month_saved = 0.0
            return 0.0

        self.sight_balance -= saved_amount

        if savings_bank is None:
            self.local_savings += saved_amount
        else:
            savings_bank.deposit_savings(self, saved_amount)

        self.last_month_saved = float(saved_amount)
        log(f"Household {self.unique_id}: Saved {saved_amount:.2f}.", level="INFO")
        return float(saved_amount)


    def _repay_savings_loans(self, savings_bank: SavingsBank | None) -> float:
        """Repay part of outstanding savings-bank loans from checking."""
        if savings_bank is None:
            return 0.0

        if self.unique_id not in savings_bank.active_loans:
            return 0.0
        outstanding = float(savings_bank.active_loans.get(self.unique_id, 0.0))
        if outstanding <= 0:
            return 0.0

        repay_budget = max(0.0, self.sight_balance) * float(self.config.household.loan_repayment_rate)
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
    def consume(self, consumption_rate: float, retailers: list[RetailerAgent]) -> float:
        # If no retailers are present, we simply can't consume this step.
        # This should not reset growth lifecycle flags.
        if consumption_rate <= 0 or not retailers:
            self.consumption = 0.0
            return 0.0

        budget = self.sight_balance * consumption_rate
        if budget <= 0:
            self.consumption = 0.0
            return 0.0

        retailer = random.choice(retailers)
        result = retailer.sell_to_household(self, budget)
        spent = result.sale_value
        self.consumption = spent
        self.consumption_this_month += float(spent)
        self.last_consumption += float(spent)

        # Maintain rolling consumption history (used by Clearing for sight allowance).
        self.consumption_history.append(float(spent))
        window = int(getattr(self.config.clearing, 'sight_allowance_window_days', 30))
        if window > 0 and len(self.consumption_history) > window:
            self.consumption_history = self.consumption_history[-window:]

        return spent

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
                float(self.sight_balance) - float(getattr(self.config.household, "transaction_buffer", 0.0)),
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
            child.region_id = getattr(self, "region_id", "region_0")
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
        child.region_id = getattr(self, "region_id", "region_0")
        child.generation = int(self.generation + 1)
        child.sight_balance = float(from_bank + from_local)

        # Reset parent's growth bookkeeping
        self.growth_phase = False
        self.growth_counter = 0
        self.child_cost_covered = False

        return child

    # --- Lifecycle / step ---
    def step(
        self,
        current_step: int,
        *,
        clock: SimulationClock,
        savings_bank: "SavingsBank",
        retailers: list["RetailerAgent"] | None = None,
    ) -> "Household | None":
        """Run one household step.

        Returns:
            - A newly created Household when a split occurs.
            - None otherwise.
        """
        # Advance time
        self.age_days += 1
        days_per_year = int(getattr(self.config.time, "days_per_year", 360))
        self.age = self.age_days // max(1, days_per_year)

        # Determine growth phase.
        # Primary trigger: total savings (local + SavingsBank account).
        bank_savings = float(savings_bank.savings_accounts.get(self.unique_id, 0.0))
        total_savings = float(self.local_savings) + bank_savings

        # Secondary trigger: sustained disposable sight balances when saving is low.
        # This prevents a systemic "no growth" outcome when savings_rate=0.
        disposable_sight = max(0.0, float(self.sight_balance) - float(self.config.household.transaction_buffer))
        wealth_trigger = float(getattr(self.config.household, "sight_growth_trigger", 0.0) or 0.0)
        if wealth_trigger <= 0:
            # Default heuristic: 5x base_income
            wealth_trigger = 5.0 * float(self.config.household.base_income)

        if total_savings >= float(self.config.household.savings_growth_trigger) or disposable_sight >= wealth_trigger:
            self.growth_phase = True
            self.child_cost_covered = False
        else:
            self.growth_phase = False

        if self.growth_phase:
            self.growth_counter += 1
            # Align with tests: withdraw the child-rearing amount into checking and
            # mark the cost as covered, but don't spend it here.
            cost = float(self.config.household.child_rearing_cost)
            if cost > 0 and not self.child_cost_covered:
                _ = savings_bank.withdraw_savings(self, cost)
                self.child_cost_covered = True
        else:
            self.growth_counter = 0

        self._repay_savings_loans(savings_bank)

        rate = (
            self.config.household.consumption_rate_growth
            if self.growth_phase
            else self.config.household.consumption_rate_normal
        )
        if retailers:
            self.consume(rate, retailers)

        # Monthly saving decision happens deterministically on month-end.
        if clock.is_month_end(current_step):
            self.save(savings_bank)

        newborn: Household | None = None
        if self.growth_phase and self.growth_counter >= self.growth_threshold:
            # Limit generations if configured.
            if int(self.generation) < int(self.max_generation):
                newborn = self.split_household(savings_bank=savings_bank)

        # Aging / lifecycle end (handled by scheduler; we only log here)
        if self.age_days >= self.max_age_days:
            log(f"Household {self.unique_id}: reached max age.", level="INFO")

        return newborn
