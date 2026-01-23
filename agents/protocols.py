"""Comprehensive agent protocols module for type-safe agent interactions."""

from typing import Protocol, runtime_checkable
from typing_extensions import TypedDict
from config import SimulationConfig

@runtime_checkable
class AgentWithBalance(Protocol):
    """Protocol for agents that have a balance."""
    balance: float

@runtime_checkable
class AgentWithImpact(Protocol):
    """Protocol for agents with environmental impact."""
    environmental_impact: float

@runtime_checkable
class MerchantProtocol(Protocol):
    """Protocol for agents that can request funds from banks."""
    def request_funds_from_bank(self, amount: float) -> float:
        ...

@runtime_checkable
class InventoryMerchant(MerchantProtocol, Protocol):
    """Protocol for merchants with inventory management."""
    inventory: float

@runtime_checkable
class LiquidityAgent(Protocol):
    """Protocol for agents that manage liquidity."""
    def balance_liquidity(self) -> None:
        ...

@runtime_checkable
class WealthAgent(Protocol):
    """Protocol for agents with wealth management capabilities."""
    balance: float

@runtime_checkable
class EnvironmentalImpactAgent(Protocol):
    """Protocol for agents with environmental impact."""
    environmental_impact: float

@runtime_checkable
class BillingAgent(Protocol):
    """Protocol for agents that can be billed."""
    def pay_bill(self, amount: float) -> float:
        ...

class BillableImpactAgent(EnvironmentalImpactAgent, BillingAgent):
    """Protocol for agents that can be billed for environmental impact."""
    pass

@runtime_checkable
class HasUniqueID(Protocol):
    """Protocol for agents with unique identifiers."""
    unique_id: str

@runtime_checkable
class BorrowerAgent(HasUniqueID, Protocol):
    """Protocol for agents that can borrow from banks."""
    def request_funds_from_bank(self, amount: float) -> float:
        ...

@runtime_checkable
class EmployerProtocol(Protocol):
    """Protocol for employers in the labor market."""
    def add_employee_from_labor_market(self, worker: "WorkerProtocol", wage: float) -> None:
        ...

@runtime_checkable
class WorkerProtocol(Protocol):
    """Protocol for workers in the labor market."""
    employed: bool
    current_wage: float | None

@runtime_checkable
class AssetPortfolioAgent(Protocol):
    """Protocol for agents with asset portfolios."""
    balance: float

@runtime_checkable
class TaxableAgent(Protocol):
    """Protocol for agents that pay taxes."""
    def pay_taxes(self, state: object) -> None:
        ...

@runtime_checkable
class AgentCollection(Protocol):
    """Protocol for collections of agents."""
    def __iter__(self):
        ...

class WorkerMatchResult(TypedDict):
    """Result of worker matching in labor market."""
    worker: WorkerProtocol
    employer: EmployerProtocol
    wage: float
    success: bool

class JobOffer(TypedDict):
    """Job offer structure."""
    employer: EmployerProtocol
    wage: float
    positions: int
