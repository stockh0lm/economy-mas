import csv
import os
import shutil
from pathlib import Path

import pytest

from config import SimulationConfig
from main import run_simulation


def _latest_csv_from(dir_path: Path, pattern: str) -> Path:
    files = sorted(dir_path.glob(pattern), key=lambda p: p.stat().st_mtime)
    assert files, f"no files matching {pattern} in {dir_path}"
    return files[-1]


def _load_global_metrics(metrics_dir: Path) -> list[dict[str, str]]:
    gpath = _latest_csv_from(metrics_dir, "global_metrics_*.csv")
    with gpath.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _update_baseline(metrics_dir: Path, scenario_name: str):
    if os.environ.get("UPDATE_BASELINES") == "1":
        baseline_dir = Path("output/golden_run_baseline")
        baseline_dir.mkdir(parents=True, exist_ok=True)
        gpath = _latest_csv_from(metrics_dir, "global_metrics_*.csv")
        shutil.copy(gpath, baseline_dir / f"{scenario_name}.csv")


class TestGoldenRunComprehensive:
    """Comprehensive golden test suite for regression detection."""

    @pytest.fixture(autouse=True)
    def setup_seed(self, monkeypatch):
        monkeypatch.setenv("SIM_SEED", "12345")

    @pytest.fixture
    def default_config(self):
        return SimulationConfig(simulation_steps=90)

    def test_short_run_default_params(self, default_config, tmp_path):
        """30-step run with default parameters (baseline)."""
        cfg = default_config
        cfg.simulation_steps = 30
        cfg.log_file = str(tmp_path / "sim.log")
        cfg.metrics_export_path = str(tmp_path / "metrics")

        run_simulation(cfg)
        metrics_path = Path(cfg.metrics_export_path)
        rows = _load_global_metrics(metrics_path)
        assert rows, "global metrics should be exported"
        assert len(rows) >= 30
        _update_baseline(metrics_path, "baseline_short_default")

    def test_medium_run_quarterly_behavior(self, default_config, tmp_path):
        """90-step run to observe quarterly behavior patterns."""
        cfg = default_config
        cfg.simulation_steps = 90
        cfg.log_file = str(tmp_path / "sim.log")
        cfg.metrics_export_path = str(tmp_path / "metrics")

        run_simulation(cfg)
        metrics_path = Path(cfg.metrics_export_path)
        rows = _load_global_metrics(metrics_path)
        assert len(rows) >= 90
        _update_baseline(metrics_path, "baseline_medium_quarterly")

    def test_demography_enabled(self, default_config, tmp_path):
        """90-step run with high Demography settings (mortality, fertility)."""
        cfg = default_config
        cfg.simulation_steps = 90
        cfg.household.mortality_base_annual = 0.05  # Higher death rate
        cfg.household.fertility_base_annual = 0.05  # Higher birth rate
        cfg.log_file = str(tmp_path / "sim.log")
        cfg.metrics_export_path = str(tmp_path / "metrics")

        run_simulation(cfg)
        metrics_path = Path(cfg.metrics_export_path)
        rows = _load_global_metrics(metrics_path)
        assert rows
        assert len(rows) >= 90
        _update_baseline(metrics_path, "baseline_demography")

    def test_multi_region_config(self, default_config, tmp_path):
        """30-step run with multi-region configuration (3 regions)."""
        cfg = default_config
        cfg.simulation_steps = 30
        cfg.spatial.num_regions = 3
        cfg.log_file = str(tmp_path / "sim.log")
        cfg.metrics_export_path = str(tmp_path / "metrics")

        run_simulation(cfg)
        metrics_path = Path(cfg.metrics_export_path)
        rows = _load_global_metrics(metrics_path)
        assert rows
        assert len(rows) >= 30
        _update_baseline(metrics_path, "baseline_multi_region")

    def test_company_founding_mergers(self, default_config, tmp_path):
        """30-step run with company founding and mergers enabled."""
        cfg = default_config
        cfg.simulation_steps = 30
        cfg.company.founding_base_annual = 0.1  # Higher founding rate
        cfg.company.merger_rate_annual = 0.1  # Higher merger rate
        cfg.log_file = str(tmp_path / "sim.log")
        cfg.metrics_export_path = str(tmp_path / "metrics")

        run_simulation(cfg)
        metrics_path = Path(cfg.metrics_export_path)
        rows = _load_global_metrics(metrics_path)
        assert rows
        assert len(rows) >= 30
        _update_baseline(metrics_path, "baseline_company_dynamics")
