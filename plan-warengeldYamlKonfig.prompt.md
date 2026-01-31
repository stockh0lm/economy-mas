# Plan: YAML-Konfiguration + Skalierung + Tests für Warengeld-Güterzyklus (Scope bis Tests)

Dieses Dokument ist die **konkrete Roadmap** für die nächsten Änderungen.

**Wichtig:** Der Scope endet **bewusst** bei den neuen Tests für den Warengeld-Güterzyklus.
Die eigentliche Umstellung der Simulation-Logik auf echtes Warengeld (Emission/Vernichtung) ist danach geplant, aber **nicht Teil dieses Plans**. Offene Punkte dazu stehen in `doc/issues.md`.

---

## Ziele (Scope)

1. Simulation mit **konfigurierbar vielen Haushalten und Firmen** starten können (ohne lange Listen per Hand).
2. Konfiguration in eine **YAML-Datei** verlagern und beim Einlesen **Pydantic-validieren**.
3. Testabdeckung erhöhen: neue Tests, die den **Warengeld-Güterzyklus** als Zielverhalten beschreiben (vor der eigentlichen Implementierung).

---

## Nicht-Ziele (Out of scope)

- Umbau der Geldlogik in `Company`, `Household` und `WarengeldBank` auf echte Warengeld-Emission/Einzug.
- Umbau der Lohn-/Einkommenslogik.
- Anpassung der vorhandenen Company-Step-Regressions-Tests an das neue Regime.

Diese Punkte werden nach den Tests bearbeitet (siehe `doc/issues.md`).

---

## 1) YAML-Migration (Konfigurationsquelle) + Validierung

### Anforderungen
- Eine YAML-Datei (z.B. `config.yaml`) soll die bisherigen `SimulationConfig`-Optionen setzen können.
- Beim Laden muss **Schema-Validierung** stattfinden (via Pydantic, nicht „hand-rolled“).
- Die bestehende Default-Konfiguration (ohne YAML) muss weiterhin funktionieren.

### Umsetzung (geplant)
- Abhängigkeit hinzufügen: YAML-Parser (z.B. `PyYAML`).
- In `config.py`:
  - neue Funktion `load_simulation_config_from_yaml(path)` (Name kann abweichen)
  - YAML -> dict -> `load_simulation_config(data)` (damit bleibt Validierung zentral)
  - saubere Fehlermeldungen bei Parsing-/Validation-Fehlern
- In `main.py` (oder zentral in `config.py`):
  - optionaler YAML-Pfad über Environment Variable oder CLI-Arg

### Done-Kriterien
- Es gibt mindestens einen Test, der eine YAML-Konfig lädt und validiert.
- Ungültige YAML/Config führt zu einem klaren Fehler (Test erwartet Exception).

---

## 2) Skalierung: viele Haushalte/Firmen ohne Handarbeit

### Anforderungen
- Agentenzahlen sollen einfach per Konfig einstellbar sein.
- Bei gleichen Startparametern sollen Agenten deterministisch erzeugt werden können.

### Umsetzung (geplant, bevorzugte Variante: Generator + Template)
- `SimulationConfig` um einen Abschnitt erweitern, z.B. `population`:
  - `num_households: int`
  - `num_companies: int`
  - `household_template: {income, land_area, environmental_impact}`
  - `company_template: {production_capacity, land_area, environmental_impact}`
  - optional: `seed` (für spätere Zufallsvarianten)
- `main.initialize_agents(config)` erzeugt initiale Agenten so:
  1. Wenn `INITIAL_HOUSEHOLDS`/`INITIAL_COMPANIES` explizit gesetzt sind -> wie bisher.
  2. Sonst, wenn `population.num_*` gesetzt sind -> generiere Listen aus Templates.

### Done-Kriterien
- Konfiguration mit z.B. `num_households=200`, `num_companies=50` lässt sich laden.
- `initialize_agents` erzeugt exakt diese Anzahl.
- Minimaler Smoke-Test stellt sicher, dass die Simulation zumindest initialisiert (ohne vollständigen Run).

---

## 3) Tests: Warengeld-Güterzyklus (Kontrakt festlegen)

### Ziel
Wir wollen Regressionen und Fehlinterpretationen vermeiden, indem wir **vor** dem Umbau der Logik Tests schreiben, die das gewünschte Warengeld-Verhalten als Kontrakt ausdrücken.

> Hinweis: Diese Tests können initial **xfail**/**skipped** sein oder als „contract tests“ formuliert werden, wenn die Implementierung noch fehlt.
> Wichtig ist, dass sie präzise festlegen, *was später gelten muss*.

### Testfälle (geplant)

1. **Test: Verkaufsvorgang zieht Geld beim Haushalt ab**
   - Arrange: Haushalt mit `checking_account > 0`, Firma mit `inventory > 0`
   - Act: `sell_to_household`
   - Assert: `household.checking_account` sinkt, `inventory` sinkt, `spent > 0`
   - (Dieser Test ist bereits implizit möglich und sollte stabil sein.)

2. **Test: (Kontrakt) Geldvernichtung beim Warenverkauf**
   - Zielverhalten später: Beim Verkauf von Waren soll Geld nicht einfach als Firmen-Saldo akkumulieren, sondern über Bank/Clearing eingezogen/vernichtet werden.
   - Test-Form: Kontrakt, der später mit der neuen Bank-API erfüllt wird.

3. **Test: (Kontrakt) Emission bei Warenfinanzierung**
   - Zielverhalten später: Geld entsteht nur im Kontext „Warenanschaffung / Warenfinanzierung“.
   - Test-Form: Kontrakt (z.B. neue Bank-Methode erzeugt issued-Tracking), noch ohne Umbau der Firmen-Lohnlogik.

### Done-Kriterien
- Es gibt eine neue Testdatei für den Warengeld-Güterzyklus.
- Mindestens ein Test ist „green“ (z.B. Verkauf reduziert checking + inventory).
- Die Kontrakt-Tests für Emission/Vernichtung sind dokumentiert (entweder als `xfail`/`skip` mit Begründung oder als failing tests, wenn wir bewusst test-first gehen).

---

## Verweise
- Backlog/Problembeschreibung der aktuellen Geldlogik vs. echtes Warengeld: `doc/issues.md`
