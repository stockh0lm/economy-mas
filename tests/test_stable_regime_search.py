from argparse import Namespace
from pathlib import Path
from random import Random

from tools.stable_regime_search import (
    InstabilityMonitor,
    candidate_overlay,
    smooth_growth_signal,
    stage_plan,
    summarize_run,
    symmetric_price_deviation,
)


def _global_rows(
    *,
    steps: int,
    early_gdp: float,
    tail_gdp: float,
    early_sales: float,
    tail_sales: float,
    price: float = 100.0,
    unemployment: float = 0.05,
    employment: float = 0.95,
    issuance: float = 20.0,
    env_impact: float = 10.0,
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    split = steps // 2
    for step in range(steps):
        rows.append(
            {
                "time_step": step,
                "gdp": early_gdp if step < split else tail_gdp,
                "sales_total": early_sales if step < split else tail_sales,
                "issuance_volume": issuance,
                "price_index": price,
                "employment_rate": employment,
                "unemployment_rate": unemployment,
                "retailers_at_cc_limit_share": 0.05,
                "retailers_stockout_share": 0.05,
                "bankruptcy_rate": 0.0,
                "company_deaths": 0.0,
                "retailer_deaths": 0.0,
                "total_companies": 4.0,
                "total_retailers": 2.0,
                "total_households": 12.0,
                "m1_proxy": 1_000.0,
                "m2_proxy": 1_200.0,
                "total_environmental_impact": env_impact,
            }
        )
    return rows


def _household_rows(steps: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for step in range(steps):
        for agent_id, wealth in [("h1", 10.0), ("h2", 20.0), ("h3", 40.0), ("h4", 80.0)]:
            rows.append(
                {
                    "time_step": step,
                    "agent_id": agent_id,
                    "total_wealth": wealth,
                    "checking_account": wealth,
                    "savings": 0.0,
                }
            )
    return rows


def _state_rows(steps: int, amount: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for step in range(steps):
        rows.append(
            {
                "time_step": step,
                "agent_id": "state",
                "tax_revenue": amount,
                "infrastructure_budget": amount,
                "social_budget": amount,
                "environment_budget": amount,
            }
        )
    return rows


def test_symmetric_price_deviation_is_balanced() -> None:
    assert symmetric_price_deviation(50.0, target=100.0) == symmetric_price_deviation(
        200.0, target=100.0
    )
    assert symmetric_price_deviation(0.0, target=100.0) < float("inf")


def test_growth_signal_rewards_growth_without_hard_threshold() -> None:
    assert smooth_growth_signal(1.08) > smooth_growth_signal(1.00)
    assert smooth_growth_signal(1.00) > smooth_growth_signal(0.90)


def test_summarize_run_penalizes_contraction_and_tracks_new_metrics() -> None:
    summary = summarize_run(
        global_rows=_global_rows(
            steps=120,
            early_gdp=100.0,
            tail_gdp=50.0,
            early_sales=120.0,
            tail_sales=60.0,
            price=100.0,
            env_impact=12.0,
        ),
        household_rows=_household_rows(120),
        company_rows=[],
        retailer_rows=[],
        bank_rows=[],
        state_rows=_state_rows(120, 25.0),
        returncode=0,
        elapsed_s=1.0,
        requested_steps=120,
        price_target=100.0,
        aborted_early=False,
        abort_reason=None,
    )

    assert summary["viable"] is False
    assert summary["gdp_floor_ratio_tail"] == 0.5
    assert summary["sales_floor_ratio_tail"] == 0.5
    assert summary["gini_tail_avg"] > 0.0
    assert summary["environmental_impact_intensity_tail"] > 0.0
    assert summary["state_budget_tail_avg"] == 75.0
    assert "no_deep_output_collapse" in summary["failed_checks"]


def test_summarize_run_uses_non_overlapping_head_and_tail_windows_for_short_runs() -> None:
    summary = summarize_run(
        global_rows=_global_rows(
            steps=4,
            early_gdp=100.0,
            tail_gdp=20.0,
            early_sales=100.0,
            tail_sales=20.0,
        ),
        household_rows=_household_rows(4),
        company_rows=[],
        retailer_rows=[],
        bank_rows=[],
        state_rows=_state_rows(4, 10.0),
        returncode=0,
        elapsed_s=1.0,
        requested_steps=4,
        price_target=100.0,
        aborted_early=False,
        abort_reason=None,
    )

    assert summary["gdp_floor_ratio_tail"] == 0.2
    assert summary["sales_floor_ratio_tail"] == 0.2


def test_summarize_run_single_step_uses_neutral_growth_ratio() -> None:
    summary = summarize_run(
        global_rows=_global_rows(
            steps=1,
            early_gdp=100.0,
            tail_gdp=100.0,
            early_sales=100.0,
            tail_sales=100.0,
        ),
        household_rows=_household_rows(1),
        company_rows=[],
        retailer_rows=[],
        bank_rows=[],
        state_rows=_state_rows(1, 10.0),
        returncode=0,
        elapsed_s=1.0,
        requested_steps=1,
        price_target=100.0,
        aborted_early=False,
        abort_reason=None,
    )

    assert summary["gdp_growth_ratio_tail"] == 1.0
    assert summary["sales_growth_ratio_tail"] == 1.0
    assert summary["environmental_impact_growth_ratio_tail"] == 1.0


def test_instability_monitor_aborts_after_sustained_breakage() -> None:
    monitor = InstabilityMonitor(warmup_steps=2, patience=2, price_target=100.0)
    for step in range(2):
        assert (
            monitor.observe(
                step=step,
                metrics={
                    "gdp": 100.0,
                    "sales_total": 100.0,
                    "price_index": 100.0,
                    "unemployment_rate": 0.05,
                    "retailers_at_cc_limit_share": 0.0,
                    "retailers_stockout_share": 0.0,
                    "total_households": 12.0,
                    "total_companies": 4.0,
                    "total_retailers": 2.0,
                },
            )
            is None
        )

    assert (
        monitor.observe(
            step=2,
            metrics={
                "gdp": 10.0,
                "sales_total": 10.0,
                "price_index": 10.0,
                "unemployment_rate": 0.99,
                "retailers_at_cc_limit_share": 1.0,
                "retailers_stockout_share": 1.0,
                "total_households": 12.0,
                "total_companies": 4.0,
                "total_retailers": 2.0,
            },
        )
        is None
    )
    assert (
        monitor.observe(
            step=3,
            metrics={
                "gdp": 10.0,
                "sales_total": 10.0,
                "price_index": 10.0,
                "unemployment_rate": 0.99,
                "retailers_at_cc_limit_share": 1.0,
                "retailers_stockout_share": 1.0,
                "total_households": 12.0,
                "total_companies": 4.0,
                "total_retailers": 2.0,
            },
        )
        == "price_distortion"
    )


def test_candidate_overlay_keeps_household_income_fields_consistent() -> None:
    overlay = candidate_overlay(Random(7), steps=100, seed=7, out_dir=Path("/tmp/fake"))

    assert overlay["population"]["household_template"]["income"] == overlay["household"]["base_income"]
    assert (
        overlay["household"]["consumption_rate_growth"]
        >= overlay["household"]["consumption_rate_normal"]
    )


def test_stage_plan_rejects_mixed_deprecated_and_stage_flags() -> None:
    args = Namespace(
        short_steps=100,
        long_steps=None,
        keep=None,
        stage_steps="100,200",
        stage_keep=None,
    )

    try:
        stage_plan(args)
    except ValueError as exc:
        assert "do not mix" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError for mixed flags")


