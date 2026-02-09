# company_agent.py
import random
from collections import deque
from typing import ClassVar, Literal

from agents.base_agent import BaseAgent
from agents.household_agent import Household
from agents.labor_market import LaborMarket
from agents.lineage_mixin import LineageMixin
from agents.savings_bank_agent import SavingsBank
from agents.state_agent import State
from config import CONFIG_MODEL, SimulationConfig
from logger import log

# Type aliases for improved readability
Employee = Household  # Type of employees (currently Household)


class Company(BaseAgent, LineageMixin):
    _lineage_counters: ClassVar[dict[str, int]] = {}

    """
    Represents a company economic agent in the simulation.

    Companies produce goods, hire employees, pay wages and taxes,
    invest in R&D and can grow or go bankrupt.
    """

    def __init__(
        self,
        unique_id: str,
        production_capacity: float = 100.0,
        resource_usage: float = 10.0,
        land_area: float = 100.0,
        environmental_impact: float = 5.0,
        max_employees: int = 10,
        employees: Employee | None = None,
        config: SimulationConfig | None = None,
        labor_market: LaborMarket | None = None,
    ) -> None:
        """
        Initialize a company with economic attributes.

        Args:
            unique_id: Unique identifier for the company
            production_capacity: Maximum production capacity
            resource_usage: Resources used per production unit
            land_area: Land area occupied (for tax calculation)
            environmental_impact: Environmental impact factor
            max_employees: Maximum number of employees
            employees: Initial list of employees
            labor_market: Optional reference to labor market for immediate job offer registration
        """
        BaseAgent.__init__(self, unique_id)
        self._init_lineage(unique_id)

        # Basic attributes
        self.generation: int = 1
        self.production_capacity: float = production_capacity
        self.resource_usage: float = resource_usage
        self.land_area: float = land_area
        self.environmental_impact: float = environmental_impact

        # Employee management
        self.max_employees: int = max_employees
        self.employees: list[Employee] = employees if employees is not None else []
        self.pending_hires: int = 0

        # Financial attributes
        # --- Real stock (goods) ---
        self.finished_goods_units: float = 0.0

        # --- Money stock (Sichtguthaben) ---
        self.sight_balance: float = 0.0

        # --- Legacy attribute compatibility (tests still use these names) ---
        # NOTE: Prefer `sight_balance` / `finished_goods_units` in new code.
        # Exposed via @property `balance` and `inventory`.

        # Growth parameters
        self.growth_phase: bool = False
        self.growth_counter: int = 0
        self.config: SimulationConfig = config or CONFIG_MODEL
        self.growth_threshold: int = self.config.company.growth_threshold
        self.investment_threshold: float = self.config.company.investment_threshold
        self.bankruptcy_threshold: float = self.config.company.bankruptcy_threshold

        if labor_market:
            labor_market.register_job_offer(
                self,
                wage=self.config.labor_market.starting_wage,
                positions=self.config.INITIAL_JOB_POSITIONS_PER_COMPANY,
            )

        # Research and development
        self.rd_investment: float = 0.0
        self.innovation_index: float = 0.0
        self._zero_staff_steps: int = 0
        self._consecutive_underpaid_steps: int = 0

        # Flow metrics (reset per step by the main loop if desired)
        # Services are booked as pure transfers (no inventory) and are explicitly
        # tracked for transparency (doc/issues.md Abschnitt 6 -> M3).
        self.service_sales_total: float = 0.0

        # --- Demand-responsive production tracking ---
        # Rolling window of daily sales (units sold to retailers).
        # Book ref: "Kaufleute [sorgen] durch ihre Warenbestellungen für eine
        # bedarfsgerechte Ausrichtung der Produktion" (line 2463).
        _window = self.config.company.production_sales_window_days
        self._sales_history: deque[float] = deque(maxlen=_window)
        self._step_sales: float = 0.0  # accumulates within a single step

    # --- Legacy compatibility properties ---
    @property
    def inventory(self) -> float:
        return float(self.finished_goods_units)

    @inventory.setter
    def inventory(self, value: float) -> None:
        self.finished_goods_units = float(value)

    @property
    def balance(self) -> float:
        return float(self.sight_balance)

    @balance.setter
    def balance(self, value: float) -> None:
        self.sight_balance = float(value)

    def invest_in_rd(self) -> None:
        """
        Track notional R&D investment for innovation probability.

        R&D is modeled as an *accounting metric* — it represents the
        company's accumulated knowledge capital, NOT a cash outflow.
        In the Warengeld model, money must always flow to a real
        counterparty (employee, supplier, state).  Previously, R&D
        investment deducted from sight_balance but the money went to
        no one, making it an unintentional money destruction sink.

        Fix E: R&D is now purely notional.  The sight_balance is NOT
        reduced.  The rd_investment counter still drives innovation
        probability via innovate().
        """
        rd_trigger: float = self.config.company.rd_investment_trigger_balance
        rd_rate: float = self.config.company.rd_investment_rate

        if self.sight_balance > rd_trigger:
            # Notional investment — NO money leaves the company.
            investment: float = (self.sight_balance - rd_trigger) * rd_rate
            self.rd_investment += investment

            log(
                f"Company {self.unique_id} notional R&D investment {investment:.2f}. "
                f"Total R&D: {self.rd_investment:.2f} (sight_balance unchanged).",
                level="INFO",
            )

    def innovate(self) -> None:
        """
        Attempt innovation based on R&D investment.

        If successful, production capacity increases and innovation index rises.
        """
        # Probability of innovation success increases with R&D investment
        probability: float = min(self.rd_investment / 1000, 0.5)
        innovation_bonus_rate: float = self.config.company.innovation_production_bonus
        rd_decay_factor: float = self.config.company.rd_investment_decay_factor

        if random.random() < probability:
            bonus: float = self.production_capacity * innovation_bonus_rate
            self.production_capacity += bonus
            self.innovation_index += 1

            log(
                f"Company {self.unique_id} innovated successfully! "
                f"Production capacity increased by {bonus:.2f} to {self.production_capacity:.2f}. "
                f"Innovation index: {self.innovation_index}.",
                level="INFO",
            )

            # Reduce R&D investment after successful innovation
            self.rd_investment *= rd_decay_factor

    def _avg_daily_sales(self) -> float:
        """Average daily sales over the rolling window.

        Returns 0.0 if no sales history exists yet (ramp-up phase).
        """
        if not self._sales_history:
            return 0.0
        return sum(self._sales_history) / len(self._sales_history)

    def _flush_step_sales(self) -> None:
        """Commit accumulated step sales to the rolling history.

        Must be called once per step *after* all sell_to_retailer() calls
        have been processed (i.e. at end-of-step or start-of-next).
        """
        self._sales_history.append(self._step_sales)
        self._step_sales = 0.0

    def produce(self) -> float:
        """Produce goods based on capacity, workforce, and demand signal.

        Demand-responsive production (Bedarfsgerechte Produktion):
        - During the ramp-up phase (no sales history), produce at full capacity
          so retailers can build initial stock.
        - Once sales history is available, target a specific inventory level
          based on recent sales velocity.
        - Production scales between min_utilization and 1.0 depending on how
          current inventory compares to the target.

        Book ref: "Kaufleute [sorgen] durch ihre Warenbestellungen für eine
        bedarfsgerechte Ausrichtung der Produktion" (line 2463).
        "Ungebremste Investitionstätigkeit führt bekanntlich zu
        Überkapazitäten" (line 1462).
        """
        if self.max_employees == 0:
            self._flush_step_sales()
            return 0.0

        efficiency: float = len(self.employees) / self.max_employees
        max_production: float = self.production_capacity * efficiency

        # --- Demand-responsive throttling ---
        avg_sales = self._avg_daily_sales()
        min_util = self.config.company.production_min_utilization
        target_days = self.config.company.production_target_stock_days
        sensitivity = self.config.company.production_ramp_sensitivity
        window = self.config.company.production_sales_window_days

        # Ramp-up detection: we need a full window AND at least one positive
        # sale in the history before we start throttling.  Without this,
        # newly founded companies (or companies at simulation start) would
        # throttle immediately because they have no sales track record yet.
        has_meaningful_history = len(self._sales_history) >= window and any(
            s > 0 for s in self._sales_history
        )

        if not has_meaningful_history:
            # Ramp-up phase: produce at full capacity so retailers can
            # build initial stock.
            utilization = 1.0
        elif avg_sales <= 0:
            # Have full history but zero recent sales → oversupply, throttle to minimum
            utilization = min_util
        else:
            target_inventory = avg_sales * target_days
            if target_inventory <= 0:
                utilization = min_util
            else:
                # ratio < 1 means we need more stock, > 1 means we have too much
                inventory_ratio = self.finished_goods_units / target_inventory
                # Scale: at ratio=0 → utilization=1.0, at ratio=1 → utilization ≈ min_util
                # Using a smooth curve: util = min_util + (1 - min_util) * max(0, 1 - ratio)^sensitivity
                gap = max(0.0, 1.0 - inventory_ratio)
                utilization = min_util + (1.0 - min_util) * (gap**sensitivity)

        utilization = max(min_util, min(1.0, utilization))
        actual_production = max_production * utilization

        self.finished_goods_units += actual_production
        self._flush_step_sales()

        log(
            f"Company {self.unique_id} produced {actual_production:.2f} units "
            f"(utilization {utilization:.1%}, avg_sales {avg_sales:.2f}/day, "
            f"inventory {self.finished_goods_units:.2f}).",
            level="INFO",
        )

        return actual_production

    def depreciate_inventory(self) -> tuple[float, float]:
        """Apply inventory depreciation (physical units lost).

        Book ref: "Nahrungsmittel verderben durch zu lange Lagerung.
        Industriegüter können durch Modeänderungen oder technologische
        Entwicklungen einen 'moralischen' Wertverlust erfahren" (line 1474).

        Fix F: Holding costs are now purely notional.  Previously, money
        was deducted from sight_balance but sent to no counterparty,
        making it an unintentional money destruction sink.  Physical
        depreciation (units lost) still applies — it reduces inventory
        volume, which creates real economic pressure via lower inventory
        value without destroying money.

        Returns:
            (units_lost, notional_holding_cost): Units written off and
            notional storage cost (reported for metrics, not deducted).
        """
        depreciation_rate = self.config.company.inventory_depreciation_rate
        holding_cost_rate = self.config.company.inventory_holding_cost_per_unit

        # 1) Physical depreciation: units are lost (spoilage, obsolescence)
        units_lost = self.finished_goods_units * depreciation_rate
        self.finished_goods_units -= units_lost

        # 2) Holding costs: notional only (for metrics / decision-making).
        #    NOT deducted from sight_balance — no money destruction.
        notional_holding_cost = self.finished_goods_units * holding_cost_rate

        if units_lost > 0.01 or notional_holding_cost > 0.01:
            log(
                f"Company {self.unique_id} inventory depreciation: "
                f"{units_lost:.2f} units lost, {notional_holding_cost:.2f} notional holding cost. "
                f"Remaining inventory: {self.finished_goods_units:.2f}, "
                f"balance: {self.sight_balance:.2f}.",
                level="INFO",
            )

        return units_lost, notional_holding_cost

    def add_employee_from_labor_market(self, worker: Employee, wage: float) -> None:
        """Receive a worker assignment from the labor market."""
        worker.employed = True  # type: ignore[attr-defined]
        worker.current_wage = wage  # type: ignore[attr-defined]
        # Optional backlink for clean worker removal.
        if hasattr(worker, "employer_id"):
            worker.employer_id = self.unique_id  # type: ignore[attr-defined]
        self.employees.append(worker)
        if self.pending_hires > 0:
            self.pending_hires -= 1
        log(
            f"Company {self.unique_id} accepted worker {worker.unique_id} at wage {wage:.2f}. "
            f"Total employees: {len(self.employees)}.",
            level="DEBUG",
        )

    def adjust_employees(self, labor_market: LaborMarket) -> None:
        """Advertise labor demand and release surplus employees via labor market.

        Also removes stale employee references (e.g., after household turnover) so
        staffing decisions are based on live workers.
        """
        # Drop stale references: only if the labor market exposes a worker registry.
        registered_workers = getattr(labor_market, "registered_workers", None)
        if self.employees and isinstance(registered_workers, list):
            live_set = set(registered_workers)
            stale = [e for e in self.employees if e not in live_set]
            if stale:
                for e in stale:
                    labor_market.release_worker(e)
                self.employees = [e for e in self.employees if e in live_set]

        employee_capacity_ratio: float = self.config.company.employee_capacity_ratio
        required_employees: int = int(self.production_capacity / employee_capacity_ratio)
        current_count = len(self.employees)

        if required_employees > current_count:
            open_positions = required_employees - current_count
            unadvertised = max(0, open_positions - self.pending_hires)
            if unadvertised > 0:
                new_positions = min(unadvertised, self.max_employees - current_count)
                if new_positions > 0:
                    self.pending_hires += new_positions
                    labor_market.register_job_offer(
                        self,
                        wage=getattr(
                            labor_market,
                            "default_wage",
                            self.config.company.base_wage,
                        ),
                        positions=new_positions,
                    )
                    log(
                        f"Company {self.unique_id} requested {new_positions} workers via labor market.",
                        level="DEBUG",
                    )
        elif required_employees < current_count:
            to_release = current_count - required_employees
            for _ in range(to_release):
                if self.employees:
                    employee = self.employees.pop()
                    # Use labor market helper to keep worker state consistent.
                    labor_market.release_worker(employee)
                    log(
                        f"Company {self.unique_id} released worker {employee.unique_id}.",
                        level="DEBUG",
                    )

    def get_unit_price(self) -> float:
        """Producer wholesale price per unit, responsive to inventory levels.

        Base price reflects production cost (Selbstkosten + innovation bonus).
        The price adjusts up/down based on inventory relative to demand:
        - High inventory → price drops (oversupply pressure)
        - Low inventory → price rises (scarcity premium)

        Book ref: "Freier Wettbewerb [muss] dafür sorgen, dass die Preise
        auf die Herstellungskosten sinken" (line 1620).
        "Sinken die Preise unter die Herstellungskosten, müssen Betriebe
        Konkurs anmelden" (line 1462).
        """
        base_price = self.config.company.production_base_price
        bonus_rate = self.config.company.production_innovation_bonus_rate
        cost_price = float(base_price * (1 + bonus_rate * self.innovation_index))

        # --- Inventory-responsive price adjustment ---
        avg_sales = self._avg_daily_sales()
        target_days = self.config.company.production_target_stock_days
        floor = self.config.company.price_inventory_floor
        ceiling = self.config.company.price_inventory_ceiling
        sensitivity = self.config.company.price_inventory_sensitivity

        if avg_sales <= 0 or target_days <= 0:
            # No demand signal yet → sell at cost
            return cost_price

        target_inventory = avg_sales * target_days
        if target_inventory <= 0:
            return cost_price

        # ratio > 1 means overstocked, < 1 means understocked
        inventory_ratio = self.finished_goods_units / target_inventory

        # Map ratio to price multiplier:
        # ratio=0 → ceiling (scarce), ratio=1 → 1.0 (balanced), ratio=2+ → floor (oversupply)
        if inventory_ratio <= 1.0:
            # Understocked: interpolate from 1.0 up to ceiling
            t = max(0.0, 1.0 - inventory_ratio) ** sensitivity
            price_factor = 1.0 + (ceiling - 1.0) * t
        else:
            # Overstocked: interpolate from 1.0 down to floor
            excess = min(inventory_ratio - 1.0, 1.0)  # cap at 2x target
            t = excess**sensitivity
            price_factor = 1.0 - (1.0 - floor) * t

        return cost_price * max(floor, min(ceiling, price_factor))

    def sell_to_retailer(self, desired_quantity: float) -> tuple[float, float]:
        """Deliver goods to a retailer (goods flow only).

        Returns (sold_quantity, sold_value).

        IMPORTANT: This method does not touch balances. Money emission
        happens in WarengeldBank.finance_goods_purchase.
        """
        if desired_quantity <= 0 or self.finished_goods_units <= 0:
            return 0.0, 0.0
        qty = min(self.finished_goods_units, desired_quantity)
        unit_price = self.get_unit_price()
        value = qty * unit_price
        self.finished_goods_units -= qty
        # Track sales for demand-responsive production
        self._step_sales += qty
        return float(qty), float(value)

    def sell_service_to_household(self, household: Household, budget: float) -> float:
        """Sell services to a household (money-neutral transfer, no inventory).

        Referenz: doc/issues.md Abschnitt 6) Prompt-Meilensteine -> M3 und
        Abschnitt 5) "Dienstleistungs-Wertschöpfung ...".

        Contract:
        - No inventory changes
        - No money creation: only a transfer between sight balances
        - Service transaction volume is tracked via `self.service_sales_total`
        """

        if budget <= 0:
            return 0.0

        paid = float(household.pay(float(budget)))
        if paid <= 0:
            return 0.0

        self.sight_balance += paid
        self.service_sales_total += paid

        log(
            "event=service_tx "
            f"payer={household.unique_id} provider={self.unique_id} amount={paid:.2f}",
            level="INFO",
        )
        return paid

    def sell_goods(self, demand: float | None = None) -> float:
        """LEGACY: Producer selling directly to a generic market.

        This bypasses the Warengeld goods cycle (Retailer + Kontokorrent financing)
        and is kept only for legacy tests/experiments.
        """
        raise RuntimeError(
            "Company.sell_goods() is legacy and not supported in the Warengeld simulation. "
            "Route goods via RetailerAgent.restock_goods() and WarengeldBank.finance_goods_purchase()."
        )

    def sell_to_household(self, household: Household, budget: float) -> float:
        """LEGACY: Direct producer-to-household sale.

        In the Warengeld model, households buy goods from retailers; producers sell
        to retailers (goods flow) and receive money only via retailer financing.
        """
        raise RuntimeError(
            "Company.sell_to_household() is legacy and not supported in the Warengeld simulation. "
            "Households must buy from RetailerAgent.sell_to_household()."
        )

    def pay_wages(self, wage_rate: float | None = None) -> float:
        """
        Pay wages to all employees.

        Args:
            wage_rate: Optional override for per-employee wage

        Returns:
            Total wages paid
        """
        if not self.employees:
            log(f"Company {self.unique_id} has no employees to pay wages.", level="DEBUG")
            return 0.0

        # Compute planned wage bill
        planned_wage_bill: float = 0.0
        wage_by_employee: list[tuple[object, float]] = []
        for employee in self.employees:
            negotiated = getattr(employee, "current_wage", None)
            rate = negotiated if negotiated is not None else wage_rate
            if rate is None:
                rate = self.config.labor_market.starting_wage
            rate = float(max(0.0, rate))
            planned_wage_bill += rate
            wage_by_employee.append((employee, rate))

        if planned_wage_bill <= 0:
            return 0.0

        # Warengeld rule: no overdraft on producers. Pay only what is available.
        buffer = float(self.config.company.min_working_capital_buffer)
        available = max(0.0, self.sight_balance - buffer)
        if available <= 0.0:
            log(
                f"Company {self.unique_id} cannot pay wages (balance {self.sight_balance:.2f}, buffer {buffer:.2f}).",
                level="DEBUG",
            )
            return 0.0

        pay_ratio = 1.0
        if planned_wage_bill > available:
            pay_ratio = available / planned_wage_bill
            log(
                f"Company {self.unique_id}: wage bill {planned_wage_bill:.2f} exceeds available {available:.2f}; "
                f"paying pro-rata at {pay_ratio:.2%}.",
                level="INFO",
            )

        total_paid: float = 0.0
        for employee, rate in wage_by_employee:
            paid = rate * pay_ratio
            if paid <= 0:
                continue
            # Transfer: caller must have reduced company balance.
            employee.receive_income(paid)  # type: ignore[attr-defined]
            total_paid += paid

        self.sight_balance -= total_paid

        # --- Track sustained underpayment for enhanced insolvency ---
        # Book ref: "Sinken die Preise unter die Herstellungskosten, müssen
        # Betriebe Konkurs anmelden" (line 1462).
        # A company that repeatedly cannot pay full wages is economically
        # non-viable and should eventually exit the simulation.
        if pay_ratio < 1.0 and self.employees:
            self._consecutive_underpaid_steps += 1
        else:
            self._consecutive_underpaid_steps = 0

        log(
            f"Company {self.unique_id} paid wages totaling {total_paid:.2f}. New balance: {self.sight_balance:.2f}.",
            level="INFO",
        )

        return total_paid

    def distribute_profits(self) -> float:
        """Distribute surplus profits to employees (Gewinnausschüttung).

        In the Warengeld cooperative model, workers ARE the company.
        Surplus retained earnings — i.e. the difference between revenue
        received from retailer restocking and costs (wages, holding costs,
        etc.) — must flow back to employees to close the monetary circular
        flow.  Without this mechanism, companies become a permanent money
        sink that starves the economy of purchasing power.

        Book ref: The Warengeld system has no absentee ownership or
        dividends to shareholders.  The productive surplus belongs to
        the workers who created it.

        Returns:
            Total profit distributed to employees.
        """
        if not self.config.company.profit_distribution_enabled:
            return 0.0
        if not self.employees:
            return 0.0

        buffer = self.config.company.profit_retention_buffer
        excess = max(0.0, self.sight_balance - buffer)
        if excess <= 0.0:
            return 0.0

        fraction = self.config.company.profit_distribution_fraction
        distributable = excess * fraction
        if distributable <= 0.0:
            return 0.0

        per_employee = distributable / len(self.employees)
        total_distributed = 0.0
        for employee in self.employees:
            employee.receive_income(per_employee)  # type: ignore[attr-defined]
            total_distributed += per_employee

        self.sight_balance -= total_distributed

        log(
            f"Company {self.unique_id} distributed profits {total_distributed:.2f} "
            f"({per_employee:.2f}/employee, {len(self.employees)} employees). "
            f"Remaining balance: {self.sight_balance:.2f}.",
            level="INFO",
        )
        return total_distributed

    def request_funds_from_bank(self, amount: float) -> float:
        """
        Request financing from a bank.

        Args:
            amount: Amount of funds to request

        Returns:
            Amount received
        """
        log(f"Company {self.unique_id} requests funds: {amount:.2f}.", level="INFO")

        self.sight_balance += amount

        log(
            f"Company {self.unique_id} received funds: {amount:.2f}. "
            f"New balance: {self.sight_balance:.2f}.",
            level="INFO",
        )

        return amount

    # --- Sparkasse investment credit (deterministic path) ---
    def request_sparkasse_investment_loan(self, savings_bank: SavingsBank) -> float:
        """Request an investment loan from the SavingsBank and convert it into capacity.

        Deterministic minimal policy (see doc/issues.md Abschnitt 6 -> M2 and Abschnitt 5 ->
        "Firmen sollen bei der Sparkasse Geld leihen..."):
        - Trigger: company is considered *under-capitalized* if `sight_balance` is below
          `config.company.investment_threshold`.
        - Desired principal: the gap to the threshold.
        - Eligibility cap: outstanding principal may not exceed
          `production_capacity * sparkasse_investment_loan_max_to_capacity`.
        - Bank cap: cannot exceed `savings_bank.available_funds`.

        Investment mapping (deterministic):
        - Each `investment_capital_cost_per_capacity` currency increases
          `production_capacity` by +1.

        Notes:
        - This path does **not** create money: it transfers from the SavingsBank's
          available funds stock into the company's sight balance.
        - Repayment is modeled via `repay_sparkasse_investment_loan()`.
        """

        if savings_bank is None:
            return 0.0

        threshold = float(self.config.company.investment_threshold)
        if float(self.sight_balance) >= threshold:
            return 0.0

        desired_principal = max(0.0, threshold - float(self.sight_balance))
        if desired_principal <= 0.0:
            return 0.0

        outstanding = float(savings_bank.active_loans.get(self.unique_id, 0.0))
        max_ratio = float(self.config.company.sparkasse_investment_loan_max_to_capacity)
        max_total_principal = max(0.0, float(self.production_capacity) * max_ratio)
        room = max(0.0, max_total_principal - outstanding)
        if room <= 0.0:
            return 0.0

        request_amount = min(desired_principal, room)
        if request_amount <= 0.0:
            return 0.0

        cap_before = float(self.production_capacity)
        granted = float(savings_bank.allocate_credit(self, request_amount))
        if granted <= 0.0:
            return 0.0

        capital_cost = float(self.config.company.investment_capital_cost_per_capacity)
        capacity_increase = granted / capital_cost
        self.production_capacity += capacity_increase

        log(
            "event=sparkasse_investment_loan_granted "
            f"borrower={self.unique_id} principal={granted:.2f} "
            f"capacity_before={cap_before:.2f} capacity_after={self.production_capacity:.2f}",
            level="INFO",
        )

        return granted

    def repay_sparkasse_investment_loan(self, savings_bank: SavingsBank | None) -> float:
        """Deterministically repay part of outstanding Sparkasse investment loans.

        Rule: pay a fixed share of the available cash buffer per step.
        This intentionally stays deterministic and simple for unit tests.
        """

        if savings_bank is None:
            return 0.0

        outstanding = float(savings_bank.active_loans.get(self.unique_id, 0.0))
        if outstanding <= 0.0:
            return 0.0

        buffer = float(self.config.company.min_working_capital_buffer)
        available = max(0.0, float(self.sight_balance) - buffer)
        if available <= 0.0:
            return 0.0

        repay_rate = float(self.config.company.sparkasse_investment_loan_repayment_rate)
        repay_budget = max(0.0, available * repay_rate)
        if repay_budget <= 0.0:
            return 0.0

        paid = float(savings_bank.receive_loan_repayment(self, repay_budget))
        if paid > 0:
            log(
                "event=sparkasse_investment_loan_repaid "
                f"borrower={self.unique_id} amount={paid:.2f} remaining={savings_bank.active_loans.get(self.unique_id, 0.0):.2f}",
                level="INFO",
            )
        return paid

    def split_company(self, labor_market: LaborMarket | None = None) -> "Company":
        """
        Split company into two, creating a new spinoff company.

        The new company receives 50% of the parent's balance
        and similar attributes. The parent resets its growth state.

        Args:
            labor_market: Optional labor market to register the new company's job offers

        Returns:
            Newly created spinoff company
        """
        # Split assets for new company
        split_ratio: float = self.config.company.split_ratio
        split_balance: float = self.sight_balance * split_ratio
        self.sight_balance -= split_balance

        # Generate new company ID using lineage-wide counter
        new_unique_id = self.generate_next_id()
        new_generation: int = self.generation + 1

        # Create new company
        new_company = Company(
            new_unique_id,
            production_capacity=self.production_capacity,
            land_area=self.land_area,
            environmental_impact=self.environmental_impact,
            max_employees=self.max_employees,
            config=self.config,
            labor_market=labor_market,
        )

        new_company.sight_balance = split_balance
        new_company.generation = new_generation

        log(
            f"New company {new_unique_id} (Generation {new_generation}) founded with "
            f"balance: {split_balance:.2f}.",
            level="INFO",
        )

        # Reset growth phase of parent company
        self.growth_phase = False
        self.growth_counter = 0

        return new_company

    def check_bankruptcy(self) -> bool:
        """Check if company is bankrupt.

        Triggers on either:
        1. Balance below threshold (acute insolvency), or
        2. Sustained inability to pay full wages (chronic non-viability).

        Book ref: "Sinken die Preise unter die Herstellungskosten, müssen
        Betriebe Konkurs anmelden" (line 1462).

        Returns:
            True if company is bankrupt, False otherwise
        """
        if self.sight_balance < self.bankruptcy_threshold:
            log(
                f"Company {self.unique_id} declared bankrupt with "
                f"balance {self.sight_balance:.2f}.",
                level="WARNING",
            )
            return True

        # Enhanced: sustained underpayment → chronic insolvency
        underpay_limit = self.config.company.bankruptcy_underpay_steps
        if self._consecutive_underpaid_steps >= underpay_limit:
            log(
                f"Company {self.unique_id} declared bankrupt after "
                f"{self._consecutive_underpaid_steps} consecutive steps of underpaying wages.",
                level="WARNING",
            )
            return True

        return False

    def _handle_rd_cycle(self) -> None:
        """Process the invest -> innovate cycle."""
        self.invest_in_rd()
        self.innovate()

    def _sync_labor_market(self, state: State | None) -> None:
        """Ensure the company interacts with the labor market if available."""
        if state and state.labor_market:
            self.adjust_employees(state.labor_market)
            return
        log(
            f"Company {self.unique_id} cannot interact with labor market: unavailable.",
            level="WARNING",
        )

    def _run_operations(self) -> None:
        """Produce goods (if staffed), depreciate inventory, pay wages, distribute profits."""
        if self.employees:
            self.produce()
        self.depreciate_inventory()
        self.pay_wages()
        self.distribute_profits()

    def _trigger_growth_and_investment(self, savings_bank: SavingsBank | None) -> None:
        """Toggle growth mode and request long-term financing if conditions are met."""
        if not self.growth_phase and self.sight_balance >= self.investment_threshold:
            self.growth_phase = True
            log(f"Company {self.unique_id} enters growth phase.", level="INFO")

            if savings_bank is not None:
                investment_factor = self.config.company.growth_investment_factor
                invest_amount = self.production_capacity * investment_factor
                if invest_amount > 0:
                    granted = savings_bank.allocate_credit(self, invest_amount)
                    if granted > 0:
                        log(
                            f"Company {self.unique_id} received investment credit {granted:.2f} "
                            f"from SavingsBank for growth.",
                            level="INFO",
                        )
                    else:
                        log(
                            f"Company {self.unique_id} could not secure investment credit of "
                            f"{invest_amount:.2f} from SavingsBank.",
                            level="WARNING",
                        )

        if self.growth_phase:
            self.growth_counter += 1

    def _handle_company_split(self, labor_market: LaborMarket | None) -> "Company | None":
        """Split the company if growth thresholds are satisfied."""
        if self.growth_phase and self.growth_counter >= self.growth_threshold:
            return self.split_company(labor_market)
        return None

    def _should_liquidate_due_to_staffing(self) -> bool:
        if not self.config.company.zero_staff_auto_liquidation:
            return False
        grace = self.config.company.zero_staff_grace_steps
        return self._zero_staff_steps >= grace

    def _handle_zero_staff_counter(self) -> None:
        if self.employees:
            self._zero_staff_steps = 0
            return
        self._zero_staff_steps += 1

    def _liquidate_due_to_staff_loss(self, state: State | None) -> Literal["LIQUIDATED"]:
        log(
            f"Company {self.unique_id} forcibly liquidated after {self._zero_staff_steps} steps without employees.",
            level="WARNING",
        )
        # Release any remaining employees back to the labor market.
        if state and getattr(state, "labor_market", None):
            for e in list(self.employees):
                state.labor_market.release_worker(e)
            self.employees = []
            self.pending_hires = 0

        payout_share = self.config.company.zero_staff_liquidation_state_share
        payout = max(0.0, self.sight_balance * payout_share)
        if payout > 0 and state is not None:
            state.tax_revenue += payout
        self.sight_balance = 0.0
        return "LIQUIDATED"

    def step(
        self,
        current_step: int,
        state: State | None = None,
        savings_bank: SavingsBank | None = None,
        # labor_market: LaborMarket | None = None,
    ) -> "Company | None":
        """
        Execute one simulation step for the company.

        During each step, the company:
        1. Handles R&D and innovation
        2. Manages workforce and staffing
        3. Runs core business operations (produce, sell, pay wages)
        4. Manages growth and investment
        5. Handles company lifecycle events (splits, bankruptcy)

        Args:
            current_step: Current simulation step number
            state: State agent providing regulation and markets
            savings_bank: Savings bank for long-term financing

        Returns:
            - Company: New company instance if split occurred
            - "DEAD": If company went bankrupt
            - "LIQUIDATED": If company was liquidated due to staffing issues
            - None: Normal completion
        """
        self._log_step_start(current_step)

        # Phase 1: Innovation & R&D
        self._handle_rd_cycle()

        # Phase 3: Workforce Management
        self._handle_zero_staff_counter()
        if self._should_liquidate_due_to_staffing():
            return self._liquidate_due_to_staff_loss(state)
        self._sync_labor_market(state)

        # Phase 4: Core Business Operations
        self._run_operations()

        # Phase 5: Growth & Investment
        self._trigger_growth_and_investment(savings_bank)

        # Phase 6: Lifecycle Events
        lifecycle_result = self._handle_lifecycle_events(state)
        if lifecycle_result is not None:
            return lifecycle_result

        self._log_step_completion(current_step)
        return None

    def _log_step_start(self, current_step: int) -> None:
        """Log the start of a company step."""
        self.log_metric("step_start", current_step)
        log(f"Company {self.unique_id} starting step {current_step}.", level="DEBUG")

    def _log_step_completion(self, current_step: int) -> None:
        """Log the completion of a company step."""
        self.log_metric("step_completion", current_step)
        log(f"Company {self.unique_id} completed step {current_step}.", level="DEBUG")

    def _handle_lifecycle_events(self, state: State | None) -> "Company | None":
        """Handle company lifecycle events (bankruptcy, splits)."""
        lm = state.labor_market if state and hasattr(state, "labor_market") else None

        new_company = self._handle_company_split(lm)
        if new_company is not None:
            # `split_company()` already registers initial job offers when a labor market
            # is provided, so we simply return the spinoff.
            return new_company

        if self.check_bankruptcy():
            # Release employees back into the labor market so they can be re-matched.
            if lm is not None:
                for e in list(self.employees):
                    lm.release_worker(e)
            self.employees = []
            self.pending_hires = 0

            log(
                f"Company {self.unique_id} is removed from simulation due to bankruptcy.",
                level="WARNING",
            )
            return "DEAD"

        return None

    def produce_output(self) -> None:
        """Deprecated wrapper maintained for compatibility."""
        self.produce()
