"""
Validate golden test scenarios against baseline snapshots.

This script runs all golden test scenarios and compares key metrics
against baseline CSV files, flagging any regressions beyond thresholds.
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict

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


def load_baseline(baseline_path: Path) -> dict[int, dict[str, float]]:
    """Load baseline metrics from CSV file."""
    baseline: Dict[int, Dict[str, float]] = {}
    with open(baseline_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            step = int(row["time_step"])
            baseline[step] = {k: float(v) for k, v in row.items() if k != "time_step"}
    return baseline


def compare_metrics(
    current: dict[int, dict[str, float]],
    baseline: dict[int, dict[str, float]],
    thresholds: dict[str, float],
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
                epsilon = 0.001
                if abs(current_val) > epsilon:
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

    return passed


def main() -> int:
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
        return 1

    if not metrics_dir.exists():
        print(f"Error: Metrics directory not found: {metrics_dir}")
        return 1

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

        current_path = metrics_dir / "global_metrics_seed_12345.csv"
        if not current_path.exists():
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
        return 0
    print("❌ Some golden test scenarios FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
