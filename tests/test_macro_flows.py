import math

import pytest

from agents.bank import WarengeldBank
from agents.company_agent import Company
from agents.household_agent import Household
from agents.retailer_agent import RetailerAgent
from config import SimulationConfig
from metrics.collector import MetricsCollector


def _cfg() -> SimulationConfig:
    cfg = SimulationConfig(simulation_steps=1)
    cfg.population.num_households = 1
    cfg.population.num_companies = 1
    cfg.population.num_retailers = 1
    return cfg


def test_goods_financing_creates_money_transferred_to_company() -> None:
    cfg = _cfg()
    bank = WarengeldBank(unique_id="bank", config=cfg)
    c = Company(unique_id="c0", production_capacity=100.0, config=cfg)
    r = RetailerAgent(unique_id="r0", config=cfg, cc_limit=10_000.0, target_inventory_value=200.0)

    bank.register_retailer(r, cc_limit=r.cc_limit)

    # Producer needs inventory to sell.
    c.finished_goods_units = 1_000.0
    assert c.sight_balance == 0.0

    financed = r.restock_goods([c], bank, current_step=0)

    # Money creation point: sight balances increase on the company side.
    assert financed > 0
    assert math.isclose(c.sight_balance, financed, rel_tol=1e-9)
    assert r.inventory_value > 0
    assert r.cc_balance < 0  # drawn CC


def test_household_consumption_moves_money_and_reduces_inventory() -> None:
    cfg = _cfg()
    bank = WarengeldBank(unique_id="bank", config=cfg)
    c = Company(unique_id="c0", production_capacity=100.0, config=cfg)
    r = RetailerAgent(unique_id="r0", config=cfg, cc_limit=10_000.0, target_inventory_value=200.0)
    h = Household(unique_id="h0", config=cfg)

    bank.register_retailer(r, cc_limit=r.cc_limit)

    c.finished_goods_units = 1_000.0
    r.restock_goods([c], bank, current_step=0)

    # Give household money (transfer in test setup).
    h.sight_balance = 100.0

    inv_units_before = r.inventory_units
    inv_value_before = r.inventory_value
    r_sight_before = r.sight_balance

    result = r.sell_to_household(h, budget=50.0)

    assert result.sale_value > 0
    assert h.sight_balance < 100.0
    assert r.sight_balance > r_sight_before
    assert r.inventory_units < inv_units_before
    assert r.inventory_value <= inv_value_before


def test_repayment_extinguishes_money_and_reduces_cc_exposure() -> None:
    cfg = _cfg()
    bank = WarengeldBank(unique_id="bank", config=cfg)
    c = Company(unique_id="c0", production_capacity=100.0, config=cfg)
    r = RetailerAgent(unique_id="r0", config=cfg, cc_limit=10_000.0, target_inventory_value=200.0)

    bank.register_retailer(r, cc_limit=r.cc_limit)

    c.finished_goods_units = 1_000.0
    financed = r.restock_goods([c], bank, current_step=0)
    assert financed > 0
    assert r.cc_balance < 0

    # Give retailer sight balance so it can repay.
    r.sight_balance = 1_000.0

    cc_before = r.cc_balance
    sight_before = r.sight_balance

    repaid = r.auto_repay_kontokorrent(bank)

    assert repaid > 0
    assert r.cc_balance > cc_before  # moves toward zero
    assert r.sight_balance < sight_before


def test_bootstrap_restock_is_bounded_per_day() -> None:
    cfg = _cfg()
    cfg.retailer.restock_bootstrap_order_value = 40.0
    bank = WarengeldBank(unique_id="bank", config=cfg)
    c = Company(unique_id="c0", production_capacity=100.0, config=cfg)
    r = RetailerAgent(unique_id="r0", config=cfg, cc_limit=10_000.0, target_inventory_value=200.0)

    bank.register_retailer(r, cc_limit=r.cc_limit)
    c.finished_goods_units = 1_000.0

    financed = r.restock_goods([c], bank, current_step=0)

    assert financed == pytest.approx(40.0)
    assert r.inventory_value == pytest.approx(40.0)


def test_recent_sales_keep_restock_flowing_above_reorder_point() -> None:
    cfg = _cfg()
    cfg.retailer.restock_flow_replenishment_multiple = 1.0
    bank = WarengeldBank(unique_id="bank", config=cfg)
    c = Company(unique_id="c0", production_capacity=100.0, config=cfg)
    r = RetailerAgent(unique_id="r0", config=cfg, cc_limit=10_000.0, target_inventory_value=200.0)

    bank.register_retailer(r, cc_limit=r.cc_limit)
    c.finished_goods_units = 1_000.0
    r.inventory_units = 17.0
    r.inventory_value = 170.0
    r.cogs_history = [25.0, 25.0, 25.0]

    financed = r.restock_goods([c], bank, current_step=0)

    assert financed == pytest.approx(25.0)
    assert r.cc_balance == pytest.approx(-25.0)


def test_bank_metrics_report_only_current_step_issuance() -> None:
    cfg = _cfg()
    bank = WarengeldBank(unique_id="bank", config=cfg)
    c = Company(unique_id="c0", production_capacity=100.0, config=cfg)
    r = RetailerAgent(unique_id="r0", config=cfg, cc_limit=10_000.0, target_inventory_value=200.0)
    collector = MetricsCollector()

    bank.register_retailer(r, cc_limit=r.cc_limit)
    c.finished_goods_units = 1_000.0

    financed = r.restock_goods([c], bank, current_step=0)
    collector.collect_bank_metrics([bank], step=0)
    collector.collect_bank_metrics([bank], step=1)

    assert collector.bank_metrics[bank.unique_id][0]["issuance_volume"] == pytest.approx(financed)
    assert collector.bank_metrics[bank.unique_id][1]["issuance_volume"] == 0.0

