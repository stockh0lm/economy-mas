"""Economic metrics collection and analysis system for the simulation.

This module tracks key economic indicators across different agent types,
calculates aggregate statistics, and provides data for visualization.

DEPRECATED: This file is a thin compatibility wrapper for backward compatibility.
All functionality has been refactored into the metrics package.
"""

# Re-export everything from the new metrics package
from metrics import (
    AgentMetricsDict,
    AgentID,
    EconomicAgent,
    MetricConfig,
    MetricDict,
    MetricName,
    MetricsCollector,
    MIN_GLOBAL_METRICS_POINTS,
    TimeSeriesDict,
    TimeStep,
    ValueType,
    apply_sight_decay,
    analyze_economic_cycles,
    get_latest_macro_snapshot,
    metrics_collector,
    get_metrics_collector,
    set_metrics_collector,
)

# Aliases for backward compatibility
from metrics.calculator import _calculate_gini_coefficient as calculate_gini_coefficient
from metrics.calculator import LaborMarketMetricsSource, FinancialMarketMetricsSource
from metrics.analyzer import EconomicCycleSnapshot

detect_economic_cycles = analyze_economic_cycles  # Alias for backward compatibility

__all__ = [
    "MetricsCollector",
    "metrics_collector",
    "apply_sight_decay",
    "detect_economic_cycles",
    "get_latest_macro_snapshot",
    "calculate_gini_coefficient",
    "AgentID",
    "TimeStep",
    "ValueType",
    "MetricName",
    "MetricDict",
    "TimeSeriesDict",
    "AgentMetricsDict",
    "EconomicAgent",
    "MetricConfig",
    "LaborMarketMetricsSource",
    "FinancialMarketMetricsSource",
    "EconomicCycleSnapshot",
    "MIN_GLOBAL_METRICS_POINTS",
    "get_metrics_collector",
    "set_metrics_collector",
]
