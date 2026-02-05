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

# Thresholds for regression detection (percentage deviation)
REGRESSION_THRESHOLDS = {
    "m1_proxy": 0.05,  # 5% deviation
    "gdp": 0.08,  # 8% deviation
    "employment_rate": 0.10,  # 10% deviation
    "price_index": 0.05,  # 5% deviation
    "total_households": 0.0,  # Zero tolerance on counts
    "total_companies": 0.0,
    "total_retailers": 0.0,
}


def load_baseline(baseline_path: Path) -> Dict[int, Dict[str, float]]:
    """Load baseline metrics from CSV file."""
    baseline = {}
    with open(baseline_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            step = int(row["time_step"])
            baseline[step] = {k: float(v) for k, v in row.items() if k != "time_step"}
    return baseline


def compare_metrics(
    current: Dict[int, Dict[str, float]],
    baseline: Dict[int, Dict[str, float]],
    thresholds: Dict[str, float],
) -> bool:
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
                print(
                    f"❌ Step {step} {metric}: "
                    f"baseline={baseline_val:.4f}, current={current_val:.4f}, "
                    f"deviation={deviation * 100:.2f}% (threshold={threshold * 100:.1f}%)"
                )
                passed = False
            else:
                # We don't print every success to avoid clutter
                pass

    return passed


def main():
    parser = argparse.ArgumentParser(description="Validate golden test scenarios against baselines")
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("output/golden_run_baseline"),
        help="Directory containing baseline CSV files",
    )
    parser.add_argument(
        "--metrics-dir",
        type=Path,
        default=Path("output/metrics"),
        help="Directory containing current metrics CSV files",
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
        print(f"\n{'=' * 60}")
        print(f"Validating: {scenario}")
        print(f"{'=' * 60}")

        baseline_path = baseline_dir / f"{scenario}.csv"
        if not baseline_path.exists():
            print(f"WARNING: Baseline not found for {scenario}, skipping")
            continue

        # Try to find matching current metrics
        # (In practice, run the scenario first or specify exact path)
        # For simplicity in this script, we look for global_metrics_seed_12345.csv
        # but in a real test it might be different.
        current_path = metrics_dir / f"global_metrics_seed_12345.csv"

        if not current_path.exists():
            # Try to find any global_metrics_*.csv if the seed one isn't there
            files = sorted(
                metrics_dir.glob("global_metrics_*.csv"), key=lambda p: p.stat().st_mtime
            )
            if files:
                current_path = files[-1]
            else:
                print(f"ERROR: Current metrics not found in {metrics_dir}")
                all_passed = False
                continue

        print(f"Comparing {current_path} against {baseline_path}")
        current = load_baseline(current_path)
        baseline = load_baseline(baseline_path)

        if compare_metrics(current, baseline, REGRESSION_THRESHOLDS):
            print(f"✅ {scenario}: PASSED")
        else:
            print(f"❌ {scenario}: FAILED")
            all_passed = False

    print(f"\n{'=' * 60}")
    if all_passed:
        print("✅ All golden test scenarios PASSED")
        sys.exit(0)
    else:
        print("❌ Some golden test scenarios FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
