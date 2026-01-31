"""Validate that CSV exports represent the in-memory metric dictionaries.

This is a regression/consistency check used during the metrics refactor:
- run a short seeded simulation
- export metrics
- rebuild expected DataFrames from the in-memory nested dicts
- reload CSVs and compare (ignoring dtype differences, NaNs)

Run:
  python scripts/validate_metrics_export.py
"""

from __future__ import annotations

from pathlib import Path
import sys

# Allow running as a script without installing the package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from pandas.testing import assert_frame_equal

import logging

# Silence noisy warnings emitted by some legacy code paths.
logging.getLogger().setLevel(logging.CRITICAL)

from config import SimulationConfig
from main import run_simulation


def _df_from_global(global_metrics: dict[int, dict]) -> pd.DataFrame:
    rows: list[dict] = []
    for step, metrics in global_metrics.items():
        row = {"time_step": int(step)}
        row.update(metrics)
        rows.append(row)
    df = pd.DataFrame.from_records(rows)
    if not df.empty:
        df = df.sort_values("time_step").reset_index(drop=True)
    return df


def _df_from_agent(agent_metrics: dict[str, dict[int, dict]]) -> pd.DataFrame:
    rows: list[dict] = []
    for agent_id, time_series in agent_metrics.items():
        for step, metrics in time_series.items():
            row = {"time_step": int(step), "agent_id": str(agent_id)}
            row.update(metrics)
            rows.append(row)
    df = pd.DataFrame.from_records(rows)
    if not df.empty:
        df = df.sort_values(["time_step", "agent_id"]).reset_index(drop=True)
    return df


def _latest_csv(export_dir: Path, prefix: str) -> Path:
    matches = sorted(export_dir.glob(f"{prefix}_*.csv"))
    if not matches:
        raise FileNotFoundError(f"No CSV exports for prefix={prefix} in {export_dir}")
    return matches[-1]


def _load_and_normalize(path: Path, sort_cols: list[str]) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in sort_cols:
        if col not in df.columns:
            raise AssertionError(f"{path.name}: missing required column {col}")
    df = df.sort_values(sort_cols).reset_index(drop=True)
    return df


def main() -> None:
    out_dir = Path("output") / "metrics_validate"
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = SimulationConfig(simulation_steps=15)
    cfg.population.num_households = 40
    cfg.population.num_companies = 10
    cfg.population.num_retailers = 6
    cfg.population.seed = 7

    cfg.metrics_export_path = str(out_dir)
    cfg.logging_level = "ERROR"

    agents = run_simulation(cfg)
    collector = agents["metrics_collector"]

    checks = {
        "global_metrics": (
            _df_from_global(collector.global_metrics),
            _load_and_normalize(_latest_csv(out_dir, "global_metrics"), ["time_step"]),
            ["time_step"],
        ),
        "household_metrics": (
            _df_from_agent(collector.household_metrics),
            _load_and_normalize(_latest_csv(out_dir, "household_metrics"), ["time_step", "agent_id"]),
            ["time_step", "agent_id"],
        ),
        "company_metrics": (
            _df_from_agent(collector.company_metrics),
            _load_and_normalize(_latest_csv(out_dir, "company_metrics"), ["time_step", "agent_id"]),
            ["time_step", "agent_id"],
        ),
        "retailer_metrics": (
            _df_from_agent(collector.retailer_metrics),
            _load_and_normalize(_latest_csv(out_dir, "retailer_metrics"), ["time_step", "agent_id"]),
            ["time_step", "agent_id"],
        ),
        "bank_metrics": (
            _df_from_agent(collector.bank_metrics),
            _load_and_normalize(_latest_csv(out_dir, "bank_metrics"), ["time_step", "agent_id"]),
            ["time_step", "agent_id"],
        ),
        "state_metrics": (
            _df_from_agent(collector.state_metrics),
            _load_and_normalize(_latest_csv(out_dir, "state_metrics"), ["time_step", "agent_id"]),
            ["time_step", "agent_id"],
        ),
        "market_metrics": (
            _df_from_agent(collector.market_metrics),
            _load_and_normalize(_latest_csv(out_dir, "market_metrics"), ["time_step", "agent_id"]),
            ["time_step", "agent_id"],
        ),
    }

    for name, (expected, actual, sort_cols) in checks.items():
        # Align column sets: missing columns become NaN
        for col in set(expected.columns).difference(actual.columns):
            actual[col] = pd.NA
        for col in set(actual.columns).difference(expected.columns):
            expected[col] = pd.NA

        expected = expected.reindex(sorted(expected.columns), axis=1)
        actual = actual.reindex(sorted(actual.columns), axis=1)

        expected = expected.sort_values(sort_cols).reset_index(drop=True)
        actual = actual.sort_values(sort_cols).reset_index(drop=True)

        assert_frame_equal(
            expected,
            actual,
            check_dtype=False,
            check_like=True,
        )

    print(f"OK: CSV exports match in-memory metrics. Export dir: {out_dir}")


if __name__ == "__main__":
    main()
