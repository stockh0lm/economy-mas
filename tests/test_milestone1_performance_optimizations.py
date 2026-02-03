import time

import pandas as pd

from config import SimulationConfig
from logger import HighPerformanceLogHandler, log, setup_logger


def test_high_performance_logging(tmp_path):
    """Referenz: doc/issues.md Abschnitt 5 → High-Performance Logging.

    Erwartung:
    - HighPerformanceLogHandler ist aktiv
    - Logs werden gepuffert (flush_count << #records)
    - Nach flush/close sind alle Zeilen im File
    """

    cfg = SimulationConfig(simulation_steps=1)
    cfg.log_file = str(tmp_path / "hp.log")
    cfg.log_format = "%(message)s"
    cfg.logging_level = "INFO"
    cfg.use_high_performance_logging = True

    logger = setup_logger(
        level=cfg.logging_level,
        log_file=cfg.log_file,
        log_format=cfg.log_format,
        file_mode="w",
        config=cfg,
        use_high_performance_logging=True,
        # Small buffer for test -> deterministic flushes.
        high_performance_log_buffer_mb=1,
    )

    hp = next(h for h in logger.handlers if isinstance(h, HighPerformanceLogHandler))

    # Emit enough data to exceed 1MB.
    n = 6000
    payload = "x" * 220
    for i in range(n):
        log(f"line {i} {payload}", level="INFO")

    # Buffered logging: we should not flush per-record.
    assert hp.flush_count >= 1
    assert hp.flush_count < n

    hp.flush()
    hp.close()

    content = (tmp_path / "hp.log").read_text(encoding="utf-8")
    assert "line 0" in content
    assert f"line {n-1}" in content


def test_plot_metrics_csv_caching(tmp_path):
    """Referenz: doc/issues.md Abschnitt 5 → Plot Metrics CSV Caching.

    Validiert:
    - load_csv_rows cached by file+mtime+usecols
    - Lazy-loading via usecols funktioniert (keine KeyErrors)
    - 10-Plot Rendering-Pfad bleibt schnell (Ziel: < 5s bei Testdaten)
    """

    from scripts.plot_metrics import (
        PLOT_SPECS,
        clear_csv_cache,
        csv_cache_info,
        load_csv_rows,
        plot_overview_dashboard,
    )

    # Minimal but complete columns for the plot set.
    global_cols = {
        "time_step",
        "gdp",
        "household_consumption",
        "government_spending",
        "m1_proxy",
        "m2_proxy",
        "cc_exposure",
        "inventory_value_total",
        "velocity_proxy",
        "employment_rate",
        "unemployment_rate",
        "bankruptcy_rate",
        "average_nominal_wage",
        "average_real_wage",
        "price_index",
        "inflation_rate",
        "environment_budget",
        "infrastructure_budget",
        "social_budget",
        "goods_tx_volume",
        "issuance_volume",
        "extinguish_volume",
        "cc_headroom_total",
        "avg_cc_utilization",
        "retailers_at_cc_limit_share",
        "retailers_stockout_share",
    }

    # Build small synthetic dataset.
    steps = list(range(60))
    global_df = pd.DataFrame({c: [0.0] * len(steps) for c in global_cols if c != "time_step"})
    global_df["time_step"] = steps
    global_df["gdp"] = [100.0 + i for i in steps]
    global_df["price_index"] = [100.0 + 0.1 * i for i in steps]
    global_df["inflation_rate"] = [0.0 for _ in steps]
    global_df["velocity_proxy"] = [0.2 for _ in steps]

    # company/household/state just need time_step + agent_id + a few series.
    company_df = pd.DataFrame(
        {
            "time_step": steps * 2,
            "agent_id": ["c0"] * len(steps) + ["c1"] * len(steps),
            "sight_balance": [10.0] * (2 * len(steps)),
            "rd_investment": [1.0] * (2 * len(steps)),
            "production_capacity": [5.0] * (2 * len(steps)),
        }
    )
    household_df = pd.DataFrame(
        {
            "time_step": steps * 3,
            "agent_id": ["h0"] * len(steps) + ["h1"] * len(steps) + ["h2"] * len(steps),
        }
    )
    state_df = pd.DataFrame(
        {
            "time_step": steps,
            "agent_id": ["state_0"] * len(steps),
            "environment_budget": [1.0] * len(steps),
            "infrastructure_budget": [1.0] * len(steps),
            "social_budget": [1.0] * len(steps),
        }
    )

    # Write CSVs
    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()
    global_path = metrics_dir / "global_metrics_test.csv"
    state_path = metrics_dir / "state_metrics_test.csv"
    company_path = metrics_dir / "company_metrics_test.csv"
    household_path = metrics_dir / "household_metrics_test.csv"
    global_df.to_csv(global_path, index=False)
    state_df.to_csv(state_path, index=False)
    company_df.to_csv(company_path, index=False)
    household_df.to_csv(household_path, index=False)

    clear_csv_cache()
    df1 = load_csv_rows(global_path, usecols=global_cols)
    info1 = csv_cache_info()
    assert info1["misses"] == 1

    # Cache hits on repeated reads.
    for _ in range(9):
        df_i = load_csv_rows(global_path, usecols=global_cols)
        assert df_i is df1
    info2 = csv_cache_info()
    assert info2["hits"] >= 9

    # Rendering path: dashboard + plot specs (10 plots total).
    data_by_scope = {
        "global": df1,
        "state": load_csv_rows(state_path, skip_fields={"agent_id"}, usecols=state_df.columns),
        "company": load_csv_rows(company_path, skip_fields={"agent_id"}, usecols=company_df.columns),
        "household": load_csv_rows(household_path, skip_fields={"agent_id"}, usecols=household_df.columns),
    }

    start = time.perf_counter()
    fig, _ = plot_overview_dashboard(data_by_scope)
    import matplotlib.pyplot as plt

    plt.close(fig)
    for scope, func in PLOT_SPECS:
        f, _ = func(data_by_scope[scope])
        plt.close(f)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0
