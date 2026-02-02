from __future__ import annotations

from dataclasses import dataclass

from agents.bank import WarengeldBank
from agents.company_agent import Company
from agents.retailer_agent import RetailerAgent
from config import SimulationConfig
from metrics import MetricsCollector


@dataclass
class _Worker:
    unique_id: str
    wage: float
    sight_balance: float = 0.0

    def receive_income(self, amount: float) -> None:
        self.sight_balance += float(amount)


def test_company_balance_sheet_naming() -> None:
    """Referenz: doc/issues.md Abschnitt 4 → Einheitliche Balance-Sheet-Namen (Company/Producer)."""

    cfg = SimulationConfig()

    company = Company("c1", config=cfg)
    company.sight_balance = 10.0

    # Alias bleibt synchron.
    assert company.balance == 10.0
    company.balance = 7.0
    assert company.sight_balance == 7.0

    # Wages buchen explizit über sight_balance.
    worker = _Worker("w1", wage=2.0)
    company.employees = [worker]
    paid = company.pay_wages(wage_rate=2.0)
    assert paid == 2.0
    assert company.sight_balance == 5.0
    assert worker.sight_balance == 2.0


def test_no_legacy_balance_names() -> None:
    """Referenz: doc/issues.md Abschnitt 4 → Einheitliche Balance-Sheet-Namen (Company/Producer)."""

    cfg = SimulationConfig()
    bank = WarengeldBank("bank", config=cfg)
    retailer = RetailerAgent("r1", config=cfg, cc_limit=1000.0, initial_sight_balance=0.0)

    # --- finance_goods_purchase: muss sight_balance bevorzugen (nicht 'balance') ---
    class _Seller:
        def __init__(self):
            self.unique_id = "seller"
            self.sight_balance = 0.0
            # legacy-Feld bewusst entkoppelt, um die Präferenz zu testen
            self.balance = 0.0

    seller = _Seller()
    bank.finance_goods_purchase(retailer=retailer, seller=seller, amount=10.0, current_step=0)
    assert seller.sight_balance == 10.0
    assert seller.balance == 0.0

    # --- process_repayment: muss sight_balance bevorzugen ---
    class _Borrower:
        def __init__(self):
            self.unique_id = "borrower"
            self.sight_balance = 5.0
            self.balance = 5.0  # bewusst separat
            self.cc_balance = -5.0

    borrower = _Borrower()
    bank.credit_lines[borrower.unique_id] = 5.0
    repaid = bank.process_repayment(borrower, amount=5.0)
    assert repaid == 5.0
    assert borrower.sight_balance == 0.0
    assert borrower.balance == 5.0
    assert borrower.cc_balance == 0.0

    # --- Metrics: Company-Metrikexport soll 'sight_balance' enthalten (kein 'balance') ---
    collector = MetricsCollector(config=cfg)
    c = Company("c2", config=cfg)
    c.sight_balance = 12.34
    collector.collect_company_metrics([c], step=1)
    exported = collector.company_metrics[c.unique_id][1]
    assert "sight_balance" in exported
    assert "balance" not in exported