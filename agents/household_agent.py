# household_agent.py
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Literal, Optional

from config import CONFIG_MODEL, SimulationConfig
from logger import log

from .economic_agent import EconomicAgent
from .savings_bank_agent import SavingsBank

if TYPE_CHECKING:
    from agents.company_agent import Company


class Household(EconomicAgent):
    """
    Represents a household economic agent in the simulation.

    Households earn income, consume goods, save money, and can eventually
    split to create new households when certain growth conditions are met.
    """

    def __init__(
        self,
        unique_id: str,
        income: float = 100.0,
        land_area: float = 50.0,
        environmental_impact: float = 1.0,
        generation: int = 1,
        config: SimulationConfig | None = None,
    ) -> None:
        """
        Initialize a household agent with economic attributes.

        Args:
            unique_id: Unique identifier for the household
            income: Regular income from work or transfers
            land_area: Living or usage area (for land tax calculation)
            environment_impact: Ecological footprint factor
            generation: Current generation of the household
        """
        super().__init__(unique_id)

        self.config: SimulationConfig = config or CONFIG_MODEL

        self.income: float = income
        self.land_area: float = land_area
        self.environmental_impact: float = environmental_impact
        self.generation: int = generation

        # Growth phase parameters
        self.growth_phase: bool = False
        self.growth_counter: int = 0
        self.growth_threshold: int = self.config.growth_threshold
        self.savings_growth_trigger: float = self.config.savings_growth_trigger

        # Age and generation tracking
        self.age: int = 0
        self.max_age: int = self.config.max_age
        self.max_generation: int = self.config.max_generation

        # Bank accounts
        self.checking_account: float = 0.0
        self.savings: float = 0.0

        self.consumption_rate_normal: float = self._resolve_consumption_rate(
            self.config.household_consumption_rate_normal
        )
        self.consumption_rate_growth: float = self._resolve_consumption_rate(
            self.config.household_consumption_rate_growth
        )

        # Child rearing and loan parameters
        self.child_rearing_cost: float = self.config.child_rearing_cost
        self.loan_repayment_rate: float = self.config.household_loan_repayment_rate

    def _resolve_consumption_rate(self, value: float) -> float:
        if not isinstance(value, (int, float)):
            log(
                f"Household {self.unique_id} uses default consumption rate due to non-numeric value.",
                level="WARNING",
            )
            return 0.0

        rate = float(value)
        if 0.0 <= rate <= 1.0:
            return rate

        clamped = max(0.0, min(1.0, rate))
        log(
            f"Household {self.unique_id} clamps consumption rate from {rate} to {clamped}.",
            level="WARNING",
        )
        return clamped

    @property
    def balance(self) -> float:
        """Expose combined deposits so external entities see realistic holdings."""
        checking = getattr(self, "checking_account", 0.0)
        savings = getattr(self, "savings", 0.0)
        return checking + savings

    @balance.setter
    def balance(self, value: float) -> None:
        """Ensure direct writes reduce checking first, then savings, or top up checking."""
        checking = getattr(self, "checking_account", 0.0)
        savings = getattr(self, "savings", 0.0)
        delta = value - (checking + savings)

        if delta >= 0:
            self.checking_account = checking + delta
            self.savings = savings
            return

        remaining = -delta
        draw = min(checking, remaining)
        checking -= draw
        remaining -= draw

        if remaining > 0:
            savings -= remaining

        self.checking_account = checking
        self.savings = savings

    def receive_income(self, amount: float | None = None) -> float:
        """Credit incoming funds to the checking account."""
        credited_amount: float = self.income if amount is None else amount
        self.checking_account += credited_amount
        log(
            f"Household {self.unique_id} received income: {credited_amount:.2f}. "
            f"Checking account now: {self.checking_account:.2f}.",
            level="INFO",
        )
        return credited_amount

    def pay_taxes(self, state: object) -> None:
        """
        Pay taxes to the state based on land area and environmental impact.

        Args:
            state: State agent that collects taxes
        """
        log(
            f"Household {self.unique_id} will pay taxes "
            f"(land_area: {self.land_area}, env_impact: {self.environmental_impact}).",
            level="DEBUG",
        )
        # Note: Actual tax payment is handled by the state agent

    def offer_labor(self, labor_market: Optional[object] = None) -> bool:
        """
        Offer labor to the labor market.

        Args:
            labor_market: Optional labor market to offer labor to

        Returns:
            True if labor was successfully offered
        """
        log(f"Household {self.unique_id} offers labor.", level="DEBUG")
        return True

    def consume(
        self, consumption_rate: float, companies: Optional[list["Company"]] = None
    ) -> float:
        """Consume goods by purchasing from companies when possible."""
        if not companies:
            return self._consume_legacy(consumption_rate)

        consumption_budget: float = self.checking_account * consumption_rate
        if consumption_budget <= 0:
            return 0.0

        supplier = random.choice(companies)
        spent = supplier.sell_to_household(self, consumption_budget)

        log(
            f"Household {self.unique_id} consumed goods for {spent:.2f}. "
            f"Checking account now: {self.checking_account:.2f}.",
            level="INFO",
        )
        return spent

    def _consume_legacy(self, consumption_rate: float) -> float:
        consumption_amount: float = self.checking_account * consumption_rate
        self.checking_account -= consumption_amount
        log(
            f"Household {self.unique_id} consumed goods worth: {consumption_amount:.2f}. "
            f"Checking account now: {self.checking_account:.2f}.",
            level="INFO",
        )
        return consumption_amount

    def save(self, savings_bank: Optional[SavingsBank] = None) -> float:
        """
        Move remaining checking balance into savings or deposit it at the savings bank.

        Returns:
            Amount saved
        """
        saved_amount: float = self.checking_account
        self.checking_account = 0.0

        if saved_amount <= 0:
            return 0.0

        if savings_bank is None:
            self.savings += saved_amount
            log(
                f"Household {self.unique_id} saved: {saved_amount:.2f}. "
                f"Total savings now: {self.savings:.2f}.",
                level="INFO",
            )
            return saved_amount

        deposited = savings_bank.deposit_savings(self, saved_amount)
        overflow = saved_amount - deposited

        if overflow > 0:
            self.savings += overflow

        log(
            f"Household {self.unique_id} deposited {deposited:.2f} to SavingsBank "
            f"and kept {overflow:.2f} as local savings. "
            f"Total local savings now: {self.savings:.2f}.",
            level="INFO",
        )
        return saved_amount

    def split_household(self) -> "Household":
        """
        Split household into two, creating a new child household.

        The child household receives 80% of parent's savings as initial capital.
        Parent household resets its growth phase.

        Returns:
            Newly created child household
        """
        # Transfer 80% of savings to new household
        split_consumption: float = self.savings * 0.8
        self.savings -= split_consumption

        log(
            f"Household {self.unique_id} splits after growth phase. "
            f"Consuming split savings: {split_consumption:.2f}. "
            f"Remaining savings: {self.savings:.2f}.",
            level="INFO",
        )

        new_unique_id: str = f"{self.unique_id}_child"
        new_generation: int = self.generation + 1

        new_household = Household(
            new_unique_id,
            income=self.income,
            land_area=self.land_area,
            environmental_impact=self.environmental_impact,
            generation=new_generation,
            config=self.config,
        )
        new_household.checking_account = split_consumption

        log(
            f"New household {new_unique_id} (Generation {new_generation}) created "
            f"with initial checking account: {split_consumption:.2f}.",
            level="INFO",
        )

        # Reset growth phase of parent household
        self.growth_phase = False
        self.growth_counter = 0

        return new_household

    def _handle_childrearing_costs(self, savings_bank: SavingsBank | None) -> float:
        """Withdraw savings via the bank when raising children triggers large expenses."""
        if self.growth_phase or self.savings <= 0:
            return 0.0
        required = self.child_rearing_cost
        if savings_bank is None:
            draw = min(required, self.savings)
            self.savings -= draw
            self.checking_account += draw
            return draw
        withdrawn = savings_bank.give_household_withdrawal(self, required)
        if withdrawn <= 0:
            fallback = min(required, self.savings)
            self.savings -= fallback
            self.checking_account += fallback
            return fallback
        self.checking_account += withdrawn
        return withdrawn

    def _repay_savings_loans(self, savings_bank: SavingsBank | None) -> float:
        """Direct a share of deposits toward repayment of savings-bank loans."""
        if savings_bank is None:
            return 0.0
        outstanding = savings_bank.active_loans.get(self.unique_id, 0.0)
        if outstanding <= 0:
            return 0.0
        disposable = max(0.0, self.checking_account)
        if disposable <= 0:
            return 0.0
        repay_budget = disposable * self.loan_repayment_rate
        repaid = savings_bank.repayment(self, repay_budget)
        self.checking_account -= repaid
        return repaid

    def step(
        self,
        current_step: int,
        state: Optional[object] = None,
        savings_bank: Optional[SavingsBank] = None,
        companies: Optional[list["Company"]] = None,
    ) -> Optional["Household"] | Literal["DEAD"]:
        """
        Execute one simulation step for the household agent.

        During each step, the household:
        1. Ages by one year
        2. Receives income
        3. Pays taxes (if state is provided)
        4. Consumes goods based on its consumption rate
        5. Saves remaining money
        6. Offers labor to the market
        7. May enter growth phase if savings are sufficient
        8. May split to create a new household if growth conditions are met
        9. May die due to aging or stagnation

        Args:
            current_step: Current simulation step number
            state: Optional state agent to pay taxes to

        Returns:
            - "DEAD" if the household should be removed from simulation
            - New household instance if a split occurred
            - None otherwise
        """
        log(f"Household {self.unique_id} starting step {current_step}.", level="INFO")

        # Age increases by 1 each simulation year
        self.age += 1
        self.receive_income()

        if state:
            self.pay_taxes(state)

        # Determine consumption rate based on growth phase
        if self.growth_phase:
            rate: float = self.consumption_rate_growth
            self.growth_counter += 1
        else:
            rate: float = self.consumption_rate_normal

        self.consume(rate, companies)
        self._handle_childrearing_costs(savings_bank)
        self.save(savings_bank)
        self._repay_savings_loans(savings_bank)
        self.offer_labor()

        # Enter growth phase if savings exceed trigger threshold
        if not self.growth_phase and self.savings >= self.savings_growth_trigger:
            self.growth_phase = True
            log(f"Household {self.unique_id} enters growth phase.", level="INFO")

        new_household: Optional[Household] = None

        # Split household if growth phase lasts long enough
        if self.growth_phase and self.growth_counter >= self.growth_threshold:
            new_household = self.split_household()

        # Check death criteria: old age or high generation with no growth
        if self.age >= self.max_age or (
            self.generation >= self.max_generation and not self.growth_phase
        ):
            log(
                f"Household {self.unique_id} (Generation {self.generation}, Age {self.age}) "
                f"dies due to aging or stagnation.",
                level="WARNING",
            )
            return "DEAD"  # Mark for removal from simulation

        log(
            f"Household {self.unique_id} completed step {current_step}. "
            f"Age: {self.age}, Generation: {self.generation}",
            level="INFO",
        )

        return new_household
