"""Analyzer module - analysis functions for metrics."""

import statistics
from typing import TypedDict


class EconomicCycleSnapshot(TypedDict):
    avg_growth_rate: float
    is_recession: bool
    is_boom: bool
    latest_growth: float
    growth_volatility: float


def apply_sight_decay(agents, *, config=None):
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
    from config import CONFIG_MODEL

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
            avg_daily = float(getattr(a, "income", 0.0))

        avg_monthly_spend = avg_daily * float(days_per_month)
        allowance = max(0.0, k * avg_monthly_spend)
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


def analyze_economic_cycles(collector):
    """Detect economic cycles like booms and recessions."""
    from metrics import MIN_GLOBAL_METRICS_POINTS

    if not collector.global_metrics or len(collector.global_metrics) < MIN_GLOBAL_METRICS_POINTS:
        return None

    steps = sorted(collector.global_metrics.keys())
    growth_values = []

    for i in range(1, len(steps)):
        current_step = steps[i]
        prev_step = steps[i - 1]

        if (
            "total_money_supply" in collector.global_metrics[current_step]
            and "total_money_supply" in collector.global_metrics[prev_step]
        ):
            current = collector.global_metrics[current_step]["total_money_supply"]
            prev = collector.global_metrics[prev_step]["total_money_supply"]

            if prev > 0:
                growth_rate = (current - prev) / prev
                growth_values.append(growth_rate)

    if not growth_values:
        return None

    recession_threshold = collector.config.market.recession_threshold
    boom_threshold = collector.config.market.boom_threshold

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


def get_latest_macro_snapshot(collector):
    snapshot = {}
    snapshot.update(collector.latest_global_metrics)
    snapshot.update(collector.latest_labor_metrics)
    return snapshot


def _check_critical_thresholds(collector, metrics):
    """Check if any metrics have crossed critical thresholds."""
    from logger import log

    for metric_name, value in metrics.items():
        if metric_name in collector.metrics_config:
            threshold = collector.metrics_config[metric_name].get("critical_threshold")
            if threshold is not None:
                if isinstance(value, (int, float)) and value >= threshold:
                    log(
                        f"CRITICAL: Metric {metric_name} value {value} has crossed threshold {threshold}",
                        level="WARNING",
                    )


def aggregate_metrics(collector, step):
    """Aggregate metrics across agent types for a given time step."""
    result: dict = {
        "market": {},
        "global": collector.global_metrics.get(step, {}),
    }

    household = _aggregate_agent_metrics(
        collector, collector.household_metrics, step, default="mean"
    )
    if household:
        result["household"] = household

    company = _aggregate_agent_metrics(collector, collector.company_metrics, step, default="mean")
    if company:
        result["company"] = company

    bank = _aggregate_agent_metrics(collector, collector.bank_metrics, step, default="sum")
    if bank:
        result["bank"] = bank

    state = _first_state_snapshot(collector.state_metrics, step)
    if state:
        result["state"] = state

    return result


def _first_state_snapshot(state_metrics, step):
    for _state_id, time_series in state_metrics.items():
        data = time_series.get(step)
        if data:
            return data
    return {}


def _aggregate_agent_metrics(collector, agent_metrics, step, default):
    from collections import defaultdict

    aggregated = {}
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
        aggregation = collector.metrics_config.get(metric, {}).get("aggregation", default)
        aggregated[metric] = _apply_aggregation(values, aggregation)

    return aggregated


def _apply_aggregation(values, aggregation):
    import statistics

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
