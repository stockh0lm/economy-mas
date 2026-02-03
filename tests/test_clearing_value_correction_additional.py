"""Additional comprehensive tests for ClearingAgent._apply_value_correction method.

This test module provides additional edge case coverage for the complex value correction logic
that handles fraud/wertberichtigung scenarios as described in doc/issues.md.
"""

import math
from dataclasses import dataclass
from typing import Any

import config
from agents.clearing_agent import ClearingAgent


@dataclass
class DummyPurchaseRecord:
    retailer_id: str
    seller_id: str
    amount: float
    step: int


class DummyBank:
    def __init__(self, bank_id: str, sight_balance: float = 1000.0) -> None:
        self.unique_id = bank_id
        self.sight_balance = sight_balance
        self.clearing_reserve_deposit = 500.0
        self.goods_purchase_ledger = []

    def write_down_cc(self, retailer: Any, amount: float, reason: str) -> None:
        # Simple implementation for testing
        pass


class DummyRetailer:
    def __init__(self, retailer_id: str, inventory_value: float = 500.0, cc_balance: float = -800.0) -> None:
        self.unique_id = retailer_id
        self.inventory_value = inventory_value
        self.cc_balance = cc_balance
        self.write_down_reserve = 100.0
        self.sight_balance = 200.0


class DummyCompany:
    def __init__(self, company_id: str, sight_balance: float = 300.0) -> None:
        self.unique_id = company_id
        self.sight_balance = sight_balance


def test_apply_value_correction_complex_robust_allocation() -> None:
    """Test complex robust pro-rata allocation with multiple rounds and partial payments."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    cfg.clearing.audit_interval = 30
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=100.0, cc_balance=-1500.0)

    # Create multiple companies with varying capacities
    company1 = DummyCompany("company_1", sight_balance=1000.0)  # High capacity
    company2 = DummyCompany("company_2", sight_balance=100.0)   # Medium capacity
    company3 = DummyCompany("company_3", sight_balance=50.0)    # Low capacity
    company4 = DummyCompany("company_4", sight_balance=0.0)     # No capacity

    companies_by_id = {
        "company_1": company1,
        "company_2": company2,
        "company_3": company3,
        "company_4": company4
    }

    # Companies received different amounts
    bank.goods_purchase_ledger = [
        DummyPurchaseRecord("retailer_1", "company_1", 500.0, 95),
        DummyPurchaseRecord("retailer_1", "company_2", 200.0, 95),
        DummyPurchaseRecord("retailer_1", "company_3", 100.0, 95),
        DummyPurchaseRecord("retailer_1", "company_4", 50.0, 95),
    ]

    # Test scenario: need 1200 from companies after using retailer funds
    # This should require multiple allocation rounds
    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=1500.0,  # 100 reserve + 200 retailer sight + 1200 needed from companies
        companies_by_id=companies_by_id,
        current_step=100
    )

    # Should get 100 + 200 + 100 (company4 can't pay) + 100 (company3 max) + 100 (company2 max) + 850 (remaining from company1) = 1450
    assert math.isclose(corrected, 1450.0)
    assert math.isclose(company1.sight_balance, 0.0)  # 1000 - 1000 (all used)
    assert math.isclose(company2.sight_balance, 0.0)    # 100 - 100
    assert math.isclose(company3.sight_balance, 0.0)    # 50 - 50
    assert math.isclose(company4.sight_balance, 0.0)    # 0 - 0


def test_apply_value_correction_all_companies_exhausted() -> None:
    """Test scenario where all companies are exhausted before full allocation."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=100.0, cc_balance=-1000.0)

    # Companies with very limited capacity
    company1 = DummyCompany("company_1", sight_balance=50.0)
    company2 = DummyCompany("company_2", sight_balance=30.0)

    companies_by_id = {
        "company_1": company1,
        "company_2": company2
    }

    bank.goods_purchase_ledger = [
        DummyPurchaseRecord("retailer_1", "company_1", 100.0, 95),
        DummyPurchaseRecord("retailer_1", "company_2", 100.0, 95),
    ]

    # Test scenario: need 700 from companies but they can only provide 80
    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=1000.0,  # 100 reserve + 200 retailer sight + 700 needed from companies
        companies_by_id=companies_by_id,
        current_step=100
    )

    # Should get 100 + 200 + 80 (all companies can provide) = 380
    assert math.isclose(corrected, 380.0)
    assert math.isclose(company1.sight_balance, 0.0)
    assert math.isclose(company2.sight_balance, 0.0)


def test_apply_value_correction_with_missing_companies() -> None:
    """Test value correction when some companies in ledger don't exist in companies_by_id."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=100.0, cc_balance=-800.0)

    # Only one company exists
    company1 = DummyCompany("company_1", sight_balance=500.0)
    companies_by_id = {
        "company_1": company1
        # company_2 is in ledger but not in companies_by_id
    }

    bank.goods_purchase_ledger = [
        DummyPurchaseRecord("retailer_1", "company_1", 200.0, 95),
        DummyPurchaseRecord("retailer_1", "company_2", 300.0, 95),  # Missing company
    ]

    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=700.0,  # 100 reserve + 200 retailer sight + 400 needed from companies
        companies_by_id=companies_by_id,
        current_step=100
    )

    # Should get 100 + 200 + 400 (all from company1 since company2 is missing) = 700
    assert math.isclose(corrected, 700.0)
    assert math.isclose(company1.sight_balance, 100.0)  # 500 - 400


def test_apply_value_correction_tiny_allocation_rounds() -> None:
    """Test value correction with very small amounts that require precise allocation."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=100.0, cc_balance=-200.0)

    company1 = DummyCompany("company_1", sight_balance=50.0)
    company2 = DummyCompany("company_2", sight_balance=50.0)

    companies_by_id = {
        "company_1": company1,
        "company_2": company2
    }

    bank.goods_purchase_ledger = [
        DummyPurchaseRecord("retailer_1", "company_1", 1.0, 95),
        DummyPurchaseRecord("retailer_1", "company_2", 1.0, 95),
    ]

    # Test with very small amount that needs precise allocation
    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=102.0,  # 100 reserve + 2 retailer sight (small) + tiny amount from companies
        companies_by_id=companies_by_id,
        current_step=100
    )

    assert math.isclose(corrected, 102.0)
    # Companies should contribute tiny amounts proportionally
    total_company_contribution = 2.0
    assert abs((company1.sight_balance - 50.0) - (company2.sight_balance - 50.0)) < 1e-6  # Should be equal


def test_apply_value_correction_with_zero_weight_companies() -> None:
    """Test value correction when some companies have zero or negative weights."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=100.0, cc_balance=-800.0)

    company1 = DummyCompany("company_1", sight_balance=500.0)
    company2 = DummyCompany("company_2", sight_balance=500.0)

    companies_by_id = {
        "company_1": company1,
        "company_2": company2
    }

    bank.goods_purchase_ledger = [
        DummyPurchaseRecord("retailer_1", "company_1", 300.0, 95),
        DummyPurchaseRecord("retailer_1", "company_2", 0.0, 95),    # Zero weight
        DummyPurchaseRecord("retailer_1", "company_1", -100.0, 95), # Negative weight (should be ignored)
    ]

    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=700.0,  # 100 reserve + 200 retailer sight + 400 needed from companies
        companies_by_id=companies_by_id,
        current_step=100
    )

    # Should only use company1 since company2 has zero weight and negative weights are ignored
    assert math.isclose(corrected, 700.0)
    assert math.isclose(company1.sight_balance, 100.0)  # 500 - 400
    assert math.isclose(company2.sight_balance, 500.0)  # Untouched