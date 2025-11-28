# labor_market.py
from dataclasses import dataclass
from typing import Protocol, TypeAlias, List, Optional, Tuple
from .base_agent import BaseAgent
from logger import log
from config import CONFIG


class EmployerProtocol(Protocol):
    """Protocol defining the requirements for employer agents"""
    unique_id: str

    def add_employee_from_labor_market(self, worker: "WorkerProtocol", wage: float) -> None: ...


class WorkerProtocol(Protocol):
    """Protocol defining the requirements for worker agents"""
    unique_id: str
    employed: bool
    current_wage: Optional[float]


@dataclass
class JobOffer:
    """Represents a job offer in the labor market"""
    employer: EmployerProtocol
    wage: float
    positions: int


WorkerMatchResult: TypeAlias = Tuple[WorkerProtocol, EmployerProtocol, float]


class LaborMarket(BaseAgent):
    """
    Manages job offers and worker matching in the economic simulation.

    Handles:
    - Registration of job offers from employers
    - Registration of workers seeking employment
    - Matching workers to available job positions
    - Setting default wage levels for unmatched workers
    """

    def __init__(self, unique_id: str) -> None:
        """
        Initialize a labor market.

        Args:
            unique_id: Unique identifier for this labor market
        """
        super().__init__(unique_id)
        self.job_offers: List[JobOffer] = []
        self.registered_workers: List[WorkerProtocol] = []

        # Configuration parameters
        self.default_wage: float = CONFIG.get("default_wage", 10)  # Default wage for unmatched workers

    def release_worker(self, worker: WorkerProtocol) -> None:
        """Mark a worker as unemployed so they can be matched again."""
        worker.employed = False
        worker.current_wage = None
        log(
            f"LaborMarket {self.unique_id}: Worker {worker.unique_id} released back to market.",
            level="INFO"
        )

    def register_job_offer(self, employer: EmployerProtocol, wage: float, positions: int = 1) -> None:
        """
        Register a job offer from an employer.

        Args:
            employer: The company or entity offering the job
            wage: The offered wage amount
            positions: Number of positions available (default: 1)
        """
        offer = JobOffer(employer=employer, wage=wage, positions=positions)
        self.job_offers.append(offer)
        log(f"LaborMarket {self.unique_id}: Registered job offer from employer {employer.unique_id} "
            f"with wage {wage:.2f} and {positions} positions.",
            level="INFO")

    def register_worker(self, worker: WorkerProtocol) -> None:
        """
        Register a worker seeking employment.

        Args:
            worker: Worker agent looking for employment
        """
        if worker not in self.registered_workers:
            self.registered_workers.append(worker)
            log(f"LaborMarket {self.unique_id}: Registered worker {worker.unique_id}.", level="INFO")

    def match_workers_to_jobs(self) -> List[WorkerMatchResult]:
        """
        Match registered workers to available job positions.

        For each job offer, available workers are assigned until all positions are filled
        or no more workers are available. Each matched worker is marked as employed
        and assigned their wage.

        Returns:
            List of successful matches as (worker, employer, wage) tuples
        """
        matches: List[WorkerMatchResult] = []

        for offer in self.job_offers:
            available_workers = [w for w in self.registered_workers if not hasattr(w, 'employed') or not w.employed]
            num_matches = min(offer.positions, len(available_workers))

            for i in range(num_matches):
                worker = available_workers[i]
                worker.employed = True
                worker.current_wage = offer.wage
                offer.employer.add_employee_from_labor_market(worker, offer.wage)
                matches.append((worker, offer.employer, offer.wage))
                log(f"LaborMarket {self.unique_id}: Matched worker {worker.unique_id} "
                    f"with employer {offer.employer.unique_id} at wage {offer.wage:.2f}.",
                    level="INFO")

        # Clear job offers after matching
        self.job_offers = []
        return matches

    def set_wage_levels(self) -> None:
        """
        Set default wage for all unmatched workers.

        Workers without a current wage are assigned the default wage from configuration.
        """
        for worker in self.registered_workers:
            if (not hasattr(worker, "current_wage") or worker.current_wage is None) and not worker.employed:
                worker.current_wage = self.default_wage
                log(f"LaborMarket {self.unique_id}: Set default wage {self.default_wage:.2f} "
                    f"for worker {worker.unique_id}.",
                    level="INFO")

    def step(self, current_step: int) -> None:
        """
        Execute one simulation step for the labor market.

        During each step:
        1. Match workers to available job positions
        2. Set default wages for unmatched workers
        3. Log matching statistics

        Args:
            current_step: Current simulation step number
        """
        log(f"LaborMarket {self.unique_id} starting step {current_step}.", level="INFO")

        matches = self.match_workers_to_jobs()
        self.set_wage_levels()

        log(f"LaborMarket {self.unique_id} completed step {current_step}. "
            f"{len(matches)} job matches made.",
            level="INFO")