#!/usr/bin/env python3
"""Analyse der 'Verhakung' (systemic seizure) in der Wirtschaftssimulation.

Liest die CSV-Metriken des letzten langen Laufs und identifiziert:
1. Wann und wie sich das System verhakt
2. Wo das Geld steckenbleibt (Firmen? Haushalte? Staat?)
3. Ursache-Wirkungs-Ketten der Blockade
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

TIMESTAMP = "20260209_004213"
METRICS = Path("output/metrics")

# ── Helpers ──────────────────────────────────────────────────────────────────


def load_csv(prefix: str) -> list[dict[str, str]]:
    path = METRICS / f"{prefix}_{TIMESTAMP}.csv"
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def flt(row: dict, key: str) -> float:
    v = row.get(key, "0")
    try:
        return float(v) if v else 0.0
    except ValueError:
        return 0.0


# ── Load data ────────────────────────────────────────────────────────────────

print("Loading data...", flush=True)
global_rows = load_csv("global_metrics")
company_rows = load_csv("company_metrics")
household_rows = load_csv("household_metrics")
retailer_rows = load_csv("retailer_metrics")
bank_rows = load_csv("bank_metrics")
state_rows = load_csv("state_metrics")

total_steps = len(global_rows)
print(f"  Global: {total_steps} steps")
print(f"  Company rows: {len(company_rows)}")
print(f"  Household rows: {len(household_rows)}")
print(f"  Retailer rows: {len(retailer_rows)}")

# ── 1. Macro overview: M1, velocity, sales around the Verhakung ──────────

print("\n" + "=" * 80)
print("1. MACRO OVERVIEW: M1, Velocity, Sales, CC Exposure")
print("=" * 80)

# Sample every 200 steps, plus dense around 3800-6000
sample_steps = set(range(0, total_steps, 200))
sample_steps.update(range(3800, min(6200, total_steps), 50))
sample_steps = sorted(sample_steps)

print(
    f"\n{'Step':>6} {'M1':>10} {'Velocity':>10} {'Sales':>10} {'CC_exp':>10} "
    f"{'Inv_val':>10} {'HH':>5} {'CO':>5} {'Empl%':>7} {'Price':>8} {'Births':>7} {'Deaths':>7}"
)
print("-" * 110)

for step in sample_steps:
    if step >= len(global_rows):
        continue
    r = global_rows[step]
    print(
        f"{step:>6} {flt(r, 'm1_proxy'):>10.1f} {flt(r, 'velocity_proxy'):>10.4f} "
        f"{flt(r, 'sales_total'):>10.1f} {flt(r, 'cc_exposure'):>10.1f} "
        f"{flt(r, 'inventory_value_total'):>10.1f} {flt(r, 'total_households'):>5.0f} "
        f"{flt(r, 'total_companies'):>5.0f} {flt(r, 'employment_rate'):>6.1f}% "
        f"{flt(r, 'price_index'):>8.1f} {flt(r, 'births'):>7.0f} {flt(r, 'deaths'):>7.0f}"
    )

# ── 2. Money location: Where is all the money? ──────────────────────────

print("\n" + "=" * 80)
print("2. MONEY LOCATION: Where does money accumulate?")
print("=" * 80)


# Group household/company/retailer balances by step
def aggregate_by_step(rows: list[dict], balance_key: str) -> dict[int, float]:
    totals: dict[int, float] = defaultdict(float)
    for r in rows:
        step = int(flt(r, "time_step"))
        totals[step] += flt(r, balance_key)
    return dict(totals)


print("\nAggregating balances by step (this may take a moment)...", flush=True)

hh_balances = defaultdict(float)
hh_savings = defaultdict(float)
hh_wealth = defaultdict(float)
hh_income = defaultdict(float)
hh_consumption = defaultdict(float)
hh_count = defaultdict(int)
for r in household_rows:
    step = int(flt(r, "time_step"))
    hh_balances[step] += flt(r, "checking_account")
    hh_savings[step] += flt(r, "savings")
    hh_wealth[step] += flt(r, "total_wealth")
    hh_income[step] += flt(r, "income")
    hh_consumption[step] += flt(r, "consumption")
    hh_count[step] += 1

co_balances = defaultdict(float)
co_inventory = defaultdict(float)
co_employees = defaultdict(float)
co_count = defaultdict(int)
for r in company_rows:
    step = int(flt(r, "time_step"))
    co_balances[step] += flt(r, "sight_balance")
    co_inventory[step] += flt(r, "inventory")
    co_employees[step] += flt(r, "employees")
    co_count[step] += 1

rt_sight = defaultdict(float)
rt_cc = defaultdict(float)
rt_inv = defaultdict(float)
rt_sales = defaultdict(float)
rt_purchases = defaultdict(float)
rt_repaid = defaultdict(float)
rt_count = defaultdict(int)
for r in retailer_rows:
    step = int(flt(r, "time_step"))
    rt_sight[step] += flt(r, "sight_balance")
    rt_cc[step] += flt(r, "cc_balance")
    rt_inv[step] += flt(r, "inventory_value")
    rt_sales[step] += flt(r, "sales_total")
    rt_purchases[step] += flt(r, "purchases_total")
    rt_repaid[step] += flt(r, "repaid_total")
    rt_count[step] += 1

st_balances: dict[int, float] = {}
for r in state_rows:
    step = int(flt(r, "time_step"))
    # State has multiple balance fields; sum relevant ones
    infra = flt(r, "infrastructure_budget") if "infrastructure_budget" in r else 0
    social = flt(r, "social_budget") if "social_budget" in r else 0
    env_b = flt(r, "environment_budget") if "environment_budget" in r else 0
    revenue = flt(r, "tax_revenue") if "tax_revenue" in r else 0
    st_balances[step] = infra + social + env_b

bk_liquidity = defaultdict(float)
bk_savings_total = defaultdict(float)
for r in bank_rows:
    step = int(flt(r, "time_step"))
    bk_liquidity[step] += flt(r, "liquidity")
    bk_savings_total[step] += flt(r, "total_savings")

print(
    f"\n{'Step':>6} {'HH_check':>10} {'HH_save':>10} {'CO_sight':>10} "
    f"{'RT_sight':>10} {'RT_cc':>10} {'ST_budg':>10} {'BK_liq':>10} "
    f"{'BK_save':>10} {'Sum':>12}"
)
print("-" * 120)

for step in sample_steps:
    if step not in hh_balances:
        continue
    hh = hh_balances.get(step, 0)
    hs = hh_savings.get(step, 0)
    co = co_balances.get(step, 0)
    rt = rt_sight.get(step, 0)
    rc = rt_cc.get(step, 0)
    st = st_balances.get(step, 0)
    bl = bk_liquidity.get(step, 0)
    bs = bk_savings_total.get(step, 0)
    total = hh + hs + co + rt + st + bl
    print(
        f"{step:>6} {hh:>10.1f} {hs:>10.1f} {co:>10.1f} "
        f"{rt:>10.1f} {rc:>10.1f} {st:>10.1f} {bl:>10.1f} "
        f"{bs:>10.1f} {total:>12.1f}"
    )

# ── 3. Flow analysis: Production, Sales, Wages around Verhakung ──────────

print("\n" + "=" * 80)
print("3. FLOW ANALYSIS: Company production, wages, retailer restock")
print("=" * 80)

print(
    f"\n{'Step':>6} {'CO_inv':>10} {'CO_empl':>8} {'RT_purch':>10} "
    f"{'RT_sales':>10} {'RT_repaid':>10} {'HH_inc':>10} {'HH_cons':>10} "
    f"{'RT_inv':>10}"
)
print("-" * 110)

for step in sample_steps:
    if step not in co_inventory:
        continue
    print(
        f"{step:>6} {co_inventory.get(step, 0):>10.1f} {co_employees.get(step, 0):>8.0f} "
        f"{rt_purchases.get(step, 0):>10.1f} {rt_sales.get(step, 0):>10.1f} "
        f"{rt_repaid.get(step, 0):>10.1f} {hh_income.get(step, 0):>10.1f} "
        f"{hh_consumption.get(step, 0):>10.1f} {rt_inv.get(step, 0):>10.1f}"
    )

# ── 4. Per-company analysis around the Verhakung ─────────────────────────

print("\n" + "=" * 80)
print("4. PER-COMPANY DETAIL around step 4000")
print("=" * 80)

# Get companies active around step 4000
companies_at_4000 = [r for r in company_rows if int(flt(r, "time_step")) == 4000]
print(f"\nCompanies at step 4000 ({len(companies_at_4000)}):")
for r in companies_at_4000:
    print(
        f"  {r['agent_id']}: sight={flt(r, 'sight_balance'):.1f}, "
        f"inv={flt(r, 'inventory'):.1f}, empl={flt(r, 'employees'):.0f}, "
        f"capacity={flt(r, 'production_capacity'):.0f}"
    )

# Track one company over time
if companies_at_4000:
    sample_co = companies_at_4000[0]["agent_id"]
    print(f"\nTracking {sample_co} over time:")
    print(f"{'Step':>6} {'Sight':>10} {'Inventory':>10} {'Empl':>6} {'Capacity':>10}")
    for r in company_rows:
        if r["agent_id"] != sample_co:
            continue
        step = int(flt(r, "time_step"))
        if step in sample_steps:
            print(
                f"{step:>6} {flt(r, 'sight_balance'):>10.1f} {flt(r, 'inventory'):>10.1f} "
                f"{flt(r, 'employees'):>6.0f} {flt(r, 'production_capacity'):>10.0f}"
            )

# ── 5. Retailer detail: CC limits, purchases, headroom ───────────────────

print("\n" + "=" * 80)
print("5. PER-RETAILER DETAIL around step 4000")
print("=" * 80)

retailers_at_4000 = [r for r in retailer_rows if int(flt(r, "time_step")) == 4000]
print(f"\nRetailers at step 4000 ({len(retailers_at_4000)}):")
for r in retailers_at_4000:
    headroom = flt(r, "cc_limit") + flt(r, "cc_balance")
    print(
        f"  {r['agent_id']}: sight={flt(r, 'sight_balance'):.1f}, "
        f"cc_bal={flt(r, 'cc_balance'):.1f}, cc_limit={flt(r, 'cc_limit'):.1f}, "
        f"headroom={headroom:.1f}, inv={flt(r, 'inventory_value'):.1f}, "
        f"sales={flt(r, 'sales_total'):.2f}, purchases={flt(r, 'purchases_total'):.2f}"
    )

# ── 6. Detect the Verhakung: when do sales collapse? ─────────────────────

print("\n" + "=" * 80)
print("6. VERHAKUNG DETECTION: When do key metrics collapse?")
print("=" * 80)

# Find the step where sales_total drops below 50% of peak
peak_sales = 0.0
peak_step = 0
collapse_step = None
for step, r in enumerate(global_rows):
    sales = flt(r, "sales_total")
    if sales > peak_sales:
        peak_sales = sales
        peak_step = step
    if (
        peak_sales > 0
        and sales < peak_sales * 0.3
        and step > peak_step + 100
        and collapse_step is None
    ):
        collapse_step = step

print(f"\nPeak sales: {peak_sales:.1f} at step {peak_step}")
if collapse_step:
    print(f"Sales collapse (<30% of peak): step {collapse_step}")

# Find when M1 starts declining
m1_values = [(i, flt(r, "m1_proxy")) for i, r in enumerate(global_rows)]
m1_peak = max(m1_values, key=lambda x: x[1])
print(f"Peak M1: {m1_peak[1]:.1f} at step {m1_peak[0]}")

# Detect sustained decline
for i in range(m1_peak[0], len(m1_values) - 100, 50):
    window = m1_values[i : i + 100]
    if all(v < m1_peak[1] * 0.7 for _, v in window):
        print(f"Sustained M1 decline below 70% of peak starts around step {i}")
        break

# ── 7. Household wealth distribution ─────────────────────────────────────

print("\n" + "=" * 80)
print("7. HOUSEHOLD WEALTH DISTRIBUTION at key moments")
print("=" * 80)

for check_step in [1000, 3000, 4000, 5000, 5800]:
    hh_at_step = [r for r in household_rows if int(flt(r, "time_step")) == check_step]
    if not hh_at_step:
        continue
    balances = sorted([flt(r, "checking_account") for r in hh_at_step])
    savings = sorted([flt(r, "savings") for r in hh_at_step])
    incomes = [flt(r, "income") for r in hh_at_step]
    employed = sum(1 for r in hh_at_step if flt(r, "employed") > 0)
    total_bal = sum(balances)
    total_sav = sum(savings)
    zero_bal = sum(1 for b in balances if b < 1.0)

    print(f"\nStep {check_step}: {len(hh_at_step)} HH, {employed} employed")
    print(
        f"  Checking: total={total_bal:.1f}, min={balances[0]:.1f}, "
        f"median={balances[len(balances) // 2]:.1f}, max={balances[-1]:.1f}, "
        f"zero(<1)={zero_bal}"
    )
    print(f"  Savings:  total={total_sav:.1f}, min={savings[0]:.1f}, max={savings[-1]:.1f}")
    print(f"  Income:   total={sum(incomes):.1f}, avg={sum(incomes) / max(1, len(incomes)):.1f}")

# ── 8. Money creation vs destruction ─────────────────────────────────────

print("\n" + "=" * 80)
print("8. MONEY CREATION vs DESTRUCTION")
print("=" * 80)

print(f"\n{'Step':>6} {'Issuance':>10} {'Extinguish':>10} {'Net':>10} {'M1':>10}")
print("-" * 60)

for step in sample_steps:
    if step >= len(global_rows):
        continue
    r = global_rows[step]
    iss = flt(r, "issuance_volume")
    ext = flt(r, "extinguish_volume")
    m1 = flt(r, "m1_proxy")
    print(f"{step:>6} {iss:>10.1f} {ext:>10.1f} {iss - ext:>10.1f} {m1:>10.1f}")

# ── 9. Company balance vs wages analysis ─────────────────────────────────

print("\n" + "=" * 80)
print("9. COMPANY MONEY ACCUMULATION: Does money get stuck in companies?")
print("=" * 80)

# Sum company sight_balance over time
print(
    f"\n{'Step':>6} {'CO total sight':>15} {'CO count':>10} {'CO avg sight':>12} "
    f"{'CO total inv':>12} {'CO avg inv':>10}"
)
print("-" * 80)

for step in sample_steps:
    if step not in co_balances:
        continue
    cnt = co_count.get(step, 1)
    print(
        f"{step:>6} {co_balances[step]:>15.1f} {cnt:>10} "
        f"{co_balances[step] / max(1, cnt):>12.1f} "
        f"{co_inventory[step]:>12.1f} {co_inventory[step] / max(1, cnt):>10.1f}"
    )

print("\nDone.")
