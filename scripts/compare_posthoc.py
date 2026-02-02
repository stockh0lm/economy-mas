#!/usr/bin/env python3
"""Post-hoc counterfactual comparison (Option A).

Referenz: doc/issues.md Abschnitt 5 → „Implement Option A: Nutzerfreundliches Post-hoc-Gegenfaktum-Script“.

This script loads an existing metrics export (`global_metrics_<runid>.csv`) and produces a
*post-hoc* counterfactual view where services are set to zero. It then recomputes derived
series (GDP alt, price index alt, inflation alt, goods-only velocity) and generates
comparison plots (Original vs Counterfactual).

Notes
-----
- This is *not* a dynamic re-simulation. It is only an accounting counterfactual.
- Price dynamics are recomputed by copying the formula from `metrics.MetricsCollector._price_dynamics` and applying it
  recursively over the alternate GDP series.

Usage
-----
    python scripts/compare_posthoc.py --run-id 20260201_201734 --metrics-dir output/metrics --plots-dir output/plots --assume-services-in-gdp

Outputs
-------
- PNG plots under: <plots-dir>/<run-id>/posthoc/
- Differences CSV: posthoc_differences_<runid>.csv
- Summary markdown: posthoc_summary_<runid>.md
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable when executed as a script (pytest calls it via subprocess).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


import argparse
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")  # headless-safe default

import matplotlib.pyplot as plt
import pandas as pd

from config import CONFIG_MODEL, SimulationConfig


DEFAULT_METRICS_DIR = REPO_ROOT / "output" / "metrics"
DEFAULT_PLOTS_DIR = REPO_ROOT / "output" / "plots"


@dataclass(frozen=True)
class PlotSpec:
    name: str
    original_column: str
    counterfactual_column: str
    title: str
    ylabel: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Post-hoc counterfactual comparison: set service metrics to 0 and recompute derived series."
        )
    )
    parser.add_argument("--run-id", help="Run identifier suffix (e.g. 20260201_201734).")
    parser.add_argument(
        "--metrics-dir",
        default=str(DEFAULT_METRICS_DIR),
        help="Directory containing global_metrics_<runid>.csv (default: output/metrics).",
    )
    parser.add_argument(
        "--plots-dir",
        default=str(DEFAULT_PLOTS_DIR),
        help="Directory for generated plots (default: output/plots).",
    )
    parser.add_argument(
        "--assume-services-in-gdp",
        action="store_true",
        help=(
            "Assume exported `gdp` includes services and recompute goods-only GDP as gdp - service_value_total."
        ),
    )
    parser.add_argument(
        "--output-prefix",
        default="posthoc",
        help="Prefix for generated output files (default: posthoc).",
    )
    return parser.parse_args()


def detect_latest_run_id(metrics_dir: Path) -> str:
    candidates = sorted(metrics_dir.glob("global_metrics_*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No global_metrics_*.csv files were found in {metrics_dir}.")
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    suffix = latest.stem.split("global_metrics_")[-1]
    if not suffix:
        raise ValueError(f"Unable to parse run identifier from file name: {latest.name}.")
    return suffix


def load_global_metrics(run_id: str, metrics_dir: Path) -> pd.DataFrame:
    path = metrics_dir / f"global_metrics_{run_id}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing export: {path}")
    df = pd.read_csv(path)
    if "time_step" not in df.columns:
        raise ValueError(f"global metrics export has no time_step column: {path}")
    return df.sort_values("time_step").reset_index(drop=True)


def recompute_price_dynamics(
    *,
    time_steps: list[int],
    total_money: list[float],
    gdp: list[float],
    household_consumption: list[float],
    config: SimulationConfig,
) -> tuple[list[float], list[float], list[float]]:
    """Copy of MetricsCollector._price_dynamics, applied recursively to an arbitrary GDP series.

    Returns:
        price_index, inflation_rate, price_pressure
    """

    price_index_base = float(config.market.price_index_base)
    price_index_max = float(getattr(config.market, "price_index_max", 1000.0))
    pressure_target = float(config.market.price_index_pressure_target)
    price_sensitivity = float(config.market.price_index_sensitivity)
    pressure_mode = str(config.market.price_index_pressure_ratio)
    eps = 1e-9

    price_index: list[float] = []
    inflation: list[float] = []
    pressure: list[float] = []

    prev_price = price_index_base
    for i, step in enumerate(time_steps):
        money = float(total_money[i])
        gdp_i = float(gdp[i])
        cons = float(household_consumption[i])

        money_supply_pressure = money / (gdp_i + eps) if gdp_i > 0 else pressure_target
        consumption_pressure = cons / (gdp_i + eps) if gdp_i > 0 else pressure_target

        if pressure_mode == "consumption_to_production":
            price_pressure = consumption_pressure
        elif pressure_mode == "blended":
            price_pressure = 0.75 * money_supply_pressure + 0.25 * consumption_pressure
        else:
            price_pressure = money_supply_pressure

        # Copy of MetricsCollector._price_dynamics (stability fix):
        # converge to an equilibrium price level instead of compounding indefinitely.
        if pressure_target > 0:
            desired_price = price_index_base * (price_pressure / pressure_target)
        else:
            desired_price = price_index_base

        current_price = prev_price + price_sensitivity * (desired_price - prev_price)
        current_price = max(float(current_price), 0.01)
        if price_index_max > 0:
            current_price = min(float(current_price), float(price_index_max))
        if not (current_price == current_price) or current_price in (float("inf"), float("-inf")):
            current_price = float(price_index_max) if price_index_max > 0 else price_index_base
        infl = ((current_price - prev_price) / prev_price) if prev_price > 0 else 0.0

        pressure.append(price_pressure)
        price_index.append(current_price)
        inflation.append(infl)
        prev_price = current_price

    return price_index, inflation, pressure


def compute_counterfactual(
    global_df: pd.DataFrame,
    *,
    assume_services_in_gdp: bool,
    config: SimulationConfig | None = None,
) -> pd.DataFrame:
    """Return a counterfactual DataFrame with services set to 0 and derived fields recomputed."""

    cfg = config or CONFIG_MODEL

    df = global_df.copy()
    if "service_value_total" not in df.columns:
        df["service_value_total"] = 0.0
    if "service_tx_volume" not in df.columns:
        df["service_tx_volume"] = 0.0
    if "service_share_of_output" not in df.columns:
        df["service_share_of_output"] = 0.0

    # Preserve originals for alt computations.
    service_value_original = df["service_value_total"].fillna(0.0).astype(float)

    # Counterfactual: services removed.
    df["service_value_total"] = 0.0
    df["service_tx_volume"] = 0.0
    df["service_share_of_output"] = 0.0

    # Derived: goods-only velocity.
    if "goods_tx_volume" in df.columns and "m1_proxy" in df.columns:
        m1 = df["m1_proxy"].fillna(0.0).astype(float)
        goods_tx = df["goods_tx_volume"].fillna(0.0).astype(float)
        df["goods_only_velocity"] = goods_tx.div(m1.where(m1 > 0, other=pd.NA)).fillna(0.0)
    else:
        df["goods_only_velocity"] = 0.0

    # Derived: alternative GDP series.
    if "gdp" not in df.columns:
        df["gdp"] = 0.0

    if assume_services_in_gdp:
        df["gdp_alt"] = df["gdp"].fillna(0.0).astype(float) - service_value_original
    else:
        df["gdp_alt"] = df["gdp"].fillna(0.0).astype(float)

    # Price dynamics alt (recursive).
    for col in ("total_money_supply", "m1_proxy"):
        if col in df.columns:
            money_col = col
            break
    else:
        money_col = "total_money_supply"
        df[money_col] = 0.0

    if "household_consumption" not in df.columns:
        df["household_consumption"] = 0.0

    steps = df["time_step"].astype(int).tolist()
    total_money = df[money_col].fillna(0.0).astype(float).tolist()
    gdp_alt = df["gdp_alt"].fillna(0.0).astype(float).tolist()
    consumption = df["household_consumption"].fillna(0.0).astype(float).tolist()

    price_index_alt, inflation_alt, price_pressure_alt = recompute_price_dynamics(
        time_steps=steps,
        total_money=total_money,
        gdp=gdp_alt,
        household_consumption=consumption,
        config=cfg,
    )

    df["price_index_alt"] = price_index_alt
    df["inflation_rate_alt"] = inflation_alt
    df["price_pressure_alt"] = price_pressure_alt

    return df


def build_plot_specs() -> list[PlotSpec]:
    return [
        PlotSpec(
            name="price_index",
            original_column="price_index",
            counterfactual_column="price_index_alt",
            title="Price Index: Original vs Post-hoc (Services=0)",
            ylabel="Index",
        ),
        PlotSpec(
            name="inflation_rate",
            original_column="inflation_rate",
            counterfactual_column="inflation_rate_alt",
            title="Inflation Rate: Original vs Post-hoc (Services=0)",
            ylabel="Rate",
        ),
        PlotSpec(
            name="gdp",
            original_column="gdp",
            counterfactual_column="gdp_alt",
            title="GDP: Original vs Goods-only (post-hoc)",
            ylabel="Value",
        ),
        PlotSpec(
            name="service_value_total",
            original_column="service_value_total",
            counterfactual_column="service_value_total",
            title="Service Value (counterfactual set to 0)",
            ylabel="Value",
        ),
        PlotSpec(
            name="service_tx_volume",
            original_column="service_tx_volume",
            counterfactual_column="service_tx_volume",
            title="Service Transaction Volume (counterfactual set to 0)",
            ylabel="Value",
        ),
        PlotSpec(
            name="service_share_of_output",
            original_column="service_share_of_output",
            counterfactual_column="service_share_of_output",
            title="Service Share of Output (counterfactual set to 0)",
            ylabel="Share",
        ),
        PlotSpec(
            name="goods_only_velocity",
            original_column="goods_only_velocity",
            counterfactual_column="goods_only_velocity",
            title="Goods-only Velocity (goods_tx_volume / m1_proxy)",
            ylabel="Velocity",
        ),
    ]


def ensure_column(df: pd.DataFrame, col: str) -> None:
    if col not in df.columns:
        df[col] = 0.0


def plot_comparisons(
    *,
    original: pd.DataFrame,
    counterfactual: pd.DataFrame,
    out_dir: Path,
    specs: list[PlotSpec],
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    x = original["time_step"].astype(int)

    for spec in specs:
        ensure_column(original, spec.original_column)
        ensure_column(counterfactual, spec.counterfactual_column)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(x, original[spec.original_column].fillna(0.0).astype(float), label="Original")
        ax.plot(
            x,
            counterfactual[spec.counterfactual_column].fillna(0.0).astype(float),
            label="Post-hoc (Services=0)",
            linestyle="--",
        )
        ax.set_title(spec.title)
        ax.set_xlabel("Time Step")
        ax.set_ylabel(spec.ylabel)
        ax.grid(True, alpha=0.3)
        ax.legend()

        path = out_dir / f"{spec.name}.png"
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        written.append(path)

    return written


def write_differences_csv(
    *,
    original: pd.DataFrame,
    counterfactual: pd.DataFrame,
    out_path: Path,
    specs: list[PlotSpec],
) -> None:
    rows: dict[str, object] = {"time_step": original["time_step"].astype(int)}
    for spec in specs:
        ensure_column(original, spec.original_column)
        ensure_column(counterfactual, spec.counterfactual_column)
        rows[f"diff_{spec.name}"] = (
            counterfactual[spec.counterfactual_column].fillna(0.0).astype(float)
            - original[spec.original_column].fillna(0.0).astype(float)
        )
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)


def write_summary_md(
    *,
    original: pd.DataFrame,
    counterfactual: pd.DataFrame,
    out_path: Path,
    specs: list[PlotSpec],
    run_id: str,
    assume_services_in_gdp: bool,
) -> None:
    lines: list[str] = []
    lines.append(f"# Post-hoc Summary ({run_id})")
    lines.append("")
    lines.append("Referenz: doc/issues.md Abschnitt 5 → Implement Option A.")
    lines.append("")
    lines.append(f"- assume_services_in_gdp: {assume_services_in_gdp}")
    lines.append("")

    lines.append("## Max absolute differences")
    lines.append("")

    for spec in specs:
        ensure_column(original, spec.original_column)
        ensure_column(counterfactual, spec.counterfactual_column)
        diff = (
            counterfactual[spec.counterfactual_column].fillna(0.0).astype(float)
            - original[spec.original_column].fillna(0.0).astype(float)
        )
        max_abs = float(diff.abs().max()) if not diff.empty else 0.0
        lines.append(f"- {spec.name}: {max_abs:.6g}")

    lines.append("")
    lines.append("## Hinweis")
    lines.append(
        "Dies ist ein buchhalterisches Gegenfaktum (post-hoc). Es bildet keine dynamischen Rückkopplungen ab."
    )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    metrics_dir = Path(args.metrics_dir)
    plots_dir = Path(args.plots_dir)

    run_id = args.run_id or detect_latest_run_id(metrics_dir)

    global_df = load_global_metrics(run_id, metrics_dir)
    counterfactual_df = compute_counterfactual(
        global_df, assume_services_in_gdp=bool(args.assume_services_in_gdp)
    )

    # Ensure the original DataFrame also has goods_only_velocity for fair plotting.
    if "goods_only_velocity" not in global_df.columns:
        tmp = compute_counterfactual(global_df, assume_services_in_gdp=False)
        global_df = global_df.copy()
        global_df["goods_only_velocity"] = tmp["goods_only_velocity"]

    out_dir = plots_dir / run_id / "posthoc"
    specs = build_plot_specs()

    written = plot_comparisons(
        original=global_df,
        counterfactual=counterfactual_df,
        out_dir=out_dir,
        specs=specs,
    )

    diff_path = out_dir / f"{args.output_prefix}_differences_{run_id}.csv"
    write_differences_csv(original=global_df, counterfactual=counterfactual_df, out_path=diff_path, specs=specs)

    summary_path = out_dir / f"{args.output_prefix}_summary_{run_id}.md"
    write_summary_md(
        original=global_df,
        counterfactual=counterfactual_df,
        out_path=summary_path,
        specs=specs,
        run_id=run_id,
        assume_services_in_gdp=bool(args.assume_services_in_gdp),
    )

    print(f"run_id={run_id}")
    print(f"plots_dir={out_dir}")
    print(f"written_plots={len(written)}")
    print(f"differences={diff_path}")
    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
