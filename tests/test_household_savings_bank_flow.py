from __future__ import annotations

import math

from agents.household_agent import Household
from agents.savings_bank_agent import SavingsBank
from config import CONFIG_MODEL


def test_household_child_costs_only_during_growth_phase() -> None:
    bank = SavingsBank("savings_test", CONFIG_MODEL)
    household = Household("hh_withdraw", config=CONFIG_MODEL)
    household.savings = 100.0

    bank.deposit_savings(household, 300.0)

    assert household._handle_childrearing_costs(bank) == 0.0

    household.growth_phase = True
    household.child_cost_covered = False

    withdrawn = household._handle_childrearing_costs(bank)

    assert math.isclose(withdrawn, CONFIG_MODEL.household.child_rearing_cost)
    assert household.child_cost_covered
    remaining = bank.savings_accounts.get(household.unique_id, 0.0)
    assert remaining <= max(0.0, 300.0 - CONFIG_MODEL.household.child_rearing_cost)


def test_household_growth_phase_triggers_from_bank_savings() -> None:
    bank = SavingsBank("savings_test", CONFIG_MODEL)
    household = Household("hh_growth", config=CONFIG_MODEL)
    household.income = 0.0
    bank.deposit_savings(household, CONFIG_MODEL.household.savings_growth_trigger + 100.0)
    
    result = household.step(current_step=1, savings_bank=bank)

    assert result is None
    assert household.growth_phase
    assert household.child_cost_covered
    bank_balance = bank.savings_accounts.get(household.unique_id, 0.0)
    assert math.isclose(
        bank_balance + household.savings + household.checking_account,
        CONFIG_MODEL.household.savings_growth_trigger + 100.0,
        rel_tol=1e-6,
    )


def test_household_repay_savings_bank_loans() -> None:
    bank = SavingsBank("savings_test", CONFIG_MODEL)
    household = Household("hh_repay", config=CONFIG_MODEL)
    household.checking_account = 400.0
    bank.active_loans[household.unique_id] = 200.0

    repaid = household._repay_savings_loans(bank)

    expected = 400.0 * CONFIG_MODEL.household.loan_repayment_rate
    assert math.isclose(repaid, expected)
    assert math.isclose(bank.active_loans[household.unique_id], 200.0 - repaid)
