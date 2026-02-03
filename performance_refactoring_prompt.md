# Arbeitspaket (4 Milestones) – Performance-Optimierung und Refactoring

Du bist ein Senior-Software-Engineer für simulationsbasierte Ökonomie (Python). Du arbeitest in einer Sandbox mit Dateisystemzugriff. Das Projekt liegt als ZIP vor: /mnt/data/wirtschaft.zip.

## Meta-Regeln (hart, um Abbrüche zu vermeiden)
Arbeite in einem Durchlauf bis zum Ende dieser Nachricht. Stelle keine Rückfragen, sondern triff sinnvolle Annahmen und dokumentiere sie kurz in Commit-Messages/Notizen.
Nach JEDEM Milestone musst du:
- doc/issues.md aktualisieren (entsprechenden Punkt auf [x] setzen oder Status anpassen)
- das Projektzip erzeugen (Name exakt: wirtschaftN.zip)
- den Download-Link im Chat als Markdown-Link ausgeben im Format:
  - Milestone N: [Download wirtschaftN.zip](sandbox:/mnt/data/wirtschaftN.zip)
Nicht anhalten, nachdem du einen Link ausgegeben hast. Fahre automatisch mit dem nächsten Milestone fort, bis Milestone 2 fertig ist oder du hart blockiert bist (z.B. Tests schlagen fehl und du kannst den Fehler nicht beheben).
Falls du blockiert bist:
- Gib trotzdem alle bis dahin erzeugten ZIP-Links aus (im oben genannten Format)
- Füge eine kurze Blocker-Diagnose (1-5 Sätze) und den konkreten nächsten Patch-Schritt hinzu.
- Erzeuge ZIPs wirklich auf dem Dateisystem via Shell (zip -r ...) und prüfe anschließend, dass die Datei existiert (z.B. ls -lh /mnt/data/wirtschaftN.zip).
Sprache: Deutsch, präzise, keine Prosa. Arbeite test-first, wo sinnvoll. Keine stillen try/except-Maskierungen.

## WICHTIG: Specs lesen
Nach dem Entpacken des Archivs MUSS doc/specs.md gelesen werden, da diese die primäre Wahrheit für die Implementierung darstellen.

## LLM-Freiheit und Priorisierung
**WICHTIG:** Die folgenden Refactoring- und Performance-Verbesserungsitems sind als Vorschläge zu betrachten. Du hast die Freiheit, bessere Lösungen zu implementieren, die die Ziele effizienter erreichen.

**Priorisierung:**
1. **Einfache, fertige Lösungen bevorzugen**: Optimierte Bibliotheken, geändertes Logging mit RAM-Nutzung als Beschleunigung, etc.
2. **Überschneidungen nutzen**: Performance- und Refactoring-Maßnahmen sollten synergistisch wirken
3. **Pragmatische Implementierung**: Lieber 80% der Verbesserung mit 20% Aufwand als Perfektionismus

## Zielbild (Kontrakt)
Performance-Optimierung und Refactoring kritischer Codebereiche:
1. Gründliches Refaktorieren kritischer Stellen mit hoher Komplexität
2. Performance-Optimierung nach Profiling-Analyse

## Explizite Referenzen in doc/issues.md
Du MUSST in jedem Milestone in mindestens einem Test/Kommentar explizit auf die zugehörigen Stellen in doc/issues.md verweisen.

## Reihenfolge (hart)
1. Einfache, isolierte Optimierungen (minimale Abhängigkeiten, schneller Nutzen)
2. Household-Agent: Refactoring + Performance (einfache Synergien, hoher Nutzen)
3. Metrics: Refactoring + Performance (mittlere Komplexität, gute Synergien)
4. ClearingAgent + Company + Retailer: Refactoring + Performance (komplexere Fälle)

## Milestones (1 → 4)

### Milestone 1 — Einfache, isolierte Optimierungen (minimale Abhängigkeiten)
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 5) → „Performance-Optimierung nach Profiling-Analyse“

**Aufgaben - Unabhängige, einfache Optimierungen**:
1. **High-Performance Logging Implementation** (4 Tage Plan, isoliert):
   - Implementiere `HighPerformanceLogHandler` in `logger.py`
   - RAM-Pufferung für Logging (50MB Standardpuffer)
   - Konfiguration in `config.py` hinzufügen
   - Integration in Hauptsimulation
   - Performance-Messung und Feinabstimmung

2. **Plot Metrics Optimierungen** (einfach, isoliert):
   - **CSV Caching**: Geparste CSV Daten zwischenspeichern für multiple Plot-Läufe
   - **Lazy Loading**: Nur benötigte Spalten laden statt vollständige DataFrames
   - **Matplotlib Optimierungen**:
     - `agg` Backend nutzen für nicht-interaktive Plots
     - Text Layout Caching aktivieren
     - Batch Rendering für multiple Figures

3. **Einfache Code-Optimierungen**:
   - Ersetze `getattr` Aufrufe durch direkte Attribute oder `@property` Dekoratoren
   - Ersetze `dict.get` Aufrufe durch direkte Dictionary-Zugriffe wo möglich
   - Führe einfache Caching-Mechanismen ein

4. **Qualitätssicherung**:
   - Unit-Tests für neue Logging-Funktionalität
   - Performance-Messung vor/nach Änderungen
   - Validierung der korrekten Funktionalität

**Erfolgskriterien:**
- High-Performance Logging implementiert und funktionstüchtig
- Plot-Generierungszeit reduziert von 8.048s auf < 5.0s (38% Reduktion)
- 50% Reduktion der `getattr` und `dict.get` Aufrufe
- Keine Regressionen in bestehenden Tests
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitt 5
- doc/issues.md aktualisiert (entsprechende Punkte auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_high_performance_logging():
    """Referenz: doc/issues.md Abschnitt 5 → High-Performance Logging"""
    # Arrange: Simulation mit Logging
    # Act: High-Performance Logging aktivieren
    # Assert: Logging funktioniert korrekt
    # Assert: Performance verbessert (RAM-Pufferung aktiv)

def test_plot_metrics_csv_caching():
    """Referenz: doc/issues.md Abschnitt 5 → Plot Metrics CSV Caching"""
    # Arrange: 10 Plots mit Standarddaten
    # Act: Optimierte Plot-Generierung mit Caching
    # Assert: Korrekte Plots
    # Assert: Performance < 5.0s (38% Reduktion)
```

**Artefakt:** wirtschaft1.zip → Link ausgeben, dann automatisch weiter zu Milestone 2.

---

### Milestone 2 — Household-Agent: Refactoring + Performance (Synergien nutzen)
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 4) → „Gründliches Refaktorieren“ + Abschnitt 5) → „Performance-Optimierung“

**Aufgaben - Synergistische Implementierung**:
1. **Gemeinsame Analyse**:
   - Führe Radon-Komplexitätsanalyse und cProfile-Profiling für Household-Agent durch
   - Identifiziere Überlappungen zwischen Komplexität und Performance-Hotspots

2. **Household.step Refactoring + Performance** (gleicher Code, gemeinsame Optimierung):
   - *Refactoring*: Lebenszyklus-Logik extrahieren, separate Handler für Finanz/Demografie
   - *Performance*: Caching für `fertility_probability_daily`, Batch Processing, direkte Attribute
   - *Synergie*: Durch Refactoring werden Performance-Optimierungen einfacher
   - *Freiheit*: Event-basiertes System oder andere Architektur, wenn besser

3. **Household.consume Performance-Optimierung**:
   - *Performance*: Batch Processing, Vektoroperationen statt Einzelaufrufe
   - *Refactoring*: Extrahiere Konsum-Logik in separate, testbare Methode
   - *Synergie*: Refactoring ermöglicht effizientere Batch-Operationen

4. **Gemeinsame Qualitätssicherung**:
   - Unit-Tests für refaktorierte und optimierte Komponenten
   - Performance-Messung vor/nach Änderungen
   - Radon-Analyse zur Validierung der Komplexitätsreduktion

**Erfolgskriterien:**
- Household.step Komplexität reduziert von C(19) auf B(≤10)
- Household-Agent Performance verbessert um 50% (von 1.581s auf < 0.8s für 43,200 Aufrufe)
- 80% Reduktion der `getattr` Aufrufe in Household-Agent
- Keine Regressionen in bestehenden Tests
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitte 4 & 5
- doc/issues.md aktualisiert (entsprechende Punkte auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_household_refactoring_performance():
    """Referenz: doc/issues.md Abschnitte 4 & 5 → Household-Agent Synergien"""
    # Arrange: 120 Haushalte, komplexer Zustand
    # Act: Refaktorierte und optimierte step-Methode aufrufen
    # Assert: Korrektes Verhalten
    # Assert: Komplexität ≤ B (≤10)
    # Assert: Performance < 0.8s für 43,200 Aufrufe

def test_household_consume_batch_performance():
    """Referenz: doc/issues.md Abschnitte 4 & 5 → Household-Agent Synergien"""
    # Arrange: 120 Haushalte mit Konsum-Entscheidungen
    # Act: Optimierte Batch-Konsum-Logik
    # Assert: Korrekte Konsum-Entscheidungen
    # Assert: Performance < 0.5s für 43,200 Aufrufe
```

**Artefakt:** wirtschaft2.zip → Link ausgeben, dann automatisch weiter zu Milestone 3.

---

### Milestone 3 — Metrics: Refactoring + Performance (Synergien nutzen)
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 4) → „Gründliches Refaktorieren“ + Abschnitt 5) → „Performance-Optimierung“

**Aufgaben - Synergistische Implementierung**:
1. **Gemeinsame Analyse**:
   - Führe Radon-Komplexitätsanalyse und cProfile-Profiling für MetricsCollector durch
   - Identifiziere Überlappungen zwischen Komplexität und Performance-Hotspots

2. **MetricsCollector._global_money_metrics Refactoring + Performance** (gleicher Code):
   - *Refactoring*: Aufteilen in Geldmengenberechnung, Inflationsmessung, Preisindex
   - *Performance*: Inkrementelle Updates, Batch Collection, Memory Views
   - *Synergie*: Durch Aufteilung werden inkrementelle Updates einfacher
   - *Freiheit*: Builder-Pattern oder andere Architektur, wenn effizienter

3. **MetricsCollector.collect_household_metrics Performance-Optimierung**:
   - *Performance*: Batch Collection für alle Haushalte gleichzeitig
   - *Refactoring*: Extrahiere Metrik-Berechnung in separate Helper-Methoden
   - *Synergie*: Refactoring ermöglicht effizientere Batch-Operationen

4. **Gemeinsame Qualitätssicherung**:
   - Unit-Tests für refaktorierte und optimierte Metrik-Komponenten
   - Performance-Messung vor/nach Änderungen
   - Validierung der Metrik-Konsistenz

**Erfolgskriterien:**
- MetricsCollector._global_money_metrics Komplexität reduziert von D(22) auf B(≤10)
- Metrics-Erfassung Performance verbessert um 60% (von 0.505s auf < 0.2s)
- 50% Reduktion der CPU-Zyklen in Metrik-Hotspots
- Keine Regressionen in Metrik-Ergebnissen
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitte 4 & 5
- doc/issues.md aktualisiert (entsprechende Punkte auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_metrics_refactoring_performance():
    """Referenz: doc/issues.md Abschnitte 4 & 5 → Metrics Synergien"""
    # Arrange: Komplexe Metrik-Daten
    # Act: Refaktorierte und optimierte _global_money_metrics
    # Assert: Korrekte Metriken
    # Assert: Komplexität ≤ B (≤10)
    # Assert: Performance < 0.2s

def test_household_metrics_batch_performance():
    """Referenz: doc/issues.md Abschnitte 4 & 5 → Metrics Synergien"""
    # Arrange: 120 Haushalte mit Metrik-Daten
    # Act: Optimierte Batch-Metrik-Erfassung
    # Assert: Korrekte Metriken
    # Assert: Performance < 0.15s
```

**Artefakt:** wirtschaft3.zip → Link ausgeben, dann automatisch weiter zu Milestone 4.

---

### Milestone 4 — ClearingAgent + Company + Retailer: Refactoring + Performance
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 4) → „Gründliches Refaktorieren“ + Abschnitt 5) → „Performance-Optimierung“

**Aufgaben - Synergistische Implementierung für komplexere Fälle**:
1. **ClearingAgent._apply_value_correction Refactoring + Performance**:
   - *Refactoring*: Aufteilen in kleinere Methoden, Helper-Klassen
   - *Performance*: Optimierte Datenstrukturen für Wertberichtigungen
   - *Synergie*: Durch Aufteilung werden Performance-Optimierungen einfacher

2. **Company.adjust_employees Refactoring**:
   - *Refactoring*: Einstellungs-/Entlassungslogik extrahieren, separate Strategien
   - *Performance*: Caching für häufige Berechnungen

3. **Retailer-Agent Performance-Optimierung**:
   - *Performance*: is_unsellable Caching, Batch Sell Operations
   - *Refactoring*: Extrahiere Lagerverwaltung in separate Klasse

4. **Gemeinsame Qualitätssicherung**:
   - Unit-Tests für alle Änderungen
   - Performance-Messung vor/nach Optimierungen
   - Integrationstests für kritische Pfade

**Erfolgskriterien:**
- ClearingAgent._apply_value_correction Komplexität reduziert von E(39) auf B(≤10)
- Gesamt-Performance verbessert um 50-70% (von 5.916s auf < 3.0s)
- Keine Regressionen in bestehenden Tests
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitte 4 & 5
- doc/issues.md aktualisiert (entsprechende Punkte auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_clearing_refactoring_performance():
    """Referenz: doc/issues.md Abschnitte 4 & 5 → ClearingAgent Synergien"""
    # Arrange: Clearing mit komplexem Wertberichtigungsfall
    # Act: Refaktorierte Methode aufrufen
    # Assert: Korrekte Wertberichtigung
    # Assert: Komplexität ≤ B (≤10)
    # Assert: Performance verbessert
```

**Artefakt:** wirtschaft4.zip → Link ausgeben.

---

## Harte Abschlussbedingungen
- Alle 4 Milestones wurden in der vorgegebenen Reihenfolge umgesetzt
- Nach jedem Milestone:
  - Tests passend zum Milestone laufen grün
  - doc/issues.md wurde aktualisiert (Punkt auf [x])
  - wirtschaftN.zip wurde erzeugt und als Link ausgegeben
- Kein Milestone „nur dokumentiert“ ohne Code+Test
- Kein neuer Try/Except-Teppich, keine stillen Fehlerunterdrückungen
- Alle Verweise auf doc/specs.md und doc/issues.md sind vorhanden
- Kritische Performance-Probleme sind behoben
- LLM hat Freiheit für bessere Lösungen genutzt
- Synergien zwischen Refactoring und Performance wurden optimal genutzt
- Einfache, isolierte Optimierungen wurden vorgezogen
