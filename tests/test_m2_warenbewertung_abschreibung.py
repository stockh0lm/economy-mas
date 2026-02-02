import pytest

from config import SimulationConfig
from agents.retailer_agent import RetailerAgent


def test_warenbewertung_abschreibung():
    """Referenz: doc/issues.md Abschnitt 2 → Warenbewertung & Abschreibung"""

    cfg = SimulationConfig()
    cfg.retailer.inventory_valuation_method = "lower_of_cost_or_market"
    cfg.retailer.obsolescence_rate = 0.0
    cfg.retailer.obsolescence_rate_by_group = {"electronics": 0.10}

    r = RetailerAgent(unique_id="retailer_0", config=cfg)
    r.add_inventory_lot(group_id="electronics", units=10.0, unit_cost=100.0, unit_market_price=80.0)

    assert r.inventory_units == pytest.approx(10.0)
    assert r.inventory_value == pytest.approx(800.0)

    # Full write-down coverage via reserve.
    r.write_down_reserve = 80.0
    r.sight_balance = 0.0

    destroyed = r.apply_obsolescence_write_down(current_step=1)

    assert destroyed == pytest.approx(80.0)
    assert r.write_down_reserve == pytest.approx(0.0)
    # Carrying value reduced by 10% for group "electronics".
    assert r.inventory_value == pytest.approx(720.0)