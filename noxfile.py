import nox

PYTHON_VERSION = "3.12"
TARGETS = ["agents", "metrics.py", "main.py", "config.py", "logger.py"]
EXCLUDES = ["build", ".nox", "__pycache__", "*.egg-info", "output", "results", "tests/__pycache__"]
DEV_DEPS = [
    "pytest",
    "mypy",
    "ruff",
    "black",
    "isort",
    "vulture",
    "lizard",
]


@nox.session(python=PYTHON_VERSION)
def lint(session: nox.Session) -> None:
    """Run formatters, linter, and type checker."""
    session.install(".[dev]")
    session.run("black", *TARGETS)
    session.run("isort", *TARGETS)
    session.run("ruff", "check", *TARGETS)
    session.run("mypy", ".")
    session.run(
        "vulture",
        *TARGETS,
        "--exclude",
        ",".join(EXCLUDES),
        success_codes=[0, 3],
    )
    session.run("lizard", *TARGETS, "--exclude", ",".join(EXCLUDES))


@nox.session(python=PYTHON_VERSION)
def tests(session: nox.Session) -> None:
    """Execute pytest suite."""
    session.install(".[dev]")
    session.run("pytest")


@nox.session(python=PYTHON_VERSION)
def format(session: nox.Session) -> None:
    """Only format code with Black and isort."""
    session.install("black", "isort")
    session.run("black", *TARGETS)
    session.run("isort", *TARGETS)


@nox.session(python=PYTHON_VERSION)
def vulture(session: nox.Session) -> None:
    """Run vulture for dead code detection."""
    session.install(".[dev]")
    session.run(
        "vulture",
        *TARGETS,
        "--exclude",
        ",".join(EXCLUDES),
        success_codes=[0, 3],
    )


@nox.session(python=PYTHON_VERSION)
def lizard(session: nox.Session) -> None:
    """Run lizard for code complexity analysis."""
    session.install(".[dev]")
    session.run("lizard", *TARGETS, "--exclude", ",".join(EXCLUDES))
