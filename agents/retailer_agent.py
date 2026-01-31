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


@dataclass
class RetailSaleResult:
    quantity: float
    sale_value: float
    cost_value: float
    gross_profit: float


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
        self.cc_limit: float = float(cc_limit if cc_limit is not None else self.config.retailer.initial_cc_limit)
        # Negative = drawn Kontokorrent
        self.cc_balance: float = 0.0

        # Inventory
        self.inventory_units: float = 0.0
        self.inventory_value: float = 0.0  # valued at cost
        self.target_inventory_value: float = float(
            target_inventory_value if target_inventory_value is not None else self.config.retailer.target_inventory_value
        )

        # Reserve for write-downs (Warenwertberichtigungskonto)
        self.write_down_reserve: float = 0.0


        # Land/environmental variables (used by State taxes / EnvironmentalAgency)
        self.land_area: float = float(
            land_area if land_area is not None else getattr(self.config.retailer, 'initial_land_area', 20.0)
        )
        self.environmental_impact: float = float(
            environmental_impact if environmental_impact is not None else getattr(self.config.retailer, 'environmental_impact', 1.0)
        )

        # Book-keeping
        self.last_unit_cost: float = self.config.company.production_base_price
        self.last_unit_price: float = self.last_unit_cost * (1 + self.config.retailer.price_markup)

        # Flow metrics (cumulative, reset each simulation step by main loop if desired)
        self.sales_total: float = 0.0
        self.purchases_total: float = 0.0
        self.write_downs_total: float = 0.0

    # --- Convenience adapters (compatibility with legacy code/tests) ---
    @property
    def balance(self) -> float:
        return self.sight_balance

    @balance.setter
    def balance(self, value: float) -> None:
        self.sight_balance = float(value)

    # --- Inventory + pricing ---
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
    def restock_goods(self, companies: list[Company], bank: WarengeldBank, current_step: int) -> float:
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

        producer = random.choice(companies)

        # Translate desired value into desired quantity at producer's unit price.
        unit_price = producer.get_unit_price()
        if unit_price <= 0:
            return 0.0

        desired_qty = desired_value / unit_price
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
            # If financing is denied (cc limit), revert goods transfer.
            producer.finished_goods_units += sold_qty
            return 0.0

        # Inventory increases at cost.
        self.inventory_units += sold_qty
        self.inventory_value += financed
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
        if budget <= 0 or self.inventory_units <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        price = self.unit_sale_price()
        if price <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        qty = min(self.inventory_units, budget / price)
        if qty <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        sale_value = qty * price
        unit_cost = self._avg_unit_cost()
        cost_value = qty * unit_cost

        # Transfer (money-neutral)
        paid = household.pay(sale_value)
        if paid <= 0:
            return RetailSaleResult(0.0, 0.0, 0.0, 0.0)

        # If household couldn't pay full sale_value, scale down quantities proportionally.
        if paid < sale_value and sale_value > 0:
            scale = paid / sale_value
            qty *= scale
            sale_value = paid
            cost_value = qty * unit_cost

        self.sight_balance += sale_value
        self.sales_total += sale_value

        # Inventory reduction at cost
        self.inventory_units -= qty
        self.inventory_value = max(0.0, self.inventory_value - cost_value)

        gross_profit = max(0.0, sale_value - cost_value)

        # Fill write-down reserve from (estimated) profits.
        reserve_add = gross_profit * self.config.retailer.write_down_reserve_share
        if reserve_add > 0 and self.sight_balance >= reserve_add:
            self.sight_balance -= reserve_add
            self.write_down_reserve += reserve_add

        return RetailSaleResult(qty, sale_value, cost_value, gross_profit)

    def auto_repay_kontokorrent(self, bank: WarengeldBank) -> float:
        """Use excess sight balances to repay Kontokorrent (money extinguishing)."""
        if not self.config.retailer.auto_repay:
            return 0.0

        if self.cc_balance >= 0:
            return 0.0

        available = max(0.0, self.sight_balance - self.config.retailer.working_capital_buffer)
        if available <= 0:
            return 0.0

        repay = min(available, abs(self.cc_balance))
        if repay <= 0:
            return 0.0

        repaid = bank.process_repayment(self, repay)
        return repaid

    def apply_obsolescence_write_down(self, current_step: int) -> float:
        """Write down inventory value and extinguish the same amount of money.

        First uses the dedicated write-down reserve. If insufficient, it uses
        the retailer's sight balance. Remaining uncovered write-down is left as
        a mismatch and should be picked up by audits / insolvency handling.
        """
        rate = self.config.retailer.obsolescence_rate
        if rate <= 0 or self.inventory_value <= 0:
            return 0.0

        write_down = self.inventory_value * rate
        if write_down <= 0:
            return 0.0

        self.inventory_value = max(0.0, self.inventory_value - write_down)
        self.write_downs_total += write_down

        destroyed = 0.0
        use_reserve = min(self.write_down_reserve, write_down)
        if use_reserve > 0:
            self.write_down_reserve -= use_reserve
            destroyed += use_reserve

        remaining = write_down - use_reserve
        if remaining > 0:
            use_sight = min(self.sight_balance, remaining)
            self.sight_balance -= use_sight
            destroyed += use_sight

        if destroyed > 0:
            log(
                f"Retailer {self.unique_id}: Inventory write-down={write_down:.2f}, extinguished={destroyed:.2f} at step {current_step}.",
                level="INFO",
            )

        return destroyed


    def settle_accounts(self, bank: WarengeldBank, current_step: int | None = None) -> dict[str, float]:
        """End-of-day settlements.

        This is where the *extinguishing* side of the Warengeld cycle primarily happens.
        """
        repaid = self.auto_repay_kontokorrent(bank)
        write_down = self.apply_obsolescence_write_down(current_step or 0)
        return {"repaid": repaid, "inventory_write_down": write_down}


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
