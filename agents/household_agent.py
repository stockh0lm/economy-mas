from .economic_agent import EconomicAgent
from logger import log

class Household(EconomicAgent):
    def __init__(self, unique_id, income=100, land_area=50, environment_impact=1, generation=1):
        """
        Parameter:
          income: Regelmäßiges Einkommen (z. B. aus Arbeit oder Transfers)
          land_area: Wohn- oder Nutzfläche (für die Berechnung der Bodensteuer)
          environment_impact: Kennzahl für den ökologischen Fußabdruck
          generation: Aktuelle Generation des Haushalts (Standard: 1)
        """
        super().__init__(unique_id)
        self.income = income
        self.land_area = land_area
        self.environment_impact = environment_impact
        self.generation = generation

        # Parameter für Wachstumsphase
        self.growth_phase = False
        self.growth_counter = 0
        self.growth_threshold = 5          # Nach 5 Schritten in der Wachstumsphase erfolgt das Splitting
        self.savings_growth_trigger = 500.0  # Überschreiten die Ersparnisse diesen Wert, startet die Wachstumsphase

        # Alters- und Generationstracking
        self.age = 0
        self.max_age = 80                  # Haushalte sterben nach 80 Jahren
        self.max_generation = 3            # Nach Generation 3 wird der Haushalt als "stagnierend" betrachtet und stirbt

        # Konten
        self.checking_account = 0.0  # Girokonto
        self.savings = 0.0           # Sparkonto

    def receive_income(self):
        self.checking_account += self.income
        log(f"Household {self.unique_id} received income: {self.income}. Checking account now: {self.checking_account}.", level="INFO")

    def pay_taxes(self, state):
        log(f"Household {self.unique_id} will pay taxes (land_area: {self.land_area}, env_impact: {self.environment_impact}).", level="DEBUG")

    def offer_labor(self, labor_market=None):
        log(f"Household {self.unique_id} offers labor.", level="DEBUG")
        return True

    def consume(self, consumption_rate):
        consumption_amount = self.checking_account * consumption_rate
        self.checking_account -= consumption_amount
        log(f"Household {self.unique_id} consumed goods worth: {consumption_amount:.2f}. Checking account now: {self.checking_account:.2f}.", level="INFO")
        return consumption_amount

    def save(self):
        saved_amount = self.checking_account
        self.savings += saved_amount
        log(f"Household {self.unique_id} saved: {saved_amount:.2f}. Total savings now: {self.savings:.2f}.", level="INFO")
        self.checking_account = 0.0

    def split_household(self):
        # 80% der Ersparnisse werden als Startkapital des neuen Haushalts genutzt.
        split_consumption = self.savings * 0.8
        self.savings -= split_consumption
        log(f"Household {self.unique_id} splits after growth phase. Consuming split savings: {split_consumption:.2f}. Remaining savings: {self.savings:.2f}.", level="INFO")
        new_unique_id = f"{self.unique_id}_child"
        new_generation = self.generation + 1
        new_household = Household(new_unique_id, income=self.income, land_area=self.land_area,
                                  environment_impact=self.environment_impact, generation=new_generation)
        new_household.checking_account = split_consumption
        log(f"New household {new_unique_id} (Generation {new_generation}) created with initial checking account: {split_consumption:.2f}.", level="INFO")
        # Zurücksetzen der Wachstumsphase des Elternhaushalts
        self.growth_phase = False
        self.growth_counter = 0
        return new_household

    def step(self, current_step, state=None):
        log(f"Household {self.unique_id} starting step {current_step}.", level="INFO")
        # Jedes Simulationsjahr erhöht das Alter um 1
        self.age += 1
        self.receive_income()
        if state:
            self.pay_taxes(state)
        # Bestimme Konsumrate abhängig von der Wachstumsphase:
        if self.growth_phase:
            rate = 0.9  # In Wachstumsphasen wird stärker konsumiert
            self.growth_counter += 1
        else:
            rate = 0.7
        self.consume(rate)
        self.save()
        self.offer_labor()
        # Eintritt in die Wachstumsphase, wenn genügend Rücklagen vorhanden sind
        if not self.growth_phase and self.savings >= self.savings_growth_trigger:
            self.growth_phase = True
            log(f"Household {self.unique_id} enters growth phase.", level="INFO")
        new_household = None
        # Splitting, wenn die Wachstumsphase lange genug anhält
        if self.growth_phase and self.growth_counter >= self.growth_threshold:
            new_household = self.split_household()
        # Überprüfe Sterbekriterien: hohes Alter oder zu hohe Generation ohne weitere Wachstumsimpulse
        if self.age >= self.max_age or (self.generation >= self.max_generation and not self.growth_phase):
            log(f"Household {self.unique_id} (Generation {self.generation}, Age {self.age}) dies due to aging or stagnation.", level="WARNING")
            return "DEAD"  # Markierung, dass der Haushalt aus der Simulation entfernt werden soll
        log(f"Household {self.unique_id} completed step {current_step}. Age: {self.age}, Generation: {self.generation}", level="INFO")
        if new_household:
            return new_household
        else:
            return None
