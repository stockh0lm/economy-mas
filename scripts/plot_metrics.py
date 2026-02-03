"""Generate Matplotlib plots for the latest simulation metrics export.

Milestone 1 (doc/issues.md Abschnitt 5): Plot-Metrics Performance
- CSV-Caching (mehrere Plot-Läufe in einem Prozess)
- Lazy Loading (nur benötigte Spalten laden)
- Matplotlib Optimierungen: Agg Backend + Vermeidung teurer Tight-Bounding-Box Berechnungen
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path

import matplotlib

# Default to a non-interactive backend for faster, headless rendering.
# Users who want interactive display can override via MPLBACKEND env var.
if os.environ.get("MPLBACKEND") is None:
    matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
REPO_ROOT = Path(__file__).resolve().parents[1]
METRICS_DIR = REPO_ROOT / 'output' / 'metrics'
PLOTS_DIR = REPO_ROOT / 'output' / 'plots'
PlotFunc = Callable[[pd.DataFrame], tuple[plt.Figure, str]]


# -------------------------
# CSV loading + caching
# -------------------------

_CSV_CACHE: dict[tuple[str, int, tuple[str, ...], tuple[str, ...]], pd.DataFrame] = {}
_CSV_CACHE_HITS = 0
_CSV_CACHE_MISSES = 0


def clear_csv_cache() -> None:
    """Clear the in-process CSV cache (useful for tests)."""

    global _CSV_CACHE_HITS, _CSV_CACHE_MISSES
    _CSV_CACHE.clear()
    _CSV_CACHE_HITS = 0
    _CSV_CACHE_MISSES = 0


def csv_cache_info() -> dict[str, int]:
    """Return basic cache statistics."""

    return {
        "entries": len(_CSV_CACHE),
        "hits": int(_CSV_CACHE_HITS),
        "misses": int(_CSV_CACHE_MISSES),
    }

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render plots for the most recent metrics export using Matplotlib.')
    parser.add_argument('--run-id', help='Timestamp suffix of the metrics files (e.g. 20250101_120000). Uses the newest export automatically when omitted.')
    parser.add_argument('--metrics-dir', default=str(METRICS_DIR), help='Directory containing the metrics CSV/JSON exports (default: output/metrics).')
    parser.add_argument('--plots-dir', default=str(PLOTS_DIR), help='Directory where rendered plots will be written (default: output/plots).')
    parser.add_argument('--live-display', action='store_true', help='Show all plots interactively and synchronize cursor + axis limits across figures. When omitted, plots are only saved to disk.')
    return parser.parse_args()

def detect_latest_run_id(metrics_dir: Path) -> str:
    candidates = sorted(metrics_dir.glob('global_metrics_*.csv'))
    if not candidates:
        raise FileNotFoundError(f'No global_metrics_*.csv files were found in {metrics_dir}.')
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    suffix = latest.stem.split('global_metrics_')[-1]
    if not suffix:
        raise ValueError(f'Unable to parse run identifier from file name: {latest.name}.')
    return suffix

def load_csv_rows(
    path: Path,
    skip_fields: Iterable[str] | None = None,
    *,
    usecols: Iterable[str] | None = None,
    cache: bool = True,
) -> pd.DataFrame:
    """Load a metrics CSV into a DataFrame (fast path).

    Milestone 1 (doc/issues.md Abschnitt 5): CSV-Caching + Lazy Loading.

    Notes:
    - `skip_fields` columns are kept as strings (no numeric coercion).
    - Non-skip numeric columns are coerced via vectorized pandas.to_numeric.
    - `time_step` is always present (filled with 0 when missing) and stored as int.
    """

    global _CSV_CACHE_HITS, _CSV_CACHE_MISSES

    skip_set = frozenset(skip_fields) if skip_fields is not None else frozenset()
    usecols_set = frozenset(usecols) if usecols is not None else frozenset()
    resolved = path.resolve()

    # Cache-key includes mtime to keep correctness when a run overwrites CSV files.
    mtime_ns = resolved.stat().st_mtime_ns if resolved.exists() else 0
    cache_key = (str(resolved), int(mtime_ns), tuple(sorted(skip_set)), tuple(sorted(usecols_set)))

    if cache and cache_key in _CSV_CACHE:
        _CSV_CACHE_HITS += 1
        return _CSV_CACHE[cache_key]

    _CSV_CACHE_MISSES += 1

    if usecols is not None:
        desired = set(usecols_set)
        desired.add("time_step")
        desired.update(skip_set)
        df = pd.read_csv(resolved, usecols=lambda c: c in desired, dtype=str)
    else:
        df = pd.read_csv(resolved, dtype=str)

    # Normalize/convert types.
    if "time_step" not in df.columns:
        df["time_step"] = pd.Series([], dtype=int)
    df["time_step"] = (
        pd.to_numeric(df["time_step"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    for col in df.columns:
        if col == "time_step" or col in skip_set:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)

    if cache:
        _CSV_CACHE[cache_key] = df
    return df

def extract_series(rows: pd.DataFrame, *columns: str) -> tuple[list[int], dict[str, list[float]]]:
    """Extract time series data using optimized pandas operations.

    Args:
        rows: DataFrame containing the metrics data
        *columns: Column names to extract as series

    Returns:
        Tuple of (time_steps, series_data) where series_data is a dict mapping
        column names to lists of float values
    """
    df = rows.sort_values('time_step')
    steps = df['time_step'].astype(int).tolist()
    series = {}
    for column in columns:
        if column in df.columns:
            series_data = df[column].fillna(0.0).replace([np.inf, -np.inf], 0.0).astype(float)
            max_reasonable_value = 10000000000.0
            series_data = series_data.clip(upper=max_reasonable_value)
            series[column] = series_data.tolist()
        else:
            # Keep shapes consistent for plotting; missing columns become a 0-series.
            series[column] = [0.0 for _ in steps]
    return (steps, series)

def aggregate_company_metrics(rows: pd.DataFrame) -> tuple[list[int], dict[str, list[float]]]:
    """Aggregate company metrics using optimized pandas groupby operations.

    Args:
        rows: DataFrame containing company metrics data

    Returns:
        Tuple of (time_steps, aggregated_data) where aggregated_data contains
        sums for sight_balance, rd_investment, and production_capacity
    """
    # Backward-compatibility: older exports (and some tests) use `balance`
    # instead of `sight_balance`.
    has_sight = 'sight_balance' in rows.columns
    has_balance = 'balance' in rows.columns
    balance_col = 'sight_balance' if has_sight else ('balance' if has_balance else None)

    available_columns: list[str] = []
    if balance_col is not None:
        available_columns.append(balance_col)
    for col in ['rd_investment', 'production_capacity']:
        if col in rows.columns:
            available_columns.append(col)

    if not available_columns:
        return ([], {'sight_balance': [], 'balance': [], 'rd_investment': [], 'production_capacity': []})
    df = rows.copy()
    df['time_step'] = df['time_step'].astype(int)
    result = df.groupby('time_step')[available_columns].sum().fillna(0.0)
    steps = sorted(result.index.tolist())
    # Always expose both keys (`balance` and `sight_balance`) for robustness.
    if balance_col is not None and balance_col in result.columns:
        bal_series = result[balance_col]
    else:
        bal_series = pd.Series([0.0 for _ in steps], index=steps, dtype=float)
    aggregated = {
        'sight_balance': bal_series.tolist(),
        'balance': bal_series.tolist(),
        'rd_investment': result.get('rd_investment', pd.Series([0.0 for _ in steps], index=steps, dtype=float)).tolist(),
        'production_capacity': result.get('production_capacity', pd.Series([0.0 for _ in steps], index=steps, dtype=float)).tolist(),
    }
    return (steps, aggregated)

def count_agents_per_step(rows: pd.DataFrame) -> tuple[list[int], list[int]]:
    """Count unique agents per time step using optimized pandas operations.

    Args:
        rows: DataFrame containing agent data with time_step and agent_id

    Returns:
        Tuple of (time_steps, agent_counts) where agent_counts contains the number
        of unique agents at each time step
    """
    df = rows.copy()
    df['time_step'] = df['time_step'].astype(int)
    result = df.groupby('time_step')['agent_id'].nunique()
    steps = sorted(result.index.tolist())
    values = result.tolist()
    return (steps, values)

def plot_global_output(global_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = extract_series(global_rows, 'gdp', 'household_consumption', 'government_spending')
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(steps, data['gdp'], label='GDP')
    ax.plot(steps, data['household_consumption'], label='Household Consumption')
    ax.plot(steps, data['government_spending'], label='Government Spending')
    ax.set_title('Output Composition')
    ax.set_xlabel('Time Step')
    ax.set_ylabel('Value')
    ax.grid(True, alpha=0.3)
    ax.legend()
    return (fig, 'global_output.png')

def plot_monetary_system(global_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    """Diagnostics for the core Warengeld mechanism."""
    steps, data = extract_series(global_rows, 'm1_proxy', 'm2_proxy', 'cc_exposure', 'inventory_value_total', 'velocity_proxy')
    fig, ax_left = plt.subplots(figsize=(10, 6))
    ax_left.plot(steps, data['m1_proxy'], label='M1 proxy')
    ax_left.plot(steps, data['m2_proxy'], label='M2 proxy', linestyle='--')
    ax_left.plot(steps, data['inventory_value_total'], label='Retail inventory value', linestyle=':')
    ax_left.set_xlabel('Time Step')
    ax_left.set_ylabel('Level')
    ax_right = ax_left.twinx()
    ax_right.plot(steps, data['cc_exposure'], label='CC exposure')
    ax_right.plot(steps, data['velocity_proxy'], label='Velocity proxy', linestyle='--')
    ax_right.set_ylabel('Exposure / Velocity')
    ax_left.set_title('Money, Inventory, and Kontokorrent')
    ax_left.grid(True, alpha=0.3)
    lines = ax_left.get_lines() + ax_right.get_lines()
    labels = [line.get_label() for line in lines]
    ax_left.legend(lines, labels, loc='upper left')
    return (fig, 'monetary_system.png')

def plot_crash_diagnostics(global_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    """Crash diagnostics (separate from the dashboard).

    High-signal indicators for debugging systemic stalls:
    - goods_tx_volume, issuance_volume, extinguish_volume (real economy + Warengeld cycle)
    - cc_exposure vs cc_headroom_total (credit saturation / deadlock risk)
    - retailers_at_cc_limit_share, retailers_stockout_share (micro state that predicts freezes)
    """
    steps, data = extract_series(
        global_rows,
        'goods_tx_volume',
        'issuance_volume',
        'extinguish_volume',
        'cc_exposure',
        'cc_headroom_total',
        'retailers_at_cc_limit_share',
        'retailers_stockout_share',
        'inventory_value_total',
    )

    fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(12, 10), sharex=True)

    ax0 = axes[0]
    ax0.plot(steps, data['goods_tx_volume'], label='Goods Tx Volume', color='tab:blue')
    ax0.plot(steps, data['issuance_volume'], label='Issuance (Money Creation)', color='tab:green', linestyle='--')
    ax0.plot(steps, data['extinguish_volume'], label='Extinguish (Money Destruction)', color='tab:red', linestyle=':')
    ax0.set_ylabel('Flow ($/step)')
    ax0.set_title('Crash Diagnostics: Flows')
    ax0.grid(True, alpha=0.3)
    ax0.legend(loc='upper right')

    ax1 = axes[1]
    ax1.plot(steps, data['cc_exposure'], label='CC Exposure', color='tab:purple')
    ax1.plot(steps, data['cc_headroom_total'], label='Total CC Headroom', color='tab:orange', linestyle='--')
    ax1.plot(steps, data['inventory_value_total'], label='Retail Inventory Value', color='tab:gray', linestyle=':')
    ax1.set_ylabel('Stock / Exposure ($)')
    ax1.set_title('Credit Saturation vs Inventory')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right')

    ax2 = axes[2]
    ax2.plot(steps, data['retailers_at_cc_limit_share'], label='Retailers at CC Limit (share)', color='tab:brown')
    ax2.plot(steps, data['retailers_stockout_share'], label='Retailers Stockout (share)', color='tab:cyan', linestyle='--')
    ax2.set_xlabel('Time Step')
    ax2.set_ylabel('Share')
    ax2.set_ylim(0, 1.05)
    ax2.set_title('Micro Crash Predictors')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper right')

    fig.tight_layout()
    return (fig, 'crash_diagnostics.png')

def plot_labor_market(global_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = extract_series(global_rows, 'employment_rate', 'unemployment_rate', 'bankruptcy_rate')
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(steps, data['employment_rate'], label='Employment Rate')
    ax.plot(steps, data['unemployment_rate'], label='Unemployment Rate')
    ax.plot(steps, data['bankruptcy_rate'], label='Bankruptcy Rate')
    ax.set_title('Labor & Bankruptcy Rates')
    ax.set_xlabel('Time Step')
    ax.set_ylabel('Share of Workforce')
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend()
    return (fig, 'labor_market.png')

def plot_prices_and_wages(global_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, wage_series = extract_series(global_rows, 'average_nominal_wage', 'average_real_wage')
    _, price_series = extract_series(global_rows, 'price_index')
    _, inflation_series = extract_series(global_rows, 'inflation_rate')
    fig, ax_wage = plt.subplots(figsize=(10, 6))
    ax_wage.plot(steps, wage_series['average_nominal_wage'], label='Nominal Wage')
    ax_wage.plot(steps, wage_series['average_real_wage'], label='Real Wage')
    ax_wage.set_xlabel('Time Step')
    ax_wage.set_ylabel('Wage Level')
    ax_price = ax_wage.twinx()
    ax_price.plot(steps, price_series['price_index'], color='tab:purple', label='Price Index')
    ax_price.plot(steps, inflation_series['inflation_rate'], color='tab:orange', label='Inflation Rate')
    ax_price.set_ylabel('Price / Inflation')
    ax_wage.set_title('Wages, Prices & Inflation')
    ax_wage.grid(True, alpha=0.3)
    lines = ax_wage.get_lines() + ax_price.get_lines()
    labels = [line.get_label() for line in lines]
    ax_wage.legend(lines, labels, loc='upper right')
    return (fig, 'prices_and_wages.png')

def plot_state_budgets(state_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = extract_series(state_rows, 'environment_budget', 'infrastructure_budget', 'social_budget')
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(steps, data['environment_budget'], label='Environment Budget')
    ax.plot(steps, data['infrastructure_budget'], label='Infrastructure Budget')
    ax.plot(steps, data['social_budget'], label='Social Budget')
    ax.set_title('State Budget Allocation')
    ax.set_xlabel('Time Step')
    ax.set_ylabel('Budget ($)')
    ax.grid(True, alpha=0.3)
    ax.legend()
    return (fig, 'state_budgets.png')

def plot_company_health(company_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = aggregate_company_metrics(company_rows)
    fig, ax_balance = plt.subplots(figsize=(10, 6))
    series = data.get('sight_balance') or data.get('balance') or [0.0 for _ in steps]
    ax_balance.plot(steps, series, label='Aggregate Balance', color='tab:blue')
    ax_balance.set_xlabel('Time Step')
    ax_balance.set_ylabel('Balance ($)')
    ax_activity = ax_balance.twinx()
    ax_activity.plot(steps, data['rd_investment'], label='R&D Investment', color='tab:green', linestyle='--')
    ax_activity.plot(steps, data['production_capacity'], label='Production Capacity', color='tab:red', linestyle=':')
    ax_activity.set_ylabel('Investment / Capacity')
    ax_balance.set_title('Company Health Indicators')
    ax_balance.grid(True, alpha=0.3)
    lines = ax_balance.get_lines() + ax_activity.get_lines()
    labels = [line.get_label() for line in lines]
    ax_balance.legend(lines, labels, loc='upper left')
    return (fig, 'company_health.png')

def plot_household_population(household_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, counts = count_agents_per_step(household_rows)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(steps, counts, color='tab:blue')
    ax.set_title('Active Households')
    ax.set_xlabel('Time Step')
    ax.set_ylabel('# Households')
    ax.grid(True, alpha=0.3)
    return (fig, 'households_count.png')

def plot_company_population(company_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, counts = count_agents_per_step(company_rows)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(steps, counts, color='tab:green')
    ax.set_title('Active Companies')
    ax.set_xlabel('Time Step')
    ax.set_ylabel('# Companies')
    ax.grid(True, alpha=0.3)
    return (fig, 'companies_count.png')

def plot_overview_dashboard(data_by_scope: dict[str, pd.DataFrame]) -> tuple[plt.Figure, str]:
    """Create a compact dashboard (2x3 grid) combining key metrics so fewer figures are needed.

    Panels:
      0,0 - Global output (GDP, consumption, government spending)
      0,1 - Monetary aggregates (M1/M2, inventory, velocity)
      1,0 - Labor & bankruptcy rates
      1,1 - Wages, price index, inflation
      2,0 - Company health aggregates (sight_balance, R&D, capacity)
      2,1 - Population counts (households + companies)
    """
    global_rows = data_by_scope.get('global', pd.DataFrame())
    company_rows = data_by_scope.get('company', pd.DataFrame())
    household_rows = data_by_scope.get('household', pd.DataFrame())
    fig, axes = plt.subplots(nrows=3, ncols=2, figsize=(14, 12))
    axs = axes.flatten()
    steps, gdat = extract_series(global_rows, 'gdp', 'household_consumption', 'government_spending')
    ax = axs[0]
    if steps and any((gdat.get(k) for k in gdat)):
        ax.plot(steps, gdat.get('gdp', []), label='GDP', color='tab:blue')
        ax.plot(steps, gdat.get('household_consumption', []), label='Household Consumption', color='tab:orange')
        ax.plot(steps, gdat.get('government_spending', []), label='Government Spending', color='tab:green')
    ax.set_title('Output Composition')
    ax.set_xlabel('Time Step')
    ax.set_ylabel('Value')
    ax.grid(True, alpha=0.3)
    ax.legend()
    steps_m, mdat = extract_series(global_rows, 'm1_proxy', 'm2_proxy', 'inventory_value_total', 'velocity_proxy', 'cc_exposure')
    ax = axs[1]
    if steps_m:
        ax.plot(steps_m, mdat.get('m1_proxy', []), label='M1 proxy', color='tab:blue')
        ax.plot(steps_m, mdat.get('m2_proxy', []), label='M2 proxy', color='tab:cyan', linestyle='--')
        ax.plot(steps_m, mdat.get('inventory_value_total', []), label='Retail inventory value', color='tab:olive', linestyle=':')
        ax.set_xlabel('Time Step')
        ax.set_ylabel('Level')
        ax_r = ax.twinx()
        ax_r.plot(steps_m, mdat.get('cc_exposure', []), label='CC exposure', color='tab:red')
        ax_r.plot(steps_m, mdat.get('velocity_proxy', []), label='Velocity proxy', color='tab:purple', linestyle='--')
        ax_r.set_ylabel('Exposure / Velocity')
        lines = ax.get_lines() + ax_r.get_lines()
        labels = [l.get_label() for l in lines]
        ax.legend(lines, labels, loc='upper left')
    ax.set_title('Money, Inventory & Velocity')
    ax.grid(True, alpha=0.3)
    steps_l, ldat = extract_series(global_rows, 'employment_rate', 'unemployment_rate', 'bankruptcy_rate')
    ax = axs[2]
    if steps_l:
        ax.plot(steps_l, ldat.get('employment_rate', []), label='Employment Rate', color='tab:green')
        ax.plot(steps_l, ldat.get('unemployment_rate', []), label='Unemployment Rate', color='tab:orange')
        ax.plot(steps_l, ldat.get('bankruptcy_rate', []), label='Bankruptcy Rate', color='tab:red')
    ax.set_title('Labor & Bankruptcy Rates')
    ax.set_xlabel('Time Step')
    ax.set_ylabel('Share')
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend()
    steps_w, wdat = extract_series(global_rows, 'average_nominal_wage', 'average_real_wage', 'price_index', 'inflation_rate')
    ax = axs[3]
    if steps_w:
        ax.plot(steps_w, wdat.get('average_nominal_wage', []), label='Nominal Wage', color='tab:blue')
        ax.plot(steps_w, wdat.get('average_real_wage', []), label='Real Wage', color='tab:green')
        ax.set_xlabel('Time Step')
        ax.set_ylabel('Wage Level')
        ax_p = ax.twinx()
        ax_p.plot(steps_w, wdat.get('price_index', []), label='Price Index', color='tab:purple')
        ax_p.plot(steps_w, wdat.get('inflation_rate', []), label='Inflation Rate', color='tab:orange')
        ax_p.set_ylabel('Price / Inflation')
        lines = ax.get_lines() + ax_p.get_lines()
        labels = [l.get_label() for l in lines]
        ax.legend(lines, labels, loc='upper right')
    ax.set_title('Wages, Prices & Inflation')
    ax.grid(True, alpha=0.3)
    steps_c, cdat = aggregate_company_metrics(company_rows)
    ax = axs[4]
    if steps_c:
        ax.plot(steps_c, cdat.get('sight_balance', []), label='Aggregate Balance', color='tab:blue')
        ax.set_xlabel('Time Step')
        ax.set_ylabel('Balance ($)')
        ax_a = ax.twinx()
        ax_a.plot(steps_c, cdat.get('rd_investment', []), label='R&D Investment', color='tab:green', linestyle='--')
        ax_a.plot(steps_c, cdat.get('production_capacity', []), label='Production Capacity', color='tab:red', linestyle=':')
        ax_a.set_ylabel('Investment / Capacity')
        lines = ax.get_lines() + ax_a.get_lines()
        labels = [l.get_label() for l in lines]
        ax.legend(lines, labels, loc='upper left')
    ax.set_title('Company Health Indicators')
    ax.grid(True, alpha=0.3)
    steps_h, hcounts = count_agents_per_step(household_rows)
    steps_co, ccounts = count_agents_per_step(company_rows)
    ax = axs[5]
    all_steps = sorted(set(steps_h) | set(steps_co))

    def reindex(values_steps, values, target_steps):
        mapping = dict(zip(values_steps, values))
        return [mapping.get(s, 0) for s in target_steps]
    hvals = reindex(steps_h, hcounts, all_steps)
    cvals = reindex(steps_co, ccounts, all_steps)
    if all_steps:
        ax.plot(all_steps, hvals, label='# Households', color='tab:blue')
        ax.plot(all_steps, cvals, label='# Companies', color='tab:green')
    ax.set_title('Active Agents')
    ax.set_xlabel('Time Step')
    ax.set_ylabel('Count')
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return (fig, 'overview_dashboard.png')
PLOT_SPECS: list[tuple[str, PlotFunc]] = [
    ('global', plot_global_output),
    ('global', plot_monetary_system),
    ('global', plot_labor_market),
    ('global', plot_prices_and_wages),
    # Separate crash/debug plot (not part of the dashboard)
    ('global', plot_crash_diagnostics),
    ('state', plot_state_budgets),
    ('company', plot_company_health),
    ('household', plot_household_population),
    ('company', plot_company_population),
]

def main() -> None:
    args = parse_args()
    metrics_dir = Path(args.metrics_dir)
    plots_dir = Path(args.plots_dir)
    run_id = args.run_id or detect_latest_run_id(metrics_dir)
    run_dir = plots_dir / run_id
    latest_dir = ensure_dirs(run_dir)

    # Lazy-load only the columns needed for the plot set.
    # (Reducible I/O + parsing time dominates for repeated plot runs.)
    global_cols = {
        "time_step",
        "gdp",
        "household_consumption",
        "government_spending",
        "m1_proxy",
        "m2_proxy",
        "cc_exposure",
        "inventory_value_total",
        "velocity_proxy",
        "employment_rate",
        "unemployment_rate",
        "bankruptcy_rate",
        "average_nominal_wage",
        "average_real_wage",
        "price_index",
        "inflation_rate",
        "environment_budget",
        "infrastructure_budget",
        "social_budget",
        # Crash diagnostics
        "goods_tx_volume",
        "issuance_volume",
        "extinguish_volume",
        "cc_headroom_total",
        "avg_cc_utilization",
        "retailers_at_cc_limit_share",
        "retailers_stockout_share",
    }
    state_cols = {"time_step", "agent_id", "environment_budget", "infrastructure_budget", "social_budget"}
    company_cols = {
        "time_step",
        "agent_id",
        "sight_balance",
        "balance",
        "rd_investment",
        "production_capacity",
    }
    household_cols = {"time_step", "agent_id"}

    global_rows = load_csv_rows(metrics_dir / f"global_metrics_{run_id}.csv", usecols=global_cols)
    state_rows = load_csv_rows(
        metrics_dir / f"state_metrics_{run_id}.csv",
        skip_fields={"agent_id"},
        usecols=state_cols,
    )
    company_rows = load_csv_rows(
        metrics_dir / f"company_metrics_{run_id}.csv",
        skip_fields={"agent_id"},
        usecols=company_cols,
    )
    household_rows = load_csv_rows(
        metrics_dir / f"household_metrics_{run_id}.csv",
        skip_fields={"agent_id"},
        usecols=household_cols,
    )
    data_by_scope = {'global': global_rows, 'state': state_rows, 'company': company_rows, 'household': household_rows}
    figures: list[plt.Figure] = []
    axes: list[plt.Axes] = []

    fig, filename = plot_overview_dashboard(data_by_scope)
    figures.append(fig)
    axes.extend(fig.axes)
    save_figure(fig, filename, run_dir, latest_dir, close_figure=not args.live_display)
    for scope, plot_func in PLOT_SPECS:
        fig, filename = plot_func(data_by_scope[scope])
        figures.append(fig)
        axes.extend(fig.axes)
        save_figure(fig, filename, run_dir, latest_dir, close_figure=not args.live_display)
    if args.live_display:
        on_move = add_linked_cursor(axes)
        for fig in figures:
            fig.canvas.mpl_connect('motion_notify_event', on_move)
        sync_axis_limits(axes)
        plt.show(block=True)

def sync_axis_limits(axes: list[plt.Axes]) -> None:
    """Synchronize zoom/pan (x/y limits) across all axes.

    Matplotlib doesn't provide this out of the box across multiple figures.
    We listen to xlim/ylim change events and propagate them.
    """
    if not axes:
        return
    syncing = {'active': False}

    def _on_xlim_changed(changed_ax: plt.Axes):
        if syncing['active']:
            return
        syncing['active'] = True
        try:
            xlim = changed_ax.get_xlim()
            for ax in axes:
                if ax is changed_ax:
                    continue
                ax.set_xlim(xlim)
                ax.figure.canvas.draw_idle()
        finally:
            syncing['active'] = False

    def _on_ylim_changed(changed_ax: plt.Axes):
        if syncing['active']:
            return
        syncing['active'] = True
        try:
            ylim = changed_ax.get_ylim()
            for ax in axes:
                if ax is changed_ax:
                    continue
                ax.set_ylim(ylim)
                ax.figure.canvas.draw_idle()
        finally:
            syncing['active'] = False
    for ax in axes:
        ax.callbacks.connect('xlim_changed', _on_xlim_changed)
        ax.callbacks.connect('ylim_changed', _on_ylim_changed)

def add_linked_cursor(axes: list[plt.Axes]) -> Callable[[object], None]:
    lines = [ax.axvline(color='gray', lw=0.8, alpha=0.5, visible=False) for ax in axes]
    canvases = {ax.figure.canvas for ax in axes}

    def on_move(event):
        if event.inaxes is None or event.xdata is None:
            for line in lines:
                line.set_visible(False)
        else:
            for line in lines:
                line.set_xdata([event.xdata, event.xdata])
                line.set_visible(True)
        for canvas in canvases:
            canvas.draw_idle()
    return on_move

def ensure_dirs(directory: Path) -> Path:
    """Ensure that the specified directory exists, creating it if necessary.

    Args:
        directory: Path object pointing to the directory to ensure exists

    Returns:
        The same Path object for convenience
    """
    directory.mkdir(parents=True, exist_ok=True)
    return directory

def save_figure(fig: plt.Figure, filename: str, run_dir: Path, latest_dir: Path, close_figure: bool=True) -> None:
    """Save a matplotlib figure to a file in the specified directory.

    Args:
        fig: The matplotlib figure to save
        filename: The filename for the saved figure
        run_dir: The base directory where figures should be saved
        latest_dir: The specific run directory (should be same as run_dir in current usage)
        close_figure: Whether to close the figure after saving
    """
    save_path = latest_dir / filename
    # Avoid bbox_inches='tight' (expensive text-layout hotpath in profiling).
    fig.savefig(save_path, dpi=150)
    if close_figure:
        plt.close(fig)

def try_float(value: str | None) -> float | None:
    if value is None or value == '':
        return None
    try:
        return float(value)
    except ValueError:
        return None
if __name__ == '__main__':
    main()
