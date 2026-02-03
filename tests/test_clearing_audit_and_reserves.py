"""Tests for ClearingAgent audit and reserve management methods.

This test module provides coverage for the audit_bank and enforce_reserve_bounds methods.
"""

import math
from typing import Any

import config
from agents.clearing_agent import ClearingAgent, AuditFinding


class DummyBank:
    def __init__(self, bank_id: str, sight_balance: float = 1000.0, total_cc_exposure: float = 5000.0) -> None:
        self.unique_id = bank_id
        self.sight_balance = sight_balance
        self.clearing_reserve_deposit = 500.0
        self.total_cc_exposure = total_cc_exposure
        self.goods_purchase_ledger = []

    def write_down_cc(self, retailer: Any, amount: float, reason: str) -> None:
        # Simple implementation for testing
        pass


class DummyRetailer:
    def __init__(self, retailer_id: str, inventory_value: float = 500.0, cc_balance: float = -800.0, write_down_reserve: float = 100.0, sight_balance: float = 200.0) -> None:
        self.unique_id = retailer_id
        self.inventory_value = inventory_value
        self.cc_balance = cc_balance
        self.write_down_reserve = write_down_reserve
        self.sight_balance = sight_balance


def test_enforce_reserve_bounds_low_reserves() -> None:
    """Test enforce_reserve_bounds when reserves are too low."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    cfg.clearing.reserve_bounds_min = 0.1  # 10% minimum
    cfg.clearing.reserve_bounds_max = 0.3  # 30% maximum
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1", sight_balance=2000.0, total_cc_exposure=10000.0)

    # Register bank and set initial low reserves
    clearing.register_bank(bank)
    clearing.bank_reserves["bank_1"] = 500.0  # Only 5% of exposure

    # Min reserve should be 1000 (10% of 10000), so need to move 500 from sight
    clearing.enforce_reserve_bounds(bank)

    assert math.isclose(clearing.bank_reserves["bank_1"], 1000.0)
    assert math.isclose(bank.sight_balance, 1500.0)  # 2000 - 500
    assert math.isclose(bank.clearing_reserve_deposit, 1000.0)


def test_enforce_reserve_bounds_high_reserves() -> None:
    """Test enforce_reserve_bounds when reserves are too high."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    cfg.clearing.reserve_bounds_min = 0.1  # 10% minimum
    cfg.clearing.reserve_bounds_max = 0.3  # 30% maximum
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1", sight_balance=1000.0, total_cc_exposure=10000.0)

    # Register bank and set initial high reserves
    clearing.register_bank(bank)
    clearing.bank_reserves["bank_1"] = 3500.0  # 35% of exposure (above max)

    # Max reserve should be 3000 (30% of 10000), so need to release 500 back to sight
    clearing.enforce_reserve_bounds(bank)

    assert math.isclose(clearing.bank_reserves["bank_1"], 3000.0)
    assert math.isclose(bank.sight_balance, 1500.0)  # 1000 + 500
    assert math.isclose(bank.clearing_reserve_deposit, 3000.0)


def test_enforce_reserve_bounds_no_exposure() -> None:
    """Test enforce_reserve_bounds when bank has no CC exposure."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1", sight_balance=1000.0, total_cc_exposure=0.0)

    # Should return early and not modify anything
    initial_sight = bank.sight_balance
    initial_reserves = len(clearing.bank_reserves)
    clearing.enforce_reserve_bounds(bank)

    assert math.isclose(bank.sight_balance, initial_sight)
    # Bank gets registered but no changes are made due to zero exposure
    assert len(clearing.bank_reserves) > initial_reserves


def test_enforce_reserve_bounds_insufficient_sight() -> None:
    """Test enforce_reserve_bounds when bank has insufficient sight balance to meet minimum reserves."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    cfg.clearing.reserve_bounds_min = 0.2  # 20% minimum
    cfg.clearing.reserve_bounds_max = 0.3  # 30% maximum
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1", sight_balance=500.0, total_cc_exposure=10000.0)

    # Register bank and set initial low reserves
    clearing.register_bank(bank)
    clearing.bank_reserves["bank_1"] = 1000.0  # 10% of exposure

    # Min reserve should be 2000 (20% of 10000), but bank only has 500 sight balance
    # So should move all 500, resulting in 1500 total reserves (still below min)
    clearing.enforce_reserve_bounds(bank)

    assert math.isclose(clearing.bank_reserves["bank_1"], 1500.0)  # 1000 + 500
    assert math.isclose(bank.sight_balance, 0.0)  # All sight balance used
    assert math.isclose(bank.clearing_reserve_deposit, 1500.0)


def test_audit_bank_no_findings() -> None:
    """Test audit_bank when all retailers meet inventory coverage requirements."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    cfg.clearing.audit_interval = 0  # Always audit
    cfg.bank.inventory_coverage_threshold = 0.8  # 80% coverage required
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer1 = DummyRetailer("retailer_1", inventory_value=1000.0, cc_balance=-1000.0)  # 100% coverage
    retailer2 = DummyRetailer("retailer_2", inventory_value=900.0, cc_balance=-1000.0)   # 90% coverage

    findings = clearing.audit_bank(
        bank=bank,
        retailers=[retailer1, retailer2],
        companies_by_id={},
        current_step=100
    )

    assert len(findings) == 0
    assert clearing.last_audit_step == 100


def test_audit_bank_with_findings() -> None:
    """Test audit_bank when retailers have inventory coverage gaps."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    cfg.clearing.audit_interval = 0  # Always audit
    cfg.bank.inventory_coverage_threshold = 0.8  # 80% coverage required
    cfg.clearing.reserve_ratio_step = 0.01  # 1% increase for findings
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer1 = DummyRetailer("retailer_1", inventory_value=700.0, cc_balance=-1000.0)   # 70% coverage (gap: 300)
    retailer2 = DummyRetailer("retailer_2", inventory_value=500.0, cc_balance=-800.0)    # 62.5% coverage (gap: 300)

    findings = clearing.audit_bank(
        bank=bank,
        retailers=[retailer1, retailer2],
        companies_by_id={},
        current_step=100
    )

    assert len(findings) == 2

    # Check first finding
    assert findings[0].bank_id == "bank_1"
    assert findings[0].retailer_id == "retailer_1"
    assert math.isclose(findings[0].inventory_value, 700.0)
    assert math.isclose(findings[0].cc_outstanding, 1000.0)
    assert math.isclose(findings[0].gap, 300.0)  # 1000 - 700

    # Check second finding
    assert findings[1].bank_id == "bank_1"
    assert findings[1].retailer_id == "retailer_2"
    assert math.isclose(findings[1].inventory_value, 500.0)
    assert math.isclose(findings[1].cc_outstanding, 800.0)
    assert math.isclose(findings[1].gap, 300.0)  # 800 - 500

    # Should have increased reserve ratio due to findings
    # Initial ratio is from config, plus step_up
    initial_ratio = float(cfg.clearing.required_reserve_ratio)
    assert math.isclose(clearing.required_reserve_ratio["bank_1"], initial_ratio + 0.01)
    assert clearing.last_audit_step == 100


def test_audit_bank_interval_skipping() -> None:
    """Test audit_bank interval skipping when audits are too frequent."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    cfg.clearing.audit_interval = 30  # Audit every 30 steps
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=500.0, cc_balance=-1000.0)

    # First audit at step 100
    findings1 = clearing.audit_bank(
        bank=bank,
        retailers=[retailer],
        companies_by_id={},
        current_step=100
    )
    assert len(findings1) > 0  # Should find issues
    assert clearing.last_audit_step == 100

    # Second audit at step 105 (too soon)
    findings2 = clearing.audit_bank(
        bank=bank,
        retailers=[retailer],
        companies_by_id={},
        current_step=105
    )
    assert len(findings2) == 0  # Should skip due to interval
    assert clearing.last_audit_step == 100  # Should not update

    # Third audit at step 130 (after interval)
    findings3 = clearing.audit_bank(
        bank=bank,
        retailers=[retailer],
        companies_by_id={},
        current_step=130
    )
    assert len(findings3) > 0  # Should find issues again
    assert clearing.last_audit_step == 130  # Should update


def test_audit_bank_zero_cc_balance() -> None:
    """Test audit_bank when retailer has zero CC balance."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    cfg.clearing.audit_interval = 0  # Always audit
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer1 = DummyRetailer("retailer_1", inventory_value=100.0, cc_balance=0.0)      # Zero CC
    retailer2 = DummyRetailer("retailer_2", inventory_value=500.0, cc_balance=-1000.0)  # Normal

    findings = clearing.audit_bank(
        bank=bank,
        retailers=[retailer1, retailer2],
        companies_by_id={},
        current_step=100
    )

    # Should only have findings for retailer2
    assert len(findings) == 1
    assert findings[0].retailer_id == "retailer_2"


def test_audit_bank_triggers_value_correction() -> None:
    """Test that audit_bank triggers value correction for retailers with coverage gaps."""
    cfg = config.CONFIG_MODEL.model_copy(deep=True)
    cfg.clearing.audit_interval = 0  # Always audit
    cfg.bank.inventory_coverage_threshold = 0.8  # 80% coverage required
    clearing = ClearingAgent("clear_1", cfg)

    bank = DummyBank("bank_1")
    retailer = DummyRetailer("retailer_1", inventory_value=600.0, cc_balance=-1000.0, write_down_reserve=200.0, sight_balance=300.0)

    # Register bank to set up reserves
    clearing.register_bank(bank)
    clearing.bank_reserves["bank_1"] = 1000.0

    findings = clearing.audit_bank(
        bank=bank,
        retailers=[retailer],
        companies_by_id={},
        current_step=100
    )

    assert len(findings) == 1
    assert math.isclose(findings[0].gap, 400.0)  # 1000 - 600

    # Value correction should have been triggered
    # Should use: 200 (write-down reserve) + 200 (retailer sight) = 400 total
    # Gap was 400, so should extinguish exactly 400 (no bank reserves needed)
    assert math.isclose(retailer.write_down_reserve, 0.0)  # Fully used
    assert math.isclose(retailer.sight_balance, 100.0)    # 300 - 200
    assert math.isclose(clearing.bank_reserves["bank_1"], 1000.0)  # Unchanged - not needed
