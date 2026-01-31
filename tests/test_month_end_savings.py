import csv
from pathlib import Path

from config import SimulationConfig
from logger import setup_logger
from main import run_simulation


def test_households_only_save_at_month_end(tmp_path):
    """Households should save leftover balances at month-end, not every day.

    This keeps day-to-day consumption/velocity, while still building SavingsBank
    deposits to fund credit.
    """

    cfg = SimulationConfig(simulation_steps=35)
    cfg.metrics_export_path = str(tmp_path / "metrics")
    cfg.log_file = str(tmp_path / "simulation.log")

    cfg.population.num_households = 5
    cfg.population.num_companies = 1
    cfg.population.num_retailers = 1

    cfg.time.days_per_month = 30
    cfg.time.days_per_year = 360

    # Ensure they would save if allowed.
    cfg.household.savings_rate = 0.5
    cfg.household.transaction_buffer = 0.0

    setup_logger(level=cfg.logging_level, log_file=cfg.log_file, log_format=cfg.log_format, file_mode="w")
    run_simulation(cfg)

    metrics_dir = Path(cfg.metrics_export_path)
    hpath = sorted(metrics_dir.glob("household_metrics_*.csv"), key=lambda p: p.stat().st_mtime)[-1]
    rows = list(csv.DictReader(hpath.open(encoding="utf-8")))

    # Look at savings per step (mean savings across households on that step).
    by_step = {}
    for r in rows:
        step = int(r["time_step"])
        by_step.setdefault(step, []).append(float(r.get("savings") or 0.0))

    avg_savings = {s: sum(vals) / len(vals) for s, vals in by_step.items()}

    # Before month end (steps 0..28), savings should stay ~0
    assert max(avg_savings[s] for s in range(0, 29)) == 0.0

    # At month end (step 29), savings should increase
    assert avg_savings[29] > 0.0
