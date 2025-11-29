import statistics

from metrics import MetricsCollector


def test_aggregate_metrics_household_uses_configured_aggregation() -> None:
    collector = MetricsCollector()
    collector.metrics_config = {
        "income": {"aggregation": "mean"},
        "savings": {"aggregation": "sum"},
    }

    collector.household_metrics = {
        "h1": {0: {"income": 100.0, "savings": 50.0}},
        "h2": {0: {"income": 200.0, "savings": 70.0}},
    }

    result = collector.aggregate_metrics(step=0)

    expected_income = statistics.mean([100.0, 200.0])
    expected_savings = sum([50.0, 70.0])

    assert result["household"]["income"] == expected_income
    assert result["household"]["savings"] == expected_savings


def test_aggregate_metrics_skips_missing_steps() -> None:
    collector = MetricsCollector()
    collector.metrics_config = {"income": {"aggregation": "mean"}}

    collector.household_metrics = {
        "h1": {1: {"income": 100.0}},
    }

    result = collector.aggregate_metrics(step=0)
    assert "income" not in result["household"]


def test_aggregate_metrics_applies_bank_sum_and_state_passthrough() -> None:
    collector = MetricsCollector()
    collector.metrics_config.update(
        {
            "liquidity": {"aggregation": "sum"},
            "total_credit": {"aggregation": "sum"},
        }
    )

    collector.bank_metrics = {
        "b1": {0: {"liquidity": 100.0, "total_credit": 50.0}},
        "b2": {0: {"liquidity": 200.0, "total_credit": 30.0}},
    }
    collector.state_metrics = {
        "state": {
            0: {
                "tax_revenue": 25.0,
                "infrastructure_budget": 5.0,
                "social_budget": 3.0,
            }
        }
    }

    result = collector.aggregate_metrics(step=0)

    assert result["bank"]["liquidity"] == 300.0
    assert result["bank"]["total_credit"] == 80.0
    assert result["state"]["tax_revenue"] == 25.0


def test_aggregate_metrics_company_custom_aggregations_and_market_passthrough() -> None:
    collector = MetricsCollector()
    collector.metrics_config.update(
        {
            "production_capacity": {"aggregation": "sum"},
            "inventory": {"aggregation": "mean"},
            "average_asset_price": {"aggregation": "median"},
        }
    )
    collector.company_metrics = {
        "c1": {0: {"production_capacity": 50.0, "inventory": 30.0}},
        "c2": {0: {"production_capacity": 70.0, "inventory": 40.0}},
    }
    collector.market_metrics = {
        "mkt": {0: {"average_asset_price": 10.0}},
        "mkt2": {0: {"average_asset_price": 30.0}},
    }

    result = collector.aggregate_metrics(step=0)

    assert result["company"]["production_capacity"] == 120.0
    assert result["company"]["inventory"] == 35.0
    assert result["market"] == {}


def test_aggregate_metrics_supports_median_and_max() -> None:
    collector = MetricsCollector()
    collector.metrics_config.update(
        {
            "income": {"aggregation": "median"},
            "savings": {"aggregation": "max"},
        }
    )
    collector.household_metrics = {
        "h1": {0: {"income": 100.0, "savings": 50.0}},
        "h2": {0: {"income": 200.0, "savings": 75.0}},
        "h3": {0: {"income": 150.0, "savings": 60.0}},
    }

    result = collector.aggregate_metrics(step=0)

    assert result["household"]["income"] == 150.0
    assert result["household"]["savings"] == 75.0


def test_aggregate_metrics_ignores_non_numeric_values() -> None:
    collector = MetricsCollector()
    collector.metrics_config.update({"balance": {"aggregation": "sum"}})
    collector.company_metrics = {
        "c1": {0: {"balance": 10.0, "status": "healthy"}},
        "c2": {0: {"balance": 20.0, "status": "healthy"}},
    }

    result = collector.aggregate_metrics(step=0)

    assert result["company"]["balance"] == 30.0
    assert "status" not in result["company"]


def test_aggregate_metrics_company_min_and_market_future_hook() -> None:
    collector = MetricsCollector()
    collector.metrics_config.update(
        {
            "resource_usage": {"aggregation": "min"},
            "balance": {"aggregation": "max"},
        }
    )
    collector.company_metrics = {
        "c1": {0: {"resource_usage": 5.0, "balance": 80.0}},
        "c2": {0: {"resource_usage": 3.0, "balance": 120.0}},
    }

    collector.market_metrics = {
        "mkt": {0: {"turnover": 100.0}},
    }

    result = collector.aggregate_metrics(step=0)

    assert result["company"]["resource_usage"] == 3.0
    assert result["company"]["balance"] == 120.0
    assert result["market"] == {}
