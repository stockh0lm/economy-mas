from copy import deepcopy
from typing import Callable

import pytest

import config
from agents.bank import MerchantProtocol, WarengeldBank


def make_bank(unique_id: str, **overrides) -> WarengeldBank:
    payload = deepcopy(config.CONFIG)
    payload.update(overrides)
    cfg = config.load_simulation_config(payload)
    return WarengeldBank(unique_id, cfg)


class MerchantDouble(MerchantProtocol):
    def __init__(self, unique_id: str = "merchant_1", callback: Callable[[float], None] | None = None):
        self.unique_id = unique_id
        self.inventory = 0.0
        self.balance = 0.0
        self.callback = callback
        self.received: list[float] = []

    def request_funds_from_bank(self, amount: float) -> float:
        self.received.append(amount)
        if self.callback:
            self.callback(amount)
        return amount


def test_bank_reads_configuration_values() -> None:
    bank = make_bank(
        "bank_test",
        bank_fee_rate=0.125,
        inventory_check_interval=4,
        inventory_coverage_threshold=0.9,
        bank_base_credit_reserve_ratio=0.2,
        bank_credit_unemployment_sensitivity=0.55,
        bank_credit_inflation_sensitivity=0.75,
        target_unemployment_rate=0.045,
        target_inflation_rate=0.015,
        initial_bank_liquidity=2500.0,
    )

    assert bank.fee_rate == 0.125
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

    assert bank.fee_rate == pytest.approx(0.01)
    assert bank.inventory_check_interval == 3
    assert bank.inventory_coverage_threshold == pytest.approx(0.8)
    assert bank.base_credit_reserve_ratio == pytest.approx(0.1)


def test_grant_credit_respects_macro_cap_and_liquidity() -> None:
    bank = make_bank(
        "bank_macro",
        initial_bank_liquidity=100.0,
        bank_base_credit_reserve_ratio=0.5,
    )
    bank.macro_unemployment = bank.target_unemployment_rate + 0.2
    bank.macro_inflation = bank.target_inflation_rate + 0.1

    merchant = MerchantDouble("merchant_macro")

    requested = 500.0
    granted = bank.grant_credit(merchant, requested)

    expected_ratio = (
        0.5
        + bank.credit_unemployment_sensitivity * 0.2
        + bank.credit_inflation_sensitivity * 0.1
    )
    max_credit = bank.liquidity / expected_ratio

    assert granted == 0.0
    assert bank.credit_lines.get(merchant.unique_id, 0.0) == 0.0
    assert merchant.received == []


def test_grant_credit_rejects_non_positive_request() -> None:
    bank = WarengeldBank("bank_zero")
    merchant = MerchantDouble("merchant_zero")

    assert bank.grant_credit(merchant, 0) == 0.0
    assert bank.grant_credit(merchant, -5) == 0.0
    assert merchant.received == []
