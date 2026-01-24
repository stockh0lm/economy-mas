import math
import pytest

from agents.company_agent import Company
from agents.household_agent import Household
from config import CONFIG_MODEL


def make_employee(uid: str) -> Household:
    return Household(uid)


def test_produce_scales_with_employee_count() -> None:
    company = Company("C1", production_capacity=100.0, max_employees=10)

    company.produce()
    assert math.isclose(company.finished_goods_units, 0.0)

    company.employees = [make_employee(f"h{i}") for i in range(5)]
    company.produce()

    assert math.isclose(company.finished_goods_units, 50.0)


def test_sell_goods_is_legacy_and_disabled() -> None:
    company = Company("C2", production_capacity=100.0)
    company.finished_goods_units = 80.0
    company.innovation_index = 1

    with pytest.raises(RuntimeError):
        _ = company.sell_goods(demand=50.0)
