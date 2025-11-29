# financial_market.py
from typing import Dict, List, Protocol, TypeAlias, Union

from config import CONFIG_MODEL, SimulationConfig
from logger import log

from .base_agent import BaseAgent


class AssetPortfolioAgent(Protocol):
    """Protocol for agents that can hold financial assets"""

    unique_id: str
    asset_portfolio: Dict[str, float]  # Maps asset name to quantity


# Type aliases for improved readability
AssetName: TypeAlias = str
Price: TypeAlias = float
Quantity: TypeAlias = float
AssetPortfolio: TypeAlias = Dict[AssetName, Quantity]


class FinancialMarket(BaseAgent):
    """
    Simulates a financial market where agents can trade assets.

    Tracks asset prices, handles trades between agents, and monitors
    for speculative asset accumulation (hyperwealth).
    """

    def __init__(self, unique_id: str, config: SimulationConfig | None = None) -> None:
        """
        Initialize a financial market.

        Args:
            unique_id: Unique identifier for this financial market
        """
        super().__init__(unique_id)

        self.config: SimulationConfig = config or CONFIG_MODEL

        # Asset prices: name -> current price
        self.list_of_assets: Dict[AssetName, Price] = {
            "Aktie_A": self.config.asset_initial_prices.get("Aktie_A", 100.0),
            "Aktie_B": self.config.asset_initial_prices.get("Aktie_B", 50.0),
            "Anleihe_X": self.config.asset_initial_prices.get("Anleihe_X", 1000.0),
        }

        # Bid-ask spread as percentage of price (e.g., 2%)
        self.bid_ask_spreads: Dict[AssetName, float] = {
            "Aktie_A": self.config.asset_bid_ask_spreads.get("Aktie_A", 0.02),
            "Aktie_B": self.config.asset_bid_ask_spreads.get("Aktie_B", 0.02),
            "Anleihe_X": self.config.asset_bid_ask_spreads.get("Anleihe_X", 0.01),
        }

        # Threshold for considering asset holdings as hyperwealth
        self.speculation_limit: float = self.config.speculation_limit

    def trade_assets(
        self,
        buyer: AssetPortfolioAgent,
        seller: AssetPortfolioAgent,
        asset: AssetName,
        quantity: Quantity,
    ) -> float:
        """
        Simulate a trading transaction between two agents.

        Args:
            buyer: Agent purchasing the asset
            seller: Agent selling the asset
            asset: Name of the traded asset
            quantity: Quantity of assets being traded

        Returns:
            Total value of the transaction, or 0.0 if asset not found
        """
        if asset not in self.list_of_assets:
            log(f"FinancialMarket {self.unique_id}: Asset {asset} not found.", level="WARNING")
            return 0.0

        base_price: Price = self.list_of_assets[asset]
        # Account for spread (as simple average)
        spread: float = self.bid_ask_spreads.get(asset, 0)
        trade_price: Price = base_price * (1 + spread / 2)
        total_value: float = trade_price * quantity

        log(
            f"FinancialMarket {self.unique_id}: Trade executed for asset {asset} – "
            f"{quantity} units at {trade_price:.2f} each. Total value: {total_value:.2f}.",
            level="INFO",
        )

        return total_value

    def check_for_hypervermoegen(self, agents: List[Union[AssetPortfolioAgent, BaseAgent]]) -> None:
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

    def step(self, current_step: int, agents: List[BaseAgent]) -> None:
        """
        Execute one simulation step for the financial market.

        During each step:
        1. (Placeholder) Simulate trading activities
        2. Check for hyperwealth accumulation

        Args:
            current_step: Current simulation step number
            agents: List of agents participating in the financial market
        """
        log(f"FinancialMarket {self.unique_id} starting step {current_step}.", level="INFO")

        # Placeholder for a trading cycle - could implement an order book here
        # self.trade_assets(buyer, seller, asset, quantity) would be called here

        # Check for speculative asset accumulation
        self.check_for_hypervermoegen(agents)

        log(f"FinancialMarket {self.unique_id} completed step {current_step}.", level="INFO")
