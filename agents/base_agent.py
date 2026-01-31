"""Enhanced base agent class with common functionality and metrics support."""

from typing import Any, ClassVar, Final
from agents.protocols import AgentWithBalance, AgentWithImpact, HasUniqueID
from agents.logging_utils import create_agent_logger
from config import SimulationConfig, CONFIG_MODEL
from logger import log

class BaseAgent(HasUniqueID):
    """Enhanced base agent class providing common functionality for all agents."""

    def __init__(self, unique_id: str, config: SimulationConfig | None = None, *, region_id: str | None = None) -> None:
        """
        Initialize a base agent with common attributes.

        Args:
            unique_id: Unique identifier for the agent
            config: Optional simulation configuration
        """
        self.unique_id: str = unique_id
        self.config: SimulationConfig = config or CONFIG_MODEL

        # Geographic partitioning ("Hausbanken"/regional markets).
        # Keep this as a simple string tag so the core model stays lightweight.
        self.region_id: str = str(region_id) if region_id is not None else "region_0"

        # Initialize enhanced logging system
        self._logger = create_agent_logger(unique_id, self.__class__.__name__)

        # Standard metrics collection
        self._metrics: dict[str, Any] = {}
        self._performance_metrics: dict[str, float] = {}

        # Agent state tracking
        self.active: bool = True
        self.created_at_step: int | None = None
        self.last_updated_step: int | None = None

    def step(self, current_step: int) -> None:
        """
        Base step method that should be overridden by subclasses.

        Args:
            current_step: Current simulation step number
        """
        self.last_updated_step = current_step
        if self.created_at_step is None:
            self.created_at_step = current_step

    def log_metric(self, name: str, value: Any, category: str = "default") -> None:
        """
        Log a metric for this agent.

        Args:
            name: Metric name
            value: Metric value
            category: Metric category (default, performance, financial, etc.)
        """
        if category == "performance":
            self._performance_metrics[name] = float(value)
        else:
            self._metrics[name] = value

    def get_metrics(self) -> dict[str, Any]:
        """
        Get all collected metrics for this agent.

        Returns:
            Dictionary containing all agent metrics
        """
        return {
            "basic": self._metrics,
            "performance": self._performance_metrics,
            "state": {
                "active": self.active,
                "created_at_step": self.created_at_step,
                "last_updated_step": self.last_updated_step
            }
        }

    def get_metric(self, name: str, category: str = "default") -> Any:
        """
        Get a specific metric value.

        Args:
            name: Metric name
            category: Metric category

        Returns:
            Metric value or None if not found
        """
        if category == "performance":
            return self._performance_metrics.get(name)
        return self._metrics.get(name)

    def reset_metrics(self) -> None:
        """Reset all collected metrics."""
        self._metrics.clear()
        self._performance_metrics.clear()

    def deactivate(self) -> None:
        """Mark agent as inactive."""
        self.active = False
        log(f"Agent {self.unique_id} deactivated", level="INFO")

    def activate(self) -> None:
        """Mark agent as active."""
        self.active = True
        log(f"Agent {self.unique_id} activated", level="INFO")

    def __str__(self) -> str:
        """String representation of the agent."""
        return f"{self.__class__.__name__}({self.unique_id})"

    def __repr__(self) -> str:
        """Detailed string representation of the agent."""
        return f"{self.__class__.__name__}(unique_id={self.unique_id}, active={self.active})"

    def get_config_value(self, path: str, default: Any = None) -> Any:
        """
        Safely get a configuration value by path.

        Args:
            path: Dot-separated path to config value (e.g., 'company.base_wage')
            default: Default value if path not found

        Returns:
            Configuration value or default
        """
        try:
            keys = path.split('.')
            value = self.config
            for key in keys:
                value = getattr(value, key, default)
                if value is None:
                    return default
            return value
        except (AttributeError, KeyError):
            return default
