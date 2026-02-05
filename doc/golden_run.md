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
- `M1`-Proxy (Summe aller Sight Balances inkl. Staat): **280 … 320**
- Retailer-Inventarwert (Summe): **240 … 280**
- CC-Exposure (Summe über Warengeld-Banken): **130 … 170**
- Beschäftigungsquote (Haushalte mit `employer_id`): **0.75 … 1.00**

## Ausführung

```bash
pytest -q -k golden_run_snapshot
```

## Rationale

- `M1` und `inventory_value` reagieren empfindlich auf Preis-/Abschreibungs- oder
  Demografieänderungen und dienen als Frühwarnindikator.
- CC-Exposure prüft die Konsum-/Restock-Kopplung und Buchhaltung im Warengeld-System.

## Economic Update (2026-02-05)

The expected ranges were updated to reflect the dynamic Kontokorrent limit policy:

- **M1 increase**: The CC limit policy (`bank.cc_limit_multiplier = 2.0`) dynamically
  adjusts retailer credit limits based on their average monthly COGS. With typical
  COGS values around 400, retailers get CC limits around 800 (vs initial 500), enabling
  higher money creation through the Warengeld mechanism.

- **Inventory adjustment**: The inventory valuation reflects the higher business volume
  supported by the expanded CC limits.

- **CC Exposure reduction**: Despite higher CC limits, the actual exposure is lower
  because retailers efficiently repay their Kontokorrent balances from sales revenue,
  demonstrating healthy money circulation.