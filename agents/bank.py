# bank.py
from typing import Protocol, TypedDict, TypeAlias, Dict, Optional, Sequence
from .base_agent import BaseAgent
from logger import log
from config import CONFIG


class MerchantProtocol(Protocol):
    """Protocol for merchants that can interact with the bank"""
    unique_id: str

    def request_funds_from_bank(self, amount: float) -> float:
        """Receive funds from bank"""
        ...


class InventoryMerchant(MerchantProtocol, Protocol):
    """Protocol for merchants that also have inventory tracking"""
    inventory: float


# Type aliases for improved readability
MerchantID: TypeAlias = str
CreditMap: TypeAlias = Dict[MerchantID, float]


class WarengeldBank(BaseAgent):
    """
    Manages interest-free credit lines for merchants in the economic simulation.

    The WarengeldBank (commodity money bank) provides liquidity to the economy
    through short-term credit lines and monitors merchants' inventory levels
    to ensure adequate backing for extended credit.
    """

    def __init__(self, unique_id: str) -> None:
        """
        Initialize a Warengeld bank with default parameters.

        Args:
            unique_id: Unique identifier for this bank
        """
        super().__init__(unique_id)

        # Credit management
        self.credit_lines: CreditMap = {}  # Maps merchant_id to outstanding credit amount

        # Bank parameters from configuration
        self.fee_rate: float = CONFIG.get("bank_fee_rate", 0.01)  # e.g., 1%
        self.inventory_check_interval: int = CONFIG.get("inventory_check_interval", 3)
        self.inventory_coverage_threshold: float = CONFIG.get("inventory_coverage_threshold", 0.8)

        # Financial tracking
        self.collected_fees: float = 0.0
        self.liquidity: float = CONFIG.get("initial_bank_liquidity", 1000.0)

    def grant_credit(self, merchant: MerchantProtocol, amount: float) -> float:
        """
        Grant interest-free credit to a merchant as commodity money creation.

        First checks if sufficient liquidity is available, then adds the
        requested amount to the existing credit (if any), deducts from bank
        liquidity, and informs the merchant.

        Args:
            merchant: Merchant requesting the credit
            amount: Amount of credit requested

        Returns:
            Amount of credit actually granted
        """
        if amount <= 0:
            log(f"WarengeldBank {self.unique_id}: Invalid credit request amount {amount:.2f}",
                level="WARNING")
            return 0.0

        if self.liquidity < amount:
            log(f"WarengeldBank {self.unique_id}: Insufficient liquidity to grant credit of {amount:.2f}. "
                f"Available liquidity: {self.liquidity:.2f}.",
                level="WARNING")
            return 0.0

        merchant_id = merchant.unique_id
        current_credit: float = self.credit_lines.get(merchant_id, 0.0)
        self.credit_lines[merchant_id] = current_credit + amount
        self.liquidity -= amount  # Reduce bank liquidity

        merchant.request_funds_from_bank(amount)

        log(f"WarengeldBank {self.unique_id}: Granted credit of {amount:.2f} to merchant {merchant_id}. "
            f"Total credit now: {self.credit_lines[merchant_id]:.2f}. "
            f"Liquidity remaining: {self.liquidity:.2f}.",
            level="INFO")

        return amount

    def process_repayment(self, merchant: MerchantProtocol, amount: float) -> float:
        """
        Process repayment of outstanding credit from a merchant.

        The repaid amount is deducted from the outstanding credit and
        added to the bank's liquidity.

        Args:
            merchant: Merchant making the repayment
            amount: Amount to repay

        Returns:
            Actual amount repaid (limited by outstanding credit)
        """
        if amount <= 0:
            log(f"WarengeldBank {self.unique_id}: Invalid repayment amount {amount:.2f}",
                level="WARNING")
            return 0.0

        merchant_id = merchant.unique_id
        outstanding: float = self.credit_lines.get(merchant_id, 0.0)

        if outstanding == 0:
            log(f"WarengeldBank {self.unique_id}: Merchant {merchant_id} has no outstanding credit.",
                level="WARNING")
            return 0.0

        repaid: float = min(amount, outstanding)
        self.credit_lines[merchant_id] = outstanding - repaid
        self.liquidity += repaid  # Increase liquidity

        log(f"WarengeldBank {self.unique_id}: Merchant {merchant_id} repaid {repaid:.2f}. "
            f"Remaining credit: {self.credit_lines[merchant_id]:.2f}. "
            f"Liquidity now: {self.liquidity:.2f}.",
            level="INFO")

        return repaid

    def check_inventories(self, merchants: Sequence[MerchantProtocol]) -> None:
        """
        Perform inventory verification for merchants to ensure adequate
        backing for extended credit.

        If a merchant's inventory value falls significantly below their
        credit amount, a warning is logged.

        Args:
            merchants: List of merchants to check
        """
        for merchant in merchants:
            merchant_id = merchant.unique_id
            credit: float = self.credit_lines.get(merchant_id, 0.0)

            if credit == 0:
                continue  # Skip merchants with no outstanding credit

            if not hasattr(merchant, "inventory"):
                log(f"WarengeldBank {self.unique_id}: Merchant {merchant_id} has no inventory attribute.",
                    level="DEBUG")
                continue

            # Cast to InventoryMerchant to access inventory attribute
            inventory_merchant = merchant  # type: InventoryMerchant
            inventory: float = inventory_merchant.inventory

            # Check if inventory value is below threshold of credit
            if inventory < self.inventory_coverage_threshold * credit:
                log(f"WarengeldBank {self.unique_id}: WARNING - Merchant {merchant_id} has insufficient "
                    f"inventory ({inventory:.2f}) to cover credit ({credit:.2f}).",
                    level="WARNING")
            else:
                log(f"WarengeldBank {self.unique_id}: Merchant {merchant_id} has sufficient inventory "
                    f"({inventory:.2f}) to cover credit ({credit:.2f}).",
                    level="DEBUG")

    def calculate_fees(self, merchants: Sequence[MerchantProtocol]) -> float:
        """
        Calculate and collect account maintenance fees from merchants based on
        their outstanding credit.

        The fee is deducted from the merchant's balance (if available)
        and recorded as bank income.

        Args:
            merchants: List of merchants to charge fees to

        Returns:
            Total fees collected in this round
        """
        total_fees: float = 0.0

        for merchant in merchants:
            merchant_id = merchant.unique_id
            credit: float = self.credit_lines.get(merchant_id, 0.0)
            fee: float = credit * self.fee_rate

            if fee <= 0:
                continue

            if hasattr(merchant, "balance"):
                # Deduct fee from merchant's balance if possible
                merchant_balance: float = getattr(merchant, "balance")
                setattr(merchant, "balance", merchant_balance - fee)
                log(f"WarengeldBank {self.unique_id}: Collected fee of {fee:.2f} from merchant {merchant_id}.",
                    level="INFO")

            self.collected_fees += fee
            self.liquidity += fee  # Add fees to bank liquidity
            total_fees += fee

        return total_fees

    def step(self, current_step: int, merchants: Sequence[MerchantProtocol]) -> None:
        """
        Execute one simulation step for the bank.

        During each step, the bank:
        1. Performs inventory verification at regular intervals
        2. Calculates and collects account maintenance fees
        3. Logs current financial state

        Args:
            current_step: Current simulation step number
            merchants: List of merchants under bank supervision
        """
        log(f"WarengeldBank {self.unique_id} starting step {current_step}.", level="INFO")

        # Inventory check at specified intervals
        if current_step % self.inventory_check_interval == 0:
            self.check_inventories(merchants)

        # Collect fees
        fees_collected = self.calculate_fees(merchants)

        log(f"WarengeldBank {self.unique_id} completed step {current_step}. "
            f"Fees collected: {fees_collected:.2f}, Total fees: {self.collected_fees:.2f}, "
            f"Liquidity: {self.liquidity:.2f}.",
            level="INFO")