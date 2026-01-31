"""SavingsBank (Sparkasse) agent.

Specification alignment:
- The Sparkasse does **not** create money.
- It intermediates between savings deposits (savings balances) and loans.
- Lending is constrained by the available savings pool (asset side), not by an
  artificial "liquidity injection". (Initial conditions may still seed a pool.)

Implementation notes:
- We model two stock variables:
  - savings_accounts: household_id -> savings_balance (liability)
  - available_funds: funds available to lend (asset liquidity)
- When lending, available_funds decreases while loan_book increases; savings_accounts stay unchanged.
"""

from __future__ import annotations

from typing import Any

from config import CONFIG_MODEL, SimulationConfig
from logger import log

from .base_agent import BaseAgent


class SavingsBank(BaseAgent):
    def __init__(self, unique_id: str, config: SimulationConfig | None = None) -> None:
        super().__init__(unique_id)
        self.config: SimulationConfig = config or CONFIG_MODEL

        # Liabilities: households' savings balances
        self.savings_accounts: dict[str, float] = {}

        # Assets: funds available to lend (liquid part of savings pool)
        self.available_funds: float = float(self.config.savings_bank.initial_liquidity)

        # Loan book (principal outstanding)
        self.active_loans: dict[str, float] = {}

        # Risk reserve (can be used to absorb write-offs)
        self.risk_reserve: float = float(self.config.savings_bank.initial_liquidity * 0.05)

    # --- Spec vocabulary aliases ---
    @property
    def savings_pool(self) -> float:
        """Total savings deposits (liability side)."""
        return float(self.total_savings)

    @property
    def loan_book(self) -> float:
        """Outstanding principal of the Sparkasse loan book."""
        return float(sum(self.active_loans.values()))


    # --- Backwards-compatible alias ---
    @property
    def liquidity(self) -> float:
        """Alias for available_funds (legacy name used in older code/tests)."""
        return float(self.available_funds)

    @liquidity.setter
    def liquidity(self, value: float) -> None:
        self.available_funds = float(value)

    # --- Savings deposit/withdraw ---
    def deposit_savings(self, household: Any, amount: float) -> float:
        if amount <= 0:
            return 0.0

        hid = str(getattr(household, "unique_id", "household"))
        amount = float(amount)

        # Enforce per-account cap (prevents unbounded accumulation in small sims)
        cap = float(getattr(self.config.savings_bank, "max_savings_per_account", 1e18) or 1e18)
        current = float(self.savings_accounts.get(hid, 0.0))
        depositable = max(0.0, min(amount, cap - current))
        if depositable <= 0:
            return 0.0

        self.savings_accounts[hid] = current + depositable
        self.available_funds += depositable

        log(
            f"SavingsBank: deposit {depositable:.2f} from {hid}. savings_balance={self.savings_accounts[hid]:.2f}",
            level="INFO",
        )
        return depositable

    def withdraw_savings(self, household: Any, amount: float) -> float:
        if amount <= 0:
            return 0.0

        hid = str(getattr(household, 'unique_id', 'household'))
        balance = float(self.savings_accounts.get(hid, 0.0))
        available = min(balance, float(self.available_funds))
        withdrawn = min(float(amount), available)
        if withdrawn <= 0:
            return 0.0

        self.savings_accounts[hid] = balance - withdrawn
        self.available_funds -= withdrawn

        # Credit household sight balance (transfer from savings pool)
        if hasattr(household, 'sight_balance'):
            household.sight_balance = float(household.sight_balance) + withdrawn
        elif hasattr(household, 'checking_account'):
            household.checking_account = float(household.checking_account) + withdrawn
        elif hasattr(household, 'balance'):
            household.balance = float(household.balance) + withdrawn

        log(
            f"SavingsBank: withdraw {withdrawn:.2f} for {hid}. remaining_savings={self.savings_accounts[hid]:.2f}",
            level="INFO",
        )
        return withdrawn

    def get_household_savings(self, household: Any) -> float:
        hid = str(getattr(household, 'unique_id', 'household'))
        return float(self.savings_accounts.get(hid, 0.0))

    # --- Lending ---
    def allocate_credit(self, borrower: Any, amount: float) -> float:
        """Allocate a loan from available savings funds.

        This increases borrower sight balance, decreases available_funds.
        """
        if amount <= 0:
            return 0.0

        amount = float(amount)
        if amount > self.available_funds:
            amount = float(self.available_funds)
        if amount <= 0:
            return 0.0

        bid = str(getattr(borrower, 'unique_id', 'borrower'))
        self.available_funds -= amount
        self.active_loans[bid] = self.active_loans.get(bid, 0.0) + amount

        # Credit borrower
        if hasattr(borrower, 'request_funds_from_bank'):
            borrower.request_funds_from_bank(amount)
        elif hasattr(borrower, 'sight_balance'):
            borrower.sight_balance = float(borrower.sight_balance) + amount
        elif hasattr(borrower, 'balance'):
            borrower.balance = float(borrower.balance) + amount

        log(
            f"SavingsBank: lent {amount:.2f} to {bid}. outstanding={self.active_loans[bid]:.2f}",
            level="INFO",
        )
        return amount

    def receive_loan_repayment(self, borrower: Any, amount: float) -> float:
        if amount <= 0:
            return 0.0
        bid = str(getattr(borrower, 'unique_id', 'borrower'))
        outstanding = float(self.active_loans.get(bid, 0.0))
        if outstanding <= 0:
            return 0.0

        # borrower must pay from sight
        if hasattr(borrower, 'sight_balance'):
            sight = float(borrower.sight_balance)
            paid = min(float(amount), sight, outstanding)
            borrower.sight_balance = sight - paid
        elif hasattr(borrower, 'balance'):
            sight = float(borrower.balance)
            paid = min(float(amount), sight, outstanding)
            borrower.balance = sight - paid
        else:
            return 0.0

        self.active_loans[bid] = outstanding - paid
        self.available_funds += paid

        if self.active_loans[bid] <= 1e-9:
            self.active_loans.pop(bid, None)

        log(
            f"SavingsBank: repayment {paid:.2f} from {bid}. remaining={self.active_loans.get(bid,0.0):.2f}",
            level="INFO",
        )
        return paid

    # --- Step (optional interest/default dynamics) ---
    def step(self, current_step: int) -> None:
        # Intentionally minimal: interest/defaults can be added later.
        return

    @property
    def total_savings(self) -> float:
        """Total savings deposits held at the bank (liability side)."""
        return float(sum(self.savings_accounts.values()))

