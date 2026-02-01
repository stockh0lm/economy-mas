"""WarengeldBank (reform bank).

Specification goals:
- **Money creation occurs only** when a retailer finances *goods purchases* via
  an interest-free Kontokorrent line.
- Money is extinguished when retailers repay Kontokorrent using sight balances.
- The bank finances itself via **account fees**, not interest.
- Retailers are controlled via inventory checks; the bank itself is controlled
  by the Clearingstelle (see `clearing_agent.py`).

This module keeps the API small and explicit. In particular, there is no
"liquidity pool" that would cap credit creation; credit creation is constrained
by retailer credit limits and collateral (inventory values) and later audits.
"""

from __future__ import annotations

from dataclasses import dataclass
import warnings
from typing import Any, Iterable, Protocol

from config import CONFIG_MODEL, SimulationConfig
from logger import log

from agents.base_agent import BaseAgent


class MerchantProtocol(Protocol):
    """Structural protocol for credit clients used by tests.

    The simulation distinguishes Retailers (Kontokorrent) from Companies (no CC).
    Unit tests in this repo use a simplified "merchant" abstraction.
    """

    unique_id: str

    # legacy attributes used by some parts of the codebase
    inventory: float  # goods stock/value proxy
    balance: float  # sight balance proxy

    def request_funds_from_bank(self, amount: float) -> float: ...


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

        # --- Legacy/public API expected by unit tests ---
        self.collected_fees: float = 0.0
        self.macro_unemployment: float = float(self.config.labor_market.target_unemployment_rate)
        self.macro_inflation: float = float(self.config.labor_market.target_inflation_rate)
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
    def fee_rate(self) -> float:  # tests expect bank.fee_rate
        warnings.warn(
            "bank.fee_rate is deprecated (legacy tests only). Use WarengeldBank.charge_account_fees(...) and its config parameters instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return float(self.config.bank.fee_rate)

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
        self.credit_lines.setdefault(str(retailer.unique_id), max(0.0, -float(getattr(retailer, "cc_balance", 0.0))))
        # Keep retailer attribute in sync if present.
        if hasattr(retailer, "cc_limit"):
            retailer.cc_limit = limit

    # --- Emission (money creation) ---
    def finance_goods_purchase(self, *, retailer: Any, seller: Any, amount: float, current_step: int) -> float:
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
        elif hasattr(seller, "balance"):
            seller.balance += amount
        elif hasattr(seller, "sight_balance"):
            seller.sight_balance += amount
        else:
            raise AttributeError("Seller has no supported balance attribute")

        # 2) Retailer draws on CC (becomes more negative)
        retailer.cc_balance = cc_balance - amount
        self.credit_lines[retailer_id] = self.credit_lines.get(retailer_id, 0.0) + amount

        self.goods_purchase_ledger.append(GoodsPurchaseRecord(current_step, retailer_id, seller_id, float(amount)))

        log(
            f"WarengeldBank: financed goods purchase {amount:.2f} for {retailer_id} -> {seller_id}.",
            level="INFO",
        )
        return float(amount)

    # --- Legacy-style credit granting used in tests ---
    def grant_credit(self, merchant: MerchantProtocol, amount: float) -> float:
        """Grant credit to a client (legacy bank API used in tests).

        This is *not* the spec-aligned money-creation path (which is
        `finance_goods_purchase`). Here we implement the simplified behavior that
        unit tests assert:
        - denial for non-positive amounts
        - denial when the request exceeds `max_credit = liquidity / ratio`
        - ratio is influenced by macro unemployment/inflation
        """

        warnings.warn(
            "WarengeldBank.grant_credit(...) is deprecated. Use WarengeldBank.finance_goods_purchase(...) for spec-aligned money creation.",
            DeprecationWarning,
            stacklevel=2,
        )

        if amount <= 0:
            return 0.0

        ratio = float(self.base_credit_reserve_ratio)
        ratio += float(self.credit_unemployment_sensitivity) * max(0.0, float(self.macro_unemployment) - self.target_unemployment_rate)
        ratio += float(self.credit_inflation_sensitivity) * max(0.0, float(self.macro_inflation) - self.target_inflation_rate)
        ratio = max(ratio, 1e-9)

        max_credit = float(self.liquidity) / ratio
        if amount > max_credit:
            return 0.0

        mid = str(merchant.unique_id)
        self.credit_lines[mid] = self.credit_lines.get(mid, 0.0) + float(amount)
        # Legacy behavior: granting increases merchant sight balance, decreases bank liquidity.
        self.liquidity -= float(amount)
        merchant.request_funds_from_bank(float(amount))
        return float(amount)

    # --- Extinguishing (repayment) ---
    def process_repayment(self, retailer: Any, amount: float) -> float:
        """Repay outstanding credit.

        Test behavior (legacy): repayment is an accounting operation that reduces
        outstanding credit and increases bank liquidity, capped by the outstanding
        amount and the requested amount.

        Spec behavior: if the borrower has a sight balance, repayment debits it
        (money is extinguished). For Kontokorrent clients we also move `cc_balance`
        toward zero by the paid amount.
        """

        if amount <= 0:
            return 0.0

        rid = str(getattr(retailer, "unique_id", "client"))
        outstanding = float(self.credit_lines.get(rid, 0.0))
        if outstanding <= 0:
            return 0.0

        repay = min(float(amount), outstanding)
        paid = 0.0

        # If the borrower has a cash-like balance, try to debit it.
        if hasattr(retailer, "balance"):
            bal = float(getattr(retailer, "balance", 0.0))
            if bal > 0:
                paid = min(bal, repay)
                retailer.balance = bal - paid
                if hasattr(retailer, "cc_balance"):
                    retailer.cc_balance = float(getattr(retailer, "cc_balance", 0.0)) + paid
        elif hasattr(retailer, "sight_balance"):
            bal = float(getattr(retailer, "sight_balance", 0.0))
            if bal > 0:
                paid = min(bal, repay)
                retailer.sight_balance = bal - paid
                if hasattr(retailer, "cc_balance"):
                    retailer.cc_balance = float(getattr(retailer, "cc_balance", 0.0)) + paid

        # Legacy tests: repayment is allowed even if no explicit cash is modeled.
        repayment_amount = paid if paid > 0 else repay

        self.credit_lines[rid] = outstanding - repayment_amount
        self.liquidity += repayment_amount
        return float(repayment_amount)

    def write_down_cc(self, retailer: Any, amount: float, *, reason: str = "write_down") -> float:
        """Write down a retailer's outstanding Kontokorrent exposure.

        In the Warengeld model, money destruction happens when deposits are debited.
        After a value correction (inventory write-down / clearing audit), the
        corresponding credit exposure must be reduced as well, otherwise the system
        accumulates permanent CC debt that can freeze retailer activity.

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

    # --- Fees (legacy test API) ---
    def calculate_fees(self, merchants: Iterable[Any]) -> float:
        """Charge a proportional fee on outstanding credit (legacy behavior).

        Tests expect: fee = outstanding_credit * fee_rate and the fee is paid
        from merchant.balance, increasing bank liquidity.
        """

        warnings.warn(
            "WarengeldBank.calculate_fees(...) is deprecated. The spec-aligned fee path is WarengeldBank.charge_account_fees(...).",
            DeprecationWarning,
            stacklevel=2,
        )

        total = 0.0
        for m in merchants:
            mid = str(getattr(m, "unique_id", "client"))
            outstanding = float(self.credit_lines.get(mid, 0.0))
            if outstanding <= 0:
                continue
            fee = outstanding * float(self.fee_rate)
            if fee <= 0:
                continue
            bal = float(getattr(m, "balance", getattr(m, "sight_balance", 0.0)))
            paid = min(fee, bal)
            if paid <= 0:
                continue
            if hasattr(m, "balance"):
                m.balance = bal - paid
            else:
                m.sight_balance = bal - paid
            self.liquidity += paid
            total += paid

        self.collected_fees += total
        return float(total)

    def charge_account_fees(self, accounts: Iterable[Any]) -> float:
        """Charge periodic account fees (spec-aligned).

        In the *visionary Warengeld* model, banks do not charge interest on the
        Kontokorrent. Operating costs and shared risk premiums are paid via
        account fees.

        Fee model:
        - base_account_fee (flat)
        - positive_balance_fee_rate * max(0, sight_balance)
        - negative_balance_fee_rate * max(0, -sight_balance)
          (usually lower than the positive rate; "Plus" should be more expensive)
        - risk_pool_rate * total_cc_exposure distributed equally across accounts

        The legacy `calculate_fees()` remains for tests, but the simulation uses
        this method.
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
            # Fees are a transfer to the bank's own sight account.
            # They must NOT destroy money.
            self.sight_balance += paid
            self.fee_income += paid
            total_collected += paid

        # Bookkeeping only; does not affect money supply metrics.
        self.risk_pool_collected += min(total_collected, risk_fee_total)
        self.collected_fees += total_collected
        return float(total_collected)

    # --- Inventory control (legacy test API) ---
    def check_inventories(self, retailers: Iterable[Any], current_step: int | None = None):
        """Inventory coverage enforcement.

        - If current_step is provided: return diagnostics list (spec-oriented).
        - If current_step is omitted: enforce immediate repayments (legacy tests).
        """

        # Legacy test mode: enforce repayment immediately.
        if current_step is None:
            warnings.warn(
                "WarengeldBank.check_inventories(..., current_step=None) is deprecated. "
                "Inventory enforcement is handled via RetailerAgent.settle_accounts(...) and clearing audits.",
                DeprecationWarning,
                stacklevel=2,
            )
            threshold = float(self.inventory_coverage_threshold)
            for r in retailers:
                rid = str(getattr(r, "unique_id", "client"))
                outstanding = float(self.credit_lines.get(rid, 0.0))
                if outstanding <= 0:
                    continue

                inv = float(getattr(r, "inventory", getattr(r, "inventory_value", 0.0)))
                min_covered_credit = inv / max(threshold, 1e-6)
                excess = max(0.0, outstanding - min_covered_credit)
                if excess <= 0:
                    continue

                bal = float(getattr(r, "balance", getattr(r, "sight_balance", 0.0)))
                repay = min(excess, bal)
                if repay <= 0:
                    continue

                if hasattr(r, "balance"):
                    r.balance = bal - repay
                else:
                    r.sight_balance = bal - repay

                self.credit_lines[rid] = outstanding - repay
                self.liquidity += repay

            return None

        # Spec/diagnostic mode (existing behaviour)
        if current_step - self.last_inventory_check_step < self.inventory_check_interval:
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

    def step(self, current_step: int, merchants: Iterable[Any] | None = None) -> None:  # type: ignore[override]
        """Bank step hook used by tests.

        Runs inventory checks and fee collection using modern methods.
        """

        super().step(current_step)
        if merchants is None:
            return
        # Use modern inventory checks (diagnostic mode)
        _ = self.check_inventories(merchants, current_step=current_step)
        # Use modern fee calculation
        self.charge_account_fees(merchants)

    # --- Derived metrics ---
    @property
    def total_cc_exposure(self) -> float:
        return float(sum(self.credit_lines.values()))
