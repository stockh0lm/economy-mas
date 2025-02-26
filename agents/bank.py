from .base_agent import BaseAgent
from logger import log
from config import CONFIG

class WarengeldBank(BaseAgent):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        # Dictionary, das jedem Händler (merchant_id) den aktuellen
        # ausstehenden Kontokorrentbetrag zuordnet.
        self.kontokorrent_lines = {}  # {merchant_id: outstanding_amount}
        # Gebührensatz, der als Prozentsatz des ausstehenden Kredits berechnet wird.
        self.fee_rate = CONFIG.get("bank_fee_rate", 0.01)  # z. B. 1%
        # Intervall für Inventurprüfungen (z. B. alle 3 Simulationsschritte)
        self.inventory_check_interval = CONFIG.get("inventory_check_interval", 3)
        # Gesammelte Gebühren als Einnahmen der Bank
        self.collected_fees = 0.0
        # Liquidity: Initialer Liquiditätsbestand der Bank; Wert aus CONFIG oder Standardwert
        self.liquidity = CONFIG.get("initial_bank_liquidity", 1000.0)

    def grant_kontokorrent(self, merchant, amount):
        """
        Gewährt einem Händler (z. B. einem Unternehmen) einen zinsfreien Kontokorrentkredit,
        der als Warengeldschöpfung fungiert.
        Zunächst wird geprüft, ob ausreichend Liquidität vorhanden ist.
        Der angeforderte Betrag wird dem bestehenden Kredit (falls vorhanden) hinzugefügt,
        von der Bankliquidität abgezogen und der Händler wird informiert.
        """
        if self.liquidity < amount:
            log(f"WarengeldBank {self.unique_id}: Insufficient liquidity to grant credit of {amount:.2f}. Available liquidity: {self.liquidity:.2f}.", level="WARNING")
            return 0.0

        merchant_id = merchant.unique_id
        current_credit = self.kontokorrent_lines.get(merchant_id, 0.0)
        self.kontokorrent_lines[merchant_id] = current_credit + amount
        self.liquidity -= amount  # Reduziere die Bankliquidität

        if hasattr(merchant, "request_funds_from_bank"):
            merchant.request_funds_from_bank(amount)
        log(f"WarengeldBank {self.unique_id}: Granted kontokorrent credit of {amount:.2f} to merchant {merchant_id}. Total credit now: {self.kontokorrent_lines[merchant_id]:.2f}. Liquidity remaining: {self.liquidity:.2f}.", level="INFO")
        return amount

    def repay_kontokorrent(self, merchant, amount):
        """
        Tilgt einen Teil des ausstehenden Kontokorrentkredits eines Händlers.
        Der zurückgezahlte Betrag wird vom ausstehenden Kredit abgezogen und zur
        Liquidität der Bank hinzugefügt.
        """
        merchant_id = merchant.unique_id
        outstanding = self.kontokorrent_lines.get(merchant_id, 0.0)
        repaid = min(amount, outstanding)
        self.kontokorrent_lines[merchant_id] = outstanding - repaid
        self.liquidity += repaid  # Erhöhe die Liquidität
        log(f"WarengeldBank {self.unique_id}: Merchant {merchant_id} repaid {repaid:.2f}. Remaining credit: {self.kontokorrent_lines[merchant_id]:.2f}. Liquidity now: {self.liquidity:.2f}.", level="INFO")
        return repaid

    def check_inventories(self, merchants):
        """
        Führt eine Inventurprüfung bei den Händlern durch, um sicherzustellen,
        dass ausreichend Warenbestand vorhanden ist, um den ausstehenden
        Kontokorrentkredit zu decken. Liegt der Inventarwert (hier als Platzhalter
        angenommen über das Attribut 'inventory' des Händlers) deutlich unter dem Kreditbetrag,
        wird eine Warnmeldung geloggt.
        """
        for merchant in merchants:
            merchant_id = merchant.unique_id
            credit = self.kontokorrent_lines.get(merchant_id, 0.0)
            if hasattr(merchant, "inventory"):
                inventory = merchant.inventory
                # Platzhalter: Wenn der Warenwert (hier als Menge) weniger als 80% des Kredits beträgt...
                if inventory < 0.8 * credit:
                    log(f"WarengeldBank {self.unique_id}: Inventory check warning for merchant {merchant_id}: inventory ({inventory}) is low compared to credit ({credit:.2f}).", level="WARNING")
                else:
                    log(f"WarengeldBank {self.unique_id}: Inventory check passed for merchant {merchant_id}.", level="DEBUG")
            else:
                log(f"WarengeldBank {self.unique_id}: Merchant {merchant_id} has no inventory attribute.", level="DEBUG")

    def calculate_fees(self, merchants):
        """
        Berechnet Kontoführungsgebühren für jeden Händler basierend auf dem
        ausstehenden Kontokorrentkredit. Die Gebühr wird vom Konto des Händlers
        abgezogen (sofern vorhanden) und als Einnahme der Bank verbucht.
        Zusätzlich wird der erhobene Betrag der Liquidität hinzugefügt.
        """
        for merchant in merchants:
            merchant_id = merchant.unique_id
            credit = self.kontokorrent_lines.get(merchant_id, 0.0)
            fee = credit * self.fee_rate
            if hasattr(merchant, "balance"):
                merchant.balance -= fee
                log(f"WarengeldBank {self.unique_id}: Charged fee of {fee:.2f} to merchant {merchant_id}.", level="INFO")
            self.collected_fees += fee
            self.liquidity += fee  # Füge die Gebühren der Liquidität hinzu

    def step(self, current_step, merchants):
        """
        Simulationsschritt der Bank:
         1. Führt alle inventory_check_interval Schritte eine Inventurprüfung durch.
         2. Berechnet und zieht Kontoführungsgebühren ein.
         3. Weitere Prozesse (z. B. Anti-Hypervermögen-Prüfung) können hier ergänzt werden.
        """
        log(f"WarengeldBank {self.unique_id} starting step {current_step}.", level="INFO")

        # Inventurprüfung alle inventory_check_interval Schritte
        if current_step % self.inventory_check_interval == 0:
            self.check_inventories(merchants)

        # Gebühren einziehen
        self.calculate_fees(merchants)

        log(f"WarengeldBank {self.unique_id} completed step {current_step}. Collected fees so far: {self.collected_fees:.2f}. Liquidity: {self.liquidity:.2f}.", level="INFO")
