import math

from agents.company_agent import Company
from agents.household_agent import Household
from config import CONFIG_MODEL


def make_employee(uid: str) -> Household:
    return Household(uid)


def test_produce_scales_with_employee_count() -> None:
    company = Company("C1", production_capacity=100.0, max_employees=10)

    company.produce()
    assert math.isclose(company.inventory, 0.0)

    company.employees = [make_employee(f"h{i}") for i in range(5)]
    company.produce()

    assert math.isclose(company.inventory, 50.0)


def test_sell_goods_reduces_inventory_and_increases_balance() -> None:
    company = Company("C2", production_capacity=100.0)
    company.inventory = 80.0
    company.innovation_index = 1

    revenue = company.sell_goods(demand=50.0)

    assert math.isclose(company.inventory, 30.0)
    assert math.isclose(revenue, company.balance)

    base_price = CONFIG_MODEL.production_base_price
    bonus_rate = CONFIG_MODEL.production_innovation_bonus_rate
    expected_price_per_unit = base_price * (1 + bonus_rate * company.innovation_index)
    assert math.isclose(revenue, 50.0 * expected_price_per_unit)
