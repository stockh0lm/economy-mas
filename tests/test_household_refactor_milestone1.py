"""Milestone 1 – Household refactoring tests.

Referenz (explizit): doc/issues.md Abschnitt 4 → "Gründliches Refaktorieren kritischer Stellen".

Hinweis: Die Komplexitätsprüfung verwendet `tools.complexity` als pragmatischen
Radon-Ersatz, da das `radon` CLI im Sandbox-Runtime nicht verfügbar ist.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from agents.household_agent import Household
from agents.savings_bank_agent import SavingsBank
from config import SimulationConfig
from sim_clock import SimulationClock
from tools.complexity import cyclomatic_complexity


@dataclass(frozen=True)
class DummySaleResult:
    sale_value: float


class DummyRetailer:
    """Minimal retailer stub for isolated Household.consume tests."""

    def __init__(self) -> None:
        self.total_sales = 0.0

    def sell_to_household(self, household: Household, budget: float) -> DummySaleResult:
        paid = household.pay(budget)
        self.total_sales += float(paid)
        return DummySaleResult(sale_value=float(paid))


def test_household_step_refactored():
    """Referenz: doc/issues.md Abschnitt 4 → Gründliches Refaktorieren."""

    cfg = SimulationConfig(simulation_steps=10)
    cfg.household.growth_threshold = 1
    cfg.household.max_generation = 3
    cfg.household.savings_rate = 0.0
    cfg.household.transaction_buffer = 0.0
    cfg.household.sight_growth_trigger = 50.0
    cfg.household.child_rearing_cost = 0.0

    sb = SavingsBank(unique_id="sb", config=cfg)

    h = Household(unique_id="h0", config=cfg)
    h.sight_balance = 100.0

    clock = SimulationClock(cfg.time)

    newborn = h.step(current_step=0, clock=clock, savings_bank=sb, retailers=[])

    assert newborn is not None
    assert isinstance(newborn, Household)
    assert newborn.generation == h.generation + 1

    # The parent should have advanced in age by 1 day.
    assert h.age_days == 1

    # Complexity gate (target: B <= 10)
    rep = cyclomatic_complexity(Household.step)
    assert rep.complexity <= 10
    assert rep.grade in {"A", "B"}


def test_household_consume_extracted():
    """Referenz: doc/issues.md Abschnitt 4 → Gründliches Refaktorieren."""

    cfg = SimulationConfig(simulation_steps=10)
    h = Household(unique_id="h0", config=cfg)
    h.sight_balance = 200.0

    r = DummyRetailer()

    rng = random.Random(0)
    plan = h.build_consumption_plan(consumption_rate=0.5, retailers=[r], rng=rng)

    # build_consumption_plan must be pure: it must not mutate balances.
    assert h.sight_balance == 200.0
    assert plan.budget == 100.0
    assert plan.retailer is r

    spent = h._execute_consumption_plan(plan)
    assert spent == 100.0
    assert h.consumption == 100.0
    assert h.consumption_history[-1] == 100.0


def test_household_handle_finances_stages():
    """Referenz: doc/issues.md Abschnitt 4 → Gründliches Refaktorieren."""

    cfg = SimulationConfig(simulation_steps=30)
    cfg.time.days_per_month = 10  # month-end at step 9, 19, ...
    cfg.household.savings_rate = 0.5
    cfg.household.transaction_buffer = 10.0
    cfg.household.loan_repayment_rate = 0.2

    sb = SavingsBank(unique_id="sb", config=cfg)

    h = Household(unique_id="h0", config=cfg)
    h.sight_balance = 300.0
    sb.active_loans[h.unique_id] = 500.0

    # Month context for saving (surplus = 200)
    h.income_received_this_month = 300.0
    h.consumption_this_month = 100.0

    clock = SimulationClock(cfg.time)

    # pre: repay loan
    h.handle_finances(0, clock=clock, savings_bank=sb, stage="pre")
    assert sb.active_loans[h.unique_id] == 500.0 - 60.0
    assert h.sight_balance == 300.0 - 60.0

    # post: month-end saving
    h.handle_finances(9, clock=clock, savings_bank=sb, stage="post")
    # save_rate=0.5, surplus=200 -> desired 100, but buffer=10
    assert sb.savings_accounts[h.unique_id] == 100.0
    assert h.sight_balance == (300.0 - 60.0) - 100.0
