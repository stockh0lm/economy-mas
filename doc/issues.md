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

- [x] **cc_limit-Policy / partnerschaftlicher Rahmen**: `cc_limit` ist aktuell (meist) statisch aus Config/Template. Spec: nicht einseitig kündbar, aber abgestimmt anpassbar.
  - Vorschlag: `cc_limit = m * avg_monthly_cogs` (rollierend) + Audit-Risk-Modifier.

- [~] **Warenbewertung & Abschreibung**:
  - Status: Es existiert eine einfache Inventarbewertung "at cost" (`RetailerAgent.inventory_value`) + ein pauschaler Obsoleszenz-Write-down (`obsolescence_rate`).
  - Offene Spec-Fragen: Bewertungsregel (Einstand/Markt/Niederstwert), „unverkaufbar“-Kriterium, Artikelgruppen.

- [~] **Fraud/Wertberichtigung-Rechenregel**:
  - Status: Clearing hat eine implementierte, einfache Verlustallokation in `_apply_value_correction(...)` (Reserve → Retailer-Sicht → Empfänger-Haircut (pro-rata via Bank-Ledger) → Bankreserve).
  - Offene Spec-Fragen: exakte Rechts-/Buchungslogik, wie Haircuts fair/robust verteilt werden sollen.

- [ ] **Sparkassen-Regeln (Spargrenze / Invest-Nachfrage-Kopplung)**:
  - Status: Es gibt derzeit nur `max_savings_per_account` als rein technische Obergrenze.
  - Spec: Spargrenzen sollen politisches Steuerinstrument sein, gekoppelt an erwartete Kreditnachfrage.
- [ ] **max_savings_per_account ersetzen durch verschiedene konfigurierbare Obergrenzen für Haushalte und Unternehmen**
  - Aktuell: Einheitliche Obergrenze für alle Konten
  - Ziel: Getrennte, konfigurierbare Obergrenzen für Haushalte und Unternehmen
  - Begründung: Unterschiedliche Sparverhalten und politische Steuerungsbedürfnisse
  - keine rückwärtskompatibilität

---

## 3) Tests / Validierung

- [ ] **Golden-run Snapshot**
  - Ein kurzer Seeded-Run (z.B. 30 Tage) mit erwarteten Makro-Kennzahlen-Bändern.


---

## 4) Code-Smells / Komplexität / Refactor-Vorschläge (schlank halten)

- [ ] **Einheitliche Balance-Sheet-Namen (Company/Producer)**
  - TODO: konsistent `sight_balance` statt gemischter Namen.

- [ ] **FinancialMarket abschalten**
  - Spec-Interpretation: Börsenschließung / Finanzmarkt stark reduziert.
  - Status: `FinancialMarket` existiert noch als Agent; prüfen, ob er in `main.py` tatsächlich Einfluss hat oder nur noop ist.

- [ ] **Einfaches Wachstums- und Sterbe-Verhalten für Haushalte und Unternehmen implementieren**
  - Ziel: Implementierung von möglichst einfachem, in Finanz-Multi-Agenten-Systemen üblichem Wachstums- und Sterbe-Verhalten
  - Haushalts-Agent:
    - Natürliches Wachstum durch Geburten (basierend auf Alter, Einkommen, Sparverhalten)
    - Natürliches Sterben (basierend auf Alter und probabilistischen Mortalitätsmodellen)
    - Generationenwechsel mit realistischem Vermögensübergang
  - Unternehmens-Agent:
    - Gründungsmechanismen (basierend auf Marktchancen und Kapitalverfügbarkeit)
    - Insolvenzmechanismen (basierend auf Cashflow, Bilanzkennzahlen und Marktbedingungen)
    - Wachstum durch Expansion und Fusionen
  - Anforderungen:
    - Konfigurierbare Wachstums- und Sterberaten
    - Realistische Altersverteilung und Demografiedynamik
    - Integration mit bestehenden Wirtschaftskreisläufen
    - Kompatibilität mit Warengeld-Buchführungssystem
  - Priorität: Hoch (für realistischere Langzeit-Simulationen)

---

## 5) Neue ToDos (aus aktuellem Review)

- [ ] **Agent-IDs auf einfache Finance-Sim-Konvention standardisieren (`household_<n>`, `company_<n>`, `retailer_<n>`)**
  - Ziel: IDs sollen den üblichen Standards in Finanz-/ABM-Simulationen folgen: string-prefix + laufende Nummer.
  - Status:
    - Prefixe existieren bereits in `config.py`: `HOUSEHOLD_ID_PREFIX="household_"`, `COMPANY_ID_PREFIX="company_"`, `RETAILER_ID_PREFIX="retailer_"`.
    - Aber: Es gibt noch abweichende Sonder-IDs (`state`, `warengeld_bank_<region>` etc.) und Stellen, die IDs umbenennen (Births/Turnover).
  - TODO:
    - Sicherstellen, dass **alle** erzeugten Agenten-IDs strikt diesem Muster folgen (inkl. Neugeborene/Splits).
    - Für „singleton“-Agenten (state, clearing, labor_market) eine klare, ebenfalls standardisierte Notation festlegen (z.B. `state_0`, `clearing_0`, `labor_market_0`) oder bewusst als Ausnahme markieren.
