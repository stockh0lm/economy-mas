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

- [ ] **cc_limit-Policy / partnerschaftlicher Rahmen**: `cc_limit` ist aktuell (meist) statisch aus Config/Template. Spec: nicht einseitig kündbar, aber abgestimmt anpassbar.
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

- [x] **Legacy-Bankpfade widersprechen dem Spec-Narrativ**
  - `WarengeldBank.grant_credit(...)`, `calculate_fees(...)` und `check_inventories(current_step=None)` existieren primär für alte Tests.
  - Risiko: Neue Features greifen versehentlich auf diese Pfade zu (Geldschöpfung außerhalb Retailer-Güterkauf).
  - Done (minimal):
    - Methoden `WarengeldBank.grant_credit(...)`, `calculate_fees(...)`, `check_inventories(current_step=None)` geben `DeprecationWarning`.
    - Test: `tests/test_legacy_bank_paths_deprecated.py` stellt sicher, dass Standard-Runs keine Legacy-Pfade aufrufen.

- [ ] **Einheitliche Balance-Sheet-Namen (Haushalte)**
  - Status: `Household` nutzt `sight_balance` als Canonical und bietet `checking_account` als Alias, aber der Codebase verwendet noch weit verbreitet den alten Namen `checking_account`.
  - TODO: Alle Verwendungen von `checking_account` auf `sight_balance` migrieren.
  - Referenz: TODO in `scripts/legacy_scan.py` für automatisierte Erkennung und Ersetzung von Legacy-Namen.

- [~] **Legacy-Muster vollständig bereinigen und Migration abschließen**
  - **Aktueller Status**: 17 Legacy-Muster in 3 Dateien verbleiben (siehe `scripts/legacy_scan.py --cleanup --include-tests`)
  - **Ziel**: Vollständige Entfernung aller Legacy-Muster für saubere Codebase
  - **Arbeitsauftrag**:
    1. **Identifizierung**: Führe `python3 scripts/legacy_scan.py --cleanup --include-tests` aus, um alle verbleibenden Muster anzuzeigen
    2. **Migration der Bank-Klasse**: Entferne Legacy-Methoden aus `agents/bank.py`:
       - `grant_credit()` → Nur `finance_goods_purchase()` beibehalten
       - `calculate_fees()` → Nur `charge_account_fees()` beibehalten
       - `check_inventories(current_step=None)` → Nur moderne Inventarprüfung beibehalten
       - `fee_rate`-Eigenschaft → Vollständig entfernen
    3. **Testbereinigung**: Aktualisiere `tests/test_config_consistency_deprecation.py`, um moderne Parameter zu testen
    4. **Validierung**: Führe alle Tests aus und stelle sicher, dass keine Regressionen auftreten
    5. **Dokumentation**: Aktualisiere `doc/specs.md` und `doc/issues.md` mit neuen APIs
  - **Erwartetes Ergebnis**: 0 Legacy-Muster, vollständige Migration auf moderne Warengeld-API
  - **Priorität**: Hoch (für nächste Version)

- [ ] **Einheitliche Balance-Sheet-Namen (Company/Producer)**
  - TODO: konsistent `sight_balance` statt gemischter Namen.

- [x] **Konfig-Konsistenz**
  - `bank.fee_rate` ist legacy (nur für Tests); im Spec ist `WarengeldBank.charge_account_fees(...)` maßgeblich.
  - Done:
    - YAML-Lader gibt `DeprecationWarning` aus, wenn `bank.fee_rate` in YAML gesetzt wird (`main.load_config`).
    - Beispiel-Konfig (`config.yaml`) enthält `bank.fee_rate` nicht mehr.
    - Test: `tests/test_config_consistency_deprecation.py` stellt Warnung + korrektes Fee-Verhalten sicher.
  - Migration:
    - Entferne `bank.fee_rate` aus YAML.
    - Nutze `bank.base_account_fee`, `bank.positive_balance_fee_rate`, `bank.negative_balance_fee_rate`, `bank.risk_pool_rate`.

- [ ] **FinancialMarket abschalten**
  - Spec-Interpretation: Börsenschließung / Finanzmarkt stark reduziert.
  - Status: `FinancialMarket` existiert noch als Agent; prüfen, ob er in `main.py` tatsächlich Einfluss hat oder nur noop ist.

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


- [ ] **Implement Option A: Nutzerfreundliches Post‑hoc‑Gegenfaktum‑Script in `scripts/`**
  - Ziel: Ein einfaches, gut dokumentiertes Kommandozeilen‑Tool, das aus einem einzelnen Simulationsexport (`global_metrics_<runid>.csv` und zugehörigen Agent‑CSVs) ein Gegenfaktum berechnet, in dem Dienstleistungs‑Wertschöpfung für die betrachteten Kennzahlen ausgeblendet wird, und daraus direkte Vergleichsplots (Original vs. Ignoriert) sowie Differenz‑Analysen erzeugt.
  - Begründung: Schneller, reproduzierbarer Weg, um buchhalterische Effekte sichtbar zu machen, ohne die Simulationslogik oder die Default‑Semantik zu verändern. Eignet sich für explorative Analysen und für Nutzer, die keine Änderungen an der Simulation selbst vornehmen wollen.
  - Anforderungen / Verhalten des Scripts (`scripts/compare_posthoc.py` oder `scripts/plot_metrics.py --posthoc`):
    1) Lade den Export `global_metrics_<runid>.csv` (und optional `household/company/retailer` CSVs, falls per‑Agent‑Normalisierung nötig).
    2) Erzeuge eine Counterfactual‑View (post‑hoc): setze `service_value_total = 0` und `service_tx_volume = 0` für alle Zeitschritte und recompute abhängige Größen:
       - `service_share_of_output = 0`
       - `goods_only_velocity = goods_tx_volume / m1_proxy` (falls m1_proxy>0)
       - ggf. `gdp_alt = gdp - service_value_total` (nur wenn Services im exportierten GDP enthalten waren; Script entscheidet heuristisch oder per Flag)
       - rekursive Neuberechnung von `price_index_alt` / `inflation_rate_alt` über die Zeit unter Verwendung der vorhandenen Preisbildungslogik (kopiere die Formel aus `metrics._price_dynamics`) aber mit den alternativen Inputs
    3) Erzeuge Vergleichsplots (Original vs. Counterfactual) und Differenzplots für Kernkennzahlen:
       - `price_index`, `inflation_rate`, `m1_proxy`, `m2_proxy`, `issuance_volume`, `goods_tx_volume`, `service_value_total` (wird 0 im CF), `service_share_of_output`, `gdp` (oder `gdp_alt`), `velocity_proxy`, `goods_only_velocity`, `employment_rate`, `bankruptcy_rate`.
    4) CLI‑Interface: akzeptiere `--run-id`, `--metrics-dir`, `--plots-dir`, `--assume-services-in-gdp` (bool), `--output-prefix`.
    5) Optional: Wenn Agent‑CSVs vorhanden, berechne zusätzlich pro‑Kopf/Per‑Agent Normalisierungen (z.B. pro Haushalt) und zeige Histogramme/Density‑Plots.
    6) Ausgabe: PNGs im `output/plots/<runid>/posthoc/` plus ein kurzes CSV mit den Differenzen (`posthoc_differences_<runid>.csv`) und ein kleines Summary‑Markdown (`posthoc_summary_<runid>.md`) mit Kernaussagen (z.B. max Preisunterschied, kumulative Inflation-Differenz).
  - Tests / Akzeptanzkriterien:
    - Unit‑Test: `tests/test_posthoc_recompute.py` prüft, dass die Counterfactual‑Rechnung (service->0) die abgeleiteten Series korrekt neu berechnet (z.B. service_share = 0, goods_only_velocity korrekt) für synthetische DataFrames.
    - Smoke: `scripts/compare_posthoc.py --run-id <existing_run>` erzeugt die PNGs ohne Fehler für einen echten Export im Repo und schreibt die Summary‑Dateien.
    - Dokumentation: README‑Abschnitt mit Usage‑Beispielen und Interpretation (Grenzen: kein dynamischer Rückkopplungseffekt erfasst).
  - CLI Beispiel:
```bash
python scripts/compare_posthoc.py --run-id 20260101_120000 --metrics-dir output/metrics --plots-dir output/plots --assume-services-in-gdp
```
  - Hinweise zur Interpretation:
    - Script zeigt nur buchhalterische Gegenfakta; es ersetzt nicht die dynamische Zweifach‑Simulationsanalyse, aber liefert schnellen, reproduzierbaren Einblick.
    - Default‑Semantik im Code bleibt unverändert (Services weiterhin als geldmengenneutral getrackt). Das Script führt nur Post‑hoc‑Transformationen durch.
  - Optional / Erweiterungen:
    - `--compare-with-run <other_runid>` um Original‑Run gegen einen tatsächlichen alternativen Run zu vergleichen (Hybrid: Post‑hoc vs. echter Zweitlauf).
    - Integration in CI: kleiner seeded example run + posthoc compare als Regressionstest.
