import pytest

from agents.bank import WarengeldBank
from agents.retailer_agent import RetailerAgent
from config import CONFIG_MODEL


def test_cc_limit_policy() -> None:
    """Referenz: doc/issues.md Abschnitt 2 → cc_limit-Policy / partnerschaftlicher Rahmen"""

    cfg = CONFIG_MODEL.model_copy(deep=True)
    cfg.bank.cc_limit_multiplier = 2.0
    cfg.bank.cc_limit_rolling_window_days = 30
    cfg.bank.cc_limit_audit_risk_penalty = 0.5
    cfg.bank.cc_limit_max_monthly_decrease = 0.25

    # Floor / initial contract
    cfg.retailer.initial_cc_limit = 100.0
    cfg.time.days_per_month = 30

    bank = WarengeldBank("bank_test", cfg)
    retailer = RetailerAgent("retailer_0", cfg, cc_limit=cfg.retailer.initial_cc_limit)
    bank.register_retailer(retailer)

    # Arrange: 30 Tage COGS-Historie (10 pro Tag)
    for _ in range(30):
        retailer.cogs_total = 10.0
        retailer.push_cogs_history(window_days=cfg.bank.cc_limit_rolling_window_days)

    # Act 1: Base policy (no audit risk)
    bank.recompute_cc_limits([retailer], current_step=30)

    # avg_monthly_cogs = 10 * 30 = 300; cc_limit = m * avg_monthly_cogs = 2 * 300 = 600
    assert retailer.cc_limit == pytest.approx(600.0)

    # Act 2: small audit risk -> small decrease accepted (partnerschaftlich anpassbar)
    retailer.audit_risk_score = 0.2  # modifier = 1 - 0.5*0.2 = 0.9
    bank.recompute_cc_limits([retailer], current_step=60)
    assert retailer.cc_limit == pytest.approx(540.0)

    # Act 3: large audit risk -> large decrease rejected (nicht einseitig kündbar)
    retailer.audit_risk_score = 1.0  # modifier = 0.5 => proposed 300
    bank.recompute_cc_limits([retailer], current_step=90)
    assert retailer.cc_limit == pytest.approx(540.0)
