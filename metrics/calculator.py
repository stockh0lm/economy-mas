"""Calculator module - metric calculations."""

import math
import statistics
from typing import Any, Dict, List, Protocol, cast
from .base import MetricDict, TimeStep, ValueType


class LaborMarketMetricsSource(Protocol):
    registered_workers: List[object]


class FinancialMarketMetricsSource(Protocol):
    list_of_assets: Dict[str, float]


def _global_money_metrics(collector: Any, step: TimeStep) -> MetricDict:
    """Global monetary aggregates (diagnostic proxies)."""
    metrics: MetricDict = {}
    m1 = 0.0
    m2 = 0.0
    service_tx_volume = 0.0

    state_sight = 0.0
    for _sid, time_series in collector.state_metrics.items():
        data = time_series.get(step)
        if not data:
            continue
        state_sight += float(data.get("tax_revenue", 0.0))
        state_sight += float(data.get("infrastructure_budget", 0.0))
        state_sight += float(data.get("social_budget", 0.0))
        state_sight += float(data.get("environment_budget", 0.0))
    m1 += max(0.0, state_sight)
    m2 += max(0.0, state_sight)

    for _cid, time_series in collector.company_metrics.items():
        data = time_series.get(step)
        if not data:
            continue
        bal = float(data.get("sight_balance", 0.0))
        m1 += max(0.0, bal)
        m2 += max(0.0, bal)
        service_tx_volume += float(data.get("service_sales_total", 0.0))

    for _hid, time_series in collector.household_metrics.items():
        data = time_series.get(step)
        if not data:
            continue
        sight = float(data.get("sight_balance", data.get("checking_account", 0.0)))
        savings = float(data.get("savings_balance", data.get("savings", 0.0)))
        m1 += max(0.0, sight)
        m2 += max(0.0, sight) + max(0.0, savings)

    cc_exposure = 0.0
    inventory_total = 0.0
    sales_total = 0.0
    extinguish_volume = 0.0
    cc_headroom_total = 0.0
    cc_utilization_values = []
    retailers_at_cc_limit = 0
    retailers_stockout = 0
    retailers_count = 0
    for _rid, time_series in collector.retailer_metrics.items():
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

        headroom = max(0.0, cc_limit - abs(cc))
        cc_headroom_total += headroom
        if cc_limit > 0:
            cc_utilization_values.append(min(1.0, abs(cc) / cc_limit))
        if headroom <= 1e-9 and abs(cc) > 0:
            retailers_at_cc_limit += 1
        if inv <= 1e-9:
            retailers_stockout += 1

    bank_sight = 0.0
    for _bid, time_series in collector.bank_metrics.items():
        data = time_series.get(step)
        if not data:
            continue
        bank_sight += float(data.get("sight_balance", 0.0))
    m1 += max(0.0, bank_sight)
    m2 += max(0.0, bank_sight)

    issuance_volume = 0.0
    for _bid, time_series in collector.bank_metrics.items():
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
    collector: Any, step: TimeStep, total_money: float, gdp: float, household_consumption: float
) -> MetricDict:
    from config import CONFIG_MODEL

    metrics: MetricDict = {}
    price_index_base = float(collector.config.market.price_index_base)
    price_index_max = float(getattr(collector.config.market, "price_index_max", 1000.0))
    pressure_target = float(collector.config.market.price_index_pressure_target)
    price_sensitivity = float(collector.config.market.price_index_sensitivity)
    pressure_mode = str(
        getattr(
            getattr(CONFIG_MODEL, "market", None),
            "price_index_pressure_ratio",
            collector.config.market.price_index_pressure_ratio,
        )
    )
    eps = 1e-9

    money_supply_pressure = total_money / (gdp + eps) if gdp > 0 else pressure_target
    consumption_pressure = household_consumption / (gdp + eps) if gdp > 0 else pressure_target
    if pressure_mode == "consumption_to_production":
        price_pressure = consumption_pressure
    elif pressure_mode == "blended":
        price_pressure = 0.75 * money_supply_pressure + 0.25 * consumption_pressure
    else:
        price_pressure = money_supply_pressure

    if step > 0 and (step - 1) in collector.global_metrics:
        prev_price = float(collector.global_metrics[step - 1].get("price_index", price_index_base))
    else:
        prev_price = price_index_base

    if pressure_target > 0:
        desired_price = price_index_base * (price_pressure / pressure_target)
    else:
        desired_price = price_index_base

    current_price = prev_price + price_sensitivity * (desired_price - prev_price)
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


def _distribution_metrics(collector: Any, step: TimeStep) -> MetricDict:
    metrics: MetricDict = {}
    wealth_values = []
    for household_id, time_series in collector.household_metrics.items():
        data = time_series.get(step)
        if data:
            wealth_values.append(float(data.get("total_wealth", 0.0)))

    if wealth_values:
        metrics["gini_coefficient"] = _calculate_gini_coefficient(wealth_values)
    return metrics


def _calculate_gini_coefficient(values: List[float]) -> float:
    if not values or all(v == 0 for v in values):
        return 0.0

    sorted_values = sorted(values)
    n = len(sorted_values)
    cumsum = 0
    for i, value in enumerate(sorted_values):
        cumsum += (n - i) * value

    return (2 * cumsum) / (n * sum(sorted_values)) - (n + 1) / n if sum(sorted_values) > 0 else 0.0


def _wage_metrics(collector: Any, step: TimeStep, price_index: float) -> MetricDict:
    metrics: MetricDict = {}
    nominal_wages = []
    for household_id, time_series in collector.household_metrics.items():
        data = time_series.get(step)
        if data and data.get("employed"):
            w = data.get("current_wage", None)
            if isinstance(w, (int, float)) and float(w) > 0:
                nominal_wages.append(float(w))
            else:
                nominal_wages.append(float(data.get("income", 0.0)))

    avg_nominal_wage = statistics.mean(nominal_wages) if nominal_wages else 0
    price_index_pct = price_index / 100
    metrics["average_nominal_wage"] = avg_nominal_wage
    metrics["average_real_wage"] = avg_nominal_wage / price_index_pct if price_index_pct > 0 else 0
    return metrics


def _environmental_metrics(collector: Any, step: TimeStep) -> MetricDict:
    metrics: MetricDict = {}
    total_impact = 0.0
    for company_id, time_series in collector.company_metrics.items():
        data = time_series.get(step)
        if data:
            total_impact += float(data.get("environmental_impact", 0.0))

    for household_id, time_series in collector.household_metrics.items():
        data = time_series.get(step)
        if data:
            total_impact += float(data.get("environmental_impact", 0.0))

    metrics["total_environmental_impact"] = total_impact
    return metrics


def _employment_metrics(collector: Any, step: TimeStep) -> MetricDict:
    metrics: MetricDict = {}
    employed_count = 0
    total_households = 0

    def _is_truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes"}
        return False

    for household_id, time_series in collector.household_metrics.items():
        data = time_series.get(step)
        if data and "employed" in data:
            total_households += 1
            if _is_truthy(data["employed"]):
                employed_count += 1

    if total_households > 0:
        metrics["employment_rate"] = employed_count / total_households
        metrics["unemployment_rate"] = 1 - (employed_count / total_households)
    return metrics


def _investment_metrics(collector: Any, step: TimeStep, gdp: float) -> MetricDict:
    metrics: MetricDict = {}
    total_rd_investment = 0.0
    for company_id, time_series in collector.company_metrics.items():
        data = time_series.get(step)
        if data:
            total_rd_investment += float(data.get("rd_investment", 0.0))

    metrics["total_rd_investment"] = total_rd_investment
    metrics["investment_pct_gdp"] = total_rd_investment / gdp if gdp > 0 else 0
    return metrics


def _bankruptcy_metrics(collector: Any, step: TimeStep) -> MetricDict:
    metrics: MetricDict = {}
    bankruptcy_count = _count_bankruptcies_at_step(collector, step)
    total_companies = len(collector.registered_companies)
    if total_companies > 0:
        metrics["bankruptcy_rate"] = bankruptcy_count / total_companies
    return metrics


def _government_metrics(collector: Any, step: TimeStep, gdp: float) -> MetricDict:
    metrics: MetricDict = {}
    tax_revenue = 0.0
    govt_spending = 0.0
    for state_id, time_series in collector.state_metrics.items():
        data = time_series.get(step)
        if not data:
            continue
        tax_revenue += float(data.get("tax_revenue", 0.0))
        govt_spending += (
            float(data.get("infrastructure_budget", 0.0))
            + float(data.get("social_budget", 0.0))
            + float(data.get("environment_budget", 0.0))
        )

    metrics["tax_revenue"] = tax_revenue
    metrics["government_spending"] = govt_spending
    metrics["govt_spending_pct_gdp"] = govt_spending / gdp if gdp > 0 else 0
    metrics["budget_balance"] = tax_revenue - govt_spending
    return metrics


def _global_activity_metrics(collector: Any, step: TimeStep) -> MetricDict:
    metrics: MetricDict = {}
    gdp = 0.0
    for _company_id, time_series in collector.company_metrics.items():
        data = time_series.get(step)
        if data:
            gdp += float(data.get("production_capacity", 0.0))

    household_consumption = 0.0
    for _household_id, time_series in collector.household_metrics.items():
        data = time_series.get(step)
        if data:
            household_consumption += float(data.get("consumption", 0.0))

    metrics["gdp"] = gdp
    metrics["household_consumption"] = household_consumption
    metrics["consumption_pct_gdp"] = household_consumption / gdp if gdp > 0 else 0.0
    return metrics


def _count_bankruptcies_at_step(collector: Any, step: TimeStep) -> int:
    if step <= 1:
        return 0

    previous_step = step - 1
    bankruptcy_count = 0

    for company_id in collector.registered_companies.copy():
        has_prev_data = previous_step in collector.company_metrics.get(company_id, {})
        has_current_data = step in collector.company_metrics.get(company_id, {})

        if has_prev_data and not has_current_data:
            bankruptcy_count += 1

    return bankruptcy_count
