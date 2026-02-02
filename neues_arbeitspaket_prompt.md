# Arbeitspaket (6 Milestones) – Wachstumsverhalten + verbleibende Aufgaben

Du bist ein Senior-Software-Engineer für simulationsbasierte Ökonomie (Python). Du arbeitest in einer Sandbox mit Dateisystemzugriff. Das Projekt liegt als ZIP vor: /mnt/data/wirtschaft.zip.

## Meta-Regeln (hart, um Abbrüche zu vermeiden)
Arbeite in einem Durchlauf bis zum Ende dieser Nachricht. Stelle keine Rückfragen, sondern triff sinnvolle Annahmen und dokumentiere sie kurz in Commit-Messages/Notizen.
Nach JEDEM Milestone musst du:
- doc/issues.md aktualisieren (entsprechenden Punkt auf [x] setzen oder Status anpassen)
- das Projektzip erzeugen (Name exakt: wirtschaftN.zip)
- den Download-Link im Chat als Markdown-Link ausgeben im Format:
  - Milestone N: [Download wirtschaftN.zip](sandbox:/mnt/data/wirtschaftN.zip)
Nicht anhalten, nachdem du einen Link ausgegeben hast. Fahre automatisch mit dem nächsten Milestone fort, bis Milestone 6 fertig ist oder du hart blockiert bist (z.B. Tests schlagen fehl und du kannst den Fehler nicht beheben).
Falls du blockiert bist:
- Gib trotzdem alle bis dahin erzeugten ZIP-Links aus (im oben genannten Format)
- Füge eine kurze Blocker-Diagnose (1-5 Sätze) und den konkreten nächsten Patch-Schritt hinzu.
- Erzeuge ZIPs wirklich auf dem Dateisystem via Shell (zip -r ...) und prüfe anschließend, dass die Datei existiert (z.B. ls -lh /mnt/data/wirtschaftN.zip).
Sprache: Deutsch, präzise, keine Prosa. Arbeite test-first, wo sinnvoll. Keine stillen try/except-Maskierungen.

## WICHTIG: Specs lesen
Nach dem Entpacken des Archivs MUSS doc/specs.md gelesen werden, da diese die primäre Wahrheit für die Implementierung darstellen.

## Zielbild (Kontrakt)
Vollständige Implementierung der verbleibenden Aufgaben:
1. Einfaches Wachstums- und Sterbe-Verhalten für Haushalte und Unternehmen
2. Warenbewertung & Abschreibung
3. Fraud/Wertberichtigung-Rechenregel
4. Sparkassen-Regeln (Spargrenze / Invest-Nachfrage-Kopplung)
5. Agent-IDs standardisieren
6. Golden-run Snapshot

## Explizite Referenzen in doc/issues.md
Du MUSST in jedem Milestone in mindestens einem Test/Kommentar explizit auf die zugehörigen Stellen in doc/issues.md verweisen.

## Reihenfolge (hart)
1. Einfaches Wachstums- und Sterbe-Verhalten (neu, hohe Priorität)
2. Warenbewertung & Abschreibung
3. Fraud/Wertberichtigung-Rechenregel
4. Sparkassen-Regeln (Spargrenze / Invest-Nachfrage-Kopplung)
5. Agent-IDs standardisieren
6. Golden-run Snapshot

## Milestones (1 → 6)

### Milestone 1 — Einfaches Wachstums- und Sterbe-Verhalten für Haushalte und Unternehmen implementieren
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 4) → „Einfaches Wachstums- und Sterbe-Verhalten für Haushalte und Unternehmen implementieren“

**Aufgaben:**
1. Implementiere Wachstums- und Sterbe-Verhalten für Haushalte:
   - Natürliches Wachstum durch Geburten (basierend auf Alter, Einkommen, Sparverhalten)
   - Natürliches Sterben (basierend auf Alter und probabilistischen Mortalitätsmodellen)
   - Generationenwechsel mit realistischem Vermögensübergang
2. Implementiere Wachstums- und Sterbe-Verhalten für Unternehmen:
   - Gründungsmechanismen (basierend auf Marktchancen und Kapitalverfügbarkeit)
   - Insolvenzmechanismen (basierend auf Cashflow, Bilanzkennzahlen und Marktbedingungen)
   - Wachstum durch Expansion und Fusionen
3. Konfigurierbare Wachstums- und Sterberaten implementieren
4. Realistische Altersverteilung und Demografiedynamik sicherstellen
5. Integration mit bestehenden Wirtschaftskreisläufen
6. Kompatibilität mit Warengeld-Buchführungssystem gewährleisten

**Erfolgskriterien:**
- Wachstums- und Sterbe-Verhalten für Haushalte implementiert
- Wachstums- und Sterbe-Verhalten für Unternehmen implementiert
- Konfigurierbare Raten funktionieren
- Realistische Demografiedynamik
- Integration mit Wirtschaftskreisläufen funktioniert
- Alle Tests grün
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitt 4
- doc/issues.md aktualisiert (Punkt auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_wachstums_sterbe_verhalten():
    """Referenz: doc/issues.md Abschnitt 4 → Einfaches Wachstums- und Sterbe-Verhalten"""
    # Arrange: Simulation mit Haushalten und Unternehmen
    # Act: Mehrere Zeitschritte durchführen
    # Assert: Wachstum und Sterben entsprechend der konfigurierten Raten
    # Assert: Realistische Altersverteilung
    # Assert: Integration mit Wirtschaftskreisläufen funktioniert
```

**Artefakt:** wirtschaft1.zip → Link ausgeben, dann automatisch weiter zu Milestone 2.

---

### Milestone 2 — Warenbewertung & Abschreibung
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 2) → „Warenbewertung & Abschreibung“

**Aufgaben:**
1. Implementiere erweiterte Inventarbewertung:
   - Einstandspreis, Marktpreis, Niederstwertprinzip
   - „Unverkaufbar“-Kriterium
   - Artikelgruppen
2. Implementiere Obsoleszenz-Write-down:
   - `obsolescence_rate` pro Artikelgruppe
   - Automatische Abschreibung
3. Aktualisiere RetailerAgent

**Erfolgskriterien:**
- Warenbewertung nach Spec implementiert
- Abschreibung funktioniert
- Test grün
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitt 2
- doc/issues.md aktualisiert (Punkt auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_warenbewertung_abschreibung():
    """Referenz: doc/issues.md Abschnitt 2 → Warenbewertung & Abschreibung"""
    # Arrange: Retailer mit Inventory
    # Act: Abschreibung durchführen
    # Assert: inventory_value korrekt reduziert
```

**Artefakt:** wirtschaft2.zip → Link ausgeben, dann automatisch weiter zu Milestone 3.

---

### Milestone 3 — Fraud/Wertberichtigung-Rechenregel
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 2) → „Fraud/Wertberichtigung-Rechenregel“

**Aufgaben:**
1. Implementiere exakte Rechts-/Buchungslogik:
   - Reserve → Retailer-Sicht → Empfänger-Haircut (pro-rata via Bank-Ledger) → Bankreserve
2. Implementiere faire/robuste Haircut-Verteilung
3. Aktualisiere Clearing-Agent

**Erfolgskriterien:**
- Wertberichtigung nach Spec implementiert
- Haircuts fair verteilt
- Test grün
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitt 2
- doc/issues.md aktualisiert (Punkt auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_fraud_wertberichtigung():
    """Referenz: doc/issues.md Abschnitt 2 → Fraud/Wertberichtigung-Rechenregel"""
    # Arrange: Clearing mit Fraud-Fall
    # Act: Wertberichtigung durchführen
    # Assert: Korrekte Buchung und Haircut-Verteilung
```

**Artefakt:** wirtschaft3.zip → Link ausgeben, dann automatisch weiter zu Milestone 4.

---

### Milestone 4 — Sparkassen-Regeln (Spargrenze / Invest-Nachfrage-Kopplung)
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 2) → „Sparkassen-Regeln (Spargrenze / Invest-Nachfrage-Kopplung)“

**Aufgaben:**
1. Ersetze `max_savings_per_account` durch konfigurierbare Obergrenzen:
   - Getrennte Obergrenzen für Haushalte und Unternehmen
   - Politisches Steuerinstrument
2. Kopple an erwartete Kreditnachfrage
3. Aktualisiere SavingsBank-Agent

**Erfolgskriterien:**
- Getrennte Spargrenzen implementiert
- Kopplung an Kreditnachfrage
- Test grün
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitt 2
- doc/issues.md aktualisiert (Punkt auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_sparkassen_spargrenzen():
    """Referenz: doc/issues.md Abschnitt 2 → Sparkassen-Regeln"""
    # Arrange: SavingsBank mit verschiedenen Agenten
    # Act: Spargrenzen anwenden
    # Assert: Korrekte Obergrenzen pro Agententyp
```

**Artefakt:** wirtschaft4.zip → Link ausgeben, dann automatisch weiter zu Milestone 5.

---

### Milestone 5 — Agent-IDs standardisieren
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 5) → „Agent-IDs auf einfache Finance-Sim-Konvention standardisieren“

**Aufgaben:**
1. Sicherstellen, dass alle Agenten-IDs strikt diesem Muster folgen:
   - `household_<n>`, `company_<n>`, `retailer_<n>`
2. Singleton-Agenten klar benennen:
   - `state_0`, `clearing_0`, `labor_market_0`
3. Aktualisiere ID-Generierung in Births/Turnover
4. Validierungstest erstellen

**Erfolgskriterien:**
- Alle Agenten-IDs standardisiert
- Singleton-Agenten klar benannt
- Test grün
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitt 5
- doc/issues.md aktualisiert (Punkt auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_agent_ids_standardisiert():
    """Referenz: doc/issues.md Abschnitt 5 → Agent-IDs standardisieren"""
    # Arrange: Neue Agenten erstellen
    # Act: IDs prüfen
    # Assert: IDs folgen Standardmuster
```

**Artefakt:** wirtschaft5.zip → Link ausgeben, dann automatisch weiter zu Milestone 6.

---

### Milestone 6 — Golden-run Snapshot
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 3) → „Golden-run Snapshot“

**Aufgaben:**
1. Implementiere kurzen Seeded-Run (z.B. 30 Tage)
2. Definiere erwartete Makro-Kennzahlen-Bänder
3. Erstelle Snapshot-Test
4. Dokumentation der erwarteten Ergebnisse

**Erfolgskriterien:**
- Golden-run implementiert
- Erwartete Kennzahlen definiert
- Test grün
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitt 3
- doc/issues.md aktualisiert (Punkt auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_golden_run_snapshot():
    """Referenz: doc/issues.md Abschnitt 3 → Golden-run Snapshot"""
    # Arrange: Seeded-Run mit 30 Tagen
    # Act: Simulation durchführen
    # Assert: Ergebnisse innerhalb erwarteter Bänder
```

**Artefakt:** wirtschaft6.zip → Link ausgeben.

---

## Harte Abschlussbedingungen
- Alle 6 Milestones wurden in der vorgegebenen Reihenfolge umgesetzt
- Nach jedem Milestone:
  - Tests passend zum Milestone laufen grün
  - doc/issues.md wurde aktualisiert (Punkt auf [x])
  - wirtschaftN.zip wurde erzeugt und als Link ausgegeben
- Kein Milestone „nur dokumentiert“ ohne Code+Test
- Kein neuer Try/Except-Teppich, keine stillen Fehlerunterdrückungen
- Alle Verweise auf doc/specs.md und doc/issues.md sind vorhanden
