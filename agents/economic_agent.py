from .base_agent import BaseAgent

class EconomicAgent(BaseAgent):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        # Zusätzliche Attribute für ökonomische Agenten
        self.balance = 0

    def step(self, current_step):
        # Beispielhafte wirtschaftliche Aktion: Balance aktualisieren
        self.balance += 1  # Dummy-Update, später z.B. Interaktionen, Kredite, etc.
        print(f"Economic Agent {self.unique_id}: balance = {self.balance} at step {current_step}.")
