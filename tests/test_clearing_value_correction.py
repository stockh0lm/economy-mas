"""Comprehensive tests for ClearingAgent._apply_value_correction method.

This test module provides thorough coverage for the complex value correction logic
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


def test_apply_value_correction_basic_scenario() -> None:
    """Test basic value correction with retailer write-down reserve and sight balance."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=400.0, cc_balance=-1000.0)
    companies_by_id = {}

    # Test scenario: gap of 600 (1000 CC exposure - 400 inventory)
    # Should use: 100 from write-down reserve + 200 from retailer sight = 300 total
    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=600.0,
        companies_by_id=companies_by_id,
        current_step=100
    )

    assert math.isclose(corrected, 300.0)  # 100 + 200
    assert math.isclose(retailer.write_down_reserve, 0.0)  # Fully used
    assert math.isclose(retailer.sight_balance, 0.0)  # Fully used
    assert math.isclose(clearing.extinguished_total, 300.0)


def test_apply_value_correction_with_company_haircut() -> None:
    """Test value correction that involves pro-rata haircut on recipient companies."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    cfg.clearing.audit_interval = 30
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=300.0, cc_balance=-1000.0)

    # Create companies that received goods from this retailer
    company1 = DummyCompany("company_1", sight_balance=400.0)
    company2 = DummyCompany("company_2", sight_balance=600.0)
    companies_by_id = {
        "company_1": company1,
        "company_2": company2
    }

    # Add purchase records to bank ledger
    bank.goods_purchase_ledger = [
        DummyPurchaseRecord("retailer_1", "company_1", 200.0, 95),
        DummyPurchaseRecord("retailer_1", "company_2", 300.0, 98),
        DummyPurchaseRecord("retailer_1", "company_1", 100.0, 99),
    ]

    # Test scenario: gap of 700, should use:
    # 100 from write-down reserve + 200 from retailer sight + 400 from companies
    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=700.0,
        companies_by_id=companies_by_id,
        current_step=100
    )

    # Expected: 100 (reserve) + 200 (retailer sight) + 400 (companies) = 700
    assert math.isclose(corrected, 700.0)
    assert math.isclose(retailer.write_down_reserve, 0.0)
    assert math.isclose(retailer.sight_balance, 0.0)

    # Companies should be haircut pro-rata based on their purchase amounts
    # company1: 300 total purchases (200+100), company2: 300 purchases
    # So each should contribute 200 (half of the 400 needed from companies)
    assert math.isclose(company1.sight_balance, 200.0)  # 400 - 200
    assert math.isclose(company2.sight_balance, 400.0)  # 600 - 200


def test_apply_value_correction_with_lookback_window() -> None:
    """Test value correction with lookback window filtering."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    cfg.clearing.audit_interval = 30
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=200.0, cc_balance=-800.0)

    company1 = DummyCompany("company_1", sight_balance=500.0)
    company2 = DummyCompany("company_2", sight_balance=500.0)
    companies_by_id = {
        "company_1": company1,
        "company_2": company2
    }

    # Add purchase records with different timestamps
    bank.goods_purchase_ledger = [
        DummyPurchaseRecord("retailer_1", "company_1", 100.0, 50),  # Old - should be excluded
        DummyPurchaseRecord("retailer_1", "company_2", 400.0, 95),  # Recent - should be included
    ]

    # Test with current_step=100, lookback=30, so only records from step 70+ should be included
    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=600.0,
        companies_by_id=companies_by_id,
        current_step=100
    )

    # Should use: 100 (reserve) + 200 (retailer sight) + 300 (from company2 only)
    assert math.isclose(corrected, 600.0)
    assert math.isclose(company1.sight_balance, 500.0)  # Not touched - old record excluded
    assert math.isclose(company2.sight_balance, 200.0)  # 500 - 300


def test_apply_value_correction_with_bank_reserves() -> None:
    """Test value correction that falls back to bank reserves."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1", sight_balance=1000.0)
    bank.clearing_reserve_deposit = 800.0  # High reserve
    retailer = DummyRetailer("retailer_1", inventory_value=100.0, cc_balance=-1000.0)
    retailer.write_down_reserve = 50.0  # Low reserve
    retailer.sight_balance = 100.0  # Low sight balance

    companies_by_id = {}

    # Register bank first to set up reserves in clearing agent
    clearing.register_bank(bank)

    # Test scenario: gap of 900, should use:
    # 50 from write-down reserve + 100 from retailer sight + 750 from bank reserves
    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=900.0,
        companies_by_id=companies_by_id,
        current_step=100
    )

    assert math.isclose(corrected, 900.0)
    assert math.isclose(retailer.write_down_reserve, 0.0)
    assert math.isclose(retailer.sight_balance, 0.0)
    assert math.isclose(clearing.bank_reserves["bank_1"], 50.0)  # 800 - 750
    assert math.isclose(bank.clearing_reserve_deposit, 50.0)  # Synced back


def test_apply_value_correction_partial_allocation() -> None:
    """Test value correction when companies have insufficient funds for full pro-rata allocation."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=100.0, cc_balance=-800.0)

    # Company1 has plenty, company2 has very little
    company1 = DummyCompany("company_1", sight_balance=500.0)
    company2 = DummyCompany("company_2", sight_balance=50.0)  # Very limited
    companies_by_id = {
        "company_1": company1,
        "company_2": company2
    }

    # Both companies received equal amounts
    bank.goods_purchase_ledger = [
        DummyPurchaseRecord("retailer_1", "company_1", 300.0, 95),
        DummyPurchaseRecord("retailer_1", "company_2", 300.0, 95),
    ]

    # Test scenario: need 600 from companies (after using retailer funds)
    # But company2 can only contribute 50, so company1 should cover the rest
    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=700.0,  # 100 reserve + 200 retailer sight + 400 needed from companies
        companies_by_id=companies_by_id,
        current_step=100
    )

    # Should get 100 + 200 + 50 (from company2) + 350 (remaining from company1) = 700
    assert math.isclose(corrected, 700.0)
    assert math.isclose(company1.sight_balance, 150.0)  # 500 - 350
    assert math.isclose(company2.sight_balance, 0.0)    # 50 - 50


def test_apply_value_correction_zero_amount() -> None:
    """Test value correction with zero or negative amount."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1")

    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=0.0,
        companies_by_id={},
        current_step=100
    )

    assert math.isclose(corrected, 0.0)
    assert math.isclose(clearing.extinguished_total, 0.0)

    # Test negative amount
    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=-50.0,
        companies_by_id={},
        current_step=100
    )

    assert math.isclose(corrected, 0.0)
    assert math.isclose(clearing.extinguished_total, 0.0)


def test_apply_value_correction_no_companies() -> None:
    """Test value correction when no companies are available for haircut."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=200.0, cc_balance=-800.0)

    # Test with empty companies dict
    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=600.0,
        companies_by_id={},
        current_step=100
    )

    # Should only get 100 (reserve) + 200 (retailer sight) = 300
    assert math.isclose(corrected, 300.0)
    assert math.isclose(retailer.write_down_reserve, 0.0)
    assert math.isclose(retailer.sight_balance, 0.0)


def test_apply_value_correction_no_ledger() -> None:
    """Test value correction when bank has no goods purchase ledger."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    # Remove ledger attribute to test fallback
    delattr(bank, 'goods_purchase_ledger')

    retailer = DummyRetailer("retailer_1", inventory_value=200.0, cc_balance=-800.0)

    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=retailer,
        amount=600.0,
        companies_by_id={},
        current_step=100
    )

    # Should only get 100 (reserve) + 200 (retailer sight) = 300
    assert math.isclose(corrected, 300.0)