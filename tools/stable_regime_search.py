#!/usr/bin/env python3
"""Search stable simulation regimes with stronger scoring and early abort.

Extracted from investigation patch. Improved on three fronts:
- score favors robust, growing, equitable, solvent regimes;
- viability rejects shrinking and price-distorted pseudo-stability;
- candidate runs abort early once sustained instability is obvious.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import shutil
import sys
import time
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from logger import setup_logger
from main import load_config
from simulation.engine import SimulationEngine


class InstabilityMonitor:
    """Stop obviously broken runs before full horizon burns CPU."""

    def __init__(
        self,
        *,
        warmup_steps: int,
        patience: int,
        collapse_ratio_floor: float = 0.35,
        price_floor_factor: float = 0.20,
        price_ceiling_factor: float = 4.0,
        price_target: float = 100.0,
    ) -> None:
        self.warmup_steps = max(1, int(warmup_steps))
        self.patience = max(1, int(patience))
        self.collapse_ratio_floor = float(collapse_ratio_floor)
        self.price_floor = max(1e-9, float(price_target) * float(price_floor_factor))
        self.price_ceiling = max(self.price_floor, float(price_target) * float(price_ceiling_factor))
        self.reference_gdp: list[float] = []
        self.reference_sales: list[float] = []
        self.streaks: dict[str, int] = defaultdict(int)

    def _bump(self, key: str, active: bool) -> bool:
        self.streaks[key] = self.streaks[key] + 1 if active else 0
        return self.streaks[key] >= self.patience

    def observe(self, *, step: int, metrics: dict[str, Any]) -> str | None:
        gdp = as_float(metrics, "gdp")
        sales = as_float(metrics, "sales_total")
        price_index = as_float(metrics, "price_index")
        unemployment = as_float(metrics, "unemployment_rate")
        cc_limit_share = as_float(metrics, "retailers_at_cc_limit_share")
        stockout_share = as_float(metrics, "retailers_stockout_share")
        total_households = int(as_float(metrics, "total_households"))
        total_companies = int(as_float(metrics, "total_companies"))
        total_retailers = int(as_float(metrics, "total_retailers"))

        finite_values = [gdp, sales, price_index, unemployment, cc_limit_share, stockout_share]
        if any(not math.isfinite(value) for value in finite_values):
            return "non_finite_metrics"
        if total_households < 2:
            return "household_extinction"
        if total_companies < 1:
            return "company_extinction"
        if total_retailers < 1:
            return "retailer_extinction"
        if price_index <= 0.0:
            return "non_positive_price_index"

        if step < self.warmup_steps:
            if gdp > 0:
                self.reference_gdp.append(gdp)
            if sales > 0:
                self.reference_sales.append(sales)
            return None

        reference_gdp = mean(self.reference_gdp) if self.reference_gdp else max(gdp, 1.0)
        reference_sales = mean(self.reference_sales) if self.reference_sales else max(sales, 1.0)

        if self._bump("price_distortion", price_index < self.price_floor or price_index > self.price_ceiling):
            return "price_distortion"
        if self._bump("demand_collapse", sales < reference_sales * self.collapse_ratio_floor):
            return "sales_collapse"
        if self._bump("output_collapse", gdp < reference_gdp * self.collapse_ratio_floor):
            return "gdp_collapse"
        if self._bump("unemployment", unemployment >= 0.95):
            return "mass_unemployment"
        if self._bump("retailer_credit_gridlock", cc_limit_share >= 0.98):
            return "credit_gridlock"
        if self._bump("retailer_stockout_gridlock", stockout_share >= 0.98):
            return "stockout_gridlock"
        return None


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def path_for_config(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def as_float(row: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value is None or value == "":
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = mean(values)
    return math.sqrt(sum((value - mu) ** 2 for value in values) / (len(values) - 1))


def gini_coefficient(values: list[float]) -> float:
    cleaned = sorted(max(0.0, float(value)) for value in values if math.isfinite(float(value)))
    if not cleaned:
        return 0.0
    total = sum(cleaned)
    if total <= 0.0:
        return 0.0
    n = len(cleaned)
    weighted_sum = sum((idx + 1) * value for idx, value in enumerate(cleaned))
    return max(0.0, min(1.0, (2.0 * weighted_sum) / (n * total) - (n + 1) / n))


def smooth_growth_signal(ratio: float, *, midpoint: float = 1.02, steepness: float = 10.0) -> float:
    if ratio <= 0 or not math.isfinite(ratio):
        return -1.0
    return 2.0 / (1.0 + math.exp(-steepness * (ratio - midpoint))) - 1.0


def symmetric_price_deviation(price_level: float, *, target: float = 100.0) -> float:
    if price_level <= 0 or target <= 0:
        return 1_000_000.0
    return price_level / target + target / price_level - 2.0


def flatten_params(data: dict[str, Any], prefix: str = "param") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        name = f"{prefix}.{key}"
        if isinstance(value, dict):
            out.update(flatten_params(value, name))
        else:
            out[name] = value
    return out


def collector_global_rows(global_metrics: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in sorted(global_metrics):
        row = {"time_step": int(step)}
        row.update(global_metrics[step])
        rows.append(row)
    return rows


def collector_agent_rows(agent_metrics: dict[str, dict[int, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for agent_id in sorted(agent_metrics):
        for step in sorted(agent_metrics[agent_id]):
            row = {"time_step": int(step), "agent_id": str(agent_id)}
            row.update(agent_metrics[agent_id][step])
            rows.append(row)
    return rows


def rows_by_step(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(as_float(row, "time_step"))].append(row)
    return grouped


def _window_step_ids(
    rows: list[dict[str, Any]], *, position: str, fraction: float = 0.25, maximum: int = 60
) -> list[int]:
    if not rows:
        return []
    ordered_steps = sorted(int(as_float(row, "time_step")) for row in rows)
    if len(ordered_steps) == 1:
        return ordered_steps
    target_n = max(1, int(len(ordered_steps) * fraction))
    keep_n = min(maximum, max(1, target_n), len(ordered_steps) // 2)
    if position == "head":
        return ordered_steps[:keep_n]
    if position == "tail":
        return ordered_steps[-keep_n:]
    raise ValueError(f"unknown window position: {position}")


def tail_steps(rows: list[dict[str, Any]], *, maximum: int = 60) -> list[int]:
    return _window_step_ids(rows, position="tail", maximum=maximum)


def first_steps(rows: list[dict[str, Any]], *, maximum: int = 60) -> list[int]:
    return _window_step_ids(rows, position="head", maximum=maximum)


def growth_ratio(values: list[float]) -> float:
    if not values or len(values) == 1:
        return 1.0
    split = max(1, len(values) // 2)
    head = values[:split]
    tail = values[split:]
    if not tail:
        return 1.0
    return mean(tail) / max(1e-9, mean(head))


def metric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [as_float(row, key) for row in rows]


def mean_for_steps(rows: list[dict[str, Any]], key: str, steps: set[int]) -> float:
    return mean([as_float(row, key) for row in rows if int(as_float(row, "time_step")) in steps])


def max_for_steps(rows: list[dict[str, Any]], key: str, steps: set[int]) -> float:
    values = [as_float(row, key) for row in rows if int(as_float(row, "time_step")) in steps]
    return max(values) if values else 0.0


def corrected_gini_tail(household_rows: list[dict[str, Any]], steps: set[int]) -> tuple[float, float]:
    grouped = rows_by_step(household_rows)
    gini_series: list[float] = []
    wealth_tail: list[float] = []
    for step in sorted(steps):
        wealth_values: list[float] = []
        for row in grouped.get(step, []):
            wealth = as_float(row, "total_wealth")
            if wealth == 0.0:
                wealth = as_float(row, "checking_account") + as_float(row, "savings")
            wealth_values.append(max(0.0, wealth))
        if wealth_values:
            gini_series.append(gini_coefficient(wealth_values))
            wealth_tail.extend(wealth_values)
    return mean(gini_series), max(wealth_tail) if wealth_tail else 0.0


def state_budget_stock_series(state_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for row in state_rows:
        total = (
            as_float(row, "infrastructure_budget")
            + as_float(row, "social_budget")
            + as_float(row, "environment_budget")
        )
        series.append({"time_step": int(as_float(row, "time_step")), "state_budget_stock": total})
    return series


def summarize_run(
    *,
    global_rows: list[dict[str, Any]],
    household_rows: list[dict[str, Any]],
    company_rows: list[dict[str, Any]],
    retailer_rows: list[dict[str, Any]],
    bank_rows: list[dict[str, Any]],
    state_rows: list[dict[str, Any]],
    returncode: int,
    elapsed_s: float,
    requested_steps: int,
    price_target: float,
    aborted_early: bool,
    abort_reason: str | None,
) -> dict[str, Any]:
    if not global_rows:
        return {
            "returncode": returncode,
            "elapsed_s": elapsed_s,
            "requested_steps": requested_steps,
            "steps_recorded": 0,
            "completed_ratio": 0.0,
            "aborted_early": aborted_early,
            "abort_reason": abort_reason or "no_global_metrics",
            "viable": False,
            "score": -1_000_000.0,
            "reason": abort_reason or "no_global_metrics",
        }

    final = global_rows[-1]
    steps_recorded = len(global_rows)
    tail_step_ids = set(tail_steps(global_rows))
    head_step_ids = set(first_steps(global_rows))
    tail = [row for row in global_rows if int(as_float(row, "time_step")) in tail_step_ids]
    head = [row for row in global_rows if int(as_float(row, "time_step")) in head_step_ids]

    sales_tail = metric_values(tail, "sales_total")
    gdp_tail = metric_values(tail, "gdp")
    issuance_tail = metric_values(tail, "issuance_volume")
    price_tail = metric_values(tail, "price_index")
    env_tail = metric_values(tail, "total_environmental_impact")

    sales_avg = mean(sales_tail)
    gdp_avg = mean(gdp_tail)
    issuance_avg = mean(issuance_tail)
    price_avg = mean(price_tail)
    env_avg = mean(env_tail)
    gdp_growth_ratio = growth_ratio(gdp_tail)
    sales_growth_ratio = growth_ratio(sales_tail)
    env_growth_ratio = growth_ratio(env_tail)

    sales_reference = mean(metric_values(head, "sales_total"))
    gdp_reference = mean(metric_values(head, "gdp"))
    sales_floor_ratio = sales_avg / max(1e-9, sales_reference)
    gdp_floor_ratio = gdp_avg / max(1e-9, gdp_reference)

    price_cv = stdev(price_tail) / max(1e-9, abs(price_avg))
    sales_cv = stdev(sales_tail) / max(1e-9, abs(sales_avg))
    gdp_cv = stdev(gdp_tail) / max(1e-9, abs(gdp_avg))
    price_deviation = symmetric_price_deviation(price_avg, target=price_target)

    tail_unemployment = mean_for_steps(tail, "unemployment_rate", tail_step_ids)
    tail_employment = mean_for_steps(tail, "employment_rate", tail_step_ids)
    tail_cc_limit_max = max_for_steps(tail, "retailers_at_cc_limit_share", tail_step_ids)
    tail_stockout_max = max_for_steps(tail, "retailers_stockout_share", tail_step_ids)
    bankruptcy_rate_max = max(metric_values(global_rows, "bankruptcy_rate") or [0.0])
    company_deaths = max(metric_values(global_rows, "company_deaths") or [0.0])
    retailer_deaths = max(metric_values(global_rows, "retailer_deaths") or [0.0])

    min_company_balance = min(metric_values(company_rows, "sight_balance") or [0.0])
    retailer_headrooms = [as_float(row, "cc_limit") + as_float(row, "cc_balance") for row in retailer_rows]
    min_retailer_headroom = min(retailer_headrooms) if retailer_headrooms else 0.0
    bank_sight_tail = mean_for_steps(bank_rows, "sight_balance", tail_step_ids)

    gini_tail_avg, max_household_wealth_tail = corrected_gini_tail(household_rows, tail_step_ids)
    env_intensity_tail = env_avg / max(1e-9, gdp_avg)

    state_series = state_budget_stock_series(state_rows)
    state_tail_avg = mean_for_steps(state_series, "state_budget_stock", tail_step_ids)
    state_head_avg = mean_for_steps(state_series, "state_budget_stock", head_step_ids)
    state_budget_ratio = state_tail_avg / max(1e-9, state_head_avg) if state_series else 1.0
    budget_balance_tail_avg = mean_for_steps(global_rows, "budget_balance", tail_step_ids)

    final_companies = as_float(final, "total_companies")
    final_retailers = as_float(final, "total_retailers")
    final_households = as_float(final, "total_households")
    completed_ratio = steps_recorded / max(1, requested_steps)

    hard_checks = {
        "returncode_zero": returncode == 0,
        "not_aborted_early": not aborted_early,
        "full_horizon_completed": steps_recorded >= requested_steps,
        "households_survive": final_households >= 2,
        "companies_survive": final_companies >= 1,
        "retailers_survive": final_retailers >= 1,
        "positive_sales": sales_avg > 0.1,
        "positive_gdp": gdp_avg > 0.1,
        "positive_issuance": issuance_avg > 0.01,
        "price_not_broken": 25.0 <= price_avg <= 300.0 and price_deviation <= 2.0,
        "no_deep_output_collapse": gdp_floor_ratio >= 0.55,
        "no_deep_sales_collapse": sales_floor_ratio >= 0.55,
        "unemployment_not_extreme": tail_unemployment <= 0.25,
        "retailer_credit_not_frozen": tail_cc_limit_max < 0.95,
        "retailer_supply_not_frozen": tail_stockout_max < 0.95,
    }
    soft_checks = {
        "gdp_growth_band": 0.90 <= gdp_growth_ratio <= 1.25,
        "sales_growth_band": 0.90 <= sales_growth_ratio <= 1.25,
        "price_near_target": 50.0 <= price_avg <= 180.0 and price_deviation <= 0.35,
        "volatility_reasonable": gdp_cv <= 0.60 and sales_cv <= 0.75 and price_cv <= 0.25,
        "unemployment_low": tail_unemployment <= 0.12,
        "retailer_headroom_good": tail_cc_limit_max < 0.75 and tail_stockout_max < 0.60,
        "distribution_reasonable": gini_tail_avg <= 0.60,
        "environment_not_accelerating": env_growth_ratio <= 1.15,
        "state_budget_resilient": state_budget_ratio >= 0.50,
        "budget_balance_not_deeply_negative": budget_balance_tail_avg >= -max(50.0, state_tail_avg * 0.25),
    }
    soft_passes = sum(1 for ok in soft_checks.values() if ok)
    viable = all(hard_checks.values()) and soft_passes >= 7
    failed_checks = [name for name, ok in {**hard_checks, **soft_checks}.items() if not ok]

    score = 0.0
    score += 50_000.0 if viable else -50_000.0
    score += min(3_000.0, sales_avg * 5.0)
    score += min(3_000.0, gdp_avg * 2.0)
    score += min(1_200.0, issuance_avg * 10.0)
    score += 1_500.0 * smooth_growth_signal(gdp_growth_ratio, midpoint=1.03)
    score += 1_200.0 * smooth_growth_signal(sales_growth_ratio, midpoint=1.03)
    score += 900.0 * max(0.0, min(1.0, tail_employment))
    score += 600.0 * max(0.0, min(1.0, state_budget_ratio))
    score -= 30_000.0 * max(0.0, tail_cc_limit_max - 0.25)
    score -= 22_000.0 * max(0.0, tail_stockout_max - 0.35)
    score -= 3_000.0 * (company_deaths + retailer_deaths)
    score -= 2_000.0 * bankruptcy_rate_max
    score -= 350.0 * sales_cv
    score -= 250.0 * gdp_cv
    score -= 150.0 * price_cv
    score -= 2_500.0 * max(0.0, tail_unemployment - 0.08)
    score -= 700.0 * price_deviation
    score -= 2_200.0 * max(0.0, 0.95 - gdp_growth_ratio)
    score -= 1_800.0 * max(0.0, 0.95 - sales_growth_ratio)
    score -= 1_200.0 * max(0.0, gdp_growth_ratio - 1.25)
    score -= 1_000.0 * max(0.0, sales_growth_ratio - 1.25)
    score -= 4_000.0 * max(0.0, 0.35 - state_budget_ratio)
    score -= 6_000.0 * max(0.0, gini_tail_avg - 0.35)
    score -= 800.0 * env_intensity_tail
    score -= 1_500.0 * max(0.0, env_growth_ratio - 1.05)
    score -= 0.5 * max(0.0, -budget_balance_tail_avg)
    score -= max(0.0, -min_company_balance) * 5.0
    score -= max(0.0, -min_retailer_headroom) * 3.0
    if aborted_early:
        score -= 12_000.0
        score -= 8_000.0 * max(0.0, 1.0 - completed_ratio)

    if viable:
        reason = "viable"
    elif abort_reason:
        reason = abort_reason
    else:
        preview = ",".join(failed_checks[:4])
        suffix = "..." if len(failed_checks) > 4 else ""
        reason = f"viability_failed:{preview}{suffix}" if failed_checks else "failed_viability_filters"
    return {
        "returncode": returncode,
        "elapsed_s": elapsed_s,
        "requested_steps": requested_steps,
        "steps_recorded": steps_recorded,
        "completed_ratio": completed_ratio,
        "aborted_early": aborted_early,
        "abort_reason": abort_reason or "",
        "viable": viable,
        "reason": reason,
        "failed_checks": ";".join(failed_checks),
        "soft_pass_count": soft_passes,
        "soft_check_count": len(soft_checks),
        "score": round(score, 6),
        "final_households": final_households,
        "final_companies": final_companies,
        "final_retailers": final_retailers,
        "tail_sales_avg": sales_avg,
        "tail_gdp_avg": gdp_avg,
        "tail_issuance_avg": issuance_avg,
        "tail_stockout_max": tail_stockout_max,
        "tail_cc_limit_max": tail_cc_limit_max,
        "tail_unemployment_avg": tail_unemployment,
        "tail_employment_avg": tail_employment,
        "final_employment_rate": as_float(final, "employment_rate"),
        "final_m1_proxy": as_float(final, "m1_proxy"),
        "final_m2_proxy": as_float(final, "m2_proxy"),
        "final_price_index": as_float(final, "price_index"),
        "tail_price_avg": price_avg,
        "price_symmetric_deviation_tail": price_deviation,
        "price_cv_tail": price_cv,
        "sales_cv_tail": sales_cv,
        "gdp_cv_tail": gdp_cv,
        "gdp_growth_ratio_tail": gdp_growth_ratio,
        "sales_growth_ratio_tail": sales_growth_ratio,
        "gdp_floor_ratio_tail": gdp_floor_ratio,
        "sales_floor_ratio_tail": sales_floor_ratio,
        "company_deaths_max": company_deaths,
        "retailer_deaths_max": retailer_deaths,
        "bank_sight_tail_avg": bank_sight_tail,
        "gini_tail_avg": gini_tail_avg,
        "max_household_wealth_tail": max_household_wealth_tail,
        "tail_environmental_impact_avg": env_avg,
        "environmental_impact_intensity_tail": env_intensity_tail,
        "environmental_impact_growth_ratio_tail": env_growth_ratio,
        "state_budget_tail_avg": state_tail_avg,
        "state_budget_ratio_tail": state_budget_ratio,
        "budget_balance_tail_avg": budget_balance_tail_avg,
    }


def uniform(rng: random.Random, lo: float, hi: float) -> float:
    return lo + (hi - lo) * rng.random()


def loguniform(rng: random.Random, lo: float, hi: float) -> float:
    return math.exp(math.log(lo) + (math.log(hi) - math.log(lo)) * rng.random())


def randint(rng: random.Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)


def candidate_overlay(rng: random.Random, *, steps: int, seed: int, out_dir: Path) -> dict[str, Any]:
    households = randint(rng, 12, 28)
    companies = randint(rng, 4, 10)
    retailers = randint(rng, 2, 6)
    regions = max(1, min(retailers, randint(rng, 1, 3)))

    household_sight = uniform(rng, 100.0, 400.0)
    household_savings = uniform(rng, 10.0, 180.0)
    company_sight = uniform(rng, 300.0, 1_500.0)
    company_stock = uniform(rng, 24.0, 220.0)
    retailer_sight = uniform(rng, 40.0, 300.0)
    retailer_stock_units = uniform(rng, 8.0, 60.0)
    unit_cost = uniform(rng, 8.0, 14.0)
    cc_limit = uniform(rng, 1_000.0, 4_000.0)
    target_inventory = uniform(rng, 220.0, 1_000.0)

    tax_rate = uniform(rng, 0.0, 0.02)
    env_tax = uniform(rng, 0.0, 0.01)
    fee = uniform(rng, 0.0, 0.02)
    risk_pool_rate = uniform(rng, 0.0, 0.002)
    household_income = uniform(rng, 85.0, 135.0)
    consumption_rate_normal = uniform(rng, 0.70, 0.95)
    consumption_rate_growth = uniform(rng, consumption_rate_normal, 0.98)

    overlay: dict[str, Any] = {
        "simulation_steps": int(steps),
        "logging_level": "WARNING",
        "log_file": path_for_config(out_dir / "simulation.log"),
        "metrics_export_path": path_for_config(out_dir / "metrics"),
        "population": {
            "seed": int(seed),
            "num_households": households,
            "num_companies": companies,
            "num_retailers": retailers,
            "household_template": {
                "income": household_income,
                "initial_sight_balance": household_sight,
                "initial_local_savings": household_savings,
                "land_area": uniform(rng, 20.0, 60.0),
                "environmental_impact": uniform(rng, 0.2, 1.8),
            },
            "company_template": {
                "production_capacity": uniform(rng, 70.0, 150.0),
                "initial_sight_balance": company_sight,
                "initial_finished_goods_units": company_stock,
                "land_area": uniform(rng, 50.0, 140.0),
                "environmental_impact": uniform(rng, 1.0, 5.0),
            },
            "retailer_template": {
                "initial_cc_limit": cc_limit,
                "target_inventory_value": target_inventory,
                "initial_sight_balance": retailer_sight,
                "initial_inventory_units": retailer_stock_units,
                "initial_inventory_unit_cost": unit_cost,
                "land_area": uniform(rng, 10.0, 35.0),
                "environmental_impact": uniform(rng, 0.2, 1.5),
            },
        },
        "spatial": {
            "num_regions": regions,
            "local_trade_bias": uniform(rng, 0.55, 0.95),
        },
        "time": {
            "days_per_month": 30,
            "seed": int(seed),
        },
        "tax_rates": {
            "bodensteuer": tax_rate,
            "umweltsteuer": env_tax,
        },
        "household": {
            "base_income": household_income,
            "consumption_rate_normal": consumption_rate_normal,
            "consumption_rate_growth": consumption_rate_growth,
            "savings_rate": uniform(rng, 0.02, 0.18),
            "transaction_buffer": uniform(rng, 5.0, 50.0),
            "fertility_base_annual": uniform(rng, 0.0, 0.001),
            "mortality_base_annual": uniform(rng, 0.0, 0.004),
            "mortality_senescence_annual": uniform(rng, 0.02, 0.10),
        },
        "company": {
            "bankruptcy_underpay_steps": randint(rng, 60, 240),
            "employee_capacity_ratio": uniform(rng, 4.0, 8.0),
            "investment_threshold": uniform(rng, 4_000.0, 20_000.0),
            "growth_threshold": randint(rng, 900, 5_000),
            "growth_investment_factor": uniform(rng, 0.0, 0.02),
            "rd_investment_trigger_balance": uniform(rng, 2_000.0, 20_000.0),
            "rd_investment_rate": uniform(rng, 0.0, 0.03),
            "profit_distribution_fraction": uniform(rng, 0.55, 0.95),
            "profit_retention_buffer": uniform(rng, 30.0, 250.0),
            "production_target_stock_days": uniform(rng, 5.0, 18.0),
            "production_min_utilization": loguniform(rng, 0.001, 0.03),
            "production_ramp_sensitivity": uniform(rng, 0.8, 2.2),
            "inventory_depreciation_rate": uniform(rng, 0.0, 0.001),
            "inventory_holding_cost_per_unit": uniform(rng, 0.0, 0.015),
            "price_inventory_floor": uniform(rng, 0.80, 0.98),
            "price_inventory_ceiling": uniform(rng, 1.03, 1.20),
            "base_wage": uniform(rng, 3.0, 7.0),
            "founding_base_annual": 0.0,
            "merger_rate_annual": 0.0,
        },
        "retailer": {
            "initial_cc_limit": cc_limit,
            "target_inventory_value": target_inventory,
            "working_capital_buffer": uniform(rng, 15.0, 120.0),
            "price_markup": uniform(rng, 0.03, 0.20),
            "price_markup_min": uniform(rng, 0.0, 0.08),
            "price_markup_max": uniform(rng, 0.12, 0.32),
            "obsolescence_rate": uniform(rng, 0.0, 0.0008),
            "restock_target_stock_days": uniform(rng, 5.0, 20.0),
            "restock_min_target_value": uniform(rng, 20.0, 120.0),
            "restock_bootstrap_order_value": uniform(rng, 40.0, 250.0),
            "restock_flow_replenishment_multiple": uniform(rng, 0.8, 2.2),
        },
        "bank": {
            "base_account_fee": fee,
            "positive_balance_fee_rate": 0.0,
            "negative_balance_fee_rate": 0.0,
            "risk_pool_rate": risk_pool_rate,
            "fee_recirculation_rate": 1.0,
            "cc_limit_multiplier": uniform(rng, 1.5, 4.5),
            "cc_limit_max_monthly_decrease": uniform(rng, 0.05, 0.25),
            "cc_limit_audit_risk_penalty": uniform(rng, 0.1, 0.6),
            "initial_liquidity": uniform(rng, 800.0, 3_000.0),
            "initial_sight_balance": uniform(rng, 0.0, 150.0),
        },
        "clearing": {
            "audit_interval": 90,
            "required_reserve_ratio": uniform(rng, 0.05, 0.15),
            "retailer_resolution_audit_failures": randint(rng, 3, 6),
            "sight_excess_decay_rate": 0.0,
        },
        "state": {
            "initial_tax_revenue": uniform(rng, 20.0, 150.0),
            "initial_infrastructure_budget": uniform(rng, 20.0, 250.0),
            "initial_social_budget": uniform(rng, 80.0, 600.0),
            "initial_environment_budget": uniform(rng, 20.0, 180.0),
        },
        "market": {
            "price_index_pressure_ratio": rng.choice(
                ["money_supply_to_gdp", "consumption_to_production", "blended"]
            ),
            "price_index_sensitivity": uniform(rng, 0.01, 0.08),
            "price_index_pressure_target": uniform(rng, 0.9, 1.8),
            "price_index_max": 1_000.0,
        },
    }

    if overlay["retailer"]["price_markup_min"] > overlay["retailer"]["price_markup"]:
        overlay["retailer"]["price_markup_min"] = max(
            0.0, overlay["retailer"]["price_markup"] * 0.5
        )
    if overlay["retailer"]["price_markup_max"] < overlay["retailer"]["price_markup"]:
        overlay["retailer"]["price_markup_max"] = overlay["retailer"]["price_markup"] + 0.05

    return overlay


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def run_candidate(
    *,
    config_path: Path,
    timeout_s: float,
    abort_warmup: int,
    abort_patience: int,
) -> dict[str, Any]:
    start = time.time()
    returncode = 0
    aborted_early = False
    abort_reason: str | None = None
    engine: SimulationEngine | None = None
    config = load_config(config_path)

    try:
        setup_logger(
            level=config.logging_level,
            log_file=config.log_file,
            log_format=config.log_format,
            file_mode="w",
            config=config,
        )
        engine = SimulationEngine(config)
        monitor = InstabilityMonitor(
            warmup_steps=min(int(config.simulation_steps) - 1, abort_warmup),
            patience=abort_patience,
            price_target=float(config.market.price_index_base),
        )

        for step in range(int(config.simulation_steps)):
            if time.time() - start > timeout_s:
                returncode = 124
                aborted_early = True
                abort_reason = "timeout"
                break

            engine.step()
            snapshot: dict[str, Any] = dict(engine.collector.global_metrics.get(step, {}))
            snapshot.setdefault("total_households", len(engine.households))
            snapshot.setdefault("total_companies", len(engine.companies))
            snapshot.setdefault("total_retailers", len(engine.retailers))
            reason = monitor.observe(step=step, metrics=snapshot)
            if reason:
                returncode = 2
                aborted_early = True
                abort_reason = reason
                break
    except Exception as exc:  # pragma: no cover - exercised by live runs, not unit tests
        returncode = 1
        aborted_early = True
        abort_reason = f"exception:{type(exc).__name__}"
    elapsed_s = time.time() - start

    global_rows: list[dict[str, Any]] = []
    household_rows: list[dict[str, Any]] = []
    company_rows: list[dict[str, Any]] = []
    retailer_rows: list[dict[str, Any]] = []
    bank_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []

    if engine is not None:
        try:
            engine.collector.export_metrics()
        except Exception:
            pass
        global_rows = collector_global_rows(engine.collector.global_metrics)
        household_rows = collector_agent_rows(engine.collector.household_metrics)
        company_rows = collector_agent_rows(engine.collector.company_metrics)
        retailer_rows = collector_agent_rows(engine.collector.retailer_metrics)
        bank_rows = collector_agent_rows(engine.collector.bank_metrics)
        state_rows = collector_agent_rows(engine.collector.state_metrics)

    summary = summarize_run(
        global_rows=global_rows,
        household_rows=household_rows,
        company_rows=company_rows,
        retailer_rows=retailer_rows,
        bank_rows=bank_rows,
        state_rows=state_rows,
        returncode=returncode,
        elapsed_s=elapsed_s,
        requested_steps=int(config.simulation_steps),
        price_target=float(config.market.price_index_base),
        aborted_early=aborted_early,
        abort_reason=abort_reason,
    )
    return summary


def evaluate_generation(
    *,
    base_config: dict[str, Any],
    overlays: list[dict[str, Any]],
    out_root: Path,
    label: str,
    timeout_s: float,
    abort_warmup: int,
    abort_patience: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, overlay in enumerate(overlays):
        run_id = f"{label}_{idx:04d}"
        run_dir = out_root / "runs" / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        cfg = deep_merge(base_config, overlay)
        cfg["log_file"] = path_for_config(run_dir / "simulation.log")
        cfg["metrics_export_path"] = path_for_config(run_dir / "metrics")
        config_path = out_root / "configs" / f"{run_id}.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

        summary = run_candidate(
            config_path=config_path,
            timeout_s=timeout_s,
            abort_warmup=abort_warmup,
            abort_patience=abort_patience,
        )
        row = {
            "run_id": run_id,
            "config_path": path_for_config(config_path),
            "metrics_dir": path_for_config(run_dir / "metrics"),
            **summary,
            **flatten_params(overlay),
        }
        rows.append(row)
        print(
            f"{run_id}: score={row['score']:.1f} viable={row['viable']} "
            f"steps={row['steps_recorded']}/{row['requested_steps']} abort={row['abort_reason'] or '-'} "
            f"sales_tail={float(row.get('tail_sales_avg', 0.0)):.2f} "
            f"gdp_tail={float(row.get('tail_gdp_avg', 0.0)):.2f}",
            flush=True,
        )
    return rows


def promote_from_config(path: Path, *, steps: int, out_dir: Path) -> dict[str, Any]:
    cfg = load_yaml(path)
    cfg["simulation_steps"] = int(steps)
    cfg["log_file"] = path_for_config(out_dir / "simulation.log")
    cfg["metrics_export_path"] = path_for_config(out_dir / "metrics")
    return cfg


def parse_int_list(raw: str) -> list[int]:
    values = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise ValueError("expected at least one integer")
    return values


def stage_plan(args: argparse.Namespace) -> tuple[list[int], list[int]]:
    uses_legacy_flags = args.short_steps is not None or args.long_steps is not None or args.keep is not None
    uses_stage_flags = args.stage_steps is not None or args.stage_keep is not None
    if uses_legacy_flags and uses_stage_flags:
        raise ValueError("do not mix deprecated short/long/keep flags with stage-steps/stage-keep")
    if uses_legacy_flags:
        short_steps = int(args.short_steps if args.short_steps is not None else 720)
        long_steps = int(args.long_steps if args.long_steps is not None else 5_400)
        keep = int(args.keep if args.keep is not None else 12)
        return [short_steps, long_steps], [keep]

    steps = parse_int_list(args.stage_steps or "720,2160,5400")
    if len(steps) < 2:
        raise ValueError("stage-steps needs at least two stages")
    keep_counts = parse_int_list(args.stage_keep or "24,8")
    if len(keep_counts) != len(steps) - 1:
        raise ValueError("stage-keep count must equal len(stage-steps) - 1")
    return steps, keep_counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("configs/crash_reproduction_minimal.yaml"))
    parser.add_argument("--out", type=Path, default=Path("output/stable_regime_search"))
    parser.add_argument("--seed", type=int, default=20260524)
    parser.add_argument("--trials", type=int, default=96)
    parser.add_argument("--stage-steps", type=str, default=None)
    parser.add_argument("--stage-keep", type=str, default=None)
    parser.add_argument("--short-steps", type=int, default=None)
    parser.add_argument("--long-steps", type=int, default=None)
    parser.add_argument("--keep", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--abort-warmup", type=int, default=90)
    parser.add_argument("--abort-patience", type=int, default=24)
    parser.add_argument("--clean", action="store_true", help="remove output directory first")
    args = parser.parse_args()

    try:
        stage_steps, stage_keep = stage_plan(args)
    except ValueError as exc:
        parser.error(str(exc))
    base_path = args.base if args.base.is_absolute() else ROOT / args.base
    out_root = args.out if args.out.is_absolute() else ROOT / args.out
    if args.clean and out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    base_config = load_yaml(base_path)
    rng = random.Random(args.seed)

    candidate_configs: list[dict[str, Any]] = []
    for idx in range(int(args.trials)):
        trial_seed = args.seed + idx * 9_973
        run_dir = out_root / "runs" / f"stage0_{idx:04d}"
        candidate_configs.append(
            candidate_overlay(rng, steps=stage_steps[0], seed=trial_seed, out_dir=run_dir)
        )

    stage_rows: list[list[dict[str, Any]]] = []
    current_overlays = candidate_configs
    for stage_idx, steps in enumerate(stage_steps):
        label = f"stage{stage_idx + 1}"
        stage_timeout = float(args.timeout) * max(1.0, steps / max(1, stage_steps[0]))
        rows = evaluate_generation(
            base_config=base_config if stage_idx == 0 else {},
            overlays=current_overlays,
            out_root=out_root,
            label=label,
            timeout_s=stage_timeout,
            abort_warmup=args.abort_warmup,
            abort_patience=args.abort_patience,
        )
        write_csv(out_root / f"{label}_results.csv", rows)
        stage_rows.append(rows)
        if stage_idx == len(stage_steps) - 1:
            break

        ranked = sorted(rows, key=lambda row: float(row.get("score", -1_000_000.0)), reverse=True)
        keep_n = max(1, min(stage_keep[stage_idx], len(ranked)))
        promoted: list[dict[str, Any]] = []
        for rank, row in enumerate(ranked[:keep_n]):
            cfg_path = ROOT / str(row["config_path"])
            out_dir = out_root / "runs" / f"stage{stage_idx + 2}_promoted_{rank:04d}"
            promoted.append(promote_from_config(cfg_path, steps=stage_steps[stage_idx + 1], out_dir=out_dir))
        current_overlays = promoted

    final_rows = sorted(stage_rows[-1], key=lambda row: float(row.get("score", -1_000_000.0)), reverse=True)
    write_csv(out_root / "ranked_results.csv", final_rows)

    best_dir = out_root / "best_configs"
    best_dir.mkdir(parents=True, exist_ok=True)
    for idx, row in enumerate(final_rows[: max(1, min(10, len(final_rows)))]):
        src = ROOT / str(row["config_path"])
        if src.exists():
            shutil.copy2(src, best_dir / f"best_{idx:02d}_score_{int(float(row['score']))}.yaml")

    print(f"\nWrote results to {out_root}")
    if final_rows:
        best = final_rows[0]
        print(
            "Best: "
            f"score={best['score']} viable={best['viable']} config={best['config_path']} "
            f"sales_tail={float(best.get('tail_sales_avg', 0.0)):.3f} "
            f"gdp_tail={float(best.get('tail_gdp_avg', 0.0)):.3f} "
            f"gini={float(best.get('gini_tail_avg', 0.0)):.3f} "
            f"env_intensity={float(best.get('environmental_impact_intensity_tail', 0.0)):.3f}"
        )


if __name__ == "__main__":
    main()




