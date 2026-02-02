from __future__ import annotations

from pathlib import Path

from main import initialize_agents, load_config, run_simulation
from config import SimulationConfig


def test_financial_market_abgeschaltet(tmp_path: Path) -> None:
    """Referenz: doc/issues.md Abschnitt 4 → „FinancialMarket abschalten“

    Erwartung: Simulation läuft ohne FinancialMarket und initialisiert diesen Agenten nicht.
    """

    cfg = SimulationConfig()
    agents = initialize_agents(cfg)
    assert "financial_market" not in agents

    # Smoke-test: kurzer Run ohne FinancialMarket.
    cfg_path = Path("configs/small_performance_test.yaml")
    cfg_from_file = load_config(cfg_path)
    cfg_from_file.simulation_steps = 5
    agents_out = run_simulation(cfg_from_file)
    collector = agents_out["metrics_collector"]
    assert len(collector.global_metrics) > 0


def test_no_financial_market_influence() -> None:
    """Referenz: doc/issues.md Abschnitt 4 → „FinancialMarket abschalten"""

    repo_root = Path(__file__).resolve().parents[1]
    main_text = (repo_root / "main.py").read_text(encoding="utf-8")

    # Kein Import / keine Initialisierung mehr in main.py.
    assert "FinancialMarket" not in main_text
    assert "financial_market" not in main_text

    # Agent-Code ist entfernt.
    assert not (repo_root / "agents" / "financial_market.py").exists()