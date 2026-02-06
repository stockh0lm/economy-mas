#!/usr/bin/env python3
"""Batch runner for refactoring prompts with dual-model review.

Runs each prompt with an implementer model and reviewer model until reviewer
signs off or max iterations are reached. Captures logs and git diffs.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
import re

try:
    import logger
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    import logger


REVIEW_PASS_TOKEN = "REVIEW_PASS"
REVIEW_FAIL_TOKEN = "REVIEW_FAIL"
TESTS_PASS_TOKEN = "TESTS_PASS"
TESTS_FAIL_TOKEN = "TESTS_FAIL"

DEFAULT_MONITOR_INTERVAL = 900
DEFAULT_STUCK_TIMEOUT = 7200
DEFAULT_PROGRESS_TAIL_LINES = 20
DEFAULT_PROGRESS_CHECK_INTERVAL = 900
DEFAULT_PROGRESS_STUCK_THRESHOLD = 2
MIN_STAGNATION_ITERATIONS = 2

READONLY_GIT_WRAPPER = """#!/bin/sh
set -eu

cmd="${1:-}"
if [ -z "$cmd" ]; then
  exec "${REAL_GIT:-git}"
fi

case "$cmd" in
  status|diff|log|show|grep|ls-files|rev-parse|describe|blame|cat-file|whatchanged)
    exec "${REAL_GIT:-git}" "$@"
    ;;
  *)
    echo "git command blocked in opencode: $cmd" 1>&2
    exit 2
    ;;
esac
"""


def resolve_model(model: str) -> str:
    normalized = (model or "").strip()
    if not normalized:
        return normalized
    lowered = normalized.lower()
    if lowered == "devstral":
        return "litellm-local/devstral-2-123b-instruct-2512"
    if lowered == "glm-4.7":
        return "litellm-local/glm-4.7-awq"
    return normalized


def tail_lines(path: Path, max_lines: int = 200) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[-max_lines:])


def log_has_token(log_file: Path, token: str) -> bool:
    if not log_file.exists():
        return False
    text = log_file.read_text(encoding="utf-8", errors="ignore")
    return token in text


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_orchestrator_log(report_dir: Path, message: str) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    log_path = report_dir / "batch_orchestrator.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")
    logger.log(message, level="INFO")


def resolve_opencode_path() -> str:
    candidates = [
        shutil.which("opencode"),
        str(Path.home() / ".opencode" / "bin" / "opencode"),
        str(Path.home() / ".local" / "bin" / "opencode"),
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    raise SystemExit(
        "opencode executable not found. Ensure it is in PATH or installed in ~/.opencode/bin."
    )


def run_command_monitored(
    cmd: list[str],
    log_file: Path,
    retry_max: int,
    retry_sleep: int,
    timeout: int = 3600,
    monitor_interval: int = DEFAULT_MONITOR_INTERVAL,
    stuck_timeout: int = DEFAULT_STUCK_TIMEOUT,
    heartbeat_file: Path | None = None,
    progress_model: str | None = None,
    progress_label: str | None = None,
    progress_tail_lines: int = DEFAULT_PROGRESS_TAIL_LINES,
    progress_check_interval: int = DEFAULT_PROGRESS_CHECK_INTERVAL,
    progress_stuck_threshold: int = DEFAULT_PROGRESS_STUCK_THRESHOLD,
    progress_check_enabled: bool = True,
) -> bool:
    attempt = 1
    while attempt <= retry_max:
        start_time = time.time()
        last_heartbeat = 0.0
        last_log_change = start_time
        last_log_mtime = 0.0
        last_progress_check = 0.0
        stuck_score = 0
        if log_file.exists():
            try:
                last_log_mtime = log_file.stat().st_mtime
            except OSError:
                last_log_mtime = 0.0

        with log_file.open("w", encoding="utf-8") as handle:
            proc = subprocess.Popen(cmd, stdout=handle, stderr=subprocess.STDOUT)
            while True:
                now = time.time()
                if log_file.exists():
                    try:
                        mtime = log_file.stat().st_mtime
                    except OSError:
                        mtime = last_log_mtime
                    if mtime > last_log_mtime:
                        last_log_mtime = mtime
                        last_log_change = now

                if monitor_interval and now - last_heartbeat >= monitor_interval:
                    last_heartbeat = now
                    message = (
                        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] heartbeat: "
                        f"pid={proc.pid} elapsed={int(now - start_time)}s "
                        f"log={log_file.name}\n"
                    )
                    if heartbeat_file is not None:
                        heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
                        with heartbeat_file.open("a", encoding="utf-8") as heartbeat:
                            heartbeat.write(message)
                    else:
                        logger.log(message.rstrip(), level="DEBUG")

                if (
                    progress_check_enabled
                    and progress_model
                    and progress_label
                    and progress_check_interval
                    and now - last_progress_check >= progress_check_interval
                ):
                    last_progress_check = now
                    status = live_progress_check(
                        log_file=log_file,
                        report_dir=heartbeat_file.parent if heartbeat_file else log_file.parent,
                        label=progress_label,
                        model_review=progress_model,
                        tail_lines_count=progress_tail_lines,
                    )
                    if status == "STUCK":
                        stuck_score += 1
                    elif status == "PROGRESS":
                        stuck_score = 0
                    if stuck_score >= progress_stuck_threshold:
                        proc.terminate()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        with log_file.open("a", encoding="utf-8") as handle_append:
                            handle_append.write(
                                f"\nrun stalled by progress check (attempt {attempt}/{retry_max})\n"
                            )
                        break

                if timeout and now - start_time >= timeout:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    with log_file.open("a", encoding="utf-8") as handle_append:
                        handle_append.write(
                            f"\nrun timed out after {timeout}s (attempt {attempt}/{retry_max})\n"
                        )
                    break

                if stuck_timeout and now - last_log_change >= stuck_timeout:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    with log_file.open("a", encoding="utf-8") as handle_append:
                        handle_append.write(
                            f"\nrun stalled for {stuck_timeout}s (attempt {attempt}/{retry_max})\n"
                        )
                    break

                return_code = proc.poll()
                if return_code is not None:
                    if return_code == 0:
                        return True
                    break

                time.sleep(5)

        with log_file.open("a", encoding="utf-8") as handle_append:
            handle_append.write(f"\nrun failed (attempt {attempt}/{retry_max})\n")
        attempt += 1
        time.sleep(retry_sleep)
    return False


def live_progress_check(
    log_file: Path,
    report_dir: Path,
    label: str,
    model_review: str,
    tail_lines_count: int = DEFAULT_PROGRESS_TAIL_LINES,
    unchanged_threshold: int = DEFAULT_PROGRESS_STUCK_THRESHOLD,
) -> str:
    log_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_")
    meta_path = report_dir / f"{log_name}_progress_meta.txt"
    count_path = report_dir / f"{log_name}_progress_count.txt"

    log_tail = tail_lines(log_file, tail_lines_count)
    if not log_tail.strip():
        return "UNKNOWN"

    prev_tail = ""
    if meta_path.exists():
        try:
            prev_tail = meta_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            prev_tail = ""

    if log_tail == prev_tail:
        prev_count = 0
        if count_path.exists():
            try:
                prev_count = int(count_path.read_text(encoding="utf-8", errors="ignore") or "0")
            except ValueError:
                prev_count = 0
        prev_count += 1
        count_path.write_text(str(prev_count), encoding="utf-8")
        if prev_count >= unchanged_threshold:
            prompt = (
                "Analyze the latest refactor log tail. "
                "If it shows no progress or repeated failures, reply STUCK. "
                "If it shows progress, reply PROGRESS. "
                "Only output one of these tokens.\n\nLog tail:\n"
            )
            cmd = [
                resolve_opencode_path(),
                "run",
                prompt + log_tail,
                "--model",
                resolve_model(model_review),
            ]
            log_path = report_dir / f"{log_name}_progress_check.log"
            ok = run_command(cmd, log_path, retry_max=1, retry_sleep=2)
            if not ok:
                return "UNKNOWN"
            response = log_path.read_text(encoding="utf-8", errors="ignore")
            for line in reversed(response.splitlines()):
                if line.strip().startswith("STUCK"):
                    return "STUCK"
                if line.strip().startswith("PROGRESS"):
                    return "PROGRESS"
            return "UNKNOWN"
    else:
        meta_path.write_text(log_tail, encoding="utf-8")
        count_path.write_text("0", encoding="utf-8")
        return "PROGRESS"

    return "UNKNOWN"


def run_command(
    cmd: list[str],
    log_file: Path,
    retry_max: int,
    retry_sleep: int,
    timeout: int = 3600,
    env: dict[str, str] | None = None,
) -> bool:
    attempt = 1
    while attempt <= retry_max:
        with log_file.open("w", encoding="utf-8") as handle:
            try:
                proc = subprocess.run(
                    cmd, stdout=handle, stderr=subprocess.STDOUT, timeout=timeout, env=env
                )
                if proc.returncode == 0:
                    return True
            except subprocess.TimeoutExpired:
                with log_file.open("a", encoding="utf-8") as handle:
                    handle.write(
                        f"\nrun timed out after {timeout}s (attempt {attempt}/{retry_max})\n"
                    )

        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(f"\nrun failed (attempt {attempt}/{retry_max})\n")
        attempt += 1
        time.sleep(retry_sleep)
    return False


def build_opencode_env(repo_root: Path, allow_git: bool) -> dict[str, str]:
    env = os.environ.copy()
    if not allow_git:
        wrapper_dir = repo_root / "tools" / ".opencode"
        wrapper_dir.mkdir(parents=True, exist_ok=True)
        wrapper_path = wrapper_dir / "git"
        wrapper_path.write_text(READONLY_GIT_WRAPPER, encoding="utf-8")
        wrapper_path.chmod(0o755)
        env["REAL_GIT"] = env.get("REAL_GIT", "git")
        env["PATH"] = f"{wrapper_dir}:{env.get('PATH', '')}"
    return env


def git_capture(repo_root: Path, args: list[str], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True)
    out_path.write_text(result.stdout, encoding="utf-8")


def get_git_snapshot(repo_root: Path) -> str:
    status = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain=v1"],
        check=False,
        capture_output=True,
        text=True,
    )
    diff = subprocess.run(
        ["git", "-C", str(repo_root), "diff"],
        check=False,
        capture_output=True,
        text=True,
    )
    status_text = status.stdout.strip()
    diff_text = diff.stdout.strip()
    if not status_text:
        status_text = "(clean)"
    if not diff_text:
        diff_text = "(no diff)"
    return f"Current git status:\n{status_text}\n\nCurrent git diff:\n{diff_text}"


def git_status_untracked(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain=v1"],
        capture_output=True,
        text=True,
    )
    paths: list[Path] = []
    for line in result.stdout.splitlines():
        if line.startswith("?? "):
            rel = line[3:].strip()
            if rel:
                paths.append(repo_root / rel)
    return paths


def is_allowed_untracked(repo_root: Path, path: Path) -> bool:
    rel = path.relative_to(repo_root)
    if (
        rel.parts
        and rel.parts[0] == "doc"
        and len(rel.parts) > 1
        and rel.parts[1] == "refactoring_reports"
    ):
        return True
    if rel.parts and rel.parts[0] == "output":
        return True
    if path.parent == repo_root and path.name.startswith("debug_") and path.suffix == ".py":
        return True
    return False


def classify_illegal_file(
    file_path: Path,
    model_review: str,
    log_file: Path,
    retry_max: int,
    retry_sleep: int,
    opencode_env: dict[str, str] | None,
) -> str:
    """Ask the reviewer model to classify an illegal file.

    Returns: "KEEP", "DELETE", or "MOVE:<path>".
    """
    prompt = (
        "Classify this file according to the project hierarchy. "
        "If it should remain, reply KEEP. "
        "If it should be removed, reply DELETE. "
        "If it should be moved, reply MOVE:<relative/path>. "
        "Only output one of these tokens."
    )
    cmd = [
        "opencode",
        "run",
        prompt,
        "--model",
        resolve_model(model_review),
        "--file",
        str(file_path),
    ]
    ok = run_command(cmd, log_file, retry_max, retry_sleep, env=opencode_env)
    if not ok:
        return "DELETE"
    text = log_file.read_text(encoding="utf-8", errors="ignore")
    for line in reversed(text.splitlines()):
        if line.startswith("KEEP"):
            return "KEEP"
        if line.startswith("DELETE"):
            return "DELETE"
        if line.startswith("MOVE:"):
            return line.strip()
    return "DELETE"


def cleanup_illegal_files(
    repo_root: Path,
    report_dir: Path,
    model_review: str,
    retry_max: int,
    retry_sleep: int,
    llm_classify: bool,
    opencode_env: dict[str, str] | None,
) -> None:
    illegal = []
    for path in git_status_untracked(repo_root):
        if not is_allowed_untracked(repo_root, path):
            illegal.append(path)

    if not illegal:
        return

    log_file = report_dir / "illegal_files.log"
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"\nIllegal files detected ({time.strftime('%Y-%m-%d %H:%M:%S')}):\n")
        for path in illegal:
            handle.write(f"- {path}\n")

    for path in illegal:
        action = "DELETE"
        if llm_classify and path.exists() and path.is_file():
            classify_log = report_dir / f"illegal_classify_{path.name}.log"
            action = classify_illegal_file(
                path, model_review, classify_log, retry_max, retry_sleep, opencode_env
            )

        if action.startswith("MOVE:"):
            target = action.split(":", 1)[1].strip()
            if target:
                dest = repo_root / target
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    path.rename(dest)
                except OSError:
                    try:
                        path.unlink()
                    except OSError:
                        pass
            else:
                try:
                    path.unlink()
                except OSError:
                    pass
        elif action == "KEEP":
            continue
        else:
            try:
                if path.is_dir():
                    for sub in path.glob("**/*"):
                        if sub.is_file():
                            try:
                                sub.unlink()
                            except OSError:
                                pass
                    path.rmdir()
                else:
                    path.unlink()
            except OSError:
                pass


def build_prompt(base_prompt: Path, extra: str | None, state: str | None = None) -> str:
    base_text = base_prompt.read_text(encoding="utf-8")
    if not extra and not state:
        return base_text
    sections: list[str] = []
    if extra:
        sections.append(extra)
    if state:
        sections.append(state)
    return f"{base_text}\n\n---\n\n" + "\n\n---\n\n".join(sections) + "\n"


def prompt_has_pass(report_dir: Path, base_name: str) -> bool:
    pattern = f"{base_name}_*_iter*_review.log"
    logs = sorted(report_dir.glob(pattern))
    if not logs:
        return False
    for log_path in reversed(logs):
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if REVIEW_PASS_TOKEN in text:
            return True
    return False


def load_completed_prompts(report_dir: Path) -> set[str]:
    marker = report_dir / "completed_prompts.txt"
    if not marker.exists():
        return set()
    try:
        lines = marker.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return set()
    completed = set()
    for line in lines:
        name = line.strip()
        if name:
            completed.add(name)
    return completed


def check_stagnation(
    report_dir: Path,
    base_name: str,
    run_stamp: str,
    current_iter: int,
    model_review: str,
    tail_max_lines: int = DEFAULT_PROGRESS_TAIL_LINES * 2,
    opencode_env: dict[str, str] | None = None,
) -> bool:
    """Analyze logs to detect if the refactoring is stuck in a loop.

    Returns True if stagnation is detected.
    """
    if current_iter < MIN_STAGNATION_ITERATIONS:
        return False

    # Collect the last two iterations of logs
    logs = []
    for i in range(current_iter - 1, current_iter + 1):
        impl_log = report_dir / f"{base_name}_{run_stamp}_iter{i}_impl.log"
        review_log = report_dir / f"{base_name}_{run_stamp}_iter{i}_review.log"
        if impl_log.exists():
            logs.append(
                f"--- Iteration {i} Implementer ---\n{tail_lines(impl_log, tail_max_lines)}"
            )
        if review_log.exists():
            logs.append(f"--- Iteration {i} Reviewer ---\n{tail_lines(review_log, tail_max_lines)}")

    log_context = "\n".join(logs)
    prompt = (
        "Analyze these refactoring logs. Are the models repeating the same errors, "
        "reverting changes made in previous iterations, or showing no logical progress? "
        "If they are stuck in a loop or deadlock, reply STAGNATED. "
        "If they are still making different attempts or moving forward, reply PROGRESS. "
        "Only output one of these tokens."
    )

    log_file = report_dir / f"{base_name}_{run_stamp}_stagnation_check.log"
    cmd = [
        resolve_opencode_path(),
        "run",
        prompt,
        "--model",
        resolve_model(model_review),
    ]

    # We pass the log context via stdin if opencode supports it, or we just rely on the LLM's
    # memory if we use a session. For now, let's append the context to the prompt.
    full_prompt = f"{prompt}\n\nLog context:\n{log_context}"
    cmd[2] = full_prompt

    # Short timeout for stagnation check
    ok = run_command(cmd, log_file, retry_max=1, retry_sleep=2, timeout=300, env=opencode_env)
    if not ok:
        return False  # Assume progress if check fails

    text = log_file.read_text(encoding="utf-8", errors="ignore")
    return "STAGNATED" in text


def run_prompt(
    repo_root: Path,
    prompt: Path,
    report_dir: Path,
    model_impl: str,
    model_review: str,
    max_iters: int,
    retry_max: int,
    retry_sleep: int,
    dry_run: bool,
    llm_classify: bool,
    monitor_interval: int,
    stuck_timeout: int,
    progress_tail_lines: int,
    progress_check_interval: int,
    progress_stuck_threshold: int,
    progress_check_enabled: bool,
    opencode_env: dict[str, str] | None,
) -> None:
    base_name = prompt.stem
    run_stamp = time.strftime("%Y%m%d_%H%M%S")
    success = False

    git_capture(
        repo_root, ["status", "--porcelain=v1"], report_dir / f"{base_name}_{run_stamp}_status.txt"
    )
    git_capture(repo_root, ["diff"], report_dir / f"{base_name}_{run_stamp}_diff_before.patch")

    try:
        for iteration in range(1, max_iters + 1):
            iter_stamp = f"{run_stamp}_iter{iteration}"
            # ... existing iteration logic ...
            impl_prompt_path = report_dir / f"{base_name}_{iter_stamp}_impl_prompt.md"
            review_prompt_path = report_dir / f"{base_name}_{iter_stamp}_review_prompt.md"
            impl_log = report_dir / f"{base_name}_{iter_stamp}_impl.log"
            review_log = report_dir / f"{base_name}_{iter_stamp}_review.log"

            impl_extra = None
            if iteration > 1:
                prev_log = report_dir / f"{base_name}_{run_stamp}_iter{iteration - 1}_review.log"
                prev_tail = tail_lines(prev_log)
                if prev_tail:
                    impl_extra = (
                        "Implementer instructions:\n"
                        "- Apply reviewer feedback from the last iteration.\n"
                        "- Re-run required verification commands.\n"
                        "- Summarize changes and remaining risks.\n"
                        f"- End your response with {TESTS_PASS_TOKEN} if all required verification commands succeeded.\n"
                        f"- End your response with {TESTS_FAIL_TOKEN} if any required verification command failed.\n\n"
                        "Reviewer feedback (tail):\n"
                        f"{prev_tail}\n"
                    )

            state_context = get_git_snapshot(repo_root)
            if iteration > 1:
                state_context = f"Current state for iteration {iteration}:\n{state_context}"
            write_text(impl_prompt_path, build_prompt(prompt, impl_extra, state_context))

            if dry_run:
                write_text(impl_log, "DRY_RUN: implementer skipped\n")
            else:
                cmd_impl = [
                    resolve_opencode_path(),
                    "run",
                    "Execute the attached prompt file end-to-end.",
                    "--model",
                    resolve_model(model_impl),
                    "--file",
                    str(impl_prompt_path),
                ]
                ok = run_command_monitored(
                    cmd_impl,
                    impl_log,
                    retry_max,
                    retry_sleep,
                    monitor_interval=monitor_interval,
                    stuck_timeout=stuck_timeout,
                    heartbeat_file=report_dir / "batch_run_console.log",
                    progress_model=model_review,
                    progress_label=f"{base_name}_iter{iteration}_impl",
                    progress_tail_lines=progress_tail_lines,
                    progress_check_interval=progress_check_interval,
                    progress_stuck_threshold=progress_stuck_threshold,
                    progress_check_enabled=progress_check_enabled,
                )
                if not ok and not log_has_token(impl_log, TESTS_PASS_TOKEN):
                    raise RuntimeError(f"Implementer run failed for {base_name}")

            if not dry_run:
                impl_text = impl_log.read_text(encoding="utf-8", errors="ignore")
                # We no longer raise RuntimeError here for test failures.
                # Instead, we let the Reviewer analyze the log and decide to fail the iteration,
                # which allows the Implementer to fix the issue in the next iteration.
                if TESTS_FAIL_TOKEN in impl_text:
                    logger.log(
                        f"Note: Implementer reported explicit {TESTS_FAIL_TOKEN} for {base_name}",
                        level="WARNING",
                    )
                elif TESTS_PASS_TOKEN not in impl_text:
                    success_regex = re.compile(r"\b\d+\s+passed\b", re.IGNORECASE)
                    if not success_regex.search(impl_text):
                        logger.log(
                            f"Note: Implementer logs do not indicate test success for {base_name}",
                            level="WARNING",
                        )

            review_extra = (
                "Reviewer instructions:\n"
                "- Review the diff and changes against the prompt requirements.\n"
                f"- If all requirements are met and tests pass, end your response with: {REVIEW_PASS_TOKEN}\n"
                f"- If issues remain, end your response with: {REVIEW_FAIL_TOKEN}\n"
                "- When failing, provide concrete fixes or a patch description for the implementer.\n"
                "- If implementer reported TESTS_FAIL or did not report TESTS_PASS, you must end with REVIEW_FAIL.\n\n"
            )
            impl_tail = tail_lines(impl_log)
            if impl_tail:
                review_extra += f"Implementer log (tail):\n{impl_tail}\n"

            write_text(review_prompt_path, build_prompt(prompt, review_extra, state_context))

            if dry_run:
                write_text(review_log, "DRY_RUN: reviewer skipped\n")
            else:
                cmd_review = [
                    resolve_opencode_path(),
                    "run",
                    "Execute the attached prompt file end-to-end.",
                    "--model",
                    resolve_model(model_review),
                    "--file",
                    str(review_prompt_path),
                ]
                ok = run_command_monitored(
                    cmd_review,
                    review_log,
                    retry_max,
                    retry_sleep,
                    monitor_interval=monitor_interval,
                    stuck_timeout=stuck_timeout,
                    heartbeat_file=report_dir / "batch_run_console.log",
                    progress_model=model_review,
                    progress_label=f"{base_name}_iter{iteration}_review",
                    progress_tail_lines=progress_tail_lines,
                    progress_check_interval=progress_check_interval,
                    progress_stuck_threshold=progress_stuck_threshold,
                    progress_check_enabled=progress_check_enabled,
                )
                if not ok and not log_has_token(review_log, REVIEW_PASS_TOKEN):
                    raise RuntimeError(f"Reviewer run failed for {base_name}")

            if dry_run:
                break

            review_text = review_log.read_text(encoding="utf-8", errors="ignore")
            if REVIEW_PASS_TOKEN in review_text:
                success = True
                break

            # Check for stagnation before continuing to next iteration
            if check_stagnation(
                report_dir=report_dir,
                base_name=base_name,
                run_stamp=run_stamp,
                current_iter=iteration,
                model_review=model_review,
                opencode_env=opencode_env,
            ):
                raise RuntimeError(f"Stagnation detected for {base_name} at iteration {iteration}")

            if iteration == max_iters:
                raise RuntimeError(f"Max iterations reached for {base_name}")

        if not dry_run and not success:
            raise RuntimeError(f"Review did not pass for {base_name}")

    finally:
        # Enforce filesystem hygiene and cleanup illegal files.
        if success and not dry_run:
            cleanup_illegal_files(
                repo_root=repo_root,
                report_dir=report_dir,
                model_review=model_review,
                retry_max=retry_max,
                retry_sleep=retry_sleep,
                llm_classify=llm_classify,
                opencode_env=opencode_env,
            )

        # Cleanup debug scripts and output artifacts after prompt completion.
        for debug_file in repo_root.glob("debug_*.py"):
            try:
                debug_file.unlink()
            except OSError:
                pass

        output_dir = repo_root / "output"
        if output_dir.exists():
            for child in output_dir.iterdir():
                if child.is_dir():
                    for sub in child.glob("**/*"):
                        if sub.is_file():
                            try:
                                sub.unlink()
                            except OSError:
                                pass
                    try:
                        child.rmdir()
                    except OSError:
                        pass
                elif child.is_file():
                    try:
                        child.unlink()
                    except OSError:
                        pass

        git_capture(repo_root, ["diff"], report_dir / f"{base_name}_{run_stamp}_diff_after.patch")
        git_capture(
            repo_root,
            ["status", "--porcelain=v1"],
            report_dir / f"{base_name}_{run_stamp}_status_after.txt",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-impl", default="devstral")
    parser.add_argument("--model-review", default="glm-4.7")
    parser.add_argument("--max-iters", type=int, default=5)
    parser.add_argument("--retry-max", type=int, default=2)
    parser.add_argument("--retry-sleep", type=int, default=5)
    parser.add_argument("--prompt-index", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-llm-classify", action="store_true")
    parser.add_argument("--no-progress-check", action="store_true")
    parser.add_argument("--monitor-interval", type=int, default=DEFAULT_MONITOR_INTERVAL)
    parser.add_argument("--stuck-timeout", type=int, default=DEFAULT_STUCK_TIMEOUT)
    parser.add_argument("--progress-tail-lines", type=int, default=DEFAULT_PROGRESS_TAIL_LINES)
    parser.add_argument(
        "--progress-check-interval",
        type=int,
        default=DEFAULT_PROGRESS_CHECK_INTERVAL,
    )
    parser.add_argument(
        "--progress-stuck-threshold",
        type=int,
        default=DEFAULT_PROGRESS_STUCK_THRESHOLD,
    )
    parser.add_argument(
        "--allow-git",
        action="store_true",
        help="Allow opencode to run full git commands (default: read-only)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    prompt_dir = repo_root / "doc" / "refactoring_prompts"
    report_dir = repo_root / "doc" / "refactoring_reports"

    prompts = [
        prompt_dir / "01_golden_test_fix.md",
        prompt_dir / "02_golden_test_suite.md",
        prompt_dir / "03_plot_metrics_tests.md",
        prompt_dir / "04_extract_simulation_engine.md",
        prompt_dir / "05_refactor_metrics.md",
        prompt_dir / "06_extract_household_components.md",
        prompt_dir / "07_increase_test_coverage.md",
        prompt_dir / "08_performance_optimization.md",
        prompt_dir / "09_documentation_types.md",
        prompt_dir / "10_comprehensive_regression.md",
    ]

    if args.prompt_index:
        if not (1 <= args.prompt_index <= len(prompts)):
            raise SystemExit("prompt-index out of range")
        prompts = [prompts[args.prompt_index - 1]]

    model_impl = resolve_model(args.model_impl)
    model_review = resolve_model(args.model_review)
    opencode_env = build_opencode_env(repo_root, allow_git=args.allow_git)

    completed_prompts = load_completed_prompts(report_dir)

    for prompt in prompts:
        if not prompt.exists():
            logger.log(f"Skipping missing prompt file: {prompt}", level="WARNING")
            continue

        logger.log(f"--- Running prompt: {prompt.name} ---", level="INFO")
        try:
            run_prompt(
                repo_root=repo_root,
                prompt=prompt,
                report_dir=report_dir,
                model_impl=model_impl,
                model_review=model_review,
                max_iters=args.max_iters,
                retry_max=args.retry_max,
                retry_sleep=args.retry_sleep,
                dry_run=args.dry_run,
                llm_classify=not args.no_llm_classify,
                monitor_interval=args.monitor_interval,
                stuck_timeout=args.stuck_timeout,
                progress_tail_lines=args.progress_tail_lines,
                progress_check_interval=args.progress_check_interval,
                progress_stuck_threshold=args.progress_stuck_threshold,
                progress_check_enabled=not args.no_progress_check,
                opencode_env=opencode_env,
            )
            logger.log(f"✅ Finished prompt: {prompt.name}", level="INFO")
        except Exception as e:
            logger.log(f"❌ Failed prompt: {prompt.name} with error: {e}", level="ERROR")
            logger.log(
                "\nAborting: Prompts are sequential and build on each other. Resolve the issue before continuing.",
                level="ERROR",
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
