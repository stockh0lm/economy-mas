import pytest

from agents.company_agent import Company
from agents.household_agent import Household
from config import load_simulation_config
from metrics import MetricsCollector


def test_dienstleistungs_sektor_geldneutral() -> None:
    """Referenz: doc/issues.md Abschnitt 6 → M3, Abschnitt 5 → „Dienstleistungs-Wertschöpfung…“, Abschnitt 3 → Test „Dienstleistungs-Sektor…"""

    # Arrange: Haushalte mit Sight; Service-Empfänger (Company) mit Sight
    config = load_simulation_config({})
    collector = MetricsCollector(config=config)

    h = Household("H0", config=config)
    h.sight_balance = 100.0

    provider = Company("C0", production_capacity=100.0, config=config)
    provider.sight_balance = 0.0

    # Baseline snapshot (no service yet)
    collector.collect_household_metrics([h], step=0)
    collector.collect_company_metrics([provider], step=0)
    collector.collect_retailer_metrics([], step=0)
    collector.collect_bank_metrics([], step=0)
    collector.calculate_global_metrics(0)
    baseline = collector.global_metrics[0]
    issuance_before = float(baseline.get("issuance_volume", 0.0))
    money_before = float(baseline.get("total_money_supply", 0.0))

    # Act: Service-Transaktion durchführen
    paid = provider.sell_service_to_household(h, budget=25.0)
    assert paid > 0

    # Re-collect at same step to compare invariants after the service booking
    collector.collect_household_metrics([h], step=0)
    collector.collect_company_metrics([provider], step=0)
    collector.collect_retailer_metrics([], step=0)
    collector.collect_bank_metrics([], step=0)
    collector.calculate_global_metrics(0)
    metrics = collector.global_metrics[0]

    # Assert: service_tx_volume steigt
    assert float(metrics.get("service_tx_volume", 0.0)) == pytest.approx(paid)

    # Assert: keine Geldschöpfung (issuance_volume unverändert, MoneySupply invariant)
    assert float(metrics.get("issuance_volume", 0.0)) == pytest.approx(issuance_before)
    assert float(metrics.get("total_money_supply", 0.0)) == pytest.approx(money_before)

    # Assert: Saldenumverteilung korrekt
    assert h.sight_balance == pytest.approx(100.0 - paid)
    assert provider.sight_balance == pytest.approx(paid)
