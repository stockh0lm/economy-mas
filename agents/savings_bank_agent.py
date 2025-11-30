# savings_bank_agent.py
from typing import Protocol, TypeAlias

from config import CONFIG_MODEL, SimulationConfig
from logger import log

from .base_agent import BaseAgent


class HasUniqueID(Protocol):
    """Protocol for agents that have a unique_id field"""

    unique_id: str


class BorrowerAgent(HasUniqueID, Protocol):
    """Protocol for agents that can receive funds from a bank"""

    def request_funds_from_bank(self, amount: float) -> float:
        """Request funds from a bank"""
        ...


# Type aliases for improved readability
AgentID: TypeAlias = str
SavingsMap: TypeAlias = dict[AgentID, float]
LoanMap: TypeAlias = dict[AgentID, float]


class SavingsBank(BaseAgent):
    """
    Manages savings accounts and provides loans to economic agents.

    Enforces savings limits and manages liquidity for the overall economy.
    """

    def __init__(self, unique_id: str, config: SimulationConfig | None = None) -> None:
        """
        Initialize a savings bank with default parameters.

        Args:
            unique_id: Unique identifier for this savings bank
        """
        super().__init__(unique_id)

        # Financial accounts
        self.savings_accounts: SavingsMap = {}  # Maps agent_id to their current savings
        self.total_savings: float = 0.0
        self.active_loans: LoanMap = {}  # Maps borrower_id to their outstanding loan amount

        self.config: SimulationConfig = config or CONFIG_MODEL

        # Configuration parameters
        self.loan_interest_rate: float = self.config.savings_bank.loan_interest_rate
        self.max_savings_per_account: float = self.config.savings_bank.max_savings_per_account
        self.liquidity: float = self.config.savings_bank.initial_liquidity

    def deposit_savings(self, agent: HasUniqueID, amount: float) -> float:
        """
        Accept savings deposits from an agent.

        If the new balance exceeds the savings limit, the excess amount is rejected.

        Args:
            agent: Agent making the deposit
            amount: Amount to deposit

        Returns:
            Amount actually deposited
        """
        if amount <= 0:
            log(
                f"SavingsBank {self.unique_id}: Invalid deposit amount {amount:.2f} for agent {agent.unique_id}.",
                level="WARNING",
            )
            return 0.0

        agent_id = agent.unique_id
        current_savings: float = self.savings_accounts.get(agent_id, 0.0)
        new_total: float = current_savings + amount

        # Check if deposit would exceed the maximum savings limit
        if new_total > self.max_savings_per_account:
            allowed_amount: float = self.max_savings_per_account - current_savings
            rejected_amount: float = amount - allowed_amount

            if allowed_amount > 0:
                self.savings_accounts[agent_id] = current_savings + allowed_amount
                self.total_savings += allowed_amount
                self.liquidity += allowed_amount

                log(
                    f"SavingsBank {self.unique_id}: Agent {agent_id} deposited {allowed_amount:.2f} "
                    f"(max reached; {rejected_amount:.2f} rejected).",
                    level="INFO",
                )
                return allowed_amount
            else:
                log(
                    f"SavingsBank {self.unique_id}: Agent {agent_id} deposit of {amount:.2f} rejected "
                    f"(max savings limit reached).",
                    level="WARNING",
                )
                return 0.0
        else:
            # Normal deposit within limits
            self.savings_accounts[agent_id] = new_total
            self.total_savings += amount
            self.liquidity += amount

            log(
                f"SavingsBank {self.unique_id}: Agent {agent_id} deposited {amount:.2f}. "
                f"Total for agent: {new_total:.2f}.",
                level="INFO",
            )
            return amount

    def withdraw_savings(self, agent: HasUniqueID, amount: float) -> float:
        """
        Process savings withdrawal for an agent.

        Args:
            agent: Agent requesting withdrawal
            amount: Amount to withdraw

        Returns:
            Actual amount withdrawn (may be less than requested if insufficient funds)
        """
        if amount <= 0:
            log(
                f"SavingsBank {self.unique_id}: Invalid withdrawal amount {amount:.2f} for agent {agent.unique_id}.",
                level="WARNING",
            )
            return 0.0

        agent_id = agent.unique_id
        current_savings: float = self.savings_accounts.get(agent_id, 0.0)

        if current_savings >= amount:
            # Sufficient funds available
            self.savings_accounts[agent_id] = current_savings - amount
            self.total_savings -= amount
            self.liquidity -= amount

            log(
                f"SavingsBank {self.unique_id}: Agent {agent_id} withdrew {amount:.2f}. "
                f"New balance: {self.savings_accounts[agent_id]:.2f}.",
                level="INFO",
            )
            return amount
        else:
            # Insufficient funds
            log(
                f"SavingsBank {self.unique_id}: Withdrawal of {amount:.2f} for Agent {agent_id} failed. "
                f"Available: {current_savings:.2f}.",
                level="WARNING",
            )
            return 0.0

    def allocate_credit(self, borrower: BorrowerAgent, amount: float) -> float:
        """
        Provide credit to a borrower agent.

        The credit is interest-free or with minimal interest as configured.

        Args:
            borrower: Agent requesting the loan
            amount: Amount of credit requested

        Returns:
            Amount of credit actually provided
        """
        if amount <= 0:
            log(
                f"SavingsBank {self.unique_id}: Invalid credit request amount {amount:.2f} from {borrower.unique_id}.",
                level="WARNING",
            )
            return 0.0

        if self.liquidity >= amount:
            borrower_id = borrower.unique_id

            # Register the loan
            self.active_loans[borrower_id] = self.active_loans.get(borrower_id, 0.0) + amount
            # Reduce available liquidity
            self.liquidity -= amount

            # Transfer funds to borrower
            borrower.request_funds_from_bank(amount)

            log(
                f"SavingsBank {self.unique_id}: Allocated credit of {amount:.2f} to borrower {borrower_id}.",
                level="INFO",
            )
            return amount
        else:
            log(
                f"SavingsBank {self.unique_id}: Insufficient liquidity to allocate credit of {amount:.2f}. "
                f"Available liquidity: {self.liquidity:.2f}.",
                level="WARNING",
            )
            return 0.0

    def repayment(self, borrower: HasUniqueID, amount: float) -> float:
        """
        Process loan repayment from a borrower.

        Args:
            borrower: Agent repaying the loan
            amount: Amount being repaid

        Returns:
            Actual amount applied to the loan (may be limited by outstanding balance)
        """
        if amount <= 0:
            log(
                f"SavingsBank {self.unique_id}: Invalid repayment amount {amount:.2f} from {borrower.unique_id}.",
                level="WARNING",
            )
            return 0.0

        borrower_id = borrower.unique_id
        outstanding_amount: float = self.active_loans.get(borrower_id, 0.0)

        if outstanding_amount == 0:
            log(
                f"SavingsBank {self.unique_id}: No outstanding loan for borrower {borrower_id}.",
                level="WARNING",
            )
            return 0.0

        # Apply repayment (limited by outstanding balance)
        repaid_amount: float = min(amount, outstanding_amount)
        self.active_loans[borrower_id] = outstanding_amount - repaid_amount
        self.liquidity += repaid_amount

        log(
            f"SavingsBank {self.unique_id}: Borrower {borrower_id} repaid {repaid_amount:.2f}. "
            f"Remaining loan: {self.active_loans[borrower_id]:.2f}.",
            level="INFO",
        )
        return repaid_amount

    def enforce_savings_limit(self, agent: HasUniqueID) -> float:
        """
        Enforce the maximum savings limit for an agent.

        Any excess savings above the limit are removed.

        Args:
            agent: Agent to check for excess savings

        Returns:
            Amount of excess savings removed (if any)
        """
        agent_id = agent.unique_id
        current_savings: float = self.savings_accounts.get(agent_id, 0.0)

        if current_savings > self.max_savings_per_account:
            excess_amount: float = current_savings - self.max_savings_per_account
            self.savings_accounts[agent_id] = self.max_savings_per_account
            self.total_savings -= excess_amount
            self.liquidity -= excess_amount

            log(
                f"SavingsBank {self.unique_id}: Enforced savings limit for Agent {agent_id}. "
                f"Excess of {excess_amount:.2f} removed.",
                level="INFO",
            )
            return excess_amount
        else:
            log(
                f"SavingsBank {self.unique_id}: Agent {agent_id} is within the savings limit.",
                level="DEBUG",
            )
            return 0.0

    def give_household_withdrawal(self, agent: HasUniqueID, amount: float) -> float:
        """Wrapper around withdraw_savings for household use."""
        return self.withdraw_savings(agent, amount)

    def step(self, current_step: int) -> None:
        """
        Execute one simulation step for the savings bank.

        This includes:
        1. Enforcing savings limits for all accounts
        2. Checking for liquidity and maturity matching (placeholder)
        3. Working with clearing agents (placeholder)

        Args:
            current_step: Current simulation step number
        """
        log(f"SavingsBank {self.unique_id} starting step {current_step}.", level="INFO")

        # Check all savings accounts for compliance with limits
        for agent_id in list(self.savings_accounts.keys()):
            dummy_agent = type("DummyAgent", (object,), {"unique_id": agent_id})
            self.enforce_savings_limit(dummy_agent)

        # Placeholder for future functionality
        log(
            f"SavingsBank {self.unique_id}: Maturity matching and clearing operations not implemented yet.",
            level="DEBUG",
        )

        log(f"SavingsBank {self.unique_id} completed step {current_step}.", level="INFO")
