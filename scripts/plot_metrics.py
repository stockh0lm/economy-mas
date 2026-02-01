"""Generate Matplotlib plots for the latest simulation metrics export."""
from __future__ import annotations

import argparse
import csv
import shutil
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

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
    """Load a metrics CSV into a DataFrame.

    Tests (and downstream plotting helpers) expect a pandas.DataFrame.
    """

    skip_fields = set(skip_fields or [])
    parsed_rows: list[dict[str, object]] = []

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            parsed: dict[str, object] = {}
            for key, value in raw.items():
                if key == "time_step":
                    parsed[key] = int(value) if value not in (None, "") else 0
                elif key in skip_fields:
                    parsed[key] = value
                else:
                    parsed[key] = try_float(value)
            parsed_rows.append(parsed)

    return pd.DataFrame(parsed_rows)




def extract_series(
    rows: pd.DataFrame, *columns: str
) -> tuple[list[int], dict[str, list[float]]]:
    """Extract time series data using optimized pandas operations.

    Args:
        rows: DataFrame containing the metrics data
        *columns: Column names to extract as series

    Returns:
        Tuple of (time_steps, series_data) where series_data is a dict mapping
        column names to lists of float values
    """
    # Vectorized sorting and type conversion
    df = rows.sort_values('time_step')
    steps = df['time_step'].astype(int).tolist()

    # Vectorized extraction with NaN handling
    series = {}
    for column in columns:
        if column in df.columns:
            # Fill NaN values with 0.0 and convert to float - all vectorized
            series[column] = df[column].fillna(0.0).astype(float).tolist()
        else:
            # If column doesn't exist, return empty list
            series[column] = []

    return steps, series


def aggregate_company_metrics(
    rows: pd.DataFrame
) -> tuple[list[int], dict[str, list[float]]]:
    """Aggregate company metrics using optimized pandas groupby operations.

    Args:
        rows: DataFrame containing company metrics data

    Returns:
        Tuple of (time_steps, aggregated_data) where aggregated_data contains
        sums for balance, rd_investment, and production_capacity
    """
    # Check which columns are available
    available_columns = ['balance', 'rd_investment', 'production_capacity']
    existing_columns = [col for col in available_columns if col in rows.columns]

    if not existing_columns:
        # No company metrics columns found, return empty result
        return [], {'balance': [], 'rd_investment': [], 'production_capacity': []}

    # Vectorized groupby and aggregation
    df = rows.copy()
    df['time_step'] = df['time_step'].astype(int)
    result = df.groupby('time_step')[existing_columns].sum().fillna(0.0)

    steps = sorted(result.index.tolist())

    # Initialize all expected columns with empty lists or data
    aggregated = {
        'balance': result.get('balance', pd.Series([], dtype=float)).tolist(),
        'rd_investment': result.get('rd_investment', pd.Series([], dtype=float)).tolist(),
        'production_capacity': result.get('production_capacity', pd.Series([], dtype=float)).tolist()
    }

    return steps, aggregated


def count_agents_per_step(rows: pd.DataFrame) -> tuple[list[int], list[int]]:
    """Count unique agents per time step using optimized pandas operations.

    Args:
        rows: DataFrame containing agent data with time_step and agent_id

    Returns:
        Tuple of (time_steps, agent_counts) where agent_counts contains the number
        of unique agents at each time step
    """
    # Vectorized groupby and unique counting
    df = rows.copy()
    df['time_step'] = df['time_step'].astype(int)
    result = df.groupby('time_step')['agent_id'].nunique()

    steps = sorted(result.index.tolist())
    values = result.tolist()

    return steps, values


def plot_global_output(global_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = extract_series(
        global_rows,
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


def plot_monetary_system(global_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    """Diagnostics for the core Warengeld mechanism."""

    steps, data = extract_series(
        global_rows,
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


def plot_labor_market(global_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = extract_series(
        global_rows,
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


def plot_prices_and_wages(global_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, wage_series = extract_series(
        global_rows,
        "average_nominal_wage",
        "average_real_wage",
    )
    _, price_series = extract_series(global_rows, "price_index")
    _, inflation_series = extract_series(global_rows, "inflation_rate")

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


def plot_state_budgets(state_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = extract_series(
        state_rows,
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


def plot_company_health(company_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, data = aggregate_company_metrics(company_rows)
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


def plot_household_population(household_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, counts = count_agents_per_step(household_rows)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(steps, counts, color="tab:blue")
    ax.set_title("Active Households")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("# Households")
    ax.grid(True, alpha=0.3)
    return fig, "households_count.png"


def plot_company_population(company_rows: pd.DataFrame) -> tuple[plt.Figure, str]:
    steps, counts = count_agents_per_step(company_rows)
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


def ensure_dirs(directory: Path) -> Path:
    """Ensure that the specified directory exists, creating it if necessary.

    Args:
        directory: Path object pointing to the directory to ensure exists

    Returns:
        The same Path object for convenience
    """
    directory.mkdir(parents=True, exist_ok=True)
    return directory

def save_figure(fig: plt.Figure, filename: str, run_dir: Path, latest_dir: Path, close_figure: bool = True) -> None:
    """Save a matplotlib figure to a file in the specified directory.

    Args:
        fig: The matplotlib figure to save
        filename: The filename for the saved figure
        run_dir: The base directory where figures should be saved
        latest_dir: The specific run directory (should be same as run_dir in current usage)
        close_figure: Whether to close the figure after saving
    """
    save_path = latest_dir / filename
    fig.savefig(save_path, bbox_inches='tight', dpi=150)
    if close_figure:
        plt.close(fig)

def try_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


if __name__ == "__main__":
    main()
