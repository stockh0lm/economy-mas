from __future__ import annotations

from config import SimulationConfig
from main import run_simulation


def test_simulation_company_and_household_turnover() -> None:
    """Regression test: lifecycle events must affect the live agent lists."""

    cfg = SimulationConfig(simulation_steps=25)

    # Force early turnover via high mortality (age-dependent hazard in the scheduler).
    cfg.population.num_households = 20
    cfg.population.num_companies = 5
    cfg.population.num_retailers = 3
    cfg.household.mortality_base_annual = 5.0

    agents = run_simulation(cfg)

    households = agents["households"]
    companies = agents["companies"]

    assert len(households) > 0
    assert len(companies) > 0

    ids = [h.unique_id for h in households]
    assert len(set(ids)) == len(ids)

    initial_count = cfg.population.num_households or len(cfg.INITIAL_HOUSEHOLDS)
    prefix = cfg.HOUSEHOLD_ID_PREFIX
    assert any(int(h.unique_id.replace(prefix, "", 1)) >= int(initial_count) for h in households)


def test_household_growth_can_create_new_households() -> None:
    cfg = SimulationConfig(simulation_steps=1)

    # Force quick split.
    cfg.household.savings_growth_trigger = 1.0  # type: ignore[attr-defined]
    cfg.household.growth_threshold = 1  # type: ignore[attr-defined]

    # Unit-test the canonical behavior directly, without requiring the full wage/income pipeline.
    from agents.household_agent import Household
    from agents.savings_bank_agent import SavingsBank

    sb = SavingsBank(unique_id="sb", config=cfg)
    h = Household(unique_id="h0", config=cfg)

    # Ensure total savings is above growth trigger.
    h.local_savings = 100.0

    from sim_clock import SimulationClock

    clock = SimulationClock(cfg.time)
    newborn = h.step(current_step=0, clock=clock, savings_bank=sb, retailers=None)
    assert newborn is not None
