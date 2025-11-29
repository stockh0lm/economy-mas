# metrics.py
"""
Economic metrics collection and analysis system for the simulation.

This module tracks key economic indicators across different agent types,
calculates aggregate statistics, and provides data for visualization.
"""

import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Set, TypedDict

from agents.company_agent import Company
from agents.household_agent import Household
from config import CONFIG
from logger import log

MIN_GLOBAL_METRICS_POINTS = 10  # Minimal steps required for cycle detection

# Type definitions for improved readability
AgentID = str
TimeStep = int
ValueType = float | int | bool | str
MetricName = str
MetricDict = Dict[MetricName, ValueType]
TimeSeriesDict = Dict[TimeStep, MetricDict]
AgentMetricsDict = Dict[AgentID, TimeSeriesDict]


class EconomicAgent(Protocol):
    """Protocol defining the minimum required attributes for tracked agents"""

    unique_id: str


class MetricConfig(TypedDict):
    """Configuration settings for a single metric"""

    enabled: bool  # Whether metric is enabled
    display_name: str  # Human-readable name for plots/reports
    unit: str  # Measurement unit (e.g., "$", "%", "units")
    aggregation: str  # How to aggregate across agents ("sum", "mean", "median", "min", "max")
    critical_threshold: Optional[float]  # Value that triggers alerts if crossed


class MetricsCollector:
    """
    Collects, aggregates, and exports economic metrics from simulation agents.

    Tracks data for multiple agent types over time and provides analysis functions
    to evaluate economic performance of the simulation.
    """

    bank_metrics: AgentMetricsDict
    household_metrics: AgentMetricsDict
    company_metrics: AgentMetricsDict
    state_metrics: AgentMetricsDict
    market_metrics: AgentMetricsDict
    global_metrics: TimeSeriesDict
    registered_households: Set[str]
    registered_companies: Set[str]
    registered_banks: Set[str]
    metrics_config: Dict[MetricName, MetricConfig]
    export_path: Path
    latest_labor_metrics: dict[str, float]
    latest_global_metrics: dict[str, float]

    def __init__(self):
        """Initialize the metrics collector."""
        self.bank_metrics: AgentMetricsDict = {}
        self.household_metrics: AgentMetricsDict = {}
        self.company_metrics: AgentMetricsDict = {}
        self.state_metrics: AgentMetricsDict = {}
        self.market_metrics: AgentMetricsDict = {}
        self.global_metrics: TimeSeriesDict = {}
        self.registered_households: Set[str] = set()
        self.registered_companies: Set[str] = set()
        self.registered_banks: Set[str] = set()
        self.metrics_config: Dict[MetricName, MetricConfig] = {}
        self.export_path: Path = Path(CONFIG.get("metrics_export_path", "output/metrics"))
        self.latest_labor_metrics = {}
        self.latest_global_metrics = {}
        self.__post_init__()

    def __post_init__(self) -> None:
        """Initialize with configuration from CONFIG"""
        self.metrics_config = CONFIG.get("metrics_config", {})
        self.setup_default_metrics_config()

        # Create export directory if it doesn't exist
        self.export_path.mkdir(parents=True, exist_ok=True)

    def setup_default_metrics_config(self) -> None:
        """Set up default configuration for tracked metrics if not specified in CONFIG"""
        default_metrics = {
            # Household metrics
            "income": {
                "enabled": True,
                "display_name": "Household Income",
                "unit": "$",
                "aggregation": "mean",
                "critical_threshold": None,
            },
            "savings": {
                "enabled": True,
                "display_name": "Household Savings",
                "unit": "$",
                "aggregation": "sum",
                "critical_threshold": None,
            },
            "consumption": {
                "enabled": True,
                "display_name": "Consumption",
                "unit": "$",
                "aggregation": "sum",
                "critical_threshold": None,
            },
            "employed": {
                "enabled": True,
                "display_name": "Employment Rate",
                "unit": "Anteil",
                "aggregation": "mean",
                "critical_threshold": 0.6,  # Alert if employment falls below 60%
            },
            # Company metrics
            "production_capacity": {
                "enabled": True,
                "display_name": "Production Capacity",
                "unit": "units",
                "aggregation": "sum",
                "critical_threshold": None,
            },
            "balance": {
                "enabled": True,
                "display_name": "Company Balance",
                "unit": "$",
                "aggregation": "sum",
                "critical_threshold": None,
            },
            "employees": {
                "enabled": True,
                "display_name": "Total Employment",
                "unit": "workers",
                "aggregation": "sum",
                "critical_threshold": None,
            },
            "rd_investment": {
                "enabled": True,
                "display_name": "R&D Investment",
                "unit": "$",
                "aggregation": "sum",
                "critical_threshold": None,
            },
            "innovation_index": {
                "enabled": True,
                "display_name": "Innovation Index",
                "unit": "",
                "aggregation": "mean",
                "critical_threshold": None,
            },
            "bankruptcy_rate": {
                "enabled": True,
                "display_name": "Bankruptcy Rate",
                "unit": "Anteil",
                "aggregation": "value",
                "critical_threshold": 0.1,  # Alert if bankruptcy exceeds 10%
            },
            # Bank metrics
            "liquidity": {
                "enabled": True,
                "display_name": "Banking Liquidity",
                "unit": "$",
                "aggregation": "sum",
                "critical_threshold": None,
            },
            "total_credit": {
                "enabled": True,
                "display_name": "Outstanding Credit",
                "unit": "$",
                "aggregation": "sum",
                "critical_threshold": None,
            },
            # State metrics
            "tax_revenue": {
                "enabled": True,
                "display_name": "Tax Revenue",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "infrastructure_budget": {
                "enabled": True,
                "display_name": "Infrastructure Budget",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "social_budget": {
                "enabled": True,
                "display_name": "Social Budget",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "environment_budget": {
                "enabled": True,
                "display_name": "Environment Budget",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
            # Global metrics
            "gini_coefficient": {
                "enabled": True,
                "display_name": "Gini Coefficient",
                "unit": "",
                "aggregation": "value",
                "critical_threshold": 0.5,  # Alert if wealth inequality exceeds 0.5
            },
            "total_money_supply": {
                "enabled": True,
                "display_name": "Money Supply",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "total_environmental_impact": {
                "enabled": True,
                "display_name": "Environmental Impact",
                "unit": "",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "employment_rate": {
                "enabled": True,
                "display_name": "Employment Rate",
                "unit": "Anteil",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "unemployment_rate": {
                "enabled": True,
                "display_name": "Unemployment Rate",
                "unit": "Anteil",
                "aggregation": "value",
                "critical_threshold": None,
            },
        }

        # Only add default configs for metrics not already defined in CONFIG
        for metric_name, config in default_metrics.items():
            if metric_name not in self.metrics_config:
                self.metrics_config[metric_name] = config

    def add_metric(
        self,
        agent_id: AgentID,
        metric_name: MetricName,
        value: ValueType,
        metric_dict: AgentMetricsDict,
        step: TimeStep,
    ) -> None:
        """
        Add a metric value for an agent.

        Args:
            agent_id: The unique ID of the agent
            metric_name: Name of the metric
            value: Value of the metric
            metric_dict: The dictionary to store the metrics in
        """
        agent_metrics = metric_dict.setdefault(agent_id, {})
        step_metrics = agent_metrics.setdefault(step, {})
        step_metrics[metric_name] = value

    def register_household(self, household: EconomicAgent) -> None:
        """
        Register a household agent for metrics tracking.

        Args:
            household: Household agent to track
        """
        agent_id = household.unique_id
        if agent_id not in self.registered_households:
            self.registered_households.add(agent_id)
            self.household_metrics[agent_id] = {}
            log(
                f"MetricsCollector: Registered household {agent_id} for metrics tracking",
                level="DEBUG",
            )

    def register_company(self, company: EconomicAgent) -> None:
        """
        Register a company agent for metrics tracking.

        Args:
            company: Company agent to track
        """
        agent_id = company.unique_id
        if agent_id not in self.registered_companies:
            self.registered_companies.add(agent_id)
            self.company_metrics[agent_id] = {}
            log(
                f"MetricsCollector: Registered company {agent_id} for metrics tracking",
                level="DEBUG",
            )

    def register_bank(self, bank: EconomicAgent) -> None:
        """
        Register a bank agent for metrics tracking.

        Args:
            bank: Bank agent to track
        """
        agent_id = bank.unique_id
        if agent_id not in self.registered_banks:
            self.registered_banks.add(agent_id)
            self.bank_metrics[agent_id] = {}
            log(f"MetricsCollector: Registered bank {agent_id} for metrics tracking", level="DEBUG")

    def register_market(self, market: EconomicAgent) -> None:
        """
        Register a market agent for metrics tracking.

        Args:
            market: Market agent to track
        """
        agent_id = market.unique_id
        if agent_id not in self.market_metrics:
            self.market_metrics[agent_id] = {}
            log(
                f"MetricsCollector: Registered market {agent_id} for metrics tracking",
                level="DEBUG",
            )

    def collect_household_metrics(self, households: list[Household], step: TimeStep) -> None:

        for household in households:
            agent_id = household.unique_id
            if agent_id not in self.household_metrics:
                self.register_household(household)

            # Collect metrics if they exist on the household object
            for attr in [
                "checking_account",
                "savings",
                "income",
                "consumption",
                "age",
                "generation",
                "growth_phase",
                "employed",
                "environmental_impact",
            ]:
                if hasattr(household, attr):
                    value = getattr(household, attr)
                    self.add_metric(
                        agent_id, attr, value, self.household_metrics, step
                    )  # Pass the specific metric dict

            # Calculate derived metrics
            total_wealth = getattr(household, "checking_account", 0.0) + getattr(
                household, "savings", 0.0
            )
            self.add_metric(agent_id, "total_wealth", total_wealth, self.household_metrics, step)

    def collect_company_metrics(self, companies: list[Company], step: TimeStep) -> None:
        """
        Collect metrics from a company agent at the current time step.

        Args:
            company: Company agent to collect metrics from
            step: Current simulation time step
        """
        for company in companies:
            agent_id = company.unique_id
            if agent_id not in self.company_metrics:
                self.register_company(company)

            # Collect metrics if they exist on the company object
            for attr in [
                "balance",
                "production_capacity",
                "inventory",
                "environmental_impact",
                "rd_investment",
                "innovation_index",
                "growth_phase",
                "resource_usage",
            ]:
                if hasattr(company, attr):
                    value = getattr(company, attr)
                    self.add_metric(agent_id, attr, value, self.company_metrics, step)

            # Count employees if available
            if hasattr(company, "employees"):
                num_employees = len(company.employees)
                self.add_metric(agent_id, "employees", num_employees, self.company_metrics, step)

    def collect_bank_metrics(self, banks: list, step: TimeStep) -> None:
        """
        Collect metrics from a bank agent at the current time step.

        Args:
            banks: List of bank agents to collect metrics from
            step: Current simulation time step
        """
        for bank in banks:
            agent_id = bank.unique_id
            if agent_id not in self.bank_metrics:
                self.register_bank(bank)

            liquidity = bank.liquidity
            self.add_metric(agent_id, "liquidity", liquidity, self.bank_metrics, step)

            if hasattr(bank, "credit_lines"):
                total_credit = sum(bank.credit_lines.values())
                num_borrowers = len(bank.credit_lines)
                self.add_metric(agent_id, "total_credit", total_credit, self.bank_metrics, step)
                self.add_metric(agent_id, "num_borrowers", num_borrowers, self.bank_metrics, step)

            if hasattr(bank, "total_savings"):
                total_savings = bank.total_savings
                self.add_metric(agent_id, "total_savings", total_savings, self.bank_metrics, step)
                if hasattr(bank, "savings_accounts"):
                    num_accounts = len(bank.savings_accounts)
                    self.add_metric(agent_id, "num_accounts", num_accounts, self.bank_metrics, step)

    def collect_state_metrics(self, state_id: str, state, households, companies, step: TimeStep):
        """
        Collect metrics related to the state agent.

        Args:
            state_id: Unique identifier of the state agent
            state: State agent object
            households: List of household agents
            companies: List of company agents
        """
        # Collect basic state budget metrics
        self.add_metric(state_id, "tax_revenue", state.tax_revenue, self.state_metrics, step)
        self.add_metric(
            state_id, "infrastructure_budget", state.infrastructure_budget, self.state_metrics, step
        )
        self.add_metric(state_id, "social_budget", state.social_budget, self.state_metrics, step)
        self.add_metric(
            state_id, "environment_budget", state.environment_budget, self.state_metrics, step
        )

        # Calculate aggregate economic metrics
        total_household_savings = sum(household.savings for household in households)
        total_company_balance = sum(company.balance for company in companies)
        total_employment = sum(
            1 for household in households if hasattr(household, "employed") and household.employed
        )
        employment_rate = total_employment / len(households) if households else 0

        # Add aggregate metrics
        self.add_metric(
            state_id, "total_household_savings", total_household_savings, self.state_metrics, step
        )
        self.add_metric(
            state_id, "total_company_balance", total_company_balance, self.state_metrics, step
        )
        self.add_metric(state_id, "employment_rate", employment_rate, self.state_metrics, step)

    def collect_market_metrics(self, market: Any, step: TimeStep) -> None:
        """
        Collect metrics from a market agent at the current time step.

        Args:
            market: Market agent to collect metrics from
            step: Current simulation time step
        """
        agent_id = market.unique_id
        if agent_id not in self.market_metrics:
            self.market_metrics[agent_id] = {}

        # Labor market metrics
        if hasattr(market, "registered_workers"):
            num_registered_workers = len(market.registered_workers)
            self.add_metric(
                agent_id,
                "registered_workers",
                float(num_registered_workers),
                self.market_metrics,
                step,
            )

            employed_workers = sum(
                1 for w in market.registered_workers if hasattr(w, "employed") and w.employed
            )
            self.add_metric(
                agent_id, "employed_workers", float(employed_workers), self.market_metrics, step
            )

            employment_rate = (
                employed_workers / num_registered_workers if num_registered_workers > 0 else 0
            )
            self.add_metric(agent_id, "employment_rate", employment_rate, self.market_metrics, step)
            self.latest_labor_metrics = {
                "registered_workers": float(num_registered_workers),
                "employed_workers": float(employed_workers),
                "employment_rate": float(employment_rate),
                "unemployment_rate": (
                    float(1 - employment_rate) if num_registered_workers > 0 else 0.0
                ),
            }
        # Financial market metrics
        if hasattr(market, "list_of_assets"):
            num_assets = len(market.list_of_assets)
            self.add_metric(agent_id, "num_assets", float(num_assets), self.market_metrics, step)

            if market.list_of_assets:
                average_asset_price = statistics.mean(market.list_of_assets.values())
                self.add_metric(
                    agent_id, "average_asset_price", average_asset_price, self.market_metrics, step
                )

    def calculate_global_metrics(self, step: TimeStep) -> None:
        """Calculate global economic metrics aggregated across all agents."""
        metrics: MetricDict = {}

        money_metrics = self._global_money_metrics(step)
        metrics.update(money_metrics)

        activity_metrics = self._global_activity_metrics(step)
        metrics.update(activity_metrics)

        price_metrics = self._price_dynamics(
            step,
            money_metrics["total_money_supply"],
            activity_metrics["gdp"],
            activity_metrics["household_consumption"],
        )
        metrics.update(price_metrics)

        metrics.update(self._distribution_metrics(step))
        metrics.update(self._wage_metrics(step, price_metrics["price_index"]))
        metrics.update(self._environmental_metrics(step))
        metrics.update(self._employment_metrics(step))
        metrics.update(self._investment_metrics(step, activity_metrics["gdp"]))
        metrics.update(self._bankruptcy_metrics(step))
        metrics.update(self._government_metrics(step, activity_metrics["gdp"]))

        self.global_metrics[step] = metrics
        self.latest_global_metrics = metrics
        self._check_critical_thresholds(metrics)

    def get_latest_macro_snapshot(self) -> dict[str, float]:
        snapshot = {}
        snapshot.update(self.latest_global_metrics)
        snapshot.update(self.latest_labor_metrics)
        return snapshot

    def _count_bankruptcies_at_step(self, step: TimeStep) -> int:
        """
        Count the number of companies that went bankrupt at a given step.

        Args:
            step: Time step to analyze

        Returns:
            Number of bankruptcies detected
        """
        # Count companies that were present in the previous step but not in this one
        if step <= 1:
            return 0

        previous_step = step - 1
        bankruptcy_count = 0

        for company_id in self.registered_companies.copy():
            has_prev_data = previous_step in self.company_metrics.get(company_id, {})
            has_current_data = step in self.company_metrics.get(company_id, {})

            if has_prev_data and not has_current_data:
                bankruptcy_count += 1

        return bankruptcy_count

    def _calculate_gini_coefficient(self, values: List[float]) -> float:
        """
        Calculate Gini coefficient as a measure of inequality.

        Args:
            values: List of values (e.g., wealth distribution)

        Returns:
            Gini coefficient (0 = perfect equality, 1 = perfect inequality)
        """
        if not values or all(v == 0 for v in values):
            return 0.0

        sorted_values = sorted(values)
        n = len(sorted_values)
        cumsum = 0
        for i, value in enumerate(sorted_values):
            cumsum += (n - i) * value

        return (
            (2 * cumsum) / (n * sum(sorted_values)) - (n + 1) / n if sum(sorted_values) > 0 else 0.0
        )

    def _check_critical_thresholds(self, metrics: MetricDict) -> None:
        """
        Check if any metrics have crossed critical thresholds.

        Args:
            metrics: Dictionary of metrics to check
        """
        for metric_name, value in metrics.items():
            if metric_name in self.metrics_config:
                threshold = self.metrics_config[metric_name].get("critical_threshold")
                if threshold is not None:
                    if isinstance(value, (int, float)) and value >= threshold:
                        log(
                            f"CRITICAL: Metric {metric_name} value {value} has crossed threshold {threshold}",
                            level="WARNING",
                        )

    def aggregate_metrics(self, step: TimeStep) -> Dict[str, Dict[str, ValueType]]:
        """Aggregate metrics across agent types for a given time step."""
        result: Dict[str, Dict[str, ValueType]] = {
            "household": self._aggregate_agent_metrics(self.household_metrics, step, default="mean"),
            "company": self._aggregate_agent_metrics(self.company_metrics, step, default="mean"),
            "bank": self._aggregate_agent_metrics(self.bank_metrics, step, default="sum"),
            "state": self._first_state_snapshot(step),
            "market": {},
            "global": self.global_metrics.get(step, {}),
        }
        return result

    def _first_state_snapshot(self, step: TimeStep) -> Dict[str, ValueType]:
        for _state_id, time_series in self.state_metrics.items():
            data = time_series.get(step)
            if data:
                return data
        return {}

    def _aggregate_agent_metrics(
        self,
        agent_metrics: AgentMetricsDict,
        step: TimeStep,
        default: str,
    ) -> Dict[str, ValueType]:
        aggregated: Dict[str, ValueType] = {}
        values_by_metric = defaultdict(list)
        for _agent_id, time_series in agent_metrics.items():
            data = time_series.get(step)
            if not data:
                continue
            for metric, value in data.items():
                if isinstance(value, (int, float)):
                    values_by_metric[metric].append(value)

        for metric, values in values_by_metric.items():
            if not values:
                continue
            aggregation = self.metrics_config.get(metric, {}).get("aggregation", default)
            aggregated[metric] = self._apply_aggregation(values, aggregation)

        return aggregated

    def _apply_aggregation(self, values: List[float], aggregation: str) -> ValueType:
        if aggregation == "sum":
            return sum(values)
        if aggregation == "mean":
            return statistics.mean(values)
        if aggregation == "median":
            return statistics.median(values)
        if aggregation == "min":
            return min(values)
        if aggregation == "max":
            return max(values)
        return statistics.mean(values)

    def _state_snapshot(self, step: TimeStep) -> Dict[str, ValueType]:
        for _state_id, time_series in self.state_metrics.items():
            data = time_series.get(step)
            if data:
                return data
        return {}

    def _market_snapshot(self, step: TimeStep) -> Dict[str, ValueType]:
        snapshot: Dict[str, ValueType] = {}
        for market_id, time_series in self.market_metrics.items():
            data = time_series.get(step)
            if data:
                snapshot.update({f"{market_id}.{metric}": value for metric, value in data.items()})
        return snapshot

    def export_metrics(self) -> None:
        """Persist metrics according to CONFIG['result_storage']."""
        storage_mode = str(CONFIG.get("result_storage", "json")).lower()
        allowed_modes = {"json", "csv", "both"}
        if storage_mode not in allowed_modes:
            log(
                f"MetricsCollector: Unknown result_storage '{storage_mode}', defaulting to JSON",
                level="WARNING",
            )
            storage_mode = "json"

        if storage_mode in ("json", "both"):
            self.export_metrics_to_json()
        if storage_mode in ("csv", "both"):
            self.export_time_series_to_csv()

    def export_metrics_to_json(self) -> None:
        """Export all collected metrics to JSON format"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.export_path / f"metrics_{timestamp}.json"

        metrics_data = {
            "household_metrics": self.household_metrics,
            "company_metrics": self.company_metrics,
            "bank_metrics": self.bank_metrics,
            "state_metrics": self.state_metrics,
            "market_metrics": self.market_metrics,
            "global_metrics": self.global_metrics,
        }

        with open(output_file, "w") as f:
            json.dump(metrics_data, f, indent=2)

        log(f"MetricsCollector: Exported metrics to {output_file}", level="INFO")

    def export_time_series_to_csv(self) -> None:
        """Export time series of metrics to structured CSV files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exports = [
            self._export_global_metrics_csv(timestamp),
            self._export_agent_metrics_csv(self.household_metrics, "household_metrics", timestamp),
            self._export_agent_metrics_csv(self.company_metrics, "company_metrics", timestamp),
            self._export_agent_metrics_csv(self.bank_metrics, "bank_metrics", timestamp),
            self._export_agent_metrics_csv(self.state_metrics, "state_metrics", timestamp),
            self._export_agent_metrics_csv(self.market_metrics, "market_metrics", timestamp),
        ]

        written = [path for path in exports if path is not None]
        if written:
            log(
                "MetricsCollector: Exported CSV metrics: "
                + ", ".join(str(p.name) for p in written),
                level="INFO",
            )
        else:
            log("MetricsCollector: No metrics available for CSV export", level="WARNING")

    def _export_global_metrics_csv(self, timestamp: str) -> Optional[Path]:
        if not self.global_metrics:
            return None

        metric_names: Set[str] = set()
        for data in self.global_metrics.values():
            metric_names.update(data.keys())

        fieldnames = ["time_step"] + sorted(metric_names)
        output_file = self.export_path / f"global_metrics_{timestamp}.csv"

        with open(output_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for step in sorted(self.global_metrics.keys()):
                row = {"time_step": step}
                row.update(self.global_metrics[step])
                writer.writerow(row)

        return output_file

    def _export_agent_metrics_csv(
        self,
        agent_metrics: AgentMetricsDict,
        filename_prefix: str,
        timestamp: str,
    ) -> Optional[Path]:
        if not agent_metrics:
            return None

        metric_names: Set[str] = set()
        has_rows = False
        for time_series in agent_metrics.values():
            if time_series:
                has_rows = True
            for metrics in time_series.values():
                metric_names.update(metrics.keys())

        if not has_rows:
            return None

        fieldnames = ["time_step", "agent_id"] + sorted(metric_names)
        output_file = self.export_path / f"{filename_prefix}_{timestamp}.csv"

        with open(output_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for agent_id, time_series in agent_metrics.items():
                for step in sorted(time_series.keys()):
                    row = {"time_step": step, "agent_id": agent_id}
                    row.update(time_series[step])
                    writer.writerow(row)

        return output_file

    def detect_economic_cycles(self) -> Optional[Dict[str, Any]]:
        """
        Detect economic cycles like booms and recessions.

        Returns:
            Dictionary with cycle information or None if insufficient data
        """
        # Need sufficient data points
        if not self.global_metrics or len(self.global_metrics) < MIN_GLOBAL_METRICS_POINTS:
            return None

        steps = sorted(self.global_metrics.keys())
        growth_values = []

        # Calculate growth rate of total production
        for i in range(1, len(steps)):
            current_step = steps[i]
            prev_step = steps[i - 1]

            if (
                "total_money_supply" in self.global_metrics[current_step]
                and "total_money_supply" in self.global_metrics[prev_step]
            ):

                current = self.global_metrics[current_step]["total_money_supply"]
                prev = self.global_metrics[prev_step]["total_money_supply"]

                if prev > 0:
                    growth_rate = (current - prev) / prev
                    growth_values.append(growth_rate)

        if not growth_values:
            return None

        # Identify potential cycles
        recession_threshold = CONFIG.get("recession_threshold", -0.01)  # -1% growth
        boom_threshold = CONFIG.get("boom_threshold", 0.03)  # 3% growth

        is_recession = any(rate <= recession_threshold for rate in growth_values[-3:])
        is_boom = any(rate >= boom_threshold for rate in growth_values[-3:])

        avg_growth = statistics.mean(growth_values)

        return {
            "avg_growth_rate": avg_growth,
            "is_recession": is_recession,
            "is_boom": is_boom,
            "latest_growth": growth_values[-1] if growth_values else 0,
            "growth_volatility": statistics.stdev(growth_values) if len(growth_values) > 1 else 0,
        }

    def _global_money_metrics(self, step: TimeStep) -> MetricDict:
        metrics: MetricDict = {}
        total_money = 0.0
        for company_id, time_series in self.company_metrics.items():
            data = time_series.get(step)
            if data:
                total_money += data.get("balance", 0.0)

        for household_id, time_series in self.household_metrics.items():
            data = time_series.get(step)
            if data:
                total_money += data.get("checking_account", 0.0) + data.get("savings", 0.0)

        metrics["total_money_supply"] = total_money
        return metrics

    def _global_activity_metrics(self, step: TimeStep) -> MetricDict:
        metrics: MetricDict = {}
        gdp = 0.0
        for company_id, time_series in self.company_metrics.items():
            data = time_series.get(step)
            if data:
                gdp += data.get("production_capacity", 0.0)

        household_consumption = 0.0
        for household_id, time_series in self.household_metrics.items():
            data = time_series.get(step)
            if data:
                household_consumption += data.get("consumption", 0.0)

        metrics["gdp"] = gdp
        metrics["household_consumption"] = household_consumption
        metrics["consumption_pct_gdp"] = household_consumption / gdp if gdp > 0 else 0
        return metrics

    def _price_dynamics(
        self,
        step: TimeStep,
        total_money: float,
        gdp: float,
        household_consumption: float,
    ) -> MetricDict:
        metrics: MetricDict = {}
        price_index_base = float(CONFIG.get("price_index_base", 100.0))
        pressure_target = float(CONFIG.get("price_index_pressure_target", 1.0))
        price_sensitivity = float(CONFIG.get("price_index_sensitivity", 0.05))
        pressure_mode = str(CONFIG.get("price_index_pressure_ratio", "money_supply_to_gdp"))
        eps = 1e-9

        money_supply_pressure = total_money / (gdp + eps) if gdp > 0 else pressure_target
        consumption_pressure = (
            household_consumption / (gdp + eps) if gdp > 0 else pressure_target
        )
        if pressure_mode == "consumption_to_production":
            price_pressure = consumption_pressure
        elif pressure_mode == "blended":
            price_pressure = statistics.mean([money_supply_pressure, consumption_pressure])
        else:
            price_pressure = money_supply_pressure

        if step > 0 and (step - 1) in self.global_metrics:
            prev_price = self.global_metrics[step - 1].get("price_index", price_index_base)
        else:
            prev_price = price_index_base

        deviation = price_pressure - pressure_target
        current_price = prev_price * (1 + price_sensitivity * deviation)
        current_price = max(current_price, 0.01)
        inflation_rate = ((current_price - prev_price) / prev_price) if prev_price > 0 else 0.0

        metrics["price_index"] = current_price
        metrics["inflation_rate"] = inflation_rate
        metrics["price_pressure"] = price_pressure
        return metrics

    def _distribution_metrics(self, step: TimeStep) -> MetricDict:
        metrics: MetricDict = {}
        wealth_values = []
        for household_id, time_series in self.household_metrics.items():
            data = time_series.get(step)
            if data:
                wealth_values.append(data.get("total_wealth", 0.0))

        if wealth_values:
            metrics["gini_coefficient"] = self._calculate_gini_coefficient(wealth_values)
        return metrics

    def _wage_metrics(self, step: TimeStep, price_index: float) -> MetricDict:
        metrics: MetricDict = {}
        nominal_wages = []
        for household_id, time_series in self.household_metrics.items():
            data = time_series.get(step)
            if data and data.get("employed"):
                nominal_wages.append(data.get("income", 0.0))

        avg_nominal_wage = statistics.mean(nominal_wages) if nominal_wages else 0
        price_index_pct = price_index / 100
        metrics["average_nominal_wage"] = avg_nominal_wage
        metrics["average_real_wage"] = (
            avg_nominal_wage / price_index_pct if price_index_pct > 0 else 0
        )
        return metrics

    def _environmental_metrics(self, step: TimeStep) -> MetricDict:
        metrics: MetricDict = {}
        total_impact = 0.0
        for company_id, time_series in self.company_metrics.items():
            data = time_series.get(step)
            if data:
                total_impact += data.get("environmental_impact", 0.0)

        for household_id, time_series in self.household_metrics.items():
            data = time_series.get(step)
            if data:
                total_impact += data.get("environmental_impact", 0.0)

        metrics["total_environmental_impact"] = total_impact
        return metrics

    def _employment_metrics(self, step: TimeStep) -> MetricDict:
        metrics: MetricDict = {}
        employed_count = 0
        total_households = 0
        for household_id, time_series in self.household_metrics.items():
            data = time_series.get(step)
            if data and "employed" in data:
                total_households += 1
                if data["employed"]:
                    employed_count += 1

        if total_households > 0:
            metrics["employment_rate"] = employed_count / total_households
            metrics["unemployment_rate"] = 1 - (employed_count / total_households)
        return metrics

    def _investment_metrics(self, step: TimeStep, gdp: float) -> MetricDict:
        metrics: MetricDict = {}
        total_rd_investment = 0.0
        for company_id, time_series in self.company_metrics.items():
            data = time_series.get(step)
            if data:
                total_rd_investment += data.get("rd_investment", 0.0)

        metrics["total_rd_investment"] = total_rd_investment
        metrics["investment_pct_gdp"] = total_rd_investment / gdp if gdp > 0 else 0
        return metrics

    def _bankruptcy_metrics(self, step: TimeStep) -> MetricDict:
        metrics: MetricDict = {}
        bankruptcy_count = self._count_bankruptcies_at_step(step)
        total_companies = len(self.registered_companies)
        if total_companies > 0:
            metrics["bankruptcy_rate"] = bankruptcy_count / total_companies
        return metrics

    def _government_metrics(self, step: TimeStep, gdp: float) -> MetricDict:
        metrics: MetricDict = {}
        tax_revenue = 0.0
        govt_spending = 0.0
        for state_id, time_series in self.state_metrics.items():
            data = time_series.get(step)
            if not data:
                continue
            tax_revenue += data.get("tax_revenue", 0.0)
            govt_spending += (
                data.get("infrastructure_budget", 0.0)
                + data.get("social_budget", 0.0)
                + data.get("environment_budget", 0.0)
            )

        metrics["tax_revenue"] = tax_revenue
        metrics["government_spending"] = govt_spending
        metrics["govt_spending_pct_gdp"] = govt_spending / gdp if gdp > 0 else 0
        metrics["budget_balance"] = tax_revenue - govt_spending
        return metrics


# Create a singleton metrics collector instance
metrics_collector = MetricsCollector()
