#!/usr/bin/env python3
"""Trace the first 10 simulation steps to confirm the bootstrap failure hypothesis.

For each step, we instrument the key phases:
  Phase 3: Company operations (produce, depreciate, pay_wages)
  Phase 4: Retail restocking (finance_goods_purchase = money creation)
  Phase 5: Household consumption
  Phase 6: Retail settlement (auto_repay_cc = money destruction)

We print balances BEFORE and AFTER each phase to show exact money flows.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from config import load_simulation_config
from simulation.engine import SimulationEngine


def sum_attr(agents, attr):
    return sum(float(getattr(a, attr, 0.0) or 0.0) for a in agents)


def snapshot(engine, label=""):
    """Print a compact snapshot of all agent balances."""
    hh = engine.households
    co = engine.companies
    rt = engine.retailers
    bk = engine.warengeld_banks

    hh_sight = sum_attr(hh, "sight_balance")
    co_sight = sum_attr(co, "sight_balance")
    rt_sight = sum_attr(rt, "sight_balance")
    rt_cc = sum_attr(rt, "cc_balance")
    rt_inv = sum_attr(rt, "inventory_value")
    co_inv = sum_attr(co, "finished_goods_units")
    bk_liq = sum_attr(bk, "sight_balance")

    # M1 = HH_sight + CO_sight + RT_sight (excludes bank's own balance)
    m1 = hh_sight + co_sight + rt_sight

    print(
        f"  {label:30s} | M1={m1:9.2f} | HH={hh_sight:9.2f} CO={co_sight:9.2f} RT={rt_sight:9.2f} | "
        f"RT_CC={rt_cc:9.2f} RT_inv={rt_inv:9.2f} CO_inv={co_inv:9.1f} | BK={bk_liq:9.2f}"
    )


def count_employed(engine):
    return sum(1 for h in engine.households if getattr(h, "employed", False))


def main():
    cfg = load_simulation_config()

    # Try loading from config.yaml for full-scale run
    import os

    yaml_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if os.path.exists(yaml_path):
        from config import load_simulation_config_from_yaml

        cfg = load_simulation_config_from_yaml(yaml_path)

    # Override to small run
    cfg.simulation_steps = 15

    engine = SimulationEngine(cfg)

    print("=" * 140)
    print("BOOTSTRAP TRACE: First 10 steps")
    print(
        f"Agents: {len(engine.households)} HH, {len(engine.companies)} CO, "
        f"{len(engine.retailers)} RT, {len(engine.warengeld_banks)} BK"
    )
    print("=" * 140)

    # Initial state
    print(f"\n--- INITIAL STATE (before any step) ---")
    snapshot(engine, "INITIAL")
    print(f"  Employed HH: {count_employed(engine)}")

    # Show initial CC limits
    for bk in engine.warengeld_banks:
        for rid, limit in bk.cc_limits.items():
            print(f"  Bank {bk.unique_id}: retailer {rid} cc_limit={limit:.2f}")

    # We need to manually step through phases to see intermediate states.
    # Unfortunately the engine.step() method doesn't expose intermediate states,
    # so we'll run step() and capture before/after for the whole step,
    # plus monkey-patch key methods to trace them.

    # Monkey-patch approach: wrap key methods to log flows
    from agents.company_agent import Company
    from agents.retailer_agent import RetailerAgent
    from agents.bank import WarengeldBank

    original_pay_wages = Company.pay_wages
    total_wages_paid = [0.0]

    def traced_pay_wages(self, wage_rate=None):
        result = original_pay_wages(self, wage_rate)
        total_wages_paid[0] += result
        return result

    Company.pay_wages = traced_pay_wages

    # Use functools.wraps-style approach: save unbound methods, call with self
    _orig_finance = WarengeldBank.finance_goods_purchase
    total_financed = [0.0]

    def traced_finance(self, *, retailer, seller, amount, current_step=None):
        result = _orig_finance(
            self, retailer=retailer, seller=seller, amount=amount, current_step=current_step
        )
        total_financed[0] += result
        return result

    WarengeldBank.finance_goods_purchase = traced_finance  # type: ignore

    _orig_auto_repay = WarengeldBank.auto_repay_cc_from_sight
    total_repaid = [0.0]

    def traced_auto_repay(self, retailer):
        result = _orig_auto_repay(self, retailer)
        total_repaid[0] += result
        return result

    WarengeldBank.auto_repay_cc_from_sight = traced_auto_repay  # type: ignore

    _orig_sell_to_hh = RetailerAgent.sell_to_household
    total_hh_spending = [0.0]

    def traced_sell_to_hh(self, household, budget):
        result = _orig_sell_to_hh(self, household, budget)
        total_hh_spending[0] += result.sale_value
        return result

    RetailerAgent.sell_to_household = traced_sell_to_hh  # type: ignore

    for step_i in range(10):
        total_wages_paid[0] = 0.0
        total_financed[0] = 0.0
        total_repaid[0] = 0.0
        total_hh_spending[0] = 0.0

        print(f"\n{'=' * 140}")
        print(f"STEP {step_i}")
        print(f"{'=' * 140}")

        snapshot(engine, f"BEFORE step {step_i}")
        print(f"  Employed HH: {count_employed(engine)}")

        engine.step()

        snapshot(engine, f"AFTER step {step_i}")
        print(f"  Employed HH: {count_employed(engine)}")
        print(
            f"  Flows: wages_paid={total_wages_paid[0]:.2f}, "
            f"restocking(money_created)={total_financed[0]:.2f}, "
            f"hh_spending={total_hh_spending[0]:.2f}, "
            f"cc_repaid(money_destroyed)={total_repaid[0]:.2f}"
        )

        # Per-company balance detail (first 5)
        print(f"  Company balances (first 5): ", end="")
        for c in engine.companies[:5]:
            emps = len(c.employees)
            print(
                f"{c.unique_id}(bal={c.sight_balance:.2f},emp={emps},inv={c.finished_goods_units:.0f}) ",
                end="",
            )
        print()

        # Per-retailer balance detail
        print(f"  Retailer balances: ", end="")
        for r in engine.retailers:
            print(
                f"{r.unique_id}(sight={r.sight_balance:.2f},cc={r.cc_balance:.2f},"
                f"inv={r.inventory_value:.2f}) ",
                end="",
            )
        print()

        # HH spending power
        hh_with_money = sum(1 for h in engine.households if h.sight_balance > 0.01)
        hh_total_balance = sum_attr(engine.households, "sight_balance")
        print(
            f"  HH with money: {hh_with_money}/{len(engine.households)}, "
            f"total HH balance: {hh_total_balance:.2f}"
        )

    print(f"\n{'=' * 140}")
    print("TRACE COMPLETE")
    print("=" * 140)


if __name__ == "__main__":
    main()
