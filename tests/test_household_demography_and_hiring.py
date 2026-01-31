from config import SimulationConfig
from sim_clock import SimulationClock


def test_household_growth_can_split_with_savings_bank(tmp_path):
    """Unit-level check: a household with sufficient savings triggers growth and can split."""

    cfg = SimulationConfig(simulation_steps=1)
    cfg.metrics_export_path = str(tmp_path / "metrics")
    cfg.log_file = str(tmp_path / "simulation.log")
    from agents.household_agent import Household
    from agents.savings_bank_agent import SavingsBank

    sb = SavingsBank(unique_id="sb", config=cfg)
    h = Household(unique_id="h", config=cfg)

    # Ensure the savings bank has enough liquid funds to honor withdrawals.
    sb.available_funds = 1_000_000.0

    # The household withdraws child_rearing_cost each growth step (see Household.step),
    # so we need enough savings to cover that AND still exceed the growth trigger so
    # growth_phase stays True until splitting.
    required = (
        float(cfg.household.savings_growth_trigger)
        + float(cfg.household.child_rearing_cost) * float(cfg.household.growth_threshold)
        + 500.0
    )
    sb.savings_accounts[h.unique_id] = required

    clock = SimulationClock(cfg.time)

    newborn = None
    for step in range(cfg.household.growth_threshold):
        newborn = h.step(current_step=step, clock=clock, savings_bank=sb, retailers=None)

    assert newborn is not None
    assert newborn.unique_id != h.unique_id
    assert newborn.sight_balance > 0


def test_company_hiring_works_round_robin(tmp_path):
    """Unit-level check: labor market matches workers across employers fairly."""

    cfg = SimulationConfig(simulation_steps=1)
    cfg.metrics_export_path = str(tmp_path / "metrics")
    cfg.log_file = str(tmp_path / "simulation.log")
    from agents.labor_market import LaborMarket
    from agents.company_agent import Company
    from agents.household_agent import Household

    lm = LaborMarket(unique_id="lm", config=cfg)

    workers = [Household(unique_id=f"h{i}", config=cfg) for i in range(10)]
    for w in workers:
        lm.register_worker(w)

    c1 = Company(unique_id="c1", config=cfg)
    c2 = Company(unique_id="c2", config=cfg)

    # Offer 5 positions each.
    lm.register_job_offer(c1, wage=10.0, positions=5)
    lm.register_job_offer(c2, wage=10.0, positions=5)

    matches = lm.match_workers_to_jobs()
    assert len(matches) == 10
    assert len(c1.employees) == 5
    assert len(c2.employees) == 5
