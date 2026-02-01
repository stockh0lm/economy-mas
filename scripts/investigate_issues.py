#!/usr/bin/env python3
"""
Investigate simulation issues using pandas.

This script analyzes:
1. Household and company population dynamics
2. Issues around turn 30000 (CC exposure, retail inventory)
3. Spawning and dying mechanics
4. Age distribution and max age effects

Usage:
    python scripts/investigate_issues.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_metrics():
    """Load all metrics CSV files"""
    metrics_dir = Path("output/metrics")

    # Load global metrics
    global_metrics_path = list(metrics_dir.glob("global_metrics_*.csv"))[0]
    global_df = pd.read_csv(global_metrics_path)

    # Load household metrics
    household_metrics_path = list(metrics_dir.glob("household_metrics_*.csv"))[0]
    household_df = pd.read_csv(household_metrics_path)

    # Load company metrics
    company_metrics_path = list(metrics_dir.glob("company_metrics_*.csv"))[0]
    company_df = pd.read_csv(company_metrics_path)

    # Load retailer metrics
    retailer_metrics_path = list(metrics_dir.glob("retailer_metrics_*.csv"))[0]
    retailer_df = pd.read_csv(retailer_metrics_path)

    return {
        'global': global_df,
        'household': household_df,
        'company': company_df,
        'retailer': retailer_df
    }

def analyze_population_dynamics(metrics):
    """Analyze household and company population dynamics"""
    logger.info("=== Population Dynamics Analysis ===")

    global_df = metrics['global']

    # Check if population is constant
    household_count = global_df['total_households']
    company_count = global_df['total_companies']

    logger.info(f"Household count - min: {household_count.min()}, max: {household_count.max()}, unique values: {household_count.nunique()}")
    logger.info(f"Company count - min: {company_count.min()}, max: {company_count.max()}, unique values: {company_count.nunique()}")

    # Check for changes over time
    household_changes = household_count.diff().abs().sum()
    company_changes = company_count.diff().abs().sum()

    logger.info(f"Total household count changes: {household_changes}")
    logger.info(f"Total company count changes: {company_changes}")

    # Plot population over time
    plt.figure(figsize=(12, 6))
    plt.plot(global_df['time_step'], household_count, label='Households')
    plt.plot(global_df['time_step'], company_count, label='Companies')
    plt.title('Population Dynamics Over Time')
    plt.xlabel('Time Step')
    plt.ylabel('Count')
    plt.legend()
    plt.savefig('output/plots/population_dynamics.png')
    plt.close()

    return {
        'household_constant': household_count.nunique() == 1,
        'company_constant': company_count.nunique() == 1,
        'household_changes': household_changes,
        'company_changes': company_changes
    }

def analyze_turn_30000_issues(metrics):
    """Analyze issues around turn 30000"""
    logger.info("\n=== Turn 30000 Analysis ===")

    global_df = metrics['global']
    retailer_df = metrics['retailer']

    # Focus on the area around turn 30000
    window_start = 25000
    window_end = 35000
    window_df = global_df[(global_df['time_step'] >= window_start) & (global_df['time_step'] <= window_end)]

    # Check CC exposure and M1 proxy
    if 'cc_exposure' in window_df.columns:
        cc_exposure = window_df['cc_exposure']
        logger.info(f"CC exposure around turn 30000 - min: {cc_exposure.min()}, max: {cc_exposure.max()}")
        logger.info(f"CC exposure trend: start={cc_exposure.iloc[0]}, end={cc_exposure.iloc[-1]}")

    if 'm1_proxy' in window_df.columns:
        m1_proxy = window_df['m1_proxy']
        logger.info(f"M1 proxy around turn 30000 - min: {m1_proxy.min()}, max: {m1_proxy.max()}")
        logger.info(f"M1 proxy trend: start={m1_proxy.iloc[0]}, end={m1_proxy.iloc[-1]}")

    # Check inventory value total (which includes retail inventory)
    if 'inventory_value_total' in window_df.columns:
        inventory_value = window_df['inventory_value_total']
        logger.info(f"Inventory value around turn 30000 - min: {inventory_value.min()}, max: {inventory_value.max()}")
        logger.info(f"Inventory value trend: start={inventory_value.iloc[0]}, end={inventory_value.iloc[-1]}")

        # Find the drop point
        max_before_drop = inventory_value[inventory_value > 600].idxmax()
        if pd.notna(max_before_drop):
            drop_series = inventory_value[max_before_drop:]
            if len(drop_series) > 0:
                drop_point = drop_series.idxmin()
                logger.info(f"Inventory value drop from {inventory_value.loc[max_before_drop]:.2f} to {inventory_value.loc[drop_point]:.2f} at step {drop_point}")

    # Plot the problematic metrics
    plt.figure(figsize=(12, 8))

    if 'cc_exposure' in window_df.columns:
        plt.subplot(3, 1, 1)
        plt.plot(window_df['time_step'], window_df['cc_exposure'])
        plt.title('CC Exposure Around Turn 30000')
        plt.ylabel('CC Exposure')

    if 'm1_proxy' in window_df.columns:
        plt.subplot(3, 1, 2)
        plt.plot(window_df['time_step'], window_df['m1_proxy'])
        plt.title('M1 Proxy Around Turn 30000')
        plt.ylabel('M1 Proxy')

    if 'inventory_value_total' in window_df.columns:
        plt.subplot(3, 1, 3)
        plt.plot(window_df['time_step'], window_df['inventory_value_total'])
        plt.title('Inventory Value Total Around Turn 30000')
        plt.ylabel('Inventory Value')

    plt.tight_layout()
    plt.savefig('output/plots/turn_30000_issues.png')
    plt.close()

def analyze_age_distribution(metrics):
    """Analyze household age distribution and max age effects"""
    logger.info("\n=== Age Distribution Analysis ===")

    household_df = metrics['household']

    # Check if age data is available
    if 'age' in household_df.columns:
        # Get age distribution at different time points
        early_df = household_df[household_df['time_step'] < 1000]
        middle_df = household_df[(household_df['time_step'] >= 15000) & (household_df['time_step'] < 20000)]
        late_df = household_df[household_df['time_step'] >= 30000]

        logger.info(f"Early phase (step < 1000) - max age: {early_df['age'].max()}, min age: {early_df['age'].min()}")
        logger.info(f"Middle phase (step 15000-20000) - max age: {middle_df['age'].max()}, min age: {middle_df['age'].min()}")
        logger.info(f"Late phase (step >= 30000) - max age: {late_df['age'].max()}, min age: {late_df['age'].min()}")

        # Plot age distribution over time
        plt.figure(figsize=(12, 6))

        # Sample some time points for clearer visualization
        sample_steps = [1000, 10000, 20000, 30000, 36000]
        for i, step in enumerate(sample_steps):
            step_df = household_df[household_df['time_step'] == step]
            if len(step_df) > 0:
                plt.subplot(2, 3, i+1)
                plt.hist(step_df['age'], bins=20, alpha=0.7)
                plt.title(f'Age Distribution at Step {step}')

        plt.tight_layout()
        plt.savefig('output/plots/age_distribution.png')
        plt.close()

        # Check for households reaching max age
        max_age = household_df['age'].max()
        max_age_households = household_df[household_df['age'] == max_age]

        if len(max_age_households) > 0:
            logger.info(f"Found {len(max_age_households)} households at max age {max_age}")
            logger.info(f"Max age households appear at steps: {sorted(max_age_households['time_step'].unique())}")

def analyze_spawning_mechanics():
    """Analyze spawning and dying mechanics in the code"""
    logger.info("\n=== Spawning Mechanics Analysis ===")

    # Read relevant source files
    try:
        with open('agents/household_agent.py', 'r') as f:
            household_code = f.read()

        with open('agents/company_agent.py', 'r') as f:
            company_code = f.read()

        # Look for spawning/dying methods
        spawning_patterns = [
            'def spawn', 'def die', 'def kill', 'def birth',
            'def create_household', 'def create_company', 'def cleanup',
            'def remove', 'def delete', 'def exit', 'def bankruptcy'
        ]

        found_patterns = []
        for pattern in spawning_patterns:
            if pattern in household_code:
                found_patterns.append(f"Household: {pattern}")
            if pattern in company_code:
                found_patterns.append(f"Company: {pattern}")

        logger.info(f"Found spawning/dying related methods: {found_patterns}")

        # Look for age-related constants
        age_patterns = ['MAX_AGE', 'max_age', 'LIFESPAN', 'lifespan', 'age_limit']
        age_constants = []
        for pattern in age_patterns:
            if pattern in household_code:
                age_constants.append(f"Household: {pattern}")

        logger.info(f"Found age-related constants: {age_constants}")

    except FileNotFoundError as e:
        logger.error(f"Could not read source files: {e}")

def analyze_simulation_log():
    """Analyze the simulation log for root causes"""
    logger.info("\n=== Simulation Log Analysis ===")

    log_path = Path("output/simulation.log")

    # Look for key patterns in the log
    patterns_to_search = [
        'spawn', 'die', 'birth', 'death', 'bankruptcy',
        'cannot pay wages', 'denied goods financing',
        'value correction', 'write-down', 'audit found'
    ]

    pattern_counts = {}
    for pattern in patterns_to_search:
        count = 0
        with open(log_path, 'r') as f:
            for line in f:
                if pattern.lower() in line.lower():
                    count += 1
        pattern_counts[pattern] = count
        logger.info(f"Pattern '{pattern}': {count} occurrences")

    # Look for specific issues around turn 30000
    logger.info("\nSearching for issues around turn 30000...")
    with open(log_path, 'r') as f:
        for line in f:
            if '30000' in line or ('2999' in line and '3000' in line):
                logger.info(f"Line around 30000: {line.strip()}")

def main():
    """Main analysis function"""
    logger.info("Starting simulation issues investigation...")

    # Create plots directory if it doesn't exist
    Path("output/plots").mkdir(parents=True, exist_ok=True)

    # Load metrics data
    metrics = load_metrics()

    # Run analyses
    population_results = analyze_population_dynamics(metrics)
    analyze_turn_30000_issues(metrics)
    analyze_age_distribution(metrics)
    analyze_spawning_mechanics()
    analyze_simulation_log()

    # Summary
    logger.info("\n=== Investigation Summary ===")
    logger.info(f"Population constant - Households: {population_results['household_constant']}, Companies: {population_results['company_constant']}")
    logger.info(f"Total population changes - Households: {population_results['household_changes']}, Companies: {population_results['company_changes']}")

    logger.info("\nAnalysis complete. Check output/plots/ for visualizations.")

if __name__ == "__main__":
    main()
