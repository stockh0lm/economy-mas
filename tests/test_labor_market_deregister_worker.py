from agents.labor_market import LaborMarket
from agents.household_agent import Household
from config import SimulationConfig


def test_labor_market_deregister_worker_removes_worker_and_is_idempotent() -> None:
    cfg = SimulationConfig(simulation_steps=1)
    lm = LaborMarket(unique_id="labor_market", config=cfg)

    w = Household(unique_id="h0", config=cfg)
    lm.register_worker(w)
    assert w in lm.registered_workers

    assert lm.deregister_worker(w) is True
    assert w not in lm.registered_workers

    # idempotent: removing twice returns False and doesn't raise
    assert lm.deregister_worker(w) is False


def test_labor_market_replace_worker_swaps_registration() -> None:
    cfg = SimulationConfig(simulation_steps=1)
    lm = LaborMarket(unique_id="labor_market", config=cfg)

    old = Household(unique_id="h_old", config=cfg)
    new = Household(unique_id="h_new", config=cfg)

    lm.register_worker(old)
    assert old in lm.registered_workers

    lm.replace_worker(old, new)
    assert old not in lm.registered_workers
    assert new in lm.registered_workers
