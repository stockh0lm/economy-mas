# Golden-run Snapshot

Expliziter Bezug: doc/issues.md Abschnitt 3 → **"Golden-run Snapshot"**.

## Szenario

- Seed: `SIM_SEED=12345`
- Horizon: 30 Tage (`simulation_steps=30`)
- Konfiguration: Default `SimulationConfig()`

## Erwartete Makro-Kennzahlen-Bänder (Snapshot-Test)

Die Snapshot-Tests prüfen keine exakten Float-Werte, sondern Bänder, um kleine
Refactorings/Order-Changes nicht unnötig zu brechen, aber Regressionen sichtbar
zu machen:

- Anzahl Haushalte: **4**
- Anzahl Retailer: **2**
- `M1`-Proxy (Summe aller Sight Balances inkl. Staat): **180 … 220**
- Retailer-Inventarwert (Summe): **250 … 310**
- CC-Exposure (Summe über Warengeld-Banken): **180 … 260**
- Beschäftigungsquote (Haushalte mit `employer_id`): **0.75 … 1.00**

## Ausführung

```bash
pytest -q -k golden_run_snapshot
```

## Rationale

- `M1` und `inventory_value` reagieren empfindlich auf Preis-/Abschreibungs- oder
  Demografieänderungen und dienen als Frühwarnindikator.
- CC-Exposure prüft die Konsum-/Restock-Kopplung und Buchhaltung im Warengeld-System.