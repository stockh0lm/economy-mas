from __future__ import annotations

from config import SimulationConfig
from agents.company_agent import Company
from agents.household_agent import Household
from agents.labor_market import LaborMarket
from agents.state_agent import State


def test_company_bankruptcy_releases_employees_back_to_labor_market() -> None:
    cfg = SimulationConfig(simulation_steps=1)
    lm = LaborMarket(unique_id="lm", config=cfg)
    state = State(unique_id="state", config=cfg)
    state.labor_market = lm

    worker = Household(unique_id="h0", config=cfg)
    worker.employed = True
    worker.current_wage = 10.0
    lm.register_worker(worker)

    company = Company(unique_id="c0", config=cfg)
    company.employees = [worker]
    company.sight_balance = -1e9  # force bankruptcy

    result = company.step(current_step=0, state=state, savings_bank=None)
    assert result == "DEAD"

    # must be released and re-matchable
    assert worker.employed is False
    assert worker.current_wage is None
    assert company.employees == []


def test_company_adjust_employees_drops_stale_employee_references() -> None:
    cfg = SimulationConfig(simulation_steps=1)
    lm = LaborMarket(unique_id="lm", config=cfg)

    live = Household(unique_id="h_live", config=cfg)
    stale = Household(unique_id="h_stale", config=cfg)

    lm.register_worker(live)
    company = Company(unique_id="c0", config=cfg)
    company.employees = [live, stale]

    company.adjust_employees(lm)

    assert stale not in company.employees
    assert live in company.employees
