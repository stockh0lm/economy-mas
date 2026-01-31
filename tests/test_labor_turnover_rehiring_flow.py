import csv
from pathlib import Path

from config import SimulationConfig
from logger import setup_logger
from main import run_simulation


def _latest_csv_from(dir_path: Path, pattern: str) -> Path:
    files = sorted(dir_path.glob(pattern), key=lambda p: p.stat().st_mtime)
    assert files, f"no files matching {pattern} in {dir_path}"
    return files[-1]


def test_newborn_and_replacement_households_are_registered_on_labor_market(tmp_path):
    """Integration-ish test: newborns and turnover replacements must be eligible workers.

    We run long enough to trigger turnover with an artificially short year, and
    verify that after the turnover the labor market still matches workers.

    This guards against the historical bug where new households were created but
    never registered in the labor market, causing employment to collapse permanently.
    """

    cfg = SimulationConfig(simulation_steps=40)
    cfg.metrics_export_path = str(tmp_path / "metrics")
    cfg.log_file = str(tmp_path / "simulation.log")

    cfg.population.num_households = 10
    cfg.population.num_companies = 2
    cfg.population.num_retailers = 1
    cfg.population.seed = 42

    # Make "1 year" = 10 steps so max_age=2 triggers turnover within 40 steps.
    cfg.time.days_per_year = 10
    cfg.household.max_age = 2

    # Make sure lending/saving isn't the bottleneck.
    cfg.household.savings_rate = 0.0
    cfg.household.transaction_buffer = 0.0

    # Ensure firms want to hire enough workers.
    cfg.company.employee_capacity_ratio = 10.0

    setup_logger(level=cfg.logging_level, log_file=cfg.log_file, log_format=cfg.log_format, file_mode="w")
    run_simulation(cfg)

    metrics_dir = Path(cfg.metrics_export_path)

    gpath = _latest_csv_from(metrics_dir, "global_metrics_*.csv")
    grows = list(csv.DictReader(gpath.open(encoding="utf-8")))

    hpath = _latest_csv_from(metrics_dir, "household_metrics_*.csv")
    hrows = list(csv.DictReader(hpath.open(encoding="utf-8")))

    # Assert turnover actually happened: new household ids beyond initial cohort exist.
    ids = {r["agent_id"] for r in hrows}
    assert any(i.startswith("household_") and int(i.split("_")[1]) >= 10 for i in ids)

    # Employment should remain positive after turnover.
    emp = [float(r.get("employment_rate") or 0.0) for r in grows]
    assert min(emp) > 0.0


def test_firms_rehire_after_mass_turnover(tmp_path):
    """Regression for the year-70 cliff.

    The economy used to collapse when the initial household cohort died, because
    the replacements weren't re-hired (or weren't hireable). We reproduce the
    situation on a compressed timescale and demand that employment doesn't stick
    at 0 after the turnover.

    This test deliberately doesn't assert consumption/sales, only rehiring.
    """

    cfg = SimulationConfig(simulation_steps=60)
    cfg.metrics_export_path = str(tmp_path / "metrics")
    cfg.log_file = str(tmp_path / "simulation.log")

    cfg.population.num_households = 10
    cfg.population.num_companies = 2
    cfg.population.num_retailers = 1
    cfg.population.seed = 7

    # Compress time: 1 year = 10 steps, max age 3 years -> mass turnover at step 30.
    cfg.time.days_per_year = 10
    cfg.household.max_age = 3

    cfg.household.savings_rate = 0.0
    cfg.household.transaction_buffer = 0.0

    cfg.company.employee_capacity_ratio = 10.0

    setup_logger(level=cfg.logging_level, log_file=cfg.log_file, log_format=cfg.log_format, file_mode="w")
    run_simulation(cfg)

    metrics_dir = Path(cfg.metrics_export_path)
    gpath = _latest_csv_from(metrics_dir, "global_metrics_*.csv")
    rows = list(csv.DictReader(gpath.open(encoding="utf-8")))

    hpath = _latest_csv_from(metrics_dir, "household_metrics_*.csv")
    hrows = list(csv.DictReader(hpath.open(encoding="utf-8")))
    ids = {r["agent_id"] for r in hrows}
    assert any(i.startswith("household_") and int(i.split("_")[1]) >= 10 for i in ids)

    # Employment should stay >0 throughout; in particular it must not stick at 0 after turnover.
    emp = [float(r.get("employment_rate") or 0.0) for r in rows]
    assert min(emp) > 0.0
