"""Economic metrics collection and analysis system for the simulation.

This module tracks key economic indicators across different agent types,
calculates aggregate statistics, and provides data for visualization.

DEPRECATED: This file is a thin compatibility wrapper for backward compatibility.
All functionality has been refactored into the metrics package.
"""

# Re-export everything from the new metrics package
from metrics import (
    MIN_GLOBAL_METRICS_POINTS,
    AgentID,
    AgentMetricsDict,
    EconomicAgent,
    MetricConfig,
    MetricDict,
    MetricName,
    MetricsCollector,
    TimeSeriesDict,
    TimeStep,
    ValueType,
    analyze_economic_cycles,
    apply_sight_decay,
    get_latest_macro_snapshot,
    get_metrics_collector,
    metrics_collector,
    set_metrics_collector,
)
from metrics.analyzer import EconomicCycleSnapshot

# Aliases for backward compatibility
from metrics.calculator import (
    FinancialMarketMetricsSource,
    LaborMarketMetricsSource,
    _calculate_gini_coefficient as calculate_gini_coefficient,
)

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
