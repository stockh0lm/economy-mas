# Wirtschaftssimulation (Warengeld)

## Entwicklung

- Tests: `pytest`
- Simulation (Beispiel): `python main.py --config config.yaml`

## Post-hoc Gegenfaktum (Option A)

Referenz: `doc/issues.md` Abschnitt 5 → **„Implement Option A: Nutzerfreundliches Post-hoc-Gegenfaktum-Script in scripts/“**.

Das Script `scripts/compare_posthoc.py` lädt einen bestehenden Export `global_metrics_<run_id>.csv` und erzeugt eine
post-hoc Gegenfaktum-Variante, in der Service-Größen auf 0 gesetzt werden. Abgeleitete Reihen werden neu berechnet
(u.a. goods-only velocity sowie ein alternatives Preisindex/Inflationspfad via kopierter Preisformel).

### Beispiel

```bash
# Automatisch letztes Run-ID wählen
python scripts/compare_posthoc.py \
  --metrics-dir output/metrics \
  --plots-dir output/plots \
  --assume-services-in-gdp

# Explizites Run-ID
python scripts/compare_posthoc.py \
  --run-id 20260201_201734 \
  --metrics-dir output/metrics \
  --plots-dir output/plots \
  --assume-services-in-gdp \
  --output-prefix posthoc
```

**Outputs** (je Run):
- Plots: `output/plots/<run_id>/posthoc/*.png`
- Differences CSV: `output/plots/<run_id>/posthoc/<prefix>_differences_<run_id>.csv`
- Summary: `output/plots/<run_id>/posthoc/<prefix>_summary_<run_id>.md`

