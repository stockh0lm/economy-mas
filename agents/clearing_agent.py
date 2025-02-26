from .base_agent import BaseAgent
from logger import log
from config import CONFIG


class ClearingAgent(BaseAgent):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        # Listen der zu überwachenden Banken und Sparkassen
        self.monitored_banks = []  # z. B. Instanzen von WarengeldBank
        self.monitored_sparkassen = []  # z. B. Instanzen von SavingsBank
        # Gesammelte Überschüsse aus Hypervermögen
        self.excess_wealth_collected = 0.0
        # Schwellenwert für Hypervermögen (Beispielwert, kann in CONFIG gesetzt werden)
        self.hyperwealth_threshold = CONFIG.get("hyperwealth_threshold", 1000000)

    def balance_liquidity(self):
        """
        Sorgt für den Ausgleich von Liquiditätsengpässen zwischen den überwachten Banken
        und Sparkassen. Beispielhafter Algorithmus: Liegt bei einer Bank Liquidität über
        einem gewünschten Niveau, und bei einer Sparkasse darunter, so wird ein Teilbetrag transferiert.
        """
        log(f"ClearingAgent {self.unique_id}: Balancing liquidity among monitored banks and sparkassen.", level="INFO")
        desired_bank_liquidity = CONFIG.get("desired_bank_liquidity", 1000)
        desired_sparkassen_liquidity = CONFIG.get("desired_sparkassen_liquidity", 500)

        for bank in self.monitored_banks:
            if hasattr(bank, "liquidity"):
                excess = bank.liquidity - desired_bank_liquidity
                if excess > 0:
                    for sparkasse in self.monitored_sparkassen:
                        if hasattr(sparkasse, "liquidity"):
                            deficit = desired_sparkassen_liquidity - sparkasse.liquidity
                            if deficit > 0:
                                transfer_amount = min(excess, deficit)
                                bank.liquidity -= transfer_amount
                                sparkasse.liquidity += transfer_amount
                                log(f"ClearingAgent {self.unique_id}: Transferred {transfer_amount:.2f} from Bank {bank.unique_id} to Sparkasse {sparkasse.unique_id}.",
                                    level="INFO")
                                excess -= transfer_amount
                                if excess <= 0:
                                    break

    def check_money_supply(self, agents):
        """
        Summiert beispielhaft das gesamte Geld (über das Attribut 'balance') aller übergebenen Agenten,
        um einen Eindruck von der Gesamtgeldmenge im System zu erhalten.
        """
        total_money = 0.0
        for agent in agents:
            if hasattr(agent, "balance"):
                total_money += agent.balance
        log(f"ClearingAgent {self.unique_id}: Total money supply in system: {total_money:.2f}.", level="INFO")
        # Hier könnte später ein Eingriff erfolgen, wenn die Geldmenge von einem angestrebten Wert abweicht.

    def report_hypervermoegen(self, agents):
        """
        Prüft, ob einzelne Agenten (z. B. Unternehmen, Haushalte) ein Vermögen besitzen,
        das den festgelegten Schwellenwert überschreitet. Überschüsse werden eingesammelt
        (hier als Reduktion des Agentenvermögens und Aufsummierung in excess_wealth_collected).
        """
        for agent in agents:
            if hasattr(agent, "balance") and agent.balance > self.hyperwealth_threshold:
                excess = agent.balance - self.hyperwealth_threshold
                agent.balance -= excess
                self.excess_wealth_collected += excess
                log(f"ClearingAgent {self.unique_id}: Collected excess wealth of {excess:.2f} from agent {agent.unique_id}.",
                    level="INFO")

    def step(self, current_step, all_agents):
        """
        Simulationsschritt der Clearingstelle:
          1. Balance der Liquidität zwischen überwachten Banken und Sparkassen ausgleichen.
          2. Gesamtgeldmenge im System überprüfen.
          3. Hypervermögen bei Agenten melden und ggf. einsammeln.
        """
        log(f"ClearingAgent {self.unique_id} starting step {current_step}.", level="INFO")
        self.balance_liquidity()
        self.check_money_supply(all_agents)
        self.report_hypervermoegen(all_agents)
        log(f"ClearingAgent {self.unique_id} completed step {current_step}. Excess wealth collected: {self.excess_wealth_collected:.2f}.",
            level="INFO")
