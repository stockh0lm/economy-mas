# company_agent.py
import random
from typing import TypeAlias, Literal, Optional

from .economic_agent import EconomicAgent
from logger import log
from config import CONFIG
from .household_agent import Household
from .labor_market import LaborMarket
from .state_agent import State


# Type aliases for improved readability
CompanyResult: TypeAlias = Optional["Company"] | Literal["DEAD"]
Employee: TypeAlias = Household  # Type of employees (currently Household)


class Company(EconomicAgent):
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
        employees: list[Employee] | None = None
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
        """
        super().__init__(unique_id)

        # Basic attributes
        self.generation: int = 0
        self.production_capacity: float = production_capacity
        self.resource_usage: float = resource_usage
        self.land_area: float = land_area
        self.environmental_impact: float = environmental_impact

        # Employee management
        self.max_employees: int = max_employees
        self.employees: list[Employee] = employees if employees is not None else []
        self.pending_hires: int = 0

        # Financial attributes
        self.inventory: float = 0.0
        self.balance: float = 0.0

        # Growth parameters
        self.growth_phase: bool = False
        self.growth_counter: int = 0
        self.growth_threshold: int = CONFIG.get("growth_threshold", 5)
        self.growth_balance_trigger: float = CONFIG.get("growth_balance_trigger", 1000)
        self.bankruptcy_threshold: float = CONFIG.get("bankruptcy_threshold", -100)

        # Research and development
        self.rd_investment: float = 0.0
        self.innovation_index: float = 0.0

    def invest_in_rd(self) -> None:
        """
        Invest in research and development if balance exceeds threshold.

        A percentage of excess balance is allocated to R&D investment.
        """
        rd_trigger: float = CONFIG.get("rd_investment_trigger_balance", 200)
        rd_rate: float = CONFIG.get("rd_investment_rate", 0.1)

        if self.balance > rd_trigger:
            investment: float = (self.balance - rd_trigger) * rd_rate
            self.balance -= investment
            self.rd_investment += investment

            log(
                f"Company {self.unique_id} invested {investment:.2f} in R&D. "
                f"Total R&D investment: {self.rd_investment:.2f}.",
                level="INFO"
            )

    def innovate(self) -> None:
        """
        Attempt innovation based on R&D investment.

        If successful, production capacity increases and innovation index rises.
        """
        # Probability of innovation success increases with R&D investment
        probability: float = min(self.rd_investment / 1000, 0.5)
        innovation_bonus_rate: float = CONFIG.get("innovation_production_bonus", 0.1)
        rd_decay_factor: float = CONFIG.get("rd_investment_decay_factor", 0.5)

        if random.random() < probability:
            bonus: float = self.production_capacity * innovation_bonus_rate
            self.production_capacity += bonus
            self.innovation_index += 1

            log(
                f"Company {self.unique_id} innovated successfully! "
                f"Production capacity increased by {bonus:.2f} to {self.production_capacity:.2f}. "
                f"Innovation index: {self.innovation_index}.",
                level="INFO"
            )

            # Reduce R&D investment after successful innovation
            self.rd_investment *= rd_decay_factor

    def produce(self) -> float:
        """Produce goods based on capacity and available workforce."""
        if self.max_employees == 0:
            actual_production: float = 0.0
        else:
            efficiency: float = len(self.employees) / self.max_employees
            actual_production: float = self.production_capacity * efficiency

        self.inventory += actual_production

        log(
            f"Company {self.unique_id} produced {actual_production:.2f} units. "
            f"Total inventory: {self.inventory:.2f}.",
            level="INFO"
        )

        return actual_production

    def add_employee_from_labor_market(self, worker: Employee, wage: float) -> None:
        """Receive a worker assignment from the labor market."""
        worker.employed = True  # type: ignore[attr-defined]
        worker.current_wage = wage  # type: ignore[attr-defined]
        self.employees.append(worker)
        if self.pending_hires > 0:
            self.pending_hires -= 1
        log(
            f"Company {self.unique_id} accepted worker {worker.unique_id} at wage {wage:.2f}. "
            f"Total employees: {len(self.employees)}.",
            level="INFO"
        )

    def adjust_employees(self, labor_market: LaborMarket) -> None:
        """Advertise labor demand and release surplus employees via labor market."""
        employee_capacity_ratio: float = CONFIG.get("employee_capacity_ratio", 10.0)
        required_employees: int = int(self.production_capacity / employee_capacity_ratio)
        current_count = len(self.employees)

        if required_employees > current_count:
            new_positions = min(required_employees - current_count, self.max_employees - current_count)
            if new_positions > 0:
                self.pending_hires += new_positions
                labor_market.register_job_offer(
                    self,
                    wage=CONFIG.get("wage_rate", CONFIG.get("default_wage", 10.0)),
                    positions=new_positions
                )
                log(
                    f"Company {self.unique_id} requested {new_positions} workers via labor market.",
                    level="INFO"
                )
        elif required_employees < current_count:
            to_release = current_count - required_employees
            for _ in range(to_release):
                if self.employees:
                    employee = self.employees.pop()
                    labor_market.release_worker(employee)
                    log(
                        f"Company {self.unique_id} released worker {employee.unique_id}.",
                        level="INFO"
                    )

    def sell_goods(self, demand: float | None = None) -> float:
        """
        Sell goods from inventory based on market demand.

        Args:
            demand: Market demand for goods

        Returns:
            Revenue from sales
        """
        actual_demand: float = demand if demand is not None else CONFIG.get("demand_default", 50)
        sold_quantity: float = min(self.inventory, actual_demand)
        base_price: float = CONFIG.get("production_base_price", 10)
        innovation_bonus_rate: float = CONFIG.get("production_innovation_bonus_rate", 0.02)

        # Calculate price with innovation bonus
        sale_price_per_unit: float = base_price * (1 + innovation_bonus_rate * self.innovation_index)
        revenue: float = sold_quantity * sale_price_per_unit

        self.balance += revenue
        self.inventory -= sold_quantity

        log(
            f"Company {self.unique_id} sold {sold_quantity:.2f} units at {sale_price_per_unit:.2f} each "
            f"for {revenue:.2f}. New balance: {self.balance:.2f}. Inventory left: {self.inventory:.2f}.",
            level="INFO"
        )

        return revenue

    def pay_wages(self, wage_rate: float | None = None) -> float:
        """
        Pay wages to all employees.

        Args:
            wage_rate: Amount to pay each employee

        Returns:
            Total wages paid
        """
        actual_wage_rate: float = wage_rate if wage_rate is not None else CONFIG.get("wage_rate", 5)

        if not self.employees:
            log(f"Company {self.unique_id} has no employees to pay wages.", level="WARNING")
            return 0.0

        total_wages: float = 0.0
        for employee in self.employees:
            rate = wage_rate if wage_rate is not None else getattr(employee, "current_wage", CONFIG.get("default_wage", 5))
            total_wages += rate
            employee.receive_income(rate)

        self.balance -= total_wages

        log(
            f"Company {self.unique_id} paid wages totaling {total_wages:.2f}. "
            f"New balance: {self.balance:.2f}.",
            level="INFO"
        )

        return total_wages

    def request_funds_from_bank(self, amount: float) -> float:
        """
        Request financing from a bank.

        Args:
            amount: Amount of funds to request

        Returns:
            Amount received
        """
        log(f"Company {self.unique_id} requests funds: {amount:.2f}.", level="INFO")

        self.balance += amount

        log(
            f"Company {self.unique_id} received funds: {amount:.2f}. "
            f"New balance: {self.balance:.2f}.",
            level="INFO"
        )

        return amount

    def split_company(self) -> "Company":
        """
        Split company into two, creating a new spinoff company.

        The new company receives 50% of the parent's balance
        and similar attributes. The parent resets its growth state.

        Returns:
            Newly created spinoff company
        """
        # Split assets for new company
        split_ratio: float = CONFIG.get("company_split_ratio", 0.5)
        split_balance: float = self.balance * split_ratio
        self.balance -= split_balance

        # Generate new company ID with generation suffix
        base_id: str = self.unique_id.split("_g")[0]
        new_generation: int = self.generation + 1
        new_unique_id: str = f"{base_id}_g{new_generation}"

        # Create new company
        new_company = Company(
            new_unique_id,
            production_capacity=self.production_capacity,
            land_area=self.land_area,
            environmental_impact=self.environmental_impact,
            max_employees=self.max_employees
        )

        new_company.balance = split_balance
        new_company.generation = new_generation

        log(
            f"New company {new_unique_id} (Generation {new_generation}) founded with "
            f"balance: {split_balance:.2f}.",
            level="INFO"
        )

        # Reset growth phase of parent company
        self.growth_phase = False
        self.growth_counter = 0

        return new_company

    def check_bankruptcy(self) -> bool:
        """
        Check if company is bankrupt based on balance threshold.

        Returns:
            True if company is bankrupt, False otherwise
        """
        if self.balance < self.bankruptcy_threshold:
            log(
                f"Company {self.unique_id} declared bankrupt with "
                f"balance {self.balance:.2f}.",
                level="WARNING"
            )
            return True
        return False

    def step(self, current_step: int, state: Optional[State] = None) -> CompanyResult:
        """
        Execute one simulation step for the company.

        During each step, the company:
        1. Invests in R&D
        2. Attempts innovation
        3. Produces goods
        4. Sells goods
        5. Pays wages
        6. Pays taxes
        7. May enter growth phase based on balance
        8. May split if growth conditions are met
        9. May go bankrupt if balance is too low

        Args:
            current_step: Current simulation step number
            state: State agent providing regulation and markets

        Returns:
            - "DEAD" if company is bankrupt
            - New Company instance if split occurred
            - None otherwise
        """
        log(f"Company {self.unique_id} starting step {current_step}.", level="INFO")

        # Investment and production
        self.invest_in_rd()
        self.innovate()

        if state and state.labor_market:
            self.adjust_employees(state.labor_market)
        else:
            log(f"Company {self.unique_id} cannot interact with labor market: unavailable.", level="WARNING")

        # Sales and finances
        if self.employees:
            self.produce()
        self.sell_goods()
        self.pay_wages()

        # Growth phase check
        if not self.growth_phase and self.balance >= self.growth_balance_trigger:
            self.growth_phase = True
            log(f"Company {self.unique_id} enters growth phase.", level="INFO")

        if self.growth_phase:
            self.growth_counter += 1

        # Company splitting if growth threshold reached
        new_company: Optional[Company] = None
        if self.growth_phase and self.growth_counter >= self.growth_threshold:
            new_company = self.split_company()

        # Bankruptcy check
        if self.check_bankruptcy():
            log(f"Company {self.unique_id} is removed from simulation due to bankruptcy.", level="WARNING")
            return "DEAD"

        log(f"Company {self.unique_id} completed step {current_step}.", level="INFO")
        return new_company

    def produce_output(self) -> None:
        """Deprecated wrapper maintained for compatibility."""
        self.produce()
