# base_agent.py
class BaseAgent:
    def __init__(self, unique_id: str) -> None:
        self.unique_id: str = unique_id

    def step(self, current_step: int) -> None:
        print(f"Agent {self.unique_id} performs step {current_step}.")
