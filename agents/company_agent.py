from .economic_agent import EconomicAgent
from logger import log
from config import CONFIG

class Company(EconomicAgent):
    def __init__(self, unique_id, production_capacity=100, resource_usage=10, land_area=100, environmental_impact=5, max_employees=10, employees=None):
        """
        Parameter:
          production_capacity: Maximale Produktionsmenge pro Zyklus.
          resource_usage: Verbrauchte Ressourcen pro Produktionszyklus.
          land_area: Genutzte Bodenfläche (wichtig für die Bodensteuer).
          environmental_impact: Kennzahl zur Umweltbelastung der Produktion.
          employees: Liste der Mitarbeiter (z. B. Household-Objekte), die Löhne erhalten.
        """
        super().__init__(unique_id)
        self.production_capacity = production_capacity
        self.resource_usage = resource_usage
        self.land_area = land_area
        self.environmental_impact = environmental_impact
        self.max_employees = max_employees
        self.employees = employees if employees is not None else []
        self.inventory = 0  # Lagerbestand an produzierten, aber noch nicht verkauften Waren

    def produce(self):
        """
         Simuliert die Produktion von Waren.
         Die produzierte Menge entspricht der Produktionskapazität multipliziert mit dem Verhältnis der tatsächlichen Mitarbeiter zur maximalen Anzahl von Mitarbeitern.
         """
        if self.max_employees == 0:
            actual_production = 0
        else:
            actual_production = self.production_capacity * (len(self.employees) / self.max_employees)
        self.inventory += actual_production
        log(f"Company {self.unique_id} produced {actual_production:.2f} units. Total inventory: {self.inventory:.2f}.",
            level="INFO")
        return actual_production

    def sell_goods(self, demand=50):
        """
        Simuliert den Verkauf von Waren.
        Ein Teil des Inventars wird verkauft. Beim Verkauf wird ein fester
        Preis pro Einheit angenommen, und der Erlös wird dem Firmenkonto (Balance) gutgeschrieben.
        Dies steht sinnbildlich für das Schöpfen von Warengeld.
        """
        sold_quantity = min(self.inventory, demand)
        sale_price_per_unit = 10  # Beispielhafter fester Preis pro Einheit
        revenue = sold_quantity * sale_price_per_unit
        self.balance += revenue
        self.inventory -= sold_quantity
        log(f"Company {self.unique_id} sold {sold_quantity} units for {revenue} (Price/unit: {sale_price_per_unit}). New balance: {self.balance}. Inventory left: {self.inventory}.", level="INFO")
        return revenue

    def pay_wages(self, wage_rate=5):
        """
        Zahlt Löhne an alle Mitarbeitenden.
        Die Gesamtsumme wird vom Firmenkonto abgezogen und bei den
        Mitarbeitern (z. B. über ihre receive_income()-Methode) gutgeschrieben.
        """
        if not self.employees:
            log(f"Company {self.unique_id} has no employees to pay wages.", level="WARNING")
            return 0
        total_wages = wage_rate * len(self.employees)
        self.balance -= total_wages
        for employee in self.employees:
            # Annahme: Mitarbeiter verfügen über eine receive_income()-Methode,
            # die den Lohn ihrem Girokonto zuführt.
            employee.receive_income()
        log(f"Company {self.unique_id} paid wages totaling {total_wages}. New balance: {self.balance}.", level="INFO")
        return total_wages

    def pay_taxes(self, state):
        """
        Simuliert die Steuerzahlung.
        Basierend auf der genutzten Bodenfläche und dem Umweltimpact des Unternehmens
        werden Bodensteuer und Umweltsteuer berechnet und vom Firmenkonto abgezogen.
        Die Steuerbeträge fließen in den Staat (hier als Erhöhung von tax_revenue).
        """
        bodensteuer_rate = CONFIG.get("tax_rates", {}).get("bodensteuer", 0.05)
        umweltsteuer_rate = CONFIG.get("tax_rates", {}).get("umweltsteuer", 0.02)
        tax_due = (self.land_area * bodensteuer_rate) + (self.environmental_impact * umweltsteuer_rate)
        self.balance -= tax_due
        log(f"Company {self.unique_id} paid taxes: {tax_due:.2f} (Bodensteuer: {self.land_area * bodensteuer_rate:.2f}, Umweltsteuer: {self.environmental_impact * umweltsteuer_rate:.2f}). New balance: {self.balance:.2f}.", level="INFO")
        return tax_due

    def request_funds_from_bank(self, amount):
        """
        Platzhalter für die zinsfreie Kreditaufnahme via Kontokorrentkredit.
        Der angeforderte Betrag wird dem Firmenkonto hinzugefügt.
        """
        log(f"Company {self.unique_id} requests funds: {amount}.", level="INFO")
        self.balance += amount
        log(f"Company {self.unique_id} received funds: {amount}. New balance: {self.balance}.", level="INFO")
        return amount

    def step(self, current_step, state=None):
        """
        Simulationsschritt des Unternehmens:
         1. Produktion von Waren.
         2. Verkauf von Waren zur Erhöhung des Kontostandes (Warengeldschöpfung).
         3. Zahlung von Löhnen an Mitarbeitende.
         4. Zahlung von Steuern an den Staat (sofern ein Staat-Agent übergeben wird).
         5. (Optional) Kreditaufnahme zur Deckung von Investitionsbedarf.
        """
        log(f"Company {self.unique_id} starting step {current_step}.", level="INFO")
        self.produce()
        self.sell_goods()
        self.pay_wages()
        if state:
            self.pay_taxes(state)
        # Weitere Schritte, wie etwa Anpassungen der Produktionskapazität oder
        # Interaktionen mit dem Bankensektor, können hier ergänzt werden.
        log(f"Company {self.unique_id} completed step {current_step}.", level="INFO")
