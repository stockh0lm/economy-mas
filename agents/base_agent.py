class BaseAgent:
    def __init__(self, unique_id):
        self.unique_id = unique_id

    def step(self, current_step):
        # Grundverhalten – kann in Subklassen überschrieben werden
        print(f"Agent {self.unique_id} performs step {current_step}.")
