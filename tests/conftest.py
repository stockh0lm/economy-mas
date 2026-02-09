"""conftest.py - Pytest configuration and fixtures.

Resets class-level mutable state between test runs to ensure test isolation.
"""

import sys
from pathlib import Path
import tempfile
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = PROJECT_ROOT / "agents"

for path in (PROJECT_ROOT, AGENTS_DIR):
    if path.exists():
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def pytest_runtest_setup(item):
    """Reset class-level mutable state before each test.

    Ensures test isolation by clearing any class-level mutable dictionaries
    that might have been modified by previous tests.
    """
    # Reset Company._lineage_counters to prevent pollution from test_m5
    # which forces company splits and modifies this global counter.
    import importlib

    company_module = sys.modules.get("agents.company_agent")
    if company_module is not None:
        company_module.Company._lineage_counters.clear()
    # Also initialize Houseoloading counters if they exist
    from agents.company_agent import Company

    # Force reset even if empty
    Company._lineage_counters = {}

    # Reset household agent's numpy RNG which is a cached global
    household_module = sys.modules.get("agents.household_agent")
    if household_module is not None:
        household_module._DEFAULT_NP_RNG = None

    # Reset consumption module's independent numpy RNG
    consumption_module = sys.modules.get("agents.household.consumption")
    if consumption_module is not None:
        consumption_module._DEFAULT_NP_RNG = None

    # Reset GlobalConfigCache singleton to prevent stale config across tests
    config_cache_module = sys.modules.get("agents.config_cache")
    if config_cache_module is not None:
        config_cache_module.GlobalConfigCache._instance = None
    config_cache_root = sys.modules.get("config_cache")
    if config_cache_root is not None:
        config_cache_root.GlobalConfigCache._instance = None


@pytest.fixture(scope="session")
def runner_metrics_dir():
    """Generate a minimal simulation run for integration tests.
    This fixture runs once per test session to avoid regenerating metrics on every test.
    """
    from main import run_simulation
    from config import SimulationConfig
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir) / "metrics"
        tmppath.mkdir(parents=True)
        cfg = SimulationConfig(simulation_steps=30)
        cfg.log_file = str(tmppath / "simulation.log")
        cfg.metrics_export_path = str(tmppath)
        agents = run_simulation(cfg)

        # Verify metrics were generated
        assert (tmppath / "global_metrics").exists() or (
            tmppath / "global_metrics_" in [f.name for f in tmppath.iterdir() if f.suffix == ".csv"]
        ), "Global metrics not generated"
        yield tmppath
