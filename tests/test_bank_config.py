import pytest

import config
from agents.bank import WarengeldBank


def make_bank(unique_id: str, **overrides) -> WarengeldBank:
    cfg = config.CONFIG_MODEL.model_copy(deep=True)

    if "base_account_fee" in overrides:
        cfg.bank.base_account_fee = float(overrides["base_account_fee"])
    if "positive_balance_fee_rate" in overrides:
        cfg.bank.positive_balance_fee_rate = float(overrides["positive_balance_fee_rate"])
    if "negative_balance_fee_rate" in overrides:
        cfg.bank.negative_balance_fee_rate = float(overrides["negative_balance_fee_rate"])
    if "risk_pool_rate" in overrides:
        cfg.bank.risk_pool_rate = float(overrides["risk_pool_rate"])

    if "inventory_check_interval" in overrides:
        cfg.bank.inventory_check_interval = int(overrides["inventory_check_interval"])
    if "inventory_coverage_threshold" in overrides:
        cfg.bank.inventory_coverage_threshold = float(overrides["inventory_coverage_threshold"])

    if "bank_base_credit_reserve_ratio" in overrides:
        cfg.bank.base_credit_reserve_ratio = float(overrides["bank_base_credit_reserve_ratio"])
    if "bank_credit_unemployment_sensitivity" in overrides:
        cfg.bank.credit_unemployment_sensitivity = float(overrides["bank_credit_unemployment_sensitivity"])
    if "bank_credit_inflation_sensitivity" in overrides:
        cfg.bank.credit_inflation_sensitivity = float(overrides["bank_credit_inflation_sensitivity"])
    if "target_unemployment_rate" in overrides:
        cfg.labor_market.target_unemployment_rate = float(overrides["target_unemployment_rate"])
    if "target_inflation_rate" in overrides:
        cfg.labor_market.target_inflation_rate = float(overrides["target_inflation_rate"])
    if "initial_bank_liquidity" in overrides:
        cfg.bank.initial_liquidity = float(overrides["initial_bank_liquidity"])

    return WarengeldBank(unique_id, cfg)


class RetailerDouble:
    def __init__(self, unique_id: str, cc_limit: float = 500.0, cc_balance: float = 0.0) -> None:
        self.unique_id = unique_id
        self.cc_limit = float(cc_limit)
        self.cc_balance = float(cc_balance)


class SellerDouble:
    def __init__(self, unique_id: str) -> None:
        self.unique_id = unique_id
        self.sight_balance = 0.0

    def request_funds_from_bank(self, amount: float) -> float:
        self.sight_balance += float(amount)
        return float(amount)


def test_bank_reads_configuration_values() -> None:
    bank = make_bank(
        "bank_test",
        base_account_fee=2.5,
        positive_balance_fee_rate=0.001,
        negative_balance_fee_rate=0.0,
        risk_pool_rate=0.01,
        inventory_check_interval=4,
        inventory_coverage_threshold=0.9,
        bank_base_credit_reserve_ratio=0.2,
        bank_credit_unemployment_sensitivity=0.55,
        bank_credit_inflation_sensitivity=0.75,
        target_unemployment_rate=0.045,
        target_inflation_rate=0.015,
        initial_bank_liquidity=2500.0,
    )

    assert bank.config.bank.base_account_fee == pytest.approx(2.5)
    assert bank.config.bank.positive_balance_fee_rate == pytest.approx(0.001)
    assert bank.config.bank.negative_balance_fee_rate == pytest.approx(0.0)
    assert bank.config.bank.risk_pool_rate == pytest.approx(0.01)

    assert bank.inventory_check_interval == 4
    assert bank.inventory_coverage_threshold == 0.9
    assert bank.base_credit_reserve_ratio == 0.2
    assert bank.credit_unemployment_sensitivity == 0.55
    assert bank.credit_inflation_sensitivity == 0.75
    assert bank.target_unemployment_rate == 0.045
    assert bank.target_inflation_rate == 0.015
    assert bank.liquidity == pytest.approx(2500.0)


def test_bank_falls_back_to_defaults_for_missing_config() -> None:
    bank = WarengeldBank("bank_defaults")

    assert bank.config.bank.base_account_fee == 0.0
    assert bank.inventory_check_interval == 3
    assert bank.inventory_coverage_threshold == pytest.approx(0.8)
    assert bank.base_credit_reserve_ratio == pytest.approx(0.1)


def test_finance_goods_purchase_respects_cc_limit() -> None:
    """Referenz: doc/issues.md Abschnitt 4 → Legacy-Muster vollständig bereinigen

    Nach der Migration gibt es keine Legacy-Kredit-Abkürzung mehr;
    relevante Schranke ist der Kontokorrent-`cc_limit`.
    """

    bank = WarengeldBank("bank_cc")

    retailer = RetailerDouble("retailer_cc", cc_limit=100.0)
    seller = SellerDouble("seller_cc")

    ok = bank.finance_goods_purchase(retailer=retailer, seller=seller, amount=80.0, current_step=1)
    assert ok == pytest.approx(80.0)
    assert retailer.cc_balance == pytest.approx(-80.0)
    assert seller.sight_balance == pytest.approx(80.0)

    denied = bank.finance_goods_purchase(retailer=retailer, seller=seller, amount=30.0, current_step=2)
    assert denied == 0.0
    assert retailer.cc_balance == pytest.approx(-80.0)
    assert seller.sight_balance == pytest.approx(80.0)


def test_finance_goods_purchase_rejects_non_positive_request() -> None:
    bank = WarengeldBank("bank_zero")
    retailer = RetailerDouble("retailer_zero")
    seller = SellerDouble("seller_zero")

    assert bank.finance_goods_purchase(retailer=retailer, seller=seller, amount=0.0, current_step=1) == 0.0
    assert bank.finance_goods_purchase(retailer=retailer, seller=seller, amount=-5.0, current_step=1) == 0.0
