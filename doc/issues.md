# Issues / Backlog: Warengeld + YAML-Konfiguration

Dieses Dokument ist ein **Arbeits- und Fortschrittslog**: Es listet Probleme/Fehler im aktuellen Simulationsmodell sowie geplante Änderungen, die **noch nicht** implementiert sind. Ziel: Nichts vergessen, Fortschritt nachhalten, und größere Umbauten in nachvollziehbare Schritte zerlegen.

## Status-Legende
- [ ] offen
- [~] in Arbeit
- [x] erledigt

---

## 1) Fehler: Geldschöpfung ist aktuell nicht „Warengeld“ (Commodity Money)

### Problem
Das aktuelle Modell entspricht **nicht** der beabsichtigten Warengeld-Mechanik („Geldschöpfung nur zwischen Händler/Firma und Bank zur Warenanschaffung; Geldvernichtung beim Warenverkauf; keine herkömmliche Geldschöpfung“).

Im Ist-Zustand entstehen und zirkulieren Geldbeträge an Stellen, die in einem reinen Warengeldregime so **nicht** vorkommen sollten:

1. **Haushalts-Einkommen erzeugt Geld aus dem Nichts**
   - `Household.receive_income()` erhöht `checking_account` direkt.
   - Bei Löhnen (`Company.pay_wages()` → `employee.receive_income(rate)`) fehlt eine konsistente Gegenbuchung.
   - Effekt: Geldmenge kann steigen, ohne dass ein warengeld-typischer Deckungsbezug (Warenbestand/Wareneinkauf) existiert.

2. **WarengeldBank-Kredit ist aktuell kein „Geldschöpfen“, sondern Liquiditätsabfluss**
   - `WarengeldBank.grant_credit()` reduziert `bank.liquidity` und erhöht `company.balance`.
   - Damit verteilt die Bank primär vorhandene Liquidität statt (im Sinne von Buchgeld) eine liability-basierte Geldmenge passend zum Warenkreislauf zu emittieren.

3. **Warengeld-Kredit wird für Löhne genutzt (unerwünscht für reines Warengeld)**
   - `Company._ensure_wage_liquidity()` zieht Warengeld-Kredit explizit zur Lohnzahlung.

4. **Warenverkauf vernichtet kein Geld**
   - `Company.sell_to_household()` transferiert Geld vom Haushalt an die Firma.
   - In der Zielmechanik soll beim Warenverkauf **Geld eingezogen/vernichtet** werden (Commodity Money Loop), statt sich als Unternehmensgeldsaldo aufzuschichten.

### Auswirkungen
- Aussagen über langfristige Geldmengenentwicklung, Umlaufgeschwindigkeit, Deflation/Inflation etc. sind aktuell schwer interpretierbar, weil die Geldentstehung nicht eindeutig an Waren-Emission/Vernichtung gekoppelt ist.

### Zielverhalten (Soll)
- **Schöpfung**: Nur wenn eine Firma Waren anschafft/finanziert (z.B. Einkauf/Herstellung mit Bankfinanzierung) soll Warengeld emittiert werden.
- **Vernichtung**: Beim Verkauf an Haushalte soll (über Bank/Clearing) der entsprechende Geldbetrag wieder eingezogen und vernichtet werden.
- **Kein** klassisches „Kredit schafft Einzahlung“ im allgemeinen Sinn (insb. nicht für Löhne/Transfers).

### Notwendige Änderungen (noch NICHT umgesetzt)
- [ ] **Monetäre Primitive als explizite API definieren** (voraussichtlich in `agents/bank.py` und genutzt in `agents/company_agent.py`):
  - `finance_goods_purchase(...)` (Emission)
  - `extinguish_on_goods_sale(...)` (Einzug/Vernichtung)
- [ ] `Company.sell_to_household()` darf nicht mehr `company.balance += revenue` machen, wenn Geld vernichtet werden soll.
- [ ] `Company._ensure_wage_liquidity()` muss entfallen oder per Config-Flag deaktivierbar werden, wenn Warengeld nur für Warenfinanzierung zulässig ist.
- [ ] `Household.receive_income()`/Lohnlogik muss so angepasst werden, dass Einkommen nicht mehr automatisch Geldschöpfung ist (Design-Entscheidung nötig).
- [ ] Metriken (`metrics.py`, `total_money_supply`) müssen zu einer klaren Geldmengendefinition passen (z.B. Deposits vs. bankseitige issued-Positionen).

---

## 2) Offene Design-Entscheidungen (blockieren spätere Implementierung)

- [ ] **Wo „existiert“ Geld im Zielmodell?**
  - Nur Haushaltskonten? Auch Firmenkonten? Oder Firmen nur als „Inventory + Verbindlichkeit“?
- [ ] **Wie werden Löhne/Einkommen modelliert, ohne wieder klassische Geldschöpfung einzuführen?**
  - Temporär: Löhne deaktivieren/vereinfachen?
  - Alternative: staatliche Transfers aus Steuern (aber dann muss auch Steuergeld-Quelle definiert sein).
- [ ] **Wo findet Geldvernichtung statt?**
  - Direkt im `sell_to_household` (vereinfacht, aber buchhalterisch „magisch“)
  - Oder zentral über Bank/Clearing (empfohlen für saubere Buchhaltung)

---

## 3) Backlog: YAML-Konfiguration + Skalierung der Agentenzahlen

### Problem
Agentenzahlen (Haushalte/Firmen) sind aktuell nur indirekt über Listen (`INITIAL_HOUSEHOLDS`, `INITIAL_COMPANIES`) steuerbar. Das ist für „viele Agenten“ unpraktisch.

### Ziel
- YAML als primäre Konfigurationsquelle
- „Leicht konfigurierbar“ viele Haushalte/Firmen (Generator + Templates)
- Validierung beim Einlesen (Pydantic)

### Geplante Änderungen (noch NICHT umgesetzt)
- [ ] YAML-Loader ergänzen (z.B. `load_simulation_config_from_yaml(...)`), der in `load_simulation_config(...)` validiert.
- [ ] Config-Schema erweitern:
  - [ ] `population.num_households`, `population.num_companies`
  - [ ] `population.household_template`, `population.company_template`
  - [ ] optional: seed/variations
- [ ] `main.initialize_agents()` so erweitern, dass bei gesetzten `num_*` die Listen generiert werden.

---

## 4) Backlog: Teststrategie für Warengeld (Regressionen früh erkennen)

### Problem
Vorhandene Tests prüfen aktuell u.a. Warengeld-Kredit für Löhne (`tests/test_company_step_regression.py`). Das widerspricht dem Zielmodell.

### Ziel
Vor der Umstellung der Logik sollen Tests das Zielmodell „festnageln“:
- Warengeld-Güterzyklus: Emission bei Warenfinanzierung / Vernichtung bei Warenverkauf
- Geldmengen-Contract klar definieren

### Geplante Tests (noch NICHT umgesetzt)
- [ ] Neuer Test: **Warengeld-Güterzyklus (minimaler Integrationstest)**
  - Arrange: Haushalt mit checking, Firma mit inventory, Bank mit Tracking
  - Act: Haushalt kauft Ware
  - Assert: Geldmenge/issued sinkt, Haushalt sinkt, Firma bekommt nicht einfach freien Geldzuwachs
- [ ] Contract-Test: Definition von `total_money_supply` explizit dokumentieren

---

## 5) Naming / Semantik: Standardisiertes Balance-Sheet Vokabular (Household/Company/Retailer)

- [ ] **Adopt a naming scheme commonly used in financial multi-agent simulations** (balance-sheet terms)

  **Problem**
  Aktuell werden Begriffe wie `balance`, `checking_account`, `savings`, `inventory` teils als Geld-Stock, teils als Vermögens-/Netto-Größe verwendet. Das führt zu Missverständnissen (z.B. „negative savings“), und erschwert eine korrekte Warengeld-Buchführung.

  **Ziel / Soll**
  Einheitliches, buchhalterisch klares Modell mit getrennten Stocks:

  - `sight_balance` (Sichtguthaben / M1-Komponente)
  - `savings_balance` (Sparguthaben bei der Sparkasse; kein negativer Stock)
  - `loan_balance` (aus Spargeld vergebene Kredite; separater Schuldenstock)
  - Retailer-spezifisch: `cc_balance`, `cc_limit`, `inventory_units`, `inventory_value`, `write_down_reserve`
  - Producer/Company: `sight_balance` (statt `balance`), `finished_goods_units` (statt `inventory`)

  **Konkrete Maßnahmen**
  - [ ] Haushalte: `checking_account` -> `sight_balance` (alias, dann Migration); `savings` umbenennen in `local_savings` oder entfernen
  - [ ] Sparkasse: Household-Sparen nur als `SavingsBank.savings_accounts[hid]` (als echter `savings_balance`)
  - [ ] Schulden explizit machen: keine „negativen savings“ als Schuldenersatz
  - [ ] Metriken: `total_money_supply` als M1-Prox sauber definieren (Summe positiver `sight_balance`), Schulden separat reporten

  **Qualitätsgate**
  - [ ] Invariant-/Contract-Tests: (a) Sparguthaben nie < 0; (b) Geldschöpfung nur über `WarengeldBank.finance_goods_purchase`.

---

## 6) Tooling: legacy_scan als Ruff/Pre-Commit/CI-Linter integrieren?

Aktuell wird `scripts/legacy_scan.py` via Pytest (`tests/test_legacy_scan.py`) ausgeführt.
Das ist robust, aber etwas „hacky“ (Subprocess in Tests) und technisch kein Linter.

Optionen:
- Ruff als *ein* Gate nutzen (z.B. über ein Pre-Commit Hook), aber: Ruff kann ohne Plugin keine semantischen Projektregeln.
- Beibehalten als eigenständiger Repo-Linter (empfohlen), aber in CI/Nox als eigener Schritt (`nox -s legacy_scan`) statt in Pytest.

Entscheidungsvorschlag:
- Mittelfristig: `legacy_scan.py` als **separaten Lint-Check** (Nox/CI/Pre-Commit), nicht als Unit-Test.

---

## Nächste Schritte (kurz)
- [ ] YAML-Konfig einführen + Agentenzahlen skalierbar machen
- [ ] Tests für Warengeld-Güterzyklus hinzufügen (ohne die Produktions-/Lohnlogik schon umzubauen)
- [ ] Erst danach: Warengeld-Mechanik implementieren und die bestehenden Regressionstests entsprechend anpassen
