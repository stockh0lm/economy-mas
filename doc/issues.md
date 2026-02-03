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

- [x] **Einheitliche Balance-Sheet-Namen (Company/Producer)**
  - TODO: konsistent `sight_balance` statt gemischter Namen.

- [x] **FinancialMarket abschalten**
  - Spec-Interpretation: Börsenschließung / Finanzmarkt stark reduziert.
  - Status: `FinancialMarket` existiert noch als Agent; prüfen, ob er in `main.py` tatsächlich Einfluss hat oder nur noop ist.

- [ ] **Gründliches Refaktorieren kritischer Stellen mit hoher Komplexität (KRITISCH)**
  - **Problem**: Radon-Komplexitätsanalyse zeigt mehrere Methoden mit extrem hoher zyklomatischer Komplexität
  - **Kritische Stellen identifiziert** (nach Komplexitätsgrad E > D > C > B > A):
    ```
    E (39) - agents/clearing_agent.py:183: ClearingAgent._apply_value_correction
    D (27) - main.py:398: _settle_household_estate
    D (22) - metrics.py:1071: MetricsCollector._global_money_metrics
    C (19) - metrics.py:24: apply_sight_decay
    C (19) - agents/household_agent.py:537: Household.step
    C (16) - agents/bank.py:331: WarengeldBank.enforce_inventory_backing
    C (15) - agents/state_agent.py:199: State.spend_budgets
    C (15) - agents/company_agent.py:201: Company.adjust_employees
    C (14) - agents/household_agent.py:414: Household._fertility_probability_daily
    C (13) - metrics.py:972: MetricsCollector._export_agent_metrics_df
    C (13) - metrics.py:1020: MetricsCollector.detect_economic_cycles
    C (13) - metrics.py:1222: MetricsCollector._price_dynamics
    C (12) - metrics.py:672: MetricsCollector.collect_market_metrics
    C (12) - agents/labor_market.py:160: LaborMarket.match_workers_to_jobs
    C (11) - agents/retailer_agent.py:473: RetailerAgent.sell_to_state
    C (11) - agents/retailer_agent.py:550: RetailerAgent.apply_obsolescence_write_down
    C (11) - agents/household_agent.py:471: Household._birth_new_household
    C (11) - agents/company_agent.py:330: Company.pay_wages
    ```
  - **Durchschnittliche Komplexität**: A (3.72) - insgesamt akzeptabel, aber kritische Ausreißer
  - **Priorität**: HOCH - Komplexe Methoden sind fehleranfällig und schwer zu warten
  - **Refactoring-Vorschläge**:
    1. **ClearingAgent._apply_value_correction (E-39)**:
       - Aufteilen in kleinere, fokussierte Methoden
       - Extrahiere Wertberichtigungslogik in separate Helper-Klassen
       - Führe Unit-Tests für Teilfunktionen ein
    2. **_settle_household_estate (D-27)**:
       - Zerlege in: Vermögensbewertung, Schuldenabwicklung, Erbenverteilung
       - Nutze State-Pattern für verschiedene Nachlass-Szenarien
    3. **Household.step (C-19)**:
       - Extrahiere Lebenszyklus-Logik (Geburt, Tod, Teilung)
       - Führe separate Handler für Finanz- vs. Demografie-Entscheidungen ein
    4. **MetricsCollector._global_money_metrics (D-22)**:
       - Aufteilen in: Geldmengenberechnung, Inflationsmessung, Preisindex
       - Nutze Builder-Pattern für schrittweise Metrik-Aggregation
    5. **Company.adjust_employees (C-15)**:
       - Extrahiere Einstellungs-, Entlassungs- und Gehaltslogik
       - Führe separate Strategien für Wachstum vs. Schrumpfung ein
  - **Ziel**: Reduzierung aller Methoden auf maximal B-Komplexität (≤ 10)
  - **Betroffene Dateien**:
    - `agents/clearing_agent.py` (kritisch)
    - `main.py` (kritisch)
    - `metrics.py` (mehrere kritische Methoden)
    - `agents/household_agent.py` (mehrere kritische Methoden)
    - `agents/company_agent.py` (mehrere kritische Methoden)
    - `agents/bank.py`, `agents/state_agent.py`, `agents/retailer_agent.py`
  - **Tools zur Unterstützung**:
    - Radon für kontinuierliche Komplexitätsüberwachung
    - Pytest für Unit-Tests der refaktorierten Komponenten
    - Black/Isort für konsistente Code-Formatierung
  - **Erfolgsmetriken**:
    - Reduktion der maximalen Komplexität von E(39) auf B(≤10)
    - Verbesserung der durchschnittlichen Komplexität von A(3.72) auf A(≤3.0)
    - 100% Testabdeckung für refaktorierte kritische Methoden
  - **Zeitaufwand**: 2-3 Wochen fokussierte Refactoring-Arbeit
  - **Risiko**: Mittel - Hohe Testabdeckung erforderlich, um Regressionen zu vermeiden


---

## 5) Neue ToDos (aus aktuellem Review)

- [ ] **Performance-Optimierung nach Profiling-Analyse - KRITISCH**
  - **Problem**: Profiling zeigt signifikante Performance-Bottlenecks in der Simulation und Metriken-Verarbeitung
  - **Profiling-Ergebnisse (Simulation mit 360 Schritten, 120 Haushalten, 40 Unternehmen, 12 Einzelhändlern)**:
    - **Gesamtlaufzeit**: 5.916 Sekunden
    - **Top Performance-Hotspots**:
      1. **Household-Agent Methoden** (75% der Gesamtzeit):
         - `household_agent.py:537(step)`: 43,200 Aufrufe, 1.581s (26.7% der Gesamtzeit)
         - `household_agent.py:306(consume)`: 43,200 Aufrufe, 1.070s (18.1% der Gesamtzeit)
         - `household_agent.py:414(_fertility_probability_daily)`: 43,200 Aufrufe, 0.258s (4.4%)
      2. **Retailer-Agent Methoden** (16% der Gesamtzeit):
         - `retailer_agent.py:426(sell_to_household)`: 41,424 Aufrufe, 0.851s (14.4%)
         - `retailer_agent.py:61(is_unsellable)`: 233,747 Aufrufe, 0.117s (2.0%)
      3. **Metrics-Erfassung** (8.5% der Gesamtzeit):
         - `metrics.py:494(collect_household_metrics)`: 360 Aufrufe, 0.505s (8.5%)
      4. **Python-Interne Overheads** (10% der Gesamtzeit):
         - `getattr` Aufrufe: 1,928,237 Aufrufe, 0.331s (5.6%)
         - `dict.get` Aufrufe: 1,292,361 Aufrufe, 0.141s (2.4%)
         - `sum` Aufrufe: 140,590 Aufrufe, 0.113s (1.9%)

  - **Plot Metrics Performance (8.048 Sekunden für 10 Plots)**:
    - **Top Performance-Hotspots**:
      1. **Matplotlib Text Layout**: 6.353s (79% der Gesamtzeit)
         - `matplotlib/text.py:926(get_window_extent)`: 2,835 Aufrufe, 3.179s (39.5%)
         - `matplotlib/text.py:358(_get_layout)`: 3,690 Aufrufe, 3.174s (39.4%)
      2. **CSV Parsing**: 0.894s (11.1% der Gesamtzeit)
         - `load_csv_rows`: 4 Aufrufe, 0.894s (11.1%)
      3. **Image Saving**: 1.179s (14.6% der Gesamtzeit)

  - **Optimierungsvorschläge**:
    1. **Household-Agent Optimierungen**:
       - **Caching**: Cache `fertility_probability_daily` Ergebnisse, da sich Parameter selten ändern
       - **Batch Processing**: Konsum-Logik in Vektoroperationen umwandeln statt Einzelaufrufe
       - **Attribute Access**: `getattr` Aufrufe durch direkte Attribute ersetzen oder `@property` Dekoratoren nutzen
       - **Lazy Evaluation**: Berechnungen nur durchführen wenn sich Inputs tatsächlich ändern

    2. **Retailer-Agent Optimierungen**:
       - **is_unsellable Optimierung**: Vorab-Berechnung oder Caching der Ergebnisse
       - **Batch Sell Operations**: Mehrere `sell_to_household` Aufrufe in Batch-Operationen zusammenfassen
       - **Inventory Management**: Lagerverwaltung mit numpy Arrays statt Python Listen

    3. **Metrics Optimierungen**:
       - **Incremental Updates**: Metriken inkementell aktualisieren statt vollständige Neuberechnung
       - **Batch Collection**: Metriken für alle Agenten gleichzeitig sammeln statt einzeln
       - **Memory Views**: numpy Memory Views nutzen um Kopieroperationen zu vermeiden

    4. **Plot Metrics Optimierungen**:
       - **CSV Caching**: Geparste CSV Daten zwischenspeichern für multiple Plot-Läufe
       - **Lazy Loading**: Nur benötigte Spalten laden statt vollständige DataFrames
       - **Matplotlib Optimierungen**:
         - `agg` Backend nutzen für nicht-interaktive Plots
         - Text Layout Caching aktivieren
         - Batch Rendering für multiple Figures
       - **Parallel Processing**: Plot-Generierung parallelisieren

    5. **Allgemeine Optimierungen**:
       - **Numba JIT**: Kritische numerische Funktionen mit Numba beschleunigen
       - **Cython**: Performance-kritische Module nach Cython portieren
       - **Profiling Integration**: Kontinuierliches Profiling in CI/CD Pipeline integrieren
       - **Memory Profiling**: Speichernutzung analysieren und reduzieren

  - **Erwartete Performance-Verbesserungen**:
    - **Ziel**: 50-70% Reduktion der Gesamtlaufzeit
    - **Priorität**: HOCH - Ermöglicht längere Simulationen und schnellere Iterationen
    - **Betroffene Dateien**:
      - `agents/household_agent.py` (kritisch)
      - `agents/retailer_agent.py` (kritisch)
      - `metrics.py` (kritisch)
      - `scripts/plot_metrics.py`
    - **Tools zur Unterstützung**:
      - `cProfile` für kontinuierliches Performance-Monitoring
      - `line_profiler` für zeilenweise Analyse
      - `memory_profiler` für Speicheranalyse
      - `numba` und `cython` für JIT-Kompilierung

  - **Erfolgsmetriken**:
    - Reduktion der Simulationszeit von 5.916s auf < 3.0s für 360-Schritte-Test
    - Reduktion der Plot-Generierungszeit von 8.048s auf < 4.0s
    - 80% Reduktion der `getattr` und `dict.get` Aufrufe
    - 50% Reduktion der CPU-Zyklen in Hotspot-Funktionen

  - **Risiko**: MITTEL - Umfassende Tests erforderlich um Regressionen zu vermeiden
  - **Zeitaufwand**: 1-2 Wochen fokussierte Optimierungsarbeit

  