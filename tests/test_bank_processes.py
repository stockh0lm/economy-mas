import pytest

from agents.bank import WarengeldBank
from config import CONFIG_MODEL


class AccountStub:
    def __init__(self, unique_id: str, sight_balance: float) -> None:
        self.unique_id = unique_id
        self.sight_balance = float(sight_balance)


class RetailerStub:
    def __init__(
        self,
        unique_id: str,
        *,
        sight_balance: float = 0.0,
        cc_balance: float = 0.0,
        inventory_value: float = 0.0,
        cc_limit: float = 500.0,
    ) -> None:
        self.unique_id = unique_id
        self.sight_balance = float(sight_balance)
        self.cc_balance = float(cc_balance)
        self.inventory_value = float(inventory_value)
        self.cc_limit = float(cc_limit)


def make_bank(unique_id: str, **overrides) -> WarengeldBank:
    cfg = CONFIG_MODEL.model_copy(deep=True)
    if "inventory_check_interval" in overrides:
        cfg.bank.inventory_check_interval = int(overrides["inventory_check_interval"])
    if "inventory_coverage_threshold" in overrides:
        cfg.bank.inventory_coverage_threshold = float(overrides["inventory_coverage_threshold"])
    if "base_account_fee" in overrides:
        cfg.bank.base_account_fee = float(overrides["base_account_fee"])
    if "positive_balance_fee_rate" in overrides:
        cfg.bank.positive_balance_fee_rate = float(overrides["positive_balance_fee_rate"])
    if "negative_balance_fee_rate" in overrides:
        cfg.bank.negative_balance_fee_rate = float(overrides["negative_balance_fee_rate"])
    if "risk_pool_rate" in overrides:
        cfg.bank.risk_pool_rate = float(overrides["risk_pool_rate"])
    return WarengeldBank(unique_id, cfg)


def test_process_repayment_limits_to_outstanding_credit() -> None:
    bank = WarengeldBank("bank_repay")
    borrower = RetailerStub("retailer_repay", sight_balance=0.0)

    bank.credit_lines[borrower.unique_id] = 50.0
    bank.liquidity = 0.0

    repaid = bank.process_repayment(borrower, 100.0)

    assert repaid == pytest.approx(50.0)
    assert bank.credit_lines[borrower.unique_id] == pytest.approx(0.0)
    assert bank.liquidity == pytest.approx(50.0)


def test_check_inventories_reports_undercoverage() -> None:
    """Referenz: doc/issues.md Abschnitt 4 → Legacy-Muster vollständig bereinigen

    Die moderne Inventarprüfung ist diagnostisch (kein sofortiges Einziehen mehr).
    """

    bank = make_bank(
        "bank_inv",
        inventory_check_interval=1,
        inventory_coverage_threshold=0.8,
    )

    # cc_balance ist negativ wenn genutzt; exposure = abs(cc_balance)
    retailer = RetailerStub("retailer_1", cc_balance=-100.0, inventory_value=50.0)

    issues = bank.check_inventories([retailer], current_step=1)
    assert issues == [("retailer_1", 50.0, 100.0)]


def test_check_inventories_respects_interval() -> None:
    bank = make_bank("bank_inv_int", inventory_check_interval=3, inventory_coverage_threshold=0.8)
    retailer = RetailerStub("retailer_1", cc_balance=-100.0, inventory_value=50.0)

    assert bank.check_inventories([retailer], current_step=1)  # first run
    assert bank.check_inventories([retailer], current_step=2) == []  # interval not reached
    assert bank.check_inventories([retailer], current_step=4)  # interval reached again


def test_charge_account_fees_debits_balance_and_books_income() -> None:
    bank = make_bank(
        "bank_fees",
        base_account_fee=2.0,
        positive_balance_fee_rate=0.01,
        negative_balance_fee_rate=0.0,
        risk_pool_rate=0.0,
    )

    acct = AccountStub("acct", sight_balance=100.0)
    total_fees = bank.charge_account_fees([acct])

    expected = 2.0 + (0.01 * 100.0)
    assert total_fees == pytest.approx(expected)
    assert acct.sight_balance == pytest.approx(100.0 - expected)
    assert bank.sight_balance == pytest.approx(expected)
    assert bank.collected_fees == pytest.approx(expected)


def test_step_runs_inventory_check_and_fee_collection() -> None:
    bank = make_bank(
        "bank_step",
        inventory_check_interval=1,
        base_account_fee=1.0,
        positive_balance_fee_rate=0.0,
        negative_balance_fee_rate=0.0,
        risk_pool_rate=0.0,
    )

    retailer = RetailerStub(
        "retailer_step",
        sight_balance=10.0,
        cc_balance=-10.0,
        inventory_value=0.0,
    )

    bank.step(1, [retailer])

    assert bank.collected_fees > 0.0
    assert retailer.sight_balance < 10.0
