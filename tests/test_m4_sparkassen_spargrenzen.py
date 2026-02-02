from config import SimulationConfig

from agents.company_agent import Company
from agents.household_agent import Household
from agents.savings_bank_agent import SavingsBank


def test_sparkassen_spargrenzen():
    """Referenz: doc/issues.md Abschnitt 2 → Sparkassen-Regeln (Spargrenze / Invest-Nachfrage-Kopplung)"""

    cfg = SimulationConfig()
    cfg.savings_bank.max_savings_household = 100.0
    cfg.savings_bank.max_savings_company = 1000.0
    cfg.savings_bank.savings_cap_demand_coupling_strength = 0.0  # deterministic baseline

    sb = SavingsBank(unique_id="savings_bank_0", config=cfg)
    h = Household(unique_id="household_0", config=cfg)
    c = Company(unique_id="company_0", production_capacity=10.0, config=cfg, labor_market=None)

    assert sb.deposit_savings(h, 500.0) == 100.0
    assert sb.savings_accounts[h.unique_id] == 100.0

    assert sb.deposit_savings(c, 5000.0) == 1000.0
    assert sb.savings_accounts[c.unique_id] == 1000.0

    # Coupling: with zero expected demand, cap is scaled down.
    cfg2 = SimulationConfig()
    cfg2.savings_bank.max_savings_household = 100.0
    cfg2.savings_bank.savings_cap_demand_coupling_strength = 1.0
    cfg2.savings_bank.savings_cap_min_scale = 0.5
    cfg2.savings_bank.savings_cap_max_scale = 2.0

    sb2 = SavingsBank(unique_id="savings_bank_0", config=cfg2)
    h2 = Household(unique_id="household_0", config=cfg2)
    assert sb2.deposit_savings(h2, 500.0) == 50.0

    # If investment need exists, the proxy raises expected demand and can scale cap up.
    c2 = Company(unique_id="company_0", production_capacity=10.0, config=cfg2, labor_market=None)
    c2.sight_balance = 0.0
    sb2.step(current_step=0, companies=[c2])
    # Demand > 0 => ratio large => cap hits max_scale => 200 total cap (another 150 room)
    assert sb2.deposit_savings(h2, 500.0) == 150.0