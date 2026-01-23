import pytest

from agents.company_agent import Company
from agents.household_agent import Household
from config import load_simulation_config


def test_goods_sale_reduces_household_deposits_and_inventory() -> None:
    """Baseline behaviour: selling goods should reduce household deposits and company inventory."""

    cfg = load_simulation_config({"company": {"production_base_price": 10.0}})

    company = Company("c1", production_capacity=0.0, config=cfg)
    company.inventory = 10.0

    household = Household("h1", config=cfg)
    household.checking_account = 100.0

    spent = company.sell_to_household(household, budget=50.0)

    assert spent > 0
    assert household.checking_account == pytest.approx(100.0 - spent)
    assert company.inventory < 10.0


@pytest.mark.xfail(reason="Contract test: requires future Warengeld money-extinguishing implementation")
def test_contract_goods_sale_extinguishes_money_instead_of_accumulating_company_balance() -> None:
    """Desired future behaviour: company shouldn't simply accumulate money when goods are sold.

    In the Warengeld regime, payment for goods should be routed to bank/clearing and extinguished
    (or directly reduce issued Warengeld liabilities). This test documents the intended contract.
    """

    cfg = load_simulation_config({"company": {"production_base_price": 10.0}})

    company = Company("c1", production_capacity=0.0, config=cfg)
    company.inventory = 10.0
    company.balance = 0.0

    household = Household("h1", config=cfg)
    household.checking_account = 100.0

    spent = company.sell_to_household(household, budget=50.0)

    # Contract: company balance should not rise as free money.
    assert company.balance == pytest.approx(0.0)
    assert spent > 0


@pytest.mark.xfail(reason="Contract test: requires future Warengeld issuance tied to goods financing")
def test_contract_goods_financing_is_only_source_of_new_money() -> None:
    """Desired future behaviour: money is created only when goods are financed via bank."""

    # The future implementation will likely introduce a bank API such as
    # `finance_goods_purchase(company, amount)` which increases issued Warengeld.
    # This placeholder asserts the future existence/behaviour.

    raise AssertionError("not implemented")

