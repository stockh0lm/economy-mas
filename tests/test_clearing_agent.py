import math

from agents.clearing_agent import ClearingAgent
from config import CONFIG


class DummyAgent:
    def __init__(self, uid: str, balance: float) -> None:
        self.unique_id = uid
        self.balance = balance


def test_report_hyperwealth_collects_excess_and_caps_balance() -> None:
    original_threshold = CONFIG.get("hyperwealth_threshold", 1_000_000)
    CONFIG["hyperwealth_threshold"] = 100.0
    try:
        clearing = ClearingAgent("clear_1")

        rich = DummyAgent("rich", 150.0)
        borderline = DummyAgent("border", 100.0)
        poor = DummyAgent("poor", 50.0)

        collected = clearing.report_hyperwealth([rich, borderline, poor])

        assert math.isclose(collected, 50.0)
        assert math.isclose(rich.balance, 100.0)
        assert math.isclose(borderline.balance, 100.0)
        assert math.isclose(poor.balance, 50.0)
        assert math.isclose(clearing.excess_wealth_collected, 50.0)
    finally:
        CONFIG["hyperwealth_threshold"] = original_threshold
