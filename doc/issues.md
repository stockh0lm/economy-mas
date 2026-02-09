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

- [~] **Gründliches Refaktorieren kritischer Stellen mit hoher Komplexität (KRITISCH)**
  - **Milestone-Tracking** (dieses Repo):
    - [x] `agents/household_agent.py: Household.step` (C-19 → B≤10) + `Household.consume` extrahiert (Milestone 1)
    - [ ] `metrics.py: MetricsCollector._global_money_metrics` (D-22 → B≤10) (Milestone 3)
    - [ ] `agents/clearing_agent.py: ClearingAgent._apply_value_correction` (E-39 → B≤10) (Milestone 5)
    - [ ] `agents/company_agent.py: Company.adjust_employees` (C-15 → B≤10) (Milestone 6)
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

## 5) Neue ToDos (aus aktuellem Review - 2026-02-09 Code Quality Audit)

- [x] **Auto-fix linting issues with ruff**
  - 252 minor issues auto-fixed (imports, annotations, formatting)
  - 444 remaining issues (mostly magic values, complexity indicators)
  - **Status**: Completed 2026-02-09

- [ ] **Critical: SimulationEngine.step() Method Refactoring**
  - **Problem**: `simulation/engine.py:577` - `step()` method is **516 lines long** with cyclomatic complexity **F(148)**, maintainability index **0.00**
  - **Indicators**:
    - 7-level nesting in company founding block
    - Handles 15 distinct phases in one method
    - Massive god method: demography, founding, mergers, labor, restocking, production, consumption, settlement, policy, clearing, environment, metrics, progress
  - **Impact**: Unmaintainable, error-prone, violates single responsibility principle
  - **Fix**: Break into ~10 private methods:
    - `_step_demography()` — death + replacement
    - `_step_company_dynamics()` — founding + mergers
    - `_step_labor_market()` — posting + matching
    - `_step_retail_restocking()` — retail ordering
    - `_step_company_operations()` — produce, wages, bankruptcy
    - `_step_household_consumption()` — household demand
    - `_step_retail_settlement()` — CC repayment, write-downs
    - `_step_monthly_policy()` — fees, revenue recirculation
    - `_step_clearing()` — audits, sight decay
    - `_step_metrics()` — data collection
  - **Files**: `simulation/engine.py`
  - **Priority**: **P0 (CRITICAL)**
  - **Effort**: High (requires comprehensive testing)

- [ ] **Critical: Massive Code Duplication Between main.py and simulation/engine.py**
  - **Problem**: Both files contain complete, duplicate copies of:
    - `create_households()` (~50 lines)
    - `create_companies()` (~20 lines)
    - `create_retailers()` (~40 lines)
    - `initialize_agents()` (~80 lines)
    - `_settle_household_estate()` (~120 lines)
    - Utility functions: `_sample_household_age_days()`, `_m1_proxy()`, `_format_duration()`, progress bar functions, coloring functions
    - `SimulationAgents` dataclass
  - **Impact**: Bug fixes must be applied in two places; maintenance burden
  - **Fix**: Keep factory functions only in `simulation/engine.py`. Reduce `main.py` to:
    - CLI parsing
    - Config loading
    - Engine instantiation and run
  - **Files**: `main.py`, `simulation/engine.py`
  - **Priority**: **P0 (CRITICAL)**
  - **Effort**: Medium

- [ ] **Critical: Duplicate config_cache.py Files**
  - **Problem**: `config_cache.py` (root) and `agents/config_cache.py` contain virtually identical implementations:
    - Both define `ConfigCache`, `AgentConfigCache`, `GlobalConfigCache`, `get_cached_config_value`
    - Engine imports from `agents.config_cache`, conftest resets both
    - Two parallel singletons can diverge; tests must know about both
  - **Fix**: Delete root-level `config_cache.py`, keep only `agents/config_cache.py`
  - **Files**: `config_cache.py`, `agents/config_cache.py`, `simulation/engine.py`, `tests/conftest.py`
  - **Priority**: **P0 (CRITICAL)**
  - **Effort**: Low

- [ ] **High Priority: Balance Access Pattern Duplicated 15+ Times**
  - **Problem**: The `sight_balance` → `checking_account` → `balance` cascade is copy-pasted across 7 files with minor variations:
    - `bank.py`: 5 instances
    - `savings_bank_agent.py`: 3 instances
    - `clearing_agent.py`: 1 instance
    - `state_agent.py`: 4 instances
    - `environmental_agency.py`: 2 instances
  - **Fix**: Extract `BalanceOps` utility module with:
    - `credit_balance(agent, amount) -> float`
    - `debit_balance(agent, amount) -> float`
    - `get_balance(agent) -> float`
  - **Files**: `agents/bank.py`, `agents/savings_bank_agent.py`, `agents/clearing_agent.py`, `agents/state_agent.py`, `agents/environmental_agency.py`
  - **Priority**: **P1 (HIGH)**
  - **Effort**: Medium

- [ ] **High Priority: Retailer Agent sell_to_household vs sell_to_state Duplication**
  - **Problem**: `retailer_agent.py:565-680` - Two methods are ~70 lines of nearly identical code. Only differences:
    - State has `budget_bucket` check
    - Household tracks `_step_sales_units`
  - **Fix**: Extract `_execute_sale(buyer, budget, budget_bucket=None)` method
  - **Files**: `agents/retailer_agent.py`
  - **Priority**: **P1 (HIGH)**
  - **Effort**: Medium

- [ ] **High Priority: MetricsCollector Class-Level Mutable Defaults**
  - **Problem**: `metrics/collector.py:25-39` declares dict/set attributes as class variables with mutable defaults:
    ```python
    class MetricsCollector:
        bank_metrics: Dict[str, Dict[TimeStep, MetricDict]] = {}
        household_metrics: Dict[str, Dict[TimeStep, MetricDict]] = {}
        # ... 6 more mutable class vars
    ```
    Although `__init__` re-assigns them, class-level mutables remain a shared-state trap
  - **Fix**: Remove class-level declarations; initialize only in `__init__`
  - **Files**: `metrics/collector.py`
  - **Priority**: **P1 (HIGH)**
  - **Effort**: Low

- [ ] **High Priority: 262 Magic Values in Codebase**
  - **Problem**: Hard-coded thresholds, epsilon values, and policy constants throughout:
    - `1e-9` epsilon used 6+ times
    - Thresholds (e.g., `0.01`, `0.5`, `10000`, etc.)
    - Policy parameters scattered across files
  - **Fix**:
    1. Match existing config items (e.g., `company.inventory_holding_cost_per_unit`)
    2. Add new config items for undocumented constants
    3. Extract to named constants for frequently-used values
  - **Files**: All agent files, simulation engine
  - **Priority**: **P1 (HIGH)**
  - **Effort**: Medium-High

- [ ] **Medium Priority: Mock Import in Production Code**
  - **Problem**: `savings_bank_agent.py:19` imports `unittest.mock.Mock` and guards balance updates with `isinstance(attr_val, Mock)` in 3 methods
  - **Fix**: Remove Mock guard; use proper protocols or user-defined traits
  - **Files**: `agents/savings_bank_agent.py`
  - **Priority**: **P2 (MEDIUM)**
  - **Effort**: Low

- [ ] **Medium Priority: MetricsCollector Module Singleton Unused**
  - **Problem**: `metrics/__init__.py:82` creates `metrics_collector = MetricsCollector()` at import time
    - This singleton is never used by the simulation (engine creates its own instance)
    - Creates confusion and unnecessary imports
  - **Fix**: Remove module-level `metrics_collector` instance
  - **Files**: `metrics/__init__.py`
  - **Priority**: **P2 (MEDIUM)**
  - **Effort**: Low

- [ ] **Low Priority: Legacy `metrics.py` Shim**
  - **Problem**: Root-level `metrics.py` is a deprecated re-export shim for `metrics/` package
    - Creates import ambiguity
    - Most files now import correctly from `metrics/`
  - **Fix**: Delete `metrics.py`, update any remaining imports
  - **Files**: `metrics.py`
  - **Priority**: **P3 (LOW)**
  - **Effort**: Low-Medium

- [ ] **Low Priority: Duplicate Protocols in protocols.py**
  - **Problem**: `agents/protocols.py` has duplicates:
    - `AgentWithBalance` (line 11) vs `WealthAgent` (line 46) — identical
    - `AgentWithImpact` (line 18) vs `EnvironmentalImpactAgent` (line 53) — identical
    - `BillableImpactAgent` (line 66) missing `@runtime_checkable` decorator
  - **Fix**: Deregister duplicates, add missing decorator
  - **Files**: `agents/protocols.py`
  - **Priority**: **P3 (LOW)**
  - **Effort**: Low

- [ ] **Low Priority: warengeld_accounting.py Dead Code Decision**
  - **Problem**: `warengeld_accounting.py` defines `DoubleEntryAccounting`, `MoneyTransactionPipeline`, `MoneySupplyGuardian` but:
    - Not imported or used anywhere in the codebase
    - Real money flows happen via direct attribute mutation, bypassing this system
    - Creates false impression of enforced double-entry accounting
  - **Decision Required**: Either:
    1. Integrate as canonical transaction layer, OR
    2. Delete as dead code
  - **Spec Violation**: The spec (Section 3) implies double-entry accounting, but current implementation doesn't use it
  - **Files**: `warengeld_accounting.py` + any potential integration points
  - **Priority**: **P2 (MEDIUM)** — needs architectural decision
  - **Effort**: High (if integrating) or Low (if deleting)

- [ ] **Spec Compliance Note: String Lifecycle Returns**
  - **Problem**: Companies return string literals for lifecycle states (`"DEAD"`, `"LIQUIDATED"`)
  - **Spec**: Should be an Enum per proper Python practice
  - **Files**: `agents/company_agent.py`
  - **Priority**: **P3 (LOW)**
  - **Effort**: Low

- [ ] **Spec Compliance Note: Logging Boilerplate**
  - **Problem**: All agents manually prefix logging with `f"{AgentType} {self.unique_id}: ..."` (~100+ occurrences)
  - **Fix**: Add `self._log(msg, level)` to `BaseAgent` that auto-prefixes
  - **Files**: All agent files
  - **Priority**: **P3 (LOW)**
  - **Effort**: Medium

- [ ] **Spec Compliance Note: Engine Mutates Module Privates**
  - **Problem**: `engine.py:468,493` sets `household_module._DEFAULT_NP_RNG` and `consumption_module._DEFAULT_NP_RNG` directly
  - **Fix**: Replace with proper dependency injection (pass RNG via parameters)
  - **Files**: `simulation/engine.py`, `agents/household/consumption.py`, `agents/household/demography.py`
  - **Priority**: **P2 (MEDIUM)**
  - **Effort**: Medium

- [ ] **Spec Compliance Note: GLOBAL State via CONFIG_MODEL**
  - **Problem**: Using `CONFIG_MODEL` as default fallback (21 files import it)
    - Makes implicit coupling, tests less reliable
  - **Fix**: Make `config` parameter mandatory (no fallback to global)
  - **Files**: All agent files, configuration access points
  - **Priority**: **P2 (MEDIUM)**
  - **Effort**: High

---

## 6) Test Infrastructure Issues

- [x] **Fix: test_household_components.py test_batch_consumption bug**
  - **Problem**: Line 140 uses undefined variable `i` (should be loop variable from line 136)
  - **Fix**: Changed to use `enumerate` with `idx`
  - **Status**: Completed 2026-02-09

---

- [~] **Performance-Optimierung nach Profiling-Analyse - KRITISCH** *(Status: Milestone 1 erledigt – Logging + Plot-Metrics + erste Hotloop-Fixes)*
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


  - **Risiko**: MITTEL - Umfassende Tests erforderlich um Regressionen zu vermeiden
  - **Zeitaufwand**: 1-2 Wochen fokussierte Optimierungsarbeit (+2-3 Tage für High-Performance Logging)

