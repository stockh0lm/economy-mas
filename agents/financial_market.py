# financial_market.py
from typing import Protocol, TypeAlias

from config import CONFIG_MODEL, SimulationConfig
from logger import log

from .base_agent import BaseAgent


class AssetPortfolioAgent(Protocol):
    """Protocol for agents that can hold financial assets"""

    unique_id: str
    asset_portfolio: dict[str, float]  # Maps asset name to quantity


# Type aliases for improved readability
AssetName: TypeAlias = str
Price: TypeAlias = float
Quantity: TypeAlias = float


class FinancialMarket(BaseAgent):
    """Closed financial market used only to monitor asset-like holdings."""

    def __init__(self, unique_id: str, config: SimulationConfig | None = None) -> None:
        super().__init__(unique_id)

        self.config: SimulationConfig = config or CONFIG_MODEL

        # Asset prices: name -> current price
        self.list_of_assets: dict[AssetName, Price] = {}

        # Bid-ask spread as percentage of price (e.g., 2%)
        self.bid_ask_spreads: dict[AssetName, float] = {}

        # Threshold for considering asset holdings as hyperwealth
        self.speculation_limit: float = self.config.market.speculation_limit

    def check_for_hypervermoegen(self, agents: list[AssetPortfolioAgent | BaseAgent]) -> None:
        """
        Check if agents have accumulated speculative assets (hyperwealth).

        Assumes agents have an 'asset_portfolio' attribute that maps
        asset names to quantities. Reports if total portfolio value
        exceeds the defined threshold.

        Args:
            agents: List of agents to check for hyperwealth
        """
        for agent in agents:
            if hasattr(agent, "asset_portfolio"):
                portfolio = agent.asset_portfolio
                total_value: float = sum(
                    portfolio.get(asset, 0) * self.list_of_assets.get(asset, 0)
                    for asset in portfolio
                )

                if total_value > self.speculation_limit:
                    log(
                        f"FinancialMarket {self.unique_id}: Agent {agent.unique_id} holds hyper wealth "
                        f"in assets (total value: {total_value:.2f}).",
                        level="WARNING",
                    )

    def step(self, current_step: int, agents: list[BaseAgent]) -> None:
        """Execute one simulation step for passive asset oversight."""
        log(
            f"FinancialMarket {self.unique_id} starting step {current_step} (monitoring only).",
            level="DEBUG",
        )

        # Check for speculative asset accumulation
        self.check_for_hypervermoegen(agents)

        log(
            f"FinancialMarket {self.unique_id} completed step {current_step}.",
            level="DEBUG",
        )
