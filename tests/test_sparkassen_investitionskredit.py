import logging

import pytest

from agents.company_agent import Company
from agents.savings_bank_agent import SavingsBank
from config import load_simulation_config


def test_sparkassen_investitionskredit(caplog: pytest.LogCaptureFixture) -> None:
    """Referenz: doc/issues.md Abschnitt 6 → M2, Abschnitt 5 → „Firmen sollen bei der Sparkasse Geld leihen…“, Abschnitt 3 → Test „Sparkassen‑Kredit -> Investition -> Produktivität"."""

    cfg = load_simulation_config(
        {
            "company": {
                # Deterministische Policy: Company ist "unterinvestiert" wenn Sight < investment_threshold.
                "investment_threshold": 200.0,
                # Deterministische Investitionsabbildung: 1 Capacity kostet 10.
                "investment_capital_cost_per_capacity": 10.0,
                # Risk/Eligibility: max. Principal = production_capacity * ratio.
                "sparkasse_investment_loan_max_to_capacity": 10.0,
                # Repayment exists, but is not used in this minimal test.
                "sparkasse_investment_loan_repayment_rate": 0.25,
            },
            "savings_bank": {"initial_liquidity": 1_000.0},
        }
    )

    sb = SavingsBank(unique_id="savings_bank_test", config=cfg)
    company = Company(unique_id="company_0", production_capacity=100.0, config=cfg)
    company.sight_balance = 0.0

    pool_before = sb.available_funds
    cap_before = company.production_capacity

    caplog.set_level(logging.INFO)

    granted = company.request_sparkasse_investment_loan(sb)

    assert granted > 0.0

    # Capacity/Productivity must increase deterministically due to the investment mapping.
    assert company.production_capacity > cap_before

    # Loan ledger must reflect outstanding principal.
    assert sb.active_loans.get(company.unique_id, 0.0) == pytest.approx(granted)

    # Savings pool / available funds must reduce by principal (no money creation).
    assert sb.available_funds == pytest.approx(pool_before - granted)

    # Standardized event/log pattern must exist and be testable.
    assert "event=sparkasse_investment_loan_granted" in caplog.text
