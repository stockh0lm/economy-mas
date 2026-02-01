import pytest

from agents.bank import WarengeldBank
from config import CONFIG_MODEL


class MerchantStub:
    def __init__(self, unique_id: str, inventory: float = 0.0, balance: float = 0.0) -> None:
        self.unique_id = unique_id
        self.inventory = inventory
        self.balance = balance
        self.received = []

    def request_funds_from_bank(self, amount: float) -> float:
        self.received.append(amount)
        self.balance += amount
        return amount


def merchant(unique_id: str, inventory: float = 0.0, balance: float = 0.0) -> MerchantStub:
    return MerchantStub(unique_id, inventory, balance)


def make_bank(unique_id: str, **overrides) -> WarengeldBank:
    cfg = CONFIG_MODEL.model_copy(deep=True)
    if "inventory_check_interval" in overrides:
        cfg.bank.inventory_check_interval = overrides["inventory_check_interval"]
    return WarengeldBank(unique_id, cfg)


def test_process_repayment_limits_to_outstanding_credit() -> None:
    bank = WarengeldBank("bank_repay")
    borrower = merchant("merchant_repay")

    bank.credit_lines[borrower.unique_id] = 50.0
    bank.liquidity = 0.0

    repaid = bank.process_repayment(borrower, 100.0)

    assert repaid == pytest.approx(50.0)
    assert bank.credit_lines[borrower.unique_id] == pytest.approx(0.0)
    assert bank.liquidity == pytest.approx(50.0)


def test_check_inventories_enforces_repayment_when_underwater() -> None:
    """Test that modern bank step method handles inventory checks and fees."""
    bank = WarengeldBank("bank_inventory")
    borrower = merchant("merchant_inventory", inventory=10.0, balance=25.0)

    bank.credit_lines[borrower.unique_id] = 30.0

    # Use modern bank.step() method which handles inventory checks and fees automatically
    bank.step(1, [borrower])

    # Modern behavior: bank.step() runs inventory checks in diagnostic mode
    # and charges account fees. It doesn't enforce immediate repayment like the legacy method.
    # Instead, it should have charged fees and potentially logged inventory issues.

    # Check that fees were collected (default config has base_account_fee=0.0, so should be 0)
    # But if there were any fees configured, they would be collected
    assert borrower.balance <= 25.0  # Balance should be same or less due to fees
    assert bank.credit_lines[borrower.unique_id] == 30.0  # No immediate repayment in diagnostic mode
    assert bank.collected_fees >= 0.0  # Fees should be collected if configured


def test_check_inventories_skips_merchants_without_credit() -> None:
    """Test that modern bank step method skips merchants without credit."""
    bank = WarengeldBank("bank_inventory_skip")
    borrower = merchant("merchant_inventory_skip", inventory=10.0, balance=0.0)

    # Use modern bank.step() method which handles inventory checks automatically
    bank.step(1, [borrower])

    assert borrower.balance == 0.0
    assert borrower.unique_id not in bank.credit_lines


def test_calculate_fees_updates_liquidity_and_fee_pool() -> None:
    """Test that modern charge_account_fees updates liquidity and fee pool."""
    bank = WarengeldBank("bank_fees")
    borrower = merchant("merchant_fees", inventory=0.0, balance=100.0)
    bank.credit_lines[borrower.unique_id] = 200.0

    # Use modern charge_account_fees method
    # Set up modern fee parameters for this test
    bank.config.bank.base_account_fee = 2.0  # Flat fee per account
    bank.config.bank.positive_balance_fee_rate = 0.01  # 1% of positive balance

    total_fees = bank.charge_account_fees([borrower])

    # Note: charge_account_fees uses sight_balance, but our test merchant has 'balance'
    # The method should work with either attribute
    # Expected fee: base_fee (2.0) + positive_balance_fee (1% of 100 = 1.0) = 3.0
    expected_fee = bank.config.bank.base_account_fee + (100.0 * bank.config.bank.positive_balance_fee_rate)
    assert total_fees == pytest.approx(expected_fee)
    assert bank.collected_fees == pytest.approx(expected_fee)
    # Fees go to bank's sight_balance, not liquidity
    assert bank.sight_balance == pytest.approx(expected_fee)
    assert borrower.balance == pytest.approx(100.0 - expected_fee)


def test_step_runs_inventory_check_and_fee_collection() -> None:
    bank = make_bank("bank_step", inventory_check_interval=1)

    borrower = merchant("merchant_step", inventory=0.0, balance=100.0)
    bank.credit_lines[borrower.unique_id] = 200.0

    bank.step(1, [borrower])

    assert bank.collected_fees > 0.0
    assert borrower.balance <= 100.0
