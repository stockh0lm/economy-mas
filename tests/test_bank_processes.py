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
    bank = WarengeldBank("bank_inventory")
    borrower = merchant("merchant_inventory", inventory=10.0, balance=25.0)

    bank.credit_lines[borrower.unique_id] = 30.0

    bank.check_inventories([borrower])

    coverage_threshold = bank.inventory_coverage_threshold
    min_covered_credit = borrower.inventory / max(coverage_threshold, 1e-6)
    excess_credit = max(0.0, 30.0 - min_covered_credit)
    expected_repayment = min(excess_credit, 25.0)

    assert borrower.balance == pytest.approx(25.0 - expected_repayment)
    assert bank.credit_lines[borrower.unique_id] == pytest.approx(30.0 - expected_repayment)
    assert bank.liquidity == pytest.approx(bank.config.bank.initial_liquidity + expected_repayment)


def test_check_inventories_skips_merchants_without_credit() -> None:
    bank = WarengeldBank("bank_inventory_skip")
    borrower = merchant("merchant_inventory_skip", inventory=10.0, balance=0.0)

    bank.check_inventories([borrower])

    assert borrower.balance == 0.0
    assert borrower.unique_id not in bank.credit_lines


def test_calculate_fees_updates_liquidity_and_fee_pool() -> None:
    bank = WarengeldBank("bank_fees")
    borrower = merchant("merchant_fees", inventory=0.0, balance=100.0)
    bank.credit_lines[borrower.unique_id] = 200.0

    total_fees = bank.calculate_fees([borrower])

    expected_fee = 200.0 * bank.fee_rate
    assert total_fees == pytest.approx(expected_fee)
    assert bank.collected_fees == pytest.approx(expected_fee)
    assert bank.liquidity == pytest.approx(bank.config.bank.initial_liquidity + expected_fee)
    assert borrower.balance == pytest.approx(100.0 - expected_fee)


def test_step_runs_inventory_check_and_fee_collection() -> None:
    bank = make_bank("bank_step", inventory_check_interval=1)

    borrower = merchant("merchant_step", inventory=0.0, balance=100.0)
    bank.credit_lines[borrower.unique_id] = 200.0

    bank.step(1, [borrower])

    assert bank.collected_fees > 0.0
    assert borrower.balance <= 100.0
