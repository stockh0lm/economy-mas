import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = PROJECT_ROOT / "agents"

for path in (PROJECT_ROOT, AGENTS_DIR):
    if path.exists():
        path_str = str(path)
        if path_str in sys.path:
            sys.path.remove(path_str)
        sys.path.insert(0, path_str)


@pytest.fixture(scope="session")
def runner_metrics_dir():
    """Generate a minimal simulation run for integration tests.

    This fixture runs once per test session to avoid regenerating
    metrics on every test.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("main", str(PROJECT_ROOT / "main.py"))
    main = importlib.util.module_from_spec(spec)
    sys.modules["main"] = main
    spec.loader.exec_module(main)
    run_simulation = main.run_simulation
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
        assert (tmppath / "global_metrics").exists() or any(
            f.name.startswith("global_metrics_") and f.suffix == ".csv" for f in tmppath.iterdir()
        ), "Global metrics not generated"

        yield tmppath
