"""Standardized logging utilities for the simulation."""

import json
import time
from typing import Any, Dict, Literal, Optional

from logger import log

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class SimulationLogger:
    """
    Standardized logger for simulation components.

    Provides structured logging with context and performance tracking.
    """

    def __init__(self, component_name: str, agent_id: Optional[str] = None):
        """
        Initialize simulation logger.

        Args:
            component_name: Name of the component (e.g., "Company", "Household")
            agent_id: Optional agent identifier for context
        """
        self.component_name = component_name
        self.agent_id = agent_id
        self._start_time = time.time()
        self._log_count = 0

    def _format_message(self, message: str, level: LogLevel) -> str:
        """Format log message with context."""
        parts = []

        if self.agent_id:
            parts.append(f"[{self.component_name}:{self.agent_id}]")
        else:
            parts.append(f"[{self.component_name}]")

        parts.append(f"[{level}]")
        parts.append(message)

        return " ".join(parts)

    def debug(self, message: str, data: Optional[Dict] = None) -> None:
        """Log debug message."""
        self._log("DEBUG", message, data)

    def info(self, message: str, data: Optional[Dict] = None) -> None:
        """Log info message."""
        self._log("INFO", message, data)

    def warning(self, message: str, data: Optional[Dict] = None) -> None:
        """Log warning message."""
        self._log("WARNING", message, data)

    def error(self, message: str, data: Optional[Dict] = None) -> None:
        """Log error message."""
        self._log("ERROR", message, data)

    def critical(self, message: str, data: Optional[Dict] = None) -> None:
        """Log critical message."""
        self._log("CRITICAL", message, data)

    def _log(self, level: LogLevel, message: str, data: Optional[Dict] = None) -> None:
        """Internal logging method."""
        formatted_message = self._format_message(message, level)
        log(formatted_message, level=level)

        self._log_count += 1

        # Log structured data if provided
        if data:
            try:
                data_str = json.dumps(data)
                log(f"DATA: {data_str}", level=level)
            except Exception:
                log(f"DATA: (unserializable data)", level=level)

    def log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Log a structured event with timestamp and context.

        Args:
            event_type: Type of event
            data: Event data dictionary
        """
        event_data = {
            "timestamp": time.time(),
            "component": self.component_name,
            "agent_id": self.agent_id,
            "event_type": event_type,
            "data": data,
        }

        log_message = f"EVENT: {event_type}"
        if self.agent_id:
            log_message += f" (Agent: {self.agent_id})"

        self.info(log_message, event_data)

    def log_performance(
        self, operation: str, duration: float, details: Optional[Dict] = None
    ) -> None:
        """
        Log performance metrics.

        Args:
            operation: Name of operation being measured
            duration: Duration in seconds
            details: Additional performance details
        """
        perf_data = {
            "operation": operation,
            "duration_seconds": duration,
            "component": self.component_name,
            "agent_id": self.agent_id,
        }

        if details:
            perf_data.update(details)

        self.debug(f"PERF: {operation} took {duration:.4f}s", perf_data)

    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics."""
        return {
            "component": self.component_name,
            "agent_id": self.agent_id,
            "log_count": self._log_count,
            "uptime_seconds": time.time() - self._start_time,
        }


class AgentLogger(SimulationLogger):
    """
    Agent-specific logger with additional agent context.
    """

    def __init__(self, agent_id: str, agent_type: str):
        """
        Initialize agent logger.

        Args:
            agent_id: Agent identifier
            agent_type: Type of agent
        """
        super().__init__(agent_type, agent_id)
        self.agent_type = agent_type

    def log_state_change(
        self, old_state: str, new_state: str, reason: Optional[str] = None
    ) -> None:
        """
        Log agent state change.

        Args:
            old_state: Previous state
            new_state: New state
            reason: Optional reason for change
        """
        data = {"old_state": old_state, "new_state": new_state, "reason": reason}
        self.info(f"State change: {old_state} -> {new_state}", data)

    def log_financial_transaction(
        self, transaction_type: str, amount: float, balance: float
    ) -> None:
        """
        Log financial transaction.

        Args:
            transaction_type: Type of transaction
            amount: Transaction amount
            balance: Resulting balance
        """
        data = {"transaction_type": transaction_type, "amount": amount, "balance": balance}
        self.debug(f"Financial transaction: {transaction_type} {amount:.2f}", data)


class SystemLogger(SimulationLogger):
    """
    System-level logger for infrastructure components.
    """

    def __init__(self, system_name: str):
        """
        Initialize system logger.

        Args:
            system_name: Name of the system component
        """
        super().__init__(system_name)

    def log_system_metric(self, metric_name: str, value: Any, unit: Optional[str] = None) -> None:
        """
        Log system metric.

        Args:
            metric_name: Name of metric
            value: Metric value
            unit: Optional unit of measurement
        """
        data = {"metric": metric_name, "value": value, "unit": unit}
        self.debug(f"System metric: {metric_name} = {value}{f' {unit}' if unit else ''}", data)


def create_agent_logger(agent_id: str, agent_type: str) -> AgentLogger:
    """
    Create an agent-specific logger.

    Args:
        agent_id: Agent identifier
        agent_type: Type of agent

    Returns:
        Configured AgentLogger instance
    """
    return AgentLogger(agent_id, agent_type)


def create_system_logger(system_name: str) -> SystemLogger:
    """
    Create a system-specific logger.

    Args:
        system_name: Name of system component

    Returns:
        Configured SystemLogger instance
    """
    return SystemLogger(system_name)
