import math

from agents.household_agent import Household
from agents.savings_bank_agent import SavingsBank
from config import CONFIG_MODEL


def test_household_uses_savings_bank_withdrawal_for_child_costs() -> None:
    bank = SavingsBank("savings_test", CONFIG_MODEL)
    household = Household("hh_withdraw", config=CONFIG_MODEL)
    household.savings = 500.0

    bank.deposit_savings(household, 300.0)

    withdrawn = household._handle_childrearing_costs(bank)

    assert math.isclose(withdrawn, CONFIG_MODEL.child_rearing_cost)
    remaining = bank.savings_accounts.get(household.unique_id, 0.0)
    assert remaining <= max(0.0, 300.0 - withdrawn)


def test_household_repay_savings_bank_loans() -> None:
    bank = SavingsBank("savings_test", CONFIG_MODEL)
    household = Household("hh_repay", config=CONFIG_MODEL)
    household.checking_account = 400.0
    bank.active_loans[household.unique_id] = 200.0

    repaid = household._repay_savings_loans(bank)

    expected = 400.0 * CONFIG_MODEL.household_loan_repayment_rate
    assert math.isclose(repaid, expected)
    assert math.isclose(bank.active_loans[household.unique_id], 200.0 - repaid)

