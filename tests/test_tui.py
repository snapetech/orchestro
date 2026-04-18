from __future__ import annotations

from pathlib import Path

from orchestro import cli
from orchestro.backends.mock import MockBackend
from orchestro.orchestrator import Orchestro
from orchestro.tui import (
    WorkspaceSurface,
    composer_placeholder,
    compose_workspace,
    derive_primary_mode,
    extract_run_diff,
    format_checklist,
    format_signal_meter,
    format_agent_loop,
    format_activity_detail,
    format_activity_line,
    format_activity_nav,
    format_act_widgets,
    format_act_workspace,
    format_card,
    format_chat_widgets,
    format_chat_workspace,
    format_diff_file_list,
    format_diff_patch,
    format_editor_banner,
    format_hero,
    format_help_overlay,
    format_integrations_detail,
    format_left_rail,
    format_metric_bar,
    format_mode_guide,
    format_mission_strip,
    format_command_meta,
    format_ops_widgets,
    format_plan_lane,
    format_plan_widgets,
    format_file_tree,
    format_review_widgets,
    format_timeline,
    format_workspace_bar,
    workspace_tray_state,
    contextual_selector_state,
    workspace_controls_state,
    workspace_switcher_state,
    format_nav_panel,
    format_review_nav,
    format_approval_detail,
    format_job_detail,
    format_ops_panel,
    format_ops_workspace,
    format_plan_workspace,
    format_plan_detail,
    format_review_detail,
    format_review_workspace,
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


def test_format_card_and_workspace_compose_cleanly():
    text = compose_workspace(
        [
            format_card("Goal", ["Ship the refactor"]),
            format_card("Trace", ["- tool_called", "- tool_result"]),
        ]
    )
    assert "[ GOAL ]" in text
    assert "[ TRACE ]" in text


def test_workspace_surface_holds_detail_and_panes():
    surface = WorkspaceSurface(primary_mode="Review", detail="main", panes=("a", "b", "c", "d"))
    assert surface.primary_mode == "Review"
    assert surface.detail == "main"
    assert surface.panes[2] == "c"


def test_composer_placeholder_changes_with_mode():
    assert "Act mode" in composer_placeholder("runs", "Act")
    assert "Review mode" in composer_placeholder("review", "Review")
    assert "Plan mode" in composer_placeholder("plans", "Plan")
    assert "Ops mode" in composer_placeholder("activity", "Ops")


def test_metric_bar_and_plan_lane_render_cleanly():
    assert "done" in format_metric_bar("done", 2, 4)
    lane = format_plan_lane("Active", ["1. step one"])
    assert lane[0] == "Active"
    assert "- 1. step one" in lane[1]


def test_file_tree_and_timeline_render_cleanly():
    tree = format_file_tree(["a/src/main.py b/src/main.py", "a/tests/test_app.py b/tests/test_app.py"], selected_index=1)
    assert "src/" in tree[0] or "tests/" in "\n".join(tree)
    assert ">  2." in "\n".join(tree)
    timeline = format_timeline("Latest", ["tool_called: bash", "tool_result: ok"])
    assert timeline[0] == "Latest"
    assert "* tool_called: bash" in timeline[1]


def test_checklist_renders_state_markers():
    lines = format_checklist("Checks", [("loaded", True), ("pending", False)])
    text = "\n".join(lines)
    assert "Checks" in text
    assert "[x] loaded" in text
    assert "[ ] pending" in text


def test_signal_meter_renders_progress_bar():
    text = format_signal_meter("health", 3, 5)
    assert "health" in text
    assert "[######" in text or "[#####." in text
    assert "3/5" in text


def test_widget_formatters_render_structured_workspace_feeds():
    review_a, review_b, review_c, review_d = format_review_widgets(
        diff_sections=[("a/src/main.py b/src/main.py", {"text": "diff --git a/src/main.py b/src/main.py"})],
        selected_diff_index=0,
        events=[{"event_type": "tool_called", "payload": {"tool": "bash"}}],
    )
    assert "Review Status" in review_a
    assert "evidence" in review_a
    assert "risk" in review_a
    assert "Changed Files" in review_b
    assert "Evidence" in review_c
    assert "selected file: a/src/main.py b/src/main.py" in review_c
    assert "file index: 1/1" in review_c
    assert "move: wc-2 / wc-3 or prev-target / next-target" in review_c
    assert "Review Checklist" in review_c
    assert "Review Timeline" in review_d

    step = type("Step", (), {"sequence_no": 1, "title": "Implement", "details": "write the feature", "status": "pending"})()
    plan_a, plan_b, plan_c, plan_d = format_plan_widgets(steps=[step], current_step_no=1)
    assert "Plan Status" in plan_a
    assert "done" in plan_a
    assert "active" in plan_a
    assert "Plan Board" in plan_b
    assert "Progress Bars" in plan_c
    assert "selected step: 1" in plan_c
    assert "title: Implement" in plan_c
    assert "details: write the feature" in plan_c
    assert "move: wc-1 / wc-2 or prev-step / next-step" in plan_c
    assert "Plan Checklist" in plan_c
    assert "Next Moves" in plan_d

    event = type("Event", (), {"event_type": "tool_called", "payload": {"tool": "bash"}})()
    ops_a, ops_b, ops_c, ops_d = format_ops_widgets(
        mode="jobs",
        job_events=[event],
        job_inputs=[],
        recent_actions=["completed check"],
        status_message="running",
    )
    assert "Ops Status" in ops_a
    assert "events" in ops_a
    assert "inputs" in ops_a
    assert "Mission Feed" in ops_b
    assert "Gates" in ops_c
    assert "controls: workspace controls drive the active ops deck" in ops_c
    assert "Ops Checklist" in ops_c
    assert "Operator Feed" in ops_d

    chat_a, chat_b, chat_c, chat_d = format_chat_widgets(
        run=None,
        events=[],
        recent_actions=["ran repo summary"],
        status_message="ready",
    )
    assert "Chat Status" in chat_a
    assert "context" in chat_a
    assert "momentum" in chat_a
    assert "Conversation Context" in chat_b
    assert "Loaded Context" in chat_c
    assert "Context Checklist" in chat_c
    assert "Suggested Next Moves" in chat_d
    assert "controls: workspace switcher changes deck" in chat_d

    act_a, act_b, act_c, act_d = format_act_widgets(
        run=None,
        events=[{"event_type": "tool_called", "payload": {"tool": "bash"}}],
        diff_sections=[("a/app.py b/app.py", {"text": "diff --git a/app.py b/app.py"})],
        selected_diff_index=0,
        live_output="stream line one\nstream line two",
    )
    assert "Act Status" in act_a
    assert "trace" in act_a
    assert "files" in act_a
    assert "Execution Timeline" in act_b
    assert "tool calls: 1" in act_b
    assert "Touched Files" in act_c
    assert "selected file: a/app.py b/app.py" in act_c
    assert "Result Stream" in act_d
    assert "Execution Checklist" in act_d


def test_format_agent_loop_tracks_mode_and_metrics():
    lines = format_agent_loop(
        primary_mode="Act",
        busy=True,
        approvals=2,
        jobs=1,
        reroutes=1,
        retries=3,
        tools=4,
        status_message="running tests",
    )
    text = "\n".join(lines)
    assert "Think -> Inspect -> Edit -> Verify" in text
    assert "approvals 2" in text
    assert "reroutes 1" in text
    assert "latest: running tests" in text


def test_workspace_bar_and_command_meta_render_operator_context():
    workspace = format_workspace_bar(
        primary_mode="Review",
        view_mode="review",
        selected_label="job-1",
        review_focus="files",
        selected_file="a/src/main.py b/src/main.py",
        busy=False,
        autonomous=True,
        tray_focus="b",
        tray_expanded=True,
    )
    assert "[ REVIEW ]" in workspace
    assert "selected job-1" in workspace
    assert "review-focus files" in workspace
    assert "tray B:max" in workspace
    assert "control auto" in workspace

    command = format_command_meta(
        backend="auto",
        model_override="gpt-5.4",
        strategy="direct",
        domain="coding",
        providers=["instructions", "lexical", "semantic"],
        autonomous=False,
        primary_mode="Act",
        nav_visible=True,
        ops_visible=False,
        tray_focus="c",
        tray_expanded=False,
    )
    assert "compose on act" in command
    assert "backend auto" in command
    assert "providers instructions, lexical, semantic" in command
    assert "layout nav:on ops:off" in command
    assert "tray c:grid" in command

    guide = format_mode_guide(
        primary_mode="Plan",
        view_mode="plans",
        editor_visible=False,
        review_focus="targets",
        busy=False,
        selected_label="plan-1",
        status_message=None,
        tray_focus="a",
        tray_expanded=False,
    )
    assert "Plan / plans | selected plan-1 | status ready | tray A grid" in guide
    assert "Use Prev Step / Next Step" in guide


def test_help_overlay_renders_mode_and_layout_guidance():
    text = format_help_overlay(
        primary_mode="Review",
        view_mode="review",
        review_focus="files",
        nav_visible=False,
        ops_visible=True,
        tray_focus="d",
        tray_expanded=True,
    )
    assert "[ QUICK HELP ]" in text
    assert "Current Mode: Review / review" in text
    assert "tray focus: D (max)" in text
    assert "review focus: files" in text
    assert "left rail: hidden" in text
    assert "ops dock:  visible" in text


def test_workspace_switcher_state_marks_active_workspace():
    state = workspace_switcher_state("review")
    assert state["ws-review"] == ("Review", "focus-review", True)
    assert state["ws-runs"] == ("Runs", "focus-runs", False)
    assert state["ws-activity"] == ("Activity", "focus-activity", False)


def test_workspace_tray_state_marks_active_pane_and_mode():
    state = workspace_tray_state(
        ["Review Status", "Changed Files", "Evidence", "Review Timeline"],
        focus="c",
        expanded=True,
    )
    assert state["tp-c"] == ("Evidence", "focus-tray:c", True, True)
    assert state["tp-max"] == ("Overview", "toggle-tray-max", True, True)


def test_contextual_selector_state_tracks_mode_specific_targets():
    run = type("Run", (), {"goal": "hello repo", "id": "run-1"})()
    state = contextual_selector_state(
        mode="runs",
        review_focus="targets",
        integration_focus=None,
        runs=[run],
        run_index=0,
        sessions=[],
        session_index=0,
        plans=[],
        plan_index=0,
        plan_steps=[],
        approvals=[],
        approval_index=0,
        jobs=[],
        job_index=0,
        activity_items=[],
        activity_index=0,
        diff_sections=[],
        diff_index=0,
        integration_options=[],
    )
    assert state["sel-1"] == ("hello repo", "select-run:0", True)

    step = type("Step", (), {"sequence_no": 2, "title": "Implement"})()
    plan = type("Plan", (), {"current_step_no": 2})()
    state = contextual_selector_state(
        mode="plans",
        review_focus="targets",
        integration_focus=None,
        runs=[],
        run_index=0,
        sessions=[],
        session_index=0,
        plans=[plan],
        plan_index=0,
        plan_steps=[step],
        approvals=[],
        approval_index=0,
        jobs=[],
        job_index=0,
        activity_items=[],
        activity_index=0,
        diff_sections=[],
        diff_index=0,
        integration_options=[],
    )
    assert state["sel-1"] == ("2. Implement", "select-plan-step:2", True)

    review_job = type("Job", (), {"goal": "review this", "status": "running", "id": "job-1"})()
    state = contextual_selector_state(
        mode="review",
        review_focus="files",
        integration_focus=None,
        runs=[],
        run_index=0,
        sessions=[],
        session_index=0,
        plans=[],
        plan_index=0,
        plan_steps=[],
        approvals=[],
        approval_index=0,
        jobs=[review_job],
        job_index=0,
        activity_items=[],
        activity_index=0,
        diff_sections=[("a/app.py b/app.py", {"text": "diff --git a/app.py b/app.py"})],
        diff_index=0,
        integration_options=[],
    )
    assert state["sel-1"] == ("a/app.py b/app.py", "select-review-file:1", True)

    state = contextual_selector_state(
        mode="integrations",
        review_focus="files",
        integration_focus="mcp",
        runs=[],
        run_index=0,
        sessions=[],
        session_index=0,
        plans=[],
        plan_index=0,
        plan_steps=[],
        approvals=[],
        approval_index=0,
        jobs=[],
        job_index=0,
        activity_items=[],
        activity_index=0,
        diff_sections=[],
        diff_index=0,
        integration_options=[("Plugins", "plugins"), ("MCP", "mcp"), ("LSP", "lsp")],
    )
    assert state["sel-2"] == ("MCP", "select-integration:mcp", True)


def test_workspace_controls_state_changes_with_mode():
    review = workspace_controls_state(mode="review", editor_visible=False, review_focus="targets")
    assert review["wc-1"] == ("Focus Files", "toggle-review-focus", True)
    assert review["wc-2"] == ("Prev Target", "review-prev", True)
    assert review["wc-3"] == ("Next Target", "review-next", True)
    assert review["wc-5"] == ("Palette", "toggle-palette", True)

    plans = workspace_controls_state(mode="plans", editor_visible=False, review_focus="targets")
    assert plans["wc-1"] == ("Prev Step", "prev-plan-step", True)
    assert plans["wc-2"] == ("Next Step", "next-plan-step", True)
    assert plans["wc-3"] == ("Advance", "advance-plan", True)
    assert plans["wc-4"] == ("Add Step", "add-plan-step", True)

    editor = workspace_controls_state(mode="plans", editor_visible=True, review_focus="files")
    assert editor["wc-1"] == ("Save", "save-editor", True)
    assert editor["wc-2"] == ("Close", "close-editor", True)


def test_derive_primary_mode_maps_workspace_modes():
    assert derive_primary_mode("runs") == "Chat"
    assert derive_primary_mode("runs", busy=True) == "Act"
    assert derive_primary_mode("plans") == "Plan"
    assert derive_primary_mode("review") == "Review"
    assert derive_primary_mode("activity") == "Ops"


def test_format_run_detail_without_selection():
    text = format_run_detail(None, [])
    assert "No run selected." in text


def test_format_chat_workspace_groups_goal_response_and_events(tmp_db):
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
    text = format_chat_workspace(run=run, events=app.db.list_events(run_id), live_output=None)
    assert "[ AGENT LOOP ]" in text
    assert "[ GOAL ]" in text
    assert "[ RESPONSE ]" in text
    assert "[ RECENT EVENTS ]" in text


def test_format_act_workspace_groups_trace_and_output(tmp_db):
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
    text = format_act_workspace(run=run, events=app.db.list_events(run_id), live_output="streamed")
    assert "[ AGENT LOOP ]" in text
    assert "[ MISSION ]" in text
    assert "[ EXECUTION TRACE ]" in text
    assert "[ LIVE OUTPUT ]" in text


def test_format_plan_workspace_groups_goal_step_board_and_history(tmp_db):
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
    text = format_plan_workspace(plan, app.db.list_plan_steps("plan-1"), app.db.list_plan_events("plan-1"))
    assert "[ AGENT LOOP ]" in text
    assert "[ PLAN GOAL ]" in text
    assert "[ PROGRESS ]" in text
    assert "[ CURRENT STEP ]" in text
    assert "[ STEP BOARD ]" in text
    assert "[ BOARD VIEW ]" in text
    assert "[ NEXT MOVES ]" in text
    assert "[ PLAN HISTORY ]" in text
    assert "[########........]" in text or "[####" in text


def test_format_review_workspace_groups_summary_files_and_patch():
    text = format_review_workspace(
        run=object(),
        review_text="Review Deck\n\nstatus: done\n\nnotable events:\n  - tool_called: {'tool': 'bash'}\n\nchild runs:\n  - child run one",
        diff_file_text="Changed Files\n\n> 1. a.py",
        diff_patch_text="Diff\n\n+print('hi')",
        diff_sections=[("a.py", {"text": "diff --git a.py"})],
        selected_diff_index=0,
        events=[{"event_type": "tool_called", "payload": {"tool": "bash"}}],
    )
    assert "[ AGENT LOOP ]" in text
    assert "[ REVIEW SUMMARY ]" in text
    assert "[ EVIDENCE ]" in text
    assert "[ NAVIGATOR ]" in text
    assert "[ FINDINGS ]" in text
    assert "[ PATCH STATS ]" in text
    assert "[ CHANGED FILES ]" in text
    assert "[ PATCH ]" in text
    assert "[ RELATED RUNS ]" in text


def test_format_ops_workspace_uses_mode_specific_card(tmp_db):
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
    text = format_ops_workspace(
        mode="approvals",
        approval=approval,
        job=None,
        integrations_text=None,
        activity=None,
        job_events=[],
        job_inputs=[],
        recent_actions=[],
        status_message=None,
    )
    assert "[ AGENT LOOP ]" in text
    assert "[ APPROVAL QUEUE ]" in text
    assert "[ DECISION ]" in text
    assert "pytest -q" in text


def test_format_ops_workspace_jobs_uses_loop_console(tmp_db):
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
        input_text="continue with caution",
    )
    job = app.db.get_shell_job("job-1")
    assert job is not None
    text = format_ops_workspace(
        mode="jobs",
        approval=None,
        job=job,
        integrations_text=None,
        activity=None,
        job_events=app.db.list_shell_job_events("job-1"),
        job_inputs=app.db.list_shell_job_inputs(job_id="job-1", status="pending"),
        recent_actions=["pause requested for job job-1"],
        status_message="paused from tui",
    )
    assert "[ AGENT LOOP ]" in text
    assert "[ MISSION CONTROL ]" in text
    assert "[ LOOP CONSOLE ]" in text
    assert "[ AUTONOMY STATE ]" in text
    assert "[ LOOP TIMELINE ]" in text
    assert "[ RECENT JOB EVENTS ]" in text
    assert "[ OPERATOR INPUTS ]" in text


def test_format_mission_strip_includes_mode_and_status():
    text = format_mission_strip(
        primary_mode="Act",
        workspace_mode="runs",
        objective="Refactor the parser and rerun tests",
        backend="auto",
        model_override="gpt-5.4",
        strategy="direct",
        busy=True,
        autonomous=True,
        selected_label="run-123",
        approval_count=2,
        job_count=3,
        recent_status="running tests",
    )
    assert "Mission" in text
    assert "Act / RUNS" in text
    assert "Backend  auto" in text
    assert "Status  running tests" in text


def test_format_left_rail_groups_navigation_and_focus(tmp_db):
    app = _make_app(tmp_db)
    run_id = app.run(
        cli.RunRequest(
            goal="hello world",
            backend_name="mock",
            working_directory=Path.cwd(),
        )
    )
    runs = app.db.list_runs(limit=5)
    assert run_id == runs[0].id
    text = format_left_rail(
        view_mode="runs",
        primary_mode="Chat",
        runs=runs,
        sessions=[],
        plans=[],
        approvals=[],
        jobs=[],
        activity_items=[],
        statuses=app.backend_statuses(),
        run_index=0,
        session_index=0,
        plan_index=0,
        approval_index=0,
        job_index=0,
        activity_index=0,
        diff_sections=[],
        diff_index=0,
        review_focus="targets",
    )
    assert "ORCHESTRO" in text
    assert "Focus" in text
    assert "mode Chat" in text
    assert "deck runs" in text
    assert "Alerts" in text
    assert "Selection" in text


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
    assert "[ CONTROL ]" in text
    assert "[ BACKEND RADAR ]" in text
    assert "[ QUEUES ]" in text
    assert "backend: auto" in text
    assert "model: smart-model" in text
    assert "busy: yes" in text
    assert "[ CONTEXT ACTIONS ]" not in text


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
    assert "[ CONTEXT ACTIONS ]" not in text
    assert "[ BACKEND RADAR ]" in text


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
    assert "[ CONTEXT ACTIONS ]" not in text
    assert "[ CONTROL ]" in text


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
    assert "[ RECENT ACTIONS ]" in text
    assert "[ RECENT ACTIONS ]" in text
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
    assert "[ STATUS ]" in text
    assert "[ STATUS ]" in text
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
        focus="mcp",
    )
    assert "focus: mcp" in text
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
