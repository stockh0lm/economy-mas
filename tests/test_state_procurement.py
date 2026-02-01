import pytest

from agents.bank import WarengeldBank
from agents.retailer_agent import RetailerAgent
from agents.state_agent import State
from config import load_simulation_config


def test_state_procurement_transfers_money_and_reduces_inventory() -> None:
    """M1: Staat kauft Waren bei Retailern (Realwirtschaftliche Rückkopplung).

    Expliziter Bezug zu `doc/issues.md`:
    - Abschnitt 6) Prompt-Meilensteine -> M1
    - Abschnitt 2) Abweichungen / Spec-Lücken -> "Staat als realer Nachfrager im Warenkreislauf"
    - Abschnitt 3) Tests / Validierung -> "Neuer Test: Staat kauft Waren bei Retailern"

    Contract:
    - Inventory sinkt exakt um gekaufte Menge
    - State.sight_balance sinkt, Retailer.sight_balance steigt
    - Summe der beiden Sichtguthaben bleibt konstant (geldmengenneutral)
    - Keine Emission/Extinguish Mechanik wird getriggert (Proxy: Bank-Ledger bleibt leer)
    """

    cfg = load_simulation_config(
        {
            "company": {"production_base_price": 10.0},
            "retailer": {
                "price_markup": 0.0,
                "write_down_reserve_share": 0.0,
            },
        }
    )

    bank = WarengeldBank("bank", cfg)

    retailer = RetailerAgent("retailer_0", config=cfg)
    retailer.inventory_units = 10.0
    retailer.inventory_value = 100.0  # avg cost = 10.0

    state = State("state", config=cfg)
    state.infrastructure_budget = 50.0

    sum_before = state.sight_balance + retailer.sight_balance
    inv_before = retailer.inventory_units

    result = retailer.sell_to_state(state, budget=30.0, budget_bucket="infrastructure_budget")

    assert result.sale_value == pytest.approx(30.0)
    assert result.quantity == pytest.approx(3.0)

    assert retailer.inventory_units == pytest.approx(inv_before - 3.0)
    assert state.infrastructure_budget == pytest.approx(50.0 - 30.0)
    assert retailer.sight_balance == pytest.approx(30.0)

    sum_after = state.sight_balance + retailer.sight_balance
    assert sum_after == pytest.approx(sum_before)

    # Proxy for "keine Geldschöpfung": Procurement darf nicht in die Bank-Ledger schreiben.
    assert bank.goods_purchase_ledger == []
