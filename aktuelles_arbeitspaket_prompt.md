# Arbeitspaket (3 Milestones) – Kritische Bugfixes und Refactoring

Du bist ein Senior-Software-Engineer für simulationsbasierte Ökonomie (Python). Du arbeitest in einer Sandbox mit Dateisystemzugriff. Das Projekt liegt als ZIP vor: /mnt/data/wirtschaft.zip.

## Meta-Regeln (hart, um Abbrüche zu vermeiden)
Arbeite in einem Durchlauf bis zum Ende dieser Nachricht. Stelle keine Rückfragen, sondern triff sinnvolle Annahmen und dokumentiere sie kurz in Commit-Messages/Notizen.
Nach JEDEM Milestone musst du:
- doc/issues.md aktualisieren (entsprechenden Punkt auf [x] setzen oder Status anpassen)
- das Projektzip erzeugen (Name exakt: wirtschaftN.zip)
- den Download-Link im Chat als Markdown-Link ausgeben im Format:
  - Milestone N: [Download wirtschaftN.zip](sandbox:/mnt/data/wirtschaftN.zip)
Nicht anhalten, nachdem du einen Link ausgegeben hast. Fahre automatisch mit dem nächsten Milestone fort, bis Milestone 3 fertig ist oder du hart blockiert bist (z.B. Tests schlagen fehl und du kannst den Fehler nicht beheben).
Falls du blockiert bist:
- Gib trotzdem alle bis dahin erzeugten ZIP-Links aus (im oben genannten Format)
- Füge eine kurze Blocker-Diagnose (1-5 Sätze) und den konkreten nächsten Patch-Schritt hinzu.
- Erzeuge ZIPs wirklich auf dem Dateisystem via Shell (zip -r ...) und prüfe anschließend, dass die Datei existiert (z.B. ls -lh /mnt/data/wirtschaftN.zip).
Sprache: Deutsch, präzise, keine Prosa. Arbeite test-first, wo sinnvoll. Keine stillen try/except-Maskierungen.

## WICHTIG: Specs lesen
Nach dem Entpacken des Archivs MUSS doc/specs.md gelesen werden, da diese die primäre Wahrheit für die Implementierung darstellen.

## Zielbild (Kontrakt)
Behebung kritischer Bugs und Umsetzung verbleibender Aufgaben:
1. Hyperinflation / Numerische Überläufe in Preisindex-Berechnung (KRITISCH)
2. Einheitliche Balance-Sheet-Namen (Company/Producer)
3. FinancialMarket abschalten

## Explizite Referenzen in doc/issues.md
Du MUSST in jedem Milestone in mindestens einem Test/Kommentar explizit auf die zugehörigen Stellen in doc/issues.md verweisen.

## Reihenfolge (hart)
1. Hyperinflation / Numerische Überläufe (höchste Priorität - KRITISCH)
2. Einheitliche Balance-Sheet-Namen (Company/Producer)
3. FinancialMarket abschalten

## Milestones (1 → 3)

### Milestone 1 — Hyperinflation / Numerische Überläufe in Preisindex-Berechnung beheben
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 4) → „Hyperinflation / Numerische Überläufe in Preisindex-Berechnung - KRITISCH“

**Aufgaben:**

2. **Gründliche Ursachenbehandlung - Warengeld-Feedback-Mechanismen implementieren gemäß specs**:
   - **Automatische Kreditrückzahlung** (Section 4.2):
     ```python
     # In bank.py implementieren
     def auto_repay_cc_from_sight(retailer):
         excess = max(0, retailer.sight_balance - retailer.sight_allowance)
         repay_amount = min(excess, abs(retailer.cc_balance))
         # Reduziert Geldmenge automatisch
     ```
   - **Lagerbasierte Kreditlimits** (Section 4.1):
     ```python
     # In bank.py implementieren
     def enforce_inventory_backing(retailer):
         required_collateral = abs(retailer.cc_balance) * 1.2
         if retailer.inventory_value < required_collateral:
             # Erzwinge Kreditreduzierung = Geldvernichtung
     ```
   - **Wertberichtigungen** (Section 4.6):
     ```python
     # In retailer_agent.py implementieren
     def apply_inventory_write_downs():
         # Abschreibungen auf unverkäufliche Waren → Geldvernichtung
     ```
   - **Sichtguthaben-Abschmelzung** (Section 4.7):
     ```python
     # In metrics.py implementieren
     def apply_sight_decay(agents):
         # Überschüssige Sichtguthaben abbauen → Geldvernichtung
     ```

3. **Testimplementierung**:
   - Erstelle Tests für Geldmengen-Regulierung und Preisstabilität
   - Reproduktionstest für das Hyperinflationsproblem
   - Test für die neuen Feedback-Mechanismen

**Erfolgskriterien:**
- Preisindex bleibt stabil und wächst nicht exponentiell
- Keine numerischen Überläufe mehr
- Geldmenge wird automatisch durch Warengeld-Mechanismen reguliert
- Alle neuen Tests grün
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitt 4
- doc/issues.md aktualisiert (Punkt auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_hyperinflation_fix():
    """Referenz: doc/issues.md Abschnitt 4 → Hyperinflation / Numerische Überläufe"""
    # Arrange: Simulation mit Parametern, die Hyperinflation auslösen
    # Act: 10,000 Schritte durchführen
    # Assert: Preisindex bleibt stabil (< 1000)
    # Assert: Keine numerischen Überläufe
    # Assert: Geldmenge wird reguliert

def test_warengeld_feedback_mechanismen():
    """Referenz: doc/specs.md Sections 4.1, 4.2, 4.6, 4.7"""
    # Arrange: Retailer mit Überschuss-Sichtguthaben und Lager
    # Act: Feedback-Mechanismen anwenden
    # Assert: Automatische Kreditrückzahlung funktioniert
    # Assert: Lagerbasierte Kreditlimits werden durchgesetzt
    # Assert: Wertberichtigungen funktionieren
    # Assert: Sichtguthaben-Abschmelzung funktioniert
```

**Artefakt:** wirtschaft1.zip → Link ausgeben, dann automatisch weiter zu Milestone 2.

---

### Milestone 2 — Einheitliche Balance-Sheet-Namen (Company/Producer)
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 4) → „Einheitliche Balance-Sheet-Namen (Company/Producer)“

**Aufgaben:**
1. Analysiere bestehende Codebase auf gemischte Kontonamen
2. Identifiziere alle Verwendungen von nicht-kanonischen Namen (z.B. checking_account, cash, balance, deposit_balance)
3. Ersetze alle gemischten Namen durch `sight_balance` oder erstelle Alias-Properties
4. Stelle sicher, dass alle wichtigen Buchungen konsistent `sight_balance` verwenden:
   - Löhne
   - Retail-Zahlungen
   - Service-Zahlungen
   - Kreditaufnahme/tilgung
5. Aktualisiere Tests, um Konsistenz zu gewährleisten

**Erfolgskriterien:**
- Alle Company-Kontostände verwenden `sight_balance` als kanonischen Namen
- Gemischte Namen sind entweder entfernt oder als getestete Aliase implementiert
- Alle Buchungen verwenden konsistent `sight_balance`
- Alle Tests grün
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitt 4
- doc/issues.md aktualisiert (Punkt auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_company_balance_sheet_naming():
    """Referenz: doc/issues.md Abschnitt 4 → Einheitliche Balance-Sheet-Namen"""
    # Arrange: Company mit verschiedenen Buchungen
    # Act: Buchungen durchführen
    # Assert: Alle Buchungen verwenden sight_balance
    # Assert: Alias-Properties sind synchron mit sight_balance

def test_no_legacy_balance_names():
    """Referenz: doc/issues.md Abschnitt 4 → Einheitliche Balance-Sheet-Namen"""
    # Arrange: Codebase-Analyse
    # Act: Suche nach legacy Namen
    # Assert: Keine nicht-kanonischen Namen mehr vorhanden
```

**Artefakt:** wirtschaft2.zip → Link ausgeben, dann automatisch weiter zu Milestone 3.

---

### Milestone 3 — FinancialMarket abschalten
**Bezug (explizit zitieren):** doc/issues.md Abschnitt 4) → „FinancialMarket abschalten“

**Aufgaben:**
1. Analysiere, ob `FinancialMarket` Agent in `main.py` tatsächlich Einfluss hat oder nur noop ist
2. Falls noop: Agent vollständig entfernen
3. Falls Einfluss: Mechanismen identifizieren und durch alternative Implementierungen ersetzen
4. Aktualisiere Konfiguration und Tests
5. Dokumentation der Änderungen

**Erfolgskriterien:**
- FinancialMarket Agent ist entweder entfernt oder hat keinen Einfluss mehr
- Alle Tests grün
- Dokumentation aktualisiert
- Expliziter Verweis in Code/Kommentaren auf doc/issues.md Abschnitt 4
- doc/issues.md aktualisiert (Punkt auf [x] gesetzt)

**Tests (Minimum):**
```python
def test_financial_market_abgeschaltet():
    """Referenz: doc/issues.md Abschnitt 4 → FinancialMarket abschalten"""
    # Arrange: Simulation ohne FinancialMarket
    # Act: Simulation durchführen
    # Assert: Keine Fehler
    # Assert: Wirtschaftskreisläufe funktionieren ohne FinancialMarket

def test_no_financial_market_influence():
    """Referenz: doc/issues.md Abschnitt 4 → FinancialMarket abschalten"""
    # Arrange: Analyse der Simulationsergebnisse
    # Act: Vergleiche mit/ohne FinancialMarket
    # Assert: Kein Unterschied in Makro-Kennzahlen
```

**Artefakt:** wirtschaft3.zip → Link ausgeben.

---

## Harte Abschlussbedingungen
- Alle 3 Milestones wurden in der vorgegebenen Reihenfolge umgesetzt
- Nach jedem Milestone:
  - Tests passend zum Milestone laufen grün
  - doc/issues.md wurde aktualisiert (Punkt auf [x])
  - wirtschaftN.zip wurde erzeugt und als Link ausgegeben
- Kein Milestone „nur dokumentiert“ ohne Code+Test
- Kein neuer Try/Except-Teppich, keine stillen Fehlerunterdrückungen
- Alle Verweise auf doc/specs.md und doc/issues.md sind vorhanden
- Kritische Bugs sind behoben (insbesondere Hyperinflation)
