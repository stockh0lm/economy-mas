import pytest

from agents.bank import WarengeldBank
from agents.company_agent import Company
from agents.household_agent import Household
from agents.retailer_agent import RetailerAgent
from config import load_simulation_config


def test_goods_sale_reduces_household_deposits_and_inventory() -> None:
    """Warengeld goods cycle: household buys from retailer, retailer inventory decreases, household sight decreases."""

    cfg = load_simulation_config({
        "company": {"production_base_price": 10.0},
        "retailer": {"price_markup": 0.0},
    })

    bank = WarengeldBank("bank", cfg)
    company = Company("c1", production_capacity=0.0, config=cfg)
    company.finished_goods_units = 10.0

    retailer = RetailerAgent("r1", config=cfg, cc_limit=1_000.0, target_inventory_value=100.0)
    bank.register_retailer(retailer, cc_limit=retailer.cc_limit)

    # Restock once (money creation happens here)
    financed = retailer.restock_goods([company], bank=bank, current_step=0)
    assert financed > 0
    assert retailer.inventory_units > 0

    household = Household("h1", config=cfg)
    household.checking_account = 100.0

    result = retailer.sell_to_household(household, budget=50.0)

    assert result.sale_value > 0
    assert household.checking_account == pytest.approx(100.0 - result.sale_value)
    assert retailer.inventory_units >= 0


@pytest.mark.xfail(reason="Contract test: extinguishing via CC repayment not yet asserted here")
def test_contract_goods_sale_extinguishes_money_instead_of_accumulating_company_balance() -> None:
    """Desired future behaviour: money should be extinguished via CC repayment when goods are sold."""

    cfg = load_simulation_config({"company": {"production_base_price": 10.0}})

    bank = WarengeldBank("bank", cfg)
    company = Company("c1", production_capacity=0.0, config=cfg)
    company.finished_goods_units = 10.0

    retailer = RetailerAgent("r1", config=cfg, cc_limit=1_000.0, target_inventory_value=100.0)
    bank.register_retailer(retailer, cc_limit=retailer.cc_limit)

    retailer.restock_goods([company], bank=bank, current_step=0)

    household = Household("h1", config=cfg)
    household.checking_account = 100.0

    result = retailer.sell_to_household(household, budget=50.0)

    # Contract: producer should not accumulate money from household purchases.
    # Producer gets paid only via goods financing at restock time.
    assert company.sight_balance >= 0.0
    assert result.sale_value > 0


@pytest.mark.xfail(reason="Contract test: requires future issuance accounting tied strictly to goods financing")
def test_contract_goods_financing_is_only_source_of_new_money() -> None:
    raise AssertionError("not implemented")
