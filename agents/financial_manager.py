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
        if hasattr(self.household, "sight_balance"):
            self.household.sight_balance += credited_amount
        else:
            self.household.checking_account += credited_amount

        self._record_transaction("income", credited_amount)
        log(
            f"Household {self.household.unique_id} received income: {credited_amount:.2f}. "
            f"Checking account now: {getattr(self.household, 'sight_balance', self.household.checking_account):.2f}.",
            level="INFO",
        )
        return credited_amount

    def manage_consumption(self, rate: float, companies: list | None = None) -> float:
        """Manage household consumption.

        Legacy behavior: if `companies` are passed, this method used to buy directly
        from Company.sell_to_household (now forbidden in the Warengeld model).

        Current behavior:
        - If no suppliers are passed, fall back to the legacy pure-debit path.
        - If suppliers are passed, they must be Retailer-like agents providing
          `sell_to_household(household, budget)`; this keeps the Warengeld goods cycle.
        """
        if companies is None or len(companies) == 0:
            return self._consume_legacy(rate)

        balance = float(getattr(self.household, "sight_balance", self.household.checking_account))
        consumption_budget = balance * rate
        if consumption_budget <= 0:
            return 0.0

        import random
        supplier = random.choice(companies)
        if not hasattr(supplier, "sell_to_household"):
            return 0.0

        result = supplier.sell_to_household(self.household, consumption_budget)
        spent = float(getattr(result, "sale_value", result))

        self._record_transaction("consumption", -spent)
        log(
            f"Household {self.household.unique_id} consumed goods for {spent:.2f}. "
            f"Checking account now: {getattr(self.household, 'sight_balance', self.household.checking_account):.2f}.",
            level="INFO",
        )
        return spent

    def _consume_legacy(self, consumption_rate: float) -> float:
        consumption_amount = float(getattr(self.household, "sight_balance", self.household.checking_account)) * consumption_rate
        if hasattr(self.household, "sight_balance"):
            self.household.sight_balance -= consumption_amount
        else:
            self.household.checking_account -= consumption_amount

        self._record_transaction("consumption", -consumption_amount)
        log(
            f"Household {self.household.unique_id} consumed goods worth: {consumption_amount:.2f}. "
            f"Checking account now: {getattr(self.household, 'sight_balance', self.household.checking_account):.2f}.",
            level="INFO",
        )
        return consumption_amount

    def optimize_savings(self, savings_bank: SavingsBank | None = None) -> float:
        """Move all remaining sight balance into savings.

        Legacy helper. Uses `local_savings` if no bank is provided.
        """
        balance = float(getattr(self.household, "sight_balance", self.household.checking_account))
        if hasattr(self.household, "sight_balance"):
            self.household.sight_balance = 0.0
        else:
            self.household.checking_account = 0.0

        saved_amount = balance
        if saved_amount <= 0:
            return 0.0

        if savings_bank is None:
            self.household.local_savings += saved_amount
            self._record_transaction("savings", saved_amount)
            log(
                f"Household {self.household.unique_id} saved: {saved_amount:.2f}. "
                f"Total local savings now: {self.household.local_savings:.2f}.",
                level="INFO",
            )
            return saved_amount

        deposited = savings_bank.deposit_savings(self.household, saved_amount)
        overflow = saved_amount - deposited

        if overflow > 0:
            self.household.local_savings += overflow
            self._record_transaction("local_savings", overflow)

        self._record_transaction("bank_savings", deposited)
        log(
            f"Household {self.household.unique_id} deposited {deposited:.2f} to SavingsBank "
            f"and kept {overflow:.2f} as local savings. "
            f"Total local savings now: {self.household.local_savings:.2f}.",
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
            from_bank = savings_bank.withdraw_savings(self.household, remaining)
            withdrawn += from_bank
            remaining -= from_bank
            if from_bank > 0:
                self._record_transaction("bank_withdrawal", from_bank)

        # Use local savings if needed
        if remaining > 0 and self.household.local_savings > 0:
            draw = min(remaining, self.household.local_savings)
            self.household.local_savings -= draw
            if hasattr(self.household, "sight_balance"):
                self.household.sight_balance += draw
            else:
                self.household.checking_account += draw
            withdrawn += draw
            remaining -= draw
            if draw > 0:
                self._record_transaction("local_withdrawal", draw)

        # Note: SavingsBank.withdraw_savings already credits the household's checking account.
        # Only local savings withdrawals should be moved to checking (handled above).

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
        repay_budget = min(float(repay_budget), float(outstanding))
        if repay_budget <= 0:
            return 0.0

        # Always deduct from checking on the household side (tests assert this).
        self.household.checking_account -= repay_budget

        repaid = 0.0
        if hasattr(savings_bank, "receive_loan_repayment"):
            repaid = float(savings_bank.receive_loan_repayment(self.household, repay_budget))
        elif hasattr(savings_bank, "repayment"):
            repaid = float(savings_bank.repayment(self.household, repay_budget))
        else:
            repaid = repay_budget

        # If the bank API returned a different amount, reconcile the difference.
        if repaid != repay_budget:
            self.household.checking_account += (repay_budget - repaid)

        if repaid > 0:
            self._record_transaction("loan_repayment", -repaid)

        return float(repaid)

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
        return float(self.household.local_savings) + float(bank_holdings)

    def get_financial_health_score(self) -> float:
        """
        Calculate a financial health score (0-1) for the household.

        Returns:
            Financial health score
        """
        total_assets = float(getattr(self.household, "sight_balance", self.household.checking_account)) + float(self.household.local_savings)
        income_stability = min(1.0, self.household.income / 100.0)
        health_score = min(1.0, total_assets / 1000.0) * 0.6 + income_stability * 0.4
        return health_score

    def _record_transaction(self, transaction_type: str, amount: float) -> None:
        """
        Record a financial transaction for tracking and analysis.

        Args:
            transaction_type: Type of transaction
            amount: Transaction amount (positive for income, negative for expenses)
        """
        balance = float(getattr(self.household, "sight_balance", self.household.checking_account))
        transaction_record = {
            "step": getattr(self.household, "age", 0),
            "type": transaction_type,
            "amount": amount,
            "balance_after": balance + float(self.household.local_savings),
            "checking": balance,
            "savings": float(self.household.local_savings),
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
            "checking_account": float(getattr(self.household, "sight_balance", self.household.checking_account)),
            "savings": float(self.household.local_savings),
            "income": self.household.income,
            "financial_health_score": self.get_financial_health_score(),
            "recent_transactions": self.get_financial_history(5),
        }
