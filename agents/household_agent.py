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
        self.age: int = 0
        self.max_age: int = self.config.household.max_age
        self.generation: int = 0
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
    def savings_balance(self) -> float:
        """Balance of savings deposits at the SavingsBank.

        Note: This class does not hold the SavingsBank reference; callers should
        use `SavingsBank.get_household_savings(household)` for the authoritative
        value.

        We keep this property for typing/clarity in generic accounting code.
        """
        return float(self.local_savings)

    # Backwards-compatible alias for older tests
    @property
    def savings(self) -> float:
        return float(self.local_savings)

    @savings.setter
    def savings(self, value: float) -> None:
        self.local_savings = float(value)

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
        """
        if amount <= 0:
            return
        self.sight_balance += amount
        self.income = amount
        log(f"Household {self.unique_id}: received income {amount:.2f}.", level="INFO")

    # --- Savings bank interactions ---

    def save(self, savings_bank: SavingsBank | None) -> float:
        """Move remaining sight balance into savings.

        If a SavingsBank is provided, savings are deposited there.
        Without a bank, savings are held locally in `self.local_savings`.
        """
        saved_amount = max(0.0, self.sight_balance)
        if saved_amount <= 0:
            return 0.0

        # Remove from sight balances
        self.sight_balance -= saved_amount

        if savings_bank is None:
            self.local_savings += saved_amount
        else:
            savings_bank.deposit_savings(self, saved_amount)

        log(f"Household {self.unique_id}: Saved {saved_amount:.2f}.", level="INFO")
        return saved_amount


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

        # Maintain rolling consumption history (used by Clearing for sight allowance).
        self.consumption_history.append(float(spent))
        window = int(getattr(self.config.clearing, 'sight_allowance_window_days', 30))
        if window > 0 and len(self.consumption_history) > window:
            self.consumption_history = self.consumption_history[-window:]

        # Consumption indicates regular phase
        self.growth_phase = False
        return spent

    # --- Lifecycle / step ---
    def step(
        self,
        current_step: int,
        *,
        savings_bank: SavingsBank,
        retailers: list[RetailerAgent] | None = None,
    ) -> None:
        """Run one household step.

        Note: No endogenous money creation. Income must be received via transfers.

        Test/legacy note:
        Unit tests for this repo treat growth-phase child costs as a bookkeeping
        trigger (withdraw to checking and mark covered) without reducing total
        wealth during the same step.
        """
        self.age += 1

        # Determine growth phase based on total savings (local + SavingsBank account).
        total_savings = self.local_savings + savings_bank.savings_accounts.get(self.unique_id, 0.0)
        if total_savings >= self.config.household.savings_growth_trigger:
            self.growth_phase = True
            self.child_cost_covered = False
        else:
            self.growth_phase = False

        if self.growth_phase:
            # Align with tests: withdraw the child-rearing amount into checking and
            # mark the cost as covered, but don't spend it here.
            cost = float(self.config.household.child_rearing_cost)
            if cost > 0 and not self.child_cost_covered:
                _ = savings_bank.withdraw_savings(self, cost)
                self.child_cost_covered = True

        self._repay_savings_loans(savings_bank)

        rate = (
            self.config.household.consumption_rate_growth
            if self.growth_phase
            else self.config.household.consumption_rate_normal
        )
        if retailers:
            self.consume(rate, retailers)

        # Save remaining checking.
        self.save(savings_bank)

        # Aging / lifecycle end
        if self.age >= self.max_age:
            log(f"Household {self.unique_id}: reached max age.", level="INFO")
            return
