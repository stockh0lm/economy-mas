# labor_market.py
from dataclasses import dataclass
from typing import Protocol

from config import CONFIG_MODEL, SimulationConfig
from logger import log

from .base_agent import BaseAgent


class EmployerProtocol(Protocol):
    """Protocol defining the requirements for employer agents"""

    unique_id: str

    def add_employee_from_labor_market(self, worker: "WorkerProtocol", wage: float) -> None: ...


class WorkerProtocol(Protocol):
    """Protocol defining the requirements for worker agents"""

    unique_id: str
    employed: bool
    current_wage: float | None


@dataclass
class JobOffer:
    """Represents a job offer in the labor market"""

    employer: EmployerProtocol
    wage: float
    positions: int


WorkerMatchResult = tuple[WorkerProtocol, EmployerProtocol, float]


class LaborMarket(BaseAgent):
    """
    Manages job offers and worker matching in the economic simulation.

    Handles:
    - Registration of job offers from employers
    - Registration of workers seeking employment
    - Matching workers to available job positions
    - Setting default wage levels for unmatched workers
    """

    def __init__(self, unique_id: str, config: SimulationConfig | None = None) -> None:
        """
        Initialize a labor market.

        Args:
            unique_id: Unique identifier for this labor market
        """
        super().__init__(unique_id)
        self.job_offers: list[JobOffer] = []
        self.registered_workers: list[WorkerProtocol] = []

        self.config: SimulationConfig = config or CONFIG_MODEL

        # Configuration parameters
        self.default_wage: float = self.config.default_wage
        self.minimum_wage_floor: float = self.config.minimum_wage_floor
        self.wage_unemployment_sensitivity: float = self.config.wage_unemployment_sensitivity
        self.wage_price_index_sensitivity: float = self.config.wage_price_index_sensitivity
        self.target_unemployment_rate: float = self.config.target_unemployment_rate
        self.target_inflation_rate: float = self.config.target_inflation_rate
        self.latest_unemployment_rate: float = 0.0
        self.config_default_wage: float = self.default_wage

    def release_worker(self, worker: WorkerProtocol) -> None:
        """Mark a worker as unemployed so they can be matched again."""
        worker.employed = False
        worker.current_wage = None
        log(
            f"LaborMarket {self.unique_id}: Worker {worker.unique_id} released back to market.",
            level="INFO",
        )

    def register_job_offer(
        self, employer: EmployerProtocol, wage: float, positions: int = 1
    ) -> None:
        """
        Register a job offer from an employer.

        Args:
            employer: The company or entity offering the job
            wage: The offered wage amount
            positions: Number of positions available (default: 1)
        """
        offer = JobOffer(employer=employer, wage=wage, positions=positions)
        self.job_offers.append(offer)
        log(
            f"LaborMarket {self.unique_id}: Registered job offer from employer {employer.unique_id} "
            f"with wage {wage:.2f} and {positions} positions.",
            level="INFO",
        )

    def register_worker(self, worker: WorkerProtocol) -> None:
        """
        Register a worker seeking employment.

        Args:
            worker: Worker agent looking for employment
        """
        if worker not in self.registered_workers:
            self.registered_workers.append(worker)
            log(
                f"LaborMarket {self.unique_id}: Registered worker {worker.unique_id}.", level="INFO"
            )

    def compute_unemployment_rate(self) -> float:
        total_workers: int = len(self.registered_workers)
        if total_workers == 0:
            return 0.0
        unemployed = sum(
            1 for worker in self.registered_workers if not getattr(worker, "employed", False)
        )
        return unemployed / total_workers

    def apply_macro_wage_adjustment(
        self,
        price_index: float | None = None,
        unemployment_rate: float | None = None,
        wage_override: float | None = None,
    ) -> None:
        if wage_override is not None:
            self.default_wage = max(self.minimum_wage_floor, wage_override)
            log(
                f"LaborMarket {self.unique_id}: Default wage overridden to {self.default_wage:.2f} from external signal.",
                level="INFO",
            )
            return
        price_reference = price_index if price_index is not None else 100.0
        unemployment = (
            unemployment_rate if unemployment_rate is not None else self.latest_unemployment_rate
        )
        unemployment_gap = unemployment - self.target_unemployment_rate
        if price_reference <= 0:
            price_reference = 100.0
        price_gap = (price_reference / 100.0) - (1 + self.target_inflation_rate)
        adjustment = 1.0 - self.wage_unemployment_sensitivity * unemployment_gap
        adjustment -= self.wage_price_index_sensitivity * price_gap
        adjusted_wage = max(self.minimum_wage_floor, self.config_default_wage * adjustment)
        self.default_wage = adjusted_wage
        log(
            f"LaborMarket {self.unique_id}: Adjusted default wage to {self.default_wage:.2f} (price_index={price_reference:.2f}, unemployment={unemployment:.2%}).",
            level="INFO",
        )

    def match_workers_to_jobs(self) -> list[WorkerMatchResult]:
        """
        Match registered workers to available job positions.

        For each job offer, available workers are assigned until all positions are filled
        or no more workers are available. Each matched worker is marked as employed
        and assigned their wage.

        Returns:
            List of successful matches as (worker, employer, wage) tuples
        """
        matches: list[WorkerMatchResult] = []

        for offer in self.job_offers:
            available_workers = [
                w for w in self.registered_workers if not hasattr(w, "employed") or not w.employed
            ]
            num_matches = min(offer.positions, len(available_workers))

            for i in range(num_matches):
                worker = available_workers[i]
                worker.employed = True
                worker.current_wage = offer.wage
                offer.employer.add_employee_from_labor_market(worker, offer.wage)
                matches.append((worker, offer.employer, offer.wage))
                log(
                    f"LaborMarket {self.unique_id}: Matched worker {worker.unique_id} "
                    f"with employer {offer.employer.unique_id} at wage {offer.wage:.2f}.",
                    level="INFO",
                )

        # Clear job offers after matching
        self.job_offers = []
        return matches

    def set_wage_levels(self) -> None:
        """
        Set default wage for all unmatched workers.

        Workers without a current wage are assigned the default wage from configuration.
        """
        for worker in self.registered_workers:
            if (
                not hasattr(worker, "current_wage") or worker.current_wage is None
            ) and not worker.employed:
                worker.current_wage = self.default_wage
                log(
                    f"LaborMarket {self.unique_id}: Set default wage {self.default_wage:.2f} "
                    f"for worker {worker.unique_id}.",
                    level="INFO",
                )

    def step(
        self,
        current_step: int,
        price_index: float | None = None,
        unemployment_rate: float | None = None,
        wage_override: float | None = None,
    ) -> None:
        """
        Execute one simulation step for the labor market.

        During each step:
        1. Match workers to available job positions
        2. Set default wages for unmatched workers
        3. Log matching statistics

        Args:
            current_step: Current simulation step number
            :param current_step:
            :param wage_override:
            :param unemployment_rate:
            :param price_index:
        """
        log(f"LaborMarket {self.unique_id} starting step {current_step}.", level="INFO")

        matches = self.match_workers_to_jobs()
        self.latest_unemployment_rate = self.compute_unemployment_rate()
        self.apply_macro_wage_adjustment(price_index, unemployment_rate, wage_override)
        self.set_wage_levels()

        log(
            f"LaborMarket {self.unique_id} completed step {current_step}. "
            f"{len(matches)} job matches made (unemployment {self.latest_unemployment_rate:.2%}).",
            level="INFO",
        )
