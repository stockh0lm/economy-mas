# Issues / Backlog (Warengeld-Simulation)

Stand: **2026-02-01**

Dieses Dokument ist ein Arbeits- und Fortschrittslog: offene Punkte, erledigte Fixes,
und konkrete nächste Schritte – mit Fokus auf **Schlankheit, Verständlichkeit, saubere Buchführung**.

## Status-Legende
- [ ] offen
- [~] in Arbeit
- [x] erledigt

---

## 1) Compliance-Fixes (gegen Buch/Spezifikation)


---

## 2) Abweichungen / Spec-Lücken (simulationskritisch)


---

## 3) Tests / Validierung



---

## 4) Code-Smells / Komplexität / Refactor-Vorschläge (schlank halten)

- [ ] **Einheitliche Balance-Sheet-Namen (Company/Producer)**
  - TODO: konsistent `sight_balance` statt gemischter Namen.

- [ ] **FinancialMarket abschalten**
  - Spec-Interpretation: Börsenschließung / Finanzmarkt stark reduziert.
  - Status: `FinancialMarket` existiert noch als Agent; prüfen, ob er in `main.py` tatsächlich Einfluss hat oder nur noop ist.


---

## 5) Neue ToDos (aus aktuellem Review)


- [ ] **Hyperinflation / Numerische Überläufe in Preisindex-Berechnung - KRITISCH**
  - **Problem**: Preisindex wächst exponentiell bis zu numerischem Overflow (1.5e+308 → inf)
  - **Symptom**: IndexError in matplotlib beim Plotten, da unendliche Werte nicht dargestellt werden können
  - **Root Cause Analysis**:
    - Preisindex-Berechnung in `metrics.py::_price_dynamics()` hat nur Untergrenze (`max(current_price, 0.01)`) aber keine Obergrenze
    - Preisdruck von 2.886 (sollte ~1.0 sein) führt zu 9.43% Preiswachstum pro Schritt
    - Nach ~700 Schritten führt dies zu numerischem Overflow
  - **Fundamentales Problem**: Verstoß gegen Warengeld-Prinzipien (siehe doc/specs.md):
    - Geldmenge sollte automatisch durch Warengeld-Mechanismen reguliert werden
    - Fehlende Implementierung kritischer Feedback-Mechanismen:
      1. **Automatische Kreditrückzahlung** (Section 4.2): Einzelhändler sollten Überschuss-Sichtguthaben für Kreditrückzahlung nutzen
      2. **Lagerbasierte Kreditlimits** (Section 4.1): Kreditlinien sollten an tatsächliche Lagerwerte gekoppelt sein
      3. **Wertberichtigungen** (Section 4.6): Unverkäufliche Waren sollten Geldvernichtung auslösen
      4. **Sichtguthaben-Abschmelzung** (Section 4.7): Überschüssige Sichtguthaben sollten automatisch abgebaut werden
  - **Aktuelle Situation**:
    - Geldmenge (M2) bleibt konstant bei 5362.89
    - GDP bleibt konstant bei 1857.97
    - Preisdruck = 5362.89 / 1857.97 ≈ 2.886 (viel zu hoch!)
    - Keine automatische Regulierung durch Warengeld-Mechanismen
  - **Lösungsvorschlag**:
    - **Kurzfristig** (Symptom-Behandlung): Obergrenze für Preisindex in `metrics.py` einführen
    - **Mittelfristig** (Ursachenbehandlung): Warengeld-Feedback-Mechanismen implementieren:
      ```python
      # 1. Automatische Kreditrückzahlung in bank.py
      def auto_repay_cc_from_sight(retailer):
          excess = max(0, retailer.sight_balance - retailer.sight_allowance)
          repay_amount = min(excess, abs(retailer.cc_balance))
          # Reduziert Geldmenge automatisch

      # 2. Lagerbasierte Kreditlimits in bank.py
      def enforce_inventory_backing(retailer):
          required_collateral = abs(retailer.cc_balance) * 1.2
          if retailer.inventory_value < required_collateral:
              # Erzwinge Kreditreduzierung = Geldvernichtung

      # 3. Wertberichtigungen in retailer_agent.py
      def apply_inventory_write_downs():
          # Abschreibungen auf unverkäufliche Waren → Geldvernichtung

      # 4. Sichtguthaben-Abschmelzung in metrics.py
      def apply_sight_decay(agents):
          # Überschüssige Sichtguthaben abbauen → Geldvernichtung
      ```
  - **Priorität**: KRITISCH - Blockiert Langzeit-Simulationen und Datenanalyse
  - **Betroffene Dateien**: `metrics.py`, `bank.py`, `retailer_agent.py`
  - **Tests**: Benötigt neue Tests für Geldmengen-Regulierung und Preisstabilität

  - **Reproduktion**:
    - **Befehl**: `python3 main.py --config configs/run_100yr_random.yaml`
    - **Konfiguration**: 36,000 Schritte, 50 Haushalte, 12 Unternehmen, 5 Einzelhändler, Seed=42
    - **Zeitpunkt des Auftretens**:
      - **Hyperinflation beginnt**: Schritt 2,623 (7.3% der Simulation)
      - **Exponentielles Wachstum**: Ab Schritt ~2,623 mit 9.43% Wachstum pro Schritt
      - **Numerischer Overflow**: Schritt 12,099 (33.6% der Simulation)
    - **Bedingungen beim Start der Hyperinflation**:
      - Preisindex: 151.25 (51% über Basiswert von 100)
      - Preisdruck: 1.3129 (sollte ~1.0 sein)
      - Inflationsrate: 1.56%
      - GDP: 1,356.79
      - Geldmenge (M2): 1,781.38
      - CC-Exposure: 2,354.31
      - Lagerwert: 555.99
    - **Endzustand vor Overflow**:
      - Letzter endlicher Preisindex: 1.65e+308
      - Durchschnittliche Wachstumsrate in exponentieller Phase: 9.43% pro Schritt
      - Dauer von Hyperinflationsbeginn bis Overflow: 9,476 Schritte
    - **Erwartetes Verhalten**: Preisindex sollte stabil bleiben oder nur moderat wachsen, da Warengeld-System Preisstabilität durch Geldmengen-Kopplung an Warenwerte gewährleisten sollte
