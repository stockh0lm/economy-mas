import math

import pytest

from agents.bank import WarengeldBank
from agents.retailer_agent import RetailerAgent
from config import SimulationConfig
from metrics import MetricsCollector, apply_sight_decay


def test_hyperinflation_fix() -> None:
    """Referenz: doc/issues.md Abschnitt 4/5 → „Hyperinflation / Numerische Überläufe in Preisindex-Berechnung - KRITISCH"""

    # Arrange: Preisindex-Berechnung mit dauerhaft hohem Preisdruck.
    # Zahlen aus doc/issues.md (Root-Cause-Beispiel): money/gdp ≈ 2.886.
    cfg = SimulationConfig()
    collector = MetricsCollector(config=cfg)

    class _Agent:
        def __init__(self, sight_balance: float, income: float = 0.0, consumption_history: list[float] | None = None):
            self.sight_balance = float(sight_balance)
            self.income = float(income)
            self.consumption_history = list(consumption_history or [])

    # Hoher Geldüberhang (wird über Sight-Decay abgebaut).
    agents = [_Agent(4000.0, income=100.0, consumption_history=[50.0] * 30), _Agent(1362.89, income=50.0, consumption_history=[20.0] * 30)]

    gdp = 1857.97

    # Act: 10k Schritte, mit monatlicher Abschmelzung.
    prices: list[float] = []
    money_series: list[float] = []
    initial_money = sum(a.sight_balance for a in agents)

    for step in range(10_000):
        if (step + 1) % int(cfg.time.days_per_month) == 0:
            _ = apply_sight_decay(agents, config=cfg)

        total_money = sum(max(0.0, a.sight_balance) for a in agents)
        money_series.append(total_money)

        metrics = collector._price_dynamics(step, total_money, gdp, household_consumption=0.0)
        collector.global_metrics[step] = metrics
        prices.append(float(metrics["price_index"]))

    # Assert: Preisindex bleibt endlich und unter stabiler Obergrenze.
    assert all(math.isfinite(p) for p in prices)
    assert max(prices) <= 1000.0

    # Geldmenge wird durch Feedback-Mechanismen reduziert.
    assert money_series[-1] < initial_money


def test_warengeld_feedback_mechanismen() -> None:
    """Referenz: doc/specs.md Sections 4.1, 4.2, 4.6, 4.7 und doc/issues.md Abschnitt 4/5."""

    cfg = SimulationConfig()
    bank = WarengeldBank("bank_0", config=cfg)

    # --- 4.2 Automatische Kreditrückzahlung ---
    retailer = RetailerAgent("retailer_0", config=cfg, cc_limit=1_000.0)
    retailer.sight_balance = 200.0
    retailer.cc_balance = -100.0
    bank.credit_lines[retailer.unique_id] = 100.0

    repaid = bank.auto_repay_cc_from_sight(retailer)
    assert repaid == pytest.approx(100.0)
    assert retailer.cc_balance == pytest.approx(0.0)
    # Retailer hält mindestens den Allowance-Puffer.
    assert retailer.sight_balance >= retailer.sight_allowance - 1e-9

    # --- 4.1 Lagerbasierte Kreditlimits / Inventory backing ---
    retailer.cc_balance = -1_000.0
    retailer.inventory_value = 500.0  # Unterdeckung bei 1.2x Collateral
    retailer.sight_balance = 0.0
    retailer.write_down_reserve = 1_000.0
    bank.credit_lines[retailer.unique_id] = 1_000.0

    destroyed = bank.enforce_inventory_backing(retailer)
    assert destroyed > 0
    # Nach Enforcement muss die 1.2x-Deckung wieder erfüllt sein.
    assert retailer.inventory_value >= abs(retailer.cc_balance) * 1.2 - 1e-9

    # --- 4.6 Wertberichtigungen (Retailer) ---
    cfg.retailer.unsellable_after_days = 1
    retailer.inventory_lots = []
    retailer.inventory_units = 0
    retailer.inventory_value = 0
    retailer.add_inventory_lot(group_id="default", units=10, unit_cost=10.0, age_days=0)
    retailer.write_down_reserve = 50.0
    retailer.sight_balance = 100.0
    retailer.cc_balance = -100.0
    bank.credit_lines[retailer.unique_id] = 100.0

    wd = retailer.apply_inventory_write_downs(current_step=0, bank=bank)
    assert wd == pytest.approx(100.0)
    assert retailer.inventory_value == pytest.approx(0.0)
    assert retailer.write_down_reserve == pytest.approx(0.0)
    assert retailer.sight_balance == pytest.approx(50.0)
    assert retailer.cc_balance == pytest.approx(0.0)
    assert bank.credit_lines[retailer.unique_id] == pytest.approx(0.0)

    # --- 4.7 Sichtguthaben-Abschmelzung (nur Überschuss) ---
    class _HH:
        def __init__(self):
            # Monatsausgaben ~ 100/Tag -> allowance ~ 3000/Monat bei 30 Tagen.
            self.sight_balance = 4000.0
            self.consumption_history = [100.0] * 30
            self.income = 0.0

    hh = _HH()
    cfg.clearing.sight_allowance_multiplier = 1.0
    cfg.clearing.sight_excess_decay_rate = 0.1
    burned = apply_sight_decay([hh], config=cfg)
    # allowance = 100*30 = 3000 -> excess=1000 -> decay=100
    assert burned == pytest.approx(100.0)
    assert hh.sight_balance == pytest.approx(3900.0)
