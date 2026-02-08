"""Base types and constants for the metrics package."""

from typing import Any, Dict, Protocol, TypeVar, Union

# Type aliases
TimeStep = int
ValueType = Union[float, int, str, bool, None]
MetricDict = Dict[str, Any]
TimeSeriesDict = Dict[TimeStep, MetricDict]

# Constants
MIN_GLOBAL_METRICS_POINTS = 5


class EconomicAgent(Protocol):
    """Protocol defining the minimum required attributes for tracked agents"""

    unique_id: str


class TypeDefinitions:
    """Shared type definitions for metrics."""

    AgentID = str
    TimeStep = int
    ValueType = Union[float, int, str, bool, None]
    MetricName = str
    MetricDict = Dict[str, Any]
    TimeSeriesDict = Dict[int, Dict[str, Any]]
    AgentMetricsDict = Dict[str, Dict[int, Dict[str, Any]]]

    EconomicAgent = EconomicAgent


class MetricConfig(Protocol):
    """Protocol for metric configuration dictionary entries"""

    enabled: bool
    display_name: str
    unit: str
    aggregation: str
    critical_threshold: Any
