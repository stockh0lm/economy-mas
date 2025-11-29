import copy

import pytest
from pydantic import ValidationError

import config


@pytest.fixture(name="config_payload")
def config_payload_fixture() -> dict:
    return copy.deepcopy(config.CONFIG)


def test_load_simulation_config_casts_and_keeps_nested_lists(config_payload: dict) -> None:
    config_payload["simulation_steps"] = "250"
    config_payload["tax_rates"]["bodensteuer"] = "0.07"
    config_payload["INITIAL_HOUSEHOLDS"][0]["income"] = "180"

    cfg = config.load_simulation_config(config_payload)

    assert cfg.simulation_steps == 250
    assert cfg.tax_rates.bodensteuer == pytest.approx(0.07)
    assert cfg.initial_households[0].income == pytest.approx(180.0)
    assert cfg.model_dump()["tax_rates"]["umweltsteuer"] == config_payload["tax_rates"]["umweltsteuer"]


def test_simulation_config_enforces_reasonable_bounds(config_payload: dict) -> None:
    config_payload["simulation_steps"] = -10

    with pytest.raises(ValidationError):
        config.load_simulation_config(config_payload)


def test_config_model_exposed_via_module_singleton() -> None:
    cfg = config.CONFIG_MODEL

    assert cfg.simulation_steps == config.CONFIG["simulation_steps"]
    assert cfg.tax_rates.bodensteuer == config.CONFIG["tax_rates"]["bodensteuer"]
    assert len(cfg.initial_households) == len(config.CONFIG["INITIAL_HOUSEHOLDS"])

