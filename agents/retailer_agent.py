"""Retailer (Einzelhandel) agent.

In the Warengeld regime, **the only place where new money is created** is when a
retailer finances *goods purchases* via an interest-free Kontokorrent line.

Money is extinguished when sales revenues flow back to the retailer and are
used to repay the Kontokorrent balance.

This agent is intentionally narrow in scope: it manages inventory, a sight
account, a Kontokorrent balance, and a reserve account for write-downs.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from config import CONFIG_MODEL, SimulationConfig
from logger import log

from .base_agent import BaseAgent

if TYPE_CHECKING:
    from .bank import WarengeldBank
    from .company_agent import Company
    from .household_agent import Household
    from .state_agent import State


@dataclass
class RetailSaleResult:
    quantity: float
    sale_value: float
    cost_value: float
    gross_profit: float


@dataclass
class InventoryLot:
    """Single inventory lot with group metadata and per-lot depreciation.

    Expliziter Bezug: doc/issues.md Abschnitt 2 → "Warenbewertung & Abschreibung".
    """

    group_id: str
    units: float
    unit_cost: float
    unit_market_price: float
    obsolescence_factor: float = 1.0
    age_days: int = 0

    def _base_unit_value(self, *, valuation_method: str) -> float:
        if valuation_method == "market":
            return float(self.unit_market_price)
        if valuation_method == "lower_of_cost_or_market":
            return float(min(self.unit_cost, self.unit_market_price))
        # default: cost
        return float(self.unit_cost)

    def is_unsellable(self, *, config: SimulationConfig) -> bool:
        if int(self.age_days) >= int(config.retailer.unsellable_after_days):
            return True
        floor = float(config.retailer.unsellable_market_price_floor_ratio)
        if self.unit_cost > 0 and float(self.unit_market_price) <= float(self.unit_cost) * floor:
            return True
        return False

    def carrying_unit_value(self, *, config: SimulationConfig) -> float:
        if self.is_unsellable(config=config):
            return 0.0
        base = self._base_unit_value(
            valuation_method=str(config.retailer.inventory_valuation_method)
        )
        return max(0.0, base * float(self.obsolescence_factor))

    def carrying_value(self, *, config: SimulationConfig) -> float:
        return float(self.units) * self.carrying_unit_value(config=config)


class RetailerAgent(BaseAgent):
    """Einzelhandelskaufmann/-frau mit Kontokorrentlinie."""

    def __init__(
        self,
        unique_id: str,
        config: SimulationConfig | None = None,
        *,
        cc_limit: float | None = None,
        target_inventory_value: float | None = None,
        initial_sight_balance: float = 0.0,
        land_area: float | None = None,
        environmental_impact: float | None = None,
    ) -> None:
        super().__init__(unique_id)

        self.config: SimulationConfig = config or CONFIG_MODEL

        # Core accounts
        self.sight_balance: float = float(initial_sight_balance)
        self.cc_limit: float = float(
            cc_limit if cc_limit is not None else self.config.retailer.initial_cc_limit
        )
        # Negative = drawn Kontokorrent
        self.cc_balance: float = 0.0

        # Inventory
        self.inventory_units: float = 0.0
        # `inventory_value` is the *carrying value* under the chosen valuation
        # rule (cost/market/lower-of...). Default config keeps this identical to
        # historic behaviour ("cost").
        self.inventory_value: float = 0.0
        # Inventory lots are opt-in and created automatically when the retailer
        # restocks or when a legacy test sets only aggregate fields.
        self.inventory_lots: list[InventoryLot] = []
        self.target_inventory_value: float = float(
            target_inventory_value
            if target_inventory_value is not None
            else self.config.retailer.target_inventory_value
        )

        # Reserve for write-downs (Warenwertberichtigungskonto)
        self.write_down_reserve: float = 0.0

        # COGS tracking for CC-Limit Policy (rolling monthly avg)
        self.cogs_total: float = 0.0
        self.cogs_history: list[float] = []
        # Audit risk score in [0,1] used by the bank as a CC-limit modifier
        self.audit_risk_score: float = 0.0

        # Land/environmental variables (used by State taxes / EnvironmentalAgency)
        self.land_area: float = float(
            land_area
            if land_area is not None
            else getattr(self.config.retailer, "initial_land_area", 20.0)
        )
        self.environmental_impact: float = float(
            environmental_impact
            if environmental_impact is not None
            else getattr(self.config.retailer, "environmental_impact", 1.0)
        )

        # Book-keeping
        self.last_unit_cost: float = self.config.company.production_base_price
        self.last_unit_price: float = self.last_unit_cost * (1 + self.config.retailer.price_markup)

        # Flow metrics (cumulative, reset each simulation step by main loop if desired)
        self.sales_total: float = 0.0
        self.purchases_total: float = 0.0
        self.write_downs_total: float = 0.0
        self.write_down_history: list[tuple[int, float, float]] = []
        # Explicit money-destruction tracking (reset each step by main loop)
        self.repaid_total: float = 0.0
        self.inventory_write_down_extinguished_total: float = 0.0

    # --- Convenience adapters (compatibility with legacy code/tests) ---
    @property
    def balance(self) -> float:
        return self.sight_balance

    @balance.setter
    def balance(self, value: float) -> None:
        self.sight_balance = float(value)

    @property
    def sight_allowance(self) -> float:
        """Freibetrag/Buffer für automatische Kontokorrent-Tilgung.

        Spezifikation: doc/specs.md Section 4.2.
        Der Retailer hält diesen Betrag als Working-Capital-Puffer; nur der
        Überschuss wird automatisiert zur CC-Tilgung verwendet.
        """

        return float(self.config.retailer.working_capital_buffer)

    # --- CC-Limit Policy helpers ---
    def push_cogs_history(self, *, window_days: int) -> None:
        # Finalize current-step COGS into the rolling history.
        if window_days <= 0:
            raise ValueError("window_days must be > 0")
        self.cogs_history.append(float(self.cogs_total))
        if len(self.cogs_history) > window_days:
            self.cogs_history = self.cogs_history[-window_days:]
        self.cogs_total = 0.0

    def avg_monthly_cogs(self, *, window_days: int, days_per_month: int) -> float:
        # Rolling monthly COGS estimate based on the last `window_days` daily totals.
        if window_days <= 0:
            raise ValueError("window_days must be > 0")
        if days_per_month <= 0:
            raise ValueError("days_per_month must be > 0")
        if not self.cogs_history:
            return 0.0
        window = self.cogs_history[-window_days:]
        avg_daily = sum(window) / float(len(window))
        return avg_daily * float(days_per_month)

    def accept_cc_limit_proposal(
        self,
        proposed_limit: float,
        *,
        current_limit: float,
        current_step: int,
        max_monthly_decrease: float,
    ) -> bool:
        # Retailer-side acceptance rule (partnership).
        _ = current_step  # currently unused; kept for possible future policies
        if proposed_limit >= current_limit:
            return True
        if current_limit <= 0:
            return True
        if not (0.0 <= max_monthly_decrease <= 1.0):
            raise ValueError("max_monthly_decrease must be within [0,1]")
        decrease_ratio = (current_limit - proposed_limit) / float(current_limit)
        return decrease_ratio <= max_monthly_decrease

    # --- Inventory + pricing ---
    def _sync_inventory_totals_from_lots(self) -> None:
        self.inventory_units = float(sum(float(l.units) for l in self.inventory_lots))
        self.inventory_value = float(
            sum(float(l.carrying_value(config=self.config)) for l in self.inventory_lots)
        )

        # Defensive clamps: small negatives can appear from float ops.
        if self.inventory_units < 0:
            self.inventory_units = 0.0
        if self.inventory_value < 0:
            self.inventory_value = 0.0

    def _ensure_legacy_lot(self) -> None:
        """Compatibility shim for older tests/code.

        Some tests assign only `inventory_units` and `inventory_value` directly
        (without lots). To keep those tests stable while adding grouped/lot
        valuation, we materialize a single lot on-demand.
        """

        if self.inventory_lots:
            return
        if self.inventory_units <= 0:
            return
        unit_value = self.last_unit_cost
        if self.inventory_value > 0:
            unit_value = float(self.inventory_value / max(self.inventory_units, 1e-9))
        group_id = str(self.config.retailer.default_article_group)
        self.inventory_lots = [
            InventoryLot(
                group_id=group_id,
                units=float(self.inventory_units),
                unit_cost=float(unit_value),
                unit_market_price=float(unit_value),
                obsolescence_factor=1.0,
                age_days=0,
            )
        ]
        self._sync_inventory_totals_from_lots()

    def add_inventory_lot(
        self,
        *,
        group_id: str,
        units: float,
        unit_cost: float,
        unit_market_price: float | None = None,
        age_days: int = 0,
    ) -> None:
        """Add a new inventory lot.

        Public helper used by restocking logic and tests.
        """

        if units <= 0:
            return
        mp = float(unit_cost if unit_market_price is None else unit_market_price)
        self.inventory_lots.append(
            InventoryLot(
                group_id=str(group_id),
                units=float(units),
                unit_cost=float(unit_cost),
                unit_market_price=mp,
                obsolescence_factor=1.0,
                age_days=int(age_days),
            )
        )
        self._sync_inventory_totals_from_lots()

    def _sellable_units(self) -> float:
        self._ensure_legacy_lot()
        return float(
            sum(
                float(l.units)
                for l in self.inventory_lots
                if not l.is_unsellable(config=self.config)
            )
        )

    def _consume_units_fifo(self, quantity: float) -> float:
        """Consume inventory FIFO and return carried cost value.

        Unsellable lots are not consumed.
        """

        if quantity <= 0:
            return 0.0
        self._ensure_legacy_lot()

        remaining = float(quantity)
        cost_value = 0.0
        new_lots: list[InventoryLot] = []

        for lot in self.inventory_lots:
            if remaining <= 1e-9:
                new_lots.append(lot)
                continue
            if lot.units <= 1e-9:
                continue
            if lot.is_unsellable(config=self.config):
                new_lots.append(lot)
                continue
            take = min(float(lot.units), remaining)
            unit_val = lot.carrying_unit_value(config=self.config)
            cost_value += take * float(unit_val)
            lot.units = float(lot.units) - take
            remaining -= take
            if lot.units > 1e-9:
                new_lots.append(lot)

        self.inventory_lots = new_lots
        self._sync_inventory_totals_from_lots()
        return float(cost_value)

    def _avg_unit_cost(self) -> float:
        if self.inventory_units <= 0:
            return float(self.last_unit_cost)
        return float(self.inventory_value / max(self.inventory_units, 1e-9))

    def unit_sale_price(self) -> float:
        cost = self._avg_unit_cost()
        self.last_unit_cost = cost
        self.last_unit_price = cost * (1 + self.config.retailer.price_markup)
        return self.last_unit_price

    # --- Warengeld primitives ---
    def restock_goods(
        self, companies: list[Company], bank: WarengeldBank, current_step: int
    ) -> float:
        """Order goods from producers if inventory is below reorder point.

        Money creation happens inside `bank.finance_goods_purchase`.

        Returns the financed purchase value.
        """
        if not companies:
            return 0.0

        reorder_point = self.config.retailer.reorder_point_ratio * self.target_inventory_value
        if self.inventory_value >= reorder_point:
            return 0.0

        desired_value = max(0.0, self.target_inventory_value - self.inventory_value)
        if desired_value <= 0:
            return 0.0

        # IMPORTANT (stability / no-deadlock):
        # When the CC limit binds, we must *scale down* the order to the
        # remaining headroom, instead of trying a fixed target order and
        # getting denied.
        #
        # Otherwise the system can enter a hard deadlock:
        # - inventory hits 0
        # - retailer at/near cc_limit cannot finance the (fixed) restock order
        # - no inventory => no sales => no repayment => no headroom => permanent stall
        #
        # Headroom formula for negative cc balances:
        #   cc_balance - amount >= -cc_limit  =>  amount <= cc_limit + cc_balance
        #
        # (cc_balance is typically <= 0; if it's positive, headroom is large.)
        headroom = max(0.0, float(self.cc_limit) + float(self.cc_balance))
        order_budget = min(float(desired_value), float(headroom))
        if order_budget <= 1e-9:
            return 0.0

        producer = random.choice(companies)

        # Translate desired value into desired quantity at producer's unit price.
        unit_price = producer.get_unit_price()
        if unit_price <= 0:
            return 0.0

        desired_qty = order_budget / unit_price
        sold_qty, sold_value = producer.sell_to_retailer(desired_qty)
        if sold_value <= 0 or sold_qty <= 0:
            return 0.0

        financed = bank.finance_goods_purchase(
            retailer=self,
            seller=producer,
            amount=sold_value,
            current_step=current_step,
        )

        if financed <= 0:
            # Financing *should* succeed because we pre-capped to headroom.
            # Keep defensive revert for rounding / unexpected bank policy changes.
            producer.finished_goods_units += sold_qty
            return 0.0

        # Inventory increases as a fresh lot (per-lot valuation & depreciation).
        default_group = self.config.retailer.default_article_group
        unit_cost = financed / sold_qty if sold_qty > 0 else unit_price
        self.add_inventory_lot(
            group_id=default_group,
            units=sold_qty,
            unit_cost=unit_cost,
            unit_market_price=unit_cost,
            age_days=0,
        )
        self.purchases_total += financed

        log(
            f"Retailer {self.unique_id}: Restocked goods value={financed:.2f} units={sold_qty:.2f} from {producer.unique_id}.",
            level="INFO",
        )
        return financed

    def sell_to_household(self, household: Household, budget: float) -> RetailSaleResult:
        """Sell goods to a household.

        This does NOT create or destroy money by itself: it is a transfer.
        Money is destroyed when the retailer later repays Kontokorrent.
        """
        sellable_units = self._sellable_units()
        if budget <= 0 or sellable_units <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        price = self.unit_sale_price()
        if price <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        qty = min(sellable_units, budget / price)
        if qty <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        sale_value = qty * price

        # Transfer (money-neutral)
        paid = household.pay(sale_value)
        if paid <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        # If household couldn't pay full sale_value, scale down quantities proportionally.
        if paid < sale_value and sale_value > 0:
            scale = paid / sale_value
            qty *= scale
            sale_value = paid

        cost_value = self._consume_units_fifo(qty)

        self.cogs_total += float(cost_value)
        self.sight_balance += sale_value
        self.sales_total += sale_value

        gross_profit = max(0.0, sale_value - cost_value)

        # Fill write-down reserve from (estimated) profits.
        reserve_add = gross_profit * self.config.retailer.write_down_reserve_share
        if reserve_add > 0 and self.sight_balance >= reserve_add:
            self.sight_balance -= reserve_add
            self.write_down_reserve += reserve_add

        return RetailSaleResult(qty, sale_value, cost_value, gross_profit)

    def sell_to_state(
        self,
        state: "State",
        budget: float,
        *,
        budget_bucket: str = "infrastructure_budget",
    ) -> RetailSaleResult:
        """Sell goods to the State (public procurement).

        Bezug: doc/issues.md Abschnitt 2) "Staat als realer Nachfrager..." und
        Abschnitt 6) M1.

        Important: This is a **pure transfer** (money-neutral). It must not call
        money-creation paths (e.g. WarengeldBank.finance_goods_purchase).
        """

        sellable_units = self._sellable_units()
        if budget <= 0 or sellable_units <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        price = self.unit_sale_price()
        if price <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        # State can only spend what is available in the chosen bucket.
        available = float(getattr(state, budget_bucket))
        effective_budget = min(float(budget), max(0.0, available))
        if effective_budget <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        qty = min(sellable_units, effective_budget / price)
        if qty <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        sale_value = qty * price
        paid = state.pay(sale_value, budget_bucket=budget_bucket)
        if paid <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        # If State couldn't pay full sale_value, scale down quantities proportionally.
        if paid < sale_value and sale_value > 0:
            scale = paid / sale_value
            qty *= scale
            sale_value = paid

        cost_value = self._consume_units_fifo(qty)

        self.cogs_total += float(cost_value)
        self.sight_balance += sale_value
        self.sales_total += sale_value

        gross_profit = max(0.0, sale_value - cost_value)
        reserve_add = gross_profit * self.config.retailer.write_down_reserve_share
        if reserve_add > 0 and self.sight_balance >= reserve_add:
            self.sight_balance -= reserve_add
            self.write_down_reserve += reserve_add

        log(
            f"Retailer {self.unique_id}: sold to State {state.unique_id} value={sale_value:.2f} units={qty:.2f}.",
            level="INFO",
        )

        return RetailSaleResult(qty, sale_value, cost_value, gross_profit)

    def auto_repay_kontokorrent(self, bank: WarengeldBank) -> float:
        """Use excess sight balances to repay Kontokorrent (money extinguishing).

        Spezifikation: doc/specs.md Section 4.2.
        """
        if not self.config.retailer.auto_repay:
            return 0.0

        repaid = bank.auto_repay_cc_from_sight(self)
        if repaid > 0:
            self.repaid_total += float(repaid)
        return repaid

    def apply_obsolescence_write_down(self, current_step: int) -> float:
        """Write down inventory value and extinguish the same amount of money.

        First uses the dedicated write-down reserve. If insufficient, it uses
        the retailer's sight balance. Remaining uncovered write-down is left as
        a mismatch and should be picked up by audits / insolvency handling.
        """
        self._ensure_legacy_lot()

        if not self.inventory_lots:
            return 0.0

        base_rate = float(self.config.retailer.obsolescence_rate)
        unsellable_after_days = int(self.config.retailer.unsellable_after_days)

        write_down_total = 0.0
        for lot in self.inventory_lots:
            old_value = lot.carrying_value(config=self.config)

            # Ageing happens daily (this method is called from settle_accounts).
            lot.age_days += 1

            # Unsellable criterion: once triggered, the lot is written down to 0.
            if unsellable_after_days > 0 and lot.age_days >= unsellable_after_days:
                lot.obsolescence_factor = 0.0
            else:
                group_rate = float(
                    self.config.retailer.obsolescence_rate_by_group.get(lot.group_id, base_rate)
                )
                if group_rate > 0:
                    lot.obsolescence_factor *= max(0.0, 1.0 - group_rate)

            new_value = lot.carrying_value(config=self.config)
            if new_value < old_value:
                write_down_total += old_value - new_value

        if write_down_total <= 0:
            return 0.0

        self.write_downs_total += write_down_total
        self._sync_inventory_totals_from_lots()

        destroyed = 0.0
        use_reserve = min(self.write_down_reserve, write_down_total)
        if use_reserve > 0:
            self.write_down_reserve -= use_reserve
            destroyed += use_reserve

        remaining = write_down_total - use_reserve
        if remaining > 0:
            use_sight = min(self.sight_balance, remaining)
            self.sight_balance -= use_sight
            destroyed += use_sight

        if destroyed > 0:
            self.inventory_write_down_extinguished_total += destroyed
            self.write_down_history.append(
                (int(current_step), float(write_down_total), float(destroyed))
            )
            log(
                f"Retailer {self.unique_id}: Inventory write-down={write_down_total:.2f}, extinguished={destroyed:.2f} at step {current_step}.",
                level="INFO",
            )

        return destroyed

    def apply_inventory_write_downs(self, *, current_step: int, bank: "WarengeldBank") -> float:
        """Abschreibungen auf Warenlager (Geldvernichtung) + CC-Exposure-Anpassung.

        Spezifikation: doc/specs.md Section 4.6.
        Expliziter Bezug: doc/issues.md Abschnitt 4/5 → "Hyperinflation / Numerische Überläufe ...".
        """

        destroyed = self.apply_obsolescence_write_down(current_step)
        if destroyed > 0:
            # Inventory value corrections must also reduce outstanding CC exposure.
            bank.write_down_cc(self, destroyed, reason="inventory_write_downs")
        return float(destroyed)

    def settle_accounts(
        self, bank: WarengeldBank, current_step: int | None = None
    ) -> dict[str, float]:
        """End-of-day settlements.

        This is where the *extinguishing* side of the Warengeld cycle primarily happens.
        """
        repaid = self.auto_repay_kontokorrent(bank)
        destroyed = self.apply_inventory_write_downs(current_step=int(current_step or 0), bank=bank)
        # Spec 4.1: enforce inventory-backed CC limits (additional destruction).
        bank.enforce_inventory_backing(self)

        return {"repaid": float(repaid), "inventory_write_down": float(destroyed)}

    def step(
        self,
        current_step: int,
        *,
        companies: list[Company] | None = None,
        households: list[Household] | None = None,
        bank: WarengeldBank | None = None,
    ) -> None:
        """Optional high-level step.

        The main simulation loop can also call the individual methods in a
        specific pipeline order.
        """
        if bank is None:
            return

        if companies:
            self.restock_goods(companies, bank, current_step)

        # Households are handled from Household.step in the main loop.

        self.auto_repay_kontokorrent(bank)
        self.apply_obsolescence_write_down(current_step)
