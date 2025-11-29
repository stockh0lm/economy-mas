import math

from agents.clearing_agent import ClearingAgent
import config


class DummyAgent:
    def __init__(self, uid: str, balance: float) -> None:
        self.unique_id = uid
        self.balance = balance


def test_report_hyperwealth_collects_excess_and_caps_balance() -> None:
    cfg = config.load_simulation_config({**config.CONFIG, "hyperwealth_threshold": 100.0})
    clearing = ClearingAgent("clear_1", cfg)

    rich = DummyAgent("rich", 150.0)
    borderline = DummyAgent("border", 100.0)
    poor = DummyAgent("poor", 50.0)

    collected = clearing.report_hyperwealth([rich, borderline, poor])

    assert math.isclose(collected, 50.0)
    assert math.isclose(rich.balance, 100.0)
    assert math.isclose(borderline.balance, 100.0)
    assert math.isclose(poor.balance, 50.0)
    assert math.isclose(clearing.excess_wealth_collected, 50.0)
