from __future__ import annotations

from pathlib import Path

from orchestro import cli
from orchestro.backends.mock import MockBackend
from orchestro.orchestrator import Orchestro
from orchestro.tui import (
    action_bar_state,
    extract_run_diff,
    format_activity_detail,
    format_activity_line,
    format_activity_nav,
    format_diff_file_list,
    format_diff_patch,
    format_editor_banner,
    format_hero,
    format_integrations_detail,
    format_nav_panel,
    format_review_nav,
    format_approval_detail,
    format_job_detail,
    format_ops_panel,
    format_plan_detail,
    format_review_detail,
    format_run_detail,
    format_runs_panel,
    format_session_detail,
    parse_palette_command,
    rank_palette_matches,
    split_diff_files,
)


def _make_app(tmp_db):
    return Orchestro(db=tmp_db, backends={"mock": MockBackend()})


def test_format_runs_panel_empty():
    text = format_runs_panel([], 0)
    assert "No runs yet." in text


def test_action_bar_state_changes_with_mode():
    sessions = action_bar_state(mode="sessions", editor_visible=False, review_focus="targets")
    assert sessions["btn-approve"] == ("Edit Title", "edit-session-title", True)
    assert sessions["btn-deny"] == ("Edit Summary", "edit-session-summary", True)

    review = action_bar_state(mode="review", editor_visible=False, review_focus="targets")
    assert review["btn-approve"] == ("Focus Files", "toggle-review-focus", True)
    assert review["btn-pause"] == ("Next File", "next-diff-file", True)

    activity = action_bar_state(mode="activity", editor_visible=False, review_focus="targets")
    assert activity["btn-approve"] == ("Refresh", "refresh", True)
    assert activity["btn-cancel"] == ("Jobs", "focus-jobs", True)


def test_action_bar_state_editor_mode_overrides_mode_actions():
    state = action_bar_state(mode="plans", editor_visible=True, review_focus="files")
    assert state["btn-approve"] == ("Save", "save-editor", True)
    assert state["btn-deny"] == ("Close", "close-editor", True)
    assert state["btn-pause"] == ("", None, False)


def test_format_run_detail_without_selection():
    text = format_run_detail(None, [])
    assert "No run selected." in text


def test_format_activity_line_and_detail():
    item = {
        "source": "run:abc",
        "event_type": "tool_called",
        "created_at": "2026-04-13T10:00:00Z",
        "ref_id": "abc",
        "summary": "bash ls -la",
        "payload": {"tool": "bash", "argument": "ls -la"},
    }
    line = format_activity_line(item, selected=True)
    detail = format_activity_detail(item)
    assert "[run:abc" in line
    assert "tool_called" in line
    assert "Activity Stream" in detail
    assert "bash ls -la" in detail


def test_format_activity_nav_renders_items():
    text = format_activity_nav(
        [
            {
                "source": "job:1",
                "event_type": "pause_requested",
                "summary": "paused from tui",
            },
            {
                "source": "plan:1",
                "event_type": "step_selected",
                "summary": "step 2",
            },
        ],
        1,
    )
    assert "[ACTIVITY]" in text
    assert "Recent Activity" in text
    assert "> [plan:1" in text


def test_format_run_detail_includes_output_and_events(tmp_db):
    app = _make_app(tmp_db)
    run_id = app.run(
        cli.RunRequest(
            goal="hello world",
            backend_name="mock",
            working_directory=Path.cwd(),
        )
    )
    run = app.db.get_run(run_id)
    assert run is not None

    text = format_run_detail(run, app.db.list_events(run_id))

    assert "hello world" in text
    assert "output:" in text
    assert "events:" in text


def test_format_ops_panel_shows_defaults(tmp_db):
    app = _make_app(tmp_db)
    text = format_ops_panel(
        statuses=app.backend_statuses(),
        sessions=[],
        plans=[],
        approvals=[],
        jobs=[],
        mode="runs",
        backend="auto",
        model_override="smart-model",
        strategy="direct",
        domain="coding",
        cwd=Path.cwd(),
        autonomous=False,
        busy=True,
    )
    assert "default backend: auto" in text
    assert "default model: smart-model" in text
    assert "busy: yes" in text
    assert "Context Actions:" in text
    assert "enter run goal" in text


def test_format_ops_panel_review_focus_actions(tmp_db):
    app = _make_app(tmp_db)
    text = format_ops_panel(
        statuses=app.backend_statuses(),
        sessions=[],
        plans=[],
        approvals=[],
        jobs=[],
        mode="review",
        backend="auto",
        model_override=None,
        strategy="direct",
        domain="coding",
        cwd=Path.cwd(),
        autonomous=False,
        busy=False,
        review_focus="files",
    )
    assert "tab focus targets" in text
    assert "target <n> select review target" in text
    assert "file <n> select diff file" in text


def test_format_ops_panel_editor_actions(tmp_db):
    app = _make_app(tmp_db)
    text = format_ops_panel(
        statuses=app.backend_statuses(),
        sessions=[],
        plans=[],
        approvals=[],
        jobs=[],
        mode="sessions",
        backend="auto",
        model_override=None,
        strategy="direct",
        domain="coding",
        cwd=Path.cwd(),
        autonomous=False,
        busy=False,
        editor_visible=True,
    )
    assert "ctrl+s save editor" in text
    assert "esc close editor" in text


def test_format_ops_panel_shows_recent_actions(tmp_db):
    app = _make_app(tmp_db)
    text = format_ops_panel(
        statuses=app.backend_statuses(),
        sessions=[],
        plans=[],
        approvals=[],
        jobs=[],
        mode="plans",
        backend="auto",
        model_override=None,
        strategy="direct",
        domain="coding",
        cwd=Path.cwd(),
        autonomous=False,
        busy=False,
        recent_actions=["updated plan step 2 in plan-1", "advanced plan plan-1"],
    )
    assert "Recent Actions:" in text
    assert "updated plan step 2 in plan-1" in text
    assert "advanced plan plan-1" in text


def test_format_ops_panel_shows_transient_status(tmp_db):
    app = _make_app(tmp_db)
    text = format_ops_panel(
        statuses=app.backend_statuses(),
        sessions=[],
        plans=[],
        approvals=[],
        jobs=[],
        mode="approvals",
        backend="auto",
        model_override=None,
        strategy="direct",
        domain="coding",
        cwd=Path.cwd(),
        autonomous=False,
        busy=False,
        status_message="approved bash request",
    )
    assert "Status:" in text
    assert "approved bash request" in text


def test_format_hero_includes_selected_run():
    text = format_hero(
        run_count=3,
        session_count=2,
        plan_count=1,
        mode="runs",
        selected_label="run-123",
        backend="auto",
        model_override="smart-model",
        strategy="direct",
        busy=False,
    )
    assert "selected run-123" in text
    assert "smart-model" in text


def test_parse_palette_command_supports_colon_prefix():
    assert parse_palette_command(":focus approvals") == ("focus", "approvals")
    assert parse_palette_command("approve") == ("approve", None)
    assert parse_palette_command("   ") == ("noop", None)


def test_rank_palette_matches_prefers_strong_matches():
    matches = rank_palette_matches(
        "session alpha",
        [
            ("run:123", "fix bug"),
            ("session:aaa", "Alpha Session"),
            ("plan:bbb", "ship feature"),
        ],
    )
    assert matches[0][0] == "session:aaa"


def test_rank_palette_matches_returns_all_candidates_for_empty_query():
    candidates = [
        ("run:123", "fix bug"),
        ("session:aaa", "Alpha Session"),
    ]
    assert rank_palette_matches("", candidates) == candidates


def test_format_diff_patch_shows_truncation():
    text = format_diff_patch({"text": "line1\nline2", "truncated": True, "original_length": 500}, title="Stored snapshot diff")
    assert "Stored snapshot diff" in text
    assert "line1" in text
    assert "truncated from 500 chars" in text


def test_format_diff_file_list_marks_selected_file():
    text = format_diff_file_list(
        [
            ("a/foo.py b/foo.py", {"text": "diff --git a/foo.py b/foo.py"}),
            ("a/bar.py b/bar.py", {"text": "diff --git a/bar.py b/bar.py"}),
        ],
        1,
    )
    assert "Changed Files" in text
    assert ">  2. a/bar.py b/bar.py" in text
    assert "[ / ] switch diff file" in text


def test_split_diff_files_splits_by_diff_headers():
    sections = split_diff_files(
        {
            "text": "diff --git a/a.py b/a.py\n+print('a')\ndiff --git a/b.py b/b.py\n+print('b')",
            "truncated": False,
            "original_length": 60,
        }
    )
    assert len(sections) == 2
    assert "a/a.py b/a.py" in sections[0][0]
    assert "print('b')" in sections[1][1]["text"]


def test_format_nav_panel_switches_modes(tmp_db):
    app = _make_app(tmp_db)
    run_id = app.run(
        cli.RunRequest(
            goal="hello world",
            backend_name="mock",
            working_directory=Path.cwd(),
        )
    )
    app.db.create_session(session_id="session-1", title="Daily Session")
    app.db.create_plan(
        plan_id="plan-1",
        goal="ship feature",
        backend_name="mock",
        strategy_name="direct",
        working_directory=str(Path.cwd()),
        domain="coding",
        steps=[("step one", None)],
    )

    runs = app.db.list_runs(limit=5)
    sessions = app.db.list_sessions(limit=5)
    plans = app.db.list_plans(limit=5)

    assert run_id == runs[0].id
    assert "[RUNS]" in format_nav_panel(
        mode="runs",
        runs=runs,
        sessions=sessions,
        plans=plans,
        approvals=[],
        jobs=[],
        run_index=0,
        session_index=0,
        plan_index=0,
        approval_index=0,
        job_index=0,
    )
    assert "[SESSIONS]" in format_nav_panel(
        mode="sessions",
        runs=runs,
        sessions=sessions,
        plans=plans,
        approvals=[],
        jobs=[],
        run_index=0,
        session_index=0,
        plan_index=0,
        approval_index=0,
        job_index=0,
    )
    assert "[PLANS]" in format_nav_panel(
        mode="plans",
        runs=runs,
        sessions=sessions,
        plans=plans,
        approvals=[],
        jobs=[],
        run_index=0,
        session_index=0,
        plan_index=0,
        approval_index=0,
        job_index=0,
    )
    assert "[APPROVALS]" in format_nav_panel(
        mode="approvals",
        runs=runs,
        sessions=sessions,
        plans=plans,
        approvals=[],
        jobs=[],
        run_index=0,
        session_index=0,
        plan_index=0,
        approval_index=0,
        job_index=0,
    )
    assert "[REVIEW]" in format_nav_panel(
        mode="review",
        runs=runs,
        sessions=sessions,
        plans=plans,
        approvals=[],
        jobs=[],
        run_index=0,
        session_index=0,
        plan_index=0,
        approval_index=0,
        job_index=0,
    )


def test_format_review_nav_includes_targets_and_diff_files(tmp_db):
    app = _make_app(tmp_db)
    app.db.create_shell_job(
        job_id="job-1",
        goal="review target",
        backend_name="mock",
        strategy_name="direct",
        domain="coding",
    )
    job = app.db.get_shell_job("job-1")
    assert job is not None

    text = format_review_nav(
        jobs=[job],
        job_index=0,
        diff_sections=[
            ("a/foo.py b/foo.py", {"text": "diff --git a/foo.py b/foo.py"}),
            ("a/bar.py b/bar.py", {"text": "diff --git a/bar.py b/bar.py"}),
        ],
        diff_index=1,
    )

    assert "Review Targets" in text
    assert "review target" in text
    assert "Changed Files" in text
    assert ">  2. a/bar.py b/bar.py" in text


def test_format_review_nav_marks_active_focus(tmp_db):
    app = _make_app(tmp_db)
    app.db.create_shell_job(
        job_id="job-1",
        goal="review target",
        backend_name="mock",
        strategy_name="direct",
        domain="coding",
    )
    job = app.db.get_shell_job("job-1")
    assert job is not None

    text = format_review_nav(
        jobs=[job],
        job_index=0,
        diff_sections=[("a/foo.py b/foo.py", {"text": "diff --git a/foo.py b/foo.py"})],
        diff_index=0,
        focus="files",
    )

    assert "[Changed Files]" in text
    assert " Review Targets " in text
    assert "tab switch review focus" in text


def test_format_session_detail_includes_session_runs(tmp_db):
    app = _make_app(tmp_db)
    app.db.create_session(session_id="session-1", title="Daily Session")
    app.run(
        cli.RunRequest(
            goal="hello world",
            backend_name="mock",
            working_directory=Path.cwd(),
            metadata={"session_id": "session-1"},
        )
    )
    session = app.db.get_session("session-1")
    assert session is not None

    text = format_session_detail(session, app.db.list_session_runs("session-1"))

    assert "Session Detail" in text
    assert "Daily Session" in text
    assert "session runs:" in text
    assert "hello world" in text
    assert "session-title <text>" in text


def test_format_plan_detail_includes_steps(tmp_db):
    app = _make_app(tmp_db)
    app.db.create_plan(
        plan_id="plan-1",
        goal="ship feature",
        backend_name="mock",
        strategy_name="direct",
        working_directory=str(Path.cwd()),
        domain="coding",
        steps=[("step one", "detail one"), ("step two", None)],
    )
    plan = app.db.get_plan("plan-1")
    assert plan is not None

    text = format_plan_detail(
        plan,
        app.db.list_plan_steps("plan-1"),
        app.db.list_plan_events("plan-1"),
    )

    assert "Plan Detail" in text
    assert "ship feature" in text
    assert "step one" in text
    assert "current step" in text
    assert "plan-add <title> | <details>" in text


def test_format_approval_detail_includes_tool_and_argument(tmp_db):
    app = _make_app(tmp_db)
    run_id = app.run(
        cli.RunRequest(
            goal="approval seed",
            backend_name="mock",
            working_directory=Path.cwd(),
        )
    )
    app.db.create_approval_request(
        request_id="approval-1",
        job_id=None,
        run_id=run_id,
        tool_name="bash",
        argument="pytest -q",
        pattern="bash:pytest -q",
    )
    approval = app.db.get_approval_request("approval-1")
    assert approval is not None

    text = format_approval_detail(approval)

    assert "Approval Inbox" in text
    assert "bash" in text
    assert "pytest -q" in text


def test_format_job_detail_includes_events_and_inputs(tmp_db):
    app = _make_app(tmp_db)
    app.db.create_shell_job(
        job_id="job-1",
        goal="long task",
        backend_name="mock",
        strategy_name="direct",
        domain="coding",
    )
    app.db.enqueue_shell_job_input(
        input_id="input-1",
        job_id="job-1",
        run_id=None,
        input_text="Please continue carefully.",
    )
    job = app.db.get_shell_job("job-1")
    assert job is not None

    text = format_job_detail(
        job,
        app.db.list_shell_job_events("job-1"),
        app.db.list_shell_job_inputs(job_id="job-1", status="pending"),
    )

    assert "Job Control" in text
    assert "long task" in text
    assert "job_created" in text
    assert "Please continue carefully." in text


def test_format_review_detail_includes_notable_events_and_children(tmp_db):
    app = _make_app(tmp_db)
    run_id = app.run(
        cli.RunRequest(
            goal="hello world",
            backend_name="mock",
            working_directory=Path.cwd(),
        )
    )
    child_id = app.run(
        cli.RunRequest(
            goal="child task",
            backend_name="mock",
            working_directory=Path.cwd(),
            parent_run_id=run_id,
        )
    )
    run = app.db.get_run(run_id)
    assert run is not None
    assert child_id

    text = format_review_detail(
        run,
        app.db.list_events(run_id),
        app.db.list_child_runs(run_id),
    )

    assert "Review Deck" in text
    assert "child runs:" in text
    assert "child task" in text


def test_extract_run_diff_uses_stored_summary_patch(tmp_db):
    app = _make_app(tmp_db)
    run_id = app.run(
        cli.RunRequest(
            goal="diff seed",
            backend_name="mock",
            working_directory=Path.cwd(),
        )
    )
    run = app.db.get_run(run_id)
    assert run is not None
    app.db.update_run_git_snapshot(
        run_id=run_id,
        phase="end",
        snapshot={"ok": True, "changed_files": ["a.py"]},
        summary={
            "end_diff_patch": {"text": "diff --git a/a.py b/a.py\n+print('hi')", "truncated": False, "original_length": 32}
        },
    )
    run = app.db.get_run(run_id)
    assert run is not None

    title, patch = extract_run_diff(run)

    assert title == "Stored snapshot diff"
    assert patch is not None
    assert "print('hi')" in patch["text"]


def test_format_editor_banner_shows_mode_and_target():
    text = format_editor_banner(mode="session-title", context={"session_id": "session-1"})
    assert "Editing session title" in text
    assert "session: session-1" in text
    assert "Ctrl+S saves changes." in text


def test_format_editor_banner_includes_multiline_format_hint():
    text = format_editor_banner(mode="plan-edit-inline", context={"plan_id": "plan-1"})
    assert "Editing current plan step" in text
    assert "first line = title" in text
    assert "remaining lines = details" in text


def test_format_integrations_detail_renders_plugin_mcp_and_lsp():
    text = format_integrations_detail(
        plugin_loaded=[type("Meta", (), {"name": "demo-plugin", "version": "1.2.3"})()],
        plugin_load_errors=[{"plugin": "broken", "error": "import boom"}],
        plugin_hook_errors=[{"hook": "pre_run", "plugin": "demo-plugin", "error": "hook boom"}],
        mcp_status={
            "connected": ["memory"],
            "degraded": ["broken-mcp"],
            "degraded_details": {"broken-mcp": "initialize failed"},
            "tool_count": 2,
        },
        lsp_status={
            "configured": ["pyright"],
            "degraded": ["rust-analyzer"],
            "degraded_details": {"rust-analyzer": "initialize failed"},
            "supported_languages": ["python", "rust"],
        },
    )
    assert "demo-plugin" in text
    assert "broken-mcp" in text
    assert "pyright" in text
    assert "initialize failed" in text


def test_tui_command_launches_via_helper(tmp_db, monkeypatch):
    app = _make_app(tmp_db)
    monkeypatch.setattr(cli, "create_app", lambda: app)
    captured: dict[str, object] = {}

    def fake_launch(app_arg, **kwargs):
        captured["app"] = app_arg
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(cli, "_launch_tui", fake_launch)

    exit_code = cli.main(["tui", "--backend", "mock", "--cwd", str(Path.cwd())])

    assert exit_code == 0
    assert captured["app"] is app
    assert captured["backend"] == "mock"
    assert captured["strategy"] == "direct"


def test_tui_command_uses_model_alias(tmp_db, monkeypatch):
    app = _make_app(tmp_db)
    monkeypatch.setattr(cli, "create_app", lambda: app)
    monkeypatch.setattr(cli, "resolve_alias", lambda alias, backends: ("mock", "special-model"))
    captured: dict[str, object] = {}

    def fake_launch(app_arg, **kwargs):
        captured["app"] = app_arg
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(cli, "_launch_tui", fake_launch)

    exit_code = cli.main(["tui", "--model", "smart", "--cwd", str(Path.cwd())])

    assert exit_code == 0
    assert captured["backend"] == "mock"
    assert captured["model_override"] == "special-model"
