import nox

PYTHON_VERSION = "3.12"
TARGETS = ["agents", "metrics.py", "main.py", "config.py", "logger.py"]
DEV_DEPS = [
    "pytest",
    "mypy",
    "ruff",
    "black",
    "isort",
]


@nox.session(python=PYTHON_VERSION)
def lint(session: nox.Session) -> None:
    """Run formatters, linter, and type checker."""
    session.install(".[dev]")
    session.run("black", *TARGETS)
    session.run("isort", *TARGETS)
    session.run("ruff", "check", *TARGETS)
    session.run("mypy", ".")


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

