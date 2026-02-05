import nox
import os

# Configure Nox to use the project's virtual environment by default
# This prevents the creation of separate virtual environments for each session
# and significantly reduces disk space usage and execution time
nox.options.force_venv_backend = "none"
nox.options.reuse_existing_virtualenvs = True

# Get the path to the project's virtual environment bin directory
VENV_BIN_PATH = os.path.join(os.getcwd(), ".venv", "bin")

PYTHON_VERSION = "3.12"
TARGETS = ["agents", "metrics.py", "main.py", "config.py", "logger.py"]
EXCLUDES = ["build", ".nox", "__pycache__", "*.egg-info", "output", "results", "tests/__pycache__"]
RADON_ARGS = ["cc", "-s", "-a", "-o", "SCORE"]
DEV_DEPS = [
    "pytest",
    "mypy",
    "ruff",
    "black",
    "isort",
    "vulture",
    "radon",
]


@nox.session(python=PYTHON_VERSION)
def lint(session: nox.Session) -> None:
    """Run formatters, linter, and type checker."""
    # Use full paths to tools in project's virtual environment
    session.run(os.path.join(VENV_BIN_PATH, "black"), *TARGETS)
    session.run(os.path.join(VENV_BIN_PATH, "isort"), *TARGETS)
    session.run(os.path.join(VENV_BIN_PATH, "ruff"), "check", ".")
    session.run(os.path.join(VENV_BIN_PATH, "mypy"), ".")
    session.run(
        os.path.join(VENV_BIN_PATH, "vulture"),
        *TARGETS,
        "--exclude",
        ",".join(EXCLUDES),
        success_codes=[0, 3],
    )
    session.run(
        os.path.join(VENV_BIN_PATH, "radon"),
        *RADON_ARGS,
        "-e",
        ",".join(EXCLUDES),
        *TARGETS,
    )


@nox.session(python=PYTHON_VERSION)
def tests(session: nox.Session) -> None:
    """Execute pytest suite."""
    # Use full path to pytest in project's virtual environment
    session.run(os.path.join(VENV_BIN_PATH, "pytest"))


@nox.session(python=PYTHON_VERSION)
def test_golden(session: nox.Session) -> None:
    """Run comprehensive golden test suite."""
    session.run(
        os.path.join(VENV_BIN_PATH, "pytest"), "tests/test_golden_run_comprehensive.py", "-xvs"
    )


@nox.session(python=PYTHON_VERSION)
def format(session: nox.Session) -> None:
    """Only format code with Black and isort."""
    # Use full paths to tools in project's virtual environment
    session.run(os.path.join(VENV_BIN_PATH, "black"), *TARGETS)
    session.run(os.path.join(VENV_BIN_PATH, "isort"), *TARGETS)


@nox.session(python=PYTHON_VERSION)
def vulture(session: nox.Session) -> None:
    """Run vulture for dead code detection."""
    # Use full path to vulture in project's virtual environment
    session.run(
        os.path.join(VENV_BIN_PATH, "vulture"),
        *TARGETS,
        "--exclude",
        ",".join(EXCLUDES),
        success_codes=[0, 3],
    )


@nox.session(python=PYTHON_VERSION)
def radon_cc(session: nox.Session) -> None:
    """Report the most complex classes and functions with Radon."""
    # Use full path to radon in project's virtual environment
    session.run(
        os.path.join(VENV_BIN_PATH, "radon"),
        *RADON_ARGS,
        "-e",
        ",".join(EXCLUDES),
        *TARGETS,
    )
