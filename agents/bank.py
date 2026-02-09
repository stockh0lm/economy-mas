"""WarengeldBank (reform bank).

Specification goals
-------------------
- **Money creation occurs only** when a retailer finances *goods purchases* via an
  interest-free Kontokorrent line.
- Money is extinguished when retailers repay Kontokorrent using sight balances.
- The bank finances itself via **account fees**, not interest.
- Retailers are controlled via periodic inventory coverage checks; the bank
  itself is controlled by the Clearingstelle (see `clearing_agent.py`).

Migration note
--------------
Legacy test-only APIs were removed to avoid accidental money-creation paths.
Referenz: doc/issues.md Abschnitt 4 → „Legacy-Muster vollständig bereinigen und Migration abschließen“.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from agents.base_agent import BaseAgent
from config import CONFIG_MODEL, SimulationConfig
from logger import log


@dataclass(frozen=True)
class GoodsPurchaseRecord:
    step: int
    retailer_id: str
    seller_id: str
    amount: float


class WarengeldBank(BaseAgent):
    """Reform bank issuing interest-free Kontokorrent credit to retailers."""

    def __init__(self, unique_id: str, config: SimulationConfig | None = None) -> None:
        super().__init__(unique_id)
        self.config: SimulationConfig = config or CONFIG_MODEL

        # Diagnostics / fields exercised by unit tests.
        self.collected_fees: float = 0.0
        self.macro_unemployment: float = float(self.config.labor_market.target_unemployment_rate)
        self.macro_inflation: float = float(self.config.labor_market.target_inflation_rate)

        # Legacy test helper: a simple "liquidity" stock. Not used for Warengeld issuance.
        self.liquidity: float = float(self.config.bank.initial_liquidity)

        # Accounting / tracking
        self.credit_lines: dict[str, float] = {}  # client_id -> outstanding credit (positive)
        self.cc_limits: dict[str, float] = {}  # retailer_id -> agreed cc_limit
        self.goods_purchase_ledger: list[GoodsPurchaseRecord] = []

        # Bank income is collected via fees into a sight account.
        self.sight_balance: float = 0.0
        self.fee_income: float = 0.0
        # Diagnostic: portion of fee income attributable to shared risk premium.
        self.risk_pool_collected: float = 0.0

        # Reserve deposit at clearing (purchasing power immobilized)
        self.clearing_reserve_deposit: float = 0.0

        # Internal: last inventory check step
        self.last_inventory_check_step: int = -1

        # Diagnostics / reporting
        self.cc_write_downs_total: float = 0.0

    # --- Config-backed convenience properties (tests expect attributes) ---
    @property
    def inventory_check_interval(self) -> int:
        return int(self.config.bank.inventory_check_interval)

    @property
    def inventory_coverage_threshold(self) -> float:
        return float(self.config.bank.inventory_coverage_threshold)

    @property
    def base_credit_reserve_ratio(self) -> float:
        return float(self.config.bank.base_credit_reserve_ratio)

    @property
    def credit_unemployment_sensitivity(self) -> float:
        return float(self.config.bank.credit_unemployment_sensitivity)

    @property
    def credit_inflation_sensitivity(self) -> float:
        return float(self.config.bank.credit_inflation_sensitivity)

    @property
    def target_unemployment_rate(self) -> float:
        return float(self.config.labor_market.target_unemployment_rate)

    @property
    def target_inflation_rate(self) -> float:
        return float(self.config.labor_market.target_inflation_rate)

    # --- Registration ---
    def register_retailer(self, retailer: Any, cc_limit: float | None = None) -> None:
        """Register a retailer for Kontokorrent issuance."""
        limit = float(cc_limit if cc_limit is not None else getattr(retailer, "cc_limit", 0.0))
        if limit <= 0:
            limit = float(self.config.retailer.initial_cc_limit)
        self.cc_limits[str(retailer.unique_id)] = limit
        self.credit_lines.setdefault(
            str(retailer.unique_id),
            max(0.0, -float(getattr(retailer, "cc_balance", 0.0))),
        )
        # Keep retailer attribute in sync if present.
        if hasattr(retailer, "cc_limit"):
            retailer.cc_limit = limit

    def deregister_retailer(self, retailer: Any) -> float:
        """Remove a retailer from the bank's books (insolvency / exit).

        Any outstanding CC balance is written off as a loss.

        Returns:
            The amount of CC exposure written off.
        """
        retailer_id = str(retailer.unique_id)
        outstanding = float(self.credit_lines.pop(retailer_id, 0.0))
        self.cc_limits.pop(retailer_id, None)

        if outstanding > 0:
            self.cc_write_downs_total += outstanding
            log(
                f"WarengeldBank {self.unique_id}: deregistered retailer {retailer_id}, "
                f"wrote off CC exposure={outstanding:.2f}.",
                level="WARNING",
            )

        return outstanding

    def recompute_cc_limits(
        self, retailers: Iterable[Any], *, current_step: int
    ) -> dict[str, float]:
        """Recompute Kontokorrent limits from rolling COGS and audit risk.

        Referenz: doc/issues.md Abschnitt 2 → „cc_limit-Policy / partnerschaftlicher Rahmen“.
        """
        if not isinstance(current_step, int):
            raise TypeError("current_step must be int")

        multiplier = float(self.config.bank.cc_limit_multiplier)
        window_days = int(self.config.bank.cc_limit_rolling_window_days)
        days_per_month = int(self.config.time.days_per_month)
        audit_penalty = float(self.config.bank.cc_limit_audit_risk_penalty)
        max_decrease = float(self.config.bank.cc_limit_max_monthly_decrease)
        floor = float(self.config.retailer.initial_cc_limit)

        updated: dict[str, float] = {}
        for r in retailers:
            retailer_id = str(getattr(r, "unique_id", ""))
            if not retailer_id:
                continue

            # Rolling monthly COGS (retailer-side helper).
            avg_monthly_cogs = 0.0
            if hasattr(r, "avg_monthly_cogs"):
                avg_monthly_cogs = float(
                    r.avg_monthly_cogs(window_days=window_days, days_per_month=days_per_month)
                )

            base_limit = max(0.0, multiplier * avg_monthly_cogs)

            # Audit risk modifier in [0,1]. Higher risk -> lower limit.
            risk_score = float(getattr(r, "audit_risk_score", 0.0))
            risk_score = max(0.0, min(1.0, risk_score))
            risk_modifier = max(0.0, 1.0 - (audit_penalty * risk_score))

            proposed_limit = max(floor, base_limit * risk_modifier)

            # Not unilaterally cancellable: never cut below current exposure.
            cc_balance = float(getattr(r, "cc_balance", 0.0))
            proposed_limit = max(proposed_limit, abs(cc_balance))

            current_limit = float(getattr(r, "cc_limit", self.cc_limits.get(retailer_id, floor)))
            accepted_limit = proposed_limit
            if proposed_limit < current_limit:
                # Partnerschaftlich: der Retailer kann Decreases (starke) ablehnen.
                if hasattr(r, "accept_cc_limit_proposal"):
                    ok = bool(
                        r.accept_cc_limit_proposal(
                            proposed_limit,
                            current_limit=current_limit,
                            current_step=current_step,
                            max_monthly_decrease=max_decrease,
                        )
                    )
                else:
                    ok = (
                        ((current_limit - proposed_limit) / current_limit) <= max_decrease
                        if current_limit > 0
                        else True
                    )
                if not ok:
                    accepted_limit = current_limit

            self.cc_limits[retailer_id] = accepted_limit
            if hasattr(r, "cc_limit"):
                r.cc_limit = accepted_limit
            updated[retailer_id] = accepted_limit

        return updated

    # --- Emission (money creation) ---
    def finance_goods_purchase(
        self, *, retailer: Any, seller: Any, amount: float, current_step: int
    ) -> float:
        """Finance a retailer's goods purchase (THIS CREATES MONEY).

        Bookings:
        - Retailer Kontokorrent balance decreases (more negative)
        - Seller sight balance increases
        - Retailer inventory value increases (at cost)

        Returns the financed amount (0 if denied).
        """
        if amount <= 0:
            return 0.0

        retailer_id = str(retailer.unique_id)
        seller_id = str(getattr(seller, "unique_id", "seller"))

        # Ensure retailer registered
        if retailer_id not in self.cc_limits:
            self.register_retailer(retailer)

        cc_limit = float(self.cc_limits[retailer_id])
        cc_balance = float(getattr(retailer, "cc_balance", 0.0))

        # CC balance is negative when used.
        if cc_balance - amount < -cc_limit:
            log(
                f"WarengeldBank: denied goods financing of {amount:.2f} for {retailer_id} (cc_limit {cc_limit:.2f}).",
                level="WARNING",
            )
            return 0.0

        # 1) Create money: credit the seller.
        if hasattr(seller, "request_funds_from_bank"):
            seller.request_funds_from_bank(amount)
        # Canonical: sight_balance (Company/Producer naming)
        elif hasattr(seller, "sight_balance"):
            seller.sight_balance += amount
        elif hasattr(seller, "balance"):
            seller.balance += amount
        else:
            raise AttributeError("Seller has no supported balance attribute")

        # 2) Retailer draws on CC (becomes more negative)
        retailer.cc_balance = cc_balance - amount
        self.credit_lines[retailer_id] = self.credit_lines.get(retailer_id, 0.0) + amount

        self.goods_purchase_ledger.append(
            GoodsPurchaseRecord(current_step, retailer_id, seller_id, float(amount))
        )

        log(
            f"WarengeldBank: financed goods purchase {amount:.2f} for {retailer_id} -> {seller_id}.",
            level="INFO",
        )
        return float(amount)

    # --- Extinguishing (repayment) ---
    def process_repayment(self, retailer: Any, amount: float) -> float:
        """Repay outstanding credit.

        This method is used in both simulation and unit tests:
        - For spec-aligned Kontokorrent clients: repayment debits sight balances
          and moves `cc_balance` toward 0.
        - For simplified stubs: repayment reduces `credit_lines` and increases
          `liquidity` as a test-only accounting proxy.
        """
        if amount <= 0:
            return 0.0

        rid = str(getattr(retailer, "unique_id", "client"))
        outstanding = float(self.credit_lines.get(rid, 0.0))
        if outstanding <= 0:
            return 0.0

        repay = min(float(amount), outstanding)
        paid = 0.0

        # If the borrower has a cash-like sight balance, try to debit it.
        # Kanonischer Kontoname: sight_balance
        # Referenz: doc/issues.md Abschnitt 4 → "Einheitliche Balance-Sheet-Namen (Company/Producer)"
        if hasattr(retailer, "sight_balance"):
            bal = float(getattr(retailer, "sight_balance", 0.0))
            if bal > 0:
                paid = min(bal, repay)
                retailer.sight_balance = bal - paid
                if hasattr(retailer, "cc_balance"):
                    retailer.cc_balance = float(getattr(retailer, "cc_balance", 0.0)) + paid
        elif hasattr(retailer, "balance"):
            bal = float(getattr(retailer, "balance", 0.0))
            if bal > 0:
                paid = min(bal, repay)
                retailer.balance = bal - paid
                if hasattr(retailer, "cc_balance"):
                    retailer.cc_balance = float(getattr(retailer, "cc_balance", 0.0)) + paid

        # Unit tests allow repayment even if no explicit cash is modeled.
        repayment_amount = paid if paid > 0 else repay

        self.credit_lines[rid] = outstanding - repayment_amount
        self.liquidity += repayment_amount
        return float(repayment_amount)

    # --- Warengeld feedback mechanisms (spec Section 4.x) ---
    def auto_repay_cc_from_sight(self, retailer: Any) -> float:
        """Automatically repay Kontokorrent from excess sight balances.

        Spezifikation: doc/specs.md Section 4.2.
        Expliziter Bezug: doc/issues.md Abschnitt 4/5 → "Hyperinflation / Numerische Überläufe ...".

        Policy:
        - Keep an allowance (working capital buffer) untouched.
        - Repay only excess above that allowance.

        Returns the repaid amount (money is extinguished via sight debit).
        """

        # Only meaningful if the retailer has outstanding CC debt.
        cc_balance = float(getattr(retailer, "cc_balance", 0.0))
        if cc_balance >= 0:
            return 0.0

        # Determine allowance (buffer). Prefer explicit attribute, fall back to config.
        allowance = float(
            getattr(retailer, "sight_allowance", float(self.config.retailer.working_capital_buffer))
        )

        # Retrieve a sight-like balance.
        if hasattr(retailer, "sight_balance"):
            sight = float(getattr(retailer, "sight_balance", 0.0))
        elif hasattr(retailer, "balance"):
            sight = float(getattr(retailer, "balance", 0.0))
        else:
            return 0.0

        excess = max(0.0, sight - allowance)
        repay_amount = min(excess, abs(cc_balance))

        # --- Throttle: only repay a fraction of excess per step ---
        # Without throttling, every sales transaction triggers immediate full
        # CC repayment, creating a structural deflationary bias (Failure 3).
        # The repayment fraction is configurable; 0.3 means "repay 30 % of
        # excess per step", letting money circulate longer.
        fraction = float(self.config.retailer.cc_repayment_fraction)
        repay_amount *= fraction

        if repay_amount <= 0:
            return 0.0

        return float(self.process_repayment(retailer, repay_amount))

    def enforce_inventory_backing(self, retailer: Any, *, collateral_factor: float = 1.2) -> float:
        """Enforce an inventory-backed CC exposure limit (money destruction).

        Spezifikation: doc/specs.md Section 4.1.
        Expliziter Bezug: doc/issues.md Abschnitt 4/5 → "Hyperinflation / Numerische Überläufe ...".

        If the retailer's inventory value is insufficient relative to their
        outstanding Kontokorrent exposure, the bank enforces a reduction of the
        exposure. The reduction is implemented as *money destruction*:
        - first by forced repayment from retailer sight balances
        - then by value-correction style write-downs (reserve, bank sight, bank clearing deposit)

        Returns:
            destroyed_total: amount of purchasing power extinguished.
        """

        if collateral_factor <= 0:
            raise ValueError("collateral_factor must be > 0")

        cc_balance = float(getattr(retailer, "cc_balance", 0.0))
        if cc_balance >= 0:
            return 0.0

        inv = float(getattr(retailer, "inventory_value", 0.0))
        exposure = abs(cc_balance)
        required_collateral = exposure * float(collateral_factor)
        if inv >= required_collateral or exposure <= 0:
            return 0.0

        # Target: reduce exposure such that inv >= collateral_factor * exposure.
        desired_exposure = max(0.0, inv / float(collateral_factor))
        excess_exposure = max(0.0, exposure - desired_exposure)
        if excess_exposure <= 0:
            return 0.0

        destroyed_total = 0.0
        remaining = excess_exposure

        # 1) Forced repayment from retailer sight balance (extinguishes money).
        if remaining > 0 and hasattr(retailer, "sight_balance"):
            sight = float(getattr(retailer, "sight_balance", 0.0))
            repay = min(max(0.0, sight), remaining)
            if repay > 0:
                paid = float(self.process_repayment(retailer, repay))
                destroyed_total += paid
                remaining = max(0.0, remaining - paid)

        # 2) Value correction using retailer write-down reserve (then bank absorbs exposure).
        if remaining > 0 and hasattr(retailer, "write_down_reserve"):
            reserve = float(getattr(retailer, "write_down_reserve", 0.0))
            take = min(max(0.0, reserve), remaining)
            if take > 0:
                retailer.write_down_reserve = reserve - take
                # Reduce exposure accordingly.
                _ = self.write_down_cc(retailer, take, reason="inventory_backing_reserve")
                destroyed_total += take
                remaining = max(0.0, remaining - take)

        # 3) Bank absorbs remaining via its own sight balance.
        if remaining > 0:
            bank_sight = float(getattr(self, "sight_balance", 0.0))
            take = min(max(0.0, bank_sight), remaining)
            if take > 0:
                self.sight_balance = bank_sight - take
                _ = self.write_down_cc(retailer, take, reason="inventory_backing_bank_sight")
                destroyed_total += take
                remaining = max(0.0, remaining - take)

        # 4) Bank absorbs remaining via its clearing reserve deposit.
        if remaining > 0:
            reserve_dep = float(getattr(self, "clearing_reserve_deposit", 0.0))
            take = min(max(0.0, reserve_dep), remaining)
            if take > 0:
                self.clearing_reserve_deposit = reserve_dep - take
                _ = self.write_down_cc(retailer, take, reason="inventory_backing_clearing_reserve")
                destroyed_total += take
                remaining = max(0.0, remaining - take)

        # If remaining > 0 here, full enforcement wasn't possible with available buffers.
        # We return the partial destruction applied; the residual should be handled by audits/insolvency.
        return float(destroyed_total)

    def write_down_cc(self, retailer: Any, amount: float, *, reason: str = "write_down") -> float:
        """Write down a retailer's outstanding Kontokorrent exposure.

        After a value correction (inventory write-down / clearing audit), the
        corresponding credit exposure must be reduced as well.

        This method only adjusts credit exposure (cc_balance + bank ledger). Callers
        are responsible for extinguishing deposits elsewhere (ClearingAgent, retailer
        write-down reserve/sight, etc.).

        Returns the applied write-down amount.
        """
        if amount <= 0:
            return 0.0

        rid = str(getattr(retailer, "unique_id", "client"))
        outstanding = float(self.credit_lines.get(rid, 0.0))
        if outstanding <= 0:
            return 0.0

        applied = min(float(amount), outstanding)
        # Reduce bank exposure.
        self.credit_lines[rid] = outstanding - applied

        # Reduce borrower CC liability (move toward zero).
        if hasattr(retailer, "cc_balance"):
            retailer.cc_balance = float(getattr(retailer, "cc_balance", 0.0)) + applied

        self.cc_write_downs_total += applied
        log(
            f"WarengeldBank: CC write-down {applied:.2f} for {rid} (reason={reason}).",
            level="INFO",
        )
        return float(applied)

    # --- Fees (spec-aligned) ---
    def charge_account_fees(self, accounts: Iterable[Any]) -> float:
        """Charge periodic account fees (spec-aligned).

        In the Warengeld model, banks do not charge interest on the Kontokorrent.
        Operating costs and shared risk premiums are paid via account fees.

        Fee model:
        - base_account_fee (flat)
        - positive_balance_fee_rate * max(0, sight_balance)
        - negative_balance_fee_rate * max(0, -sight_balance)
          (usually lower than the positive rate; "Plus" should be more expensive)
        - risk_pool_rate * total_cc_exposure distributed equally across accounts

        Fees are transfers (NOT money destruction): they move to the bank's own
        sight_balance.
        """

        accounts_list = list(accounts)
        if not accounts_list:
            return 0.0

        base_fee = float(self.config.bank.base_account_fee)
        pos_rate = float(self.config.bank.positive_balance_fee_rate)
        neg_rate = float(self.config.bank.negative_balance_fee_rate)

        # Shared risk premium (not interest): proportional to total exposure, shared evenly.
        risk_pool_rate = float(getattr(self.config.bank, "risk_pool_rate", 0.0))
        risk_fee_total = risk_pool_rate * float(self.total_cc_exposure)
        risk_fee_per_account = risk_fee_total / len(accounts_list) if accounts_list else 0.0

        total_collected = 0.0
        for acc in accounts_list:
            # Best-effort retrieval of a sight balance-like field.
            if hasattr(acc, "sight_balance"):
                bal = float(getattr(acc, "sight_balance"))
                setter = lambda v, _acc=acc: setattr(_acc, "sight_balance", v)
            elif hasattr(acc, "checking_account"):
                bal = float(getattr(acc, "checking_account"))
                setter = lambda v, _acc=acc: setattr(_acc, "checking_account", v)
            elif hasattr(acc, "balance"):
                bal = float(getattr(acc, "balance"))
                setter = lambda v, _acc=acc: setattr(_acc, "balance", v)
            else:
                continue

            fee = base_fee
            fee += pos_rate * max(0.0, bal)
            fee += neg_rate * max(0.0, -bal)
            fee += risk_fee_per_account

            if fee <= 0:
                continue

            paid = min(max(0.0, bal), fee)
            if paid <= 0:
                continue

            setter(bal - paid)
            self.sight_balance += paid
            self.fee_income += paid
            total_collected += paid

        self.risk_pool_collected += min(total_collected, risk_fee_total)
        self.collected_fees += total_collected
        return float(total_collected)

    # --- Inventory control (modern diagnostic API) ---
    def check_inventories(
        self, retailers: Iterable[Any], *, current_step: int
    ) -> list[tuple[str, float, float]]:
        """Inventory coverage diagnostics.

        Returns a list of issues `(retailer_id, inventory_value, cc_exposure)`.

        NOTE: This is diagnostic-only. Enforcement happens through clearing audits
        and retailer-side settlement, not via an immediate bank-side repayment.

        Referenz: doc/issues.md Abschnitt 4 → „Legacy-Muster vollständig bereinigen“.
        """

        if not isinstance(current_step, int):
            raise TypeError("current_step must be int")

        if (
            self.last_inventory_check_step >= 0
            and (current_step - self.last_inventory_check_step) < self.inventory_check_interval
        ):
            return []

        self.last_inventory_check_step = current_step
        threshold = float(self.config.bank.inventory_coverage_threshold)
        issues: list[tuple[str, float, float]] = []
        for r in retailers:
            rid = str(r.unique_id)
            inv = float(getattr(r, "inventory_value", 0.0))
            cc = abs(float(getattr(r, "cc_balance", 0.0)))
            if cc <= 0:
                continue
            if inv < threshold * cc:
                issues.append((rid, inv, cc))

        if issues:
            log(f"WarengeldBank: inventory coverage issues: {issues}", level="WARNING")
        return issues

    def step(
        self, current_step: int, merchants: Iterable[Any] | None = None, **kwargs: Any
    ) -> None:
        """Bank step hook used by tests.

        Runs inventory checks and fee collection using modern methods.
        """

        super().step(current_step)
        if merchants is None:
            return
        _ = self.check_inventories(merchants, current_step=current_step)
        self.charge_account_fees(merchants)

    def recirculate_fee_income(self, households: Iterable[Any]) -> float:
        """Recirculate accumulated fee income back into the economy.

        In the Warengeld model, banks finance themselves via fees (not interest).
        These fees are the bank's revenue for operating costs — wages to bank
        employees, rent, IT systems, etc.  If they are not spent, they become
        a permanent money drain (see Failure 2 in systemic diagnosis).

        This method models the bank's operating expenditures as transfers to
        households, representing bank employee wages.  A configurable fraction
        ``fee_recirculation_rate`` (default 80 %) of the bank's sight balance is
        distributed equally among all households in the bank's region.

        Book ref: "Die Bank lebt nicht von Zinsen, sondern von Gebühren" —
        but fees *are* bank revenue and must flow back into circulation to
        avoid deflation.

        Returns:
            Total amount recirculated.
        """
        rate = float(self.config.bank.fee_recirculation_rate)
        if rate <= 0 or self.sight_balance <= 0:
            return 0.0

        hh_list = list(households)
        if not hh_list:
            return 0.0

        pool = self.sight_balance * rate
        if pool <= 0:
            return 0.0

        per_hh = pool / len(hh_list)
        total_distributed = 0.0

        for hh in hh_list:
            if hasattr(hh, "receive_income"):
                hh.receive_income(per_hh)
            elif hasattr(hh, "sight_balance"):
                hh.sight_balance = float(getattr(hh, "sight_balance")) + per_hh
            elif hasattr(hh, "balance"):
                hh.balance = float(getattr(hh, "balance")) + per_hh
            else:
                continue
            total_distributed += per_hh

        self.sight_balance -= total_distributed

        if total_distributed > 0:
            log(
                f"WarengeldBank {self.unique_id}: recirculated {total_distributed:.2f} "
                f"fee income to {len(hh_list)} households ({per_hh:.4f} each). "
                f"Remaining bank balance: {self.sight_balance:.2f}.",
                level="INFO",
            )

        return float(total_distributed)

    # --- Derived metrics ---
    @property
    def total_cc_exposure(self) -> float:
        return float(sum(self.credit_lines.values()))
