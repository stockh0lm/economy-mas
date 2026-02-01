"""Tests for scripts/plot_metrics.py to ensure functionality during refactoring."""

import csv
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from scripts.plot_metrics import (
    load_csv_rows,
    try_float,
    extract_series,
    aggregate_company_metrics,
    count_agents_per_step,
    detect_latest_run_id,
    parse_args,
    plot_global_output,
    plot_monetary_system,
    plot_labor_market,
    plot_prices_and_wages,
    plot_state_budgets,
    plot_company_health,
    plot_household_population,
    plot_company_population,
)

@pytest.fixture
def sample_csv_data():
    """Create sample CSV data for testing."""
    return [
        {"time_step": "1", "gdp": "100.5", "consumption": "80.2", "agent_id": "agent_1"},
        {"time_step": "2", "gdp": "110.3", "consumption": "85.1", "agent_id": "agent_2"},
        {"time_step": "3", "gdp": "120.7", "consumption": "90.4", "agent_id": "agent_1"},
        {"time_step": "4", "gdp": "130.1", "consumption": "95.3", "agent_id": "agent_3"},
    ]

@pytest.fixture
def sample_csv_file(sample_csv_data):
    """Create a temporary CSV file with sample data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        fieldnames = sample_csv_data[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sample_csv_data)
        return Path(f.name)

def test_try_float_valid_numbers():
    """Test try_float with valid numeric strings."""
    assert try_float("100.5") == 100.5
    assert try_float("0.0") == 0.0
    assert try_float("123") == 123.0
    assert try_float("-50.25") == -50.25

def test_try_float_invalid_values():
    """Test try_float with invalid values."""
    assert try_float("invalid") is None
    assert try_float("") is None
    assert try_float(None) is None
    assert try_float("100.5.3") is None

def test_load_csv_rows_basic(sample_csv_file):
    """Test basic CSV loading functionality."""
    df = load_csv_rows(sample_csv_file)

    # Check structure
    assert len(df) == 4
    assert isinstance(df, pd.DataFrame)
    assert 'time_step' in df.columns

    # Check data types
    assert df['time_step'].dtype == 'int64'
    assert df['gdp'].dtype == 'float64'
    assert df['consumption'].dtype == 'float64'

    # Check values
    assert df.iloc[0]['time_step'] == 1
    assert df.iloc[0]['gdp'] == 100.5
    assert df.iloc[0]['consumption'] == 80.2

def test_load_csv_rows_skip_fields(sample_csv_file):
    """Test CSV loading with skip_fields parameter."""
    df = load_csv_rows(sample_csv_file, skip_fields={'agent_id'})

    # agent_id should be loaded as string (not converted to float)
    assert df.iloc[0]['agent_id'] == 'agent_1'
    assert isinstance(df.iloc[0]['agent_id'], str)

def test_load_csv_rows_missing_values():
    """Test CSV loading with missing values."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=['time_step', 'value', 'missing'])
        writer.writeheader()
        writer.writerow({'time_step': '1', 'value': '10.5', 'missing': ''})
        writer.writerow({'time_step': '2', 'value': 'invalid', 'missing': '20.3'})
        csv_path = Path(f.name)

    df = load_csv_rows(csv_path)

    # Missing/invalid values should be None
    assert pd.isna(df.iloc[0]['missing'])
    assert pd.isna(df.iloc[1]['value'])
    assert df.iloc[1]['missing'] == 20.3

def test_extract_series_basic():
    """Test series extraction from loaded data."""
    data = pd.DataFrame([
        {'time_step': 1, 'gdp': 100.5, 'consumption': 80.2},
        {'time_step': 3, 'gdp': 120.7, 'consumption': 90.4},
        {'time_step': 2, 'gdp': 110.3, 'consumption': 85.1},
    ])

    steps, series = extract_series(data, 'gdp', 'consumption')

    # Check ordering
    assert steps == [1, 2, 3]

    # Check series data
    assert series['gdp'] == [100.5, 110.3, 120.7]
    assert series['consumption'] == [80.2, 85.1, 90.4]

def test_extract_series_missing_values():
    """Test series extraction with missing values."""
    data = pd.DataFrame([
        {'time_step': 1, 'gdp': 100.5, 'missing': None},
        {'time_step': 2, 'gdp': None, 'missing': 20.3},
    ])

    steps, series = extract_series(data, 'gdp', 'missing')

    # Missing values should be converted to 0.0
    assert series['gdp'] == [100.5, 0.0]
    assert series['missing'] == [0.0, 20.3]

def test_aggregate_company_metrics():
    """Test company metrics aggregation."""
    data = pd.DataFrame([
        {'time_step': 1, 'agent_id': 'comp1', 'balance': 100.0, 'rd_investment': 10.0, 'production_capacity': 50.0},
        {'time_step': 1, 'agent_id': 'comp2', 'balance': 150.0, 'rd_investment': 15.0, 'production_capacity': 60.0},
        {'time_step': 2, 'agent_id': 'comp1', 'balance': 110.0, 'rd_investment': 12.0, 'production_capacity': 52.0},
        {'time_step': 3, 'agent_id': 'comp2', 'balance': 160.0, 'rd_investment': 18.0, 'production_capacity': 65.0},
    ])

    steps, aggregated = aggregate_company_metrics(data)

    # Check step ordering
    assert steps == [1, 2, 3]

    # Check aggregation
    assert aggregated['balance'] == [250.0, 110.0, 160.0]
    assert aggregated['rd_investment'] == [25.0, 12.0, 18.0]
    assert aggregated['production_capacity'] == [110.0, 52.0, 65.0]

def test_aggregate_company_metrics_missing_data():
    """Test aggregation with missing data points."""
    data = pd.DataFrame([
        {'time_step': 1, 'agent_id': 'comp1', 'balance': 100.0, 'rd_investment': 10.0, 'production_capacity': 50.0},
        {'time_step': 3, 'agent_id': 'comp1', 'balance': 120.0, 'rd_investment': 12.0, 'production_capacity': 55.0},
        # Missing time_step 2
    ])

    steps, aggregated = aggregate_company_metrics(data)

    assert steps == [1, 3]
    assert aggregated['balance'] == [100.0, 120.0]
    assert aggregated['rd_investment'] == [10.0, 12.0]
    assert aggregated['production_capacity'] == [50.0, 55.0]

def test_count_agents_per_step():
    """Test agent counting functionality."""
    data = pd.DataFrame([
        {'time_step': 1, 'agent_id': 'agent1'},
        {'time_step': 1, 'agent_id': 'agent2'},
        {'time_step': 2, 'agent_id': 'agent1'},
        {'time_step': 3, 'agent_id': 'agent3'},
        {'time_step': 3, 'agent_id': 'agent4'},
        {'time_step': 3, 'agent_id': 'agent5'},
    ])

    steps, counts = count_agents_per_step(data)

    assert steps == [1, 2, 3]
    assert counts == [2, 1, 3]

def test_count_agents_per_step_duplicate_agents():
    """Test counting with duplicate agent IDs in same step."""
    data = pd.DataFrame([
        {'time_step': 1, 'agent_id': 'agent1'},
        {'time_step': 1, 'agent_id': 'agent1'},  # Duplicate
        {'time_step': 1, 'agent_id': 'agent2'},
    ])

    steps, counts = count_agents_per_step(data)

    assert steps == [1]
    assert counts == [2]  # Should count unique agents only

def test_detect_latest_run_id():
    """Test latest run ID detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        metrics_dir = Path(tmpdir)

        # Create test files with different timestamps
        test_files = [
            "global_metrics_20240101_120000.csv",
            "global_metrics_20240102_153000.csv",
            "global_metrics_20240103_090000.csv",
        ]

        for filename in test_files:
            (metrics_dir / filename).touch()

        # Mock file modification times
        import os
        for i, filename in enumerate(test_files):
            filepath = metrics_dir / filename
            # Set different modification times
            os.utime(filepath, (i * 1000, i * 1000))

        latest_id = detect_latest_run_id(metrics_dir)
        assert latest_id == "20240103_090000"

def test_detect_latest_run_id_no_files():
    """Test error handling when no files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        metrics_dir = Path(tmpdir)

        with pytest.raises(FileNotFoundError):
            detect_latest_run_id(metrics_dir)

def test_parse_args_defaults():
    """Test argument parsing with default values."""
    with patch('sys.argv', ['plot_metrics.py']):
        args = parse_args()

        assert args.run_id is None
        assert args.metrics_dir.endswith("output/metrics")
        assert args.plots_dir.endswith("output/plots")
        assert args.show is False
        assert args.link_cursor is False

def test_parse_args_custom():
    """Test argument parsing with custom values."""
    test_args = [
        'plot_metrics.py',
        '--run-id', '20240101_120000',
        '--metrics-dir', '/custom/metrics',
        '--plots-dir', '/custom/plots',
        '--show',
        '--link-cursor'
    ]

    with patch('sys.argv', test_args):
        args = parse_args()

        assert args.run_id == '20240101_120000'
        assert args.metrics_dir == '/custom/metrics'
        assert args.plots_dir == '/custom/plots'
        assert args.show is True
        assert args.link_cursor is True

def test_edge_case_empty_csv():
    """Test handling of empty CSV file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=['time_step', 'value'])
        writer.writeheader()
        csv_path = Path(f.name)

    df = load_csv_rows(csv_path)
    assert len(df) == 0

def test_edge_case_no_numeric_data():
    """Test handling of CSV with no numeric data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=['time_step', 'name'])
        writer.writeheader()
        writer.writerow({'time_step': '1', 'name': 'test'})
        csv_path = Path(f.name)

    df = load_csv_rows(csv_path, skip_fields={'name'})
    assert len(df) == 1
    assert df.iloc[0]['time_step'] == 1
    assert df.iloc[0]['name'] == 'test'

def test_edge_case_large_dataset():
    """Test performance with larger dataset."""
    large_data = []
    for i in range(1000):
        large_data.append({
            'time_step': str(i % 100),
            'value1': str(i * 1.5),
            'value2': str(i * 2.3),
            'agent_id': f'agent_{i % 50}'
        })

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        fieldnames = large_data[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(large_data)
        csv_path = Path(f.name)

    # Should complete in reasonable time
    df = load_csv_rows(csv_path)
    assert len(df) == 1000

    # Test aggregation performance
    steps, aggregated = aggregate_company_metrics(df)
    assert len(steps) <= 100  # Should aggregate by time_step

def test_data_consistency_across_functions():
    """Test that data processing maintains consistency."""
    data = pd.DataFrame([
        {'time_step': 1, 'agent_id': 'comp1', 'balance': 100.0, 'rd_investment': 10.0},
        {'time_step': 1, 'agent_id': 'comp2', 'balance': 150.0, 'rd_investment': 15.0},
        {'time_step': 2, 'agent_id': 'comp1', 'balance': 110.0, 'rd_investment': 12.0},
    ])

    # Test extract_series
    steps1, series1 = extract_series(data, 'balance')
    assert series1['balance'] == [100.0, 150.0, 110.0]

    # Test aggregate_company_metrics
    steps2, aggregated = aggregate_company_metrics(data)
    assert aggregated['balance'] == [250.0, 110.0]

    # Steps should be consistent
    assert steps1 == [1, 1, 2]
    assert steps2 == [1, 2]

    # Test count_agents_per_step
    steps3, counts = count_agents_per_step(data)
    assert steps3 == [1, 2]
    assert counts == [2, 1]

@pytest.fixture
def sample_global_data():
    """Create sample global metrics data for plotting tests."""
    return pd.DataFrame([
        {'time_step': 1, 'gdp': 100.0, 'household_consumption': 80.0, 'government_spending': 10.0,
         'm1_proxy': 50.0, 'm2_proxy': 60.0, 'cc_exposure': 20.0, 'inventory_value_total': 30.0,
         'velocity_proxy': 1.5, 'employment_rate': 0.9, 'unemployment_rate': 0.1, 'bankruptcy_rate': 0.01,
         'average_nominal_wage': 50.0, 'average_real_wage': 45.0, 'price_index': 100.0, 'inflation_rate': 0.02,
         'environment_budget': 5.0, 'infrastructure_budget': 10.0, 'social_budget': 8.0},
        {'time_step': 2, 'gdp': 110.0, 'household_consumption': 85.0, 'government_spending': 12.0,
         'm1_proxy': 55.0, 'm2_proxy': 65.0, 'cc_exposure': 22.0, 'inventory_value_total': 32.0,
         'velocity_proxy': 1.6, 'employment_rate': 0.92, 'unemployment_rate': 0.08, 'bankruptcy_rate': 0.008,
         'average_nominal_wage': 52.0, 'average_real_wage': 47.0, 'price_index': 102.0, 'inflation_rate': 0.02,
         'environment_budget': 5.5, 'infrastructure_budget': 11.0, 'social_budget': 8.5},
    ])

@pytest.fixture
def sample_company_data():
    """Create sample company data for plotting tests."""
    return pd.DataFrame([
        {'time_step': 1, 'agent_id': 'comp1', 'balance': 100.0, 'rd_investment': 10.0, 'production_capacity': 50.0},
        {'time_step': 1, 'agent_id': 'comp2', 'balance': 150.0, 'rd_investment': 15.0, 'production_capacity': 60.0},
        {'time_step': 2, 'agent_id': 'comp1', 'balance': 110.0, 'rd_investment': 12.0, 'production_capacity': 52.0},
    ])

@pytest.fixture
def sample_household_data():
    """Create sample household data for plotting tests."""
    return pd.DataFrame([
        {'time_step': 1, 'agent_id': 'hh1'},
        {'time_step': 1, 'agent_id': 'hh2'},
        {'time_step': 2, 'agent_id': 'hh1'},
        {'time_step': 2, 'agent_id': 'hh3'},
    ])

def test_plot_global_output(sample_global_data):
    """Test global output plot generation."""
    fig, filename = plot_global_output(sample_global_data)

    assert filename == "global_output.png"
    assert fig is not None
    assert len(fig.axes) == 1

    # Check that the plot has the expected title and labels
    ax = fig.axes[0]
    assert ax.get_title() == "Output Composition"
    assert ax.get_xlabel() == "Time Step"
    assert ax.get_ylabel() == "Value"

def test_plot_monetary_system(sample_global_data):
    """Test monetary system plot generation."""
    fig, filename = plot_monetary_system(sample_global_data)

    assert filename == "monetary_system.png"
    assert fig is not None
    assert len(fig.axes) == 2  # Should have two y-axes

    # Check main axis
    ax_left = fig.axes[0]
    assert ax_left.get_title() == "Money, Inventory, and Kontokorrent"
    assert ax_left.get_xlabel() == "Time Step"
    assert ax_left.get_ylabel() == "Level"

def test_plot_labor_market(sample_global_data):
    """Test labor market plot generation."""
    fig, filename = plot_labor_market(sample_global_data)

    assert filename == "labor_market.png"
    assert fig is not None
    assert len(fig.axes) == 1

    ax = fig.axes[0]
    assert ax.get_title() == "Labor & Bankruptcy Rates"
    assert ax.get_xlabel() == "Time Step"
    assert ax.get_ylabel() == "Share of Workforce"

def test_plot_prices_and_wages(sample_global_data):
    """Test prices and wages plot generation."""
    fig, filename = plot_prices_and_wages(sample_global_data)

    assert filename == "prices_and_wages.png"
    assert fig is not None
    assert len(fig.axes) == 2  # Should have two y-axes

    ax_wage = fig.axes[0]
    assert ax_wage.get_title() == "Wages, Prices & Inflation"
    assert ax_wage.get_xlabel() == "Time Step"
    assert ax_wage.get_ylabel() == "Wage Level"

def test_plot_state_budgets(sample_global_data):
    """Test state budgets plot generation."""
    fig, filename = plot_state_budgets(sample_global_data)

    assert filename == "state_budgets.png"
    assert fig is not None
    assert len(fig.axes) == 1

    ax = fig.axes[0]
    assert ax.get_title() == "State Budget Allocation"
    assert ax.get_xlabel() == "Time Step"
    assert ax.get_ylabel() == "Budget ($)"

def test_plot_company_health(sample_company_data):
    """Test company health plot generation."""
    fig, filename = plot_company_health(sample_company_data)

    assert filename == "company_health.png"
    assert fig is not None
    assert len(fig.axes) == 2  # Should have two y-axes

    ax_balance = fig.axes[0]
    assert ax_balance.get_title() == "Company Health Indicators"
    assert ax_balance.get_xlabel() == "Time Step"
    assert ax_balance.get_ylabel() == "Balance ($)"

def test_plot_household_population(sample_household_data):
    """Test household population plot generation."""
    fig, filename = plot_household_population(sample_household_data)

    assert filename == "households_count.png"
    assert fig is not None
    assert len(fig.axes) == 1

    ax = fig.axes[0]
    assert ax.get_title() == "Active Households"
    assert ax.get_xlabel() == "Time Step"
    assert ax.get_ylabel() == "# Households"

def test_plot_company_population(sample_company_data):
    """Test company population plot generation."""
    fig, filename = plot_company_population(sample_company_data)

    assert filename == "companies_count.png"
    assert fig is not None
    assert len(fig.axes) == 1

    ax = fig.axes[0]
    assert ax.get_title() == "Active Companies"
    assert ax.get_xlabel() == "Time Step"
    assert ax.get_ylabel() == "# Companies"

def test_plotting_functions_return_consistent_filenames():
    """Test that all plotting functions return expected filenames."""
    plotting_functions = [
        (plot_global_output, "global_output.png"),
        (plot_monetary_system, "monetary_system.png"),
        (plot_labor_market, "labor_market.png"),
        (plot_prices_and_wages, "prices_and_wages.png"),
        (plot_state_budgets, "state_budgets.png"),
        (plot_company_health, "company_health.png"),
        (plot_household_population, "households_count.png"),
        (plot_company_population, "companies_count.png"),
   ]

    # Create comprehensive test data with all required columns for each plotting function
    sample_data = pd.DataFrame([
        {
            'time_step': 1,
            'gdp': 100.0, 'household_consumption': 80.0, 'government_spending': 10.0,
            'm1_proxy': 50.0, 'm2_proxy': 60.0, 'cc_exposure': 20.0, 'inventory_value_total': 30.0,
            'velocity_proxy': 1.5, 'employment_rate': 0.9, 'unemployment_rate': 0.1, 'bankruptcy_rate': 0.01,
            'average_nominal_wage': 50.0, 'average_real_wage': 45.0, 'price_index': 100.0, 'inflation_rate': 0.02,
            'environment_budget': 5.0, 'infrastructure_budget': 10.0, 'social_budget': 8.0,
            'balance': 100.0, 'rd_investment': 10.0, 'production_capacity': 50.0,
            'agent_id': 'agent_1'
        },
        {
            'time_step': 2,
            'gdp': 110.0, 'household_consumption': 85.0, 'government_spending': 12.0,
            'm1_proxy': 55.0, 'm2_proxy': 65.0, 'cc_exposure': 22.0, 'inventory_value_total': 32.0,
            'velocity_proxy': 1.6, 'employment_rate': 0.92, 'unemployment_rate': 0.08, 'bankruptcy_rate': 0.008,
            'average_nominal_wage': 52.0, 'average_real_wage': 47.0, 'price_index': 102.0, 'inflation_rate': 0.02,
            'environment_budget': 5.5, 'infrastructure_budget': 11.0, 'social_budget': 8.5,
            'balance': 110.0, 'rd_investment': 12.0, 'production_capacity': 52.0,
            'agent_id': 'agent_2'
        }
    ])

    for func, expected_filename in plotting_functions:
        fig, filename = func(sample_data)
        assert filename == expected_filename
        assert fig is not None
