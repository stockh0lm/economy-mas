import math

from config import CONFIG_MODEL
from metrics import MetricsCollector


def test_calculate_global_metrics_tracks_macro_outputs() -> None:
    collector = MetricsCollector()

    collector.registered_companies = {"c1", "c2"}

    collector.company_metrics = {
        "c1": {
                0: {"sight_balance": 80.0},
            1: {
                    "sight_balance": 100.0,
                "production_capacity": 60.0,
                "rd_investment": 10.0,
                "environmental_impact": 3.0,
            },
        },
        "c2": {
                0: {"sight_balance": 60.0},
            1: {
                    "sight_balance": 200.0,
                "production_capacity": 40.0,
                "rd_investment": 5.0,
                "environmental_impact": 2.0,
            },
        },
    }

    collector.household_metrics = {
        "h1": {
            1: {
                "checking_account": 50.0,
                "savings": 10.0,
                "consumption": 20.0,
                "income": 30.0,
                "employed": True,
                "total_wealth": 60.0,
                "environmental_impact": 1.0,
            }
        },
        "h2": {
            1: {
                "checking_account": 30.0,
                "savings": 5.0,
                "consumption": 10.0,
                "income": 15.0,
                "employed": False,
                "total_wealth": 35.0,
                "environmental_impact": 0.5,
            }
        },
    }

    collector.state_metrics = {
        "state": {
            1: {
                "tax_revenue": 10.0,
                "infrastructure_budget": 4.0,
                "social_budget": 3.0,
                "environment_budget": 2.0,
            }
        }
    }

    collector.global_metrics[0] = {"price_index": 120.0}

    collector.calculate_global_metrics(step=1)

    metrics = collector.global_metrics[1]

    # total_money_supply ~= m2_proxy. With state deposits included in the money
    # aggregates, broad money includes the state's budget buckets as well.
    assert math.isclose(metrics["total_money_supply"], 414.0)
    assert math.isclose(metrics["gdp"], 100.0)
    assert math.isclose(metrics["household_consumption"], 30.0)
    assert math.isclose(metrics["consumption_pct_gdp"], 0.3)

    # Preisniveau-Dynamik konvergiert gegen Gleichgewicht (siehe metrics._price_dynamics).
    # Referenz: doc/issues.md Abschnitt 4/5 → „Hyperinflation / Numerische Überläufe ...“.
    # Including state deposits increases money_for_price, shifting equilibrium.
    expected_price_index = 134.7
    assert math.isclose(metrics["price_index"], expected_price_index, rel_tol=1e-9)
    assert math.isclose(metrics["inflation_rate"], (expected_price_index - 120.0) / 120.0, rel_tol=1e-9)

    assert math.isclose(metrics["employment_rate"], 0.5)
    assert math.isclose(metrics["unemployment_rate"], 0.5)

    assert math.isclose(metrics["total_rd_investment"], 15.0)
    assert math.isclose(metrics["investment_pct_gdp"], 0.15)

    assert math.isclose(metrics["tax_revenue"], 10.0)
    assert math.isclose(metrics["government_spending"], 9.0)
    assert math.isclose(metrics["govt_spending_pct_gdp"], 0.09)
    assert math.isclose(metrics["budget_balance"], 1.0)


def test_calculate_global_metrics_handles_zero_gdp_and_no_prior_price() -> None:
    collector = MetricsCollector()
    collector.registered_companies = {"c1"}
    collector.company_metrics = {
        "c1": {
            2: {"sight_balance": 10.0, "production_capacity": 0.0, "rd_investment": 0.0},
        }
    }
    collector.household_metrics = {
        "h1": {2: {"checking_account": 5.0, "savings": 5.0, "consumption": 0.0, "employed": False}},
    }

    collector.calculate_global_metrics(step=2)
    metrics = collector.global_metrics[2]

    assert math.isclose(metrics["gdp"], 0.0)
    assert math.isclose(metrics["consumption_pct_gdp"], 0.0)
    assert math.isclose(metrics["investment_pct_gdp"], 0.0)
    assert math.isclose(metrics["price_index"], CONFIG_MODEL.market.price_index_base, abs_tol=100.0)
    assert math.isclose(metrics["inflation_rate"], 0.0)


def test_calculate_global_metrics_accumulates_multiple_states_and_bankruptcies() -> None:
    collector = MetricsCollector()
    collector.registered_companies = {"c_alive", "c_dead"}
    collector.company_metrics = {
        "c_alive": {
            3: {
                    "sight_balance": 80.0,
                "production_capacity": 30.0,
                "rd_investment": 5.0,
                "environmental_impact": 1.0,
            },
        },
        "c_dead": {
                2: {"sight_balance": 20.0, "production_capacity": 10.0},
        },
    }

    collector.household_metrics = {
        "h1": {3: {"checking_account": 40.0, "savings": 10.0, "consumption": 15.0, "employed": True, "total_wealth": 50.0}},
        "h2": {3: {"checking_account": 10.0, "savings": 0.0, "consumption": 5.0, "employed": False, "total_wealth": 10.0}},
    }

    collector.state_metrics = {
        "state_a": {3: {"tax_revenue": 5.0, "infrastructure_budget": 2.0, "social_budget": 1.0, "environment_budget": 1.0}},
        "state_b": {3: {"tax_revenue": 7.0, "infrastructure_budget": 1.0, "social_budget": 2.0, "environment_budget": 0.5}},
    }

    collector.calculate_global_metrics(step=3)
    metrics = collector.global_metrics[3]

    # Includes both states' deposits in broad money.
    assert math.isclose(metrics["total_money_supply"], 159.5)
    assert math.isclose(metrics["tax_revenue"], 12.0)
    assert math.isclose(metrics["government_spending"], 7.5)
    assert math.isclose(metrics["bankruptcy_rate"], 0.5)
    assert math.isclose(metrics["total_environmental_impact"], 1.0)


def test_calculate_global_metrics_gini_and_blended_price_pressure() -> None:
    original_ratio = CONFIG_MODEL.market.price_index_pressure_ratio
    CONFIG_MODEL.market.price_index_pressure_ratio = "blended"
    try:
        collector = MetricsCollector()
        collector.registered_companies = {"c1"}
        collector.company_metrics = {
            "c1": {
                1: {
                        "sight_balance": 50.0,
                    "production_capacity": 20.0,
                    "rd_investment": 5.0,
                    "environmental_impact": 1.0,
                }
            }
        }
        collector.household_metrics = {
            "h1": {1: {"checking_account": 10.0, "savings": 0.0, "consumption": 5.0, "employed": True, "income": 10.0, "total_wealth": 10.0}},
            "h2": {1: {"checking_account": 0.0, "savings": 20.0, "consumption": 2.0, "employed": False, "income": 0.0, "total_wealth": 20.0}},
            "h3": {1: {"checking_account": 30.0, "savings": 5.0, "consumption": 1.0, "employed": True, "income": 15.0, "total_wealth": 35.0}},
        }
        collector.global_metrics[0] = {"price_index": 100.0}

        collector.calculate_global_metrics(step=1)
        metrics = collector.global_metrics[1]

        assert math.isclose(metrics["gini_coefficient"], -0.2564102564, rel_tol=1e-6)
        # Blended mode uses the historical 75/25 blend on M1 pressure vs consumption pressure.
        assert math.isclose(metrics["price_pressure"], 3.4749999998, rel_tol=1e-9)
        assert math.isclose(metrics["price_index"], 112.374999999, rel_tol=1e-9)
    finally:
        CONFIG_MODEL.market.price_index_pressure_ratio = original_ratio


def test_calculate_global_metrics_tracks_employment_and_labor_snapshot() -> None:
    collector = MetricsCollector()
    collector.household_metrics = {
        "h1": {4: {"employed": True, "income": 20.0, "checking_account": 10.0, "savings": 5.0}},
        "h2": {4: {"employed": False, "income": 0.0, "checking_account": 5.0, "savings": 2.0}},
        "h3": {4: {"employed": True, "income": 15.0, "checking_account": 8.0, "savings": 4.0}},
    }
    collector.company_metrics = {
        "c1": {4: {"sight_balance": 30.0, "production_capacity": 10.0, "rd_investment": 2.0}},
    }
    collector.latest_labor_metrics = {
        "registered_workers": 3.0,
        "employed_workers": 2.0,
        "employment_rate": 2.0 / 3.0,
        "unemployment_rate": 1.0 / 3.0,
    }

    collector.calculate_global_metrics(step=4)
    metrics = collector.global_metrics[4]

    assert math.isclose(metrics["employment_rate"], 2 / 3)
    assert math.isclose(metrics["unemployment_rate"], 1 / 3)
    snapshot = collector.get_latest_macro_snapshot()
    assert snapshot["registered_workers"] == 3.0
    assert snapshot["employment_rate"] == metrics["employment_rate"]
