"""Financial management system for household agents."""

from typing import TYPE_CHECKING
from agents.savings_bank_agent import SavingsBank
from logger import log

if TYPE_CHECKING:
    from agents.household_agent import Household

class FinancialManager:
    """
    Financial management system for household agents.

    Handles income allocation, consumption, savings strategies,
    loan management, and financial planning.
    """

    def __init__(self, household: "Household"):
        """
        Initialize financial manager for a household.

        Args:
            household: The household agent to manage
        """
        self.household = household
        self._financial_history: list[dict] = []

    def process_income(self, amount: float | None = None) -> float:
        """
        Process incoming funds and allocate to checking account.

        Args:
            amount: Optional specific amount (uses household.income if None)

        Returns:
            Amount credited to checking account
        """
        credited_amount = self.household.income if amount is None else amount
        self.household.checking_account += credited_amount

        self._record_transaction("income", credited_amount)
        log(
            f"Household {self.household.unique_id} received income: {credited_amount:.2f}. "
            f"Checking account now: {self.household.checking_account:.2f}.",
            level="INFO",
        )
        return credited_amount

    def manage_consumption(self, rate: float, companies: list | None = None) -> float:
        """
        Manage household consumption based on consumption rate.

        Args:
            rate: Consumption rate (0-1)
            companies: Optional list of companies to purchase from

        Returns:
            Amount spent on consumption
        """
        if companies is None or len(companies) == 0:
            return self._consume_legacy(rate)

        consumption_budget = self.household.checking_account * rate
        if consumption_budget <= 0:
            return 0.0

        # Select a random company to purchase from
        import random
        supplier = random.choice(companies)
        spent = supplier.sell_to_household(self.household, consumption_budget)

        self._record_transaction("consumption", -spent)
        log(
            f"Household {self.household.unique_id} consumed goods for {spent:.2f}. "
            f"Checking account now: {self.household.checking_account:.2f}.",
            level="INFO",
        )
        return spent

    def _consume_legacy(self, consumption_rate: float) -> float:
        """Legacy consumption method without company interaction."""
        consumption_amount = self.household.checking_account * consumption_rate
        self.household.checking_account -= consumption_amount

        self._record_transaction("consumption", -consumption_amount)
        log(
            f"Household {self.household.unique_id} consumed goods worth: {consumption_amount:.2f}. "
            f"Checking account now: {self.household.checking_account:.2f}.",
            level="INFO",
        )
        return consumption_amount

    def optimize_savings(self, savings_bank: SavingsBank | None = None) -> float:
        """
        Optimize savings strategy by moving funds between accounts.

        Args:
            savings_bank: Optional savings bank for deposits

        Returns:
            Total amount saved
        """
        saved_amount = self.household.checking_account
        self.household.checking_account = 0.0

        if saved_amount <= 0:
            return 0.0

        if savings_bank is None:
            # Local savings if no bank available
            self.household.savings += saved_amount
            self._record_transaction("savings", saved_amount)
            log(
                f"Household {self.household.unique_id} saved: {saved_amount:.2f}. "
                f"Total savings now: {self.household.savings:.2f}.",
                level="INFO",
            )
            return saved_amount

        # Bank deposit strategy
        deposited = savings_bank.deposit_savings(self.household, saved_amount)
        overflow = saved_amount - deposited

        if overflow > 0:
            self.household.savings += overflow
            self._record_transaction("local_savings", overflow)

        self._record_transaction("bank_savings", deposited)
        log(
            f"Household {self.household.unique_id} deposited {deposited:.2f} to SavingsBank "
            f"and kept {overflow:.2f} as local savings. "
            f"Total local savings now: {self.household.savings:.2f}.",
            level="INFO",
        )
        return saved_amount

    def handle_childrearing_costs(self, savings_bank: SavingsBank | None) -> float:
        """
        Handle upfront child-rearing costs during growth phase.

        Args:
            savings_bank: Optional savings bank for withdrawals

        Returns:
            Amount withdrawn for child-rearing costs
        """
        if not self.household.growth_phase or self.household.child_cost_covered:
            return 0.0

        required = self.household.child_rearing_cost
        remaining = required
        withdrawn = 0.0

        # Try bank withdrawal first
        if savings_bank is not None and remaining > 0:
            from_bank = savings_bank.give_household_withdrawal(self.household, remaining)
            withdrawn += from_bank
            remaining -= from_bank
            if from_bank > 0:
                self._record_transaction("bank_withdrawal", from_bank)

        # Use local savings if needed
        if remaining > 0 and self.household.savings > 0:
            draw = min(remaining, self.household.savings)
            self.household.savings -= draw
            withdrawn += draw
            remaining -= draw
            if draw > 0:
                self._record_transaction("local_withdrawal", draw)

        # Add to checking account for spending
        if withdrawn > 0:
            self.household.checking_account += withdrawn
            self._record_transaction("childrearing_funds", withdrawn)

        if remaining <= 0:
            self.household.child_cost_covered = True

        return withdrawn

    def repay_savings_loans(self, savings_bank: SavingsBank | None) -> float:
        """
        Manage repayment of savings bank loans.

        Args:
            savings_bank: Optional savings bank for loan repayment

        Returns:
            Amount repaid
        """
        if savings_bank is None:
            return 0.0

        outstanding = savings_bank.active_loans.get(self.household.unique_id, 0.0)
        if outstanding <= 0:
            return 0.0

        disposable = max(0.0, self.household.checking_account)
        if disposable <= 0:
            return 0.0

        repay_budget = disposable * self.household.loan_repayment_rate
        repaid = savings_bank.repayment(self.household, repay_budget)
        self.household.checking_account -= repaid

        if repaid > 0:
            self._record_transaction("loan_repayment", -repaid)

        return repaid

    def get_total_savings(self, savings_bank: SavingsBank | None) -> float:
        """
        Calculate total savings across all accounts.

        Args:
            savings_bank: Optional savings bank

        Returns:
            Total savings amount
        """
        bank_holdings = 0.0
        if savings_bank is not None:
            bank_holdings = savings_bank.savings_accounts.get(self.household.unique_id, 0.0)
        return self.household.savings + bank_holdings

    def get_financial_health_score(self) -> float:
        """
        Calculate a financial health score (0-1) for the household.

        Returns:
            Financial health score
        """
        total_assets = self.household.checking_account + self.household.savings
        income_stability = min(1.0, self.household.income / 100.0)  # Normalized

        # Simple health score calculation
        health_score = min(1.0, total_assets / 1000.0) * 0.6 + income_stability * 0.4
        return health_score

    def _record_transaction(self, transaction_type: str, amount: float) -> None:
        """
        Record a financial transaction for tracking and analysis.

        Args:
            transaction_type: Type of transaction
            amount: Transaction amount (positive for income, negative for expenses)
        """
        transaction_record = {
            "step": getattr(self.household, "age", 0),
            "type": transaction_type,
            "amount": amount,
            "balance_after": self.household.checking_account + self.household.savings,
            "checking": self.household.checking_account,
            "savings": self.household.savings
        }

        self._financial_history.append(transaction_record)

        # Keep history manageable
        if len(self._financial_history) > 100:
            self._financial_history = self._financial_history[-100:]

    def get_financial_history(self, limit: int = 10) -> list[dict]:
        """
        Get recent financial history.

        Args:
            limit: Maximum number of transactions to return

        Returns:
            List of recent financial transactions
        """
        return self._financial_history[-limit:]

    def get_financial_summary(self) -> dict:
        """
        Get a summary of the household's financial situation.

        Returns:
            Financial summary dictionary
        """
        return {
            "checking_account": self.household.checking_account,
            "savings": self.household.savings,
            "income": self.household.income,
            "financial_health_score": self.get_financial_health_score(),
            "recent_transactions": self.get_financial_history(5)
        }
