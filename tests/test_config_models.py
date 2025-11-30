
import pytest
from pydantic import ValidationError

import config


def test_simulation_config_structure_defaults() -> None:
    """Test that SimulationConfig initializes with expected default values and structure."""
    cfg = config.SimulationConfig()
    
    assert cfg.simulation_steps == 100
    assert cfg.household.max_age == 80
    assert cfg.company.base_wage == 5.0
    assert cfg.labor_market.starting_wage == 10.0
    assert cfg.bank.fee_rate == 0.01
    assert cfg.tax_rates.bodensteuer == 0.05


def test_simulation_config_enforces_reasonable_bounds() -> None:
    """Test that Pydantic validation enforces bounds on configuration values."""
    
    # Test negative simulation steps
    with pytest.raises(ValidationError):
        config.SimulationConfig(simulation_steps=-10)
        
    # Test invalid tax rate
    with pytest.raises(ValidationError):
        config.SimulationConfig(tax_rates={"bodensteuer": 1.5})


def test_load_simulation_config_casts_types() -> None:
    """Test that loading config performs type casting where appropriate."""
    # load_simulation_config now expects a mapping compatible with SimulationConfig model
    payload = {
        "simulation_steps": "250",
        "tax_rates": {"bodensteuer": "0.07"},
        "INITIAL_HOUSEHOLDS": [{"income": "180", "land_area": 50, "environmental_impact": 1}]
    }
    
    cfg = config.load_simulation_config(payload)
    
    assert cfg.simulation_steps == 250
    assert cfg.tax_rates.bodensteuer == pytest.approx(0.07)
    assert cfg.initial_households[0].income == pytest.approx(180.0)


def test_asset_price_map_behaves_like_mapping() -> None:
    """Test AssetPriceMap wrapper functionality."""
    price_map = config.AssetPriceMap.from_dict({"foo": 1.5, "bar": 2.5})

    assert price_map.get("foo") == pytest.approx(1.5)
    assert price_map.get("missing", 3.3) == pytest.approx(3.3)
    assert dict(price_map.as_dict()) == {"foo": 1.5, "bar": 2.5}
    assert list(iter(price_map)) == ["foo", "bar"]
