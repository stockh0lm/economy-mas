"""Tests for tools/run_refactor_batch.py (refactored version)."""

from pathlib import Path

import pytest

import tools.run_refactor_batch as batch

# ---------------------------------------------------------------------------
# resolve_model
# ---------------------------------------------------------------------------


class TestResolveModel:
    def test_cline_devstral(self):
        assert batch.resolve_model("devstral", "cline") == "devstral-2-123b-instruct-2512"

    def test_cline_glm(self):
        assert batch.resolve_model("glm-4.7", "cline") == "glm-4.7-awq"

    def test_cline_gemini_free(self):
        assert (
            batch.resolve_model("gemini-free", "cline")
            == "google/gemini-2.0-flash-lite-preview-02-05:free"
        )

    def test_opencode_devstral_gets_prefix(self):
        assert (
            batch.resolve_model("devstral", "opencode")
            == "litellm-local/devstral-2-123b-instruct-2512"
        )

    def test_opencode_glm_gets_prefix(self):
        assert batch.resolve_model("glm-4.7", "opencode") == "litellm-local/glm-4.7-awq"

    def test_unknown_model_passed_through(self):
        assert batch.resolve_model("my-custom-model", "cline") == "my-custom-model"
        assert batch.resolve_model("my-custom-model", "opencode") == "my-custom-model"

    def test_empty_string(self):
        assert batch.resolve_model("", "cline") == ""
        assert batch.resolve_model("  ", "opencode") == ""


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


class TestFileHelpers:
    def test_tail_existing(self, tmp_path):
        f = tmp_path / "test.log"
        f.write_text("\n".join(f"line{i}" for i in range(10)))
        result = batch.tail(f, max_lines=3)
        assert result == "line7\nline8\nline9"

    def test_tail_missing(self, tmp_path):
        assert batch.tail(tmp_path / "missing.log") == ""

    def test_tail_max_bytes_truncates(self, tmp_path):
        f = tmp_path / "big.log"
        # 100 lines of 100 chars each = ~10100 bytes
        f.write_text("\n".join("x" * 100 for _ in range(100)))
        result = batch.tail(f, max_lines=100, max_bytes=500)
        assert len(result) <= 500

    def test_tail_max_bytes_zero_disables(self, tmp_path):
        f = tmp_path / "big.log"
        f.write_text("\n".join("x" * 100 for _ in range(100)))
        result = batch.tail(f, max_lines=100, max_bytes=0)
        # All 100 lines should be present
        assert result.count("\n") == 99  # 100 lines = 99 newlines

    def test_write_file_creates_dirs(self, tmp_path):
        target = tmp_path / "a" / "b" / "c.txt"
        batch.write_file(target, "hello")
        assert target.read_text() == "hello"

    def test_has_token_found(self, tmp_path):
        f = tmp_path / "log.txt"
        f.write_text("some text REVIEW_PASS more text")
        assert batch.has_token(f, "REVIEW_PASS")

    def test_has_token_not_found(self, tmp_path):
        f = tmp_path / "log.txt"
        f.write_text("some text")
        assert not batch.has_token(f, "REVIEW_PASS")

    def test_has_token_missing_file(self, tmp_path):
        assert not batch.has_token(tmp_path / "missing.txt", "REVIEW_PASS")


# ---------------------------------------------------------------------------
# Completed prompts tracking
# ---------------------------------------------------------------------------


class TestCompletedTracking:
    def test_load_empty(self, tmp_path):
        assert batch.load_completed(tmp_path) == set()

    def test_mark_and_load(self, tmp_path):
        batch.mark_completed(tmp_path, "01_golden_test_fix")
        batch.mark_completed(tmp_path, "02_golden_test_suite")
        batch.mark_completed(tmp_path, "01_golden_test_fix")  # duplicate

        completed = batch.load_completed(tmp_path)
        assert completed == {"01_golden_test_fix", "02_golden_test_suite"}


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_is_allowed_untracked(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()

        assert batch.is_allowed_untracked(repo, repo / "doc" / "refactoring_reports" / "file.log")
        assert batch.is_allowed_untracked(repo, repo / "output" / "data.csv")
        assert batch.is_allowed_untracked(repo, repo / "debug_test.py")
        # Source directories created by refactoring prompts are allowed
        assert batch.is_allowed_untracked(repo, repo / "simulation" / "engine.py")
        assert batch.is_allowed_untracked(repo, repo / "metrics" / "collector.py")
        assert batch.is_allowed_untracked(repo, repo / "agents" / "household" / "savings.py")
        assert batch.is_allowed_untracked(repo, repo / "tests" / "test_new.py")
        # Random files are not allowed
        assert not batch.is_allowed_untracked(repo, repo / "random_file.py")
        assert not batch.is_allowed_untracked(repo, repo / "node_modules" / "pkg")

    def test_cleanup_temp_artifacts(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "debug_test.py").write_text("pass")
        (repo / "output").mkdir()
        (repo / "output" / "data.csv").write_text("data")

        batch.cleanup_temp_artifacts(repo)

        assert not (repo / "debug_test.py").exists()
        assert not (repo / "output").exists()


# ---------------------------------------------------------------------------
# RunResult / run_monitored
# ---------------------------------------------------------------------------


class TestRunMonitored:
    def test_stops_on_no_output(self, tmp_path, monkeypatch):
        log_file = tmp_path / "run.log"

        class FakeProc:
            pid = 123

            def poll(self):
                return None

            def terminate(self):
                pass

            def wait(self, timeout=None):
                pass

            def kill(self):
                pass

        monkeypatch.setattr(batch.subprocess, "Popen", lambda *a, **kw: FakeProc())

        now = {"t": 0.0}
        monkeypatch.setattr(batch.time, "monotonic", lambda: now["t"])

        def fake_sleep(s):
            now["t"] += s

        monkeypatch.setattr(batch.time, "sleep", fake_sleep)

        result = batch.run_monitored(
            cmd=["echo", "noop"],
            log_file=log_file,
            timeout=9999,
            stuck_timeout=9999,
            no_output_timeout=5,
            monitor_interval=0,
            retry_max=1,
            retry_sleep=0,
        )

        assert not result.success
        assert result.killed_reason == "no_output"

    def test_success_on_zero_exit(self, tmp_path, monkeypatch):
        log_file = tmp_path / "run.log"

        call_count = {"n": 0}

        class FakeProc:
            pid = 456

            def poll(self):
                call_count["n"] += 1
                return 0 if call_count["n"] >= 2 else None

            def terminate(self):
                pass

            def wait(self, timeout=None):
                pass

        monkeypatch.setattr(batch.subprocess, "Popen", lambda *a, **kw: FakeProc())

        now = {"t": 0.0}
        monkeypatch.setattr(batch.time, "monotonic", lambda: now["t"])

        def fake_sleep(s):
            now["t"] += s

        monkeypatch.setattr(batch.time, "sleep", fake_sleep)

        result = batch.run_monitored(
            cmd=["echo", "ok"],
            log_file=log_file,
            timeout=9999,
            stuck_timeout=9999,
            no_output_timeout=9999,
            monitor_interval=0,
        )

        assert result.success
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


class TestPromptBuilding:
    def test_build_impl_prompt_first_iter(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        prompt.write_text("# Do the thing")

        result = batch.build_impl_prompt(prompt, 1, "git status: clean")
        assert "# Do the thing" in result
        assert "git status: clean" in result
        assert "Reviewer Feedback" not in result

    def test_build_impl_prompt_subsequent_iter(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        prompt.write_text("# Do the thing")

        result = batch.build_impl_prompt(prompt, 2, "git state", "fix the tests")
        assert "Reviewer Feedback" in result
        assert "fix the tests" in result

    def test_build_review_prompt(self, tmp_path):
        prompt = tmp_path / "prompt.md"
        prompt.write_text("# Review this")

        result = batch.build_review_prompt(prompt, "test output", "git state")
        assert "# Review this" in result
        assert "REVIEW_PASS" in result
        assert "REVIEW_FAIL" in result
        assert "test output" in result


# ---------------------------------------------------------------------------
# Backend commands
# ---------------------------------------------------------------------------


class TestBackendCommands:
    def test_build_impl_command_cline(self, tmp_path, monkeypatch):
        monkeypatch.setattr(batch, "find_cline", lambda: "/usr/bin/cline")
        cfg = batch.BatchConfig(backend="cline")
        prompt = tmp_path / "prompt.md"
        prompt.write_text("test")

        cmd, stdin = batch.build_impl_command(cfg, prompt, "devstral", "session-1")
        assert cmd[0] == "/usr/bin/cline"
        assert "--yolo" in cmd
        assert "-" in cmd
        assert stdin == prompt

    def test_build_impl_command_opencode(self, tmp_path, monkeypatch):
        monkeypatch.setattr(batch, "find_opencode", lambda: "/usr/bin/opencode")
        cfg = batch.BatchConfig(backend="opencode")
        prompt = tmp_path / "prompt.md"
        prompt.write_text("test")

        cmd, stdin = batch.build_impl_command(cfg, prompt, "devstral", "session-1")
        assert cmd[0] == "/usr/bin/opencode"
        assert "run" in cmd
        assert "--file" in cmd
        assert stdin is None

    def test_build_preflight_command_cline(self, monkeypatch):
        monkeypatch.setattr(batch, "find_cline", lambda: "/usr/bin/cline")
        cfg = batch.BatchConfig(backend="cline")
        cmd, stdin = batch.build_preflight_command(cfg, "devstral")
        assert "Reply with OK." in cmd
        assert stdin is None

    def test_build_preflight_command_opencode(self, monkeypatch):
        monkeypatch.setattr(batch, "find_opencode", lambda: "/usr/bin/opencode")
        cfg = batch.BatchConfig(backend="opencode")
        cmd, stdin = batch.build_preflight_command(cfg, "devstral")
        assert "Reply with OK." in cmd
        assert "--model" in cmd


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


class TestPreflight:
    def test_preflight_raises_on_failure(self, tmp_path, monkeypatch):
        cfg = batch.BatchConfig(
            backend="cline",
            report_dir=tmp_path / "reports",
            model_impl="devstral",
            model_review="glm-4.7",
        )
        monkeypatch.setattr(batch, "run_simple", lambda *a, **kw: False)
        monkeypatch.setattr(batch, "find_cline", lambda: "cline")

        with pytest.raises(RuntimeError, match="Preflight failed"):
            batch.preflight(cfg, {})

    def test_preflight_succeeds(self, tmp_path, monkeypatch):
        cfg = batch.BatchConfig(
            backend="cline",
            report_dir=tmp_path / "reports",
            model_impl="devstral",
            model_review="glm-4.7",
        )
        monkeypatch.setattr(batch, "run_simple", lambda *a, **kw: True)
        monkeypatch.setattr(batch, "find_cline", lambda: "cline")

        batch.preflight(cfg, {})  # should not raise


# ---------------------------------------------------------------------------
# run_single_prompt
# ---------------------------------------------------------------------------


class TestRunSinglePrompt:
    def test_success_on_review_pass(self, tmp_path, monkeypatch):
        cfg = batch.BatchConfig(
            repo_root=tmp_path / "repo",
            report_dir=tmp_path / "reports",
            backend="cline",
            max_iters=1,
            retry_max=1,
            retry_sleep=0,
        )
        (tmp_path / "repo").mkdir()

        prompt = tmp_path / "prompt.md"
        prompt.write_text("do something")

        def fake_run_monitored(cmd, log_file, **kwargs):
            if "review" in log_file.name:
                batch.write_file(log_file, "All good. REVIEW_PASS")
            else:
                batch.write_file(log_file, "Done. TESTS_PASS")
            return batch.RunResult(True, 0, None, 10.0)

        monkeypatch.setattr(batch, "run_monitored", fake_run_monitored)
        monkeypatch.setattr(batch, "find_cline", lambda: "cline")
        monkeypatch.setattr(batch, "git_save_snapshot", lambda *a, **kw: None)
        monkeypatch.setattr(batch, "cleanup_illegal_files", lambda *a, **kw: 0)
        monkeypatch.setattr(batch, "cleanup_temp_artifacts", lambda *a, **kw: None)
        monkeypatch.setattr(
            batch,
            "git_snapshot",
            lambda *a: "Current git status:\n(clean)\n\nCurrent git diff:\n(no diff)",
        )

        ok = batch.run_single_prompt(cfg, prompt, {})
        assert ok

    def test_dry_run_succeeds(self, tmp_path, monkeypatch):
        cfg = batch.BatchConfig(
            repo_root=tmp_path / "repo",
            report_dir=tmp_path / "reports",
            backend="cline",
            dry_run=True,
            max_iters=1,
        )
        (tmp_path / "repo").mkdir()

        prompt = tmp_path / "prompt.md"
        prompt.write_text("do something")

        monkeypatch.setattr(batch, "git_save_snapshot", lambda *a, **kw: None)
        monkeypatch.setattr(batch, "cleanup_temp_artifacts", lambda *a, **kw: None)
        monkeypatch.setattr(
            batch,
            "git_snapshot",
            lambda *a: "Current git status:\n(clean)\n\nCurrent git diff:\n(no diff)",
        )

        ok = batch.run_single_prompt(cfg, prompt, {})
        assert ok


# ---------------------------------------------------------------------------
# CLI / parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_defaults(self, monkeypatch):
        # parse_args uses __file__ to find repo root, mock it
        monkeypatch.setattr(
            batch,
            "__file__",
            str(Path("/tmp/Wirtschaftssimulation/tools/run_refactor_batch.py")),
        )
        cfg = batch.parse_args([])
        assert cfg.backend == "cline"
        assert cfg.model_impl == "devstral"
        assert cfg.model_review == "glm-4.7"
        assert cfg.max_iters == 5
        assert cfg.dry_run is False
        assert cfg.kill_stale is False

    def test_override_backend(self, monkeypatch):
        monkeypatch.setattr(
            batch,
            "__file__",
            str(Path("/tmp/Wirtschaftssimulation/tools/run_refactor_batch.py")),
        )
        cfg = batch.parse_args(["--backend", "opencode", "--dry-run", "--kill-stale"])
        assert cfg.backend == "opencode"
        assert cfg.dry_run is True
        assert cfg.kill_stale is True


# ---------------------------------------------------------------------------
# discover_prompts
# ---------------------------------------------------------------------------


class TestDiscoverPrompts:
    def test_all_prompts(self, tmp_path):
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        for name in batch.DEFAULT_PROMPTS[:3]:
            (prompt_dir / name).write_text("test")

        cfg = batch.BatchConfig(prompt_dir=prompt_dir)
        prompts = batch.discover_prompts(cfg)
        assert len(prompts) == 3

    def test_single_prompt(self, tmp_path):
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        for name in batch.DEFAULT_PROMPTS:
            (prompt_dir / name).write_text("test")

        cfg = batch.BatchConfig(prompt_dir=prompt_dir, prompt_index=3)
        prompts = batch.discover_prompts(cfg)
        assert len(prompts) == 1
        assert prompts[0].name == "03_plot_metrics_tests.md"

    def test_invalid_index(self, tmp_path):
        cfg = batch.BatchConfig(prompt_dir=tmp_path, prompt_index=99)
        with pytest.raises(SystemExit):
            batch.discover_prompts(cfg)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


class TestGitHelpers:
    def test_is_allowed_untracked_report(self, tmp_path):
        repo = tmp_path
        assert batch.is_allowed_untracked(repo, repo / "doc" / "refactoring_reports" / "x.log")

    def test_is_allowed_untracked_output(self, tmp_path):
        repo = tmp_path
        assert batch.is_allowed_untracked(repo, repo / "output" / "y.csv")

    def test_is_not_allowed_random(self, tmp_path):
        repo = tmp_path
        assert not batch.is_allowed_untracked(repo, repo / "hack.py")


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


class TestClassifyError:
    def test_permanent_max_tokens(self):
        assert batch.classify_error("max_tokens must be at least 1, got -9961") == "permanent"

    def test_permanent_context_length(self):
        assert batch.classify_error("279189 input tokens > 131072 max") == "permanent"

    def test_transient_upstream(self):
        assert batch.classify_error("403 upstream connect error") == "transient"

    def test_transient_502(self):
        assert batch.classify_error("502 Bad Gateway") == "transient"

    def test_unknown_error(self):
        assert batch.classify_error("something went wrong") == "unknown"

    def test_empty_stderr(self):
        assert batch.classify_error("") == "unknown"


# ---------------------------------------------------------------------------
# Prompt size validation
# ---------------------------------------------------------------------------


class TestCheckPromptSize:
    def test_small_prompt_unchanged(self):
        prompt = "# Hello\n\nCurrent git diff:\nsome diff"
        result = batch.check_prompt_size(prompt, "devstral", "test")
        assert result == prompt

    def test_unknown_model_unchanged(self):
        prompt = "x" * 1_000_000
        result = batch.check_prompt_size(prompt, "unknown-model", "test")
        assert result == prompt  # no limit known, pass through

    def test_oversized_prompt_truncated(self):
        # glm-4.7 has 128K tokens limit, 90% = ~115K tokens = ~460K chars
        base = "# Prompt\n\n"
        diff_section = "Current git diff:\n" + "x" * 600_000
        prompt = base + diff_section
        result = batch.check_prompt_size(prompt, "glm-4.7", "test")
        assert len(result) < len(prompt)
        assert "truncated" in result.lower()

    def test_oversized_no_diff_marker(self):
        # If there's no diff section, can't truncate — returns as-is
        prompt = "x" * 600_000
        result = batch.check_prompt_size(prompt, "glm-4.7", "test")
        assert result == prompt
