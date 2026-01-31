"""Clearingstelle / ClearingAgent.

This component provides system-level controls described in the specification:
- bank reserve deposits (Mindestreserve / Risikorücklage) with bounds
- periodic audits of banks and their retailer clients
- value corrections / write-down triggered money extinguishing (Geldvernichtung)
- sight-balance decay for excess deposits (Sichtfaktor)

The implementation is deliberately lightweight: it does not try to emulate full
regulatory or legal procedures. The goal is to keep the simulation's *monetary
invariants* aligned: money creation occurs only at retailer goods purchases; money is extinguished via Kontokorrent repayment and explicit value corrections / sight decay.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from config import CONFIG_MODEL, SimulationConfig
from logger import log

from .base_agent import BaseAgent


@dataclass
class AuditFinding:
    bank_id: str
    retailer_id: str
    inventory_value: float
    cc_outstanding: float
    gap: float


class ClearingAgent(BaseAgent):
    def __init__(self, unique_id: str, config: SimulationConfig | None = None) -> None:
        super().__init__(unique_id)
        self.config: SimulationConfig = config or CONFIG_MODEL

        # Reserves held at clearing (bank_id -> amount)
        self.bank_reserves: dict[str, float] = {}
        self.required_reserve_ratio: dict[str, float] = {}
        self.last_audit_step: int = -1

        # Accounting of destroyed money (for diagnostics)
        self.extinguished_total: float = 0.0

        # Legacy/test accounting: tracked separately from extinguishing.
        self.excess_wealth_collected: float = 0.0

    # --- Reserve management ---
    def register_bank(self, bank: Any) -> None:
        bank_id = str(getattr(bank, "unique_id", "bank"))
        self.bank_reserves.setdefault(bank_id, float(getattr(bank, "clearing_reserve_deposit", 0.0)))
        self.required_reserve_ratio.setdefault(bank_id, float(self.config.clearing.required_reserve_ratio))

    def _sync_bank_reserve_attr(self, bank: Any) -> None:
        bank_id = str(getattr(bank, "unique_id", "bank"))
        bank.clearing_reserve_deposit = float(self.bank_reserves.get(bank_id, 0.0))

    def enforce_reserve_bounds(self, bank: Any) -> None:
        """Keep bank reserves within configured bounds relative to CC exposure."""
        bank_id = str(getattr(bank, "unique_id", "bank"))
        self.register_bank(bank)

        exposure = float(getattr(bank, "total_cc_exposure", 0.0))
        if exposure <= 0:
            return

        min_ratio = float(self.config.clearing.reserve_bounds_min)
        max_ratio = float(self.config.clearing.reserve_bounds_max)

        current = float(self.bank_reserves.get(bank_id, 0.0))
        min_reserve = exposure * min_ratio
        max_reserve = exposure * max_ratio

        # If too low, try to move funds from bank sight balance to reserves.
        if current < min_reserve:
            needed = min_reserve - current
            available = float(getattr(bank, "sight_balance", 0.0))
            moved = min(needed, max(0.0, available))
            if moved > 0:
                bank.sight_balance = available - moved
                self.bank_reserves[bank_id] = current + moved
                log(
                    f"Clearing: moved {moved:.2f} from bank {bank_id} sight to reserves (needed {needed:.2f}).",
                    level="INFO",
                )

        # If too high, release back to bank sight balance (avoid excessive purchasing-power immobilisation).
        current = float(self.bank_reserves.get(bank_id, 0.0))
        if current > max_reserve:
            release = current - max_reserve
            self.bank_reserves[bank_id] = current - release
            bank.sight_balance = float(getattr(bank, "sight_balance", 0.0)) + release
            log(
                f"Clearing: released {release:.2f} from reserves back to bank {bank_id} sight.",
                level="INFO",
            )

        self._sync_bank_reserve_attr(bank)

    # --- Audits ---
    def audit_bank(
        self,
        *,
        bank: Any,
        retailers: Iterable[Any],
        companies_by_id: dict[str, Any] | None = None,
        current_step: int,
    ) -> list[AuditFinding]:
        """Perform periodic audit.

        Returns list of findings (inventory under-coverage).
        """
        audit_interval = int(self.config.clearing.audit_interval)
        if audit_interval > 0 and current_step - self.last_audit_step < audit_interval:
            return []

        self.last_audit_step = current_step
        self.register_bank(bank)

        threshold = float(self.config.bank.inventory_coverage_threshold)
        findings: list[AuditFinding] = []

        for r in retailers:
            rid = str(getattr(r, "unique_id", "retailer"))
            inv = float(getattr(r, "inventory_value", 0.0))
            cc = abs(float(getattr(r, "cc_balance", 0.0)))
            if cc <= 0:
                continue
            if inv < threshold * cc:
                gap = max(0.0, cc - inv)
                findings.append(AuditFinding(str(getattr(bank, "unique_id", "bank")), rid, inv, cc, gap))

                if gap > 0:
                    self._apply_value_correction(
                        bank=bank,
                        retailer=r,
                        amount=gap,
                        companies_by_id=companies_by_id or {},
                    )

        # If repeated problems: increase required reserve ratio as competition sanction.
        if findings:
            step_up = float(self.config.clearing.reserve_ratio_step)
            self.required_reserve_ratio[str(getattr(bank, "unique_id", "bank"))] += step_up
            log(
                f"Clearing: audit found {len(findings)} issues for bank {getattr(bank,'unique_id','bank')}; "
                f"increasing required reserve ratio by {step_up:.4f}.",
                level="WARNING",
            )

        # Enforce reserve bounds after audit adjustments.
        self.enforce_reserve_bounds(bank)
        return findings

    # --- Money destruction primitives ---
    def _extinguish_from_sight(self, agent: Any, amount: float) -> float:
        if amount <= 0:
            return 0.0
        # prefer sight_balance property, fallback balance
        if hasattr(agent, "sight_balance"):
            bal = float(agent.sight_balance)
            take = min(bal, amount)
            agent.sight_balance = bal - take
            self.extinguished_total += take
            return take
        if hasattr(agent, "balance"):
            bal = float(agent.balance)
            take = min(bal, amount)
            agent.balance = bal - take
            self.extinguished_total += take
            return take
        return 0.0

    def _apply_value_correction(
        self,
        *,
        bank: Any,
        retailer: Any,
        amount: float,
        companies_by_id: dict[str, Any],
    ) -> float:
        """Destroy money to correct an uncovered CC exposure.

        Order of loss allocation (simple, simulation-friendly):
        1) Retailer write-down reserve (if available)
        2) Retailer sight balance
        3) Haircut on recent recipient companies of this retailer's financed purchases (pro-rata)
        4) Bank reserve deposit at clearing

        This is not a full legal recovery model; it is a *monetary correction*.
        """
        remaining = float(max(0.0, amount))
        if remaining <= 0:
            return 0.0

        # 1) Retailer write-down reserve
        if hasattr(retailer, "write_down_reserve"):
            reserve = float(retailer.write_down_reserve)
            take = min(reserve, remaining)
            if take > 0:
                retailer.write_down_reserve = reserve - take
                self.extinguished_total += take
                remaining -= take

        # 2) Retailer sight
        if remaining > 0:
            remaining -= self._extinguish_from_sight(retailer, remaining)

        # 3) Recipient companies (trace via bank ledger)
        if remaining > 0 and hasattr(bank, "goods_purchase_ledger"):
            rid = str(getattr(retailer, "unique_id", "retailer"))
            records = [r for r in getattr(bank, "goods_purchase_ledger", []) if r.retailer_id == rid]
            total = sum(float(r.amount) for r in records)
            if total > 0:
                # pro-rata across companies
                for rec in records:
                    if remaining <= 0:
                        break
                    company = companies_by_id.get(rec.seller_id)
                    if company is None:
                        continue
                    share = remaining * (float(rec.amount) / total)
                    remaining -= self._extinguish_from_sight(company, share)

        # 4) Bank reserves at clearing
        if remaining > 0:
            bank_id = str(getattr(bank, "unique_id", "bank"))
            current_reserve = float(self.bank_reserves.get(bank_id, 0.0))
            take = min(current_reserve, remaining)
            if take > 0:
                self.bank_reserves[bank_id] = current_reserve - take
                self.extinguished_total += take
                remaining -= take
                self._sync_bank_reserve_attr(bank)

        corrected = float(amount) - remaining
        log(
            f"Clearing: value correction triggered for retailer {getattr(retailer,'unique_id','retailer')}: "
            f"requested {amount:.2f}, extinguished {corrected:.2f}.",
            level="WARNING",
        )
        return corrected

    # --- Sight balance decay (Sichtfaktor) ---
    def apply_sight_decay(self, accounts: Iterable[Any]) -> float:
        """Apply monthly decay to excess sight balances.

        Spec intent: limit "too large" sight balances without blanket demurrage.
        - For households we estimate the allowance from rolling consumption history.
        - For other agent types, we default to a high allowance so we only affect
          extreme hoarding, keeping the core model stable.
        """
        factor = float(self.config.clearing.sight_excess_decay_rate)
        k = float(self.config.clearing.sight_allowance_multiplier)
        if factor <= 0 or k <= 0:
            return 0.0

        destroyed_total = 0.0
        hyperwealth = float(getattr(self.config.clearing, "hyperwealth_threshold", 0.0))
        for h in accounts:
            if not hasattr(h, "sight_balance"):
                continue
            spend_hist = getattr(h, "consumption_history", [])
            if spend_hist:
                avg_spend = sum(spend_hist) / len(spend_hist)
            else:
                # Fallback: for non-households this should not constantly burn
                # operational balances; only act on extreme hoarding.
                avg_spend = float(getattr(h, "income", 0.0))

            allowance = max(hyperwealth, k * avg_spend)
            excess = max(0.0, float(h.sight_balance) - allowance)
            if excess <= 0:
                continue
            decay = factor * excess
            destroyed = self._extinguish_from_sight(h, decay)
            destroyed_total += destroyed

        if destroyed_total > 0:
            log(f"Clearing: sight-decay extinguished {destroyed_total:.2f}.", level="INFO")
        return destroyed_total

    # --- Legacy compatibility (optional) ---
    def report_hyperwealth(self, agents: Iterable[Any]) -> float:
        """Collect balances above the configured hyperwealth threshold.

        Tests treat this as a simple cap: any balance above threshold is removed
        from the agent and tracked in `excess_wealth_collected`.
        """

        threshold = float(getattr(self.config.clearing, "hyperwealth_threshold", 0.0))
        if threshold <= 0:
            return 0.0

        collected = 0.0
        for agent in agents:
            if hasattr(agent, "balance"):
                bal = float(agent.balance)
                excess = max(0.0, bal - threshold)
                if excess > 0:
                    agent.balance = bal - excess
                    collected += excess

        self.excess_wealth_collected += collected
        return float(collected)
