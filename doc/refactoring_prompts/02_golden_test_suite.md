# Prompt 2: Create Enhanced Golden Test Suite

## Context
A single golden test is insufficient for catching regressions. We need a more comprehensive suite that validates simulation behavior across multiple scenarios. Any helpers referenced must be defined in this prompt or already exist in the repo.

---

## Task

### Step 1: Create Test Module

Create `tests/test_golden_run_comprehensive.py` with multiple test scenarios. These tests must read from exported metrics CSVs in `cfg.metrics_export_path`.

```python
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
```

### Step 1b: Git Workflow (Required)

- Create a refactoring branch (example): `git checkout -b refactor/p02-golden-suite`
- Before changes: `git status` and `git diff`
- Commit after each logical step with a clear message
- Reviewer model checks `git diff --stat` and `git show` before approving
- Roll back safely if needed: `git restore <files>` for uncommitted changes, `git revert <commit>` for committed changes (no `reset --hard`)

---

## Controlled Diagnostics (Required)

- Use only existing tests and temporary files under `tmp_path` or `output/` with clear naming
- If a debug script is necessary, it must be named `debug_*.py` and deleted after use
- Do not add permanent debug tests
- Prefer metrics CSV exports to validate scenarios

---

### Step 2: Optional Validation Script

If you want CSV baseline comparison, create `scripts/validate_golden_run.py` and wire it to real CSV exports. This is optional and must not be a dependency for the tests above. Use the same CSV structure exported by `metrics.py` (global_metrics_*.csv).

```python
#!/usr/bin/env python3
"""
Validate golden test scenarios against baseline snapshots.

This script runs all golden test scenarios and compares key metrics
against baseline CSV files, flagging any regressions beyond thresholds.
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, Any

import pandas as pd

# Thresholds for regression detection (percentage deviation)
REGRESSION_THRESHOLDS = {
    "m1_proxy": 0.05,              # 5% deviation
    "gdp": 0.08,                   # 8% deviation
    "employment_rate": 0.10,       # 10% deviation
    "price_index": 0.05,           # 5% deviation
    "total_households": 0.0,       # Zero tolerance on counts
    "total_companies": 0.0,
    "total_retailers": 0.0,
}

def load_baseline(baseline_path: Path) -> Dict[int, Dict[str, float]]:
    """Load baseline metrics from CSV file."""
    baseline = {}
    with open(baseline_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            step = int(row["time_step"])
            baseline[step] = {k: float(v) for k, v in row.items() if k != "time_step"}
    return baseline

def compare_metrics(current: Dict[int, Dict[str, float]], 
                   baseline: Dict[int, Dict[str, float]],
                   thresholds: Dict[str, float]) -> bool:
    """
    Compare current metrics against baseline.
    
    Returns:
        True if all metrics within thresholds, False otherwise.
    """
    passed = True
    
    for step, current_row in current.items():
        if step not in baseline:
            print(f"WARNING: Step {step} in current but not baseline")
            continue
        
        baseline_row = baseline[step]
        
        for metric, threshold in thresholds.items():
            if metric not in current_row or metric not in baseline_row:
                continue
            
            current_val = current_row[metric]
            baseline_val = baseline_row[metric]
            
            if baseline_val == 0.0:
                if abs(current_val) > 0.001:  # Small epsilon
                    print(f"❌ Step {step} {metric}: baseline=0, current={current_val}")
                    passed = False
                continue
            
            deviation = abs((current_val - baseline_val) / baseline_val)
            
            if deviation > threshold:
                print(f"❌ Step {step} {metric}: "
                      f"baseline={baseline_val:.4f}, current={current_val:.4f}, "
                      f"deviation={deviation*100:.2f}% (threshold={threshold*100:.1f}%)")
                passed = False
            else:
                print(f"✓ Step {step} {metric}: "
                      f"baseline={baseline_val:.4f}, current={current_val:.4f}, "
                      f"deviation={deviation*100:.2f}%")
    
    return passed

def main():
    parser = argparse.ArgumentParser(
        description="Validate golden test scenarios against baselines"
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("output/golden_run_baseline"),
        help="Directory containing baseline CSV files"
    )
    parser.add_argument(
        "--metrics-dir",
        type=Path,
        default=Path("output/metrics"),
        help="Directory containing current metrics CSV files"
    )
    
    args = parser.parse_args()
    
    baseline_dir = args.baseline_dir
    metrics_dir = args.metrics_dir
    
    if not baseline_dir.exists():
        print(f"Error: Baseline directory not found: {baseline_dir}")
        sys.exit(1)
    
    if not metrics_dir.exists():
        print(f"Error: Metrics directory not found: {metrics_dir}")
        sys.exit(1)
    
    # Define scenarios to validate
    scenarios = [
        "baseline_short_default",
        "baseline_medium_quarterly",
        "baseline_demography",
        "baseline_multi_region",
        "baseline_company_dynamics",
    ]
    
    all_passed = True
    
    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"Validating: {scenario}")
        print(f"{'='*60}")
        
        baseline_path = baseline_dir / f"{scenario}.csv"
        if not baseline_path.exists():
            print(f"WARNING: Baseline not found for {scenario}, skipping")
            continue
        
        # Try to find matching current metrics
        # (In practice, run the scenario first or specify exact path)
        current_path = metrics_dir / f"global_metrics_seed_12345.csv"
        
        if not current_path.exists():
            print(f"ERROR: Current metrics not found: {current_path}")
            print("Hint: Run the scenario with SIM_SEED=12345 first")
            all_passed = False
            continue
        
        current = load_baseline(current_path)
        baseline = load_baseline(baseline_path)
        
        if compare_metrics(current, baseline, REGRESSION_THRESHOLDS):
            print(f"✅ {scenario}: PASSED")
        else:
            print(f"❌ {scenario}: FAILED")
            all_passed = False
    
    print(f"\n{'='*60}")
    if all_passed:
        print("✅ All golden test scenarios PASSED")
        sys.exit(0)
    else:
        print("❌ Some golden test scenarios FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Step 3: Optional Helpers

Only add helper modules if you can base them on existing data sources (exported CSVs). Avoid inventing invariants that depend on non-existent fields. Keep any helper optional to avoid hard dependencies in the new tests.

### Step 4: Optional nox Session

If you want CI integration, add a `test_golden` nox session to run the suite. This is optional.

### Step 5: Optional Baselines

If you choose to maintain baselines, generate them with a fixed seed and keep them under `output/golden_run_baseline/`. This step is optional and should only be done after a known-good run.

### Step 6: Create Documentation

Create `doc/golden_test_suite.md`:

```markdown
# Golden Test Suite Documentation

## Purpose
The golden test suite validates simulation behavior across multiple scenarios and catches regressions in core economic behavior.

## Scenarios

1. **Baseline Short (30 steps)**: Validates basic operation with default parameters
2. **Quarterly (90 steps)**: Validates behavior over longer time horizons
3. **Demography Tests**: Validates mortality, fertility, and age progression
4. **Multi-Region Tests**: Validates spatial distribution and local trade
5. **Company Dynamics**: Validates founding, mergers, and bankruptcy

## Running the Suite

```bash
# Run all golden tests
pytest tests/test_golden_run_comprehensive.py -xvs

# Optional: validate against baselines
python scripts/validate_golden_run.py

# Optional: update baselines after intentional changes
# (only if you implement baseline export logic)
UPDATE_BASELINES=1 pytest tests/test_golden_run_comprehensive.py
```

## Interpreting Results

- ✅ All scenarios pass: Simulation is stable
- ⚠️ Small deviations (< threshold): Acceptable stochastic variance
- ❌ Large deviations: Potential regression or bug

## Regressing Metrics and Thresholds

| Metric | Threshold | Reason |
|--------|-----------|--------|
| m1_proxy | 5% | Money supply must be stable |
| gdp | 8% | Allows for seasonal variance |
| employment_rate | 10% | Labor market has inherent variance |
| price_index | 5% | Inflation must be controlled |
| total_households | 0% | Exact count match for demography |
```

---

## Success Criteria

- ✅ New comprehensive golden test suite passes
- ✅ Tests do not rely on undefined helpers
- ✅ (Optional) baseline CSV snapshots created and validated
- ✅ Documentation created in `doc/golden_test_suite.md`

---

## Files to Create

- `tests/test_golden_run_comprehensive.py`
- `scripts/validate_golden_run.py` (optional)
- `output/golden_run_baseline/` directory with snapshots (optional)
- `doc/golden_test_suite.md`

---

## Files to Modify

- `noxfile.py` (optional: add test_golden session)

---

## Verification Commands

```bash
# Run new golden test suite
pytest tests/test_golden_run_comprehensive.py -xvs

# Optional: validate against baselines
python scripts/validate_golden_run.py
```

---

## Notes

- Use fixed seed (SIM_SEED=12345) for reproducible baselines
- Baselines should only change after intentional refactors
- Different scenarios require different tolerance thresholds
- Some metrics have strict thresholds (counts) while others allow variance (rates)

---

## Expected Timeline

3-4 hours to create comprehensive test suite and generate baselines
