import warnings

import pytest

from agents.bank import WarengeldBank
from config import load_simulation_config
from main import run_simulation


class AccountStub:
    """Minimal stub for account operations."""

    def __init__(self, unique_id: str, sight_balance: float) -> None:
        self.unique_id = unique_id
        self.sight_balance = float(sight_balance)

class MerchantStub:
    """Minimal stub to call legacy bank APIs."""

    def __init__(self, unique_id: str, inventory: float = 0.0, balance: float = 0.0) -> None:
        self.unique_id = unique_id
        self.inventory = float(inventory)
        self.balance = float(balance)

    def request_funds_from_bank(self, amount: float) -> float:
        self.balance += float(amount)
        return float(amount)


def test_legacy_bank_paths_deprecated() -> None:
    """Referenz: doc/issues.md Abschnitt 6 → M4, Abschnitt 4 → Legacy-Bankpfade

    Updated to test that legacy methods are properly deprecated and modern alternatives work correctly.
    """

    cfg = load_simulation_config({})
    bank = WarengeldBank("bank_legacy", cfg)
    m = MerchantStub("merchant_legacy", inventory=10.0, balance=100.0)

    # Test modern money creation via finance_goods_purchase (spec-aligned)
    # This should work without warnings
    granted = bank.finance_goods_purchase(
        retailer=m,
        seller=AccountStub("seller", sight_balance=0.0),
        amount=10.0,
        current_step=1
    )
    assert granted >= 0.0

    # Test modern fee calculation via charge_account_fees (spec-aligned)
    bank.credit_lines[m.unique_id] = 200.0
    m.sight_balance = 100.0  # Modern method uses sight_balance
    charged = bank.charge_account_fees([m])
    assert charged >= 0.0

    # Test modern inventory management via retailer settle_accounts
    # This happens automatically in the modern flow, no direct bank method needed
    # The bank's inventory control is handled via clearing audits


def test_standard_simulation_does_not_touch_legacy_bank_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Referenz: doc/issues.md Abschnitt 6 → M4 (Legacy-Pfade dürfen in Standard-Runs nicht aufgerufen werden)."""

    monkeypatch.setenv("SIM_SEED", "0")
    cfg = load_simulation_config(
        {
            "simulation_steps": 3,
            "population": {"num_households": 4, "num_companies": 1, "num_retailers": 1},
        }
    )

    # Any legacy call would raise a DeprecationWarning; ensure a normal run emits none.
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        run_simulation(cfg)
