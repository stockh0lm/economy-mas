# Notizen / Annahmen (Implementierungs-Log)

## Milestone 1 — Wachstums- und Sterbe-Verhalten

- **Haushalts-Geburten** werden als *neue Haushaltsgründung* modelliert (nicht als Baby im selben Haushalt): eine probabilistische Entscheidung pro Tag, abhängig von Alter (triangular um `fertility_peak_age`), Einkommen (Elasticity) und Vermögen (Elasticity). Finanzierung ausschließlich via Transfer aus Sichtgeld/Local-Savings/Sparkasse-Einlagen (kein Geldschöpfen).
- **Haushalts-Tod**: vor Entfernen wird der Nachlass abgewickelt: Sparkassen-Kredit wird aus der Erbmasse bedient (Sichtgeld → Local-Savings → Einlagen), Restvermögen wird an einen (bevorzugt jüngeren) Erben im selben Gebiet übertragen (Fallback: Staat). Einlagen werden per Ledger-Umbuchung übertragen.
- **Altersverteilung**: Initiale Haushalte erhalten eine deterministische (seeded) Triangular-Verteilung (`initial_age_*`). Replacement-Haushalte bei Todesfällen werden mit arbeitsfähigem Alter gesampelt.
- **Unternehmens-Gründung**: pro Region probabilistisch, getrieben durch Inventar-Knappheit der Retailer und Kapitalverfügbarkeit eines (reichsten) Haushalts-Funders (Transfer-finanziert).
- **Fusion/Merger**: vereinfacht als Absorption eines distress-Unternehmens durch ein liquides Unternehmen (Transfer von Employees/Assets), 1 Ereignis/Tag max.

## Milestone 1 — Performance-Optimierung (Logging + Plot-Metrics)

- **Logging**: `HighPerformanceLogHandler` schreibt im RAM-Puffer (Default 50MB) und flush't size-basiert. Annahme: persistente Logs sind primär Debug/Analyse, daher ist size-basierte Flush-Strategie ausreichend (Flush/Close via atexit). *Kein stilles try/except*.
- **Plot-Metrics**: CSV wird per pandas (vektorisiert) geladen, mit In-Prozess Cache keyed by `(path, mtime_ns, skip_fields, usecols)`; `usecols` wird in `main()` aus dem Plot-Set abgeleitet (Lazy Loading). Matplotlib standardmäßig Agg Backend + `savefig` ohne `bbox_inches='tight'` zur Reduktion der Text-Layout Hotspots.
- **Hotloop**: erste `getattr()`-Entfernung im Simulationsloop dort, wo Config garantiert Felder bereitstellt (`config.spatial.local_trade_bias`).

## Milestone 1 — Household-Agent Refactoring (Komplexitätsreduktion)

- `Household.step` wurde in drei klare Handler zerlegt:
  - `handle_demographics()` (Alterung + Wachstum/Teilung/Geburt-Entscheid)
  - `handle_finances(stage="pre"|"post")` (Kreditrückzahlung vor Konsum, Sparen am Monatsende)
  - `handle_consumption()` (Konsumentscheid, delegiert in `consume()`)
- `Household.consume` ist jetzt zweistufig:
  - `build_consumption_plan()` (pure, side-effect-free; unit-testbar)
  - `_execute_consumption_plan()` (Side-Effects + Buchungs-Update)
- Radon-CLI ist in dieser Sandbox nicht verfügbar; Komplexitäts-Gate via `tools/complexity.py`
  (McCabe-ähnlich, Radon-Grade-Schwellen A..F). Referenzwerte aus `doc/issues.md`.

## Milestone 2 — Household-Agent Performance (Hotspot)

- Referenz: doc/issues.md Abschnitt 5 → "Performance-Optimierung nach Profiling-Analyse".
- Umgesetzte Optimierungen:
  - Entfernen sämtlicher Config-`getattr()`-Zugriffe im Household-Agent (direkte Attribute).
  - Rolling-Window `consumption_history` als `deque(maxlen=...)` statt List-Slicing im Hotpath.
  - Caching: `_fertility_probability_daily` nutzt `(age_years, income_bin, wealth_bin)` Cache.
  - Batch-Pfad: `Household.batch_consume` (numpy Budgets + retailer choice) und `Household.batch_step` (einmaliger month-end Check).
  - Simulationsloop: Haushalte werden pro Region gebündelt und via `Household.batch_step` verarbeitet.
- Profiling-Artefakt: `doc/profile_household_m2.txt` (Top-Stats aus `scripts/profile_household_m2.py`).
