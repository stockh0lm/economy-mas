from agents.household_agent import Household
from agents.savings_bank_agent import SavingsBank
from config import SimulationConfig
from sim_clock import SimulationClock


def test_household_can_enter_growth_phase_and_split_based_on_sight_balance(tmp_path):
    """Regression: households should be able to split even when savings_rate=0.

    The refactor introduced a de-facto requirement to accumulate SavingsBank deposits
    (via savings_rate) to ever hit savings_growth_trigger. In typical configs
    savings_rate is 0, so growth never triggers and household count never increases.

    We now allow a disposable sight-balance trigger, which should enable splits
    when the household repeatedly has enough leftover money.
    """

    cfg = SimulationConfig(simulation_steps=10)
    cfg.household.growth_threshold = 2
    cfg.household.max_generation = 3
    cfg.household.savings_rate = 0.0
    cfg.household.transaction_buffer = 0.0
    # Make the new trigger easy to reach: 50
    cfg.household.sight_growth_trigger = 50.0

    sb = SavingsBank(unique_id="sb", config=cfg)

    h = Household(unique_id="h0", config=cfg)
    h.sight_balance = 100.0

    clock = SimulationClock(cfg.time)

    newborn = None
    for step in range(2):
        clock.day_index = step
        newborn = h.step(current_step=step, clock=clock, savings_bank=sb, retailers=[])

    assert newborn is not None
    assert isinstance(newborn, Household)
    assert newborn.generation == h.generation + 1
    assert newborn.sight_balance > 0.0
