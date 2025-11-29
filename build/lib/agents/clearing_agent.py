# clearing_agent.py
from typing import TYPE_CHECKING, Protocol, Sequence, TypeAlias, cast, runtime_checkable

from config import CONFIG_MODEL, SimulationConfig
from logger import log

from .base_agent import BaseAgent

if TYPE_CHECKING:
    from .state_agent import State


@runtime_checkable
class LiquidityAgent(Protocol):
    """Protocol for agents that maintain a liquidity attribute"""

    unique_id: str
    liquidity: float


@runtime_checkable
class WealthAgent(Protocol):
    """Protocol for agents that maintain a balance attribute"""

    unique_id: str
    balance: float


# Type aliases for better readability
AgentWithBalance: TypeAlias = WealthAgent
FinancialAgent: TypeAlias = LiquidityAgent | WealthAgent


class ClearingAgent(BaseAgent):
    """
    Manages liquidity balance between financial institutions and monitors system-wide money supply.

    The clearing agent serves as a central oversight mechanism to:
    1. Balance liquidity between banks and savings banks
    2. Monitor total money supply in the economic system
    3. Implement wealth caps by collecting excess wealth above thresholds
    """

    def __init__(self, unique_id: str, config: SimulationConfig | None = None) -> None:
        """
        Initialize a clearing agent with oversight responsibilities.

        Args:
            unique_id: Unique identifier for this clearing agent
        """
        super().__init__(unique_id)

        # Banks and savings banks under monitoring
        self.monitored_banks: list[LiquidityAgent] = []
        self.monitored_savings_banks: list[LiquidityAgent] = []

        self.config: SimulationConfig = config or CONFIG_MODEL

        # Accumulated wealth from hyperwealth collection
        self.excess_wealth_collected: float = 0.0

        # Configuration parameters
        self.hyperwealth_threshold: float = self.config.hyperwealth_threshold
        self.desired_bank_liquidity: float = self.config.desired_bank_liquidity
        self.desired_savings_bank_liquidity: float = self.config.desired_sparkassen_liquidity

    def balance_liquidity(self) -> None:
        """
        Balance liquidity between monitored banks and savings banks.

        If a bank has excess liquidity above the desired level and a savings bank
        has liquidity below its desired level, transfer funds to achieve balance.
        """
        log(
            f"ClearingAgent {self.unique_id}: Balancing liquidity among monitored banks and savings banks.",
            level="INFO",
        )

        for bank in self.monitored_banks:
            excess: float = bank.liquidity - self.desired_bank_liquidity

            if excess > 0:
                for savings_bank in self.monitored_savings_banks:
                    deficit: float = self.desired_savings_bank_liquidity - savings_bank.liquidity

                    if deficit > 0:
                        # Calculate transfer amount (minimum of excess and deficit)
                        transfer_amount: float = min(excess, deficit)

                        # Update liquidity values
                        bank.liquidity -= transfer_amount
                        savings_bank.liquidity += transfer_amount

                        log(
                            f"ClearingAgent {self.unique_id}: Transferred {transfer_amount:.2f} "
                            f"from {bank.unique_id} to {savings_bank.unique_id}.",
                            level="INFO",
                        )

                        # Update remaining excess after transfer
                        excess -= transfer_amount

                        if excess <= 0:
                            break  # No more excess to distribute

    def check_money_supply(self, agents: Sequence[AgentWithBalance]) -> float:
        """
        Calculate the total money supply in the system by summing all agent balances.

        This provides a measure of the overall money in circulation and can
        be used for monetary policy decisions.

        Args:
            agents: Collection of agents with balance attributes

        Returns:
            Total money supply in the system
        """
        total_money: float = 0.0

        for agent in agents:
            if hasattr(agent, "balance"):
                agent_balance = cast(WealthAgent, agent).balance
                total_money += agent_balance

        log(
            f"ClearingAgent {self.unique_id}: Total money supply in system: {total_money:.2f}.",
            level="INFO",
        )

        return total_money

    def report_hyperwealth(self, agents: Sequence[AgentWithBalance]) -> float:
        """
        Identify and collect excess wealth from agents exceeding the hyperwealth threshold.

        For any agent with balance above the threshold, the excess amount is
        collected and the agent's balance is reduced accordingly.

        Args:
            agents: Collection of agents to check for hyperwealth

        Returns:
            Total excess wealth collected in this operation
        """
        collected_this_round: float = 0.0

        for agent in agents:
            if hasattr(agent, "balance"):
                wealth_agent = cast(WealthAgent, agent)

                if wealth_agent.balance > self.hyperwealth_threshold:
                    excess: float = wealth_agent.balance - self.hyperwealth_threshold
                    wealth_agent.balance -= excess
                    self.excess_wealth_collected += excess
                    collected_this_round += excess

                    log(
                        f"ClearingAgent {self.unique_id}: Collected excess wealth of {excess:.2f} "
                        f"from agent {wealth_agent.unique_id}.",
                        level="WARNING",
                    )

        return collected_this_round

    def step(
        self,
        current_step: int,
        all_agents: Sequence[FinancialAgent],
        state: "State | None" = None,
    ) -> None:
        """
        Execute one simulation step for the clearing agent.

        This includes:
        1. Balancing liquidity between monitored financial institutions
        2. Checking the total money supply in the system
        3. Reporting and collecting hyperwealth from agents

        Args:
            current_step: Current simulation step number
            all_agents: Collection of all economic agents to monitor
        """
        log(f"ClearingAgent {self.unique_id} starting step {current_step}.", level="INFO")

        self.balance_liquidity()
        self.check_money_supply(all_agents)
        collected: float = self.report_hyperwealth(all_agents)

        if state is not None and collected > 0:
            state.receive_hyperwealth(collected)
            log(
                f"ClearingAgent {self.unique_id}: forwarded {collected:.2f} of excess wealth to state.",
                level="INFO",
            )

        log(
            f"ClearingAgent {self.unique_id} completed step {current_step}. "
            f"Excess wealth collected this step: {collected:.2f}. "
            f"Total excess collected: {self.excess_wealth_collected:.2f}.",
            level="INFO",
        )
