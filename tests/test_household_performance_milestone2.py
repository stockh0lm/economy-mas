"""Milestone 2 – Household performance tests.

Referenz (explizit): doc/issues.md Abschnitt 5 → "Performance-Optimierung nach Profiling-Analyse".

Hinweis:
- Die Performance-Messungen isolieren Household-Overhead weitgehend, indem ein sehr
  schneller DummyRetailer verwendet wird. Damit können wir den Effekt von
  Caching/Batching im Household-Code stabil testen.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import pytest

from agents.household_agent import Household
from agents.savings_bank_agent import SavingsBank
from config import SimulationConfig
from sim_clock import SimulationClock


@dataclass(frozen=True, slots=True)
class DummySale:
    sale_value: float


class DummyRetailer:
    """Sehr schneller Retailer-Stub (keine Mutation, keine Lagerlogik)."""

    def sell_to_household(self, household: Household, budget: float) -> DummySale:
        # Für den Household-Test reicht es, den budgetierten Betrag als "spent" zurückzugeben.
        return DummySale(sale_value=float(budget))


def test_fertility_probability_daily_cached():
    """Referenz: doc/issues.md Abschnitt 5 → Caching-Hotspot."""

    cfg = SimulationConfig()
    sb = SavingsBank(unique_id="sb", config=cfg)
    h = Household(unique_id="h", config=cfg, income=100.0)
    h.sight_balance = 1000.0
    # In den fertilitätsrelevanten Altersbereich setzen, damit p_daily > 0 ist
    # und der Cache-Key befüllt wird.
    days_per_year = int(cfg.time.days_per_year)
    h.age_days = int(cfg.household.fertility_peak_age) * days_per_year
    h.age = h.age_days // days_per_year
    # Stabiler Zustand → identischer Cache-Key
    p1 = h._fertility_probability_daily(savings_bank=sb)
    p2 = h._fertility_probability_daily(savings_bank=sb)
    assert p1 == p2
    assert len(h._fertility_p_daily_cache) == 1


def test_household_step_performance():
    """Referenz: doc/issues.md Abschnitt 5 → Performance-Optimierung."""

    cfg = SimulationConfig()
    # Für stabile Performance: Demografie deaktivieren (keine Geburten/Haushalts-Events)
    cfg.household.fertility_base_annual = 0.0
    cfg.household.sight_growth_trigger = 1e12
    cfg.household.savings_growth_trigger = 1e12

    clock = SimulationClock(cfg.time)
    sb = SavingsBank(unique_id="sb", config=cfg)

    households: list[Household] = []
    for i in range(120):
        h = Household(unique_id=f"h{i}", config=cfg, income=100.0)
        h.sight_balance = 1000.0
        households.append(h)

    steps = 360
    t0 = time.perf_counter()
    for step in range(steps):
        month_end = clock.is_month_end(step)
        for h in households:
            h.step(
                current_step=step,
                clock=clock,
                savings_bank=sb,
                retailers=[],
                is_month_end=month_end,
            )
    elapsed = time.perf_counter() - t0

    # Ziel aus doc/issues.md (Abschnitt 5): < 0.8s für 43,200 Aufrufe
    assert elapsed < 0.8


def test_household_consume_batch_performance():
    """Referenz: doc/issues.md Abschnitt 5 → Batch-Optimierung in consume."""

    cfg = SimulationConfig()
    cfg.household.consumption_rate_normal = 0.7
    cfg.household.consumption_rate_growth = 0.4

    households: list[Household] = []
    for i in range(120):
        h = Household(unique_id=f"h{i}", config=cfg, income=100.0)
        h.sight_balance = 1000.0
        households.append(h)

    retailers = [DummyRetailer()]
    steps = 360

    t0 = time.perf_counter()
    for _ in range(steps):
        spent = Household.batch_consume(households, retailers)
    elapsed = time.perf_counter() - t0

    # Korrektheit: spend-Liste passt zur Haushaltsanzahl
    assert len(spent) == 120
    assert households[0].consumption == pytest.approx(1000.0 * cfg.household.consumption_rate_normal)

    # Ziel: < 0.5s für 43,200 "consumption ops" in Batchform
    assert elapsed < 0.5
