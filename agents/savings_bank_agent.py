from .base_agent import BaseAgent
from logger import log
from config import CONFIG


class SavingsBank(BaseAgent):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        # Gesamte Spareinlagen und verfügbare Liquidität
        self.savings_accounts = {}  # {agent_id: current_savings}
        self.total_savings = 0.0
        self.active_loans = {}  # {borrower_id: outstanding_amount}
        # Minimaler Zinssatz – in diesem Modell zinslos oder nur minimal
        self.loan_interest_rate = CONFIG.get("loan_interest_rate", 0.0)
        # Liquidität entspricht zunächst dem Gesamtbetrag an Spareinlagen
        self.liquidity = 0.0
        # Maximale Spargrenze pro Konto (Platzhalter, z. B. 10.000 Einheiten)
        self.max_savings_per_account = CONFIG.get("max_savings_per_account", 10000)

    def deposit_savings(self, agent, amount):
        """
        Agenten (Haushalte oder Unternehmen) legen Spareinlagen bei der Sparkasse an.
        Falls das neue Guthaben die Spargrenze überschreitet, wird der Überschuss
        abgewiesen (oder separat behandelt).
        """
        agent_id = agent.unique_id
        current = self.savings_accounts.get(agent_id, 0.0)
        new_total = current + amount

        if new_total > self.max_savings_per_account:
            allowed = self.max_savings_per_account - current
            rejected = amount - allowed
            if allowed > 0:
                self.savings_accounts[agent_id] = current + allowed
                self.total_savings += allowed
                self.liquidity += allowed
                log(f"SavingsBank {self.unique_id}: Agent {agent_id} deposited {allowed:.2f} (max reached; {rejected:.2f} rejected).",
                    level="INFO")
            else:
                log(f"SavingsBank {self.unique_id}: Agent {agent_id} deposit of {amount:.2f} rejected (max savings limit reached).",
                    level="WARNING")
        else:
            self.savings_accounts[agent_id] = new_total
            self.total_savings += amount
            self.liquidity += amount
            log(f"SavingsBank {self.unique_id}: Agent {agent_id} deposited {amount:.2f}. Total for agent: {new_total:.2f}.",
                level="INFO")

    def withdraw_savings(self, agent, amount):
        """
        Agent zieht Geld von seinem Sparkonto ab, sofern ausreichend Guthaben vorhanden.
        """
        agent_id = agent.unique_id
        current = self.savings_accounts.get(agent_id, 0.0)
        if current >= amount:
            self.savings_accounts[agent_id] = current - amount
            self.total_savings -= amount
            self.liquidity -= amount
            log(f"SavingsBank {self.unique_id}: Agent {agent_id} withdrew {amount:.2f}. New balance: {self.savings_accounts[agent_id]:.2f}.",
                level="INFO")
            return amount
        else:
            log(f"SavingsBank {self.unique_id}: Withdrawal of {amount:.2f} for Agent {agent_id} failed. Available: {current:.2f}.",
                level="WARNING")
            return 0.0

    def allocate_credit(self, borrower, amount):
        """
        Vergibt einen zinsfreien (oder minimal verzinsten) Kredit an einen Kreditnehmer.
        Der angeforderte Betrag wird, sofern ausreichend Liquidität vorhanden ist,
        dem Firmenkonto des Kreditnehmers gutgeschrieben und als aktiver Kredit
        registriert.
        """
        if self.liquidity >= amount:
            borrower_id = borrower.unique_id
            # Kreditvergabe: Betrag wird zum Kredit hinzugefügt
            self.active_loans[borrower_id] = self.active_loans.get(borrower_id, 0.0) + amount
            # Verringerung der verfügbaren Liquidität
            self.liquidity -= amount
            # Kredit wird zinslos zum Konto des Kreditnehmers transferiert:
            if hasattr(borrower, "request_funds_from_bank"):
                borrower.request_funds_from_bank(amount)
            log(f"SavingsBank {self.unique_id}: Allocated credit of {amount:.2f} to borrower {borrower_id}.",
                level="INFO")
            return amount
        else:
            log(f"SavingsBank {self.unique_id}: Insufficient liquidity to allocate credit of {amount:.2f}. Available liquidity: {self.liquidity:.2f}.",
                level="WARNING")
            return 0.0

    def repayment(self, borrower, amount):
        """
        Nimmt Rückzahlungen von Kreditnehmern entgegen. Der zurückgezahlte Betrag
        wird der Liquidität hinzugefügt und vom aktiven Kredit abgezogen.
        """
        borrower_id = borrower.unique_id
        outstanding = self.active_loans.get(borrower_id, 0.0)
        if outstanding == 0:
            log(f"SavingsBank {self.unique_id}: No outstanding loan for borrower {borrower_id}.", level="WARNING")
            return 0.0
        repaid = min(amount, outstanding)
        self.active_loans[borrower_id] = outstanding - repaid
        self.liquidity += repaid
        log(f"SavingsBank {self.unique_id}: Borrower {borrower_id} repaid {repaid:.2f}. Remaining loan: {self.active_loans[borrower_id]:.2f}.",
            level="INFO")
        return repaid

    def enforce_spargrenze(self, agent):
        """
        Überprüft das Sparkonto eines Agenten. Falls das Guthaben die festgelegte
        Spargrenze überschreitet, wird der Überschuss entfernt (und ggf. an den Staat
        gemeldet, hier als Logausgabe).
        """
        agent_id = agent.unique_id
        current = self.savings_accounts.get(agent_id, 0.0)
        if current > self.max_savings_per_account:
            excess = current - self.max_savings_per_account
            self.savings_accounts[agent_id] = self.max_savings_per_account
            self.total_savings -= excess
            self.liquidity -= excess
            log(f"SavingsBank {self.unique_id}: Enforced savings limit for Agent {agent_id}. Excess of {excess:.2f} removed.",
                level="INFO")
            # Hier könnte zusätzlich eine Meldung an den Staat erfolgen.
        else:
            log(f"SavingsBank {self.unique_id}: Agent {agent_id} is within the savings limit.", level="DEBUG")

    def step(self, current_step):
        """
        Simulationsschritt der Sparkasse:
         1. Überprüft alle Konten auf Einhaltung der Spargrenzen.
         2. (Platzhalter) Prüft, ob Fristenkongruenz für die Einlagen gegeben ist.
         3. (Platzhalter) Arbeitet mit einer Clearingstelle zur Ausgleichung von Liquiditätsengpässen.
        """
        log(f"SavingsBank {self.unique_id} starting step {current_step}.", level="INFO")
        # Überprüfe alle Einlagen
        for agent_id in list(self.savings_accounts.keys()):
            # Hier müsste man idealerweise den Agenten referenzieren – als Platzhalter prüfen wir das Guthaben
            self.enforce_spargrenze(type("DummyAgent", (object,), {"unique_id": agent_id}))
        # Platzhalter für Fristenkongruenz und Clearingstelle-Zusammenarbeit:
        log(f"SavingsBank {self.unique_id}: Fristenkongruenz and clearing operations not implemented yet.",
            level="DEBUG")
        log(f"SavingsBank {self.unique_id} completed step {current_step}.", level="INFO")
