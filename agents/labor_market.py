from .base_agent import BaseAgent
from logger import log
from config import CONFIG


class LaborMarket(BaseAgent):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        # Liste der registrierten Jobangebote; jedes Angebot ist ein Dictionary mit
        # 'employer' (Referenz zum anbietenden Unternehmen), 'wage' und 'positions'
        self.job_offers = []
        # Liste der registrierten arbeitssuchenden Agenten (z. B. Haushalte)
        self.registered_workers = []

    def register_job_offer(self, employer, wage, positions=1):
        """
        Ein Unternehmen (employer) registriert ein Jobangebot mit einem bestimmten
        Lohn (wage) und einer Anzahl von Positionen.
        """
        offer = {'employer': employer, 'wage': wage, 'positions': positions}
        self.job_offers.append(offer)
        log(f"LaborMarket {self.unique_id}: Registered job offer from employer {employer.unique_id} with wage {wage} and {positions} positions.",
            level="INFO")

    def register_worker(self, worker):
        """
        Registriert einen arbeitssuchenden Haushalt oder sonstigen Agenten.
        """
        if worker not in self.registered_workers:
            self.registered_workers.append(worker)
            log(f"LaborMarket {self.unique_id}: Registered worker {worker.unique_id}.", level="INFO")

    def match_workers_to_jobs(self):
        """
        Führt ein einfaches Matching zwischen Jobangeboten und registrierten Arbeitssuchenden durch.
        Für jedes Jobangebot werden verfügbare (arbeitslose) Worker zugeordnet, bis alle Positionen besetzt sind.
        Dabei wird dem Worker ein Attribut 'employed' (True) sowie ein 'current_wage' zugewiesen.
        """
        matches = []
        for offer in self.job_offers:
            positions = offer['positions']
            wage = offer['wage']
            employer = offer['employer']
            # Suche verfügbare Worker: wir gehen davon aus, dass ein Worker nicht 'employed' ist
            available_workers = [w for w in self.registered_workers if not hasattr(w, 'employed') or not w.employed]
            num_matches = min(positions, len(available_workers))
            for i in range(num_matches):
                worker = available_workers[i]
                worker.employed = True
                worker.current_wage = wage
                matches.append((worker, employer, wage))
                log(f"LaborMarket {self.unique_id}: Matched worker {worker.unique_id} with employer {employer.unique_id} at wage {wage}.",
                    level="INFO")
        # Nach Matching können die Jobangebote gelöscht werden, da sie besetzt wurden
        self.job_offers = []
        return matches

    def set_wage_levels(self, default_wage):
        """
        Setzt für alle registrierten, noch nicht beschäftigten Worker einen Mindestlohn,
        falls noch kein aktueller Lohn zugewiesen wurde.
        """
        for worker in self.registered_workers:
            if not hasattr(worker, 'current_wage') or worker.current_wage is None:
                worker.current_wage = default_wage
                log(f"LaborMarket {self.unique_id}: Set default wage {default_wage} for worker {worker.unique_id}.",
                    level="INFO")

    def step(self, current_step):
        """
        Simulationsschritt des Arbeitsmarktes:
         1. Zunächst werden alle registrierten Jobangebote gematcht.
         2. Anschließend wird für alle noch nicht besetzten Worker ein Mindestlohn gesetzt.
         3. Die Anzahl der gematchten Positionen wird geloggt.
        """
        log(f"LaborMarket {self.unique_id} starting step {current_step}.", level="INFO")
        matches = self.match_workers_to_jobs()
        default_wage = CONFIG.get("default_wage", 10)
        self.set_wage_levels(default_wage)
        log(f"LaborMarket {self.unique_id} completed step {current_step}. {len(matches)} job matches made.",
            level="INFO")
