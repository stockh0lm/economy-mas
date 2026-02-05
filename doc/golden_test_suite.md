# Golden Test Suite Documentation

## Purpose
The golden test suite validates simulation behavior across multiple scenarios and catches regressions in core economic behavior.

## Scenarios

1. **Baseline Short (30 steps)**: Validates basic operation with default parameters
2. **Quarterly (90 steps)**: Validates behavior over longer time horizons
3. **Demography Tests**: Validates mortality, fertility, and age progression
4. **Multi-Region Tests**: Validates spatial distribution and local trade
5. **Company Dynamics**: Validates founding, mergers, and bankruptcy

## Running the Suite

```bash
# Run all golden tests
pytest tests/test_golden_run_comprehensive.py -xvs

# Optional: validate against baselines
python scripts/validate_golden_run.py

# Optional: update baselines after intentional changes
# (only if you implement baseline export logic)
UPDATE_BASELINES=1 pytest tests/test_golden_run_comprehensive.py
```

## Interpreting Results

- ✅ All scenarios pass: Simulation is stable
- ⚠️ Small deviations (< threshold): Acceptable stochastic variance
- ❌ Large deviations: Potential regression or bug

## Regressing Metrics and Thresholds

| Metric | Threshold | Reason |
|--------|-----------|--------|
| m1_proxy | 5% | Money supply must be stable |
| gdp | 8% | Allows for seasonal variance |
| employment_rate | 10% | Labor market has inherent variance |
| price_index | 5% | Inflation must be controlled |
| total_households | 0% | Exact count match for demography |
| total_companies | 0% | Exact count match for companies |
| total_retailers | 0% | Exact count match for retailers |
