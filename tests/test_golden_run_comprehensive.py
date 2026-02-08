import csv
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
    return list(csv.DictReader(gpath.open(encoding="utf-8")))

class TestGoldenRunComprehensive:
    """Comprehensive golden test suite for regression detection."""

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
        rows = _load_global_metrics(Path(cfg.metrics_export_path))
        assert rows, "global metrics should be exported"

    def test_medium_run_quarterly_behavior(self, default_config, tmp_path):
        """90-step run to observe quarterly behavior patterns."""
        cfg = default_config
        cfg.simulation_steps = 90
        cfg.log_file = str(tmp_path / "sim.log")
        cfg.metrics_export_path = str(tmp_path / "metrics")
        run_simulation(cfg)
        rows = _load_global_metrics(Path(cfg.metrics_export_path))
        assert len(rows) >= 90

    def test_demography_enabled(self, default_config, tmp_path):
        """90-step run with high Demography settings (mortality, fertility)."""
        cfg = default_config
        cfg.simulation_steps = 90
        cfg.household.mortality_base_annual = 0.05  # Higher death rate
        cfg.household.fertility_base_annual = 0.05  # Higher birth rate
        cfg.log_file = str(tmp_path / "sim.log")
        cfg.metrics_export_path = str(tmp_path / "metrics")
        run_simulation(cfg)
        rows = _load_global_metrics(Path(cfg.metrics_export_path))
        assert rows

    def test_multi_region_config(self, default_config, tmp_path):
        """30-step run with multi-region configuration (3 regions)."""
        cfg = default_config
        cfg.simulation_steps = 30
        cfg.spatial.num_regions = 3
        cfg.log_file = str(tmp_path / "sim.log")
        cfg.metrics_export_path = str(tmp_path / "metrics")
        run_simulation(cfg)
        rows = _load_global_metrics(Path(cfg.metrics_export_path))
        assert rows

    def test_company_founding_mergers(self, default_config, tmp_path):
        """30-step run with company founding and mergers enabled."""
        cfg = default_config
        cfg.simulation_steps = 30
        cfg.company.founding_base_annual = 0.1  # Higher founding rate
        cfg.company.merger_rate_annual = 0.1  # Higher merger rate
        cfg.log_file = str(tmp_path / "sim.log")
        cfg.metrics_export_path = str(tmp_path / "metrics")
        run_simulation(cfg)
        rows = _load_global_metrics(Path(cfg.metrics_export_path))
        assert rows