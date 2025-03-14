# environmental_agency.py
from typing import Protocol, TypeAlias, cast, runtime_checkable
from .base_agent import BaseAgent
from logger import log
from config import CONFIG


@runtime_checkable
class EnvironmentalImpactAgent(Protocol):
    """Protocol for agents that have environmental impact"""
    unique_id: str
    environmental_impact: float


@runtime_checkable
class BillingAgent(Protocol):
    """Protocol for agents that can be billed"""
    unique_id: str
    balance: float


class BillableImpactAgent(EnvironmentalImpactAgent, BillingAgent):
    """Protocol for agents with both environmental impact and billing capability"""
    pass


# Type aliases for improved readability
AgentWithImpact: TypeAlias = EnvironmentalImpactAgent
AgentWithBalance: TypeAlias = BillableImpactAgent


class EnvironmentalAgency(BaseAgent):
    """
    Monitors environmental standards and collects environmental taxes.
    """

    def __init__(self, unique_id: str) -> None:
        """
        Initialize an environmental agency with standard parameters.

        Args:
            unique_id: Unique identifier for this agency
        """
        super().__init__(unique_id)

        # Environmental standards from configuration
        self.env_standards: dict[str, float] = {
            "max_environmental_impact": CONFIG.get("max_environmental_impact", 10.0)
        }

        # Accumulated environmental taxes
        self.collected_env_tax: float = 0.0

        # Penalty factor from configuration
        self.penalty_factor: float = CONFIG.get("penalty_factor_env_audit", 5.0)

    def set_env_standards(self, standards_dict: dict[str, float]) -> None:
        """
        Update environmental standards with new values.

        Args:
            standards_dict: Dictionary of standard names and their values
        """
        self.env_standards.update(standards_dict)
        log(f"EnvironmentalAgency {self.unique_id} set new environmental standards: {self.env_standards}.",
            level="INFO")

    def collect_env_tax(self, agents: list[AgentWithImpact]) -> float:
        """
        Collect environmental tax from agents based on their impact.

        Args:
            agents: Collection of agents with environmental impact

        Returns:
            Total environmental tax collected in this operation
        """
        tax_rate: float = CONFIG.get("tax_rates", {}).get("umweltsteuer", 0.02)
        total_tax: float = 0.0

        for agent in agents:
            # Calculate tax based on environmental impact
            tax: float = agent.environmental_impact * tax_rate
            total_tax += tax

            # Deduct tax from agent's balance if available
            if isinstance(agent, BillingAgent):
                billing_agent = cast(BillingAgent, agent)
                billing_agent.balance -= tax

            log(f"EnvironmentalAgency {self.unique_id} collected {tax:.2f} env tax from agent {agent.unique_id}.",
                level="INFO")

        self.collected_env_tax += total_tax
        log(f"EnvironmentalAgency {self.unique_id} total collected env tax: {self.collected_env_tax:.2f}.",
            level="INFO")

        return total_tax

    def audit_company(self, company: AgentWithImpact) -> float:
        """
        Audit a company for environmental compliance and impose penalties if needed.

        Args:
            company: Company to audit for environmental compliance

        Returns:
            Amount of penalty imposed (0.0 if compliant)
        """
        max_impact: float = self.env_standards.get("max_environmental_impact", 10.0)

        if company.environmental_impact > max_impact:
            # Calculate penalty based on excess impact
            excess: float = company.environmental_impact - max_impact
            penalty: float = excess * self.penalty_factor

            # Apply penalty if company has balance attribute
            if isinstance(company, BillingAgent):
                billing_company = cast(BillingAgent, company)
                billing_company.balance -= penalty

            log(f"EnvironmentalAgency {self.unique_id} audited company {company.unique_id} and imposed "
                f"a penalty of {penalty:.2f} for excess environmental impact.",
                level="WARNING")

            return penalty
        else:
            log(f"EnvironmentalAgency {self.unique_id} audited company {company.unique_id}: Compliance confirmed.",
                level="DEBUG")

            return 0.0

    def step(self, current_step: int, agents: list[AgentWithImpact]) -> None:
        """
        Execute one simulation step for the environmental agency.

        Args:
            current_step: Current simulation step number
            agents: Collection of agents to monitor and tax
        """
        log(f"EnvironmentalAgency {self.unique_id} starting step {current_step}.", level="INFO")

        # Collect environmental taxes
        self.collect_env_tax(agents)

        # Audit all agents with environmental_impact attribute
        for agent in agents:
            self.audit_company(agent)

        log(f"EnvironmentalAgency {self.unique_id} completed step {current_step}.", level="INFO")


class RecyclingCompany(BaseAgent):
    """
    Collects and processes waste into recycled materials.
    """

    def __init__(
        self,
        unique_id: str,
        recycling_efficiency: float | None = None
    ) -> None:
        """
        Initialize a recycling company with specified efficiency.

        Args:
            unique_id: Unique identifier for this company
            recycling_efficiency: Percentage of waste that can be recycled (0.0-1.0)
        """
        super().__init__(unique_id)

        # Set recycling efficiency from config or parameter
        self.recycling_efficiency: float = (
            recycling_efficiency if recycling_efficiency is not None
            else CONFIG.get("recycling_efficiency", 0.8)
        )

        # Operating metrics
        self.waste_collected: float = 0.0
        self.processed_materials: float = 0.0

    def collect_waste(self, source: BaseAgent, waste_amount: float) -> float:
        """
        Collect waste from an agent and add it to the collection pool.

        Args:
            source: Agent providing the waste
            waste_amount: Amount of waste to collect

        Returns:
            Amount of waste actually collected
        """
        if waste_amount <= 0:
            log(f"RecyclingCompany {self.unique_id}: Cannot collect negative or zero waste amount.",
                level="WARNING")
            return 0.0

        self.waste_collected += waste_amount

        log(f"RecyclingCompany {self.unique_id} collected {waste_amount:.2f} units of waste from "
            f"{source.unique_id}. Total waste: {self.waste_collected:.2f}.",
            level="INFO")

        return waste_amount

    def process_recycling(self) -> float:
        """
        Process collected waste into recycled materials.

        Returns:
            Amount of recycled materials produced
        """
        if self.waste_collected <= 0:
            log(f"RecyclingCompany {self.unique_id}: No waste to process.",
                level="DEBUG")
            return 0.0

        processed: float = self.waste_collected * self.recycling_efficiency
        self.processed_materials += processed

        log(f"RecyclingCompany {self.unique_id} processed {processed:.2f} units of waste into "
            f"recycled materials. Total processed: {self.processed_materials:.2f}.",
            level="INFO")

        # Reset collected waste after processing
        self.waste_collected = 0.0

        return processed

    def report_materials(self) -> float:
        """
        Report the amount of recycled materials available.

        Returns:
            Current quantity of processed recycled materials
        """
        log(f"RecyclingCompany {self.unique_id} reports {self.processed_materials:.2f} "
            f"units of recycled materials available.",
            level="INFO")

        return self.processed_materials

    def step(self, current_step: int) -> None:
        """
        Execute one simulation step for the recycling company.

        Args:
            current_step: Current simulation step number
        """
        log(f"RecyclingCompany {self.unique_id} starting step {current_step}.", level="INFO")

        # Process waste if available
        if self.waste_collected > 0:
            self.process_recycling()
        else:
            log(f"RecyclingCompany {self.unique_id} has no waste to process at step {current_step}.",
                level="DEBUG")

        # Report available materials
        self.report_materials()

        log(f"RecyclingCompany {self.unique_id} completed step {current_step}.", level="INFO")