from .base_agent import BaseAgent
from logger import log
from config import CONFIG

class EnvironmentalAgency(BaseAgent):
    def __init__(self, unique_id):
        super().__init__(unique_id)
        # Umweltstandards, z. B. maximal erlaubter Umweltimpact pro Unternehmen
        self.env_standards = {
            "max_environmental_impact": CONFIG.get("max_environmental_impact", 10)
        }
        # Hier werden die eingesammelten Umweltsteuern akkumuliert.
        self.collected_env_tax = 0.0

    def set_env_standards(self, standards_dict):
        """
        Ermöglicht das Setzen bzw. Aktualisieren der Umweltstandards.
        """
        self.env_standards.update(standards_dict)
        log(f"EnvironmentalAgency {self.unique_id} set new environmental standards: {self.env_standards}.", level="INFO")

    def collect_env_tax(self, agents):
        """
        Iteriert über übergebene Agenten (z. B. Unternehmen, Haushalte) und sammelt
        eine Umweltsteuer basierend auf ihrem 'environment_impact'. Der Steuersatz
        wird aus der Konfiguration gelesen (z. B. 0.02).
        """
        tax_rate = CONFIG.get("tax_rates", {}).get("umweltsteuer", 0.02)
        total_tax = 0.0
        for agent in agents:
            if hasattr(agent, "environment_impact"):
                # Steuerbetrag basiert auf dem Umweltimpact
                tax = agent.environment_impact * tax_rate
                total_tax += tax
                # Falls der Agent über ein Konto verfügt, wird der Steuerbetrag abgezogen
                if hasattr(agent, "balance"):
                    agent.balance -= tax
                log(f"EnvironmentalAgency {self.unique_id} collected {tax:.2f} env tax from agent {agent.unique_id}.", level="INFO")
        self.collected_env_tax += total_tax
        log(f"EnvironmentalAgency {self.unique_id} total collected env tax: {self.collected_env_tax:.2f}.", level="INFO")
        return total_tax

    def audit_company(self, company):
        """
        Prüft, ob das Unternehmen die Umweltstandards einhält. Liegt der
        'environmental_impact' über dem erlaubten Maximum, wird ein Strafbetrag
        (hier als Differenz mal einem Straffaktor) erhoben und dem Staat bzw.
        der Clearingstelle gemeldet.
        """
        max_impact = self.env_standards.get("max_environmental_impact", 10)
        if hasattr(company, "environmental_impact") and company.environmental_impact > max_impact:
            # Straffaktor als Platzhalter, z. B. 5 Einheiten pro überschrittenem Impact-Punkt
            penalty_factor = 5
            excess = company.environmental_impact - max_impact
            penalty = excess * penalty_factor
            if hasattr(company, "balance"):
                company.balance -= penalty
            log(f"EnvironmentalAgency {self.unique_id} audited company {company.unique_id} and imposed a penalty of {penalty:.2f} for excess environmental impact.", level="WARNING")
            return penalty
        else:
            log(f"EnvironmentalAgency {self.unique_id} audited company {company.unique_id}: Compliance confirmed.", level="DEBUG")
            return 0.0

    def step(self, current_step, agents):
        """
        Simulationsschritt der EnvironmentalAgency:
          1. Umweltsteuern von relevanten Agenten einziehen.
          2. Unternehmen auditen und bei Überschreitungen Strafzahlungen erheben.
          3. (Platzhalter) Weitere Aufgaben, z. B. Beratung oder Subventionierung, können hier ergänzt werden.
        """
        log(f"EnvironmentalAgency {self.unique_id} starting step {current_step}.", level="INFO")
        self.collect_env_tax(agents)
        # Audit alle Unternehmen (angenommen, Unternehmen besitzen das Attribut 'environmental_impact')
        for agent in agents:
            if hasattr(agent, "environmental_impact"):
                self.audit_company(agent)
        log(f"EnvironmentalAgency {self.unique_id} completed step {current_step}.", level="INFO")


class RecyclingCompany(BaseAgent):
    def __init__(self, unique_id, recycling_efficiency=0.8):
        """
        Parameter:
          recycling_efficiency: Anteil der Abfälle, der zu wiederverwertbaren Materialien verarbeitet wird.
        """
        super().__init__(unique_id)
        self.recycling_efficiency = recycling_efficiency
        self.waste_collected = 0.0
        self.processed_materials = 0.0

    def collect_waste(self, source, waste_amount):
        """
        Simuliert die Sammlung von Abfällen von einem Agenten (z. B. Unternehmen oder Haushalt).
        Der gesammelte Abfall wird zum internen Pool hinzugefügt.
        """
        self.waste_collected += waste_amount
        log(f"RecyclingCompany {self.unique_id} collected {waste_amount:.2f} units of waste from {source.unique_id}. Total waste: {self.waste_collected:.2f}.", level="INFO")
        return waste_amount

    def process_recycling(self):
        """
        Verarbeitet den gesammelten Abfall. Ein Teil des Abfalls wird gemäß der Recyclingeffizienz
        in wiederverwertbare Materialien umgewandelt.
        """
        processed = self.waste_collected * self.recycling_efficiency
        self.processed_materials += processed
        log(f"RecyclingCompany {self.unique_id} processed {processed:.2f} units of waste into recycled materials. Total processed: {self.processed_materials:.2f}.", level="INFO")
        # Nach der Verarbeitung wird der gesammelte Abfall reduziert
        self.waste_collected = 0.0
        return processed

    def report_materials(self):
        """
        Gibt die Menge der recycelten Materialien zurück, die als Input für nachhaltige
        Produktionsprozesse oder zur Weiterverwertung dienen können.
        """
        log(f"RecyclingCompany {self.unique_id} reports {self.processed_materials:.2f} units of recycled materials available.", level="INFO")
        return self.processed_materials

    def step(self, current_step):
        """
        Simulationsschritt der RecyclingCompany:
          1. Verarbeitet gesammelt Abfall (falls vorhanden).
          2. Meldet die verarbeiteten Materialien.
          3. (Platzhalter) Weitere Interaktionen, z. B. Wettbewerb mit anderen Recyclingunternehmen.
        """
        log(f"RecyclingCompany {self.unique_id} starting step {current_step}.", level="INFO")
        if self.waste_collected > 0:
            self.process_recycling()
        else:
            log(f"RecyclingCompany {self.unique_id} has no waste to process at step {current_step}.", level="DEBUG")
        self.report_materials()
        log(f"RecyclingCompany {self.unique_id} completed step {current_step}.", level="INFO")
