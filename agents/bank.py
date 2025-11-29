# bank.py
from typing import Protocol, Sequence, TypeAlias

from agents.base_agent import BaseAgent
from config import CONFIG_MODEL, SimulationConfig

from logger import log


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
CreditMap: TypeAlias = dict[MerchantID, float]


class WarengeldBank(BaseAgent):
    """
    Manages interest-free credit lines for merchants in the economic simulation.

    The WarengeldBank (commodity money bank) provides liquidity to the economy
    through short-term credit lines and monitors merchants' inventory levels
    to ensure adequate backing for extended credit.
    """

    def __init__(self, unique_id: str, config: SimulationConfig | None = None) -> None:
        """
        Initialize a Warengeld bank with default parameters.

        Args:
            unique_id: Unique identifier for this bank
        """
        super().__init__(unique_id)

        # Credit management
        self.credit_lines: CreditMap = {}  # Maps merchant_id to outstanding credit amount

        self.config: SimulationConfig = config or CONFIG_MODEL

        # Bank parameters from configuration
        self.fee_rate: float = self.config.bank_fee_rate
        self.inventory_check_interval: int = self.config.inventory_check_interval
        self.inventory_coverage_threshold: float = self.config.inventory_coverage_threshold
        self.base_credit_reserve_ratio: float = self.config.bank_base_credit_reserve_ratio
        self.credit_unemployment_sensitivity: float = self.config.bank_credit_unemployment_sensitivity
        self.credit_inflation_sensitivity: float = self.config.bank_credit_inflation_sensitivity
        self.target_unemployment_rate: float = self.config.target_unemployment_rate
        self.target_inflation_rate: float = self.config.target_inflation_rate
        self.macro_unemployment: float = 0.0
        self.macro_inflation: float = 0.0

        # Financial tracking
        self.collected_fees: float = 0.0
        self.liquidity: float = self.config.initial_bank_liquidity

    def update_macro_signals(
        self, unemployment_rate: float | None, inflation_rate: float | None
    ) -> None:
        if unemployment_rate is not None:
            self.macro_unemployment = max(0.0, unemployment_rate)
        if inflation_rate is not None:
            self.macro_inflation = inflation_rate

    def _allowed_credit_ratio(self) -> float:
        unemployment_gap = max(0.0, self.macro_unemployment - self.target_unemployment_rate)
        inflation_gap = max(0.0, self.macro_inflation - self.target_inflation_rate)
        ratio = self.base_credit_reserve_ratio
        ratio += self.credit_unemployment_sensitivity * unemployment_gap
        ratio += self.credit_inflation_sensitivity * inflation_gap
        return max(0.01, ratio)

    def _max_credit_for_request(self, amount: float) -> float:
        total_credit = sum(self.credit_lines.values())
        allowed_ratio = self._allowed_credit_ratio()
        max_credit = self.liquidity / allowed_ratio if allowed_ratio > 0 else self.liquidity
        available_capacity = max(0.0, max_credit - total_credit)
        return min(amount, available_capacity)

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
            log(
                f"WarengeldBank {self.unique_id}: Invalid credit request amount {amount:.2f}",
                level="WARNING",
            )
            return 0.0

        allowed_amount = self._max_credit_for_request(amount)
        if allowed_amount <= 0:
            log(
                f"WarengeldBank {self.unique_id}: Macro credit cap restricts lending. Requested {amount:.2f}, allowed 0.0.",
                level="WARNING",
            )
            return 0.0
        if allowed_amount < amount:
            log(
                f"WarengeldBank {self.unique_id}: Macro cap reduced credit from {amount:.2f} to {allowed_amount:.2f}.",
                level="INFO",
            )
            amount = allowed_amount

        if self.liquidity < amount:
            log(
                f"WarengeldBank {self.unique_id}: Insufficient liquidity to grant credit of {amount:.2f}. "
                f"Available liquidity: {self.liquidity:.2f}.",
                level="WARNING",
            )
            return 0.0

        merchant_id = merchant.unique_id
        current_credit: float = self.credit_lines.get(merchant_id, 0.0)
        self.credit_lines[merchant_id] = current_credit + amount
        self.liquidity -= amount  # Reduce bank liquidity

        merchant.request_funds_from_bank(amount)

        log(
            f"WarengeldBank {self.unique_id}: Granted credit of {amount:.2f} to merchant {merchant_id}. "
            f"Total credit now: {self.credit_lines[merchant_id]:.2f}. "
            f"Liquidity remaining: {self.liquidity:.2f}.",
            level="INFO",
        )

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
            log(
                f"WarengeldBank {self.unique_id}: Invalid repayment amount {amount:.2f}",
                level="WARNING",
            )
            return 0.0

        merchant_id = merchant.unique_id
        outstanding: float = self.credit_lines.get(merchant_id, 0.0)

        if outstanding == 0:
            log(
                f"WarengeldBank {self.unique_id}: Merchant {merchant_id} has no outstanding credit.",
                level="WARNING",
            )
            return 0.0

        repaid: float = min(amount, outstanding)
        self.credit_lines[merchant_id] = outstanding - repaid
        self.liquidity += repaid  # Increase liquidity

        log(
            f"WarengeldBank {self.unique_id}: Merchant {merchant_id} repaid {repaid:.2f}. "
            f"Remaining credit: {self.credit_lines[merchant_id]:.2f}. "
            f"Liquidity now: {self.liquidity:.2f}.",
            level="INFO",
        )

        return repaid

    def check_inventories(self, merchants: Sequence[MerchantProtocol]) -> None:
        """
        Perform inventory verification for merchants to ensure adequate
        backing for extended credit.

        If a merchant's inventory value falls significantly below their
        credit amount, enforce repayments tied to merchant balances
        until coverage is restored.

        Args:
            merchants: List of merchants to check
        """
        forced_repayments: float = 0.0
        flagged_merchants: int = 0

        for merchant in merchants:
            merchant_id = merchant.unique_id
            credit: float = self.credit_lines.get(merchant_id, 0.0)

            if credit == 0:
                continue  # Skip merchants with no outstanding credit

            if not hasattr(merchant, "inventory"):
                log(
                    f"WarengeldBank {self.unique_id}: Merchant {merchant_id} has credit but no inventory attribute.",
                    level="WARNING",
                )
                continue

            inventory = merchant.inventory
            coverage_denominator = max(self.inventory_coverage_threshold, 1e-6)
            min_covered_credit = inventory / coverage_denominator

            if credit > min_covered_credit:
                excess_credit = credit - min_covered_credit
                flagged_merchants += 1
                repayment_from_balance = 0.0

                if hasattr(merchant, "balance"):
                    merchant_balance = merchant.balance
                    usable_balance = max(0.0, merchant_balance)
                    repayment_from_balance = min(excess_credit, usable_balance)

                    if repayment_from_balance > 0:
                        merchant.balance = merchant_balance - repayment_from_balance
                        repaid = self.process_repayment(merchant, repayment_from_balance)
                        forced_repayments += repaid
                        excess_credit = max(0.0, excess_credit - repaid)
                else:
                    log(
                        f"WarengeldBank {self.unique_id}: Merchant {merchant_id} lacks balance attribute; cannot force repayment.",
                        level="WARNING",
                    )

                log(
                    f"WarengeldBank {self.unique_id}: Enforced repayment of {repayment_from_balance:.2f} from merchant {merchant_id} due to insufficient inventory "
                    f"({inventory:.2f} vs credit {credit:.2f}). Remaining uncovered credit: {excess_credit:.2f}.",
                    level="WARNING",
                )
            else:
                log(
                    f"WarengeldBank {self.unique_id}: Merchant {merchant_id} has sufficient inventory ({inventory:.2f}) to cover credit ({credit:.2f}).",
                    level="DEBUG",
                )

        if flagged_merchants > 0 and forced_repayments > 0:
            log(
                f"WarengeldBank {self.unique_id}: Forced repayments totaled {forced_repayments:.2f} across {flagged_merchants} merchants during inventory check.",
                level="INFO",
            )
        elif flagged_merchants > 0:
            log(
                f"WarengeldBank {self.unique_id}: {flagged_merchants} merchants lacked sufficient inventory but had no funds for repayment.",
                level="WARNING",
            )

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
                merchant_balance: float = merchant.balance
                merchant.balance = merchant_balance - fee
                log(
                    f"WarengeldBank {self.unique_id}: Collected fee of {fee:.2f} from merchant {merchant_id}.",
                    level="INFO",
                )

            self.collected_fees += fee
            self.liquidity += fee  # Add fees to bank liquidity
            total_fees += fee

        return total_fees

    def step(
        self,
        current_step: int,
        merchants: Sequence[MerchantProtocol],
        unemployment_rate: float | None = None,
        inflation_rate: float | None = None,
    ) -> None:
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

        self.update_macro_signals(unemployment_rate, inflation_rate)

        log(
            f"WarengeldBank {self.unique_id} completed step {current_step}. "
            f"Fees collected: {fees_collected:.2f}, Total fees: {self.collected_fees:.2f}, "
            f"Liquidity: {self.liquidity:.2f}.",
            level="INFO",
        )
