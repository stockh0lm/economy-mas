from config import SimulationConfig
from main import _m1_proxy, run_simulation


def test_golden_run_detailed(monkeypatch, tmp_path):
    """Detailed debug version to track money creation"""

    monkeypatch.setenv("SIM_SEED", "12345")

    cfg = SimulationConfig(simulation_steps=30)
    cfg.log_file = str(tmp_path / "sim.log")
    cfg.metrics_export_path = str(tmp_path / "metrics.json")

    # Run simulation with detailed logging
    agents = run_simulation(cfg)

    households = agents["households"]
    companies = agents["companies"]
    retailers = agents["retailers"]
    state = agents["state"]
    warengeld_banks = agents["warengeld_banks"]

    m1 = _m1_proxy(households=households, companies=companies, retailers=retailers, state=state)
    total_inventory_value = sum(float(r.inventory_value) for r in retailers)
    total_cc_exposure = sum(float(b.total_cc_exposure) for b in warengeld_banks)

    employed = sum(1 for h in households if getattr(h, "employer_id", None) is not None)
    employment_rate = employed / max(1, len(households))

    print(f"\n=== DETAILED ANALYSIS ===")
    print(f"M1: {m1:.2f}")
    print(f"Total CC exposure: {total_cc_exposure:.2f}")
    print(f"Total inventory value: {total_inventory_value:.2f}")

    # Check retailer CC usage
    print(f"\n=== RETAILER CC USAGE ===")
    for i, r in enumerate(retailers):
        cc_balance = getattr(r, "cc_balance", 0.0)
        cc_limit = getattr(r, "cc_limit", 0.0)
        cc_utilization = (cc_limit + cc_balance) / cc_limit if cc_limit > 0 else 0.0
        print(
            f"Retailer {i}: cc_balance={cc_balance:.2f}, cc_limit={cc_limit:.2f}, utilization={cc_utilization:.2%}"
        )

    # Check bank credit lines
    print(f"\n=== BANK CREDIT LINES ===")
    for i, b in enumerate(warengeld_banks):
        print(f"Bank {i}: credit_lines={dict(b.credit_lines)}")

    # Check company production
    print(f"\n=== COMPANY PRODUCTION ===")
    for i, c in enumerate(companies):
        finished_goods = getattr(c, "finished_goods_units", 0.0)
        production_capacity = getattr(c, "production_capacity", 0.0)
        print(
            f"Company {i}: finished_goods={finished_goods:.2f}, capacity={production_capacity:.2f}"
        )

    # Check household consumption
    print(f"\n=== HOUSEHOLD CONSUMPTION ===")
    total_consumption = sum(float(h.consumption) for h in households)
    print(f"Total consumption: {total_consumption:.2f}")
    for i, h in enumerate(households):
        print(f"Household {i}: consumption={h.consumption:.2f}, balance={h.balance:.2f}")

    # Check money flows
    print(f"\n=== MONEY FLOWS ===")
    print(f"Household balances sum: {sum(float(h.balance) for h in households):.2f}")
    print(f"Company balances sum: {sum(float(c.balance) for c in companies):.2f}")
    print(f"Retailer balances sum: {sum(float(r.balance) for r in retailers):.2f}")
    print(f"M1 calculation: {m1:.2f}")

    # Check if retailers are restocking
    print(f"\n=== RETAILER RESTOCKING ===")
    for i, r in enumerate(retailers):
        reorder_point = cfg.retailer.reorder_point_ratio * r.target_inventory_value
        print(
            f"Retailer {i}: inventory={r.inventory_value:.2f}, target={r.target_inventory_value:.2f}, reorder_point={reorder_point:.2f}"
        )
        print(f"  -> Should restock: {r.inventory_value < reorder_point}")

    # Check CC limits vs actual usage
    print(f"\n=== CC LIMIT ANALYSIS ===")
    for i, r in enumerate(retailers):
        cc_balance = getattr(r, "cc_balance", 0.0)
        cc_limit = getattr(r, "cc_limit", 0.0)
        headroom = max(0.0, float(cc_limit) + float(cc_balance))
        print(f"Retailer {i}: headroom={headroom:.2f}, can purchase up to {headroom:.2f}")
