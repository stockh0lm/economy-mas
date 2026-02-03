# metrics.py
"""
Economic metrics collection and analysis system for the simulation.

This module tracks key economic indicators across different agent types,
calculates aggregate statistics, and provides data for visualization.
"""

import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Protocol, TypedDict, cast

from agents.company_agent import Company
from agents.household_agent import Household
from config import CONFIG_MODEL, SimulationConfig
from logger import log

MIN_GLOBAL_METRICS_POINTS = 10  # Minimal steps required for cycle detection


def apply_sight_decay(agents: Iterable[Any], *, config: SimulationConfig | None = None) -> float:
    """Sichtguthaben-Abschmelzung (nur Überschuss über Freibetrag).

    Spezifikation: doc/specs.md Section 4.7 (monatlich).
    Expliziter Bezug: doc/issues.md Abschnitt 4/5 → "Hyperinflation / Numerische Überläufe ...".

    Hinweis zur Einheitenkonsistenz:
    - `consumption_history` wird in der Simulation täglich geführt.
    - Der Freibetrag orientiert sich an *monatlichen* Ausgaben.
      => Wir skalieren die rollierende Tages-Mean mit `days_per_month`.

    Returns:
        destroyed_total: Summe der abgeschmolzenen Sichtguthaben.
    """

    cfg = config or CONFIG_MODEL
    factor = float(getattr(getattr(cfg, "clearing", None), "sight_excess_decay_rate", 0.0))
    k = float(getattr(getattr(cfg, "clearing", None), "sight_allowance_multiplier", 0.0))
    window = int(getattr(getattr(cfg, "clearing", None), "sight_allowance_window_days", 30) or 30)
    hyperwealth = float(
        getattr(getattr(cfg, "clearing", None), "hyperwealth_threshold", 0.0) or 0.0
    )
    days_per_month = int(getattr(getattr(cfg, "time", None), "days_per_month", 30) or 30)

    if factor <= 0 or k <= 0 or window <= 0 or days_per_month <= 0:
        return 0.0

    destroyed_total = 0.0
    for a in agents:
        if not hasattr(a, "sight_balance"):
            continue
        bal = float(getattr(a, "sight_balance", 0.0))
        if bal <= 0:
            continue

        hist = list(getattr(a, "consumption_history", []) or [])
        if hist:
            tail = hist[-window:]
            avg_daily = float(sum(tail) / len(tail)) if tail else 0.0
        else:
            # Fallback: approximate spend from income if available.
            avg_daily = float(getattr(a, "income", 0.0))

        avg_monthly_spend = avg_daily * float(days_per_month)
        allowance = max(0.0, k * avg_monthly_spend)
        # Conservative default: only apply to non-households when balances are extreme.
        if not hist and hyperwealth > 0:
            allowance = max(allowance, hyperwealth)

        excess = max(0.0, bal - allowance)
        if excess <= 0:
            continue

        decay = factor * excess
        if decay <= 0:
            continue

        burned = min(bal, decay)
        setattr(a, "sight_balance", bal - burned)
        destroyed_total += burned

    return float(destroyed_total)


# Type definitions for improved readability
AgentID = str
TimeStep = int
ValueType = float | int | bool | str
MetricName = str
MetricDict = dict[MetricName, ValueType]
TimeSeriesDict = dict[TimeStep, MetricDict]
AgentMetricsDict = dict[AgentID, TimeSeriesDict]


class EconomicAgent(Protocol):
    """Protocol defining the minimum required attributes for tracked agents"""

    unique_id: str


class MetricConfig(TypedDict):
    """Configuration settings for a single metric"""

    enabled: bool  # Whether metric is enabled
    display_name: str  # Human-readable name for plots/reports
    unit: str  # Measurement unit (e.g., "$", "%", "units")
    aggregation: str  # How to aggregate across agents ("sum", "mean", "median", "min", "max")
    critical_threshold: float | None  # Value that triggers alerts if crossed


class LaborMarketMetricsSource(Protocol):
    registered_workers: list[object]


class FinancialMarketMetricsSource(Protocol):
    list_of_assets: dict[str, float]


class EconomicCycleSnapshot(TypedDict):
    avg_growth_rate: float
    is_recession: bool
    is_boom: bool
    latest_growth: float
    growth_volatility: float


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
    registered_households: set[str]
    registered_companies: set[str]
    registered_banks: set[str]
    metrics_config: dict[MetricName, MetricConfig]
    export_path: Path
    latest_labor_metrics: dict[str, float]
    latest_global_metrics: dict[str, float]
    config: SimulationConfig

    def __init__(self, config: SimulationConfig | None = None):
        """Initialize the metrics collector."""
        self.config: SimulationConfig = config or CONFIG_MODEL
        self.bank_metrics: AgentMetricsDict = {}
        self.household_metrics: AgentMetricsDict = {}
        self.company_metrics: AgentMetricsDict = {}
        self.retailer_metrics: AgentMetricsDict = {}
        self.state_metrics: AgentMetricsDict = {}
        self.market_metrics: AgentMetricsDict = {}
        self.global_metrics: TimeSeriesDict = {}
        self.registered_households: set[str] = set()
        self.registered_companies: set[str] = set()
        self.registered_retailers: set[str] = set()
        self.registered_banks: set[str] = set()
        self.metrics_config: dict[MetricName, MetricConfig] = {}
        self.export_path: Path = Path(self.config.metrics_export_path)
        self.latest_labor_metrics = {}
        self.latest_global_metrics = {}
        # Cached DataFrames (materialized on export)
        self.household_metrics_df: pd.DataFrame | None = None
        self.company_metrics_df: pd.DataFrame | None = None
        self.retailer_metrics_df: pd.DataFrame | None = None
        self.bank_metrics_df: pd.DataFrame | None = None
        self.state_metrics_df: pd.DataFrame | None = None
        self.market_metrics_df: pd.DataFrame | None = None
        self.global_metrics_df: pd.DataFrame | None = None
        self.__post_init__()

    def __post_init__(self) -> None:
        """Initialize with configuration from SimulationConfig"""
        self.metrics_config = self.config.metrics_config
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
            "sight_balance": {
                "enabled": True,
                "display_name": "Company Sight Balance",
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
            # Goods vs services transparency (Warengeld contract)
            "goods_tx_volume": {
                "enabled": True,
                "display_name": "Goods Transaction Volume",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "service_tx_volume": {
                "enabled": True,
                "display_name": "Service Transaction Volume",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "issuance_volume": {
                "enabled": True,
                "display_name": "Issuance Volume (Money Creation)",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "extinguish_volume": {
                "enabled": True,
                "display_name": "Extinguish Volume (Money Destruction)",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "goods_value_total": {
                "enabled": True,
                "display_name": "Goods Output Value",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "service_value_total": {
                "enabled": True,
                "display_name": "Service Output Value",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
            "service_share_of_output": {
                "enabled": True,
                "display_name": "Service Share of Output",
                "unit": "Anteil",
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

    def register_retailer(self, retailer: EconomicAgent) -> None:
        """Register a retailer agent for metrics tracking."""

        agent_id = retailer.unique_id
        if agent_id not in self.registered_retailers:
            self.registered_retailers.add(agent_id)
            self.retailer_metrics[agent_id] = {}
            log(
                f"MetricsCollector: Registered retailer {agent_id} for metrics tracking",
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

            step_metrics: dict[str, ValueType] = {}

            # Collect metrics if they exist on the household object
            for attr in [
                "checking_account",
                "savings",
                "income",
                # Actual wage signal from the labor market (nominal wage rate).
                # This is the correct basis for "nominal/real wage" metrics.
                "current_wage",
                # Optional cashflow counters (useful for debugging transfer vs. money creation).
                "income_received_this_month",
                "last_income_received",
                "consumption",
                "age",
                "generation",
                "growth_phase",
                "employed",
                "environmental_impact",
            ]:
                if hasattr(household, attr):
                    step_metrics[attr] = cast(ValueType, getattr(household, attr))

            # Calculate derived metrics (kept for backwards compatibility)
            total_wealth = float(getattr(household, "checking_account", 0.0)) + float(
                getattr(household, "savings", 0.0)
            )
            step_metrics["total_wealth"] = total_wealth

            self.household_metrics.setdefault(agent_id, {})[step] = step_metrics

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

            step_metrics: dict[str, ValueType] = {}

            # Collect metrics if they exist on the company object
            for attr in [
                "sight_balance",
                "service_sales_total",
                "production_capacity",
                "inventory",
                "environmental_impact",
                "rd_investment",
                "innovation_index",
                "growth_phase",
                "resource_usage",
            ]:
                if hasattr(company, attr):
                    step_metrics[attr] = cast(ValueType, getattr(company, attr))

            # Count employees if available
            if hasattr(company, "employees"):
                step_metrics["employees"] = int(len(company.employees))

            self.company_metrics.setdefault(agent_id, {})[step] = step_metrics

    def collect_retailer_metrics(self, retailers: list, step: TimeStep) -> None:
        """Collect metrics from retailer agents."""

        for retailer in retailers:
            agent_id = retailer.unique_id
            if agent_id not in self.retailer_metrics:
                self.register_retailer(retailer)

            step_metrics: dict[str, ValueType] = {}
            for attr in [
                "sight_balance",
                "cc_balance",
                "cc_limit",
                "inventory_value",
                "target_inventory_value",
                "write_downs_total",
                "inventory_write_down_extinguished_total",
                "sales_total",
                "purchases_total",
                "repaid_total",
            ]:
                if hasattr(retailer, attr):
                    step_metrics[attr] = cast(ValueType, getattr(retailer, attr))
            self.retailer_metrics.setdefault(agent_id, {})[step] = step_metrics

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

            step_metrics: dict[str, ValueType] = {}
            step_metrics["liquidity"] = float(getattr(bank, "liquidity", 0.0))
            # Include bank's own sight balance (fee income stock) so broad-money
            # proxies can remain transfer-invariant when fees move to the bank.
            if hasattr(bank, "sight_balance"):
                step_metrics["sight_balance"] = float(getattr(bank, "sight_balance", 0.0))

            if hasattr(bank, "credit_lines"):
                credit_lines = getattr(bank, "credit_lines")
                total_credit = float(sum(credit_lines.values()))
                step_metrics["total_credit"] = total_credit
                step_metrics["num_borrowers"] = int(len(credit_lines))

            # Warengeld-relevant money creation tracking: volume of financed goods purchases.
            # Referenz: doc/issues.md Abschnitt 6) -> M3 (Dienstleistungssektor: Service-Tx müssen issuance_volume NICHT beeinflussen).
            if hasattr(bank, "goods_purchase_ledger"):
                ledger = getattr(bank, "goods_purchase_ledger")
                issuance = 0.0
                for rec in ledger:
                    if int(getattr(rec, "step", -1)) == int(step):
                        issuance += float(getattr(rec, "amount", 0.0))
                step_metrics["issuance_volume"] = float(issuance)

            if hasattr(bank, "total_savings"):
                total_savings = float(getattr(bank, "total_savings"))
                step_metrics["total_savings"] = total_savings
                if hasattr(bank, "savings_accounts"):
                    step_metrics["num_accounts"] = int(len(getattr(bank, "savings_accounts")))

            self.bank_metrics.setdefault(agent_id, {})[step] = step_metrics

    def collect_state_metrics(self, state_id: str, state, households, companies, step: TimeStep):
        """
        Collect metrics related to the state agent.

        Args:
            state_id: Unique identifier of the state agent
            state: State agent object
            households: List of household agents
            companies: List of company agents
        """
        step_metrics: dict[str, ValueType] = {
            "tax_revenue": float(getattr(state, "tax_revenue", 0.0)),
            "infrastructure_budget": float(getattr(state, "infrastructure_budget", 0.0)),
            "social_budget": float(getattr(state, "social_budget", 0.0)),
            "environment_budget": float(getattr(state, "environment_budget", 0.0)),
        }

        # Calculate aggregate economic metrics
        total_household_savings = sum(
            float(getattr(h, "local_savings", getattr(h, "savings", 0.0))) for h in households
        )
        total_company_balance = sum(
            float(getattr(c, "sight_balance", getattr(c, "balance", 0.0))) for c in companies
        )
        total_employment = sum(
            1 for household in households if hasattr(household, "employed") and household.employed
        )
        employment_rate = total_employment / len(households) if households else 0

        step_metrics["total_household_savings"] = float(total_household_savings)
        step_metrics["total_company_balance"] = float(total_company_balance)
        step_metrics["employment_rate"] = float(employment_rate)

        self.state_metrics.setdefault(state_id, {})[step] = step_metrics

    def collect_market_metrics(self, market: EconomicAgent, step: TimeStep) -> None:
        """
        Collect metrics from a market agent at the current time step.

        Args:
            market: Market agent to collect metrics from
        """
        agent_id = market.unique_id
        if agent_id not in self.market_metrics:
            self.market_metrics[agent_id] = {}

        step_metrics: dict[str, ValueType] = {}

        # Labor market metrics
        if hasattr(market, "registered_workers"):
            labor_market = cast(LaborMarketMetricsSource, market)
            num_registered_workers = len(labor_market.registered_workers)
            step_metrics["registered_workers"] = float(num_registered_workers)

            employed_workers = sum(
                1 for w in labor_market.registered_workers if hasattr(w, "employed") and w.employed
            )
            step_metrics["employed_workers"] = float(employed_workers)

            employment_rate = (
                employed_workers / num_registered_workers if num_registered_workers > 0 else 0
            )
            step_metrics["employment_rate"] = float(employment_rate)
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
            financial_market = cast(FinancialMarketMetricsSource, market)
            num_assets = len(financial_market.list_of_assets)
            step_metrics["num_assets"] = float(num_assets)

            if financial_market.list_of_assets:
                average_asset_price = statistics.mean(financial_market.list_of_assets.values())
                step_metrics["average_asset_price"] = float(average_asset_price)

        if step_metrics:
            self.market_metrics.setdefault(agent_id, {})[step] = step_metrics

    def calculate_global_metrics(self, step: TimeStep) -> None:
        """Calculate global economic metrics aggregated across all agents."""
        metrics: MetricDict = {}

        money_metrics = self._global_money_metrics(step)
        # Backward-compatible name expected by tests/exports:
        # total_money_supply ~= broad money (sight + savings)
        if "total_money_supply" not in money_metrics:
            money_metrics["total_money_supply"] = float(money_metrics.get("m2_proxy", 0.0))
        metrics.update(money_metrics)

        activity_metrics = self._global_activity_metrics(step)
        metrics.update(activity_metrics)

        # - Default/non-blended: broad money pressure
        # - Blended mode: historical tests blend M1 pressure with consumption pressure
        # NOTE: Tests mutate CONFIG_MODEL at runtime; re-read the global model here.
        pressure_mode = str(
            getattr(
                getattr(CONFIG_MODEL, "market", None),
                "price_index_pressure_ratio",
                self.config.market.price_index_pressure_ratio,
            )
        )

        money_for_price = float(
            money_metrics.get("total_money_supply", money_metrics.get("m2_proxy", 0.0))
        )
        if pressure_mode == "blended":
            money_for_price = float(money_metrics.get("m1_proxy", 0.0))

        price_metrics = self._price_dynamics(
            step,
            money_for_price,
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

    def _calculate_gini_coefficient(self, values: list[float]) -> float:
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

    def aggregate_metrics(self, step: TimeStep) -> dict[str, dict[str, ValueType]]:
        """Aggregate metrics across agent types for a given time step."""
        result: dict[str, dict[str, ValueType]] = {
            "household": self._aggregate_agent_metrics(
                self.household_metrics, step, default="mean"
            ),
            "company": self._aggregate_agent_metrics(self.company_metrics, step, default="mean"),
            "bank": self._aggregate_agent_metrics(self.bank_metrics, step, default="sum"),
            "state": self._first_state_snapshot(step),
            "market": {},
            "global": self.global_metrics.get(step, {}),
        }
        return result

    def _first_state_snapshot(self, step: TimeStep) -> dict[str, ValueType]:
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
    ) -> dict[str, ValueType]:
        aggregated: dict[str, ValueType] = {}
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

    def _apply_aggregation(self, values: list[float], aggregation: str) -> ValueType:
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

    def _state_snapshot(self, step: TimeStep) -> dict[str, ValueType]:
        for _state_id, time_series in self.state_metrics.items():
            data = time_series.get(step)
            if data:
                return data
        return {}

    def _market_snapshot(self, step: TimeStep) -> dict[str, ValueType]:
        snapshot: dict[str, ValueType] = {}
        for market_id, time_series in self.market_metrics.items():
            data = time_series.get(step)
            if data:
                snapshot.update({f"{market_id}.{metric}": value for metric, value in data.items()})
        return snapshot

    def export_metrics(self) -> None:
        """Persist metrics to CSV (JSON export removed for performance)."""
        self.export_time_series_to_csv()

    def export_time_series_to_csv(self) -> None:
        """Export time series of metrics to structured CSV files using pandas."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        exports = [
            self._export_global_metrics_df(timestamp),
            self._export_agent_metrics_df(self.household_metrics, "household_metrics", timestamp),
            self._export_agent_metrics_df(self.company_metrics, "company_metrics", timestamp),
            self._export_agent_metrics_df(self.retailer_metrics, "retailer_metrics", timestamp),
            self._export_agent_metrics_df(self.bank_metrics, "bank_metrics", timestamp),
            self._export_agent_metrics_df(self.state_metrics, "state_metrics", timestamp),
            self._export_agent_metrics_df(self.market_metrics, "market_metrics", timestamp),
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

    def _export_global_metrics_df(self, timestamp: str) -> Path | None:
        if not self.global_metrics:
            return None

        import pandas as pd

        rows: list[dict[str, ValueType]] = []
        for step, metrics in self.global_metrics.items():
            row: dict[str, ValueType] = {"time_step": int(step)}
            row.update(metrics)
            rows.append(row)

        df = pd.DataFrame.from_records(rows)
        if not df.empty and "time_step" in df.columns:
            df = df.sort_values("time_step")

        output_file = self.export_path / f"global_metrics_{timestamp}.csv"
        import warnings

        with warnings.catch_warnings():
            # pandas may warn about dtype casts when writing NaNs in mixed-type frames.
            warnings.simplefilter("ignore", RuntimeWarning)
            df.to_csv(output_file, index=False)
        # Cache for interactive/debug use
        self.global_metrics_df = df
        return output_file

    def _export_agent_metrics_df(
        self,
        agent_metrics: AgentMetricsDict,
        filename_prefix: str,
        timestamp: str,
    ) -> Path | None:
        if not agent_metrics:
            return None

        import pandas as pd

        rows: list[dict[str, ValueType]] = []
        for agent_id, time_series in agent_metrics.items():
            for step, metrics in time_series.items():
                row: dict[str, ValueType] = {"time_step": int(step), "agent_id": str(agent_id)}
                row.update(metrics)
                rows.append(row)

        if not rows:
            return None

        df = pd.DataFrame.from_records(rows)
        if not df.empty and "time_step" in df.columns:
            df = df.sort_values(["time_step", "agent_id"])  # stable output

        output_file = self.export_path / f"{filename_prefix}_{timestamp}.csv"
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            df.to_csv(output_file, index=False)

        # Cache for interactive/debug use
        if filename_prefix.startswith("household"):
            self.household_metrics_df = df
        elif filename_prefix.startswith("company"):
            self.company_metrics_df = df
        elif filename_prefix.startswith("retailer"):
            self.retailer_metrics_df = df
        elif filename_prefix.startswith("bank"):
            self.bank_metrics_df = df
        elif filename_prefix.startswith("state"):
            self.state_metrics_df = df
        elif filename_prefix.startswith("market"):
            self.market_metrics_df = df

        return output_file

    def detect_economic_cycles(self) -> EconomicCycleSnapshot | None:
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
        recession_threshold = self.config.market.recession_threshold
        boom_threshold = self.config.market.boom_threshold

        is_recession = any(rate <= recession_threshold for rate in growth_values[-3:])
        is_boom = any(rate >= boom_threshold for rate in growth_values[-3:])

        avg_growth = statistics.mean(growth_values)

        return {
            "avg_growth_rate": avg_growth,
            "is_recession": is_recession,
            "is_boom": is_boom,
            "latest_growth": growth_values[-1] if growth_values else 0.0,
            "growth_volatility": statistics.stdev(growth_values) if len(growth_values) > 1 else 0.0,
        }

    def _global_money_metrics(self, step: TimeStep) -> MetricDict:
        """Global monetary aggregates (diagnostic proxies).

        - m1_proxy: sum of positive sight balances (households + companies + retailers + state + banks)
        - m2_proxy: m1_proxy + household savings (Sparkasse deposits)
        - cc_exposure: sum of absolute cc balances (retailers)
        - inventory_value_total: sum of retailer inventory values

        Additional transparency metrics (doc/issues.md Abschnitt 6 -> M3):
        - goods_tx_volume: sum of retailer sales_total
        - service_tx_volume: sum of company service_sales_total
        - goods_value_total, service_value_total, service_share_of_output
        - issuance_volume: sum of WarengeldBank financed goods purchases in this step
        - extinguish_volume: sum of retailer CC repayments + inventory write-down extinguishing in this step
        """

        metrics: MetricDict = {}

        m1 = 0.0
        m2 = 0.0

        service_tx_volume = 0.0

        # State deposits (budget buckets) are part of sight money; including them
        # keeps M1/M2 invariant under pure transfers (e.g. taxes).
        state_sight = 0.0
        for _sid, time_series in self.state_metrics.items():
            data = time_series.get(step)
            if not data:
                continue
            state_sight += float(data.get("tax_revenue", 0.0))
            state_sight += float(data.get("infrastructure_budget", 0.0))
            state_sight += float(data.get("social_budget", 0.0))
            state_sight += float(data.get("environment_budget", 0.0))
            # Only one state is expected; if multiple exist, we sum them.
        m1 += max(0.0, state_sight)
        m2 += max(0.0, state_sight)

        # Companies (sight + services)
        for _cid, time_series in self.company_metrics.items():
            data = time_series.get(step)
            if not data:
                continue
            # Prefer spec name, fall back to legacy
            # Kanonischer Kontoname: sight_balance
            # Referenz: doc/issues.md Abschnitt 4 → „Einheitliche Balance-Sheet-Namen (Company/Producer)“
            bal = float(data.get("sight_balance", 0.0))
            m1 += max(0.0, bal)
            m2 += max(0.0, bal)
            service_tx_volume += float(data.get("service_sales_total", 0.0))

        # Households (sight + savings)
        for _hid, time_series in self.household_metrics.items():
            data = time_series.get(step)
            if not data:
                continue
            sight = float(data.get("sight_balance", data.get("checking_account", 0.0)))
            savings = float(data.get("savings_balance", data.get("savings", 0.0)))
            m1 += max(0.0, sight)
            m2 += max(0.0, sight) + max(0.0, savings)

        # Retailers (sight) + exposures + inventory + extinction flows
        cc_exposure = 0.0
        inventory_total = 0.0
        sales_total = 0.0
        extinguish_volume = 0.0
        # Debugging / crash indicators (computed from retailer balance sheets).
        cc_headroom_total = 0.0
        cc_utilization_values: list[float] = []
        retailers_at_cc_limit = 0
        retailers_stockout = 0
        retailers_count = 0
        for _rid, time_series in self.retailer_metrics.items():
            data = time_series.get(step)
            if not data:
                continue
            retailers_count += 1
            sight = float(data.get("sight_balance", 0.0))
            cc = float(data.get("cc_balance", 0.0))
            cc_limit = float(data.get("cc_limit", 0.0))
            inv = float(data.get("inventory_value", 0.0))
            sales_total += float(data.get("sales_total", 0.0))
            extinguish_volume += float(data.get("repaid_total", 0.0))
            extinguish_volume += float(data.get("inventory_write_down_extinguished_total", 0.0))
            m1 += max(0.0, sight)
            m2 += max(0.0, sight)
            cc_exposure += abs(cc)
            inventory_total += max(0.0, inv)

            # CC headroom and utilization diagnostics.
            # With negative `cc_balance` representing drawn credit, the remaining
            # headroom is: cc_limit - abs(cc_balance).
            headroom = max(0.0, cc_limit - abs(cc))
            cc_headroom_total += headroom
            if cc_limit > 0:
                cc_utilization_values.append(min(1.0, abs(cc) / cc_limit))
            if headroom <= 1e-9 and abs(cc) > 0:
                retailers_at_cc_limit += 1
            if inv <= 1e-9:
                retailers_stockout += 1

        # Banks: include their own sight balances (fee income stock).
        bank_sight = 0.0
        for _bid, time_series in self.bank_metrics.items():
            data = time_series.get(step)
            if not data:
                continue
            bank_sight += float(data.get("sight_balance", 0.0))
        m1 += max(0.0, bank_sight)
        m2 += max(0.0, bank_sight)

        # Issuance: sum across banks that provide per-step issuance_volume.
        issuance_volume = 0.0
        for _bid, time_series in self.bank_metrics.items():
            data = time_series.get(step)
            if not data:
                continue
            issuance_volume += float(data.get("issuance_volume", 0.0))

        metrics["m1_proxy"] = m1
        metrics["m2_proxy"] = m2
        metrics["cc_exposure"] = cc_exposure
        metrics["inventory_value_total"] = inventory_total
        metrics["sales_total"] = sales_total
        metrics["velocity_proxy"] = sales_total / m1 if m1 > 0 else 0.0
        metrics["goods_tx_volume"] = sales_total
        metrics["service_tx_volume"] = service_tx_volume
        metrics["issuance_volume"] = issuance_volume
        metrics["extinguish_volume"] = extinguish_volume
        # Crash-indicative diagnostics:
        metrics["cc_headroom_total"] = float(cc_headroom_total)
        metrics["avg_cc_utilization"] = (
            float(sum(cc_utilization_values) / len(cc_utilization_values))
            if cc_utilization_values
            else 0.0
        )
        metrics["retailers_at_cc_limit_share"] = (
            float(retailers_at_cc_limit / retailers_count) if retailers_count > 0 else 0.0
        )
        metrics["retailers_stockout_share"] = (
            float(retailers_stockout / retailers_count) if retailers_count > 0 else 0.0
        )

        goods_value_total = sales_total
        service_value_total = service_tx_volume
        metrics["goods_value_total"] = goods_value_total
        metrics["service_value_total"] = service_value_total
        denom = goods_value_total + service_value_total
        metrics["service_share_of_output"] = service_value_total / denom if denom > 0 else 0.0
        return metrics

    def _price_dynamics(
        self,
        step: TimeStep,
        total_money: float,
        gdp: float,
        household_consumption: float,
    ) -> MetricDict:
        metrics: MetricDict = {}
        price_index_base = float(self.config.market.price_index_base)
        price_index_max = float(getattr(self.config.market, "price_index_max", 1000.0))
        pressure_target = float(self.config.market.price_index_pressure_target)
        price_sensitivity = float(self.config.market.price_index_sensitivity)
        pressure_mode = str(
            getattr(
                getattr(CONFIG_MODEL, "market", None),
                "price_index_pressure_ratio",
                self.config.market.price_index_pressure_ratio,
            )
        )
        eps = 1e-9

        money_supply_pressure = total_money / (gdp + eps) if gdp > 0 else pressure_target
        consumption_pressure = household_consumption / (gdp + eps) if gdp > 0 else pressure_target
        if pressure_mode == "consumption_to_production":
            price_pressure = consumption_pressure
        elif pressure_mode == "blended":
            # Tested behavior: 75% money-supply pressure + 25% consumption pressure.
            price_pressure = 0.75 * money_supply_pressure + 0.25 * consumption_pressure
        else:
            price_pressure = money_supply_pressure

        if step > 0 and (step - 1) in self.global_metrics:
            prev_price = self.global_metrics[step - 1].get("price_index", price_index_base)
        else:
            prev_price = price_index_base

        # --- Preisniveau-Dynamik (Stabilitäts-Fix) ---
        # Referenz: doc/issues.md Abschnitt 4/5 → „Hyperinflation / Numerische Überläufe in Preisindex-Berechnung - KRITISCH“.
        # Ziel: Bei konstantem Preisdruck soll das Preisniveau gegen ein Gleichgewicht konvergieren
        #       (anstatt pro Tick mit konstanter Rate exponentiell zu wachsen).
        if pressure_target > 0:
            desired_price = price_index_base * (price_pressure / pressure_target)
        else:
            desired_price = price_index_base

        # Exponentielle Glättung zum Zielpreis (sensitivity = Anpassungsgeschwindigkeit).
        current_price = prev_price + price_sensitivity * (desired_price - prev_price)

        # Defensive clamps (Numerik / Negativwerte)
        current_price = max(float(current_price), 0.01)
        if price_index_max > 0:
            current_price = min(float(current_price), float(price_index_max))
        if not math.isfinite(current_price):
            current_price = float(price_index_max) if price_index_max > 0 else price_index_base
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
                # Prefer the labor-market wage rate if available; fall back to
                # legacy 'income' template parameter.
                w = data.get("current_wage", None)
                if isinstance(w, (int, float)) and float(w) > 0:
                    nominal_wages.append(float(w))
                else:
                    nominal_wages.append(float(data.get("income", 0.0)))

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

        def _is_truthy(value: object) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return value != 0
            if isinstance(value, str):
                return value.strip().lower() in {"true", "1", "yes"}
            return False

        for household_id, time_series in self.household_metrics.items():
            data = time_series.get(step)
            if data and "employed" in data:
                total_households += 1
                if _is_truthy(data["employed"]):
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

    def _global_activity_metrics(self, step: TimeStep) -> MetricDict:
        """Global activity aggregates.

        GDP proxy: sum of company production_capacity at this step.
        Consumption: sum of household consumption at this step.
        """
        metrics: MetricDict = {}
        gdp = 0.0
        for _company_id, time_series in self.company_metrics.items():
            data = time_series.get(step)
            if data:
                gdp += float(data.get("production_capacity", 0.0))

        household_consumption = 0.0
        for _household_id, time_series in self.household_metrics.items():
            data = time_series.get(step)
            if data:
                household_consumption += float(data.get("consumption", 0.0))

        metrics["gdp"] = gdp
        metrics["household_consumption"] = household_consumption
        metrics["consumption_pct_gdp"] = household_consumption / gdp if gdp > 0 else 0.0
        return metrics


# Create a singleton metrics collector instance
metrics_collector = MetricsCollector()
