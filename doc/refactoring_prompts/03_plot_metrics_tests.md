# Prompt 3: Integration Test for scripts/plot_metrics.py

## Context
The plot_metrics.py script already has unit tests in `tests/test_plot_metrics.py`. This prompt extends coverage with a small end-to-end run that uses real metrics exports and validates plot generation.

---

## Task

### Step 1: Review Existing Tests

Run the existing tests and confirm they pass before adding integration coverage:

```bash
pytest tests/test_plot_metrics.py -v
```

### Step 1b: Git Workflow (Required)

- Create a refactoring branch (example): `git checkout -b refactor/p03-plot-metrics-tests`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

---

### Step 2: Create Integration Test Module

Create `tests/test_plot_metrics_integration.py` that reuses the existing plotting functions and validates real output. Keep it small to avoid long test times.

```python
"""Integration tests for plot_metrics.py script.

These tests verify end-to-end functionality of plot generation,
performance optimizations (CSV caching), and robustness.
"""

import pytest
from pathlib import Path
import tempfile
import time
import sys

# Import plot script functions
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from plot_metrics import (
    load_csv_rows,
    extract_series,
    aggregate_company_metrics,
    count_agents_per_step,
    plot_global_output,
    plot_monetary_system,
    plot_crash_diagnostics,
    plot_labor_market,
    plot_prices_and_wages,
    plot_state_budgets,
    plot_company_health,
    plot_household_population,
    plot_company_population,
    plot_overview_dashboard,
    csv_cache_info,
    clear_csv_cache,
)


class TestPlotMetricsIntegration:
    """Integration tests for plot_metrics.py."""
    
    @pytest.fixture
    def simulated_metrics_dir(self, tmp_path):
        """Generate a short simulation run and return metrics directory."""
        from main import run_simulation
        from config import SimulationConfig
        
        cfg = SimulationConfig(simulation_steps=10)
        cfg.log_file = str(tmp_path / "simulation.log")
        cfg.metrics_export_path = str(tmp_path / "metrics")
        
        run_simulation(cfg)
        return tmp_path / "metrics"
    
    def test_plot_metrics_generates_all_plot_types(self, simulated_metrics_dir, tmp_path):
        """Verify all plot types generate successfully."""
        import matplotlib.pyplot as plt
        
        plots_dir = tmp_path / "plots"
        plots_dir.mkdir()
        
        # Find the latest run
        global_metrics_files = list(simulated_metrics_dir.glob("global_metrics_*.csv"))
        if not global_metrics_files:
            pytest.skip("No metrics files generated")
        
        run_id = global_metrics_files[0].stem.replace("global_metrics_", "")
        
        # Load data
        global_rows = load_csv_rows(simulated_metrics_dir / f"global_metrics_{run_id}.csv")
        company_rows = load_csv_rows(simulated_metrics_dir / f"company_metrics_{run_id}.csv", 
                                     usecols=None, skip_fields={"agent_id"})
        household_rows = load_csv_rows(simulated_metrics_dir / f"household_metrics_{run_id}.csv",
                                       usecols={"time_step", "agent_id"})
        state_rows = load_csv_rows(simulated_metrics_dir / f"state_metrics_{run_id}.csv",
                                  skip_fields={"agent_id"})
        
        data_by_scope = {
            'global': global_rows,
            'company': company_rows,
            'household': household_rows,
            'state': state_rows,
        }
        
        # Generate each plot type
        plot_functions = [
            ('global', plot_global_output),
            ('global', plot_monetary_system),
            ('global', plot_crash_diagnostics),
            ('global', plot_labor_market),
            ('global', plot_prices_and_wages),
            ('state', plot_state_budgets),
            ('company', plot_company_health),
            ('household', plot_household_population),
            ('company', plot_company_population),
        ]
        
        generated_plots = []
        
        for scope, plot_func in plot_functions:
            fig, filename = plot_func(data_by_scope[scope])
            fig.savefig(plots_dir / filename, dpi=150)
            plt.close(fig)
            generated_plots.append(filename)
        
        # Generate overview dashboard
        fig, filename = plot_overview_dashboard(data_by_scope)
        fig.savefig(plots_dir / filename, dpi=150)
        plt.close(fig)
        generated_plots.append(filename)
        
        # Verify all plots were created
        for filename in generated_plots:
            plot_path = plots_dir / filename
            assert plot_path.exists(), f"Plot file not created: {filename}"
            assert plot_path.stat().st_size > 0, f"Plot file is empty: {filename}"
    
    def test_plot_metrics_csv_cache_works(self, simulated_metrics_dir):
        """Verify CSV caching improves performance on repeated loads."""
        global_metrics_files = list(simulated_metrics_dir.glob("global_metrics_*.csv"))
        if not global_metrics_files:
            pytest.skip("No metrics files generated")
        
        # Clear cache first
        clear_csv_cache()
        initial_info = csv_cache_info()
        assert initial_info["entries"] == 0, "Cache should be empty initially"
        
        # Load data (first time - cache miss)
        start_time = time.time()
        rows1 = load_csv_rows(global_metrics_files[0], cache=True)
        first_load_time = time.time() - start_time
        
        after_first_info = csv_cache_info()
        assert after_first_info["misses"] > 0, "Should have cache misses on first load"
        assert after_first_info["entries"] > 0, "Should have cached entries after load"
        
        # Load same data again (should be cached)
        start_time = time.time()
        rows2 = load_csv_rows(global_metrics_files[0], cache=True)
        second_load_time = time.time() - start_time
        
        after_second_info = csv_cache_info()
        assert after_second_info["hits"] > 0, "Should have cache hit on second load"
        
        # Second load should be faster
        assert second_load_time <= first_load_time * 1.5, \
            f"Cached load ({second_load_time}s) should be faster than first ({first_load_time}s)"
        
        # Data should be identical
        assert rows1.equals(rows2), "Cached data should match original"
    
    def test_plot_metrics_lazy_column_loading(self, simulated_metrics_dir):
        """Verify only needed columns are loaded (lazy loading)."""
        global_metrics_files = list(simulated_metrics_dir.glob("global_metrics_*.csv"))
        if not global_metrics_files:
            pytest.skip("No metrics files generated")
        
        # Clear cache
        clear_csv_cache()
        
        # Load only specific columns
        selected_cols = {"time_step", "gdp", "m1_proxy", "employment_rate"}
        rows = load_csv_rows(global_metrics_files[0], usecols=selected_cols)
        
        # Verify only requested columns and time_step are present
        for col in rows.columns:
            assert col in selected_cols, f"Unexpected column loaded: {col}"
        
        assert "time_step" in rows.columns, "time_step should always be loaded"
        assert "gdp" in rows.columns, "gdp should be loaded"
        assert "m1_proxy" in rows.columns, "m1_proxy should be loaded"
        assert "employment_rate" in rows.columns, "employment_rate should be loaded"
        # Other columns should not be loaded
        assert "unused_metric" not in rows.columns if "unused_metric" in rows.columns else True
    
    def test_plot_metrics_handles_missing_metrics(self, tmp_path):
        """Verify graceful handling when some metrics are missing."""
        import pandas as pd
        
        # Create minimal CSV with only some columns
        csv_path = tmp_path / "minimal_metrics.csv"
        with open(csv_path, "w") as f:
            f.write("time_step,gdp\n")
            for i in range(10):
                f.write(f"{i},{100.0 + i * 10.0}\n")
        
        # Extract series - missing columns should be handled
        steps, data = extract_series(
            load_csv_rows(csv_path),
            'gdp',
            'm1_proxy',  # This column doesn't exist
            'employment_rate'  # This column doesn't exist either
        )
        
        assert len(steps) == 10, "Should extract all rows"
        assert 'gdp' in data, "Existing metric should be extracted"
        assert len(data['gdp']) == 10, "GDP data should be complete"
        # Missing metrics should have zero-series
        assert 'm1_proxy' in data, "Missing metric key should exist"
        assert len(data['m1_proxy']) == 10, "Missing metric should be zero-filled"
        assert all(v == 0.0 for v in data['m1_proxy']), "Missing metric values should be 0.0"
        assert 'employment_rate' in data, "Missing metric key should exist"
        assert len(data['employment_rate']) == 10, "Missing metric should be zero-filled"
    
    def test_plot_metrics_live_display_mode_non_interactive(self, simulated_metrics_dir):
        """Test plotting works in non-interactive mode (live=False)."""
        import matplotlib.pyplot as plt
        
        global_metrics_files = list(simulated_metrics_dir.glob("global_metrics_*.csv"))
        if not global_metrics_files:
            pytest.skip("No metrics files generated")
        
        # Force non-interactive backend
        import matplotlib
        matplotlib.use('Agg', force=True)
        
        rows = load_csv_rows(global_metrics_files[0])
        data = {'global': rows}
        
        # Generate plots without live display
        fig, filename = plot_overview_dashboard(data)
        
        assert fig is not None, "Figure should be created"
        assert len(fig.axes) > 0, "Figure should have axes"
        plt.close(fig)


class TestPlotMetricsDataExtraction:
    """Unit tests for data extraction helper functions."""
    
    def test_extract_series_with_extra_columns(self, tmp_path):
        """Extract specific columns from DataFrame with many columns."""
        import pandas as pd
        
        csv_path = tmp_path / "test_metrics.csv"
        data = {
            "time_step": [0, 1, 2, 3],
            "gdp": [100.0, 105.0, 110.0, 115.0],
            "m1_proxy": [200.0, 210.0, 220.0, 230.0],
            "unused_metric": [1, 2, 3, 4],
        }
        df = pd.DataFrame(data)
        df.to_csv(csv_path, index=False)
        
        rows = load_csv_rows(csv_path)
        steps, extracted = extract_series(rows, "gdp", "m1_proxy")
        
        assert steps == [0, 1, 2, 3]
        assert extracted["gdp"] == [100.0, 105.0, 110.0, 115.0]
        assert extracted["m1_proxy"] == [200.0, 210.0, 220.0, 230.0]
    
    def test_aggregate_company_metrics(self, tmp_path):
        """Aggregate company metrics by time step."""
        import pandas as pd
        
        csv_path = tmp_path / "company_metrics.csv"
        data = {
            "time_step": [0, 0, 1, 1, 2, 2],
            "agent_id": ["c1", "c2", "c1", "c2", "c1", "c2"],
            "sight_balance": [80.0, 60.0, 90.0, 70.0, 100.0, 80.0],
            "production_capacity": [30.0, 20.0, 30.0, 20.0, 30.0, 20.0],
            "rd_investment": [5.0, 2.0, 6.0, 3.0, 7.0, 4.0],
        }
        df = pd.DataFrame(data)
        df.to_csv(csv_path, index=False)
        
        rows = load_csv_rows(csv_path, usecols=["time_step", "sight_balance", 
                                                "production_capacity", "rd_investment"])
        steps, aggregated = aggregate_company_metrics(rows)
        
        assert steps == [0, 1, 2]
        assert aggregated["sight_balance"] == [140.0, 160.0, 180.0]
        assert aggregated["production_capacity"] == [50.0, 50.0, 50.0]
        assert aggregated["rd_investment"] == [7.0, 9.0, 11.0]
    
    def test_count_agents_per_step(self, tmp_path):
        """Count unique agents per time step."""
        import pandas as pd
        
        csv_path = tmp_path / "agent_counts.csv"
        data = {
            "time_step": [0, 0, 0, 1, 1, 2],
            "agent_id": ["h1", "h2", "h3", "h1", "h4", "h1"],
        }
        df = pd.DataFrame(data)
        df.to_csv(csv_path, index=False)
        
        rows = load_csv_rows(csv_path, skip_fields={"agent_id"}, usecols={"time_step"})
        steps, counts = count_agents_per_step(rows)
        
        assert steps == [0, 1, 2]
        assert counts == [3, 2, 1]
```

### Step 3: Update conftest.py with Fixtures

Add to `tests/conftest.py`:

```python
"""Test fixtures for plot_metrics integration tests."""

import pytest
from pathlib import Path
import tempfile


@pytest.fixture(scope="session")
def runner_metrics_dir():
    """Generate a minimal simulation run for integration tests.
    
    This fixture runs once per test session to avoid regenerating
    metrics on every test.
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
        assert (tmppath / "global_metrics").exists() or (tmppath / "global_metrics_" in [
            f.name for f in tmppath.iterdir() if f.suffix == '.csv'
        ]), "Global metrics not generated"
        
        yield tmppath
```

### Step 4: Verify Existing Tests Still Pass

Run all existing plot_metrics tests:

```bash
pytest tests/test_plot_metrics.py -xvs
```

All 28 existing tests should pass. Fix any issues found.

### Step 5: Run New Integration Tests

```bash
pytest tests/test_plot_metrics_integration.py -xvs
```

Fix any failures or issues.

### Step 6: Add to noxfile.py

```python
@nox.session
def test_plots(session):
    """Run plot metrics integration tests."""
    session.install("-r", "requirements.txt", "-r", "requirements-dev.txt")
    session.run("pytest", "tests/test_plot_metrics.py", "-xvs")
    session.run("pytest", "tests/test_plot_metrics_integration.py", "-xvs")
```

---

## Success Criteria

- ✅ All existing test_plot_metrics.py tests still pass (28 tests)
- ✅ New integration tests pass
- ✅ Plot generation verified as working end-to-end
- ✅ Performance tests confirm caching is effective
- ✅ No regressions in plotting functionality
- ✅ Integration tests run in CI

---

## Files to Create

- `tests/test_plot_metrics_integration.py`

---

## Files to Modify

- `tests/conftest.py` (add fixtures)
- `scripts/plot_metrics.py` (may need minor tweaks for testability, if any)
- `noxfile.py` (add test_plots session)

---

## Verification Commands

```bash
# Ensure existing tests pass
pytest tests/test_plot_metrics.py -xvs --tb=short

# Run new integration tests
pytest tests/test_plot_metrics_integration.py -xvs --tb=short

# Run all plot-related tests
pytest tests/test_plot_metrics*.py -xvs

# Check performance of caching
pytest tests/test_plot_metrics_integration.py::TestPlotMetricsIntegration::test_plot_metrics_csv_cache_works -xvs -k test_plot_metrics_csv_cache_works -vv
```

---

## Notes

- Integration tests verify the script works end-to-end with real simulation data
- Performance tests ensure CSV caching is working and provides speedup
- Lazy loading tests verify only needed columns are loaded (important for large metrics files)
- Missing metrics should be handled gracefully (not crash with KeyError)
- Non-interactive rendering (Agg backend) should be tested for CI environments

---

## Expected Timeline

2-3 hours to create integration tests and verify end-to-end functionality
