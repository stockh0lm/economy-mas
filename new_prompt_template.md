# Prompt: Wirtschaft-Simulator Refactor mit garantierten ZIP-Artefakten

Du bist ein Senior-Software-Engineer für simulationsbasierte Ökonomie (Python). Du arbeitest **in einer Sandbox mit Dateisystemzugriff**. Das Projekt liegt als ZIP vor: **/mnt/data/wirtschaft.zip**.

## Meta-Regeln (wichtig, um Abbrüche zu vermeiden)
1. **Arbeite in einem Durchlauf bis zum Ende** dieser Nachricht. Stelle **keine Rückfragen**, sondern triff sinnvolle Annahmen.
2. **Nach JEDEM Milestone** musst du:
   - das Projektzip **erzeugen** (Name exakt: `wirtschaftN.zip`)
   - den **Download-Link im Chat als Markdown-Link** ausgeben im Format:
     `- Milestone N: [Download wirtschaftN.zip](sandbox:/mnt/data/wirtschaftN.zip)`
3. **Nicht anhalten**, nachdem du einen Link ausgegeben hast. Fahre **automatisch** mit dem nächsten Milestone fort, bis Milestone 7 fertig ist oder du **hart blockiert** bist (z.B. Tests schlagen fehl und du kannst den Fehler nicht beheben).
4. Falls du **blockiert** bist:
   - Gib **trotzdem** alle bis dahin erzeugten ZIP-Links aus (im oben genannten Format)
   - Füge eine **kurze Blocker-Diagnose** und den **konkreten nächsten Patch-Schritt** hinzu.
5. Erzeuge ZIPs **wirklich auf dem Dateisystem** via Shell (`zip -r ...`) und prüfe anschließend, dass die Datei existiert (z.B. `ls -lh /mnt/data/wirtschaftN.zip`).

## Ziel
Die Simulation muss den Specs für ein alternatives Geldsystem entsprechen und „natürlich“ wirken:
- Je nach Parametern kann sie wachsen oder schrumpfen.
- Haushalte und Firmen entstehen/wachsen und sterben/gehen insolvent.
- **Geld entsteht nur** am **Retailer-Kontokorrent** beim **Warenkauf** und **verschwindet** beim Rückfluss/Write-Down/Decay.
- Keine Rückwärtskompatibilitätspflicht; Legacy-Code darf entfernt werden.
- **Agenten ausschließlich in `agents/`**.
- Code klar, lesbar, testbar.

## Zeitauflösung (global konsistent)
- 1 Step = 1 Tag
- 30 Tage = 1 Monat
- 12 Monate = 1 Jahr
- 1 Jahr = 360 Tage
- Monat/Quartal/Jahr-Prozesse werden über Tagessteps getriggert:
  - Monatsende alle 30 Tage
  - Jahresende alle 360 Tage
Nutze diese Konvention überall konsistent (Demografie, Sparen, Fees, Audits, Abschreibungen).

## Primäre Wahrheit
Die unten eingefügten **extrahierten Specs** sind die primäre Wahrheit. Greife nur im Zweifel auf `doc/Vorschlag für eine Geldreform*.txt` zurück.

## Bekannte Root Causes (müssen an der Wurzel behoben werden)
- Bugs: SavingsBank-Metrics, `total_savings` property, `Household.receive_income` überschreibt Baseline-Income

## Workflow
- Entpacken nach Arbeitsverzeichnis.
- Struktur bereinigen, Agenten nur in `agents/`, doppelte Root-Dateien entfernen.
- Zeitmodell zentral (SimulationClock/Calendar).
- Sim-Loop deterministisch als Pipeline pro Tag strukturieren.
- Kleine Runs (360–3600 Schritte), lange Runs mit wenigen Haushalten und Firmen um zu testen ob es Unstetigkeiten gibt, z.B. beim Ende von Haushaltsalter
- Output-Validierung mit pandas (SavingsBank > 0, MoneySupply plausibel, Velocity nicht kollabiert).
- Root Causes fixen, nicht Symptome.
- Dead Code konsequent entfernen, Docstrings schreiben, kein Fehlerabfangen mit try .. except, weil das fehler nur versteckt, nicht löst.

---

# Milestones (du arbeitest Milestone 1 → 7 in dieser Reihenfolge ab)

## Milestone 1 — Projekt entpacken
Aufgaben:
- `/mnt/data/wirtschaft.zip` entpacken.
- Stelle sicher: `python -m py_compile` und ein minimaler Run crashen nicht.

**Artefakt:** `wirtschaft1.zip` → Link ausgeben, dann weiter zu Milestone 2.

## Milestone 2 — Struktur bereinigen und Sim-Loop optimieren
Ziel: Saubere Projektstruktur und deterministische Simulation

Aufgaben:
- Agenten ausschließlich in `agents/` - doppelte Root-Dateien entfernen
- Sim-Loop deterministisch als Pipeline pro Tag strukturieren
- Dead Code konsequent entfernen
- Zeitmodell ist bereits zentralisiert (sim_clock.py existiert)

**Artefakt:** `wirtschaft2.zip` → Link ausgeben, dann weiter zu Milestone 3.

## Milestone 3 — Grundlegende Agenten-Refaktorierung
Ziel: Konsistente Agenten-IDs und Basis-Funktionalität

Aufgaben:
- Agent-IDs standardisieren: `household_<n>`, `company_<n>`, `retailer_<n>`
- Singleton-Agenten klar benennen (z.B. `state_0`, `clearing_0`)
- Basis-Agenten-Funktionalität testen
- Legacy-Bankpfade als deprecated markieren

**Artefakt:** `wirtschaft3.zip` → Link ausgeben, dann weiter zu Milestone 4.

## Milestone 4 — Sparen/Sparkasse + natürliches Mikroverhalten
Ziel: natürliche, fließende Veränderungen in den Metriken

Aufgaben:
- Household:
  - Baseline-Income nicht überschreiben (Bug fix).
  - `income_received_this_month`, `consumption_this_month` sammeln.
  - Sparentscheidung monatlich an Month-End (z.B. Sight-Balance über Puffer → Sparbetrag).
- SavingsBank:
  - `deposit()/withdraw()` korrekt, `total_savings` property korrekt.
  - Kreditvergabe nur aus `savings_pool`.
- Demografie:
  - Alterung pro Tag, Tod nach Wahrscheinlichkeit (altersabhängig).
  - Geburt/Neugründung optional (parametrisiert).
- Kleine Tests:
  - 360–720 Tage Run: Savings entsteht.
  - 10000 Tage Run: Trends prüfen. Sind Metrics stetig und differenzierbar? Wenn nein, warum nicht? Was ist die Wurzelursache?

**Artefakt:** `wirtschaft4.zip` → Link ausgeben, dann weiter zu Milestone 5.

## Milestone 5 — Metrics/Validation + Beispiel-Configs Wachstum/Shrink
Ziel: Simulation validierbar, aussagekräftige Outputs, 2 Beispiel-Configs

Aufgaben:
- `metrics.py` refaktorieren:
  - MoneySupply (M1 proxy) klar definieren.
  - CC Exposure, inventory_value_total, velocity_proxy.
  - SavingsBank.total_savings in CSV.
  - Insolvenzen/Deaths zählen.
  - optional Gini.
- `output/` sauber strukturieren:
  - Run-Folder mit Timestamp/Name.
  - CSVs: `macro.csv`, `banks.csv`, `agents_households.csv`, `agents_companies.csv`, `retailers.csv`.
- `analyze.py`: pandas liest CSVs, druckt Kurzzusammenfassung + Trendindikatoren.
- Beispiel-Configs:
  - `configs/growth.yaml`
  - `configs/shrink.yaml`
  - small-run defaults (z.B. 3600 Tage)
- Führe zwei kleine Runs aus und zeige Key-Trends kurz (Savings>0, MoneySupply, Velocity).

**Artefakt:** `wirtschaft5.zip` → Link ausgeben, dann weiter zu Milestone 6.

## Milestone 6 — Staat als realer Nachfrager und Dienstleistungs-Wertschöpfung
Ziel: Realwirtschaftliche Rückkopplung und Dienstleistungssektor

Aufgaben:
- Staat als realer Nachfrager implementieren:
  - State.procure_goods(retailers, amount, ...) Methode
  - Retailer.sell_to_state(state, budget) Methode
  - Güterfluss/Inventory muss mitgehen
  - Keine Geldschöpfung, nur Transfer
- Dienstleistungs-Wertschöpfung tracken:
  - Metriken: `service_value_total`, `goods_value_total`, `service_share_of_output`
  - `service_tx_volume` und `goods_tx_volume` separat erfassen
  - Service-Transaktionen beeinflussen Geldmenge nicht
- Tests:
  - State procurement Test: Inventory sinkt, Retailer.sight steigt, State.sight sinkt
  - Service-Output Test: GDP steigt durch Services, aber m1_proxy bleibt unverändert

**Artefakt:** `wirtschaft6.zip` → Link ausgeben, dann weiter zu Milestone 7.

## Milestone 7 — Sparkassen-Investitionskredite und cc_limit-Policy
Ziel: Firmen können bei Sparkasse Kredite für Investitionen aufnehmen

Aufgaben:
- Sparkassen-Investitionskredite für Companies:
  - Company kann Kredit für Investitionen beantragen
  - Kredit aus Savings-Pool
  - Produktivität/Capacity steigt nach Investition
  - Tilgung/Zins/Defaults modellieren
- cc_limit-Policy implementieren:
  - `cc_limit = m * avg_monthly_cogs` (rollierend)
  - Audit-Risk-Modifier
  - Nicht einseitig kündbar, aber abgestimmt anpassbar
- Tests:
  - Investitionskredit Test: Company nimmt Kredit, capacity steigt, active_loans steigt
  - cc_limit Policy Test: cc_limit passt sich an COGS an

**Artefakt:** `wirtschaft7.zip` → Link ausgeben.

---

# Nach Milestone 7: Refaktorierungsplan (Markdown)
Erstelle eine detaillierte Roadmap:
- Module, Zuständigkeiten, Tests, Erweiterungen (RetailerAgent als eigener Typ, InventoryLedger, Clearing-Audits etc.)
- Priorisierung P0/P1/P2
- Risiken und Validierungskriterien

---

# SPECS (Primäre Wahrheit)
...

---

# Issues.md Updates (nach Abschluss)
Nach Abschluss dieses Prompts sollen folgende Punkte in issues.md aktualisiert werden:

- [x] **Kontokorrent-Geldschöpfung nur im Einzelhandel** (abgeschlossen in Milestone 1-4)
- [x] **Geldvernichtung beim Rückstrom zum Kontokorrent** (abgeschlossen in Milestone 1-4)
- [x] **Kontogebühren statt Zinsen** (abgeschlossen in Milestone 1-4)
- [x] **Clearing-Reserve-Grenzen korrekt** (abgeschlossen in Milestone 1-4)
- [x] **Zeitliche Granularität** (abgeschlossen in Milestone 2)
- [x] **Örtliche Granularität** (abgeschlossen in Milestone 1-4)
- [x] **Metriken + Plots** (abgeschlossen in Milestone 5)
- [x] **Integrationstest Warengeld-Zyklus** (abgeschlossen in Milestone 4-5)
- [x] **Regressionstest Clearing-Reserve-Bounds** (abgeschlossen in Milestone 4-5)

Neue offene Punkte (werden in issues.md aktualisiert):
- [ ] **cc_limit-Policy / partnerschaftlicher Rahmen** (Milestone 7)
- [ ] **Warenbewertung & Abschreibung** (teilweise in Milestone 6-7)
- [ ] **Fraud/Wertberichtigung-Rechenregel** (offen bleibt)
- [ ] **Sparkassen-Regeln (Spargrenze / Invest-Nachfrage-Kopplung)** (Milestone 7)
- [ ] **Staat als realer Nachfrager im Warenkreislauf** (Milestone 6)
- [ ] **Dienstleistungs-Wertschöpfung abbilden/tracken** (Milestone 6)
- [ ] **Golden-run Snapshot** (offen bleibt)
- [ ] **Neuer Test: Staat kauft Waren bei Retailern** (Milestone 6)
- [ ] **Neuer Test: Sparkassen-Kredit -> Investition -> Produktivität** (Milestone 7)
- [ ] **Doppelte Paketstruktur konsolidieren** (offen bleibt)
- [ ] **Legacy-Bankpfade deprecaten** (Milestone 3)
- [ ] **Einheitliche Balance-Sheet-Namen** (offen bleibt)
- [ ] **Konfig-Konsistenz** (offen bleibt)
- [ ] **FinancialMarket abschalten** (offen bleibt)
- [ ] **Agent-IDs standardisieren** (Milestone 3)
- [ ] **scripts/plot_metrics.py anpassen** (offen bleibt)
- [ ] **scripts/plot_metrics.py auf pandas umstellen** (offen bleibt)

---

# Technische Schuld vs. Neue Funktionalität
Dieses Arbeitspaket mischt gezielt:
- **Technische Schuld Reduktion** (Milestone 2-3, 6-7):
  - Struktur bereinigen
  - Legacy-Code entfernen
  - Agent-IDs standardisieren
  - cc_limit-Policy implementieren
- **Neue wichtige Funktionalität** (Milestone 5-7):
  - Metrics/Validation Framework
  - Staat als realer Nachfrager
  - Dienstleistungs-Wertschöpfung
  - Sparkassen-Investitionskredite

Diese Mischung stellt sicher, dass die Codebasis sauber bleibt, während gleichzeitig wichtige neue Features hinzugefügt werden.
