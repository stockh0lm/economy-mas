# Issues / Backlog (Warengeld-Simulation)

Stand: **2026-01-24**

Dieses Dokument ist ein Arbeits- und Fortschrittslog: offene Punkte, erledigte Fixes,
und konkrete nächste Schritte – mit Fokus auf **Schlankheit, Verständlichkeit, saubere Buchführung**.

## Status-Legende
- [ ] offen
- [~] in Arbeit
- [x] erledigt

---

## 1) Compliance-Fixes (gegen Buch/Spezifikation)

- [x] **Kontokorrent-Geldschöpfung nur im Einzelhandel**: Geld entsteht in `WarengeldBank.finance_goods_purchase(...)` bei Warenankauf durch `RetailerAgent`.
- [x] **Geldvernichtung beim Rückstrom zum Kontokorrent**: `RetailerAgent.auto_repay_contokorrent(...)` tilgt CC aus Sichtguthaben (M1 sinkt).
- [x] **Kontogebühren statt Zinsen**: `WarengeldBank.charge_account_fees(...)` nutzt `base_account_fee + pos_fee_rate * max(0, sight) + neg_fee_rate * max(0, -sight)`; Plus ist teurer als Minus.
- [x] **Clearing-Reserve-Grenzen korrekt**: Bugfix `reserve_bounds_min/max` (vorher falsche Feldnamen in `ClearingAgent`).
- [x] **Zeitliche Granularität**: tägliche Transaktionen; monatliche Policies (Fees, Sichtfaktor/Decay); Audit im konfigurierten Intervall.
- [x] **Örtliche Granularität**: `spatial.num_regions` → pro Region Hausbank (WarengeldBank), Sparkasse, Retailer, Haushalte.
- [x] **Metriken + Plots**: Export pro Run; neue Global-Metriken `m1_proxy`, `m2_proxy`, `cc_exposure`, `inventory_value_total`, `velocity_proxy`; neuer Plot `monetary_system.png`.

---

## 2) Noch offene Design-Entscheidungen (simulationskritisch)

- [ ] **Kreditrahmen-Formel (`cc_limit`)**: Derzeit statisch aus YAML. Im Buch/Spezifikation: partnerschaftlich/unkündbar, aber Anpassung möglich.
  - Vorschlag: `cc_limit = m * avg_monthly_cogs` (rollierend) mit Audit-Risk-Modifier.

- [ ] **Warenbewertung & Abschreibung**:
  - Welche Bewertungsregel (Einstand, Markt, Niederstwert)?
  - Wann gilt Ware als „unverkaufbar“?
  - Soll eine explizite `ware_value_adjustment_account`-Logik inkl. Befüllung aus Gewinnen eingeführt werden?

- [ ] **Fraud/Wertberichtigung-Rechenregel**:
  - Clearing erkennt Inventarbetrug → wie genau wird der Differenzbetrag vernichtet (Retailer haircut? Bankreserve? proportionaler Haircut bei Empfängern?)
  - Wichtig, weil Makrodynamik stark davon abhängt.

- [ ] **Sparkassen-Regeln (Spargrenze / Invest-Nachfrage-Kopplung)**:
  - Das Buch nennt Spargrenzen als Steuerinstrument; derzeit gibt es nur `max_savings_per_account`.
  - Minimalvorschlag: Cap an erwartete Kreditnachfrage koppeln und Überschüsse automatisch in Konsum/Abgabe umleiten.

---

---

## 4) Code-Smells / Refactor-Vorschläge (schlank halten)
- try .. except Blöcke verdecken Fehlerquellen; besser gezielt prüfen.
---

## 5) Performance-Analyse & Optimierungsvorschläge

### Performance-Profiling (Stand: 2026-01-31)

**Testkonfiguration**: `configs/small_performance_test.yaml`
- 1.000 Simulationsschritte (reduziert von 36.000)
- 50 Haushalte, 12 Unternehmen, 4 Händler, 2 Regionen
- **Gesamtlaufzeit**: 11,0 Sekunden
- **Funktionsaufrufe**: 41.182.378

#### Identifizierte Flaschenhälse

1. **JSON-Metriken-Export (40,5% der Laufzeit)**
   - `json.dump()`: 0,751s + `json/encoder.py:_iterencode_dict`: 2,318s
   - **Problem**: Export von 3,2 Mio. Metrik-Einträgen mit Einrückung am Ende der Simulation
   - **Gesamtauswirkung**: 4,46s (40,5% der Laufzeit)

2. **Metrikensammlung (47% der Laufzeit)**
   - `collect_household_metrics`: 0,198s (1.000 Aufrufe)
   - `add_metric`: 0,228s (662.000 Aufrufe)
   - **Problem**: 7 Metrikensammlungen pro Schritt × 1.000 Schritte = 7.000 Sammlungsoperationen
   - **Gesamtauswirkung**: ~5,2s (47% der Laufzeit)

3. **Logging-Overhead (21% der Laufzeit)**
   - `logging.info`: 1,893s (62.722 Aufrufe)
   - `logger.log`: 2,326s (90.848 Aufrufe)
   - **Problem**: Ausführliches Logging mit Stack-Trace-Inspektion bei jedem Aufruf
   - **Gesamtauswirkung**: ~2,3s (21% der Laufzeit)

#### Leistungsaufschlüsselung nach Kategorien

| Kategorie | Zeit (s) | Anteil | Hauptfunktionen |
|-----------|---------|--------|-----------------|
| **Metriken-Export** | 4,46 | 40,5% | `json.dump()`, `_iterencode_dict` |
| **Metrikensammlung** | 1,80 | 16,4% | `collect_*_metrics`, `add_metric` |
| **Logging** | 2,33 | 21,2% | `logger.log()`, `logging.info()` |
| **Agentenverarbeitung** | 1,20 | 10,9% | `Household.step()`, `Company.step()` |
| **CSV-Schreiben** | 0,56 | 5,1% | `csv.writer.writerow()` |
| **Sonstiges** | 0,65 | 5,9% | Verschiedenes |

#### Konkrete Optimierungsvorschläge

**A. Pandas/Numpy-basierte Metriken-Optimierung (40-50% Verbesserungspotenzial)**

1. **JSON-Elimination durch Pandas/Numpy**
   ```python
   # Statt: json.dump(self._metrics, f, indent=2)  # 4,46s
   # Nutze: pandas DataFrames mit numpy Arrays
   metrics_df = pd.DataFrame(metrics_data)
   metrics_df.to_csv(output_file, index=False)  # <1s
   ```
   **Vorteile**:
   - 40-50% Performance-Gewinn durch Elimination der JSON-Serialisierung
   - Speichereffiziente numpy Arrays für Metrikenspeicherung
   - Vektorisierte Operationen für schnelle Aggregationen
   - Effizienter CSV-Export mit pandas.to_csv()

   **Erwartete Auswirkung**: 4-5s eingespart (40-50% Verbesserung)

2. **Pre-allocated numpy Arrays**
   ```python
   # Vorab-Allokation zu Simulationsbeginn
   max_steps = config.simulation_steps
   num_households = config.population.num_households
   self.household_metrics = np.zeros((max_steps, num_households, num_metrics))
   ```
   **Erwartete Auswirkung**: 0,5-1s eingespart (5-10% Verbesserung)

#### Implementierungspriorität

| Priorität | Vorschlag | Erwartete Auswirkung | Komplexität |
|-----------|-----------|----------------------|-------------|
| 1 | Pandas/Numpy-basierte Metriken | 4-5s (40-50%) | Mittel |
| 2 | Reduzierte Metrikensammelfrequenz | 1-1,5s (10-15%) | Niedrig |
| 5 | Pre-allocated numpy Arrays | 0,5-1s (5-10%) | Mittel |

#### Geschätztes Gesamtverbesserungspotenzial

Mit allen Vorschlägen implementiert:
- **Bestes Szenario**: ~8s eingespart (70% Verbesserung) → 3s Laufzeit
- **Realistisches Szenario**: ~6s eingespart (55% Verbesserung) → 5s Laufzeit
- **Konservatives Szenario**: ~4s eingespart (35% Verbesserung) → 7s Laufzeit

---

## 6) Empfohlene nächste Schritte (praktisch)

1) **Pandas/Numpy-basierte Metriken implementieren** (hohe Auswirkung, mittlere Komplexität):
   - JSON-Elimination durch pandas DataFrames
   - Pre-allocated numpy Arrays für Metrikenspeicherung
   - Effizienter CSV-Export mit pandas.to_csv()

3) **Fraud/Wertberichtigung** als klare Buchungsregel implementieren (klein anfangen: Inventar-Delta → Retailer-Haircut + Bankreserve).

4) **cc_limit-Policy** (rollierend, audit-basiert) ergänzen.

5) **Spargrenzen** (Kapitel 13) minimal implementieren + Szenarien (Spar-Invest-Mismatch) aus der Spezifikation.

6) Danach: Aufräumen der Root-Duplikate + Tests als Qualitätsnetz.
