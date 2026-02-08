"""MetricsCollector - collects metrics from simulation agents."""

from typing import Any, Dict, List, Optional, Protocol, Set, cast
from .base import MetricDict, TimeStep, ValueType
from agents.company_agent import Company
from agents.household_agent import Household
from config import CONFIG_MODEL, SimulationConfig
from logger import log


class EconomicAgent(Protocol):
    """Protocol defining the minimum required attributes for tracked agents"""

    unique_id: str


class MetricsCollector:
    """
    Collects, aggregates, and exports economic metrics from simulation agents.

    Tracks data for multiple agent types over time and provides analysis functions
    to evaluate economic performance of the simulation.
    """

    bank_metrics: Dict[str, Dict[TimeStep, MetricDict]] = {}
    household_metrics: Dict[str, Dict[TimeStep, MetricDict]] = {}
    company_metrics: Dict[str, Dict[TimeStep, MetricDict]] = {}
    retailer_metrics: Dict[str, Dict[TimeStep, MetricDict]] = {}
    state_metrics: Dict[str, Dict[TimeStep, MetricDict]] = {}
    market_metrics: Dict[str, Dict[TimeStep, MetricDict]] = {}
    global_metrics: Dict[TimeStep, MetricDict] = {}
    registered_households: Set[str] = set()
    registered_companies: Set[str] = set()
    registered_retailers: Set[str] = set()
    registered_banks: Set[str] = set()
    metrics_config: Dict[str, Any] = {}
    export_path: Any = None
    latest_labor_metrics: Dict[str, float] = {}
    latest_global_metrics: MetricDict = {}
    config: SimulationConfig

    def __init__(self, config: Optional[SimulationConfig] = None):
        """Initialize the metrics collector."""
        self.config = config or CONFIG_MODEL
        self.bank_metrics = {}
        self.household_metrics = {}
        self.company_metrics = {}
        self.retailer_metrics = {}
        self.state_metrics = {}
        self.market_metrics = {}
        self.global_metrics = {}
        self.registered_households = set()
        self.registered_companies = set()
        self.registered_retailers = set()
        self.registered_banks = set()
        self.metrics_config = {}
        from pathlib import Path

        self.export_path = Path(self.config.metrics_export_path)

        self.latest_labor_metrics = {}
        self.latest_global_metrics = {}
        self.household_metrics_df = None
        self.company_metrics_df = None
        self.retailer_metrics_df = None
        self.bank_metrics_df = None
        self.state_metrics_df = None
        self.market_metrics_df = None
        self.global_metrics_df = None
        self.__post_init__()

    def __post_init__(self):
        """Initialize with configuration from SimulationConfig"""
        self.metrics_config = self.config.metrics_config
        self.setup_default_metrics_config()

        self.export_path.mkdir(parents=True, exist_ok=True)

    def setup_default_metrics_config(self):
        """Set up default configuration for tracked metrics if not specified in CONFIG"""
        default_metrics = {
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
                "critical_threshold": 0.6,
            },
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
                "critical_threshold": 0.1,
            },
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
            "gini_coefficient": {
                "enabled": True,
                "display_name": "Gini Coefficient",
                "unit": "",
                "aggregation": "value",
                "critical_threshold": 0.5,
            },
            "total_money_supply": {
                "enabled": True,
                "display_name": "Money Supply",
                "unit": "$",
                "aggregation": "value",
                "critical_threshold": None,
            },
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

        for metric_name, config in default_metrics.items():
            if metric_name not in self.metrics_config:
                self.metrics_config[metric_name] = config

    def add_metric(self, agent_id, metric_name, value, metric_dict, step):
        """Add a metric value for an agent."""
        agent_metrics = metric_dict.setdefault(agent_id, {})
        step_metrics = agent_metrics.setdefault(step, {})
        step_metrics[metric_name] = value

    def register_household(self, household):
        """Register a household agent for metrics tracking."""
        agent_id = household.unique_id
        if agent_id not in self.registered_households:
            self.registered_households.add(agent_id)
            self.household_metrics[agent_id] = {}
            log(
                f"MetricsCollector: Registered household {agent_id} for metrics tracking",
                level="DEBUG",
            )

    def register_company(self, company):
        """Register a company agent for metrics tracking."""
        agent_id = company.unique_id
        if agent_id not in self.registered_companies:
            self.registered_companies.add(agent_id)
            self.company_metrics[agent_id] = {}
            log(
                f"MetricsCollector: Registered company {agent_id} for metrics tracking",
                level="DEBUG",
            )

    def register_retailer(self, retailer):
        """Register a retailer agent for metrics tracking."""
        agent_id = retailer.unique_id
        if agent_id not in self.registered_retailers:
            self.registered_retailers.add(agent_id)
            self.retailer_metrics[agent_id] = {}
            log(
                f"MetricsCollector: Registered retailer {agent_id} for metrics tracking",
                level="DEBUG",
            )

    def register_bank(self, bank):
        """Register a bank agent for metrics tracking."""
        agent_id = bank.unique_id
        if agent_id not in self.registered_banks:
            self.registered_banks.add(agent_id)
            self.bank_metrics[agent_id] = {}
            log(f"MetricsCollector: Registered bank {agent_id} for metrics tracking", level="DEBUG")

    def register_market(self, market):
        """Register a market agent for metrics tracking."""
        agent_id = market.unique_id
        if agent_id not in self.market_metrics:
            self.market_metrics[agent_id] = {}
            log(
                f"MetricsCollector: Registered market {agent_id} for metrics tracking",
                level="DEBUG",
            )

    def collect_household_metrics(self, households, step):
        for household in households:
            agent_id = household.unique_id
            if agent_id not in self.household_metrics:
                self.register_household(household)

            step_metrics = {}
            for attr in [
                "checking_account",
                "savings",
                "income",
                "current_wage",
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
                    step_metrics[attr] = getattr(household, attr)

            total_wealth = float(getattr(household, "checking_account", 0.0)) + float(
                getattr(household, "savings", 0.0)
            )
            step_metrics["total_wealth"] = total_wealth
            self.household_metrics.setdefault(agent_id, {})[step] = step_metrics

    def collect_company_metrics(self, companies, step):
        for company in companies:
            agent_id = company.unique_id
            if agent_id not in self.company_metrics:
                self.register_company(company)

            step_metrics = {}
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
                    step_metrics[attr] = getattr(company, attr)

            if hasattr(company, "employees"):
                step_metrics["employees"] = int(len(company.employees))

            self.company_metrics.setdefault(agent_id, {})[step] = step_metrics

    def collect_retailer_metrics(self, retailers, step):
        for retailer in retailers:
            agent_id = retailer.unique_id
            if agent_id not in self.retailer_metrics:
                self.register_retailer(retailer)

            step_metrics = {}
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
                    step_metrics[attr] = getattr(retailer, attr)
            self.retailer_metrics.setdefault(agent_id, {})[step] = step_metrics

    def collect_bank_metrics(self, banks, step):
        for bank in banks:
            agent_id = bank.unique_id
            if agent_id not in self.bank_metrics:
                self.register_bank(bank)

            step_metrics = {}
            step_metrics["liquidity"] = float(getattr(bank, "liquidity", 0.0))
            if hasattr(bank, "sight_balance"):
                step_metrics["sight_balance"] = float(getattr(bank, "sight_balance", 0.0))

            if hasattr(bank, "credit_lines"):
                credit_lines = getattr(bank, "credit_lines")
                total_credit = float(sum(credit_lines.values()))
                step_metrics["total_credit"] = total_credit
                step_metrics["num_borrowers"] = int(len(credit_lines))

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

    def collect_state_metrics(self, state_id, state, households, companies, step):
        step_metrics = {
            "tax_revenue": float(getattr(state, "tax_revenue", 0.0)),
            "infrastructure_budget": float(getattr(state, "infrastructure_budget", 0.0)),
            "social_budget": float(getattr(state, "social_budget", 0.0)),
            "environment_budget": float(getattr(state, "environment_budget", 0.0)),
        }

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

    def collect_market_metrics(self, market, step):
        agent_id = market.unique_id
        if agent_id not in self.market_metrics:
            self.market_metrics[agent_id] = {}

        step_metrics = {}

        if hasattr(market, "registered_workers"):
            import statistics

            num_registered_workers = len(market.registered_workers)
            step_metrics["registered_workers"] = float(num_registered_workers)

            employed_workers = sum(
                1 for w in market.registered_workers if hasattr(w, "employed") and w.employed
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
                "unemployment_rate": float(1 - employment_rate)
                if num_registered_workers > 0
                else 0.0,
            }
        if hasattr(market, "list_of_assets"):
            import statistics

            num_assets = len(market.list_of_assets)
            step_metrics["num_assets"] = float(num_assets)

            if market.list_of_assets:
                average_asset_price = statistics.mean(market.list_of_assets.values())
                step_metrics["average_asset_price"] = float(average_asset_price)

        if step_metrics:
            self.market_metrics.setdefault(agent_id, {})[step] = step_metrics

    def calculate_global_metrics(self, step):
        """Calculate global economic metrics aggregated across all agents."""
        from metrics.calculator import (
            _global_money_metrics,
            _price_dynamics,
            _distribution_metrics,
            _wage_metrics,
            _environmental_metrics,
            _employment_metrics,
            _investment_metrics,
            _bankruptcy_metrics,
            _government_metrics,
            _global_activity_metrics,
        )
        from metrics.analyzer import _check_critical_thresholds

        metrics = {}
        money_metrics = _global_money_metrics(self, step)
        if "total_money_supply" not in money_metrics:
            m2 = money_metrics.get("m2_proxy")
            money_metrics["total_money_supply"] = float(cast(Any, m2)) if m2 is not None else 0.0
        metrics.update(money_metrics)

        activity_metrics = _global_activity_metrics(self, step)
        metrics.update(activity_metrics)

        market_cfg = getattr(CONFIG_MODEL, "market", None)
        pressure_ratio = getattr(market_cfg, "price_index_pressure_ratio", "money_supply")
        pressure_mode = str(pressure_ratio)

        m_supply = money_metrics.get("total_money_supply", money_metrics.get("m2_proxy", 0.0))
        money_for_price = float(cast(Any, m_supply)) if m_supply is not None else 0.0
        if pressure_mode == "blended":
            m1 = money_metrics.get("m1_proxy")
            money_for_price = float(cast(Any, m1)) if m1 is not None else 0.0

        gdp_val = activity_metrics.get("gdp")
        cons_val = activity_metrics.get("household_consumption")
        price_metrics = _price_dynamics(
            self,
            step,
            money_for_price,
            float(cast(Any, gdp_val)) if gdp_val is not None else 0.0,
            float(cast(Any, cons_val)) if cons_val is not None else 0.0,
        )
        metrics.update(price_metrics)

        metrics.update(_distribution_metrics(self, step))
        idx_val = price_metrics.get("price_index")
        metrics.update(
            _wage_metrics(self, step, float(cast(Any, idx_val)) if idx_val is not None else 1.0)
        )
        metrics.update(_environmental_metrics(self, step))
        metrics.update(_employment_metrics(self, step))

        gdp_val2 = activity_metrics.get("gdp")
        metrics.update(
            _investment_metrics(
                self, step, float(cast(Any, gdp_val2)) if gdp_val2 is not None else 0.0
            )
        )
        metrics.update(_bankruptcy_metrics(self, step))

        gdp_val3 = activity_metrics.get("gdp")
        metrics.update(
            _government_metrics(
                self, step, float(cast(Any, gdp_val3)) if gdp_val3 is not None else 0.0
            )
        )

        self.global_metrics[step] = metrics
        self.latest_global_metrics = metrics
        _check_critical_thresholds(self, metrics)

    def export_metrics(self):
        """Persist metrics to CSV (JSON export removed for performance)."""
        from metrics.exporter import export_metrics

        export_metrics(self)

    def _global_money_metrics(self, step):
        from metrics.calculator import _global_money_metrics

        return _global_money_metrics(self, step)

    def _price_dynamics(self, step, total_money, gdp, household_consumption):
        from metrics.calculator import _price_dynamics

        return _price_dynamics(self, step, total_money, gdp, household_consumption)

    def _aggregate_agent_metrics(self, agent_metrics, step, default="mean"):
        from metrics.analyzer import _aggregate_agent_metrics

        return _aggregate_agent_metrics(self, agent_metrics, step, default)

    def aggregate_metrics(self, step):
        from metrics.analyzer import aggregate_metrics

        return aggregate_metrics(self, step)

    def get_latest_macro_snapshot(self):
        from metrics.analyzer import get_latest_macro_snapshot

        return get_latest_macro_snapshot(self)

    def detect_economic_cycles(self):
        """Detect economic cycles like booms and recessions."""
        from metrics.analyzer import analyze_economic_cycles

        return analyze_economic_cycles(self)
