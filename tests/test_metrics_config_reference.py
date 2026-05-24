import pytest
from config import SimulationConfig
from metrics import MetricsCollector


def test_price_dynamics_uses_collector_config_not_global_config() -> None:
    config = SimulationConfig()
    config.market.price_index_base = 100.0
    config.market.price_index_pressure_ratio = "consumption_to_production"
    config.market.price_index_pressure_target = 1.0
    config.market.price_index_sensitivity = 1.0
    config.market.price_index_max = 10_000.0

    collector = MetricsCollector(config=config)
    collector.registered_companies = {"c1"}
    collector.company_metrics = {"c1": {1: {"production_capacity": 100.0}}}
    collector.household_metrics = {
        "h1": {
            1: {
                "checking_account": 0.0,
                "savings": 0.0,
                "consumption": 25.0,
                "employed": True,
            }
        }
    }

    collector.calculate_global_metrics(step=1)

    assert collector.global_metrics[1]["price_index"] == pytest.approx(25.0)
    assert collector.global_metrics[1]["price_pressure"] == pytest.approx(0.25)
