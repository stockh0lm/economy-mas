from config import SimulationConfig
from main import _m1_proxy, run_simulation


def test_golden_run_snapshot(monkeypatch, tmp_path):
    """Referenz: doc/issues.md Abschnitt 3 → Golden-run Snapshot"""

    monkeypatch.setenv("SIM_SEED", "12345")

    cfg = SimulationConfig(simulation_steps=30)
    cfg.log_file = str(tmp_path / "sim.log")
    cfg.metrics_export_path = str(tmp_path / "metrics.json")

    agents = run_simulation(cfg)

    households = agents["households"]
    companies = agents["companies"]
    retailers = agents["retailers"]
    state = agents["state"]
    warengeld_banks = agents["warengeld_banks"]

    m1 = _m1_proxy(households=households, companies=companies, retailers=retailers, state=state)
    total_inventory_value = sum(float(r.inventory_value) for r in retailers)
    total_cc_exposure = sum(float(b.total_cc_exposure) for b in warengeld_banks)

    employed = sum(1 for h in households if getattr(h, "employer_id", None) is not None)
    employment_rate = employed / max(1, len(households))

    # --- Expected macro bands (seeded 30-day run) ---
    # Bands are intentionally not razor-thin; they should catch
    # regressions while remaining robust to minor refactors.
    # Updated after introducing demand-responsive production (P1),
    # inventory depreciation/holding costs (P2), price responsiveness (P3),
    # insolvency mechanisms (P4), retailer-as-mediator (P5: demand-driven
    # ordering + price-aware supplier selection), and profit distribution /
    # money-sink fixes (D/E/F).  Profit distribution drains company balances
    # faster → lower M1; CC throttle + faster household spending → lower CC
    # exposure at the 30-step snapshot.
    assert len(households) == 4
    assert len(retailers) == 2

    assert 120.0 <= m1 <= 350.0
    assert 150.0 <= total_inventory_value <= 350.0
    assert 50.0 <= total_cc_exposure <= 280.0
    assert 0.75 <= employment_rate <= 1.0
