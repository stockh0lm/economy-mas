import textwrap

from main import _resolve_config_from_args_or_env


def test_main_resolves_config_from_env(monkeypatch, tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        textwrap.dedent(
            """
            simulation_steps: 7
            population:
              num_households: 1
              num_companies: 1
            INITIAL_HOUSEHOLDS: []
            INITIAL_COMPANIES: []
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SIM_CONFIG", str(cfg_path))
    monkeypatch.setattr("sys.argv", ["main.py"])

    cfg = _resolve_config_from_args_or_env()
    assert cfg.simulation_steps == 7


def test_main_resolves_config_from_cli_over_env(monkeypatch, tmp_path) -> None:
    cfg_env = tmp_path / "env.yaml"
    cfg_env.write_text("simulation_steps: 3\n", encoding="utf-8")

    cfg_cli = tmp_path / "cli.yaml"
    cfg_cli.write_text("simulation_steps: 9\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SIM_CONFIG", str(cfg_env))
    monkeypatch.setattr("sys.argv", ["main.py", "--config", str(cfg_cli)])

    cfg = _resolve_config_from_args_or_env()
    assert cfg.simulation_steps == 9


def test_main_loads_default_config_yaml_when_present(monkeypatch, tmp_path) -> None:
    (tmp_path / "config.yaml").write_text("simulation_steps: 11\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SIM_CONFIG", raising=False)
    monkeypatch.setattr("sys.argv", ["main.py"])

    cfg = _resolve_config_from_args_or_env()
    assert cfg.simulation_steps == 11

