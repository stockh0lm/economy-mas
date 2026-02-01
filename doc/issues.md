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
  - Offene Spec-Fragen: Bewertungsregel (Einstand/Markt/Niederstwert), “unverkaufbar”-Kriterium, Artikelgruppen.

- [~] **Fraud/Wertberichtigung-Rechenregel**:
  - Status: Clearing hat eine implementierte, einfache Verlustallokation in `_apply_value_correction(...)` (Reserve → Retailer-Sicht → Empfänger-Haircut (pro-rata via Bank-Ledger) → Bankreserve).
  - Offene Spec-Fragen: exakte Rechts-/Buchungslogik, wie Haircuts fair/robust verteilt werden sollen.

- [ ] **Sparkassen-Regeln (Spargrenze / Invest-Nachfrage-Kopplung)**:
  - Status: Es gibt derzeit nur `max_savings_per_account` als rein technische Obergrenze.
  - Spec: Spargrenzen sollen politisches Steuerinstrument sein, gekoppelt an erwartete Kreditnachfrage.

- [x] **Staat als realer Nachfrager im Warenkreislauf**:
  - Status: Implementiert: `RetailerAgent.sell_to_state(...)` + `State.pay(...)`.
  - State nutzt Procurement in `state.spend_budgets(...)` (Infrastruktur-Budget) → Warenfluss + Inventarabbau, Geldmengenneutral.

---

## 3) Tests / Validierung

- [ ] **Golden-run Snapshot**
  - Ein kurzer Seeded-Run (z.B. 30 Tage) mit erwarteten Makro-Kennzahlen-Bändern.

- [x] **Neuer Test: Staat kauft Waren bei Retailern**
  - Referenz: Abschnitt **2) Abweichungen / Spec-Lücken → „Staat als realer Nachfrager…“**
  - Arrange: Retailer hat Inventory; State hat Budget.
  - Act: State procurement → `RetailerAgent.sell_to_state(...)` (oder Reuse `sell_to_household` mit State als Käufer-Protokoll).
  - Assert: Inventory sinkt, Retailer.sight steigt, State.sight sinkt, keine Geldschöpfung/Vernichtung.

- [ ] **Neuer Test: Sparkassen-Kredit -> Investition -> Produktivität**
  - Referenz: Abschnitt **5) Neue ToDos → „Firmen sollen bei der Sparkasse Geld leihen…“**
  - Arrange: Company ohne ausreichendes Sight, Sparkasse mit Savings-Pool.
  - Act: Company *kann, muss nicht* Sparkassenkredit für Investition nehmen; Produktivität/Capacity steigt.
  - Assert: `production_capacity` steigt, `active_loans` steigt, Logging-Event vorhanden.

- [ ] **Neuer Test: Dienstleistungs-Sektor (geldmengenneutral) sichtbar**
  - Referenz: Abschnitt **5) Neue ToDos → „Dienstleistungs‑Wertschöpfung…“**
  - Arrange: Haushalte haben Dienstleistungsbudget, zahlen an Company/ServiceProvider.
  - Act: Service-Transaktionen werden gebucht.
  - Assert: `service_tx_volume` > 0, `issuance_volume` unverändert (≈0 Effekt), nur Verteilung ändert sich.

---

## 4) Code-Smells / Komplexität / Refactor-Vorschläge (schlank halten)

- [~] **Legacy-Bankpfade widersprechen dem Spec-Narrativ**
  - `WarengeldBank.grant_credit(...)`, `calculate_fees(...)` und `check_inventories(current_step=None)` existieren primär für alte Tests.
  - Risiko: Neue Features greifen versehentlich auf diese Pfade zu (Geldschöpfung außerhalb Retailer-Güterkauf).
  - Vorschlag: klar als deprecated markieren + in der Simulation-Pipeline nicht verwenden (oder per Flag hart deaktivieren).

- [x] **Einheitliche Balance-Sheet-Namen (Haushalte)**
  - Erledigt: `Household` nutzt `sight_balance` als Canonical und bietet `checking_account` als Alias.

- [ ] **Einheitliche Balance-Sheet-Namen (Company/Producer)**
  - TODO: konsistent `sight_balance` statt gemischter Namen.

- [ ] **Konfig-Konsistenz**
  - `bank.fee_rate` ist legacy (nur für Tests); im Spec ist `charge_account_fees` maßgeblich.
  - Vorschlag: deprecate/aus YAML entfernen oder sehr deutlich als legacy markieren.

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

- [ ] **Dienstleistungs-Wertschöpfung (~75% im heutigen System) abbilden/tracken**
  - Problem/Spec-Spannung:
    - In realen Volkswirtschaften entsteht ein sehr großer Teil der Wertschöpfung im **Dienstleistungssektor**.
    - Im Warengeld-Modell soll **Geldschöpfung nur bei Waren(finanzierung) im Einzelhandel** stattfinden.
    - Dienstleistungen sind im Spec *geldmengenneutral*: sie ändern die Geldmenge nicht, nur die Verteilung.
  - Ziel: In der Simulation soll sichtbar werden können, welche Konsequenzen ein hoher Service-Anteil hat, **wenn 3/4 der Wertschöpfung keine Geldschöpfung triggert**.
  - Vorschlag (minimal-invasive Umsetzung, messbar):
    1) **Service-Output / Service-GDP** separat erfassen:
       - Metriken: `service_value_total`, `goods_value_total`, `service_share_of_output`.
       - Proxy: Service-Transaktionen (z.B. Haushalte zahlen „Dienstleistungsbudget“ an Companies/ServiceProvider) zählen in GDP/Output, aber **ohne** Inventarfluss.
    2) **Money-Interaction-Tracking**:
       - Metriken: `service_tx_volume` (Summe Service-Zahlungen), `goods_tx_volume` (Summe Warenverkäufe an Haushalte),
         `issuance_volume` (nur aus `finance_goods_purchase`), `extinguish_volume` (nur CC-Tilgung + Wertberichtigungen).
       - Erwartung/Check: `service_tx_volume` beeinflusst `issuance_volume` nicht (≈0 Wirkung).
    3) **Folgen sichtbar machen** (Beobachtbarkeit statt sofort „richtiges“ Modell):
       - Korrelationen/Plots: `service_share_of_output` vs
         - `m1_proxy` / `cc_exposure`
         - `velocity_proxy`
         - „Absatzstockung“-Proxies (Retail-Inventar steigt, Umschlag sinkt)
         - Lohn-/Preis-Proxies
    4) Optional (später): eigener `ServiceProviderAgent` oder Flag in `Company` (goods vs services),
       damit Entscheidungen/Investitionen getrennt modelliert werden können.

- [ ] **Firmen: Produktivität/Capacity-Steigerung durch Investitionen prüfen (Tests + Logging)**
  - Code-Status: Es gibt `Company.invest_in_rd()` + `Company.innovate()` (stochastisch), aber **kein** explizites “Investitionsprojekt” mit Sparkassenfinanzierung.
  - TODO:
    - Test hinzufügen, der deterministisch eine Kapazitäts-/Produktivitätssteigerung auslöst.
    - Logging-Message/Ereignis standardisieren (z.B. `investment:` / `productivity:`).

- [ ] **Firmen sollen bei der Sparkasse Geld leihen können für Investitionen und Produktivität steigern**
  - Status: `SavingsBank.allocate_credit(...)` funktioniert bereits generisch für Borrower, aber Company hat keinen klaren Pfad:
    - wann beantragt Company Kredit,
    - wie wird aus Kredit produktives Kapital (capacity/innovation),
    - wie werden Tilgung/Zins/Defaults modelliert.
  - TODO: Minimal-Policy definieren (Trigger, max. loan-to-capacity, repayment rule) + Tests.

- [ ] **scripts/plot_metrics.py** anpassen, um neue Metriken (Güter-/Dienstleistungs-Output, Velocity-Proxies) zu plotten.
  - [ ] **scripts/plot_metrics.py** intern vollständig auf pandas umstellen um performance zu steigern (DataFrame-basiert statt dict-basiert). eventuell noch numpy, wenns hilft.

---

## 6) Prompt-Meilensteine (für das nächste große 2h-LLM-Arbeitspaket)

**Wichtig:** Wenn ein Milestone in einem LLM-Run abgeschlossen ist, muss diese Datei (`doc/issues.md`) direkt aktualisiert werden:
- Den entsprechenden Punkt auf `[x]` setzen.
- Wenn der Punkt vollständig erledigt ist, in eine „Done / Erledigt“-Sektion verschieben oder entfernen.
- Verweise/Tests dabei konsistent halten.

- [x] **M1: Staat kauft Waren bei Retailern (Realwirtschaftliche Rückkopplung)**
  - Bezug: Abschnitt **2) → „Staat als realer Nachfrager im Warenkreislauf“** und Abschnitt **3) → Test „Staat kauft Waren…“**.

- [ ] **M2: Sparkassen‑Investitionskredite für Companies (Policy + deterministischer Test + Logging)**
  - Bezug: Abschnitt **5) → „Firmen sollen bei der Sparkasse Geld leihen…“** und Abschnitt **3) → Test „Sparkassen‑Kredit → Investition…“**.

- [ ] **M3: Dienstleistungs‑Sektor transparent machen (Metriken + Buchung ohne Geldschöpfung)**
  - Bezug: Abschnitt **5) → „Dienstleistungs‑Wertschöpfung…“** und Abschnitt **3) → Test „Dienstleistungs‑Sektor…“**.

- [ ] **M4: Tech‑Debt klein – Legacy‑Bankpfade härter deprecaten / unbenutzt machen**
  - Bezug: Abschnitt **4) → „Legacy‑Bankpfade…“**.

- [ ] **M5: Tech‑Debt klein – Company Balance‑Sheet Naming auf `sight_balance` konsolidieren**
  - Bezug: Abschnitt **4) → „Einheitliche Balance-Sheet-Namen (Company/Producer)“**.

---

## 7) Empfohlene nächste Schritte (praktisch)

1) (erledigt) **State-Procurement via Retailer** ist implementiert (+ Test) (siehe Abschnitt 6) M1).
2) **Sparkassen-Investitionskredite** für Companies minimal implementieren (deterministisch testbar) + Logging.
3) **Dienstleistungssektor transparent machen** (Metriken + money-neutral booking).
4) Danach: `cc_limit-Policy` (rollierend, audit-basiert) ergänzen.
