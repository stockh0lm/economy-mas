"""Exporter module - CSV and pickle export functionality."""

from datetime import datetime
from pathlib import Path
from typing import Protocol


class MetricsCollectorProtocol(Protocol):
    """Protocol for metrics collector to allow duck typing"""

    global_metrics: dict
    household_metrics: dict
    company_metrics: dict
    retailer_metrics: dict
    bank_metrics: dict
    state_metrics: dict
    market_metrics: dict
    export_path: Path
    household_metrics_df = None
    company_metrics_df = None
    retailer_metrics_df = None
    bank_metrics_df = None
    state_metrics_df = None
    market_metrics_df = None
    global_metrics_df = None


def export_metrics(collector):
    """Persist metrics to CSV (JSON export removed for performance)."""
    export_time_series_to_csv(collector)


def export_time_series_to_csv(collector):
    """Export time series of metrics to structured CSV files using pandas."""
    from logger import log

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    exports = [
        _export_global_metrics_df(collector, timestamp),
        _export_agent_metrics_df(
            collector, collector.household_metrics, "household_metrics", timestamp
        ),
        _export_agent_metrics_df(
            collector, collector.company_metrics, "company_metrics", timestamp
        ),
        _export_agent_metrics_df(
            collector, collector.retailer_metrics, "retailer_metrics", timestamp
        ),
        _export_agent_metrics_df(collector, collector.bank_metrics, "bank_metrics", timestamp),
        _export_agent_metrics_df(collector, collector.state_metrics, "state_metrics", timestamp),
        _export_agent_metrics_df(collector, collector.market_metrics, "market_metrics", timestamp),
    ]

    written = [path for path in exports if path is not None]
    if written:
        log(
            "MetricsCollector: Exported CSV metrics: " + ", ".join(str(p.name) for p in written),
            level="INFO",
        )
    else:
        log("MetricsCollector: No metrics available for CSV export", level="WARNING")


def _export_global_metrics_df(collector, timestamp):
    if not collector.global_metrics:
        return None

    import pandas as pd

    rows = []
    for step, metrics in collector.global_metrics.items():
        row = {"time_step": int(step)}
        row.update(metrics)
        rows.append(row)

    df = pd.DataFrame.from_records(rows)
    if not df.empty and "time_step" in df.columns:
        df = df.sort_values("time_step")

    output_file = collector.export_path / f"global_metrics_{timestamp}.csv"
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        df.to_csv(output_file, index=False)
    collector.global_metrics_df = df
    return output_file


def _export_agent_metrics_df(
    collector,
    agent_metrics,
    filename_prefix,
    timestamp,
):
    if not agent_metrics:
        return None

    import pandas as pd

    rows = []
    for agent_id, time_series in agent_metrics.items():
        for step, metrics in time_series.items():
            row = {"time_step": int(step), "agent_id": str(agent_id)}
            row.update(metrics)
            rows.append(row)

    if not rows:
        return None

    df = pd.DataFrame.from_records(rows)
    if not df.empty and "time_step" in df.columns:
        df = df.sort_values(["time_step", "agent_id"])

    output_file = collector.export_path / f"{filename_prefix}_{timestamp}.csv"
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        df.to_csv(output_file, index=False)

    if filename_prefix.startswith("household"):
        collector.household_metrics_df = df
    elif filename_prefix.startswith("company"):
        collector.company_metrics_df = df
    elif filename_prefix.startswith("retailer"):
        collector.retailer_metrics_df = df
    elif filename_prefix.startswith("bank"):
        collector.bank_metrics_df = df
    elif filename_prefix.startswith("state"):
        collector.state_metrics_df = df
    elif filename_prefix.startswith("market"):
        collector.market_metrics_df = df

    return output_file
