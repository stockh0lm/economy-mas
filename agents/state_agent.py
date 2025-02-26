from .base_agent import BaseAgent
from config import CONFIG
from logger import log

class State(BaseAgent):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        # Initialisierung der finanziellen Felder
        self.tax_revenue = 0.0
        self.infrastructure_budget = 0.0
        self.social_budget = 0.0
        self.environment_budget = 0.0

        # Steuerparameter aus der Konfiguration (Beispielwerte)
        self.bodensteuer_rate = CONFIG.get("tax_rates", {}).get("bodensteuer", 0.05)
        self.umweltsteuer_rate = CONFIG.get("tax_rates", {}).get("umweltsteuer", 0.02)

        # Beispielhafter Schwellenwert für Hypervermögen (Platzhalter)
        self.hyperwealth_threshold = 1000000  # z. B. 1 Mio. Einheiten

    def collect_taxes(self, agents):
        """
        Erhebt Steuern von Agenten (z. B. Haushalte, Unternehmen).
        Es wird angenommen, dass Agenten Attribute wie 'land_area' (für die Bodensteuer)
        und 'environment_impact' (für die Umweltsteuer) besitzen. Die Steuern werden
        proportional zu diesen Attributen erhoben und vom Agenten abgezogen.
        """
        total_tax = 0.0
        for agent in agents:
            # Erhebung der Bodensteuer
            if hasattr(agent, "land_area"):
                tax = agent.land_area * self.bodensteuer_rate
                total_tax += tax
                if hasattr(agent, "balance"):
                    agent.balance -= tax
            # Erhebung der Umweltsteuer
            if hasattr(agent, "environment_impact"):
                tax = agent.environment_impact * self.umweltsteuer_rate
                total_tax += tax
                if hasattr(agent, "balance"):
                    agent.balance -= tax

        self.tax_revenue += total_tax
        log(f"State {self.unique_id} collected taxes: {total_tax:.2f}. Total revenue now: {self.tax_revenue:.2f}.", level="INFO")

    def distribute_funds(self):
        """
        Verteilt die gesammelten Steuereinnahmen auf verschiedene Bereiche:
        Beispielsweise 50% für Infrastruktur, 30% für soziale Dienste und 20% für
        Umweltmaßnahmen (Recycling, Schadstoffkontrolle etc.).
        Nach der Verteilung wird das Steueraufkommen zurückgesetzt.
        """
        if self.tax_revenue <= 0:
            log("No tax revenue available for distribution.", level="WARNING")
            return

        allocation = {
            "infrastructure": 0.5,
            "social": 0.3,
            "environment": 0.2
        }
        self.infrastructure_budget += self.tax_revenue * allocation["infrastructure"]
        self.social_budget += self.tax_revenue * allocation["social"]
        self.environment_budget += self.tax_revenue * allocation["environment"]

        log(
            f"Funds distributed - Infrastructure: {self.infrastructure_budget:.2f}, "
            f"Social: {self.social_budget:.2f}, Environment: {self.environment_budget:.2f}.",
            level="INFO"
        )
        # Nach der Verteilung wird das Steueraufkommen zurückgesetzt
        self.tax_revenue = 0.0

    def oversee_hypervermoegen(self, agents):
        """
        Überprüft, ob Agenten (z. B. Unternehmen oder Haushalte) ein Vermögen
        besitzen, das die definierte Schwelle überschreitet. Liegt das der Fall,
        wird der Überschuss (als Beispiel) abgezogen und dem Staat als zusätzliche
        Einnahme zuführt.
        """
        for agent in agents:
            if hasattr(agent, "balance") and agent.balance > self.hyperwealth_threshold:
                excess = agent.balance - self.hyperwealth_threshold
                agent.balance -= excess
                self.tax_revenue += excess
                log(f"State {self.unique_id} confiscated {excess:.2f} from agent {agent.unique_id} for hyper wealth control.", level="INFO")

    def step(self, agents):
        """
        Simulationsschritt des Staates:
         1. Erhebt Steuern von den übergebenen Agenten.
         2. Überwacht die Vermögensbildung (Hypervermögen) und führt ggf. Abschöpfungen durch.
         3. Verteilt die gesammelten Mittel auf Infrastruktur, soziale Dienste und Umwelt.
        """
        log(f"State {self.unique_id} starting simulation step.", level="INFO")
        self.collect_taxes(agents)
        self.oversee_hypervermoegen(agents)
        self.distribute_funds()
        log(f"State {self.unique_id} completed simulation step.", level="INFO")
