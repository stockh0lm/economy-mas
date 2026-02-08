#!/usr/bin/env python3
"""Batch runner for autonomous refactoring with local LLM models.

Runs a set of prompt files through an implementer/reviewer cycle using
cline (default) or opencode as the LLM middleware. Designed to run
unattended overnight against local models via LiteLLM.

Usage:
    python tools/run_refactor_batch.py                          # all prompts
    python tools/run_refactor_batch.py --prompt-index 2         # single prompt
    python tools/run_refactor_batch.py --dry-run                # no LLM calls
    python tools/run_refactor_batch.py --backend opencode       # use opencode
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Logging setup - standalone, no external dependencies
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

log = logging.getLogger("refactor_batch")


def setup_logging(report_dir: Path, verbose: bool = False) -> None:
    """Configure dual logging: stderr + file."""
    level = logging.DEBUG if verbose else logging.INFO
    log.setLevel(level)
    log.handlers.clear()

    # Console handler (stderr so stdout stays clean for piping)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    log.addHandler(console)

    # File handler
    report_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(report_dir / "batch_orchestrator.log", mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    log.addHandler(fh)


# ---------------------------------------------------------------------------
# Tokens for inter-model communication
# ---------------------------------------------------------------------------

REVIEW_PASS = "REVIEW_PASS"
REVIEW_FAIL = "REVIEW_FAIL"
TESTS_PASS = "TESTS_PASS"
TESTS_FAIL = "TESTS_FAIL"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Model short-name aliases
MODEL_ALIASES: dict[str, str] = {
    "devstral": "devstral-2-123b-instruct-2512",
    "glm-4.7": "glm-4.7-awq",
    "gemini-free": "google/gemini-2.0-flash-lite-preview-02-05:free",
}

# Default prompt file ordering (looked up in prompt_dir)
DEFAULT_PROMPTS = [
    "01_golden_test_fix.md",
    "02_golden_test_suite.md",
    "03_plot_metrics_tests.md",
    "04_extract_simulation_engine.md",
    "05_refactor_metrics.md",
    "06_extract_household_components.md",
    "07_increase_test_coverage.md",
    "08_performance_optimization.md",
    "09_documentation_types.md",
    "10_comprehensive_regression.md",
]

# Approximate context limits (tokens) for known models.
# Used for prompt-size validation before sending to the backend.
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "devstral-2-123b-instruct-2512": 262_144,
    "glm-4.7-awq": 128_000,
}

# Conservative chars-per-token ratio for estimation.
CHARS_PER_TOKEN = 4


@dataclass
class BatchConfig:
    """All runtime configuration in one place."""

    repo_root: Path = field(default_factory=lambda: Path.cwd())
    prompt_dir: Path = field(default_factory=lambda: Path.cwd() / "doc" / "refactoring_prompts")
    report_dir: Path = field(default_factory=lambda: Path.cwd() / "doc" / "refactoring_reports")
    backend: Literal["cline", "opencode"] = "cline"
    model_impl: str = "devstral"
    model_review: str = "glm-4.7"
    max_iters: int = 5
    retry_max: int = 2
    retry_sleep: int = 5
    dry_run: bool = False
    allow_git: bool = False
    verbose: bool = False
    prompt_index: int = 0  # 0 = all
    # Timeouts
    command_timeout: int = 3600
    stuck_timeout: int = 7200
    no_output_timeout: int = 1200
    monitor_interval: int = 900
    kill_stale: bool = False


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------


def resolve_model(short_name: str, backend: str = "cline") -> str:
    """Expand a short model name to its full ID.

    For opencode, known LiteLLM models get the ``litellm-local/`` prefix.
    For cline, the raw model ID is used (configured via ``cline auth``).
    """
    name = short_name.strip()
    if not name:
        return name
    model_id = MODEL_ALIASES.get(name.lower(), name)
    if backend == "opencode" and model_id in (
        "devstral-2-123b-instruct-2512",
        "glm-4.7-awq",
    ):
        return f"litellm-local/{model_id}"
    return model_id


# ---------------------------------------------------------------------------
# Backend abstraction
# ---------------------------------------------------------------------------


def _find_binary(name: str, extra_paths: list[str] | None = None) -> str:
    """Locate an executable by name, checking PATH and common install dirs."""
    found = shutil.which(name)
    if found:
        return found
    for p in extra_paths or []:
        if Path(p).exists():
            return p
    raise FileNotFoundError(
        f"{name!r} not found in PATH" + (f" or {extra_paths}" if extra_paths else "")
    )


def find_cline() -> str:
    return _find_binary("cline")


def find_opencode() -> str:
    return _find_binary(
        "opencode",
        [
            str(Path.home() / ".opencode" / "bin" / "opencode"),
            str(Path.home() / ".local" / "bin" / "opencode"),
        ],
    )


def build_impl_command(
    cfg: BatchConfig,
    prompt_path: Path,
    model: str,
    session_id: str,
) -> tuple[list[str], Path | None]:
    """Build the command list and optional stdin file for the implementer.

    Returns (cmd, stdin_file) where stdin_file is set for cline (pipe mode).
    """
    resolved = resolve_model(model, cfg.backend)
    if cfg.backend == "cline":
        return (
            [find_cline(), "-m", resolved, "--yolo", "-"],
            prompt_path,
        )
    # opencode
    return (
        [
            find_opencode(),
            "run",
            "Execute the attached prompt file end-to-end.",
            "--model",
            resolved,
            "--file",
            str(prompt_path),
            "--title",
            session_id,
        ],
        None,
    )


def build_review_command(
    cfg: BatchConfig,
    prompt_path: Path,
    model: str,
    session_id: str,
) -> tuple[list[str], Path | None]:
    """Build the command for the reviewer. Same structure as implementer."""
    resolved = resolve_model(model, cfg.backend)
    if cfg.backend == "cline":
        return (
            [find_cline(), "-m", resolved, "--yolo", "-"],
            prompt_path,
        )
    return (
        [
            find_opencode(),
            "run",
            "Execute the attached prompt file end-to-end.",
            "--model",
            resolved,
            "--file",
            str(prompt_path),
            "--title",
            session_id,
        ],
        None,
    )


def build_preflight_command(
    cfg: BatchConfig,
    model: str,
) -> tuple[list[str], Path | None]:
    """Build a minimal 'Reply with OK' command for preflight checks."""
    resolved = resolve_model(model, cfg.backend)
    if cfg.backend == "cline":
        return ([find_cline(), "-m", resolved, "--yolo", "Reply with OK."], None)
    return (
        [
            find_opencode(),
            "run",
            "Reply with OK.",
            "--model",
            resolved,
        ],
        None,
    )


# ---------------------------------------------------------------------------
# Cline configuration helper
# ---------------------------------------------------------------------------


def get_opencode_config() -> dict:
    """Read the opencode config to extract LiteLLM backend settings."""
    # Check both project-local and user-global config
    candidates = [
        Path.cwd() / "opencode.json",
        Path.home() / ".config" / "opencode" / "config.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                log.debug("Failed to read %s: %s", path, exc)
    return {}


def configure_cline_from_opencode() -> None:
    """Auto-configure cline with the same LiteLLM backend as opencode."""
    config = get_opencode_config()
    litellm = config.get("provider", {}).get("litellm-local", {})
    options = litellm.get("options", {})
    base_url = options.get("baseURL")
    auth_header = options.get("headers", {}).get("Authorization", "")
    api_key = auth_header.replace("Bearer ", "").strip()

    if not (base_url and api_key):
        log.warning("No LiteLLM config found; cline may not connect to local models")
        return

    models = list(litellm.get("models", {}).keys())
    if not models:
        log.warning("No models defined in opencode config")
        return

    log.info("Configuring cline with LiteLLM backend: %s", base_url)
    result = subprocess.run(
        [
            "cline",
            "auth",
            "--provider",
            "openai",
            "--baseurl",
            base_url,
            "--apikey",
            api_key,
            "--modelid",
            models[0],
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        log.warning("cline auth failed: %s", result.stderr.strip())
    else:
        log.debug("cline auth succeeded for model %s", models[0])


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

READONLY_GIT_WRAPPER = """\
#!/bin/sh
set -eu
cmd="${1:-}"
[ -z "$cmd" ] && exec "${REAL_GIT:-git}"
case "$cmd" in
  status|diff|log|show|grep|ls-files|rev-parse|describe|blame|cat-file|whatchanged)
    exec "${REAL_GIT:-git}" "$@" ;;
  *)
    echo "git write blocked by refactor batch: $cmd" >&2; exit 2 ;;
esac
"""


def build_env(cfg: BatchConfig) -> dict[str, str]:
    """Build environment dict, optionally with read-only git wrapper."""
    env = os.environ.copy()
    if cfg.allow_git:
        return env
    wrapper_dir = cfg.repo_root / "tools" / ".opencode"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = wrapper_dir / "git"
    tmp = wrapper_dir / f"git.{os.getpid()}.tmp"
    tmp.write_text(READONLY_GIT_WRAPPER, encoding="utf-8")
    tmp.chmod(0o755)
    try:
        tmp.replace(wrapper_path)
    except OSError:
        tmp.unlink(missing_ok=True)
    env["REAL_GIT"] = env.get("REAL_GIT") or shutil.which("git") or "git"
    env["PATH"] = f"{wrapper_dir}:{env.get('PATH', '')}"
    return env


def git_run(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def git_snapshot(repo: Path, max_diff_bytes: int = 50_000) -> str:
    """Return a human-readable summary of git status + diff.

    Truncates the diff to ``max_diff_bytes`` to prevent prompt overflow.
    Excludes tooling/report paths from the diff.
    """
    status = git_run(repo, ["status", "--porcelain=v1"]).stdout.strip() or "(clean)"

    # Only diff source-relevant files (exclude reports, output, tooling)
    diff_result = git_run(
        repo,
        [
            "diff",
            "--",
            ":(exclude)doc/refactoring_reports",
            ":(exclude)output",
            ":(exclude)package-lock.json",
            ":(exclude)package.json",
            ":(exclude)node_modules",
        ],
    )
    diff = diff_result.stdout.strip() or "(no diff)"

    if len(diff) > max_diff_bytes:
        # Show stat summary instead of full diff when too large
        stat_result = git_run(repo, ["diff", "--stat"])
        stat = stat_result.stdout.strip()
        truncated = diff[:max_diff_bytes]
        # Cut at last complete line
        last_nl = truncated.rfind("\n")
        if last_nl > 0:
            truncated = truncated[:last_nl]
        diff = (
            f"(diff truncated: {len(diff_result.stdout)} bytes > {max_diff_bytes} limit)\n\n"
            f"Diff stat:\n{stat}\n\n"
            f"Diff (first {max_diff_bytes} bytes):\n{truncated}\n"
        )

    return f"Current git status:\n{status}\n\nCurrent git diff:\n{diff}"


def git_current_branch(repo: Path) -> str:
    return git_run(repo, ["branch", "--show-current"]).stdout.strip() or "HEAD"


def git_untracked(repo: Path) -> list[Path]:
    result = git_run(repo, ["status", "--porcelain=v1"])
    return [
        repo / line[3:].strip()
        for line in result.stdout.splitlines()
        if line.startswith("?? ") and line[3:].strip()
    ]


def git_status_entries(repo: Path) -> list[tuple[str, str]]:
    result = git_run(repo, ["status", "--porcelain=v1"])
    return [(line[:2], line[3:]) for line in result.stdout.splitlines() if line]


def git_save_snapshot(repo: Path, report_dir: Path, prefix: str) -> None:
    """Save git status and diff to report files."""
    report_dir.mkdir(parents=True, exist_ok=True)
    status = git_run(repo, ["status", "--porcelain=v1"])
    (report_dir / f"{prefix}_status.txt").write_text(status.stdout, encoding="utf-8")
    diff = git_run(repo, ["diff"])
    (report_dir / f"{prefix}_diff.patch").write_text(diff.stdout, encoding="utf-8")


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def tail(path: Path, max_lines: int = 200, max_bytes: int = 20_000) -> str:
    """Return the last ``max_lines`` of a file, capped at ``max_bytes``.

    If the tail exceeds ``max_bytes``, lines are dropped from the front
    until the result fits.  Set *max_bytes* to 0 to disable the byte limit.
    """
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    selected = lines[-max_lines:]

    if max_bytes and max_bytes > 0:
        total = sum(len(l) + 1 for l in selected)  # +1 for newline
        while selected and total > max_bytes:
            total -= len(selected[0]) + 1
            selected.pop(0)

    return "\n".join(selected)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def has_token(path: Path, token: str) -> bool:
    if not path.exists():
        return False
    return token in path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Process runner with monitoring
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    """Outcome of a monitored process run."""

    success: bool
    exit_code: int | None = None
    killed_reason: str | None = None  # "timeout", "stuck", "no_output", "progress_stuck"
    duration: float = 0.0
    permanent_error: bool = False  # True if retrying won't help (context overflow, etc.)


# Patterns in stderr/stdout that indicate permanent (non-retryable) errors.
_PERMANENT_ERROR_PATTERNS = [
    "max_tokens must be at least",
    "input tokens >",
    "exceeds the model's maximum context length",
    "context_length_exceeded",
    "maximum context length",
    "This model's maximum context length is",
    "max_tokens",
]

# Patterns that indicate transient (retryable) errors.
_TRANSIENT_ERROR_PATTERNS = [
    "upstream connect error",
    "502 Bad Gateway",
    "503 Service Unavailable",
    "504 Gateway Timeout",
    "Connection refused",
    "Connection reset",
    "ECONNRESET",
    "ETIMEDOUT",
    "rate_limit",
    "Rate limit",
]


def classify_error(stderr_text: str) -> str:
    """Classify an error as 'permanent', 'transient', or 'unknown'.

    Reads the stderr output and checks for known error patterns.
    """
    for pat in _PERMANENT_ERROR_PATTERNS:
        if pat in stderr_text:
            return "permanent"
    for pat in _TRANSIENT_ERROR_PATTERNS:
        if pat in stderr_text:
            return "transient"
    return "unknown"


def run_monitored(
    cmd: list[str],
    log_file: Path,
    *,
    env: dict[str, str] | None = None,
    stdin_file: Path | None = None,
    timeout: int = 3600,
    stuck_timeout: int = 7200,
    no_output_timeout: int = 1200,
    monitor_interval: int = 900,
    retry_max: int = 1,
    retry_sleep: int = 5,
) -> RunResult:
    """Run a command with monitoring for stuck/timeout conditions.

    Writes stdout to log_file, stderr to log_file.stderr.
    Retries on failure up to retry_max times.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    stderr_file = log_file.with_name(log_file.name + ".stderr")
    start = time.monotonic()

    for attempt in range(1, retry_max + 1):
        start = time.monotonic()
        last_change = start
        last_heartbeat = 0.0
        prev_size = 0

        mode = "w" if attempt == 1 else "a"
        stdin_handle = None

        try:
            with (
                log_file.open(mode, encoding="utf-8") as out,
                stderr_file.open(mode, encoding="utf-8") as err,
            ):
                if attempt > 1:
                    out.write(f"\n--- ATTEMPT {attempt}/{retry_max} ---\n")
                    log.info("Retry %d/%d for %s", attempt, retry_max, log_file.name)

                if stdin_file:
                    stdin_handle = stdin_file.open("r", encoding="utf-8")

                log.debug("Starting: %s", " ".join(cmd[:4]) + "...")
                proc = subprocess.Popen(
                    cmd,
                    stdout=out,
                    stderr=err,
                    stdin=stdin_handle,
                    env=env,
                    start_new_session=True,
                )

                while True:
                    now = time.monotonic()
                    elapsed = now - start

                    # Check log file growth
                    try:
                        cur_size = log_file.stat().st_size
                    except OSError:
                        cur_size = prev_size
                    if cur_size > prev_size:
                        last_change = now
                        prev_size = cur_size

                    # Heartbeat
                    if monitor_interval and now - last_heartbeat >= monitor_interval:
                        last_heartbeat = now
                        log.info(
                            "HEARTBEAT pid=%d elapsed=%ds log=%s size=%d",
                            proc.pid,
                            int(elapsed),
                            log_file.name,
                            cur_size,
                        )

                    # Timeout check
                    if timeout and elapsed >= timeout:
                        _kill(proc)
                        return RunResult(False, None, "timeout", elapsed)

                    # Stuck check (log unchanged for too long)
                    if stuck_timeout and now - last_change >= stuck_timeout:
                        _kill(proc)
                        return RunResult(False, None, "stuck", elapsed)

                    # No-output check
                    if no_output_timeout and elapsed >= no_output_timeout and cur_size == 0:
                        _kill(proc)
                        return RunResult(False, None, "no_output", elapsed)

                    # Process done?
                    rc = proc.poll()
                    if rc is not None:
                        duration = time.monotonic() - start
                        if rc == 0:
                            return RunResult(True, rc, None, duration)

                        # Read stderr to classify the failure
                        try:
                            stderr_text = stderr_file.name  # flush first
                            err.flush()
                            stderr_text = Path(stderr_file.name).read_text(
                                encoding="utf-8", errors="replace"
                            )
                        except OSError:
                            stderr_text = ""

                        error_class = classify_error(stderr_text)
                        log.warning(
                            "Process exited with code %d after %.0fs (%s error): %s",
                            rc,
                            duration,
                            error_class,
                            log_file.name,
                        )
                        if stderr_text.strip():
                            # Log first 500 chars of stderr for diagnostics
                            snippet = stderr_text.strip()[:500]
                            log.warning("stderr: %s", snippet)

                        if error_class == "permanent":
                            return RunResult(
                                False,
                                rc,
                                "permanent_error",
                                duration,
                                permanent_error=True,
                            )

                        break  # retry (transient or unknown)

                    time.sleep(5)
        finally:
            if stdin_handle:
                stdin_handle.close()

        if attempt < retry_max:
            time.sleep(retry_sleep)

    return RunResult(False, None, "retries_exhausted", time.monotonic() - start)


def run_simple(
    cmd: list[str],
    log_file: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> bool:
    """Run a command without monitoring. For quick tasks like preflight."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_file.open("w", encoding="utf-8") as out:
            proc = subprocess.run(
                cmd,
                stdout=out,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                env=env,
                check=False,
            )
            return proc.returncode == 0
    except subprocess.TimeoutExpired:
        log.warning("Command timed out after %ds: %s", timeout, cmd[0])
        return False
    except OSError as exc:
        log.error("Failed to run %s: %s", cmd[0], exc)
        return False


def _kill(proc: subprocess.Popen) -> None:
    """Terminate then kill a process."""
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def build_impl_prompt(
    base_prompt: Path,
    iteration: int,
    git_state: str,
    prev_review_feedback: str | None = None,
) -> str:
    """Build the composite prompt for the implementer."""
    parts = [base_prompt.read_text(encoding="utf-8")]

    if iteration > 1 and prev_review_feedback:
        parts.append(
            "---\n\n"
            "## Reviewer Feedback from Previous Iteration\n\n"
            "Apply the following feedback and re-run verification:\n\n"
            f"{prev_review_feedback}\n\n"
            f"End your response with {TESTS_PASS} if all verification commands succeeded, "
            f"or {TESTS_FAIL} if any failed."
        )

    parts.append(f"---\n\n## Current Repository State\n\n{git_state}")
    return "\n\n".join(parts) + "\n"


def build_review_prompt(
    base_prompt: Path,
    impl_log_tail: str,
    git_state: str,
) -> str:
    """Build the composite prompt for the reviewer."""
    parts = [base_prompt.read_text(encoding="utf-8")]
    parts.append(
        "---\n\n"
        "## Reviewer Instructions\n\n"
        "Review the implementation against the prompt requirements.\n\n"
        f"- If all requirements are met and tests pass, end with: {REVIEW_PASS}\n"
        f"- If issues remain, end with: {REVIEW_FAIL}\n"
        "- When failing, provide concrete fixes for the implementer.\n"
        f"- If the implementer reported {TESTS_FAIL}, you must end with {REVIEW_FAIL}.\n"
    )
    if impl_log_tail:
        parts.append(f"## Implementer Log (tail)\n\n```\n{impl_log_tail}\n```")
    parts.append(f"## Current Repository State\n\n{git_state}")
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Prompt size validation
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ~ 4 characters."""
    return len(text) // CHARS_PER_TOKEN


def check_prompt_size(prompt_text: str, model: str, label: str) -> str:
    """Validate prompt size against the model context limit.

    If the prompt is too large, the git diff section is truncated to fit.
    Returns the (possibly truncated) prompt text.
    Logs a warning when truncation happens.
    """
    model_id = MODEL_ALIASES.get(model.lower(), model)
    limit = MODEL_CONTEXT_LIMITS.get(model_id)
    if not limit:
        return prompt_text

    # Reserve 10% of context for output tokens + overhead
    max_input_tokens = int(limit * 0.90)
    est = estimate_tokens(prompt_text)

    if est <= max_input_tokens:
        log.debug(
            "Prompt size OK for %s: ~%d tokens (limit %d) [%s]",
            model,
            est,
            max_input_tokens,
            label,
        )
        return prompt_text

    overshoot = est - max_input_tokens
    overshoot_chars = overshoot * CHARS_PER_TOKEN
    log.warning(
        "Prompt too large for %s: ~%d tokens > %d limit (overshoot ~%d chars) [%s]",
        model,
        est,
        max_input_tokens,
        overshoot_chars,
        label,
    )

    # Try to shrink the "Current git diff" section
    diff_marker = "Current git diff:"
    idx = prompt_text.rfind(diff_marker)
    if idx < 0:
        log.warning("Cannot find diff section to truncate for %s [%s]", model, label)
        return prompt_text

    prefix = prompt_text[: idx + len(diff_marker)]
    diff_body = prompt_text[idx + len(diff_marker) :]

    # Cut diff body to fit
    allowed = len(diff_body) - overshoot_chars - 200  # 200 chars safety margin
    if allowed < 200:
        truncated_diff = "\n(diff removed: prompt too large for model context)\n"
    else:
        truncated_diff = diff_body[:allowed]
        last_nl = truncated_diff.rfind("\n")
        if last_nl > 0:
            truncated_diff = truncated_diff[:last_nl]
        truncated_diff += f"\n\n(diff truncated to fit {model} context limit)\n"

    result = prefix + truncated_diff
    new_est = estimate_tokens(result)
    log.info(
        "Truncated prompt: ~%d -> ~%d tokens for %s [%s]",
        est,
        new_est,
        model,
        label,
    )
    return result


ALLOWED_UNTRACKED_PREFIXES = ("doc/refactoring_reports/", "output/")


def is_allowed_untracked(repo: Path, path: Path) -> bool:
    try:
        rel = str(path.relative_to(repo))
    except ValueError:
        return False
    if any(rel.startswith(p) for p in ALLOWED_UNTRACKED_PREFIXES):
        return True
    if path.parent == repo and path.name.startswith("debug_") and path.suffix == ".py":
        return True
    return False


def cleanup_illegal_files(repo: Path, report_dir: Path) -> int:
    """Remove untracked files that don't belong. Returns count removed."""
    illegal = [p for p in git_untracked(repo) if not is_allowed_untracked(repo, p)]
    if not illegal:
        return 0

    log.info("Found %d illegal untracked files", len(illegal))
    log_path = report_dir / "illegal_files.log"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        for p in illegal:
            f.write(f"  DELETE: {p}\n")

    removed = 0
    for p in illegal:
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink()
            removed += 1
        except OSError as exc:
            log.warning("Could not remove %s: %s", p, exc)
    return removed


def cleanup_temp_artifacts(repo: Path) -> None:
    """Remove debug scripts and output artifacts."""
    for f in repo.glob("debug_*.py"):
        try:
            f.unlink()
        except OSError:
            pass
    output = repo / "output"
    if output.exists():
        shutil.rmtree(output, ignore_errors=True)


# ---------------------------------------------------------------------------
# Completed prompts tracking
# ---------------------------------------------------------------------------


def load_completed(report_dir: Path) -> set[str]:
    marker = report_dir / "completed_prompts.txt"
    if not marker.exists():
        return set()
    try:
        return {
            line.strip() for line in marker.read_text(encoding="utf-8").splitlines() if line.strip()
        }
    except OSError:
        return set()


def mark_completed(report_dir: Path, name: str) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    marker = report_dir / "completed_prompts.txt"
    completed = load_completed(report_dir)
    if name not in completed:
        with marker.open("a", encoding="utf-8") as f:
            f.write(f"{name}\n")


# ---------------------------------------------------------------------------
# Stale process management
# ---------------------------------------------------------------------------


def kill_stale_processes(name: str = "opencode") -> int:
    """Find and kill orphaned processes. Returns count killed."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", name],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return 0
    killed = 0
    for line in result.stdout.splitlines():
        try:
            pid = int(line.strip())
            if pid == os.getpid():
                continue
            os.kill(pid, signal.SIGTERM)
            killed += 1
            log.info("Terminated stale %s process: %d", name, pid)
        except (ValueError, OSError):
            continue
    return killed


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------


def preflight(cfg: BatchConfig, env: dict[str, str]) -> None:
    """Verify that both models respond before starting the batch."""
    for label, model in [("implementer", cfg.model_impl), ("reviewer", cfg.model_review)]:
        safe = resolve_model(model, cfg.backend).replace("/", "_")
        log_file = cfg.report_dir / f"{cfg.backend}_preflight_{safe}.log"
        cmd, stdin_file = build_preflight_command(cfg, model)

        log.info("Preflight check: %s model=%s backend=%s", label, model, cfg.backend)
        ok = run_simple(cmd, log_file, env=env, timeout=180)
        if not ok:
            err_text = tail(log_file, 20)
            raise RuntimeError(
                f"Preflight failed for {label} ({model}) via {cfg.backend}.\n"
                f"Log: {log_file}\n{err_text}"
            )
        log.info("Preflight OK: %s", label)


# ---------------------------------------------------------------------------
# Single prompt execution
# ---------------------------------------------------------------------------


def run_single_prompt(
    cfg: BatchConfig,
    prompt: Path,
    env: dict[str, str],
) -> bool:
    """Execute one prompt through the implement/review cycle.

    Returns True on success (REVIEW_PASS received).
    Raises RuntimeError on unrecoverable failure.
    """
    name = prompt.stem
    stamp = time.strftime("%Y%m%d_%H%M%S")
    session = uuid.uuid4().hex[:12]

    # Snapshot before
    git_save_snapshot(cfg.repo_root, cfg.report_dir, f"{name}_{stamp}_before")

    success = False
    try:
        for iteration in range(1, cfg.max_iters + 1):
            tag = f"{name}_{stamp}_iter{iteration}"
            log.info(
                "=== %s iteration %d/%d ===",
                name,
                iteration,
                cfg.max_iters,
            )

            # --- Implementer phase ---
            prev_feedback = None
            if iteration > 1:
                prev_review = cfg.report_dir / f"{name}_{stamp}_iter{iteration - 1}_review.log"
                prev_feedback = tail(prev_review)

            state = git_snapshot(cfg.repo_root)
            if iteration > 1:
                state = f"State for iteration {iteration}:\n{state}"

            impl_prompt_text = build_impl_prompt(prompt, iteration, state, prev_feedback)
            impl_prompt_text = check_prompt_size(
                impl_prompt_text, cfg.model_impl, f"{name} impl iter{iteration}"
            )
            impl_prompt_file = cfg.report_dir / f"{tag}_impl_prompt.md"
            write_file(impl_prompt_file, impl_prompt_text)

            impl_log = cfg.report_dir / f"{tag}_impl.log"

            if cfg.dry_run:
                write_file(impl_log, f"DRY_RUN: implementer skipped (iter {iteration})\n")
            else:
                cmd, stdin = build_impl_command(
                    cfg,
                    impl_prompt_file,
                    cfg.model_impl,
                    f"{name}-impl-{session}",
                )
                result = run_monitored(
                    cmd,
                    impl_log,
                    env=env,
                    stdin_file=stdin,
                    timeout=cfg.command_timeout,
                    stuck_timeout=cfg.stuck_timeout,
                    no_output_timeout=cfg.no_output_timeout,
                    monitor_interval=cfg.monitor_interval,
                    retry_max=cfg.retry_max,
                    retry_sleep=cfg.retry_sleep,
                )
                if not result.success:
                    if result.permanent_error:
                        raise RuntimeError(
                            f"Implementer hit permanent error for {name} iter {iteration}: "
                            f"{result.killed_reason} (prompt too large for model context?)"
                        )
                    log.warning(
                        "Implementer failed (%s, %.0fs); proceeding to reviewer",
                        result.killed_reason or f"exit={result.exit_code}",
                        result.duration,
                    )
                    with impl_log.open("a", encoding="utf-8") as f:
                        f.write(f"\n{TESTS_FAIL}\n")

                # Log test status
                if not cfg.dry_run:
                    impl_text = impl_log.read_text(encoding="utf-8", errors="replace")
                    if TESTS_FAIL in impl_text:
                        log.warning("Implementer reported %s", TESTS_FAIL)
                    elif TESTS_PASS not in impl_text:
                        log.warning("Implementer did not report test status")

            # --- Reviewer phase ---
            impl_tail = tail(impl_log)
            review_prompt_text = build_review_prompt(prompt, impl_tail, state)
            review_prompt_text = check_prompt_size(
                review_prompt_text, cfg.model_review, f"{name} review iter{iteration}"
            )
            review_prompt_file = cfg.report_dir / f"{tag}_review_prompt.md"
            write_file(review_prompt_file, review_prompt_text)

            review_log = cfg.report_dir / f"{tag}_review.log"

            if cfg.dry_run:
                write_file(review_log, f"DRY_RUN: reviewer skipped (iter {iteration})\n")
                break  # dry-run does one iteration

            cmd, stdin = build_review_command(
                cfg,
                review_prompt_file,
                cfg.model_review,
                f"{name}-review-{session}",
            )
            result = run_monitored(
                cmd,
                review_log,
                env=env,
                stdin_file=stdin,
                timeout=cfg.command_timeout,
                stuck_timeout=cfg.stuck_timeout,
                no_output_timeout=cfg.no_output_timeout,
                monitor_interval=cfg.monitor_interval,
                retry_max=cfg.retry_max,
                retry_sleep=cfg.retry_sleep,
            )

            if not result.success and not has_token(review_log, REVIEW_PASS):
                if result.permanent_error:
                    raise RuntimeError(
                        f"Reviewer hit permanent error for {name} iter {iteration}: "
                        f"{result.killed_reason} (prompt too large for model context?)"
                    )
                log.error(
                    "Reviewer process failed (%s) for %s iter %d",
                    result.killed_reason or f"exit={result.exit_code}",
                    name,
                    iteration,
                )
                raise RuntimeError(f"Reviewer process failed for {name}")

            # Check reviewer verdict
            if has_token(review_log, REVIEW_PASS):
                log.info("REVIEW_PASS received for %s at iteration %d", name, iteration)
                success = True
                break

            if iteration == cfg.max_iters:
                log.error("Max iterations reached for %s without REVIEW_PASS", name)
                raise RuntimeError(f"Max iterations ({cfg.max_iters}) reached for {name}")

            log.info("REVIEW_FAIL for %s iter %d; continuing to next iteration", name, iteration)

        if not cfg.dry_run and not success:
            raise RuntimeError(f"Prompt {name} did not receive REVIEW_PASS")

        return success or cfg.dry_run

    finally:
        # Always clean up regardless of success
        if success and not cfg.dry_run:
            cleanup_illegal_files(cfg.repo_root, cfg.report_dir)
        cleanup_temp_artifacts(cfg.repo_root)
        git_save_snapshot(cfg.repo_root, cfg.report_dir, f"{name}_{stamp}_after")


# ---------------------------------------------------------------------------
# Git commit for successful prompt
# ---------------------------------------------------------------------------


def commit_changes(repo: Path, prompt_name: str, dry_run: bool) -> None:
    """Stage and commit changes from a successful prompt."""
    if dry_run:
        return
    entries = git_status_entries(repo)
    if not entries:
        log.warning("No changes to commit for %s", prompt_name)
        return

    # Stage everything except report/output dirs
    to_stage = [
        path
        for status, path in entries
        if not path.startswith("doc/refactoring_reports") and not path.startswith("output/")
    ]
    if not to_stage:
        log.warning("No eligible changes to commit for %s", prompt_name)
        return

    git_run(repo, ["add", "--", *to_stage])
    result = git_run(repo, ["commit", "-m", f"refactor({prompt_name}): apply prompt changes"])
    if result.returncode != 0:
        log.error("Git commit failed for %s: %s", prompt_name, result.stderr.strip())
        raise RuntimeError(f"Git commit failed for {prompt_name}")
    log.info("Committed changes for %s", prompt_name)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def discover_prompts(cfg: BatchConfig) -> list[Path]:
    """Find prompt files to execute."""
    if cfg.prompt_index:
        if not (1 <= cfg.prompt_index <= len(DEFAULT_PROMPTS)):
            raise SystemExit(
                f"--prompt-index must be 1..{len(DEFAULT_PROMPTS)}, got {cfg.prompt_index}"
            )
        return [cfg.prompt_dir / DEFAULT_PROMPTS[cfg.prompt_index - 1]]

    # All prompts in order
    prompts = []
    for name in DEFAULT_PROMPTS:
        p = cfg.prompt_dir / name
        if p.exists():
            prompts.append(p)
        else:
            log.warning("Prompt file not found, skipping: %s", p)
    return prompts


def run_batch(cfg: BatchConfig) -> int:
    """Main entry point. Returns 0 on success, 1 on failure."""
    setup_logging(cfg.report_dir, cfg.verbose)

    log.info("=" * 60)
    log.info("Refactor batch starting")
    log.info("  backend:    %s", cfg.backend)
    log.info("  impl model: %s", cfg.model_impl)
    log.info("  review model: %s", cfg.model_review)
    log.info("  max iters:  %d", cfg.max_iters)
    log.info("  repo root:  %s", cfg.repo_root)
    log.info("  prompt dir: %s", cfg.prompt_dir)
    log.info("  dry run:    %s", cfg.dry_run)
    log.info("=" * 60)

    # Configure cline backend if needed
    if cfg.backend == "cline":
        configure_cline_from_opencode()

    env = build_env(cfg)
    prompts = discover_prompts(cfg)
    if not prompts:
        log.error("No prompt files found")
        return 1

    # Record starting branch
    start_branch = git_current_branch(cfg.repo_root)
    completed = load_completed(cfg.report_dir)

    # Preflight
    try:
        preflight(cfg, env)
    except RuntimeError as exc:
        log.error("Preflight failed: %s", exc)
        return 1

    # Process prompts sequentially
    for i, prompt in enumerate(prompts, 1):
        name = prompt.stem

        if name in completed:
            log.info("Skipping already completed: %s", name)
            continue

        # Branch safety check
        current = git_current_branch(cfg.repo_root)
        if current != start_branch:
            log.error(
                "Branch changed: expected %s, got %s. Aborting.",
                start_branch,
                current,
            )
            return 1

        log.info("--- [%d/%d] Running prompt: %s ---", i, len(prompts), name)
        try:
            ok = run_single_prompt(cfg, prompt, env)
            if ok:
                commit_changes(cfg.repo_root, name, cfg.dry_run)
                mark_completed(cfg.report_dir, name)
                log.info("COMPLETED: %s", name)
            else:
                log.error("FAILED: %s", name)
                return 1
        except RuntimeError as exc:
            log.error("FAILED: %s -- %s", name, exc)
            log.error("Aborting batch: prompts are sequential. Fix the issue before re-running.")
            return 1
        except KeyboardInterrupt:
            log.warning("Interrupted by user")
            return 130

    log.info("All prompts completed successfully")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> BatchConfig:
    parser = argparse.ArgumentParser(
        description="Autonomous batch refactoring with local LLM models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s                              Run all prompts with defaults (cline + devstral)
  %(prog)s --prompt-index 3             Run only prompt 03
  %(prog)s --backend opencode           Use opencode instead of cline
  %(prog)s --dry-run                    Skip LLM calls, test orchestration
  %(prog)s --model-impl devstral --model-review glm-4.7
  %(prog)s --verbose                    Show debug output
""",
    )

    # Basic options
    parser.add_argument(
        "--backend",
        choices=["cline", "opencode"],
        default="cline",
        help="LLM middleware to use (default: cline)",
    )
    parser.add_argument(
        "--model-impl", default="devstral", help="Implementer model (default: devstral)"
    )
    parser.add_argument(
        "--model-review", default="glm-4.7", help="Reviewer model (default: glm-4.7)"
    )
    parser.add_argument(
        "--prompt-index", type=int, default=0, help="Run single prompt (1-10), 0=all"
    )
    parser.add_argument(
        "--max-iters", type=int, default=5, help="Max implement/review cycles (default: 5)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM calls")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    # Retry / timeout
    parser.add_argument("--retry-max", type=int, default=2, help="Retries per command (default: 2)")
    parser.add_argument(
        "--retry-sleep", type=int, default=5, help="Seconds between retries (default: 5)"
    )
    parser.add_argument(
        "--command-timeout",
        type=int,
        default=3600,
        help="Per-command timeout in seconds (default: 3600)",
    )
    parser.add_argument(
        "--stuck-timeout",
        type=int,
        default=7200,
        help="Kill if log unchanged for N seconds (default: 7200)",
    )
    parser.add_argument(
        "--no-output-timeout",
        type=int,
        default=1200,
        help="Kill if zero output after N seconds (default: 1200)",
    )
    parser.add_argument(
        "--monitor-interval",
        type=int,
        default=900,
        help="Heartbeat interval in seconds (default: 900)",
    )

    # Git
    parser.add_argument(
        "--allow-git", action="store_true", help="Allow LLM full git access (default: read-only)"
    )

    # Housekeeping
    parser.add_argument(
        "--kill-stale", action="store_true", help="Kill orphaned LLM processes before starting"
    )

    args = parser.parse_args(argv)

    # Resolve paths relative to repo root
    repo_root = Path(__file__).resolve().parents[1]

    return BatchConfig(
        repo_root=repo_root,
        prompt_dir=repo_root / "doc" / "refactoring_prompts",
        report_dir=repo_root / "doc" / "refactoring_reports",
        backend=args.backend,
        model_impl=args.model_impl,
        model_review=args.model_review,
        max_iters=args.max_iters,
        retry_max=args.retry_max,
        retry_sleep=args.retry_sleep,
        dry_run=args.dry_run,
        allow_git=args.allow_git,
        verbose=args.verbose,
        prompt_index=args.prompt_index,
        command_timeout=args.command_timeout,
        stuck_timeout=args.stuck_timeout,
        no_output_timeout=args.no_output_timeout,
        monitor_interval=args.monitor_interval,
        kill_stale=args.kill_stale,
    )


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)
    if cfg.kill_stale:
        kill_stale_processes("opencode")
        kill_stale_processes("cline")
    return run_batch(cfg)


if __name__ == "__main__":
    sys.exit(main())
