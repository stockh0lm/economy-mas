"""Base types and constants for the metrics package."""

from typing import Any, Protocol, TypedDict, Union

# Type aliases
TimeStep = int
ValueType = Union[float, int, str, bool, None]
MetricDict = dict[str, Any]
TimeSeriesDict = dict[TimeStep, MetricDict]

# Constants
MIN_GLOBAL_METRICS_POINTS = 10


class EconomicAgent(Protocol):
    """Protocol defining the minimum required attributes for tracked agents"""

    unique_id: str


class TypeDefinitions:
    """Shared type definitions for metrics."""

    AgentID = str
    TimeStep = int
    ValueType = Union[float, int, str, bool, None]
    MetricName = str
    MetricDict = dict[str, Any]
    TimeSeriesDict = dict[int, dict[str, Any]]
    AgentMetricsDict = dict[str, dict[int, dict[str, Any]]]

    EconomicAgent = EconomicAgent


class MetricConfig(TypedDict):
    """Configuration for a single tracked metric."""

    enabled: bool
    display_name: str
    unit: str
    aggregation: str
    critical_threshold: Any
