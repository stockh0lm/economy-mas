import os
import pytest
from config import SimulationConfig
from simulation.engine import SimulationEngine
from main import run_simulation, _m1_proxy


def test_simulation_engine_step_advances_clock():
    """Verify that step() correctly advances clock.day_index."""
    cfg = SimulationConfig(simulation_steps=5)
    engine = SimulationEngine(cfg)

    assert engine.current_step == 0
    assert engine.clock.day_index == 0

    engine.step()
    assert engine.current_step == 1
    assert engine.clock.day_index == 0  # Current step is 0 when step starts, then it increments
    # Wait, looking at engine.py:
    # def step(self) -> None:
    #     step = self.current_step
    #     self.clock.day_index = step
    #     ...
    #     self.current_step += 1

    engine.step()
    assert engine.current_step == 2
    assert engine.clock.day_index == 1


def test_simulation_engine_reset():
    """Verify that reset() re-initializes agents and clock."""
    cfg = SimulationConfig(simulation_steps=10)
    engine = SimulationEngine(cfg)

    # Run some steps
    engine.step()
    engine.step()
    assert engine.current_step == 2
    initial_households_count = len(engine.households)

    engine.reset()
    assert engine.current_step == 0
    assert engine.clock.day_index == 0
    assert len(engine.households) == initial_households_count


def test_simulation_engine_deterministic(monkeypatch):
    """Verify that SimulationEngine produces identical results with fixed seed."""
    monkeypatch.setenv("SIM_SEED", "42")
    cfg = SimulationConfig(simulation_steps=20)

    engine1 = SimulationEngine(cfg)
    results1 = engine1.run()
    m1_1 = _m1_proxy(
        results1["households"], results1["companies"], results1["retailers"], results1["state"]
    )

    # Resetting global seed is important if engine doesn't do it perfectly or if there's global state
    # But SimulationEngine.reset() or __init__ should handle it via monkeypatch env var
    engine2 = SimulationEngine(cfg)
    results2 = engine2.run()
    m1_2 = _m1_proxy(
        results2["households"], results2["companies"], results2["retailers"], results2["state"]
    )

    assert m1_1 == m1_2
    assert len(results1["households"]) == len(results2["households"])


def test_simulation_engine_parity_with_main(monkeypatch):
    """Verify that SimulationEngine.run() matches main.run_simulation()."""
    monkeypatch.setenv("SIM_SEED", "999")
    cfg = SimulationConfig(simulation_steps=15)

    # Run via main.run_simulation
    results_main = run_simulation(cfg)
    m1_main = _m1_proxy(
        results_main["households"],
        results_main["companies"],
        results_main["retailers"],
        results_main["state"],
    )

    # Run via Engine directly
    engine = SimulationEngine(cfg)
    results_engine = engine.run()
    m1_engine = _m1_proxy(
        results_engine["households"],
        results_engine["companies"],
        results_engine["retailers"],
        results_engine["state"],
    )

    assert m1_main == m1_engine
