"""Cyclomatic complexity helpers (Radon-compatible intent).

The backlog in `doc/issues.md` references Radon complexity grades (A..E) for
specific functions. The execution environment for this task does not provide the
`radon` CLI, so we ship a tiny McCabe-style complexity calculator for tests.

Pragmatic contract:
- cyclomatic complexity = 1 + number of decision points
- grading (common Radon thresholds):
  - A: 1..5
  - B: 6..10
  - C: 11..20
  - D: 21..30
  - E: 31..40
  - F: 41+

This is intentionally minimal but stable enough to enforce refactoring goals.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from dataclasses import dataclass
from typing import Callable, Iterable


class ComplexityError(RuntimeError):
    """Raised when we cannot compute complexity for a given callable."""


@dataclass(frozen=True, slots=True)
class ComplexityReport:
    complexity: int
    grade: str


def complexity_grade(complexity: int) -> str:
    if complexity <= 5:
        return "A"
    if complexity <= 10:
        return "B"
    if complexity <= 20:
        return "C"
    if complexity <= 30:
        return "D"
    if complexity <= 40:
        return "E"
    return "F"


class _ComplexityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.complexity = 1

    # Decision points
    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
        # Each except handler adds a branch.
        self.complexity += len(node.handlers)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:  # noqa: N802
        # a and b and c -> +2, same for or.
        if isinstance(node.op, (ast.And, ast.Or)):
            self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:  # noqa: N802
        # list/set/dict/generator comprehensions may have multiple if clauses.
        self.complexity += len(node.ifs)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:  # noqa: N802
        # Each case is a branch.
        self.complexity += len(node.cases)
        self.generic_visit(node)

    # Do not count nested function definitions as part of parent complexity.
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        return


def _first_function_def(module: ast.AST) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    raise ComplexityError("No function definition found in parsed source")


def cyclomatic_complexity_of_source(source: str) -> ComplexityReport:
    """Compute complexity report from a function source snippet."""

    tree = ast.parse(source)
    func = _first_function_def(tree)

    visitor = _ComplexityVisitor()
    for stmt in func.body:
        visitor.visit(stmt)

    c = int(visitor.complexity)
    return ComplexityReport(complexity=c, grade=complexity_grade(c))


def cyclomatic_complexity(fn: Callable[..., object]) -> ComplexityReport:
    """Compute complexity report for a python callable via `inspect.getsource`."""

    try:
        src = inspect.getsource(fn)
    except OSError as exc:
        raise ComplexityError(f"Cannot read source for {fn!r}") from exc

    src = textwrap.dedent(src)
    return cyclomatic_complexity_of_source(src)


def summarize_reports(reports: Iterable[ComplexityReport]) -> ComplexityReport:
    """Return the report for the most complex item in an iterable."""

    worst = None
    for rep in reports:
        if worst is None or rep.complexity > worst.complexity:
            worst = rep
    if worst is None:
        return ComplexityReport(complexity=0, grade="A")
    return worst
