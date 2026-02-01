import textwrap
from pathlib import Path

import pytest

from agents.bank import WarengeldBank
from main import load_config


class AccountStub:
    def __init__(self, unique_id: str, sight_balance: float) -> None:
        self.unique_id = unique_id
        self.sight_balance = float(sight_balance)


def test_config_consistency_deprecation(tmp_path: Path) -> None:
    """Referenz: doc/issues.md Abschnitt 4 → Konfig-Konsistenz

    Updated to test that a legacy fee key is not used and modern parameters work correctly.
    """

    cfg_text = textwrap.dedent(
        """
        bank:
          base_account_fee: 2.0
          positive_balance_fee_rate: 0.0
          negative_balance_fee_rate: 0.0
          risk_pool_rate: 0.0
          initial_liquidity: 1000
        """
    ).strip()

    path = tmp_path / "modern_fee_config.yaml"
    path.write_text(cfg_text, encoding="utf-8")

    # Modern config should load without warnings
    cfg = load_config(path)

    # Verify modern parameters are used
    assert cfg.bank.base_account_fee == pytest.approx(2.0)
    assert cfg.bank.positive_balance_fee_rate == 0.0
    assert cfg.bank.negative_balance_fee_rate == 0.0
    assert cfg.bank.risk_pool_rate == 0.0

    bank = WarengeldBank("bank_cfg", cfg)
    account = AccountStub("acct", sight_balance=10.0)

    charged = bank.charge_account_fees([account])
    assert charged == pytest.approx(cfg.bank.base_account_fee)
    assert account.sight_balance == pytest.approx(10.0 - charged)
