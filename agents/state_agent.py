# state_agent.py
from collections.abc import Sequence
from typing import Protocol, TypeAlias, cast

from config import CONFIG_MODEL, SimulationConfig
from logger import log

from .base_agent import BaseAgent
from .labor_market import LaborMarket


class TaxableAgent(Protocol):
    """Protocol defining agents that can be taxed by the state"""

    unique_id: str
    balance: float
    land_area: float = 0.0
    environment_impact: float = 0.0


AgentCollection: TypeAlias = Sequence[TaxableAgent | BaseAgent]


class State(BaseAgent):
    """
    State agent responsible for tax collection, fund distribution, and wealth regulation.
    Acts as the governance mechanism in the simulation economy.
    """

    def __init__(self, unique_id: str, config: SimulationConfig | None = None) -> None:
        """
        Initialize the State agent with default budgets and tax configurations.

        Args:
            unique_id: Unique identifier for the state
        """
        super().__init__(unique_id)

        self.config: SimulationConfig = config or CONFIG_MODEL

        # Financial accounts
        self.tax_revenue: float = 0.0
        self.infrastructure_budget: float = 0.0
        self.social_budget: float = 0.0
        self.environment_budget: float = 0.0

        # Tax parameters from configuration
        self.bodensteuer_rate: float = self.config.tax_rates.bodensteuer
        self.umweltsteuer_rate: float = self.config.tax_rates.umweltsteuer

        # Hyperwealth control parameter
        self.hyperwealth_threshold: float = self.config.clearing.hyperwealth_threshold

        # Budget allocation percentages
        allocation = self.config.state.budget_allocation or {}
        self.infrastructure_allocation: float = allocation.get("infrastructure", 0.5)
        self.social_allocation: float = allocation.get("social", 0.3)
        self.environment_allocation: float = allocation.get("environment", 0.2)

        # Reference to labor market (set after initialization)
        self.labor_market: LaborMarket | None = None


    @property
    def sight_balance(self) -> float:
        """Total state sight balances (sum of sub-budgets).

        We model state deposits as split among several budget buckets.
        This makes tax collection and internal allocations money-neutral.
        """
        return float(
            self.tax_revenue
            + self.infrastructure_budget
            + self.social_budget
            + self.environment_budget
        )


    def collect_taxes(self, agents: AgentCollection) -> None:
        """
        Collect land taxes from all applicable agents.

        Taxes are calculated based on land area, and the collected taxes are added to the state's revenue.

        Args:
            agents: Collection of agents to tax
        """
        total_tax: float = 0.0

        for agent in agents:
            # Skip agents without balance attribute
            if not hasattr(agent, "balance"):
                continue

            taxable_agent = cast(TaxableAgent, agent)
            agent_taxes: float = 0.0

            # Land tax collection
            if hasattr(agent, "land_area") and agent.land_area > 0:
                land_tax: float = agent.land_area * self.bodensteuer_rate
                agent_taxes += land_tax

            # Apply total tax to agent (transfer, no money creation/destruction)
            if agent_taxes > 0:
                # Prefer sight_balance (Warengeld) if available, else fall back to balance.
                if hasattr(taxable_agent, "sight_balance"):
                    available = float(max(0.0, getattr(taxable_agent, "sight_balance")))
                    paid = min(float(agent_taxes), available)
                    setattr(taxable_agent, "sight_balance", available - paid)
                else:
                    available = float(max(0.0, taxable_agent.balance))
                    paid = min(float(agent_taxes), available)
                    taxable_agent.balance -= paid

                if paid > 0:
                    total_tax += paid
                    log(
                        f"State {self.unique_id} collected {paid:.2f} taxes from {agent.unique_id}",
                        level="DEBUG",
                    )

        self.tax_revenue += total_tax
        log(
            f"State {self.unique_id} collected total taxes: {total_tax:.2f}. Revenue now: {self.tax_revenue:.2f}",
            level="INFO",
        )

    def distribute_funds(self) -> None:
        """
        Distribute collected tax revenue to various budget categories.

        Funds are allocated according to predefined percentages for:
        - Infrastructure (default 50%)
        - Social services (default 30%)
        - Environmental initiatives (default 20%)

        After distribution, tax revenue is reset to zero.
        """
        if self.tax_revenue <= 0:
            log(f"State {self.unique_id} has no tax revenue to distribute", level="WARNING")
            return

        # Distribute according to allocation percentages
        self.infrastructure_budget += self.tax_revenue * self.infrastructure_allocation
        self.social_budget += self.tax_revenue * self.social_allocation
        self.environment_budget += self.tax_revenue * self.environment_allocation

        log(
            f"State {self.unique_id} distributed funds - Infrastructure: {self.infrastructure_budget:.2f}, "
            f"Social: {self.social_budget:.2f}, Environment: {self.environment_budget:.2f}",
            level="INFO",
        )

        # Reset tax revenue after distribution
        self.tax_revenue = 0.0

    def receive_hyperwealth(self, amount: float) -> None:
        """Add externally collected hyperwealth to tax revenue."""
        self.tax_revenue += amount
        log(
            f"State {self.unique_id} received {amount:.2f} in forwarded hyperwealth. "
            f"Tax revenue now: {self.tax_revenue:.2f}.",
            level="INFO",
        )

    def oversee_hyperwealth(self, agents: AgentCollection) -> None:
        """
        Monitor and regulate excessive wealth accumulation among agents.

        Any balance exceeding the hyperwealth threshold is confiscated
        and added to the state's tax revenue.

        Args:
            agents: Collection of agents to check for hyperwealth
        """
        log(
            f"State {self.unique_id} oversees hyperwealth passively; ClearingAgent performs confiscations.",
            level="DEBUG",
        )

    def step(self, agents: AgentCollection) -> None:
        """
        Execute one simulation step for the state agent.

        This includes:
        1. Collecting taxes from all agents
        2. Overseeing wealth distribution and applying wealth caps
        3. Distributing collected funds to various budget categories

        Args:
            agents: Collection of agents under state jurisdiction
        """
        log(f"State {self.unique_id} starting step", level="INFO")

        self.collect_taxes(agents)
        self.oversee_hyperwealth(agents)
        self.distribute_funds()

        log(f"State {self.unique_id} completed step", level="INFO")
