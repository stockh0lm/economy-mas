import math

import pytest

from agents.company_agent import Company
from agents.household_agent import Household
from config import SimulationConfig


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


def test_company_step_allows_single_zero_money_bootstrap_lot() -> None:
    cfg = SimulationConfig(simulation_steps=1)
    cfg.company.inventory_depreciation_rate = 0.0
    cfg.company.profit_distribution_enabled = False
    cfg.company.bankruptcy_threshold = -1_000_000.0
    company = Company("C3", production_capacity=100.0, max_employees=10, config=cfg)
    company.employees = [make_employee("h0")]

    result = company.step(current_step=0)

    assert result is None
    assert math.isclose(company.finished_goods_units, 10.0)
    assert math.isclose(company.last_wage_pay_ratio, 1.0)


def test_company_step_blocks_unfunded_ongoing_production() -> None:
    cfg = SimulationConfig(simulation_steps=1)
    cfg.company.inventory_depreciation_rate = 0.0
    cfg.company.profit_distribution_enabled = False
    cfg.company.bankruptcy_threshold = -1_000_000.0
    company = Company("C4", production_capacity=100.0, max_employees=10, config=cfg)
    company.employees = [make_employee("h0")]
    company.finished_goods_units = 20.0

    result = company.step(current_step=1)

    assert result is None
    assert math.isclose(company.finished_goods_units, 20.0)
    assert math.isclose(company.last_wage_pay_ratio, 0.0)

