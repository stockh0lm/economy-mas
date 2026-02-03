"""Comprehensive tests for MetricsCollector._global_money_metrics method.

This test module provides thorough coverage for the complex monetary metrics calculation
as described in doc/issues.md Abschnitt 4.
"""

import math
from metrics import MetricsCollector
from config import CONFIG_MODEL


def setup_mock_metrics_data(collector: MetricsCollector, step: int):
    """Helper function to set up mock metrics data for testing."""
    # Mock state metrics
    collector.state_metrics["state"] = {
        step: {
            "tax_revenue": 1000.0,
            "infrastructure_budget": 500.0,
            "social_budget": 300.0,
            "environment_budget": 200.0
        }
    }

    # Mock company metrics
    collector.company_metrics["company1"] = {
        step: {
            "sight_balance": 2000.0,
            "service_sales_total": 500.0,
            "production_capacity": 1000.0
        }
    }
    collector.company_metrics["company2"] = {
        step: {
            "sight_balance": 1500.0,
            "service_sales_total": 300.0,
            "production_capacity": 800.0
        }
    }

    # Mock household metrics
    collector.household_metrics["household1"] = {
        step: {
            "sight_balance": 1000.0,
            "savings": 500.0,
            "consumption": 200.0,
            "total_wealth": 1500.0
        }
    }
    collector.household_metrics["household2"] = {
        step: {
            "sight_balance": 800.0,
            "savings": 300.0,
            "consumption": 150.0,
            "total_wealth": 1100.0
        }
    }

    # Mock retailer metrics
    collector.retailer_metrics["retailer1"] = {
        step: {
            "sight_balance": 600.0,
            "cc_balance": -400.0,
            "cc_limit": 1000.0,
            "inventory_value": 800.0,
            "sales_total": 1200.0,
            "repaid_total": 300.0,
            "inventory_write_down_extinguished_total": 50.0
        }
    }
    collector.retailer_metrics["retailer2"] = {
        step: {
            "sight_balance": 400.0,
            "cc_balance": -200.0,
            "cc_limit": 800.0,
            "inventory_value": 600.0,
            "sales_total": 900.0,
            "repaid_total": 200.0,
            "inventory_write_down_extinguished_total": 30.0
        }
    }

    # Mock bank metrics
    collector.bank_metrics["bank1"] = {
        step: {
            "sight_balance": 300.0,
            "issuance_volume": 250.0
        }
    }


def test_global_money_metrics_basic_aggregation():
    """Test basic M1/M2 calculation with simple agent data."""
    collector = MetricsCollector(CONFIG_MODEL)
    step = 10

    setup_mock_metrics_data(collector, step)

    # Test
    metrics = collector._global_money_metrics(step)

    # Verify M1 calculation: sum of positive sight balances
    # State: 1000 + 500 + 300 + 200 = 2000
    # Companies: 2000 + 1500 = 3500
    # Households: 1000 + 800 = 1800
    # Retailers: 600 + 400 = 1000
    # Banks: 300
    expected_m1 = 2000 + 3500 + 1800 + 1000 + 300
    assert math.isclose(metrics["m1_proxy"], expected_m1)

    # Verify M2 calculation: M1 + household savings
    # Household savings: 500 + 300 = 800
    expected_m2 = expected_m1 + 800
    assert math.isclose(metrics["m2_proxy"], expected_m2)

    # Verify CC exposure: sum of absolute cc balances
    expected_cc_exposure = abs(-400.0) + abs(-200.0)
    assert math.isclose(metrics["cc_exposure"], expected_cc_exposure)

    # Verify inventory total: sum of retailer inventory values
    expected_inventory = 800.0 + 600.0
    assert math.isclose(metrics["inventory_value_total"], expected_inventory)


def test_global_money_metrics_with_savings():
    """Test M2 calculation including household savings."""
    collector = MetricsCollector(CONFIG_MODEL)
    step = 20

    # Setup with more complex savings data
    collector.state_metrics["state"] = {
        step: {"tax_revenue": 500.0, "infrastructure_budget": 200.0}
    }

    collector.company_metrics["company1"] = {
        step: {"sight_balance": 1000.0, "service_sales_total": 200.0}
    }

    collector.household_metrics["household1"] = {
        step: {
            "sight_balance": 500.0,
            "savings": 1000.0,  # Large savings
            "consumption": 100.0
        }
    }
    collector.household_metrics["household2"] = {
        step: {
            "sight_balance": 300.0,
            "savings": 2000.0,  # Very large savings
            "consumption": 50.0
        }
    }

    collector.retailer_metrics["retailer1"] = {
        step: {
            "sight_balance": 200.0,
            "cc_balance": -100.0,
            "inventory_value": 300.0,
            "sales_total": 500.0
        }
    }

    collector.bank_metrics["bank1"] = {
        step: {"sight_balance": 100.0}
    }

    # Test
    metrics = collector._global_money_metrics(step)

    # M1 should include sight balances only
    expected_m1 = 700.0 + 1000.0 + 500.0 + 300.0 + 200.0 + 100.0
    assert math.isclose(metrics["m1_proxy"], expected_m1)

    # M2 should include savings: 1000 + 2000 = 3000
    expected_m2 = expected_m1 + 3000.0
    assert math.isclose(metrics["m2_proxy"], expected_m2)


def test_global_money_metrics_velocity_calculation():
    """Test velocity proxy calculation."""
    collector = MetricsCollector(CONFIG_MODEL)
    step = 30

    # Setup with known sales and M1
    collector.state_metrics["state"] = {
        step: {"tax_revenue": 100.0}
    }

    collector.company_metrics["company1"] = {
        step: {"sight_balance": 500.0}
    }

    collector.household_metrics["household1"] = {
        step: {"sight_balance": 300.0, "savings": 100.0}
    }

    collector.retailer_metrics["retailer1"] = {
        step: {
            "sight_balance": 200.0,
            "cc_balance": -50.0,
            "inventory_value": 100.0,
            "sales_total": 800.0  # Known sales total
        }
    }

    collector.bank_metrics["bank1"] = {
        step: {"sight_balance": 100.0}
    }

    # Test
    metrics = collector._global_money_metrics(step)

    # M1 = 100 (state) + 500 (company) + 300 (household) + 200 (retailer) + 100 (bank) = 1200
    expected_m1 = 1200.0
    assert math.isclose(metrics["m1_proxy"], expected_m1)

    # Velocity = sales_total / M1 = 800 / 1200
    expected_velocity = 800.0 / 1200.0
    assert math.isclose(metrics["velocity_proxy"], expected_velocity)


def test_global_money_metrics_issuance_extinguish():
    """Test issuance and extinguish volume tracking."""
    collector = MetricsCollector(CONFIG_MODEL)
    step = 40

    # Setup with issuance and extinguish data
    collector.state_metrics["state"] = {
        step: {"tax_revenue": 100.0}
    }

    collector.company_metrics["company1"] = {
        step: {"sight_balance": 500.0}
    }

    collector.household_metrics["household1"] = {
        step: {"sight_balance": 300.0, "savings": 100.0}
    }

    collector.retailer_metrics["retailer1"] = {
        step: {
            "sight_balance": 200.0,
            "cc_balance": -100.0,
            "inventory_value": 100.0,
            "sales_total": 500.0,
            "repaid_total": 150.0,  # CC repayment
            "inventory_write_down_extinguished_total": 50.0  # Write-down
        }
    }

    collector.bank_metrics["bank1"] = {
        step: {
            "sight_balance": 100.0,
            "issuance_volume": 200.0  # Goods purchase financing
        }
    }

    # Test
    metrics = collector._global_money_metrics(step)

    # Issuance volume should be 200
    assert math.isclose(metrics["issuance_volume"], 200.0)

    # Extinguish volume should be 150 (repaid) + 50 (write-down) = 200
    assert math.isclose(metrics["extinguish_volume"], 200.0)


def test_global_money_metrics_service_sector():
    """Test goods vs services transparency metrics."""
    collector = MetricsCollector(CONFIG_MODEL)
    step = 50

    # Setup with both goods and services
    collector.state_metrics["state"] = {
        step: {"tax_revenue": 100.0}
    }

    collector.company_metrics["company1"] = {
        step: {
            "sight_balance": 500.0,
            "service_sales_total": 300.0  # Services
        }
    }
    collector.company_metrics["company2"] = {
        step: {
            "sight_balance": 400.0,
            "service_sales_total": 200.0  # More services
        }
    }

    collector.household_metrics["household1"] = {
        step: {"sight_balance": 300.0, "savings": 100.0}
    }

    collector.retailer_metrics["retailer1"] = {
        step: {
            "sight_balance": 200.0,
            "cc_balance": -100.0,
            "inventory_value": 100.0,
            "sales_total": 800.0  # Goods sales
        }
    }

    collector.bank_metrics["bank1"] = {
        step: {"sight_balance": 100.0}
    }

    # Test
    metrics = collector._global_money_metrics(step)

    # Goods transaction volume should be retailer sales: 800
    assert math.isclose(metrics["goods_tx_volume"], 800.0)

    # Service transaction volume should be company service sales: 300 + 200 = 500
    assert math.isclose(metrics["service_tx_volume"], 500.0)

    # Service share should be 500 / (800 + 500) = 500/1300
    expected_service_share = 500.0 / 1300.0
    assert math.isclose(metrics["service_share_of_output"], expected_service_share)


def test_global_money_metrics_cc_utilization():
    """Test CC headroom and utilization diagnostics."""
    collector = MetricsCollector(CONFIG_MODEL)
    step = 60

    # Setup with CC data
    collector.state_metrics["state"] = {
        step: {"tax_revenue": 100.0}
    }

    collector.company_metrics["company1"] = {
        step: {"sight_balance": 500.0}
    }

    collector.household_metrics["household1"] = {
        step: {"sight_balance": 300.0, "savings": 100.0}
    }

    # Retailer at CC limit
    collector.retailer_metrics["retailer1"] = {
        step: {
            "sight_balance": 200.0,
            "cc_balance": -1000.0,  # Fully drawn
            "cc_limit": 1000.0,     # At limit
            "inventory_value": 100.0,
            "sales_total": 500.0
        }
    }

    # Retailer with headroom
    collector.retailer_metrics["retailer2"] = {
        step: {
            "sight_balance": 150.0,
            "cc_balance": -300.0,   # Partially drawn
            "cc_limit": 1000.0,     # 700 headroom
            "inventory_value": 50.0,
            "sales_total": 300.0
        }
    }

    collector.bank_metrics["bank1"] = {
        step: {"sight_balance": 100.0}
    }

    # Test
    metrics = collector._global_money_metrics(step)

    # CC exposure should be 1000 + 300 = 1300
    assert math.isclose(metrics["cc_exposure"], 1300.0)

    # CC headroom: (1000-1000) + (1000-300) = 0 + 700 = 700
    assert math.isclose(metrics["cc_headroom_total"], 700.0)

    # Avg CC utilization: (1000/1000 + 300/1000) / 2 = (1.0 + 0.3) / 2 = 0.65
    assert math.isclose(metrics["avg_cc_utilization"], 0.65)

    # Retailers at CC limit share: 1/2 = 0.5
    assert math.isclose(metrics["retailers_at_cc_limit_share"], 0.5)


def test_global_money_metrics_empty_data():
    """Test behavior with empty/no data."""
    collector = MetricsCollector(CONFIG_MODEL)
    step = 70

    # Test with no data
    metrics = collector._global_money_metrics(step)

    # All metrics should be 0 or handle gracefully
    assert math.isclose(metrics["m1_proxy"], 0.0)
    assert math.isclose(metrics["m2_proxy"], 0.0)
    assert math.isclose(metrics["cc_exposure"], 0.0)
    assert math.isclose(metrics["inventory_value_total"], 0.0)
    assert math.isclose(metrics["sales_total"], 0.0)
    assert math.isclose(metrics["velocity_proxy"], 0.0)
    assert math.isclose(metrics["goods_tx_volume"], 0.0)
    assert math.isclose(metrics["service_tx_volume"], 0.0)
    assert math.isclose(metrics["issuance_volume"], 0.0)
    assert math.isclose(metrics["extinguish_volume"], 0.0)
    assert math.isclose(metrics["goods_value_total"], 0.0)
    assert math.isclose(metrics["service_value_total"], 0.0)
    assert math.isclose(metrics["service_share_of_output"], 0.0)