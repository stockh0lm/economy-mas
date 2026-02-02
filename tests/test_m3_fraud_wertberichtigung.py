from config import SimulationConfig

from agents.bank import GoodsPurchaseRecord, WarengeldBank
from agents.clearing_agent import ClearingAgent
from agents.company_agent import Company
from agents.retailer_agent import RetailerAgent


def test_fraud_wertberichtigung():
    """Referenz: doc/issues.md Abschnitt 2 → Fraud/Wertberichtigung-Rechenregel"""

    cfg = SimulationConfig()

    clearing = ClearingAgent(unique_id="clearing_0", config=cfg)
    bank = WarengeldBank(unique_id="warengeld_bank_region_0", config=cfg)
    r = RetailerAgent(unique_id="retailer_0", config=cfg)

    c0 = Company(unique_id="company_0", production_capacity=10.0, config=cfg, labor_market=None)
    c1 = Company(unique_id="company_1", production_capacity=10.0, config=cfg, labor_market=None)

    # Ledger: company_0 received 70, company_1 received 30 from retailer_0
    bank.goods_purchase_ledger = [
        GoodsPurchaseRecord(step=0, retailer_id=r.unique_id, seller_id=c0.unique_id, amount=70.0),
        GoodsPurchaseRecord(step=0, retailer_id=r.unique_id, seller_id=c1.unique_id, amount=30.0),
    ]

    # Correction amount (e.g., fraud / uncovered inventory): 50
    # Order per issues.md: Reserve → Retailer-Sicht → Empfänger-Haircut (pro-rata) → Bankreserve
    r.write_down_reserve = 10.0
    r.sight_balance = 20.0

    c0.sight_balance = 100.0
    c1.sight_balance = 5.0  # forces redistribution

    # Ensure bank reserve at clearing isn't used
    clearing.bank_reserves[bank.unique_id] = 0.0

    corrected = clearing._apply_value_correction(
        bank=bank,
        retailer=r,
        amount=50.0,
        companies_by_id={c0.unique_id: c0, c1.unique_id: c1},
        current_step=1,
    )

    assert corrected == 50.0
    assert r.write_down_reserve == 0.0
    assert r.sight_balance == 0.0
    # Remaining 20 should be allocated pro-rata (70/30), with c1 capped at 5:
    # c1 pays 5, c0 pays 15.
    assert c0.sight_balance == 85.0
    assert c1.sight_balance == 0.0
