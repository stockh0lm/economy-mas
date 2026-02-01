import inspect
import warnings

import pytest

from agents.bank import WarengeldBank
from config import load_simulation_config
from main import run_simulation


def test_legacy_bank_methods_removed() -> None:
    """Referenz: doc/issues.md Abschnitt 4 → „Legacy-Muster vollständig bereinigen und Migration abschließen"""

    bank = WarengeldBank("bank")

    # Die alten Abkürzungen existieren nicht mehr.
    assert not hasattr(bank, "grant_credit")
    assert not hasattr(bank, "calculate_fees")

    # check_inventories ist nur noch die moderne, diagnostische API.
    sig = inspect.signature(bank.check_inventories)
    assert "current_step" in sig.parameters
    assert sig.parameters["current_step"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        # type: ignore[arg-type] - absichtlich
        step = None
        bank.check_inventories([], current_step=step)


def test_standard_simulation_emits_no_deprecation_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Referenz: doc/issues.md Abschnitt 4 → keine Legacy-Pfade im Standard-Run."""

    monkeypatch.setenv("SIM_SEED", "0")
    cfg = load_simulation_config(
        {
            "simulation_steps": 3,
            "population": {"num_households": 4, "num_companies": 1, "num_retailers": 1},
        }
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        run_simulation(cfg)
