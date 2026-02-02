import math

import pandas as pd
import pytest

from scripts.compare_posthoc import compute_counterfactual


def test_posthoc_recompute() -> None:
    """Referenz: doc/issues.md Abschnitt 5 → Implement Option A"""

    # Arrange: synthetische Minimal-Serie (3 Schritte)
    df = pd.DataFrame(
        {
            "time_step": [0, 1, 2],
            "m1_proxy": [100.0, 120.0, 120.0],
            "goods_tx_volume": [50.0, 60.0, 70.0],
            "service_tx_volume": [0.0, 20.0, 20.0],
            "service_value_total": [0.0, 20.0, 20.0],
            "service_share_of_output": [0.0, 0.25, 0.2222222222],
            "total_money_supply": [100.0, 120.0, 120.0],
            # gdp enthält Services (angenommen)
            "gdp": [100.0, 120.0, 120.0],
            "household_consumption": [50.0, 60.0, 70.0],
            # Original-Preisbildung: hier so gewählt, dass pressure==target => stabil
            "price_index": [100.0, 100.0, 100.0],
            "inflation_rate": [0.0, 0.0, 0.0],
        }
    )

    # Act
    cf = compute_counterfactual(df, assume_services_in_gdp=True)

    # Assert: Services komplett entfernt
    assert (cf["service_tx_volume"] == 0.0).all()
    assert (cf["service_value_total"] == 0.0).all()
    assert (cf["service_share_of_output"] == 0.0).all()

    # Assert: goods_only_velocity = goods_tx_volume / m1_proxy
    assert cf.loc[0, "goods_only_velocity"] == pytest.approx(50.0 / 100.0)
    assert cf.loc[1, "goods_only_velocity"] == pytest.approx(60.0 / 120.0)

    # Assert: gdp_alt = gdp - service_value_total(original)
    assert cf.loc[0, "gdp_alt"] == pytest.approx(100.0 - 0.0)
    assert cf.loc[1, "gdp_alt"] == pytest.approx(120.0 - 20.0)

    # Assert: price_index_alt folgt der (kopierten) Preis-Formel (stabilisiert / konvergent)
    # Default-Config: price_index_base=100, target=1.0, sensitivity=0.05, mode=money_supply_to_gdp.
    # Step 0: pressure=1.0 => desired=100 -> price 100
    # Step 1: pressure=1.2 => desired=120 -> price = 100 + 0.05*(120-100) = 101
    expected_p1 = 100.0 + 0.05 * (120.0 - 100.0)
    assert cf.loc[0, "price_index_alt"] == pytest.approx(100.0)
    assert cf.loc[1, "price_index_alt"] == pytest.approx(expected_p1)

    # Step 2 repeats the same pressure => converges further (no endless compounding)
    expected_p2 = expected_p1 + 0.05 * (120.0 - expected_p1)
    assert cf.loc[2, "price_index_alt"] == pytest.approx(expected_p2)
    assert cf.loc[1, "inflation_rate_alt"] == pytest.approx((expected_p1 - 100.0) / 100.0)
    assert cf.loc[2, "inflation_rate_alt"] == pytest.approx((expected_p2 - expected_p1) / expected_p1)

    # Sanity: finite numbers
    assert all(math.isfinite(x) for x in cf["price_index_alt"].tolist())
