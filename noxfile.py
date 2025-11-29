import nox
    session.run("isort", *TARGETS)
    session.run("black", *TARGETS)
    session.install("black", "isort")
    """Only run Black and isort."""
def format(session: nox.Session) -> None:
@nox.session(python=PYTHON_VERSION)


    session.run("pytest")
    session.install(".[dev]")
    """Execute pytest suite."""
def tests(session: nox.Session) -> None:
@nox.session(python=PYTHON_VERSION)


    session.run("mypy", ".")
    session.run("ruff", "check", ".")
    session.run("isort", *TARGETS)
    session.run("black", *TARGETS)
    session.install(".[dev]")
    """Run formatters, lint, and type checks."""
def lint(session: nox.Session) -> None:
@nox.session(python=PYTHON_VERSION)


]
    "isort",
    "black",
    "ruff",
    "mypy",
    "pytest",
DEV_DEPS = [
TARGETS = ["agents", "metrics.py", "main.py", "config.py", "logger.py"]
PYTHON_VERSION = "3.12"


