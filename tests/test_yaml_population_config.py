import textwrap

import pytest
from pydantic import ValidationError

from config import load_simulation_config, load_simulation_config_from_yaml
from main import initialize_agents


def test_load_simulation_config_from_yaml_loads_and_validates(tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        textwrap.dedent(
            """
            simulation_steps: 3
            population:
              num_households: 5
              num_companies: 2
              household_template:
                income: 123
                land_area: 10
                environmental_impact: 0
              company_template:
                production_capacity: 77
                land_area: 33
                environmental_impact: 2
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = load_simulation_config_from_yaml(str(cfg_path))

    assert cfg.simulation_steps == 3
    assert cfg.population.num_households == 5
    assert cfg.population.num_companies == 2
    assert cfg.population.household_template.income == pytest.approx(123.0)
    assert cfg.population.company_template.production_capacity == pytest.approx(77.0)


def test_load_simulation_config_from_yaml_rejects_invalid_values(tmp_path) -> None:
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text(
        textwrap.dedent(
            """
            population:
              num_households: -1
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_simulation_config_from_yaml(str(cfg_path))


def test_initialize_agents_generates_population_when_initial_lists_empty() -> None:
    """If INITIAL_* lists are empty, initialize_agents should use population.num_* + templates."""

    payload = {
        # Important: override INITIAL lists to empty to activate generation
        "INITIAL_HOUSEHOLDS": [],
        "INITIAL_COMPANIES": [],
        "population": {
            "num_households": 12,
            "num_companies": 4,
            "household_template": {"income": 50, "land_area": 1, "environmental_impact": 0},
            "company_template": {
                "production_capacity": 10,
                "land_area": 2,
                "environmental_impact": 0,
            },
        },
    }

    sim_cfg = load_simulation_config(payload)
    agents = initialize_agents(sim_cfg)

    assert len(agents["households"]) == 12
    assert len(agents["companies"]) == 4

    # Spot-check template was applied
    assert agents["households"][0].income == pytest.approx(50.0)
    assert agents["companies"][0].production_capacity == pytest.approx(10.0)
