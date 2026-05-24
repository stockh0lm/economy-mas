import math

import pytest

from agents.environmental_agency import EnvironmentalAgency, RecyclingCompany
from agents.state_agent import State
from config import SimulationConfig


class DummyAgent:
    def __init__(self, unique_id: str, impact: float, balance: float = 100.0):
        self.unique_id = unique_id
        self.environmental_impact = impact
        self.balance = balance


@pytest.fixture()
def env_setup() -> tuple[EnvironmentalAgency, State, list[DummyAgent]]:
    config = SimulationConfig()
    state = State("state_test", config)
    agency = EnvironmentalAgency("env_test", state=state, config=config)
    agents = [DummyAgent("a1", 2.0), DummyAgent("a2", 3.0)]
    return agency, state, agents


def test_collect_env_tax_deducts_balance_and_updates_state(env_setup) -> None:
    agency, state, agents = env_setup
    initial_balances = [agent.balance for agent in agents]

    total_tax = agency.collect_env_tax(agents, state)

    expected_tax = sum(agent.environmental_impact for agent in agents) * agency.config.tax_rates.umweltsteuer
    assert math.isclose(total_tax, expected_tax)
    for idx, agent in enumerate(agents):
        assert agent.balance == pytest.approx(initial_balances[idx] - agent.environmental_impact * agency.config.tax_rates.umweltsteuer)
    assert state.environment_budget > 0
    assert agency.env_tax_transferred_to_state == state.environment_budget


def test_recycling_company_collects_waste(env_setup) -> None:
    agency, state, agents = env_setup
    recycler = RecyclingCompany("recycler_test", config=agency.config)
    agency.attach_recycling_company(recycler)

    agency.collect_env_tax(agents, state)

    expected_waste = sum(agent.environmental_impact for agent in agents) * agency.config.environmental.waste_output_per_env_impact
    assert recycler.waste_collected == pytest.approx(expected_waste)



def test_environmental_tax_is_capped_by_available_balance_and_routed_to_state() -> None:
    config = SimulationConfig()
    config.tax_rates.umweltsteuer = 1.0
    state = State("state_test", config)
    agency = EnvironmentalAgency("env_test", state=state, config=config)
    agent = DummyAgent("poor", impact=10.0, balance=3.0)

    paid = agency.collect_env_tax([agent], state)

    assert paid == pytest.approx(3.0)
    assert agent.balance == pytest.approx(0.0)
    assert state.environment_budget + state.tax_revenue == pytest.approx(3.0)


def test_environmental_penalties_are_capped_and_paid_to_public_budget() -> None:
    config = SimulationConfig()
    state = State("state_test", config)
    agency = EnvironmentalAgency("env_test", state=state, config=config)
    agency.set_env_standards({"max_environmental_impact": 1.0})
    company = DummyAgent("dirty", impact=5.0, balance=7.0)

    paid = agency.audit_company(company, state)

    assert paid == pytest.approx(7.0)
    assert company.balance == pytest.approx(0.0)
    assert state.environment_budget == pytest.approx(7.0)
    assert agency.environmental_penalties_transferred_to_state == pytest.approx(7.0)
