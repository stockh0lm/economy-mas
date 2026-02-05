from config import SimulationConfig
from main import _m1_proxy, run_simulation


def test_golden_run_debug(monkeypatch, tmp_path):
    """Debug version to examine simulation trajectory"""

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

    print(f"\n=== FINAL METRICS ===")
    print(f"M1: {m1:.2f}")
    print(f"Total inventory value: {total_inventory_value:.2f}")
    print(f"Total CC exposure: {total_cc_exposure:.2f}")
    print(f"Employment rate: {employment_rate:.2f}")
    print(f"Households: {len(households)}")
    print(f"Retailers: {len(retailers)}")
    print(f"Companies: {len(companies)}")

    # Print household balances
    print(f"\n=== HOUSEHOLD BALANCES ===")
    for i, h in enumerate(households):
        print(f"Household {i}: balance={h.balance:.2f}, employer={getattr(h, 'employer_id', None)}")

    # Print retailer metrics
    print(f"\n=== RETAILER METRICS ===")
    for i, r in enumerate(retailers):
        print(f"Retailer {i}: balance={r.balance:.2f}, inventory_value={r.inventory_value:.2f}")

    # Print company metrics
    print(f"\n=== COMPANY METRICS ===")
    for i, c in enumerate(companies):
        print(f"Company {i}: balance={c.balance:.2f}")

    # Print warengeld bank metrics
    print(f"\n=== WARENGELD BANK METRICS ===")
    for i, b in enumerate(warengeld_banks):
        print(f"Bank {i}: total_cc_exposure={b.total_cc_exposure:.2f}")

    # Check assertions
    print(f"\n=== ASSERTION CHECKS ===")
    print(
        f"Households count: {len(households)} (expected 4) - {'PASS' if len(households) == 4 else 'FAIL'}"
    )
    print(
        f"Retailers count: {len(retailers)} (expected 2) - {'PASS' if len(retailers) == 2 else 'FAIL'}"
    )
    print(f"M1 range: {m1:.2f} (expected 180-220) - {'PASS' if 180.0 <= m1 <= 220.0 else 'FAIL'}")
    print(
        f"Inventory value range: {total_inventory_value:.2f} (expected 250-310) - {'PASS' if 250.0 <= total_inventory_value <= 310.0 else 'FAIL'}"
    )
    print(
        f"CC exposure range: {total_cc_exposure:.2f} (expected 180-260) - {'PASS' if 180.0 <= total_cc_exposure <= 260.0 else 'FAIL'}"
    )
    print(
        f"Employment rate range: {employment_rate:.2f} (expected 0.75-1.0) - {'PASS' if 0.75 <= employment_rate <= 1.0 else 'FAIL'}"
    )
