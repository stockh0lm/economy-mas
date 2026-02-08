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
| total_companies | 0% | Exact count match for company dynamics |
| total_retailers | 0% | Exact count match for retailer dynamics |

## Implementation Details

The test suite includes:

1. **Test Module**: `tests/test_golden_run_comprehensive.py`
   - Multiple test scenarios with different configurations
   - Uses pytest fixtures for configuration management
   - Validates against exported metrics CSVs

2. **Validation Script** (Optional): `scripts/validate_golden_run.py`
   - Compares current runs against baseline snapshots
   - Configurable regression thresholds
   - Detailed deviation reporting

3. **Baseline Management** (Optional)
   - Baselines stored in `output/golden_run_baseline/`
   - Generated with fixed seed for reproducibility
   - Only updated after intentional refactors

## Usage Patterns

### Basic Testing
```bash
pytest tests/test_golden_run_comprehensive.py -xvs
```

### Baseline Validation
```bash
# Generate baselines (first time)
mkdir -p output/golden_run_baseline
SIM_SEED=12345 pytest tests/test_golden_run_comprehensive.py
# Copy generated metrics to baseline directory

# Validate against baselines
python scripts/validate_golden_run.py --baseline-dir output/golden_run_baseline --metrics-dir output/metrics
```

### CI Integration
```bash
# Run in CI pipeline
pytest tests/test_golden_run_comprehensive.py -xvs --tb=short
```

## Notes

- Use fixed seed (`SIM_SEED=12345`) for reproducible baselines
- Baselines should only change after intentional refactors
- Different scenarios require different tolerance thresholds
- Some metrics have strict thresholds (counts) while others allow variance (rates)
- All tests use temporary directories for isolation
- Metrics are validated through CSV exports from `cfg.metrics_export_path`