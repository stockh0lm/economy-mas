# company_agent.py
import random
from typing import TypeAlias, Literal, Optional, cast

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

    def produce(self, labor_market: LaborMarket) -> float:
        """
        Produce goods based on capacity and available workforce.

        Args:
            labor_market: Labor market for hiring/firing employees

        Returns:
            Amount of goods produced
        """
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

        self.adjust_employees(labor_market)
        return actual_production

    def adjust_employees(self, labor_market: LaborMarket) -> None:
        """
        Adjust employee count based on production capacity.

        Args:
            labor_market: Labor market for hiring/firing employees
        """
        employee_capacity_ratio: float = CONFIG.get("employee_capacity_ratio", 10.0)
        required_employees: int = int(self.production_capacity / employee_capacity_ratio)

        if required_employees > len(self.employees):
            self.hire_employees(required_employees - len(self.employees), labor_market)
        elif required_employees < len(self.employees):
            self.fire_employees(len(self.employees) - required_employees)

    def hire_employees(self, number: int, labor_market: LaborMarket) -> None:
        """
        Hire employees from labor market.

        Args:
            number: Number of employees to hire
            labor_market: Labor market to hire from
        """
        for _ in range(number):
            if len(self.employees) < self.max_employees:
                available_workers = [
                    worker for worker in labor_market.registered_workers
                    if not hasattr(worker, 'employed') or not worker.employed
                ]

                if available_workers:
                    new_employee = cast(Employee, available_workers.pop(0))
                    new_employee.employed = True  # type: ignore
                    self.employees.append(new_employee)

                    log(
                        f"Company {self.unique_id} hired a new employee. "
                        f"Total employees: {len(self.employees)}.",
                        level="INFO"
                    )

    def fire_employees(self, number: int) -> None:
        """
        Fire employees due to downsizing.

        Args:
            number: Number of employees to fire
        """
        for _ in range(number):
            if self.employees:
                employee = self.employees.pop()
                employee.employed = False  # type: ignore

                log(
                    f"Company {self.unique_id} fired an employee. "
                    f"Total employees: {len(self.employees)}.",
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

        total_wages: float = actual_wage_rate * len(self.employees)
        self.balance -= total_wages

        for employee in self.employees:
            employee.receive_income()

        log(
            f"Company {self.unique_id} paid wages totaling {total_wages:.2f}. "
            f"New balance: {self.balance:.2f}.",
            level="INFO"
        )

        return total_wages

    def pay_taxes(self, state: State) -> float:
        """
        Pay land and environmental taxes to the state.

        Args:
            state: State agent collecting taxes

        Returns:
            Total taxes paid
        """
        bodensteuer_rate: float = CONFIG.get("tax_rates", {}).get("bodensteuer", 0.05)
        umweltsteuer_rate: float = CONFIG.get("tax_rates", {}).get("umweltsteuer", 0.02)

        land_tax: float = self.land_area * bodensteuer_rate
        env_tax: float = self.environmental_impact * umweltsteuer_rate
        tax_due: float = land_tax + env_tax

        self.balance -= tax_due

        log(
            f"Company {self.unique_id} paid taxes: {tax_due:.2f} "
            f"(Land: {land_tax:.2f}, Env: {env_tax:.2f}). "
            f"New balance: {self.balance:.2f}.",
            level="INFO"
        )

        return tax_due

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
            self.produce(state.labor_market)
        else:
            log(f"Company {self.unique_id} cannot produce: no labor market available.", level="WARNING")

        # Sales and finances
        self.sell_goods()
        self.pay_wages()

        if state:
            self.pay_taxes(state)

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