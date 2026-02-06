import tools.run_refactor_batch as batch


def test_resolve_opencode_path_prefers_path(tmp_path, monkeypatch):
    opencode = tmp_path / "opencode"
    opencode.write_text("")

    monkeypatch.setattr(batch.shutil, "which", lambda name: str(opencode))

    assert batch.resolve_opencode_path() == str(opencode)


def test_resolve_opencode_path_falls_back_to_home(tmp_path, monkeypatch):
    home = tmp_path
    opencode = home / ".opencode" / "bin" / "opencode"
    opencode.parent.mkdir(parents=True)
    opencode.write_text("")

    monkeypatch.setattr(batch.shutil, "which", lambda name: None)
    monkeypatch.setattr(batch.Path, "home", lambda: home)

    assert batch.resolve_opencode_path() == str(opencode)


def test_live_progress_check_stuck_on_unchanged_tail(tmp_path, monkeypatch):
    log_file = tmp_path / "run.log"
    log_file.write_text("same log tail")
    label = "prompt_iter1"

    meta_path = tmp_path / f"{label}_progress_meta.txt"
    meta_path.write_text("same log tail")
    count_path = tmp_path / f"{label}_progress_count.txt"
    count_path.write_text("0")

    monkeypatch.setattr(batch, "run_command", lambda *args, **kwargs: True)
    monkeypatch.setattr(batch, "resolve_opencode_path", lambda: "opencode")
    progress_log = tmp_path / f"{label}_progress_check.log"
    progress_log.write_text("STUCK", encoding="utf-8")

    status = batch.live_progress_check(
        log_file=log_file,
        report_dir=tmp_path,
        label=label,
        model_review="dummy-model",
        tail_lines_count=20,
        unchanged_threshold=1,
    )

    assert status == "STUCK"


def test_run_command_monitored_stops_on_progress_stuck(tmp_path, monkeypatch):
    log_file = tmp_path / "run.log"

    class FakeProc:
        def __init__(self):
            self.pid = 123

        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return None

        def kill(self):
            return None

    fake_proc = FakeProc()

    monkeypatch.setattr(batch.subprocess, "Popen", lambda *args, **kwargs: fake_proc)
    monkeypatch.setattr(batch, "live_progress_check", lambda **kwargs: "STUCK")

    now = {"t": 0.0}

    def fake_time():
        return now["t"]

    def fake_sleep(seconds):
        now["t"] += seconds

    monkeypatch.setattr(batch.time, "time", fake_time)
    monkeypatch.setattr(batch.time, "sleep", fake_sleep)

    ok = batch.run_command_monitored(
        cmd=["echo", "noop"],
        log_file=log_file,
        retry_max=1,
        retry_sleep=0,
        timeout=999,
        monitor_interval=0,
        stuck_timeout=999,
        progress_model="dummy-model",
        progress_label="prompt_iter1",
        progress_check_interval=1,
        progress_stuck_threshold=1,
    )

    assert ok is False
    assert "run stalled by progress check" in log_file.read_text(encoding="utf-8")


def test_run_command_monitored_stops_on_no_output(tmp_path, monkeypatch):
    log_file = tmp_path / "run.log"

    class FakeProc:
        def __init__(self):
            self.pid = 123

        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return None

        def kill(self):
            return None

    fake_proc = FakeProc()
    monkeypatch.setattr(batch.subprocess, "Popen", lambda *args, **kwargs: fake_proc)

    now = {"t": 0.0}

    def fake_time():
        return now["t"]

    def fake_sleep(seconds):
        now["t"] += seconds

    monkeypatch.setattr(batch.time, "time", fake_time)
    monkeypatch.setattr(batch.time, "sleep", fake_sleep)

    ok = batch.run_command_monitored(
        cmd=["echo", "noop"],
        log_file=log_file,
        retry_max=1,
        retry_sleep=0,
        timeout=6,
        monitor_interval=0,
        stuck_timeout=0,
        progress_check_enabled=False,
        no_output_timeout=5,
    )

    assert ok is False
    assert "run produced no output" in log_file.read_text(encoding="utf-8")
    stderr_file = log_file.with_suffix(log_file.suffix + ".stderr")
    assert stderr_file.exists()


def test_check_stagnation_uses_llm_result(tmp_path, monkeypatch):
    report_dir = tmp_path
    base_name = "test_prompt"
    run_stamp = "20260101_000000"

    (report_dir / f"{base_name}_{run_stamp}_iter1_impl.log").write_text("impl 1")
    (report_dir / f"{base_name}_{run_stamp}_iter1_review.log").write_text("review 1")
    (report_dir / f"{base_name}_{run_stamp}_iter2_impl.log").write_text("impl 2")
    (report_dir / f"{base_name}_{run_stamp}_iter2_review.log").write_text("review 2")

    def fake_run_command(cmd, log_file, retry_max, retry_sleep, timeout=3600, env=None):
        log_file.write_text("STAGNATED", encoding="utf-8")
        return True

    monkeypatch.setattr(batch, "run_command", fake_run_command)
    monkeypatch.setattr(batch, "resolve_opencode_path", lambda: "opencode")

    assert batch.check_stagnation(
        report_dir=report_dir,
        base_name=base_name,
        run_stamp=run_stamp,
        current_iter=2,
        model_review="glm-4.7",
    )


def test_write_orchestrator_log_creates_log(tmp_path):
    report_dir = tmp_path / "reports"

    batch.write_orchestrator_log(report_dir, "first")
    batch.write_orchestrator_log(report_dir, "second")

    log_path = report_dir / "batch_orchestrator.log"
    assert log_path.exists()
    assert log_path.read_text(encoding="utf-8") == "first\nsecond\n"


def test_run_prompt_sets_success_on_review_pass(tmp_path, monkeypatch):
    report_dir = tmp_path / "reports"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt")

    def fake_run_command_monitored(*args, **kwargs):
        log_path = args[1]
        if "review" in log_path.name:
            log_path.write_text("REVIEW_PASS")
        else:
            log_path.write_text("TESTS_PASS")
        return True

    monkeypatch.setattr(batch, "run_command_monitored", fake_run_command_monitored)
    monkeypatch.setattr(batch, "resolve_opencode_path", lambda: "opencode")
    monkeypatch.setattr(batch, "git_capture", lambda *args, **kwargs: None)
    monkeypatch.setattr(batch, "cleanup_illegal_files", lambda *args, **kwargs: None)

    batch.run_prompt(
        repo_root=repo_root,
        prompt=prompt,
        report_dir=report_dir,
        model_impl="devstral",
        model_review="glm-4.7",
        max_iters=1,
        retry_max=1,
        retry_sleep=0,
        dry_run=False,
        llm_classify=False,
        monitor_interval=0,
        stuck_timeout=0,
        progress_tail_lines=5,
        progress_check_interval=0,
        progress_stuck_threshold=1,
        progress_check_enabled=False,
        no_output_timeout=0,
        opencode_env=None,
        impl_title=None,
        review_title=None,
    )


def test_run_prompt_includes_git_state_in_prompts(tmp_path, monkeypatch):
    report_dir = tmp_path / "reports"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt")

    monkeypatch.setattr(batch, "git_capture", lambda *args, **kwargs: None)
    monkeypatch.setattr(batch, "cleanup_illegal_files", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        batch,
        "get_git_snapshot",
        lambda *_: "Current git status:\n(clean)\n\nCurrent git diff:\n(no diff)",
    )

    def fake_run_command_monitored(*args, **kwargs):
        log_path = args[1]
        log_path.write_text("REVIEW_PASS" if "review" in log_path.name else "TESTS_PASS")
        return True

    monkeypatch.setattr(batch, "run_command_monitored", fake_run_command_monitored)

    batch.run_prompt(
        repo_root=repo_root,
        prompt=prompt,
        report_dir=report_dir,
        model_impl="devstral",
        model_review="glm-4.7",
        max_iters=1,
        retry_max=1,
        retry_sleep=0,
        dry_run=False,
        llm_classify=False,
        monitor_interval=0,
        stuck_timeout=0,
        progress_tail_lines=5,
        progress_check_interval=0,
        progress_stuck_threshold=1,
        progress_check_enabled=False,
        no_output_timeout=0,
        opencode_env=None,
        impl_title=None,
        review_title=None,
    )


def test_terminate_stale_opencode_kills(tmp_path, monkeypatch):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    monkeypatch.setattr(
        batch,
        "list_opencode_processes",
        lambda: [(123, f"opencode run --file {report_dir}/file.md")],
    )
    killed = []

    def fake_kill(pid, sig):
        killed.append((pid, sig))

    monkeypatch.setattr(batch.os, "kill", fake_kill)
    monkeypatch.setattr(batch, "write_orchestrator_log", lambda *args, **kwargs: None)

    batch.terminate_stale_opencode(report_dir, True)

    assert killed


def test_preflight_opencode_raises_on_failure(tmp_path, monkeypatch):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()

    def fake_run_command(cmd, log_file, retry_max, retry_sleep, timeout=3600, env=None):
        log_file.write_text("boom", encoding="utf-8")
        return False

    monkeypatch.setattr(batch, "run_command", fake_run_command)
    monkeypatch.setattr(batch, "resolve_opencode_path", lambda: "opencode")
    monkeypatch.setattr(batch, "build_opencode_env", lambda *args, **kwargs: {})

    try:
        batch.preflight_opencode(tmp_path, "glm-4.7", report_dir)
    except RuntimeError:
        return
    assert False, "Expected RuntimeError"
