import os

from config import SimulationConfig
from main import run_simulation


def _sum_global(collector, key: str) -> float:
    return float(sum(float(m.get(key, 0.0) or 0.0) for m in collector.global_metrics.values()))


def test_wachstums_sterbe_verhalten(monkeypatch, tmp_path):
    """Referenz: doc/issues.md Abschnitt 4 → Einfaches Wachstums- und Sterbe-Verhalten.

    This test focuses on:
    - Geburten/Haushaltsgründung via fertility model
    - Sterben via mortality model (incl. turnover)
    - Company growth/death via split + merger hooks
    """

    # --- A) Fertility should create births even without deaths (rates configurable) ---
    cfg = SimulationConfig(simulation_steps=30)
    cfg.log_file = str(tmp_path / "m1a.log")
    cfg.metrics_export_path = str(tmp_path / "m1a_metrics")

    cfg.population.num_households = 40
    cfg.population.num_companies = 3
    cfg.population.num_retailers = 2

    # Make households liquid so endowment transfers are possible.
    cfg.company.base_wage = 20.0
    cfg.household.consumption_rate_normal = 0.1
    cfg.household.consumption_rate_growth = 0.1

    # Disable split-growth births to isolate the fertility mechanism.
    cfg.household.savings_growth_trigger = 1e9
    cfg.household.sight_growth_trigger = 1e9
    cfg.household.growth_threshold = 999

    # No deaths in run A (avoid age-max edge by seeding only younger ages).
    cfg.household.mortality_base_annual = 0.0
    cfg.household.mortality_senescence_annual = 0.0
    cfg.household.initial_age_min_years = 18
    cfg.household.initial_age_mode_years = 28
    cfg.household.initial_age_max_years = 40

    cfg.household.fertility_base_annual = 4.0
    cfg.household.birth_endowment_share = 0.15

    # Keep company demography quiet in run A.
    cfg.company.founding_base_annual = 0.0
    cfg.company.merger_rate_annual = 0.0
    cfg.company.growth_threshold = 999
    cfg.company.investment_threshold = 1e9

    monkeypatch.setenv("SIM_SEED", "123")
    agents_a = run_simulation(cfg)
    collector_a = agents_a["metrics_collector"]

    births_a = _sum_global(collector_a, "births")
    deaths_a = _sum_global(collector_a, "deaths")
    assert births_a > 0, "Fertility births should occur when fertility_base_annual is high"
    assert deaths_a == 0, "No deaths expected when mortality is disabled and ages are below max_age"

    ages = [int(getattr(h, "age", 0)) for h in agents_a["households"]]
    assert max(ages) > min(ages), "Initial age distribution should not be degenerate"

    # Integration: goods cycle should have created trade ledger entries.
    banks = agents_a.get("warengeld_banks", [agents_a["warengeld_bank"]])
    assert any(len(getattr(b, "goods_purchase_ledger", [])) > 0 for b in banks)

    # --- B) Mortality + company merger/split should produce deaths and births ---
    cfg_b = SimulationConfig(simulation_steps=10)
    cfg_b.log_file = str(tmp_path / "m1b.log")
    cfg_b.metrics_export_path = str(tmp_path / "m1b_metrics")

    cfg_b.population.num_households = 30
    cfg_b.population.num_companies = 3
    cfg_b.population.num_retailers = 1

    # Force household turnover.
    cfg_b.household.mortality_base_annual = 5.0
    cfg_b.household.mortality_senescence_annual = 0.0
    cfg_b.household.initial_age_min_years = 50
    cfg_b.household.initial_age_mode_years = 60
    cfg_b.household.initial_age_max_years = 70

    # Allow company splits to create births.
    cfg_b.company.investment_threshold = 0.0
    cfg_b.company.growth_threshold = 1
    # Force mergers daily to create company deaths.
    cfg_b.company.merger_rate_annual = float(cfg_b.time.days_per_year)
    cfg_b.company.merger_distress_threshold = 1.0
    cfg_b.company.merger_min_acquirer_balance = 0.0
    cfg_b.company.founding_base_annual = 0.0

    monkeypatch.setenv("SIM_SEED", "123")
    agents_b = run_simulation(cfg_b)
    collector_b = agents_b["metrics_collector"]

    deaths_b = _sum_global(collector_b, "deaths")
    company_births_b = _sum_global(collector_b, "company_births")
    company_deaths_b = _sum_global(collector_b, "company_deaths")

    assert deaths_b > 0, "Household deaths should occur when mortality_base_annual is high"
    assert company_births_b > 0, "Company splits should occur when investment_threshold=0 and growth_threshold=1"
    assert company_deaths_b > 0, "Company mergers should remove at least one company"
