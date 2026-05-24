from config import InitialCompany, InitialHousehold, InitialRetailer, SimulationConfig
from simulation.engine import create_companies, create_households, create_retailers, initialize_agents


def test_population_templates_seed_initial_agent_stocks() -> None:
    config = SimulationConfig()
    config.population.num_households = 2
    config.population.household_template = InitialHousehold(
        income=100.0,
        initial_sight_balance=125.0,
        initial_local_savings=45.0,
    )
    config.population.num_companies = 1
    config.population.company_template = InitialCompany(
        production_capacity=80.0,
        initial_sight_balance=300.0,
        initial_finished_goods_units=12.0,
    )
    config.population.num_retailers = 1
    config.population.retailer_template = InitialRetailer(
        initial_cc_limit=900.0,
        target_inventory_value=250.0,
        initial_sight_balance=70.0,
        initial_inventory_units=9.0,
        initial_inventory_unit_cost=11.0,
    )

    households = create_households(config)
    companies = create_companies(config)
    retailers = create_retailers(config)

    assert {h.sight_balance for h in households} == {125.0}
    assert {h.local_savings for h in households} == {45.0}

    assert companies[0].sight_balance == 300.0
    assert companies[0].finished_goods_units == 12.0

    assert retailers[0].sight_balance == 70.0
    assert retailers[0].cc_limit == 900.0
    assert retailers[0].inventory_units == 9.0
    assert retailers[0].inventory_value == 99.0


def test_state_and_bank_initial_balances_are_configurable() -> None:
    config = SimulationConfig()
    config.spatial.num_regions = 1
    config.state.initial_tax_revenue = 100.0
    config.state.initial_infrastructure_budget = 200.0
    config.state.initial_social_budget = 300.0
    config.state.initial_environment_budget = 400.0
    config.bank.initial_sight_balance = 50.0

    agents = initialize_agents(config)
    state = agents["state"]
    bank = agents["warengeld_banks"][0]

    assert state.tax_revenue == 100.0
    assert state.infrastructure_budget == 200.0
    assert state.social_budget == 300.0
    assert state.environment_budget == 400.0
    assert state.sight_balance == 1000.0
    assert bank.sight_balance == 50.0
