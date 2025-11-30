"""Generate Matplotlib plots for the latest simulation metrics export."""
from __future__ import annotations

import argparse
import csv
import shutil
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path

import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
METRICS_DIR = REPO_ROOT / "output" / "metrics"
PLOTS_DIR = REPO_ROOT / "output" / "plots"

PlotFunc = Callable[[list[dict[str, object]]], tuple[plt.Figure, str]]


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


def load_csv_rows(path: Path, skip_fields: Iterable[str] | None = None) -> list[dict[str, object]]:
    skip_fields = set(skip_fields or [])
    rows: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            parsed: dict[str, object] = {}
            for key, value in raw.items():
                if key == "time_step":
                    parsed[key] = int(value)
                elif key in skip_fields:
                    parsed[key] = value
                else:
                    parsed[key] = try_float(value)
            rows.append(parsed)
    return rows


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


def save_figure(fig: plt.Figure, filename: str, run_dir: Path, latest_dir: Path) -> None:
    target = run_dir / filename
    fig.savefig(target, dpi=150, bbox_inches="tight")
    shutil.copy2(target, latest_dir / filename)
    plt.close(fig)


def extract_series(
    rows: list[dict[str, object]], *columns: str
) -> tuple[list[int], dict[str, list[float]]]:
    ordered = sorted(rows, key=lambda row: int(row["time_step"]))
    steps = [int(row["time_step"]) for row in ordered]
    series: dict[str, list[float]] = {}
    for column in columns:
        series[column] = [float(row.get(column) or 0.0) for row in ordered]
    return steps, series


def aggregate_company_metrics(
    rows: list[dict[str, object]]
) -> tuple[list[int], dict[str, list[float]]]:
    totals: defaultdict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        step = int(row["time_step"])
        for key in ("balance", "rd_investment", "production_capacity"):
            value = row.get(key)
            if isinstance(value, (int, float)) and value is not None:
                totals[step][key] += float(value)
    steps = sorted(totals)
    aggregated = {
        key: [totals[step].get(key, 0.0) for step in steps]
        for key in ("balance", "rd_investment", "production_capacity")
    }
    return steps, aggregated


def count_agents_per_step(rows: list[dict[str, object]]) -> tuple[list[int], list[int]]:
    counts: defaultdict[int, set[str]] = defaultdict(set)
    for row in rows:
        counts[int(row["time_step"])].add(str(row.get("agent_id", "")))
    steps = sorted(counts)
    values = [len(counts[step]) for step in steps]
    return steps, values


def plot_global_output(global_rows: list[dict[str, object]]) -> tuple[plt.Figure, str]:
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


def plot_labor_market(global_rows: list[dict[str, object]]) -> tuple[plt.Figure, str]:
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


def plot_prices_and_wages(global_rows: list[dict[str, object]]) -> tuple[plt.Figure, str]:
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


def plot_state_budgets(state_rows: list[dict[str, object]]) -> tuple[plt.Figure, str]:
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


def plot_company_health(company_rows: list[dict[str, object]]) -> tuple[plt.Figure, str]:
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


def plot_household_population(household_rows: list[dict[str, object]]) -> tuple[plt.Figure, str]:
    steps, counts = count_agents_per_step(household_rows)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(steps, counts, color="tab:blue")
    ax.set_title("Active Households")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("# Households")
    ax.grid(True, alpha=0.3)
    return fig, "households_count.png"


def plot_company_population(company_rows: list[dict[str, object]]) -> tuple[plt.Figure, str]:
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
        save_figure(fig, filename, run_dir, latest_dir)

    if args.show:
        if args.link_cursor:
            on_move = add_linked_cursor(axes)
            for fig in figures:
                fig.canvas.mpl_connect("motion_notify_event", on_move)
        plt.show(block=True)


def add_linked_cursor(axes: list[plt.Axes]) -> Callable[[object], None]:
    lines = [ax.axvline(color="gray", lw=0.8, alpha=0.5, visible=False) for ax in axes]

    def on_move(event):
        if event.inaxes is None or event.xdata is None:
            for line in lines:
                line.set_visible(False)
            event.canvas.draw_idle()
            return
        for line in lines:
            line.set_xdata(event.xdata)
            line.set_visible(True)
        event.canvas.draw_idle()

    return on_move
