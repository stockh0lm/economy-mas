"""Generate Matplotlib plots for the latest simulation metrics export."""
from __future__ import annotations

import argparse
import shutil
from collections.abc import Callable
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
METRICS_DIR = REPO_ROOT / "output" / "metrics"
PLOTS_DIR = REPO_ROOT / "output" / "plots"

PlotFunc = Callable[[pd.DataFrame], tuple[plt.Figure, str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render plots for the most recent metrics export using Matplotlib."
    )
    parser.add_argument(
        "--run-id",
        help="Timestamp suffix of the metrics files (e.g. 20250101_120000)."
        " Uses the newest export automatically when omitted.",
    )
    parser.add_argument(
        "--metrics-dir",
        default=str(METRICS_DIR),
        help="Directory containing the metrics CSV/JSON exports (default: output/metrics).",
    )
    parser.add_argument(
        "--plots-dir",
        default=str(PLOTS_DIR),
        help="Directory where rendered plots will be written (default: output/plots).",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the figures in an interactive window after saving them.",
    )
    parser.add_argument(
        "--link-cursor",
        action="store_true",
        help="When used with --show, keep a synchronized vertical cursor across plots.",
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


def load_csv_rows(path: Path, skip_fields: Iterable[str] | None = None) -> pd.DataFrame:
    """Load CSV data

    Args:
        path: Path to CSV file
        skip_fields: Fields to skip numeric conversion on

    Returns:
        DataFrame with loaded data
    """
    skip_fields = set(skip_fields or [])

    df = pd.read_csv(path)
    # Convert time_step to int
    df['time_step'] = pd.to_numeric(df['time_step'], errors='coerce').fillna(0).astype(int)

    # Convert numeric columns, skip specified fields
    numeric_cols = [col for col in df.columns if col not in skip_fields and col != 'time_step']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def try_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def ensure_dirs(run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    latest_dir = run_dir.parent / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    return latest_dir


def save_figure(
    fig: plt.Figure,
    filename: str,
    run_dir: Path,
    latest_dir: Path,
    close_figure: bool = True,
) -> None:
    target = run_dir / filename
    fig.savefig(target, dpi=150, bbox_inches="tight")
    shutil.copy2(target, latest_dir / filename)
    if close_figure:
        plt.close(fig)


def extract_series(
    df: pd.DataFrame, *columns: str
) -> tuple[list[int], dict[str, list[float]]]:
    """Extract time series data

    Args:
        df: DataFrame with data
        columns: Column names to extract

    Returns:
        Tuple of (time_steps, {column: values})
    """
    # Sort by time_step
    df_sorted = df.sort_values('time_step')

    # Extract time steps
    steps = df_sorted['time_step'].tolist()

    # Extract series data, filling missing values with 0.0
    series: dict[str, list[float]] = {}
    for column in columns:
        # Only include columns that exist in the dataframe
        if column in df_sorted.columns:
            # Use pandas vectorized operations
            col_data = df_sorted[column].fillna(0.0).tolist()
            series[column] = col_data
        else:
            # Fill with zeros if column doesn't exist
            series[column] = [0.0] * len(steps)

    return steps, series


def aggregate_company_metrics(
    df: pd.DataFrame
) -> tuple[list[int], dict[str, list[float]]]:
    """Aggregate company metrics using pandas DataFrame operations.

    Args:
        df: DataFrame with company data

    Returns:
        Tuple of (time_steps, aggregated_metrics)
    """
    # Ensure time_step is int
    df['time_step'] = df['time_step'].astype(int)

    # Only aggregate columns that exist in the dataframe
    agg_columns = {
        'balance': 'sum',
        'rd_investment': 'sum',
        'production_capacity': 'sum'
    }

    # Filter to only include columns that exist
    existing_columns = {col: func for col, func in agg_columns.items() if col in df.columns}
    if not existing_columns:
        # Return empty results if no valid columns
        return [], {}

    # Group by time_step and sum numeric columns
    aggregated_df = df.groupby('time_step', as_index=False).agg(existing_columns).fillna(0.0)

    # Sort by time_step
    aggregated_df = aggregated_df.sort_values('time_step')

    # Convert to output format
    steps = aggregated_df['time_step'].tolist()
    aggregated = {
        col: aggregated_df[col].tolist() for col in existing_columns.keys()
    }
    return steps, aggregated


def count_agents_per_step(df: pd.DataFrame) -> tuple[list[int], list[int]]:
    """Count agents per time step using pandas DataFrame operations.

    Args:
        df: DataFrame with agent data

    Returns:
        Tuple of (time_steps, agent_counts)
    """
    # Ensure time_step is int
    df['time_step'] = df['time_step'].astype(int)

    # Check if agent_id column exists
    if 'agent_id' not in df.columns:
        # Return empty results if no agent_id column
        return [], []

    # Count unique agents per time step
    count_df = df.groupby('time_step')['agent_id'].nunique().reset_index()
    count_df = count_df.sort_values('time_step')

    steps = count_df['time_step'].tolist()
    values = count_df['agent_id'].tolist()
    return steps, values


def plot_global_output(global_df: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = extract_series(
        global_df,
        "gdp",
        "household_consumption",
        "government_spending",
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(steps, data["gdp"], label="GDP")
    ax.plot(steps, data["household_consumption"], label="Household Consumption")
    ax.plot(steps, data["government_spending"], label="Government Spending")
    ax.set_title("Output Composition")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Value")
    ax.grid(True, alpha=0.3)
    ax.legend()
    return fig, "global_output.png"


def plot_monetary_system(global_df: pd.DataFrame) -> tuple[plt.Figure, str]:
    """Diagnostics for the core Warengeld mechanism."""

    steps, data = extract_series(
        global_df,
        "m1_proxy",
        "m2_proxy",
        "cc_exposure",
        "inventory_value_total",
        "velocity_proxy",
    )

    fig, ax_left = plt.subplots(figsize=(10, 6))
    ax_left.plot(steps, data["m1_proxy"], label="M1 proxy")
    ax_left.plot(steps, data["m2_proxy"], label="M2 proxy", linestyle="--")
    ax_left.plot(steps, data["inventory_value_total"], label="Retail inventory value", linestyle=":")
    ax_left.set_xlabel("Time Step")
    ax_left.set_ylabel("Level")

    ax_right = ax_left.twinx()
    ax_right.plot(steps, data["cc_exposure"], label="CC exposure")
    ax_right.plot(steps, data["velocity_proxy"], label="Velocity proxy", linestyle="--")
    ax_right.set_ylabel("Exposure / Velocity")

    ax_left.set_title("Money, Inventory, and Kontokorrent")
    ax_left.grid(True, alpha=0.3)

    lines = ax_left.get_lines() + ax_right.get_lines()
    labels = [line.get_label() for line in lines]
    ax_left.legend(lines, labels, loc="upper left")
    return fig, "monetary_system.png"


def plot_labor_market(global_df: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = extract_series(
        global_df,
        "employment_rate",
        "unemployment_rate",
        "bankruptcy_rate",
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(steps, data["employment_rate"], label="Employment Rate")
    ax.plot(steps, data["unemployment_rate"], label="Unemployment Rate")
    ax.plot(steps, data["bankruptcy_rate"], label="Bankruptcy Rate")
    ax.set_title("Labor & Bankruptcy Rates")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Share of Workforce")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend()
    return fig, "labor_market.png"


def plot_prices_and_wages(global_df: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, wage_series = extract_series(
        global_df,
        "average_nominal_wage",
        "average_real_wage",
    )
    _, price_series = extract_series(global_df, "price_index")
    _, inflation_series = extract_series(global_df, "inflation_rate")

    fig, ax_wage = plt.subplots(figsize=(10, 6))
    ax_wage.plot(steps, wage_series["average_nominal_wage"], label="Nominal Wage")
    ax_wage.plot(steps, wage_series["average_real_wage"], label="Real Wage")
    ax_wage.set_xlabel("Time Step")
    ax_wage.set_ylabel("Wage Level")

    ax_price = ax_wage.twinx()
    ax_price.plot(
        steps,
        price_series["price_index"],
        color="tab:purple",
        label="Price Index",
    )
    ax_price.plot(
        steps,
        inflation_series["inflation_rate"],
        color="tab:orange",
        label="Inflation Rate",
    )
    ax_price.set_ylabel("Price / Inflation")

    ax_wage.set_title("Wages, Prices & Inflation")
    ax_wage.grid(True, alpha=0.3)

    lines = ax_wage.get_lines() + ax_price.get_lines()
    labels = [line.get_label() for line in lines]
    ax_wage.legend(lines, labels, loc="upper right")
    return fig, "prices_and_wages.png"


def plot_state_budgets(state_df: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = extract_series(
        state_df,
        "environment_budget",
        "infrastructure_budget",
        "social_budget",
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(steps, data["environment_budget"], label="Environment Budget")
    ax.plot(steps, data["infrastructure_budget"], label="Infrastructure Budget")
    ax.plot(steps, data["social_budget"], label="Social Budget")
    ax.set_title("State Budget Allocation")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Budget ($)")
    ax.grid(True, alpha=0.3)
    ax.legend()
    return fig, "state_budgets.png"


def plot_company_health(company_df: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = aggregate_company_metrics(company_df)

    # Handle case where no valid columns were found
    if not steps or not data:
        fig, ax_balance = plt.subplots(figsize=(10, 6))
        ax_balance.set_title("Company Health Indicators - No Data Available")
        ax_balance.set_xlabel("Time Step")
        ax_balance.set_ylabel("Value")
        ax_balance.grid(True, alpha=0.3)
        return fig, "company_health.png"

    fig, ax_balance = plt.subplots(figsize=(10, 6))
    ax_balance.plot(steps, data["balance"], label="Aggregate Balance", color="tab:blue")
    ax_balance.set_xlabel("Time Step")
    ax_balance.set_ylabel("Balance ($)")

    ax_activity = ax_balance.twinx()
    ax_activity.plot(
        steps,
        data["rd_investment"],
        label="R&D Investment",
        color="tab:green",
        linestyle="--",
    )
    ax_activity.plot(
        steps,
        data["production_capacity"],
        label="Production Capacity",
        color="tab:red",
        linestyle=":",
    )
    ax_activity.set_ylabel("Investment / Capacity")

    ax_balance.set_title("Company Health Indicators")
    ax_balance.grid(True, alpha=0.3)

    lines = ax_balance.get_lines() + ax_activity.get_lines()
    labels = [line.get_label() for line in lines]
    ax_balance.legend(lines, labels, loc="upper left")
    return fig, "company_health.png"


def plot_household_population(household_df: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, counts = count_agents_per_step(household_df)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(steps, counts, color="tab:blue")
    ax.set_title("Active Households")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("# Households")
    ax.grid(True, alpha=0.3)
    return fig, "households_count.png"


def plot_company_population(company_df: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, counts = count_agents_per_step(company_df)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(steps, counts, color="tab:green")
    ax.set_title("Active Companies")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("# Companies")
    ax.grid(True, alpha=0.3)
    return fig, "companies_count.png"


PLOT_SPECS: list[tuple[str, PlotFunc]] = [
    ("global", plot_global_output),
    ("global", plot_monetary_system),
    ("global", plot_labor_market),
    ("global", plot_prices_and_wages),
    ("state", plot_state_budgets),
    ("company", plot_company_health),
    ("household", plot_household_population),
    ("company", plot_company_population),
]


def main() -> None:
    args = parse_args()
    metrics_dir = Path(args.metrics_dir)
    plots_dir = Path(args.plots_dir)

    run_id = args.run_id or detect_latest_run_id(metrics_dir)

    run_dir = plots_dir / run_id
    latest_dir = ensure_dirs(run_dir)

    global_rows = load_csv_rows(metrics_dir / f"global_metrics_{run_id}.csv")
    state_rows = load_csv_rows(
        metrics_dir / f"state_metrics_{run_id}.csv", skip_fields={"agent_id"}
    )
    company_rows = load_csv_rows(
        metrics_dir / f"company_metrics_{run_id}.csv",
        skip_fields={"agent_id"},
    )
    household_rows = load_csv_rows(
        metrics_dir / f"household_metrics_{run_id}.csv",
        skip_fields={"agent_id"},
    )

    data_by_scope = {
        "global": global_rows,
        "state": state_rows,
        "company": company_rows,
        "household": household_rows,
    }

    figures: list[plt.Figure] = []
    axes: list[plt.Axes] = []
    for scope, plot_func in PLOT_SPECS:
        fig, filename = plot_func(data_by_scope[scope])
        figures.append(fig)
        axes.extend(fig.axes)
        save_figure(fig, filename, run_dir, latest_dir, close_figure=not args.show)

    if args.show:
        if args.link_cursor:
            on_move = add_linked_cursor(axes)
            for fig in figures:
                fig.canvas.mpl_connect("motion_notify_event", on_move)
        plt.show(block=True)


def add_linked_cursor(axes: list[plt.Axes]) -> Callable[[object], None]:
    lines = [ax.axvline(color="gray", lw=0.8, alpha=0.5, visible=False) for ax in axes]
    canvases = {ax.figure.canvas for ax in axes}

    def on_move(event):
        if event.inaxes is None or event.xdata is None:
            for line in lines:
                line.set_visible(False)
        else:
            # event.xdata is a single float, but set_xdata usually expects a sequence
            # for a vertical line, however, axvline objects (Line2D) are special.
            # The error "x must be a sequence" suggests we are treating it as a general Line2D
            # where xdata must be [x0, x1].
            # But axvline sets x position via transform. Let's try setting it as a list of 2 identical points.
            for line in lines:
                line.set_xdata([event.xdata, event.xdata])
                line.set_visible(True)
        
        for canvas in canvases:
            canvas.draw_idle()

    return on_move


if __name__ == "__main__":
    main()
