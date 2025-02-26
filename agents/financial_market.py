from .base_agent import BaseAgent
from logger import log
from config import CONFIG


class FinancialMarket(BaseAgent):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        # Eine einfache Darstellung von Assets: Name -> aktueller Preis
        self.list_of_assets = {
            "Aktie_A": 100.0,
            "Aktie_B": 50.0,
            "Anleihe_X": 1000.0
        }
        # Bid-Ask-Spreads als Prozentsatz des Preises, z. B. 2%
        self.bid_ask_spreads = {
            "Aktie_A": 0.02,
            "Aktie_B": 0.02,
            "Anleihe_X": 0.01
        }
        # Schwellenwert, ab dem spekulative Assetbestände als Hypervermögen gelten
        self.speculation_limit = CONFIG.get("speculation_limit", 10000)

    def trade_assets(self, buyer, seller, asset, quantity):
        """
        Simuliert einen Handelsvorgang:
          - Überprüft, ob das Asset vorhanden ist.
          - Ermittelt den aktuellen Handelspreis (hier als Basispreis).
          - Loggt den Handel und gibt den Gesamtwert der Transaktion zurück.
        """
        if asset not in self.list_of_assets:
            log(f"FinancialMarket {self.unique_id}: Asset {asset} not found.", level="WARNING")
            return 0.0

        base_price = self.list_of_assets[asset]
        # Berücksichtigt den Spread (als einfacher Mittelwert)
        spread = self.bid_ask_spreads.get(asset, 0)
        trade_price = base_price * (1 + spread / 2)
        total_value = trade_price * quantity

        log(f"FinancialMarket {self.unique_id}: Trade executed for asset {asset} – {quantity} units at {trade_price:.2f} each. Total value: {total_value:.2f}.",
            level="INFO")
        return total_value

    def check_for_hypervermoegen(self, agents):
        """
        Überprüft, ob Agenten spekulative Assetbestände (Hypervermögen) aufgebaut haben.
        Es wird angenommen, dass Agenten (z. B. Unternehmen oder Haushalte) ein Attribut
        'asset_portfolio' besitzen, das ein Dictionary von Assetnamen zu Mengen (oder Werten) darstellt.
        Überschreitet der Gesamtwert eines Portfolios den definierten Schwellenwert, wird dies gemeldet.
        """
        for agent in agents:
            if hasattr(agent, "asset_portfolio"):
                portfolio = agent.asset_portfolio
                total_value = sum(portfolio.get(asset, 0) * self.list_of_assets.get(asset, 0) for asset in portfolio)
                if total_value > self.speculation_limit:
                    log(f"FinancialMarket {self.unique_id}: Agent {agent.unique_id} holds hyper wealth in assets (total value: {total_value:.2f}).",
                        level="WARNING")

    def step(self, current_step, agents):
        """
        Simulationsschritt des Finanzmarktes:
          1. (Platzhalter) Simuliere einen Handelsvorgang oder mehrere.
          2. Überprüfe mittels check_for_hypervermoegen, ob spekulative Bestände aufgebaut wurden.
        """
        log(f"FinancialMarket {self.unique_id} starting step {current_step}.", level="INFO")

        # Platzhalter für einen Handelszyklus: Beispielhafter Handel zwischen zwei Agenten
        # Hier könnte später ein Orderbuch implementiert werden.
        # trade_assets(buyer, seller, asset, quantity) wird hier nicht aktiv aufgerufen.

        # Überprüfung spekulativer Assetbestände
        self.check_for_hypervermoegen(agents)

        log(f"FinancialMarket {self.unique_id} completed step {current_step}.", level="INFO")
