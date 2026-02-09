import nox
import os

nox.options.force_venv_backend = "none"
nox.options.reuse_existing_virtualenvs = True

VENV_BIN_PATH = os.path.join(os.getcwd(), ".venv", "bin")

PYTHON_VERSION = "3.12"
TARGETS = [
    "agents",
    "metrics",
    "simulation",
    "scripts",
    "main.py",
    "config.py",
    "config_cache.py",
    "logger.py",
    "sim_clock.py",
    "warengeld_accounting.py",
]
EXCLUDES = ["build", ".nox", "__pycache__", "*.egg-info", "output", "results"]
RADON_ARGS = ["cc", "-s", "-a", "-o", "SCORE"]


def _tool(name: str) -> str:
    """Return the full path to a tool in the project's virtual environment."""
    return os.path.join(VENV_BIN_PATH, name)


@nox.session(python=PYTHON_VERSION)
def lint(session: nox.Session) -> None:
    """Run formatter, linter, and type checker."""
    session.run(_tool("ruff"), "format", ".")
    session.run(_tool("ruff"), "check", "--fix", ".")
    session.run(_tool("mypy"), ".")
    session.run(
        _tool("vulture"),
        *TARGETS,
        "--exclude",
        ",".join(EXCLUDES),
        success_codes=[0, 3],
    )
    session.run(
        _tool("radon"),
        *RADON_ARGS,
        "-e",
        ",".join(EXCLUDES),
        *TARGETS,
    )


@nox.session(python=PYTHON_VERSION)
def tests(session: nox.Session) -> None:
    """Execute pytest suite."""
    session.run(_tool("pytest"))


@nox.session(python=PYTHON_VERSION)
def test_golden(session: nox.Session) -> None:
    """Run comprehensive golden test suite."""
    session.run(_tool("pytest"), "tests/test_golden_run_comprehensive.py", "-xvs")


@nox.session(python=PYTHON_VERSION)
def test_plots(session: nox.Session) -> None:
    """Run plot metrics integration tests."""
    session.run(_tool("pytest"), "tests/test_plot_metrics.py", "-xvs")
    session.run(_tool("pytest"), "tests/test_plot_metrics_integration.py", "-xvs")


@nox.session(python=PYTHON_VERSION)
def test_engine(session: nox.Session) -> None:
    """Run simulation engine tests."""
    session.run(_tool("pytest"), "tests/test_simulation_engine.py", "-xvs")


@nox.session(python=PYTHON_VERSION)
def format(session: nox.Session) -> None:
    """Format code with ruff."""
    session.run(_tool("ruff"), "format", ".")
    session.run(_tool("ruff"), "check", "--fix", "--select", "I", ".")


@nox.session(python=PYTHON_VERSION)
def vulture(session: nox.Session) -> None:
    """Run vulture for dead code detection."""
    session.run(
        _tool("vulture"),
        *TARGETS,
        "--exclude",
        ",".join(EXCLUDES),
        success_codes=[0, 3],
    )


@nox.session(python=PYTHON_VERSION)
def radon_cc(session: nox.Session) -> None:
    """Report the most complex classes and functions with Radon."""
    session.run(
        _tool("radon"),
        *RADON_ARGS,
        "-e",
        ",".join(EXCLUDES),
        *TARGETS,
    )
