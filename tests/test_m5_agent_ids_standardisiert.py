import os
import re

from config import SimulationConfig
from main import run_simulation


def test_agent_ids_standardisiert(monkeypatch, tmp_path):
    """Referenz: doc/issues.md Abschnitt 5 → Agent-IDs standardisieren"""

    cfg = SimulationConfig()
    cfg.simulation_steps = 2
    cfg.log_file = str(tmp_path / "sim.log")
    cfg.metrics_export_path = str(tmp_path / "metrics.json")

    # Force a company birth via split to validate newly generated IDs.
    cfg.company.investment_threshold = 0.0
    cfg.company.growth_threshold = 1

    monkeypatch.setenv("SIM_SEED", "123")

    agents = run_simulation(cfg)

    assert agents["state"].unique_id == "state_0"
    assert agents["clearing_agent"].unique_id == "clearing_0"
    assert agents["labor_market"].unique_id == "labor_market_0"

    hh_re = re.compile(r"^household_\d+$")
    co_re = re.compile(r"^company_\d+$")
    rt_re = re.compile(r"^retailer_\d+$")

    hh_ids = [h.unique_id for h in agents["households"]]
    co_ids = [c.unique_id for c in agents["companies"]]
    rt_ids = [r.unique_id for r in agents["retailers"]]

    assert all(hh_re.match(i) for i in hh_ids)
    assert all(co_re.match(i) for i in co_ids)
    assert all(rt_re.match(i) for i in rt_ids)

    assert len(set(hh_ids)) == len(hh_ids)
    assert len(set(co_ids)) == len(co_ids)
    assert len(set(rt_ids)) == len(rt_ids)
