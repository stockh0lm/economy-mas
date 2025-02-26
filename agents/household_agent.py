from .economic_agent import EconomicAgent
from logger import log

class Household(EconomicAgent):
    def __init__(self, unique_id, income=100, land_area=50, environment_impact=1):
        """
        Parameter:
          income: Regelmäßiges Einkommen (z. B. aus Arbeit oder Transfers)
          land_area: Wohn- oder Nutzfläche (für die Berechnung der Bodensteuer)
          environment_impact: Kennzahl für den ökologischen Fußabdruck
        """
        super().__init__(unique_id)
        self.income = income
        self.land_area = land_area
        self.environment_impact = environment_impact

        # Konten: Jeder Haushalt besitzt ein Girokonto (checking_account) und ein Sparkonto (savings)
        self.checking_account = 0.0  # Geld, das kurzfristig zur Verfügung steht (Girokonto)
        self.savings = 0.0           # Erspartes (Sparkonto)

    def receive_income(self):
        """
        Simuliert den Geldeingang (z. B. Lohn oder Transferleistung) und schreibt
        diesen auf das Girokonto.
        """
        self.checking_account += self.income
        log(f"Household {self.unique_id} received income: {self.income}. Checking account now: {self.checking_account}.", level="INFO")

    def pay_taxes(self, state):
        """
        Platzhalter: In diesem Modell werden Haushalte über ihre Attribute
        'land_area' und 'environment_impact' in die Steuererhebung einbezogen.
        Falls ein Staat-Agent über 'collect_taxes' arbeitet, kann er diese Attribute
        nutzen, um Steuern zu berechnen und von der Bilanz (z. B. checking_account)
        abzuziehen.
        """
        log(f"Household {self.unique_id} will pay taxes (land_area: {self.land_area}, env_impact: {self.environment_impact}).", level="DEBUG")
        # Hier erfolgt keine direkte Abrechnung – die Steuer wird vom Staat-Agenten abgeholt.

    def offer_labor(self, labor_market=None):
        """
        Platzhalter: Der Haushalt bietet seine Arbeitskraft an.
        """
        log(f"Household {self.unique_id} offers labor.", level="DEBUG")
        return True

    def consume(self):
        """
        Simuliert Konsum: Ein bestimmter Anteil des verfügbaren Giroguthabens wird ausgegeben.
        Hier wird beispielhaft ein Konsumanteil von 70% des aktuellen Girokontostandes veranschlagt.
        """
        consumption_rate = 0.7
        consumption_amount = self.checking_account * consumption_rate
        self.checking_account -= consumption_amount
        log(f"Household {self.unique_id} consumed goods worth: {consumption_amount:.2f}. Checking account now: {self.checking_account:.2f}.", level="INFO")

    def save(self):
        """
        Simuliert Sparen: Das verbleibende Giroguthaben wird als Ersparnis auf das Sparkonto übertragen.
        """
        saved_amount = self.checking_account
        self.savings += saved_amount
        log(f"Household {self.unique_id} saved: {saved_amount:.2f}. Total savings now: {self.savings:.2f}.", level="INFO")
        self.checking_account = 0.0

    def step(self, current_step, state=None):
        """
        Simulationsschritt des Haushalts:
         1. Einkommen empfangen.
         2. (Optional) Steuern zahlen – hier wird als Platzhalter nur geloggt.
         3. Konsumieren.
         4. Sparen.
         5. Arbeitskraft anbieten.
        """
        log(f"Household {self.unique_id} starting step {current_step}.", level="INFO")
        self.receive_income()
        if state:
            self.pay_taxes(state)
        self.consume()
        self.save()
        self.offer_labor()
        log(f"Household {self.unique_id} completed step {current_step}.", level="INFO")
