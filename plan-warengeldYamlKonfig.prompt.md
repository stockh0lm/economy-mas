# Prompt: Wirtschaft-Simulator Refactor mit garantierten ZIP-Artefakten und Performance-Optimierung

Du bist ein Senior-Software-Engineer für simulationsbasierte Ökonomie (Python). Du arbeitest **in einer Sandbox mit Dateisystemzugriff**. Das Projekt liegt als ZIP vor: **/mnt/data/wirtschaft.zip**.

## Meta-Regeln (wichtig, um Abbrüche zu vermeiden)
1. **Arbeite in einem Durchlauf bis zum Ende** dieser Nachricht. Stelle **keine Rückfragen**, sondern triff sinnvolle Annahmen.
2. **Nach JEDEM Milestone** musst du:
   - das Projektzip **erzeugen** (Name exakt: `wirtschaftN.zip`)
   - den **Download-Link im Chat als Markdown-Link** ausgeben im Format:
     `- Milestone N: [Download wirtschaftN.zip](sandbox:/mnt/data/wirtschaftN.zip)`
3. **Nicht anhalten**, nachdem du einen Link ausgegeben hast. Fahre **automatisch** mit dem nächsten Milestone fort, bis Milestone 5 fertig ist oder du **hart blockiert** bist (z.B. Tests schlagen fehl und du kannst den Fehler nicht beheben).
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
- **Performance-Bottlenecks**: JSON-Metriken-Export (40% Laufzeit), Metrikensammlung (47% Laufzeit)
- **Stagnation-Problem**: Kein Wachstum/Schrumpfen nach Tag 3000, keine natürliche Demografie

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

# Milestones (du arbeitest Milestone 1 → 5 in dieser Reihenfolge ab)

## Milestone 1 — Projekt entpacken und Performance-Baseline etablieren
**Ziel**: Projektstruktur verstehen, Performance-Baseline messen, kritische Bugs identifizieren

**Aufgaben**:
- `/mnt/data/wirtschaft.zip` entpacken nach Arbeitsverzeichnis
- Projektstruktur analysieren: `tree -L 2` ausgeben
- Performance-Baseline messen:
  ```bash
  python -m cProfile -o output/baseline.prof main.py --config configs/small_performance_test.yaml
  python -c "import pstats; p = pstats.Stats('output/baseline.prof'); p.sort_stats('cumulative').print_stats(20)"
  ```
- Kritische Bugs analysieren:
  - `Household.receive_income` Baseline-Income Bug
  - `SavingsBank.total_savings` Property Bug
  - Performance-Bottlenecks dokumentieren
- Stelle sicher: `python -m py_compile` und minimaler Run crashen nicht

**Artefakt**: `wirtschaft1.zip` → Link ausgeben, dann weiter zu Milestone 2.

## Milestone 2 — Performance-Optimierung: Pandas/Numpy Metriken
**Ziel**: JSON-Bottleneck eliminieren, 40-50% Performance-Gewinn erzielen

**Aufgaben**:
Lies den abschnitt über performance-optimierung in `doc/issues.md` und vor dem hintergrund prüfe die folgenden punkte.
- `metrics.py` refaktorieren für Pandas/Numpy:
  ```python
  # Ersetze dict-basierte Speicherung durch pandas DataFrames
  self.household_metrics_df = pd.DataFrame()
  self.company_metrics_df = pd.DataFrame()
  # Pre-allocated numpy arrays für bekannte Metriken
  ```
- JSON-Export eliminieren:
  ```python
  # Statt: json.dump(metrics_data, f, indent=2)
  # Nutze: metrics_df.to_csv(output_file, index=False)
  ```
- Performance-Test:
  ```bash
  time python main.py --config configs/small_performance_test.yaml
  ```
- Validierung: Output-CSVs müssen gleiche Daten wie JSON enthalten

**Artefakt**: `wirtschaft2.zip` → Link ausgeben, dann weiter zu Milestone 3.

## Milestone 3 — Root-Cause Analyse: Stagnation und Demografie
**Ziel**: Ursachen für Stagnation nach Tag 3000 finden und beheben

**Aufgaben**:
- Logfile-Analyse:
  ```bash
  # Analysiere Output-Logs für Stagnationsmuster
  grep -n "bankruptcy\|death\|birth\|growth" output/simulation.log | tail -100
  ```
- Demografie-Analyse:
  - `Household.aging()` prüfen: Wird `age_days` täglich inkrementiert?
  - `Household.death_probability()` prüfen: Wird altersabhängige Sterblichkeit angewendet?
  - Geburt/Neugründung prüfen: Werden neue Haushalte/Firmen erstellt?
- Firmen-Dynamik Analyse:
  - `Company.bankruptcy()` prüfen: Gehen Firmen insolvent?
  - `Company.growth()` prüfen: Wachsen Firmen?
- Metriken-Trendanalyse:
  ```python
  # Analysiere CSV-Outputs auf Stagnation
  import pandas as pd
  df = pd.read_csv('output/metrics/macro.csv')
  print(df[['time_step', 'total_companies', 'total_households', 'm1_proxy']].tail(100))
  ```
**ziel**: Geldmenge M1 ändert sich auch nach tag 3000
**Artefakt**: `wirtschaft3.zip` → Link ausgeben, dann weiter zu Milestone 4.

## Milestone 4 — Natürlicher Fluss: Demografie und Firmen-Dynamik
**Ziel**: Natürliche, fließende Veränderungen in den Metriken umsetzen

**Aufgaben**:
- **Household-Demografie fixen**:
    - Haushalte sollten sich teilen, wenn genug geld da ist (gespart oder auf der hand). findet das statt?
    - Haushalte sollten altern und sterben, wenn sie ihr maximales Alter erreichen. findet das statt?
- **Firmen-Dynamik kontrollieren/debuggen**:
   - warum wächst die anzahl der Firmen nicht? sie sollten sich irgendwann teilen, wenn sie profitabel sind. aber die anzahl der firmen bleibt konstant.
- **Validation**:
  - 720 Tage Run: Prüfe ob Haushalte/Firmen kommen und gehen
  - haushalte könnten länger brauchen als 720 tage. probiere auch 10000 tage
  - 3600 Tage Run: Prüfe ob Metriken stetig und differenzierbar sind
**Ziel**: Natürliche, fließende Veränderungen in den Metriken durch wachstum/Schrumpfen. stetiges, differenzierbares Verhalten in den Metriken.
**Artefakt**: `wirtschaft4.zip` → Link ausgeben, dann weiter zu Milestone 5.


## Milestone 5 — Metrics/Validation + Beispiel-Configs Wachstum/Shrink
Ziel: Simulation validierbar, aussagekräftige Outputs, 2 Beispiel-Configs.

Bestellt der Retailer täglich Ware nach? es könnte sein, dass die aktivität kollabiert, wenn der retailer nicht regelmäßig bestellt. das würde die geldschöpfung beeinträchtigen.


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

**Artefakt:** `wirtschaft5.zip` → Link ausgeben.

---

# Nach Milestone 5: Refaktorierungsplan (Markdown)
Erstelle eine detaillierte Roadmap:
- Module, Zuständigkeiten, Tests, Erweiterungen (RetailerAgent als eigener Typ, InventoryLedger, Clearing-Audits etc.)
- Priorisierung P0/P1/P2
- Risiken und Validierungskriterien
- gibt es noch fehler in der Implementierung, gegenüber den specs?

---

# SPECS (Primäre Wahrheit)
## 1) Ziel, Systemgrenzen, Leitprinzipien (aus dem Text extrahiert) ### 1.1 Kernprinzip: Geldschöpfung nur an einer Stelle * **Geldschöpfung soll ausschließlich** durch **Kontokorrentkredite an Einzelhandelskaufleute** erfolgen, damit Geldmenge ↔ Warenwertmenge gekoppelt ist. * Dadurch schwanken **Geldmenge und Warenwertmenge** mit Ein-/Verkauf von Waren. ### 1.2 Geld entsteht & verschwindet im Warenkreislauf * Geld entsteht „in der Zirkulationssphäre“ durch Warenkredit; es zirkuliert (auch für Dienstleistungen) **bis** es „auf die Kontokorrentkonten zurückströmt und dort verschwindet“. * Dienstleistungen ändern die **Geldmenge nicht**, nur die Verteilung. ### 1.3 Banken als operative Emittenten + Kontrolle * Reformierte Banken: Aufgabe ist die **Geldversorgung** durch **zinsfreie Kontokorrentkredite** an den Einzelhandel (Geldschöpfung). * Banken kontrollieren Einzelhandel (u.a. Inventuren); Banken werden wiederum durch eine **Clearingstelle** kontrolliert, u.a. gegen Bilanzfälschungen. * Kredite sollen **nicht einseitig kündbar** sein; Änderungen des Kreditrahmens nur abgestimmt. ### 1.4 Sparkassen: separater Kreditkreislauf aus Spargeld (keine Geldschöpfung) * Sparen senkt Kaufkraft; Spargeld muss über Kreditvergabe wieder in Umlauf, sonst Absatz/Produktion sinken. * Sparkassen verleihen Spargeld zur Vorfinanzierung → Sichtguthaben wird zu Spargeld und zurück (untergeordneter Kreislauf). --- ## 2) Benötigte Agenten/Institutionen (Mapping auf deine bestehenden Klassen) Du hast schon viele Bausteine. Grobe Zuordnung: * **household_agent.py** → Haushalte (Konsum, Arbeit, Sparen, Kontoführung) * **company_agent.py** → Unternehmen (Produzenten/Dienstleister) *und/oder* Einzelhändler (besser: Einzelhändler als eigener Typ/Flag) * **bank.py** → Reformbanken (Kontokorrentlinie + Kontogebühren + Inventur-Kontrolle) * **savings_bank_agent.py** → Sparkassen (Sparannahme, Vorfinanzierungskredite aus Spargeld) * **clearing_agent.py** → Clearingstelle (Mindestreserve/Risikoreserven, Prüfungen, Wertberichtigungen/Geldvernichtung) * **financial_market.py** → sollte im Zielsystem stark reduziert/abgeschaltet sein (Börsenschließung wird impliziert: „Nach Schließen der Börsen…“ ) * **state_agent.py** → Staat (im Text gibt es politische/steuerliche Regeln; du wolltest volkswirtschaftliche Faktoren → Staat als Steuer- und Regelsetzer) * **environmental_agency.py** → optional: Stoffkreislauf/Umweltsteuer wird erwähnt (Abbildung 3). **Fehlend (empfohlen)**: * **RetailerAgent** (Einzelhandel) als eigener Agententyp, weil dort Geld entsteht/verschwindet. * **InventoryLedger / GoodsFlowModule** (Warenwerte, Inventuren, Wertberichtigungslogik). --- ## 3) Zustandsvariablen & Kontenmodell (Simulation-Datenmodell) ### 3.1 Kontotypen (pro Agent) **Für alle Agenten (Haushalt, Unternehmen):** * sight_balance (Sichtguthaben / Giro) * savings_balance (Sparguthaben; nur falls Sparkasse genutzt) * payment_card_balance (falls Bargeldersatz über Guthabenkarte/Offline-Zahlungen modelliert werden soll; dazu später) **Für Einzelhändler (zusätzlich):** * cc_limit (Kontokorrentrahmen) * cc_balance (typisch negativ = Inanspruchnahme) * inventory_value (bewerteter Warenbestand) * inventory_items (optional granular) * ware_value_adjustment_accounts[] (Warenwertberichtigungskonten, je Artikelgruppe oder je Abschreibungsgrund) **Für Reformbank:** * clients[] (Einzelhändlerkonten) * operating_costs (gedeckt über Kontogebühren statt Zinsen) * risk_reserve (Risikoprämie in Kontogebühren; plus Rücklagenmechanik) * clearing_reserve_deposit (Mindestreserve/Risikorücklage bei Clearingstelle) **Für Sparkasse:** * savings_pool (Summe Sparguthaben) * loan_book (Vorfinanzierungskredite aus Spargeld) * risk_reserve (für Abschreibungen) **Für Clearingstelle:** * bank_reserves[bank_id] (verwaltete Mindestreserven/Risikoreserven) * reserve_bounds (prozentuale Grenzen; zu hoch = Kaufkraftstilllegung, zu niedrig = Wertberichtigung unmöglich) * audit_schedule, audit_rules * value_correction_rules (Wertberichtigungen = Geldvernichtung) --- ## 4) Prozesslogik (State-Update-Regeln pro Zeitschritt) Ich beschreibe das als **deterministische Pipeline** je Simulations-Tick (mit Stochastik nur bei Entscheidungen/Schocks). ### 4.1 Warenkauf durch Einzelhändler (Geldschöpfung – primärer Emissionspunkt) **Event**: Retailer bestellt Ware vom Produzenten/Großhandel. **Regel A – Entstehung von Geld im Moment des Handels / der Bezahlung** * Wenn Retailer die Rechnung bezahlt und dazu Kontokorrent nutzt, wird das „durch Geldschöpfung“ abgewickelt: * beim Retailer entsteht Schuld (negativer Saldo), * beim Empfänger entsteht Guthaben. (Analog WIR-Beschreibung im Text) * Der Text fasst das als: „Mit dem Erscheinen der Waren … wird Geld … geschaffen und in Umlauf gebracht.“ **Algorithmisch:** 1. purchase_value = price_to_retailer * quantity 2. Check retailer.cc_balance - purchase_value >= -retailer.cc_limit * Wenn nein: Bestellung ablehnen oder Menge reduzieren (**offene Frage**: Priorität/Allokation) 3. Buchung: * retailer.cc_balance -= purchase_value (mehr negativ) * producer.sight_balance += purchase_value * **Money supply** (M1-Proxy) steigt um purchase_value (weil neues Sichtguthaben beim Produzenten entsteht) 4. retailer.inventory_value += purchase_value (oder Einstandswert) **Kontrollregel B – Inventuren als harte Deckungsprüfung** * Banken müssen per Inventur prüfen, ob „Warenwerte im Umfang des aktuellen Kreditvolumens … real vorhanden“ sind. Algorithmisch: Bank führt Inventur, vergleicht inventory_value mit abs(cc_balance); Abweichung triggert Wertberichtigung/Strafen. > **Offene Frage (wichtig):** Wie wird Warenwert bewertet? Einstandspreis, Marktpreis, Niederstwertprinzip? Wie schnell wird veraltete Ware abgeschrieben? --- ### 4.2 Verkauf an Haushalte (Rückstrom Richtung Kontokorrent – Geld verschwindet beim Ausgleich) **Event**: Haushalt kauft Ware im Einzelhandel. **Textregel:** * Geld zirkuliert, „bis das Geld durch Kauf von Waren auf die Kontokorrentkonten zurückströmt und dort verschwindet“. **Algorithmisch:** 1. sale_value = retail_price * quantity 2. Buchung: * household.sight_balance -= sale_value * retailer.sight_balance += sale_value 3. Periodisch (oder sofort) **Netting** Retailer: * Retailer verwendet Überschuss-Sichtguthaben zur Reduktion des Kontokorrents: * repay = min(retailer.sight_balance, abs(retailer.cc_balance)) * retailer.sight_balance -= repay * retailer.cc_balance += repay (weniger negativ) * **Money supply sinkt** um repay, weil Tilgung die zuvor geschaffenen Sichtguthaben wieder „einsaugt“ (entspricht „verschwindet“). > **Offene Frage:** Muss Tilgung zwingend automatisch passieren (täglich), oder entscheidet Retailer? Für Stabilität würde ich „automatisch ab Schwelle“ empfehlen. --- ### 4.3 Dienstleistungen (sekundäre Kreisläufe, keine Geldmengenänderung) **Textregel:** Dienstleistungen ändern die Geldmenge nicht, nur Verteilung. **Algorithmisch:** normale Überweisung: * buyer.sight_balance -= service_fee * seller.sight_balance += service_fee * Money supply konstant. --- ### 4.4 Kontogebühren statt Zinsen (Bankfinanzierung + Anti-Eigenkapital-Bias) **Textregeln:** * Banken finanzieren Betriebskosten durch **Kontogebühren**, nicht Zinsen. * Konten „im Plus“ sollen höhere Gebühren zahlen als Konten „im Minus“, um Eigenkapitalfinanzierung zu „bestrafen“. * Risikoprämie ist Teil der Kontogebühren und wird gleichmäßig verteilt → Anreiz, alle Kredite solide zu halten. **Algorithmisch (pro Tick, pro Konto):** * fee = base_fee + alpha * max(0, sight_balance) + beta * max(0, -sight_balance?) + gamma * risk_pool_share * wobei im Text die Richtung klar ist: **Plus teurer als Minus** (alpha > beta). * Abbuchung: account.sight_balance -= fee; bank.income += fee * bank zahlt Gehälter/Costs aus bank.income (optional) > **Offene Frage:** Bemessungsgrundlage (täglich, monatlich; linear vs. progressiv). Für Simulation: monatlich und progressiv (damit „große Plus-Bestände“ stärker gedrückt werden). --- ### 4.5 Clearingstelle: Mindestreserve, Wettbewerbssanktion, Prüfungen, Wertberichtigungen **Textregeln (sehr konkret):** * Kopplung Geldschöpfung an Warenwerte ist Grundlage der Geldmengensteuerung. * Banken halten Rücklagen als „Mindestreserve“ bei der Clearingstelle; bei wiederholten Problemen erhöht Clearing die Mindestreserveforderung. * Zu hohe Rücklagen = Stilllegung von Kaufkraft → partieller Geldmangel/Absatzstockungen; daher prozentuale Grenzen. * Bei schweren Bilanzfälschungen: Clearing erzwingt Wertberichtigungen (Geldvernichtung), ggf. Bank schließen, seriöse Konten übertragen. **Algorithmisch (Audit-Zyklus, z.B. monatlich/vierteljährlich):** 1. Für jede Bank: * Prüfe Stichproben-Retailer: inventory_value vs abs(cc_balance) + Buchungen. * Prüfe Reservequote: bank.clearing_reserve_deposit / bank.total_cc_exposure 2. Wenn problem_score hoch: * Erhöhe required_reserve_ratio[bank] (Wettbewerbssanktion: Bank muss Kosten über Gebühren/Gehälter tragen). 3. Wenn Fraud detected: * Trigger Wertberichtigung: Geldvernichtung in beteiligten Geschäften. * Optional: Bank resolution (Kontoumzug seriöser Kunden) > **Offene Frage:** Was ist die exakte „Fehlerkorrektur“ bei Bilanzfälschung? Welche Konten werden wie stark wertberichtigt? (Da hängt die Makrodynamik extrem dran.) --- ### 4.6 Wertberichtigungen über Warenwertberichtigungskonten (gezielte Geldvernichtung) Der Text gibt dafür eine klare Buchungslogik: * Für „unverkaufbare Waren“ werden **Warenwertberichtigungskonten** geführt; dort werden Rücklagen aus Gewinnen gespeichert. * Beim Abschreiben unverkaufbarer Ware wird von dort Geld vernichtet: „Geldguthaben wird vom Warenwertberichtigungskonto abgezogen und verschwindet.“ * Gleichzeitig wird der Warenwert im Lager reduziert. **Algorithmisch (bei Abschreibung / Verderb / Modewechsel):** 1. write_down = f(obsolescence, spoilage, demand_shift) 2. retailer.inventory_value -= write_down 3. retailer.ware_value_adjustment_account -= write_down 4. **Money supply sinkt** um write_down (Geldvernichtung) > **Offene Frage:** Wie werden Rücklagen *gefüllt*? „Aus Gewinnen“ heißt: aus Überschüssen beim Retailer. Aber Gewinndefinition ist im System (Selbstkostenpreise, Wettbewerb) heikel: Was ist legitimer Gewinn vs. verbotener Profit? (Der Text argumentiert Wettbewerb begrenzt das, liefert aber keine harte Buchungsregel.) --- ### 4.7 Sichtguthaben-Abschmelzung / Schwund nur für Überschuss (Geldflusssicherung) Im Text wird ein Mechanismus beschrieben, der **nicht generelles Schwundgeld** ist, sondern gezielt „zu große Sichtguthaben“ adressiert: * Es gibt einen **Sichtfaktor**: Wenn Sichtguthaben über einem **Sichtfreibetrag** liegen, wird der Überschuss **abgeschmolzen** (dokumentiert als Geldvernichtung / Kaufkraftabschmelzung). * Sichtfreibetrag orientiert sich an „durchschnittlichen monatlichen Ausgaben“, damit auch geringe Einkommen nicht „auf den Markt getrieben“ werden. * Kernidee: „zu große Sichtguthaben“ wachsen nicht unbegrenzt; es gibt Rückkopplung über den Sichtfaktor. **Algorithmisch (monatlich, weil Bezug auf Monatsausgaben):** 1. Für jeden Agenten: * avg_monthly_spend = rolling_mean(consumption, window=30d) * sight_allowance = k * avg_monthly_spend (k aus Politikregel) 2. excess = max(0, sight_balance - sight_allowance) 3. decay = sight_factor * excess 4. sight_balance -= decay 5. **Money supply sinkt** um decay > **Offene Frage:** Sichtfaktor dynamisch? Wer setzt ihn (Clearingstelle/Staat)? Gibt es Zielgröße (Inflation=0, Lagerumschlag, Vollbeschäftigung)? --- ### 4.8 Spargrenzen & Sparkassenkredite (Sparen an Investitionsbedarf koppeln) **Textregeln:** * Sparvolumen muss an Kreditnachfrage für Investitionen/vorgezogenen Konsum angepasst werden. * Zu geringe Kreditaufnahme → Absatzstockungen. * Sparkassenkredite sollen einen (niedrigen) Kreditzins haben, um sinnlose Überinvestition zu dämpfen; aber das ist **keine Geldschöpfung**, sondern Verleih von Spargeld. **Algorithmisch (pro Monat):** 1. Haushalte entscheiden Sparrate (abhängig von Vorsicht, Einkommen, Sichtguthaben-Abschmelzung). 2. Transfer zu Sparkasse: * household.sight_balance -= s * household.savings_balance += s * Kaufkraft sinkt, Geldmenge (gesamt) bleibt, aber M1 sinkt. 3. Sparkasse vergibt Kredite aus savings_pool: * loan_amount <= available_savings_pool * borrower.sight_balance += loan_amount * borrower.loan_balance += loan_amount 4. Tilgung/Raten → Sparkasse, ggf. Abschreibung fauler Kredite aus Risikorücklage (und dadurch ggf. Geldvernichtung, wenn Risikorücklagen „vernichtet“ werden – sinngemäß im Text bei Abschreibungen). > **Offene Frage:** Konkrete Spargrenzen-Formel fehlt im extrahierten Ausschnitt. (Es ist aber als zentrales Steuerinstrument angekündigt.) --- ## 5) Makro-Messgrößen (für „Validität & Praxistauglichkeit“) Damit du das System testen kannst, solltest du in jedem Tick mindestens tracken: * **Money supply (M1-Proxy)**: Summe aller sight_balance (inkl. positiver Salden) minus ggf. negatives? (Definiere sauber.) * **CC-Exposure**: Summe abs(retailer.cc_balance) * **Warenwertmenge (Value)**: Summe inventory_value bei Retailern (oder inklusive Produzentenlager, wenn modelliert) * **Velocity**: Transaktionsvolumen / durchschnittliches Geld * **Preisniveau** (CPI-Proxy) & **Selbstkosten-Abstand** (wenn du Produktionskosten modellierst) * **Absatzstockungen**: Lageraufbau + sinkende Umschlagsgeschwindigkeit * **Insolvenzrate** (Retailer, Produzenten, Sparkassenkreditnehmer) * **Ungleichheit**: Gini auf Sicht- und Sparguthaben * **Bankenstabilität**: Reservequote, Audit-Findings, Wertberichtigungen * **Vollbeschäftigung/Output**: wenn Arbeitsmarkt modelliert ist
