"""Metrics package for economic simulation analysis."""

from .analyzer import (
    _apply_aggregation,
    _check_critical_thresholds,
    aggregate_metrics,
    analyze_economic_cycles,
    apply_sight_decay,
    get_latest_macro_snapshot,
)
from .base import (
    MIN_GLOBAL_METRICS_POINTS,
    EconomicAgent,
    MetricConfig,
    MetricDict,
    TimeSeriesDict,
    TimeStep,
    TypeDefinitions,
    ValueType,
)
from .calculator import (
    _bankruptcy_metrics,
    _distribution_metrics,
    _employment_metrics,
    _environmental_metrics,
    _global_activity_metrics,
    _global_money_metrics,
    _government_metrics,
    _investment_metrics,
    _price_dynamics,
    _wage_metrics,
)
from .collector import MetricsCollector
from .exporter import (
    _export_agent_metrics_df,
    _export_global_metrics_df,
    export_metrics,
)

# Re-export type aliases from TypeDefinitions for backward compatibility
AgentID = TypeDefinitions.AgentID
MetricName = TypeDefinitions.MetricName
AgentMetricsDict = TypeDefinitions.AgentMetricsDict

__all__ = [
    "MetricsCollector",
    "apply_sight_decay",
    "analyze_economic_cycles",
    "get_latest_macro_snapshot",
    "aggregate_metrics",
    "export_metrics",
    "_check_critical_thresholds",
    "_apply_aggregation",
    "_global_money_metrics",
    "_price_dynamics",
    "_distribution_metrics",
    "_wage_metrics",
    "_environmental_metrics",
    "_employment_metrics",
    "_investment_metrics",
    "_bankruptcy_metrics",
    "_government_metrics",
    "_global_activity_metrics",
    "_export_global_metrics_df",
    "_export_agent_metrics_df",
    "MIN_GLOBAL_METRICS_POINTS",
    "metrics_collector",
    "get_metrics_collector",
    "set_metrics_collector",
    "EconomicAgent",
    "MetricConfig",
    "MetricDict",
    "TimeSeriesDict",
    "TimeStep",
    "ValueType",
    "AgentID",
    "MetricName",
    "AgentMetricsDict",
    "TypeDefinitions",
]

metrics_collector = MetricsCollector()


def get_metrics_collector():
    """Get or create the singleton metrics collector instance."""
    global metrics_collector
    if metrics_collector is None:
        from config import CONFIG_MODEL

        metrics_collector = MetricsCollector(CONFIG_MODEL)
    return metrics_collector


def set_metrics_collector(collector):
    """Set the singleton metrics collector instance."""
    global metrics_collector
    metrics_collector = collector
