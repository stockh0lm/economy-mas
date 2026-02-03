"""Comprehensive tests for _settle_household_estate function.

This test module provides thorough coverage for the complex estate settlement logic
as described in doc/issues.md Abschnitt 4.
"""

import math
from agents.household_agent import Household
from agents.savings_bank_agent import SavingsBank
from agents.state_agent import State
from config import CONFIG_MODEL
from main import _settle_household_estate


def test_settle_household_estate_basic_scenario():
    """Test basic estate settlement with no loans, single heir."""
    # Setup
    config = CONFIG_MODEL.model_copy(deep=True)
    deceased = Household("deceased", config=config)
    deceased.sight_balance = 1000.0
    deceased.local_savings = 500.0

    heir = Household("heir", config=config)
    heir.sight_balance = 100.0

    state = State("state", config=config)
    state.tax_revenue = 500.0  # Set initial state funds via tax_revenue

    savings_bank = SavingsBank("savings", config=config)
    savings_bank.deposit_savings(deceased, 2000.0)

    # Test
    _settle_household_estate(
        deceased=deceased,
        heir=heir,
        state=state,
        savings_bank=savings_bank,
        config=config
    )

    # Verify
    # Heir should receive all assets (default inheritance_share_on_death = 1.0)
    expected_heir_sight = 100.0 + 1000.0 + 500.0  # original + deceased sight + local savings
    assert math.isclose(heir.sight_balance, expected_heir_sight)

    # Heir should receive deceased's savings account
    assert math.isclose(savings_bank.savings_accounts.get("heir", 0.0), 2000.0)

    # Deceased balances should be zeroed
    assert math.isclose(deceased.sight_balance, 0.0)
    assert math.isclose(deceased.local_savings, 0.0)

    # Deceased savings account should be removed
    assert "deceased" not in savings_bank.savings_accounts

    # State should be unchanged (sight_balance is calculated from sub-budgets)
    assert math.isclose(state.sight_balance, 500.0)
    assert math.isclose(state.tax_revenue, 500.0)


def test_settle_household_estate_with_loan_repayment():
    """Test estate settlement with outstanding savings bank loan."""
    # Setup
    config = CONFIG_MODEL.model_copy(deep=True)
    deceased = Household("deceased", config=config)
    deceased.sight_balance = 1500.0
    deceased.local_savings = 500.0

    heir = Household("heir", config=config)
    heir.sight_balance = 100.0

    state = State("state", config=config)
    state.tax_revenue = 500.0  # Set initial state funds

    savings_bank = SavingsBank("savings", config=config)
    savings_bank.deposit_savings(deceased, 2000.0)
    savings_bank.active_loans["deceased"] = 1800.0  # Loan to repay

    # Test
    _settle_household_estate(
        deceased=deceased,
        heir=heir,
        state=state,
        savings_bank=savings_bank,
        config=config
    )

    # Verify loan repayment
    # Should repay from: sight (1500) + local savings (500) + deposits (2000) = 4000 available
    # Loan is 1800, so full repayment possible
    assert "deceased" not in savings_bank.active_loans

    # Heir should receive remaining assets
    remaining_sight = 1500.0 - min(1500.0, 1800.0)  # 1500 used from sight
    remaining_local = 500.0 - min(max(0.0, 1800.0 - 1500.0), 500.0)  # 300 used from local savings
    remaining_deposit = 2000.0 - max(0.0, 1800.0 - 1500.0 - 500.0)  # 0 used from deposits

    expected_heir_sight = 100.0 + remaining_sight + remaining_local
    assert math.isclose(heir.sight_balance, expected_heir_sight, rel_tol=1e-6)
    assert math.isclose(savings_bank.savings_accounts.get("heir", 0.0), remaining_deposit, rel_tol=1e-6)

    # State should be unchanged
    assert math.isclose(state.tax_revenue, 500.0)


def test_settle_household_estate_partial_loan_repayment():
    """Test estate settlement with insufficient assets to repay loan."""
    # Setup
    config = CONFIG_MODEL.model_copy(deep=True)
    deceased = Household("deceased", config=config)
    deceased.sight_balance = 500.0
    deceased.local_savings = 200.0

    heir = Household("heir", config=config)
    heir.sight_balance = 100.0

    state = State("state", config=config)
    state.tax_revenue = 500.0  # Set initial state funds

    savings_bank = SavingsBank("savings", config=config)
    savings_bank.deposit_savings(deceased, 300.0)
    savings_bank.active_loans["deceased"] = 2000.0  # Large loan
    savings_bank.risk_reserve = 1000.0  # Risk reserve available
    savings_bank.available_funds = 500.0  # Liquidity available

    # Test
    _settle_household_estate(
        deceased=deceased,
        heir=heir,
        state=state,
        savings_bank=savings_bank,
        config=config
    )

    # Verify partial repayment
    # Available assets: 500 (sight) + 200 (local) + 300 (deposits) = 1000
    # Loan is 2000, so 1000 repaid from assets, 1000 remaining
    # Remaining 1000 should be covered by risk reserve (1000) + liquidity (500)
    assert "deceased" not in savings_bank.active_loans

    # Heir should receive nothing (all assets used for repayment)
    assert math.isclose(heir.sight_balance, 100.0)  # Unchanged
    assert "heir" not in savings_bank.savings_accounts  # No inheritance

    # Risk reserve and liquidity should be reduced
    assert math.isclose(savings_bank.risk_reserve, 0.0)  # 1000 used
    assert math.isclose(savings_bank.available_funds, 500.0)  # Not used since risk reserve covered the remaining loan

    # State should be unchanged
    assert math.isclose(state.tax_revenue, 500.0)


def test_settle_household_estate_no_heir():
    """Test estate settlement with no heir (assets go to state)."""
    # Setup
    config = CONFIG_MODEL.model_copy(deep=True)
    deceased = Household("deceased", config=config)
    deceased.sight_balance = 1000.0
    deceased.local_savings = 500.0

    state = State("state", config=config)
    state.tax_revenue = 500.0  # Initial state funds

    savings_bank = SavingsBank("savings", config=config)
    savings_bank.deposit_savings(deceased, 2000.0)

    initial_state_sight = state.sight_balance  # 500.0

    # Test with no heir
    _settle_household_estate(
        deceased=deceased,
        heir=None,  # No heir
        state=state,
        savings_bank=savings_bank,
        config=config
    )

    # Verify state receives all assets
    # State should receive: 1000 (sight) + 500 (local savings) = 1500
    # State sight balance should be initial (500) + 1500 = 2000
    expected_state_sight = initial_state_sight + 1000.0 + 500.0
    assert math.isclose(state.sight_balance, expected_state_sight)

    # State should receive deceased's savings account
    assert math.isclose(savings_bank.savings_accounts.get("state", 0.0), 2000.0)

    # Deceased balances should be zeroed
    assert math.isclose(deceased.sight_balance, 0.0)
    assert math.isclose(deceased.local_savings, 0.0)


def test_settle_household_estate_inheritance_share():
    """Test estate settlement with inheritance share configuration."""
    # Setup
    config = CONFIG_MODEL.model_copy(deep=True)
    config.household.inheritance_share_on_death = 0.7  # 70% to heir, 30% to state

    deceased = Household("deceased", config=config)
    deceased.sight_balance = 1000.0
    deceased.local_savings = 0.0  # Simpler calculation

    heir = Household("heir", config=config)
    heir.sight_balance = 100.0

    state = State("state", config=config)
    state.tax_revenue = 500.0  # Initial state funds

    savings_bank = SavingsBank("savings", config=config)
    # No deposits for simpler calculation

    initial_state_sight = state.sight_balance  # 500.0

    # Test
    _settle_household_estate(
        deceased=deceased,
        heir=heir,
        state=state,
        savings_bank=savings_bank,
        config=config
    )

    # Verify correct split
    heir_share = 1000.0 * 0.7
    state_share = 1000.0 * 0.3

    expected_heir_sight = 100.0 + heir_share
    expected_state_tax_revenue = initial_state_sight + state_share

    assert math.isclose(heir.sight_balance, expected_heir_sight, rel_tol=1e-6)
    assert math.isclose(state.tax_revenue, expected_state_tax_revenue, rel_tol=1e-6)


def test_settle_household_estate_with_zero_balances():
    """Test estate settlement when deceased has no assets."""
    # Setup
    config = CONFIG_MODEL.model_copy(deep=True)
    deceased = Household("deceased", config=config)
    deceased.sight_balance = 0.0
    deceased.local_savings = 0.0

    heir = Household("heir", config=config)
    heir.sight_balance = 100.0

    state = State("state", config=config)
    state.tax_revenue = 500.0  # Initial state funds

    savings_bank = SavingsBank("savings", config=config)
    # No deposits

    initial_heir_sight = heir.sight_balance
    initial_state_sight = state.sight_balance

    # Test
    _settle_household_estate(
        deceased=deceased,
        heir=heir,
        state=state,
        savings_bank=savings_bank,
        config=config
    )

    # Verify no changes when deceased has no assets
    assert math.isclose(heir.sight_balance, initial_heir_sight)  # Unchanged
    assert math.isclose(state.sight_balance, initial_state_sight)  # Unchanged
    assert math.isclose(deceased.sight_balance, 0.0)  # Still zero
    assert math.isclose(deceased.local_savings, 0.0)  # Still zero


def test_settle_household_estate_edge_case_empty_deceased_id():
    """Test edge case where deceased has empty unique_id."""
    # Setup
    config = CONFIG_MODEL.model_copy(deep=True)
    deceased = Household("", config=config)  # Empty ID
    deceased.sight_balance = 1000.0

    heir = Household("heir", config=config)
    heir.sight_balance = 100.0

    state = State("state", config=config)
    state.tax_revenue = 500.0  # Initial state funds

    savings_bank = SavingsBank("savings", config=config)

    initial_heir_sight = heir.sight_balance
    initial_state_sight = state.sight_balance
    initial_deceased_sight = deceased.sight_balance

    # Test - should handle gracefully (early return)
    _settle_household_estate(
        deceased=deceased,
        heir=heir,
        state=state,
        savings_bank=savings_bank,
        config=config
    )

    # Verify no changes when deceased ID is empty
    assert math.isclose(heir.sight_balance, initial_heir_sight)  # Unchanged
    assert math.isclose(state.sight_balance, initial_state_sight)  # Unchanged
    assert math.isclose(deceased.sight_balance, initial_deceased_sight)  # Unchanged
