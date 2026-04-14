from __future__ import annotations

import difflib
import threading
import time
from pathlib import Path

from orchestro.cli import DEFAULT_CONTEXT_PROVIDERS
from orchestro.git_changes import collect_git_changes
from orchestro.models import RunRequest
from orchestro.orchestrator import Orchestro


def _clip(text: str | None, limit: int) -> str:
    value = (text or "").strip().replace("\n", " ")
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def format_run_line(run: object, *, selected: bool = False) -> str:
    marker = ">" if selected else " "
    status = getattr(run, "status", "?")
    backend = getattr(run, "backend_name", "?")
    goal = _clip(getattr(run, "goal", ""), 52) or "-"
    return f"{marker} [{status:<9}] {backend:<14} {goal}"


def format_session_line(session: object, *, selected: bool = False) -> str:
    marker = ">" if selected else " "
    status = getattr(session, "status", "?")
    title = _clip(getattr(session, "title", None) or getattr(session, "id", "?"), 46)
    return f"{marker} [{status:<9}] {title}"


def format_plan_line(plan: object, *, selected: bool = False) -> str:
    marker = ">" if selected else " "
    status = getattr(plan, "status", "?")
    step = getattr(plan, "current_step_no", "?")
    goal = _clip(getattr(plan, "goal", ""), 42) or getattr(plan, "id", "?")
    return f"{marker} [{status:<9}] step {step:<3} {goal}"


def format_approval_line(approval: object, *, selected: bool = False) -> str:
    marker = ">" if selected else " "
    status = getattr(approval, "status", "?")
    tool = _clip(getattr(approval, "tool_name", "?"), 18)
    argument = _clip(getattr(approval, "argument", ""), 30)
    return f"{marker} [{status:<9}] {tool:<18} {argument}"


def format_job_line(job: object, *, selected: bool = False) -> str:
    marker = ">" if selected else " "
    status = getattr(job, "status", "?")
    control = getattr(job, "control_state", "?")
    goal = _clip(getattr(job, "goal", ""), 34)
    return f"{marker} [{status:<9}] ({control}) {goal}"


def format_activity_line(item: dict[str, object], *, selected: bool = False) -> str:
    marker = ">" if selected else " "
    source = _clip(str(item.get("source", "?")), 12)
    kind = _clip(str(item.get("event_type", "?")), 20)
    summary = _clip(str(item.get("summary", "")), 48)
    return f"{marker} [{source:<12}] {kind:<20} {summary}"


def format_nav_panel(
    *,
    mode: str,
    runs: list[object],
    sessions: list[object],
    plans: list[object],
    approvals: list[object],
    jobs: list[object],
    run_index: int,
    session_index: int,
    plan_index: int,
    approval_index: int,
    job_index: int,
) -> str:
    labels = {
        "runs": ("[RUNS]", " sessions ", " plans ", " approvals ", " jobs ", " review ", " integrations ", " activity "),
        "sessions": (" runs ", "[SESSIONS]", " plans ", " approvals ", " jobs ", " review ", " integrations ", " activity "),
        "plans": (" runs ", " sessions ", "[PLANS]", " approvals ", " jobs ", " review ", " integrations ", " activity "),
        "approvals": (" runs ", " sessions ", " plans ", "[APPROVALS]", " jobs ", " review ", " integrations ", " activity "),
        "jobs": (" runs ", " sessions ", " plans ", " approvals ", "[JOBS]", " review ", " integrations ", " activity "),
        "review": (" runs ", " sessions ", " plans ", " approvals ", " jobs ", "[REVIEW]", " integrations ", " activity "),
        "integrations": (" runs ", " sessions ", " plans ", " approvals ", " jobs ", " review ", "[INTEGRATIONS]", " activity "),
        "activity": (" runs ", " sessions ", " plans ", " approvals ", " jobs ", " review ", " integrations ", "[ACTIVITY]"),
    }
    tab_runs, tab_sessions, tab_plans, tab_approvals, tab_jobs, tab_review, tab_integrations, tab_activity = labels.get(mode, labels["runs"])
    lines = [
        f"{tab_runs}  {tab_sessions}  {tab_plans}",
        f"{tab_approvals}  {tab_jobs}  {tab_review}",
        f"{tab_integrations}  {tab_activity}",
        "",
    ]
    if mode == "runs":
        if not runs:
            lines.extend(["No runs yet.", "Submit a prompt below to start."])
        else:
            lines.extend(format_run_line(run, selected=index == run_index) for index, run in enumerate(runs))
    elif mode == "sessions":
        if not sessions:
            lines.extend(["No sessions yet.", "Create or accumulate one from shell/API flows."])
        else:
            lines.extend(
                format_session_line(session, selected=index == session_index)
                for index, session in enumerate(sessions)
            )
    elif mode == "plans":
        if not plans:
            lines.extend(["No plans yet.", "Create one with the CLI or API plan flows."])
        else:
            lines.extend(format_plan_line(plan, selected=index == plan_index) for index, plan in enumerate(plans))
    elif mode == "approvals":
        if not approvals:
            lines.extend(["No pending approvals.", "Approval prompts will appear here."])
        else:
            lines.extend(
                format_approval_line(approval, selected=index == approval_index)
                for index, approval in enumerate(approvals)
            )
    elif mode in {"jobs", "review"}:
        source_jobs = jobs if mode == "jobs" else [
            job for job in jobs if getattr(job, "status", "") in {"running", "paused", "failed", "cancel_requested"}
        ]
        if not source_jobs:
            lines.extend(["No shell jobs.", "Background and approval-gated jobs appear here."])
        else:
            lines.extend(
                format_job_line(job, selected=index == job_index)
                for index, job in enumerate(source_jobs)
            )
    else:
        lines.extend(
            [
                "Integration Deck",
                "",
                "Inspect plugin, MCP, and LSP status here.",
                "Use the detail pane for degraded details.",
            ]
        )
    return "\n".join(lines)


def format_activity_nav(items: list[dict[str, object]], selected_index: int) -> str:
    lines = ["[ACTIVITY]", "", "Recent Activity", ""]
    if not items:
        lines.extend(["No activity yet.", "Run tasks or use plans/jobs to populate the stream."])
    else:
        lines.extend(
            format_activity_line(item, selected=index == selected_index)
            for index, item in enumerate(items[:24])
        )
    lines.extend(["", "Keys:", "  j/k move activity selection"])
    return "\n".join(lines)


def format_review_nav(
    *,
    jobs: list[object],
    job_index: int,
    diff_sections: list[tuple[str, dict[str, object]]],
    diff_index: int,
    focus: str = "targets",
) -> str:
    target_label = "[Review Targets]" if focus == "targets" else " Review Targets "
    file_label = "[Changed Files]" if focus == "files" else " Changed Files "
    lines = ["[REVIEW]", "", f"{target_label}", ""]
    review_jobs = [
        job for job in jobs if getattr(job, "status", "") in {"running", "paused", "failed", "cancel_requested"}
    ]
    if not review_jobs:
        lines.extend(["No review targets.", "Background and approval-gated jobs appear here."])
    else:
        lines.extend(
            format_job_line(job, selected=index == job_index)
            for index, job in enumerate(review_jobs)
        )
    lines.extend(["", f"{file_label}", ""])
    if not diff_sections:
        lines.append("No diff files available.")
    else:
        for index, (label, _patch) in enumerate(diff_sections):
            marker = ">" if index == diff_index else " "
            lines.append(f"{marker} {index + 1:>2}. {_clip(label, 40)}")
    lines.extend(["", "Keys:", "  tab switch review focus", "  j/k move current review pane", "  [ / ] switch diff file"])
    return "\n".join(lines)


def format_runs_panel(runs: list[object], selected_index: int) -> str:
    lines = ["Runs", ""]
    if not runs:
        lines.append("No runs yet.")
        lines.append("Submit a prompt below to start.")
        return "\n".join(lines)
    for index, run in enumerate(runs):
        lines.append(format_run_line(run, selected=index == selected_index))
    return "\n".join(lines)


def format_session_detail(session: object | None, runs: list[object]) -> str:
    if session is None:
        return "\n".join(
            [
                "Session Detail",
                "",
                "No session selected.",
                "Press 2 to switch to the session navigator.",
            ]
        )
    lines = [
        "Session Detail",
        "",
        f"id: {getattr(session, 'id', '-')}",
        f"title: {getattr(session, 'title', None) or '-'}",
        f"status: {getattr(session, 'status', '-')}",
        f"parent: {getattr(session, 'parent_session_id', None) or '-'}",
        f"fork run: {getattr(session, 'fork_point_run_id', None) or '-'}",
        f"updated: {getattr(session, 'updated_at', '-')}",
        "",
    ]
    if getattr(session, "summary", None):
        lines.extend(["summary:", str(getattr(session, "summary")), ""])
    if getattr(session, "context_snapshot", None):
        lines.extend(["context snapshot:", str(getattr(session, "context_snapshot")), ""])
    lines.append("session runs:")
    if not runs:
        lines.append("  (none)")
    else:
        for run in runs[-8:]:
            lines.append(
                f"  - [{getattr(run, 'status', '?')}] {getattr(run, 'backend_name', '?')}: {_clip(getattr(run, 'goal', ''), 70)}"
            )
    lines.extend(
        [
            "",
            "Palette actions:",
            "  session-title <text>",
            "  session-summary <text>",
            "  archive-session",
            "  activate-session",
        ]
    )
    return "\n".join(lines)


def format_plan_detail(plan: object | None, steps: list[object], events: list[object]) -> str:
    if plan is None:
        return "\n".join(
            [
                "Plan Detail",
                "",
                "No plan selected.",
                "Press 3 to switch to the plan navigator.",
            ]
        )
    lines = [
        "Plan Detail",
        "",
        f"id: {getattr(plan, 'id', '-')}",
        f"status: {getattr(plan, 'status', '-')}",
        f"backend: {getattr(plan, 'backend_name', '-')}",
        f"strategy: {getattr(plan, 'strategy_name', '-')}",
        f"current step: {getattr(plan, 'current_step_no', '-')}",
        f"domain: {getattr(plan, 'domain', None) or '-'}",
        f"updated: {getattr(plan, 'updated_at', '-')}",
        "",
        "goal:",
        getattr(plan, "goal", "") or "-",
        "",
        "steps:",
    ]
    if not steps:
        lines.append("  (none)")
    else:
        for step in steps[:12]:
            marker = ">" if getattr(step, "sequence_no", None) == getattr(plan, "current_step_no", None) else " "
            lines.append(
                f"  {marker} {getattr(step, 'sequence_no', '?'):>2}. [{getattr(step, 'status', '?')}] {getattr(step, 'title', '-')}"
            )
            if getattr(step, "details", None):
                lines.append(f"     {_clip(getattr(step, 'details'), 90)}")
    lines.extend(["", "plan events:"])
    if not events:
        lines.append("  (none)")
    else:
        for event in events[-6:]:
            lines.append(
                f"  - {getattr(event, 'event_type', '?')}: {_clip(str(getattr(event, 'payload', {})), 100)}"
            )
    lines.extend(
        [
            "",
            "Palette actions:",
            "  plan-add <title> | <details>",
            "  plan-edit <seq> | <title> | <details>",
            "  plan-drop <seq>",
            "  advance-plan",
            "  block-plan",
        ]
    )
    return "\n".join(lines)


def format_approval_detail(approval: object | None) -> str:
    if approval is None:
        return "\n".join(
            [
                "Approval Inbox",
                "",
                "No approval selected.",
                "Press 4 to switch to approvals.",
            ]
        )
    return "\n".join(
        [
            "Approval Inbox",
            "",
            f"id: {getattr(approval, 'id', '-')}",
            f"status: {getattr(approval, 'status', '-')}",
            f"tool: {getattr(approval, 'tool_name', '-')}",
            f"run: {getattr(approval, 'run_id', None) or '-'}",
            f"job: {getattr(approval, 'job_id', None) or '-'}",
            f"created: {getattr(approval, 'created_at', '-')}",
            "",
            "argument:",
            getattr(approval, "argument", "") or "-",
            "",
            f"pattern: {getattr(approval, 'pattern', '-')}",
            "",
            "Palette actions:",
            "  approve",
            "  deny",
        ]
    )


def format_job_detail(job: object | None, events: list[object], inputs: list[object]) -> str:
    if job is None:
        return "\n".join(
            [
                "Job Control",
                "",
                "No job selected.",
                "Press 5 to switch to jobs.",
            ]
        )
    lines = [
        "Job Control",
        "",
        f"id: {getattr(job, 'id', '-')}",
        f"status: {getattr(job, 'status', '-')}",
        f"control: {getattr(job, 'control_state', '-')}",
        f"backend: {getattr(job, 'backend_name', '-')}",
        f"strategy: {getattr(job, 'strategy_name', '-')}",
        f"run: {getattr(job, 'run_id', None) or '-'}",
        f"updated: {getattr(job, 'updated_at', '-')}",
        "",
        "goal:",
        getattr(job, "goal", "") or "-",
        "",
        "recent events:",
    ]
    if not events:
        lines.append("  (none)")
    else:
        for event in events[-6:]:
            lines.append(f"  - {getattr(event, 'event_type', '?')}: {_clip(str(getattr(event, 'payload', {})), 96)}")
    lines.extend(["", "pending inputs:"])
    if not inputs:
        lines.append("  (none)")
    else:
        for item in inputs[:6]:
            lines.append(f"  - {_clip(getattr(item, 'input_text', ''), 96)}")
    lines.extend(
        [
            "",
            "Palette actions:",
            "  pause",
            "  resume",
            "  cancel",
        ]
    )
    return "\n".join(lines)


def format_review_detail(run: object | None, events: list[dict[str, object]], child_runs: list[object]) -> str:
    if run is None:
        return "\n".join(
            [
                "Review Deck",
                "",
                "No run selected.",
                "Press 6 to switch to review.",
            ]
        )
    lines = [
        "Review Deck",
        "",
        f"id: {getattr(run, 'id', '-')}",
        f"status: {getattr(run, 'status', '-')}",
        f"backend: {getattr(run, 'backend_name', '-')}",
        f"strategy: {getattr(run, 'strategy_name', '-')}",
        f"tokens: {getattr(run, 'total_tokens', 0)}",
        f"quality: {getattr(run, 'quality_level', '-')}",
        "",
    ]
    summary = getattr(run, "git_change_summary", None)
    if summary:
        lines.extend(["git change summary:", _clip(str(summary), 120), ""])
    lines.append("notable events:")
    notable = [event for event in events if event["event_type"] in {
        "tool_called",
        "tool_result",
        "approval_requested",
        "backend_auto_rerouted",
        "retry_scheduled",
        "plan_step_selected",
    }]
    if not notable:
        lines.append("  (none)")
    else:
        for event in notable[-10:]:
            lines.append(f"  - {event['event_type']}: {_clip(str(event.get('payload', {})), 100)}")
    lines.extend(["", "child runs:"])
    if not child_runs:
        lines.append("  (none)")
    else:
        for child in child_runs[:8]:
            lines.append(
                f"  - [{getattr(child, 'status', '?')}] {getattr(child, 'backend_name', '?')}: {_clip(getattr(child, 'goal', ''), 72)}"
            )
    return "\n".join(lines)


def format_diff_patch(patch: dict[str, object] | None, *, title: str = "Diff") -> str:
    if not patch:
        return f"{title}\n\nNo diff available."
    text = str(patch.get("text") or "").strip("\n")
    if not text:
        return f"{title}\n\nNo diff available."
    lines = [title, ""]
    snippet = text.splitlines()[:60]
    lines.extend(snippet)
    if patch.get("truncated"):
        lines.extend(["", f"... truncated from {patch.get('original_length', '?')} chars"])
    return "\n".join(lines)


def format_diff_file_list(diff_sections: list[tuple[str, dict[str, object]]], selected_index: int) -> str:
    lines = ["Changed Files", ""]
    if not diff_sections:
        lines.append("No diff files available.")
        return "\n".join(lines)
    for index, (label, _patch) in enumerate(diff_sections):
        marker = ">" if index == selected_index else " "
        lines.append(f"{marker} {index + 1:>2}. {_clip(label, 72)}")
    lines.extend(["", "Keys:", "  [ / ] switch diff file"])
    return "\n".join(lines)


def split_diff_files(patch: dict[str, object] | None) -> list[tuple[str, dict[str, object]]]:
    if not patch:
        return []
    text = str(patch.get("text") or "")
    if not text.strip():
        return []
    sections: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("diff --git ") and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)
    results: list[tuple[str, dict[str, object]]] = []
    for section in sections:
        header = section[0] if section else "diff"
        label = header.replace("diff --git ", "", 1)
        results.append(
            (
                label,
                {
                    "text": "\n".join(section),
                    "truncated": bool(patch.get("truncated")),
                    "original_length": patch.get("original_length", len("\n".join(section))),
                },
            )
        )
    return results


def extract_run_diff(run: object | None) -> tuple[str, dict[str, object] | None]:
    if run is None:
        return "No run selected.", None
    summary = getattr(run, "git_change_summary", None) or {}
    stored_patch = summary.get("end_diff_patch") if isinstance(summary, dict) else None
    if stored_patch:
        return "Stored snapshot diff", stored_patch
    cwd = Path(getattr(run, "working_directory", Path.cwd()))
    live = collect_git_changes(cwd)
    if not live.get("ok"):
        return f"Live diff unavailable: {live.get('error', 'unknown error')}", None
    patch = live.get("diff_patch")
    if isinstance(patch, dict) and patch.get("text"):
        return "Live working tree diff", patch
    return "No diff available.", None


def format_editor_banner(*, mode: str | None, context: dict[str, object]) -> str:
    if not mode:
        return ""
    labels = {
        "session-title": "Editing session title",
        "session-summary": "Editing session summary",
        "plan-add-inline": "Adding plan step",
        "plan-edit-inline": "Editing current plan step",
    }
    lines = [
        "Editor",
        "",
        labels.get(mode, mode),
        "",
        "Ctrl+S saves changes.",
        "Esc closes without saving.",
    ]
    if mode in {"session-summary", "plan-add-inline", "plan-edit-inline"}:
        lines.append("Format:")
        if mode == "session-summary":
            lines.append("  multi-line summary")
        else:
            lines.append("  first line = title")
            lines.append("  remaining lines = details")
    if mode.startswith("plan-") and context.get("plan_id"):
        lines.append(f"plan: {context['plan_id']}")
    if mode.startswith("session-") and context.get("session_id"):
        lines.append(f"session: {context['session_id']}")
    return "\n".join(lines)


def format_integrations_detail(
    *,
    plugin_loaded: list[object],
    plugin_load_errors: list[dict[str, str]],
    plugin_hook_errors: list[dict[str, str]],
    mcp_status: dict[str, object] | None,
    lsp_status: dict[str, object] | None,
) -> str:
    lines = ["Integrations", "", "Plugins:"]
    if not plugin_loaded:
        lines.append("  loaded: none")
    else:
        for meta in plugin_loaded[:8]:
            lines.append(f"  - {getattr(meta, 'name', '?')} {getattr(meta, 'version', '')}".rstrip())
    if plugin_load_errors:
        lines.append("  load errors:")
        for item in plugin_load_errors[:6]:
            lines.append(f"    - {item.get('plugin', '?')}: {_clip(item.get('error'), 90)}")
    if plugin_hook_errors:
        lines.append("  hook errors:")
        for item in plugin_hook_errors[:6]:
            lines.append(f"    - {item.get('hook', '?')} / {item.get('plugin', '?')}: {_clip(item.get('error'), 80)}")
    lines.extend(["", "MCP:"])
    if not mcp_status:
        lines.append("  unavailable")
    else:
        lines.append(f"  connected: {', '.join(mcp_status.get('connected', [])) or 'none'}")
        lines.append(f"  degraded: {', '.join(mcp_status.get('degraded', [])) or 'none'}")
        if mcp_status.get("degraded_details"):
            for name, detail in sorted(mcp_status["degraded_details"].items()):
                lines.append(f"    - {name}: {_clip(detail, 88)}")
        lines.append(f"  tools: {mcp_status.get('tool_count', 0)}")
    lines.extend(["", "LSP:"])
    if not lsp_status:
        lines.append("  unavailable")
    else:
        lines.append(f"  configured: {', '.join(lsp_status.get('configured', [])) or 'none'}")
        lines.append(f"  degraded: {', '.join(lsp_status.get('degraded', [])) or 'none'}")
        if lsp_status.get("degraded_details"):
            for name, detail in sorted(lsp_status["degraded_details"].items()):
                lines.append(f"    - {name}: {_clip(detail, 88)}")
        lines.append(f"  languages: {', '.join(lsp_status.get('supported_languages', [])) or 'none'}")
    return "\n".join(lines)


def format_activity_detail(item: dict[str, object] | None) -> str:
    if item is None:
        return "\n".join(
            [
                "Activity Stream",
                "",
                "No activity selected.",
                "Press 8 to switch to the activity stream.",
            ]
        )
    lines = [
        "Activity Stream",
        "",
        f"source: {item.get('source', '-')}",
        f"type: {item.get('event_type', '-')}",
        f"created: {item.get('created_at', '-')}",
        f"ref: {item.get('ref_id', '-')}",
        "",
        "summary:",
        str(item.get("summary", "-")),
        "",
    ]
    payload = item.get("payload")
    if payload:
        lines.extend(["payload:", _clip(str(payload), 500)])
    return "\n".join(lines)


def format_run_detail(run: object | None, events: list[dict[str, object]], live_output: str | None = None) -> str:
    if run is None:
        return "\n".join(
            [
                "Run Detail",
                "",
                "No run selected.",
                "Use j/k to move through recent runs.",
            ]
        )
    metadata = getattr(run, "metadata", {}) or {}
    lines = [
        "Run Detail",
        "",
        f"id: {getattr(run, 'id', '-')}",
        f"status: {getattr(run, 'status', '-')}",
        f"backend: {getattr(run, 'backend_name', '-')}",
        f"strategy: {getattr(run, 'strategy_name', '-')}",
        f"created: {getattr(run, 'created_at', '-')}",
        f"domain: {metadata.get('domain') or '-'}",
        f"model: {metadata.get('backend_model') or '-'}",
        "",
        "goal:",
        getattr(run, "goal", "") or "-",
        "",
    ]
    output_text = live_output if live_output is not None else getattr(run, "final_output", None)
    if output_text:
        lines.extend(["output:", output_text, ""])
    if getattr(run, "error_message", None):
        lines.extend(["error:", str(getattr(run, "error_message")), ""])
    lines.append("events:")
    if not events:
        lines.append("  (none)")
    else:
        for event in events[-8:]:
            event_type = str(event.get("event_type", "?"))
            payload = event.get("payload", {})
            payload_text = _clip(str(payload), 120)
            lines.append(f"  - {event_type}: {payload_text}")
    return "\n".join(lines)


def format_ops_panel(
    *,
    statuses: list[dict[str, object]],
    sessions: list[object],
    plans: list[object],
    approvals: list[object],
    jobs: list[object],
    mode: str,
    backend: str,
    model_override: str | None,
    strategy: str,
    domain: str | None,
    cwd: Path,
    autonomous: bool,
    busy: bool,
    review_focus: str = "targets",
    editor_visible: bool = False,
    recent_actions: list[str] | None = None,
    status_message: str | None = None,
) -> str:
    lines = [
        "Ops",
        "",
        f"focus: {mode}",
        f"default backend: {backend}",
        f"default model: {model_override or '-'}",
        f"strategy: {strategy}",
        f"domain: {domain or '-'}",
        f"cwd: {cwd}",
        f"autonomous: {'yes' if autonomous else 'no'}",
        f"busy: {'yes' if busy else 'no'}",
        "",
        "Backends:",
    ]
    if not statuses:
        lines.append("  (none)")
    else:
        for status in statuses[:8]:
            state = "up" if status.get("reachable") else "down"
            if status.get("temporarily_unavailable"):
                state = "cooldown"
            model = _clip(str(status.get("model") or "-"), 20)
            lines.append(f"  - {status['name']}: {state} [{model}]")
    lines.extend(["", "Sessions:"])
    if not sessions:
        lines.append("  (none)")
    else:
        for session in sessions[:5]:
            lines.append(f"  - {getattr(session, 'title', None) or getattr(session, 'id', '?')}")
    lines.extend(["", "Plans:"])
    if not plans:
        lines.append("  (none)")
    else:
        for plan in plans[:5]:
            lines.append(
                f"  - [{getattr(plan, 'status', '?')}] {_clip(getattr(plan, 'goal', ''), 42) or getattr(plan, 'id', '?')}"
            )
    lines.extend(["", "Approvals:"])
    if not approvals:
        lines.append("  (none)")
    else:
        for approval in approvals[:4]:
            lines.append(
                f"  - {getattr(approval, 'tool_name', '?')} [{getattr(approval, 'status', '?')}]"
            )
    lines.extend(["", "Jobs:"])
    if not jobs:
        lines.append("  (none)")
    else:
        for job in jobs[:4]:
            lines.append(f"  - [{getattr(job, 'status', '?')}] {_clip(getattr(job, 'goal', ''), 36)}")
    lines.extend(
        [
            "",
            "Keys:",
            "  1-6 switch decks",
            "  j/k  move current selection",
            "  ctrl+p open command palette",
            "  r    refresh",
            "  q    quit",
        ]
    )
    lines.extend(["", "Context Actions:"])
    if editor_visible:
        lines.extend(["  - ctrl+s save editor", "  - esc close editor"])
    elif mode == "approvals":
        lines.extend(["  - approve", "  - deny"])
    elif mode == "jobs":
        lines.extend(["  - pause", "  - resume", "  - cancel"])
    elif mode == "sessions":
        lines.extend(["  - e edit title", "  - s edit summary", "  - archive-session", "  - activate-session"])
    elif mode == "plans":
        lines.extend(["  - e edit step", "  - a add step", "  - x drop current step", "  - advance-plan", "  - block-plan"])
    elif mode == "review":
        lines.extend(
            [
                f"  - tab focus {'files' if review_focus == 'targets' else 'targets'}",
                "  - target <n> select review target",
                "  - file <n> select diff file",
            ]
        )
    elif mode == "integrations":
        lines.extend(["  - refresh integration state"])
    else:
        lines.extend(["  - enter run goal", "  - open <query>", "  - focus <deck>"])
    if status_message:
        lines.extend(["", "Status:", f"  {status_message}"])
    if recent_actions:
        lines.extend(["", "Recent Actions:"])
        for item in recent_actions[:5]:
            lines.append(f"  - {item}")
    return "\n".join(lines)


def format_hero(
    *,
    run_count: int,
    session_count: int,
    plan_count: int,
    mode: str,
    selected_label: str | None,
    backend: str,
    model_override: str | None,
    strategy: str,
    busy: bool,
) -> str:
    status = "RUNNING" if busy else "READY"
    selected = selected_label or "-"
    model_part = f" | model {model_override}" if model_override else ""
    return (
        f" Orchestro Command Deck  [{status}]  focus {mode.upper()}  backend {backend}{model_part}  strategy {strategy}\n"
        f" runs {run_count} | sessions {session_count} | plans {plan_count} | selected {selected}"
    )


def parse_palette_command(raw: str) -> tuple[str, str | None]:
    text = raw.strip()
    if not text:
        return "noop", None
    if text.startswith(":"):
        text = text[1:].strip()
    if not text:
        return "noop", None
    parts = text.split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else None
    return command, arg


def rank_palette_matches(query: str, candidates: list[tuple[str, str]]) -> list[tuple[str, str]]:
    lowered = query.strip().lower()
    if not lowered:
        return candidates
    scored: list[tuple[float, tuple[str, str]]] = []
    for key, label in candidates:
        hay = f"{key} {label}".lower()
        if lowered in hay:
            score = 2.0
        else:
            score = difflib.SequenceMatcher(None, lowered, hay).ratio()
        scored.append((score, (key, label)))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item for score, item in scored if score > 0.2]


def action_bar_state(
    *,
    mode: str,
    editor_visible: bool,
    review_focus: str,
) -> dict[str, tuple[str, str | None, bool]]:
    if editor_visible:
        return {
            "btn-approve": ("Save", "save-editor", True),
            "btn-deny": ("Close", "close-editor", True),
            "btn-pause": ("", None, False),
            "btn-resume": ("", None, False),
            "btn-cancel": ("", None, False),
        }
    if mode == "approvals":
        return {
            "btn-approve": ("Approve", "approve", True),
            "btn-deny": ("Deny", "deny", True),
            "btn-pause": ("", None, False),
            "btn-resume": ("", None, False),
            "btn-cancel": ("", None, False),
        }
    if mode == "jobs":
        return {
            "btn-approve": ("Pause", "pause", True),
            "btn-deny": ("Resume", "resume", True),
            "btn-pause": ("Cancel", "cancel", True),
            "btn-resume": ("", None, False),
            "btn-cancel": ("", None, False),
        }
    if mode == "sessions":
        return {
            "btn-approve": ("Edit Title", "edit-session-title", True),
            "btn-deny": ("Edit Summary", "edit-session-summary", True),
            "btn-pause": ("Archive", "archive-session", True),
            "btn-resume": ("Activate", "activate-session", True),
            "btn-cancel": ("", None, False),
        }
    if mode == "plans":
        return {
            "btn-approve": ("Edit Step", "edit-plan-step", True),
            "btn-deny": ("Add Step", "add-plan-step", True),
            "btn-pause": ("Drop Step", "drop-plan-step", True),
            "btn-resume": ("Advance", "advance-plan", True),
            "btn-cancel": ("Block", "block-plan", True),
        }
    if mode == "review":
        toggle_label = "Focus Files" if review_focus == "targets" else "Focus Targets"
        return {
            "btn-approve": (toggle_label, "toggle-review-focus", True),
            "btn-deny": ("Prev File", "prev-diff-file", True),
            "btn-pause": ("Next File", "next-diff-file", True),
            "btn-resume": ("", None, False),
            "btn-cancel": ("", None, False),
        }
    if mode == "integrations":
        return {
            "btn-approve": ("Refresh", "refresh", True),
            "btn-deny": ("", None, False),
            "btn-pause": ("", None, False),
            "btn-resume": ("", None, False),
            "btn-cancel": ("", None, False),
        }
    if mode == "activity":
        return {
            "btn-approve": ("Refresh", "refresh", True),
            "btn-deny": ("Runs", "focus-runs", True),
            "btn-pause": ("Review", "focus-review", True),
            "btn-resume": ("Approvals", "focus-approvals", True),
            "btn-cancel": ("Jobs", "focus-jobs", True),
        }
    return {
        "btn-approve": ("Refresh", "refresh", True),
        "btn-deny": ("Runs", "focus-runs", True),
        "btn-pause": ("Sessions", "focus-sessions", True),
        "btn-resume": ("Plans", "focus-plans", True),
        "btn-cancel": ("Review", "focus-review", True),
    }


def launch_tui(
    orchestro: Orchestro,
    *,
    backend: str = "auto",
    model_override: str | None = None,
    strategy: str = "direct",
    domain: str | None = None,
    cwd: Path | None = None,
    providers: list[str] | None = None,
    autonomous: bool = False,
) -> int:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal
        from textual.reactive import reactive
        from textual.widgets import Button, Footer, Header, Input, Static, TextArea
    except ImportError as exc:
        raise RuntimeError(
            "Textual is not installed. Install the TUI extras with `pip install -e .[tui]`."
        ) from exc

    resolved_cwd = (cwd or Path.cwd()).resolve()
    context_providers = list(providers or DEFAULT_CONTEXT_PROVIDERS)

    class OrchestroTUI(App[None]):
        CSS = """
        Screen {
            layout: vertical;
            background: #091019;
            color: #f5f7fb;
        }

        Header {
            background: #10243a;
            color: #f5f7fb;
        }

        Footer {
            background: #10243a;
            color: #f5f7fb;
        }

        #hero {
            height: 4;
            margin: 1 1 0 1;
            padding: 1 2;
            background: #10304d;
            border: round #65d6ff;
            color: #f5f7fb;
            text-style: bold;
        }

        #body {
            height: 1fr;
            margin: 1;
        }

        .pane {
            width: 1fr;
            height: 1fr;
            padding: 1 2;
            margin-right: 1;
            border: round #2ec4b6;
            background: #0d1724;
            overflow: auto auto;
        }

        #nav-pane {
            border: round #2ec4b6;
            background: #0d1724;
        }

        #detail-pane {
            width: 2fr;
            border: round #65d6ff;
            background: #08111c;
        }

        #ops-pane {
            margin-right: 0;
            border: round #f4a261;
            background: #17131d;
        }

        #actions {
            height: 3;
            margin: 0 1;
            padding: 0 1;
        }

        .action-btn {
            min-width: 12;
            margin-right: 1;
        }

        #btn-approve {
            background: #1f6f50;
        }

        #btn-deny, #btn-cancel {
            background: #7a2230;
        }

        #btn-pause, #btn-resume {
            background: #7b5d1e;
        }

        #composer {
            margin: 0 1 1 1;
            border: round #e9c46a;
            background: #0d1826;
            color: #f5f7fb;
        }

        #palette {
            margin: 0 1 1 1;
            border: round #ff7f50;
            background: #26131b;
            color: #fff5ee;
        }

        #editor-area {
            margin: 0 1 1 1;
            height: 10;
            border: round #7bdff2;
            background: #0d1826;
            color: #f5f7fb;
        }
        """

        BINDINGS = [
            ("q", "quit", "Quit"),
            ("r", "refresh_dashboard", "Refresh"),
            ("1", "switch_runs", "Runs"),
            ("2", "switch_sessions", "Sessions"),
            ("3", "switch_plans", "Plans"),
            ("4", "switch_approvals", "Approvals"),
            ("5", "switch_jobs", "Jobs"),
            ("6", "switch_review", "Review"),
            ("7", "switch_integrations", "Integrations"),
            ("8", "switch_activity", "Activity"),
            ("ctrl+p", "toggle_palette", "Palette"),
            ("tab", "toggle_review_focus", "Review Focus"),
            ("escape", "close_palette", "Close"),
            ("[", "prev_diff_file", "Prev Diff"),
            ("]", "next_diff_file", "Next Diff"),
            ("ctrl+s", "save_editor", "Save Editor"),
            ("e", "open_editor", "Edit"),
            ("a", "open_add_editor", "Add"),
            ("x", "drop_selected", "Drop"),
            ("s", "open_summary_editor", "Summary"),
            ("j", "next_item", "Next"),
            ("k", "prev_item", "Prev"),
        ]

        selected_run_index = reactive(0)
        selected_session_index = reactive(0)
        selected_plan_index = reactive(0)
        selected_approval_index = reactive(0)
        selected_job_index = reactive(0)
        selected_activity_index = reactive(0)
        view_mode = reactive("runs")

        def __init__(self) -> None:
            super().__init__()
            self._runs: list[object] = []
            self._sessions: list[object] = []
            self._plans: list[object] = []
            self._approvals: list[object] = []
            self._jobs: list[object] = []
            self._busy = False
            self._live_output: dict[str, str] = {}
            self._last_error: str | None = None
            self._palette_visible = False
            self._palette_history: list[str] = []
            self._palette_suggestions: list[str] = []
            self._selected_diff_index = 0
            self._integration_cache: tuple[dict[str, object] | None, dict[str, object] | None] = (None, None)
            self._editor_visible = False
            self._editor_mode: str | None = None
            self._editor_context: dict[str, object] = {}
            self._review_focus = "targets"
            self._recent_actions: list[str] = []
            self._status_message: str | None = None
            self._status_until = 0.0
            self._activity_items: list[dict[str, object]] = []

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            yield Static("", id="hero")
            with Horizontal(id="body"):
                yield Static("", id="nav-pane", classes="pane")
                yield Static("", id="detail-pane", classes="pane")
                yield Static("", id="ops-pane", classes="pane")
            with Horizontal(id="actions"):
                yield Button("Approve", id="btn-approve", classes="action-btn")
                yield Button("Deny", id="btn-deny", classes="action-btn")
                yield Button("Pause", id="btn-pause", classes="action-btn")
                yield Button("Resume", id="btn-resume", classes="action-btn")
                yield Button("Cancel", id="btn-cancel", classes="action-btn")
                yield Button("Palette", id="btn-palette", classes="action-btn")
            yield Input(
                placeholder="Ask Orchestro... Enter runs a goal. 1-6 switch decks. j/k move selection.",
                id="composer",
            )
            yield Input(
                placeholder="Palette: focus runs|sessions|plans|approvals|jobs|review | approve | deny | pause | resume | cancel | refresh",
                id="palette",
            )
            yield Input(
                placeholder="Editor",
                id="editor",
            )
            yield TextArea("", id="editor-area")
            yield Footer()

        def on_mount(self) -> None:
            self._refresh_dashboard()
            self.query_one("#palette", Input).styles.display = "none"
            self.query_one("#editor", Input).styles.display = "none"
            self.query_one("#editor-area", TextArea).styles.display = "none"
            self.set_interval(5.0, self._refresh_dashboard)

        def action_refresh_dashboard(self) -> None:
            self._refresh_dashboard()

        def action_switch_runs(self) -> None:
            self.view_mode = "runs"
            self._refresh_dashboard()

        def action_switch_sessions(self) -> None:
            self.view_mode = "sessions"
            self._refresh_dashboard()

        def action_switch_plans(self) -> None:
            self.view_mode = "plans"
            self._refresh_dashboard()

        def action_switch_approvals(self) -> None:
            self.view_mode = "approvals"
            self._refresh_dashboard()

        def action_switch_jobs(self) -> None:
            self.view_mode = "jobs"
            self._refresh_dashboard()

        def action_switch_review(self) -> None:
            self.view_mode = "review"
            self._review_focus = "targets"
            self._refresh_dashboard()

        def action_switch_integrations(self) -> None:
            self.view_mode = "integrations"
            self._refresh_dashboard()

        def action_switch_activity(self) -> None:
            self.view_mode = "activity"
            self._refresh_dashboard()

        def action_toggle_palette(self) -> None:
            self._palette_visible = not self._palette_visible
            palette = self.query_one("#palette", Input)
            composer = self.query_one("#composer", Input)
            if self._palette_visible:
                palette.styles.display = "block"
                palette.value = ""
                palette.focus()
                composer.styles.display = "none"
            else:
                palette.styles.display = "none"
                composer.styles.display = "block"
                composer.focus()

        def action_toggle_review_focus(self) -> None:
            if self.view_mode != "review":
                return
            self._review_focus = "files" if self._review_focus == "targets" else "targets"
            self._refresh_dashboard()

        def action_close_palette(self) -> None:
            if self._editor_visible:
                self._editor_visible = False
                self._editor_mode = None
                self._editor_context = {}
                editor = self.query_one("#editor", Input)
                editor_area = self.query_one("#editor-area", TextArea)
                editor.styles.display = "none"
                editor_area.styles.display = "none"
                composer = self.query_one("#composer", Input)
                composer.styles.display = "block"
                composer.focus()
                self._set_status("editor closed", ttl=2.0)
                return
            if not self._palette_visible:
                return
            self._palette_visible = False
            palette = self.query_one("#palette", Input)
            composer = self.query_one("#composer", Input)
            palette.styles.display = "none"
            composer.styles.display = "block"
            composer.focus()

        def action_next_item(self) -> None:
            if self.view_mode == "review":
                if self._review_focus == "files":
                    review_run = self._selected_review_run()
                    _title, patch = extract_run_diff(review_run)
                    diff_sections = split_diff_files(patch)
                    if diff_sections:
                        self._selected_diff_index = min(len(diff_sections) - 1, self._selected_diff_index + 1)
                elif self._jobs:
                    self.selected_job_index = min(len(self._jobs) - 1, self.selected_job_index + 1)
            elif self.view_mode == "runs" and self._runs:
                self.selected_run_index = min(len(self._runs) - 1, self.selected_run_index + 1)
            elif self.view_mode == "sessions" and self._sessions:
                self.selected_session_index = min(len(self._sessions) - 1, self.selected_session_index + 1)
            elif self.view_mode == "plans" and self._plans:
                self.selected_plan_index = min(len(self._plans) - 1, self.selected_plan_index + 1)
            elif self.view_mode == "approvals" and self._approvals:
                self.selected_approval_index = min(len(self._approvals) - 1, self.selected_approval_index + 1)
            elif self.view_mode == "activity" and self._activity_items:
                self.selected_activity_index = min(len(self._activity_items) - 1, self.selected_activity_index + 1)
            elif self.view_mode in {"jobs", "review"} and self._jobs:
                self.selected_job_index = min(len(self._jobs) - 1, self.selected_job_index + 1)
            self._refresh_dashboard()

        def action_prev_item(self) -> None:
            if self.view_mode == "review":
                if self._review_focus == "files":
                    self._selected_diff_index = max(0, self._selected_diff_index - 1)
                elif self._jobs:
                    self.selected_job_index = max(0, self.selected_job_index - 1)
            elif self.view_mode == "runs" and self._runs:
                self.selected_run_index = max(0, self.selected_run_index - 1)
            elif self.view_mode == "sessions" and self._sessions:
                self.selected_session_index = max(0, self.selected_session_index - 1)
            elif self.view_mode == "plans" and self._plans:
                self.selected_plan_index = max(0, self.selected_plan_index - 1)
            elif self.view_mode == "approvals" and self._approvals:
                self.selected_approval_index = max(0, self.selected_approval_index - 1)
            elif self.view_mode == "activity" and self._activity_items:
                self.selected_activity_index = max(0, self.selected_activity_index - 1)
            elif self.view_mode in {"jobs", "review"} and self._jobs:
                self.selected_job_index = max(0, self.selected_job_index - 1)
            self._refresh_dashboard()

        def action_next_diff_file(self) -> None:
            self._selected_diff_index += 1
            self._refresh_dashboard()

        def action_prev_diff_file(self) -> None:
            self._selected_diff_index = max(0, self._selected_diff_index - 1)
            self._refresh_dashboard()

        def action_open_editor(self) -> None:
            if self.view_mode == "sessions":
                session = self._selected_session()
                if session is None:
                    self._last_error = "no session selected"
                    self._refresh_dashboard()
                    return
                self._show_editor(
                    mode="session-title",
                    value=str(getattr(session, "title", None) or ""),
                    placeholder="Edit session title and press Enter to save",
                    context={"session_id": getattr(session, "id")},
                )
                return
            if self.view_mode == "plans":
                plan = self._selected_plan()
                if plan is None:
                    self._last_error = "no plan selected"
                    self._refresh_dashboard()
                    return
                step = self._current_plan_step(plan_id=getattr(plan, "id"), sequence_no=int(getattr(plan, "current_step_no", 1)))
                if step is None:
                    self._last_error = "no current plan step"
                    self._refresh_dashboard()
                    return
                details = getattr(step, "details", None) or ""
                value = str(getattr(step, "title", "") or "")
                if details:
                    value = f"{value}\n{details}"
                self._show_editor(
                    mode="plan-edit-inline",
                    value=value,
                    placeholder="Edit current step",
                    context={"plan_id": getattr(plan, "id"), "sequence_no": getattr(step, "sequence_no")},
                )

        def action_open_add_editor(self) -> None:
            if self.view_mode != "plans":
                return
            plan = self._selected_plan()
            if plan is None:
                self._last_error = "no plan selected"
                self._refresh_dashboard()
                return
            self._show_editor(
                mode="plan-add-inline",
                value="",
                placeholder="Add step",
                context={"plan_id": getattr(plan, "id"), "after_sequence_no": int(getattr(plan, "current_step_no", 1))},
            )

        def action_open_summary_editor(self) -> None:
            if self.view_mode != "sessions":
                return
            session = self._selected_session()
            if session is None:
                self._last_error = "no session selected"
                self._refresh_dashboard()
                return
            self._show_editor(
                mode="session-summary",
                value=str(getattr(session, "summary", None) or ""),
                placeholder="Edit session summary and press Enter to save",
                context={"session_id": getattr(session, "id")},
            )

        def action_drop_selected(self) -> None:
            if self.view_mode != "plans":
                return
            plan = self._selected_plan()
            if plan is None:
                self._last_error = "no plan selected"
                self._refresh_dashboard()
                return
            seq = int(getattr(plan, "current_step_no", 1))
            orchestro.db.delete_plan_step(plan_id=getattr(plan, "id"), sequence_no=seq)
            self._last_error = None
            self._record_action(f"dropped plan step {seq} from {getattr(plan, 'id', '?')}")
            self._refresh_dashboard()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id == "editor":
                self._commit_editor(event.value)
                event.input.value = ""
                return
            if event.input.id == "palette":
                command_text = event.value.strip()
                if command_text:
                    self._palette_history.insert(0, command_text)
                    self._palette_history = self._palette_history[:12]
                self._execute_palette_command(command_text)
                event.input.value = ""
                return
            goal = event.value.strip()
            if not goal or self._busy:
                event.input.value = ""
                return
            event.input.value = ""
            self._busy = True
            thread = threading.Thread(target=self._run_goal, args=(goal,), daemon=True, name="orchestro-tui-run")
            thread.start()
            self._set_status(f"starting run: {_clip(goal, 72)}", ttl=3.0)
            self._refresh_dashboard()

        def on_input_changed(self, event: Input.Changed) -> None:
            if event.input.id != "palette":
                return
            raw = event.value.strip().lower()
            commands = [
                "focus runs",
                "focus sessions",
                "focus plans",
                "focus approvals",
                "focus jobs",
                "focus review",
                "focus integrations",
                "focus activity",
                "review-focus files",
                "target 2",
                "file 1",
                "open run-id-or-query",
                "session-title updated session title",
                "session-summary concise summary",
                "plan-add step title | optional details",
                "plan-edit 2 | new title | new details",
                "plan-drop 2",
                "approve",
                "deny",
                "pause",
                "resume",
                "cancel",
                "advance-plan",
                "block-plan",
                "archive-session",
                "activate-session",
                "refresh",
                "clear-error",
            ]
            if not raw:
                self._palette_suggestions = self._palette_history[:5]
            else:
                self._palette_suggestions = [item for item in commands if raw in item][:6]
            self._refresh_dashboard()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            button_id = event.button.id or ""
            if button_id == "btn-palette":
                self.action_toggle_palette()
                return
            command_map = action_bar_state(
                mode=self.view_mode,
                editor_visible=self._editor_visible,
                review_focus=self._review_focus,
            )
            _label, command, enabled = command_map.get(button_id, ("", None, False))
            if not enabled:
                return
            if command:
                self._execute_button_command(command)

        def _execute_button_command(self, command: str) -> None:
            if command == "save-editor":
                self.action_save_editor()
                return
            if command == "close-editor":
                self.action_close_palette()
                return
            if command == "edit-session-title":
                self.action_open_editor()
                return
            if command == "edit-session-summary":
                self.action_open_summary_editor()
                return
            if command == "edit-plan-step":
                self.action_open_editor()
                return
            if command == "add-plan-step":
                self.action_open_add_editor()
                return
            if command == "drop-plan-step":
                self.action_drop_selected()
                return
            if command == "toggle-review-focus":
                self.action_toggle_review_focus()
                return
            if command == "prev-diff-file":
                self.action_prev_diff_file()
                return
            if command == "next-diff-file":
                self.action_next_diff_file()
                return
            if command == "focus-runs":
                self.action_switch_runs()
                return
            if command == "focus-approvals":
                self.action_switch_approvals()
                return
            if command == "focus-jobs":
                self.action_switch_jobs()
                return
            if command == "focus-sessions":
                self.action_switch_sessions()
                return
            if command == "focus-plans":
                self.action_switch_plans()
                return
            if command == "focus-review":
                self.action_switch_review()
                return
            self._execute_palette_command(command)

        def action_save_editor(self) -> None:
            if not self._editor_visible:
                return
            if self._editor_mode in {"session-summary", "plan-add-inline", "plan-edit-inline"}:
                editor_area = self.query_one("#editor-area", TextArea)
                self._commit_editor(editor_area.text)
            else:
                editor = self.query_one("#editor", Input)
                self._commit_editor(editor.value)

        def _record_action(self, message: str) -> None:
            text = _clip(message, 88)
            self._recent_actions.insert(0, text)
            self._recent_actions = self._recent_actions[:10]
            self._set_status(text)

        def _set_status(self, message: str | None, *, ttl: float = 4.0) -> None:
            self._status_message = _clip(message, 104) if message else None
            self._status_until = time.monotonic() + ttl if message else 0.0

        def _show_editor(
            self,
            *,
            mode: str,
            value: str,
            placeholder: str,
            context: dict[str, object],
        ) -> None:
            self._editor_visible = True
            self._editor_mode = mode
            self._editor_context = context
            self._palette_visible = False
            palette = self.query_one("#palette", Input)
            composer = self.query_one("#composer", Input)
            editor = self.query_one("#editor", Input)
            editor_area = self.query_one("#editor-area", TextArea)
            palette.styles.display = "none"
            composer.styles.display = "none"
            multiline = mode in {"session-summary", "plan-add-inline", "plan-edit-inline"}
            if multiline:
                editor.styles.display = "none"
                editor_area.styles.display = "block"
                editor_area.text = value
                editor_area.focus()
            else:
                editor_area.styles.display = "none"
                editor.styles.display = "block"
                editor.placeholder = placeholder
                editor.value = value
                editor.focus()

        def _commit_editor(self, raw: str) -> None:
            mode = self._editor_mode
            value = raw.strip()
            if not mode:
                self.action_close_palette()
                return
            try:
                if mode == "session-title":
                    session_id = str(self._editor_context["session_id"])
                    orchestro.db.update_session(session_id=session_id, title=value or None)
                    self._record_action(f"updated session title for {session_id}")
                elif mode == "session-summary":
                    session_id = str(self._editor_context["session_id"])
                    orchestro.db.update_session(session_id=session_id, summary=value or None)
                    self._record_action(f"updated session summary for {session_id}")
                elif mode == "plan-add-inline":
                    plan_id = str(self._editor_context["plan_id"])
                    after_sequence_no = int(self._editor_context["after_sequence_no"])
                    title, details = self._split_title_details(value)
                    if not title:
                        self._last_error = "plan step title cannot be empty"
                    else:
                        orchestro.db.insert_plan_step(
                            plan_id=plan_id,
                            after_sequence_no=after_sequence_no,
                            title=title,
                            details=details,
                        )
                        self._last_error = None
                        self._record_action(f"added plan step to {plan_id}: {title}")
                elif mode == "plan-edit-inline":
                    plan_id = str(self._editor_context["plan_id"])
                    sequence_no = int(self._editor_context["sequence_no"])
                    title, details = self._split_title_details(value)
                    if not title:
                        self._last_error = "plan step title cannot be empty"
                    else:
                        orchestro.db.update_plan_step(
                            plan_id=plan_id,
                            sequence_no=sequence_no,
                            title=title,
                            details=details,
                        )
                        self._last_error = None
                        self._record_action(f"updated plan step {sequence_no} in {plan_id}")
            finally:
                self._editor_visible = False
                self._editor_mode = None
                self._editor_context = {}
                editor = self.query_one("#editor", Input)
                editor_area = self.query_one("#editor-area", TextArea)
                editor.styles.display = "none"
                editor_area.styles.display = "none"
                composer = self.query_one("#composer", Input)
                composer.styles.display = "block"
                composer.focus()
                self._refresh_dashboard()

        def _selected_run(self) -> object | None:
            if not self._runs:
                return None
            if self.selected_run_index >= len(self._runs):
                self.selected_run_index = max(0, len(self._runs) - 1)
            return self._runs[self.selected_run_index]

        def _selected_session(self) -> object | None:
            if not self._sessions:
                return None
            if self.selected_session_index >= len(self._sessions):
                self.selected_session_index = max(0, len(self._sessions) - 1)
            return self._sessions[self.selected_session_index]

        def _selected_plan(self) -> object | None:
            if not self._plans:
                return None
            if self.selected_plan_index >= len(self._plans):
                self.selected_plan_index = max(0, len(self._plans) - 1)
            return self._plans[self.selected_plan_index]

        def _selected_approval(self) -> object | None:
            if not self._approvals:
                return None
            if self.selected_approval_index >= len(self._approvals):
                self.selected_approval_index = max(0, len(self._approvals) - 1)
            return self._approvals[self.selected_approval_index]

        def _selected_job(self) -> object | None:
            if not self._jobs:
                return None
            if self.selected_job_index >= len(self._jobs):
                self.selected_job_index = max(0, len(self._jobs) - 1)
            return self._jobs[self.selected_job_index]

        def _selected_review_run(self) -> object | None:
            selected_job = self._selected_job()
            if getattr(selected_job, "run_id", None):
                return orchestro.db.get_run(getattr(selected_job, "run_id"))
            return self._selected_run()

        def _selected_activity(self) -> dict[str, object] | None:
            if not self._activity_items:
                return None
            if self.selected_activity_index >= len(self._activity_items):
                self.selected_activity_index = max(0, len(self._activity_items) - 1)
            return self._activity_items[self.selected_activity_index]

        def _review_jobs(self) -> list[object]:
            return [
                job for job in self._jobs if getattr(job, "status", "") in {"running", "paused", "failed", "cancel_requested"}
            ]

        def _select_review_target(self, raw_index: str) -> None:
            try:
                requested = int(raw_index.strip())
            except ValueError:
                self._last_error = "target requires a numeric index"
                return
            review_jobs = self._review_jobs()
            if requested < 1 or requested > len(review_jobs):
                self._last_error = f"target out of range: {requested}"
                return
            chosen = review_jobs[requested - 1]
            chosen_id = getattr(chosen, "id", None)
            if chosen_id is None:
                self._last_error = "selected target has no id"
                return
            for index, job in enumerate(self._jobs):
                if getattr(job, "id", None) == chosen_id:
                    self.selected_job_index = index
                    self._review_focus = "targets"
                    self._last_error = None
                    self._record_action(f"selected review target {requested}")
                    return
            self._last_error = "selected target is no longer available"

        def _select_review_file(self, raw_index: str) -> None:
            try:
                requested = int(raw_index.strip())
            except ValueError:
                self._last_error = "file requires a numeric index"
                return
            _title, patch = extract_run_diff(self._selected_review_run())
            diff_sections = split_diff_files(patch)
            if requested < 1 or requested > len(diff_sections):
                self._last_error = f"file out of range: {requested}"
                return
            self._selected_diff_index = requested - 1
            self._review_focus = "files"
            self._last_error = None
            self._record_action(f"selected diff file {requested}")

        def _selected_run_id(self) -> str | None:
            run = self._selected_run()
            return getattr(run, "id", None) if run is not None else None

        def _set_selected_run_by_id(self, run_id: str) -> None:
            for index, run in enumerate(self._runs):
                if getattr(run, "id", None) == run_id:
                    self.selected_run_index = index
                    break

        def _current_plan_step(self, *, plan_id: str, sequence_no: int) -> object | None:
            for step in orchestro.db.list_plan_steps(plan_id):
                if int(getattr(step, "sequence_no", -1)) == sequence_no:
                    return step
            return None

        def _build_activity_items(self) -> list[dict[str, object]]:
            items: list[dict[str, object]] = []
            for run in self._runs[:8]:
                run_id = getattr(run, "id", None)
                if not run_id:
                    continue
                for event in orchestro.db.list_events(run_id)[-4:]:
                    items.append(
                        {
                            "source": f"run:{run_id}",
                            "event_type": event.get("event_type", "?"),
                            "created_at": event.get("created_at", ""),
                            "ref_id": run_id,
                            "summary": _clip(str(event.get("payload", {})), 96),
                            "payload": event.get("payload", {}),
                        }
                    )
            for plan in self._plans[:6]:
                plan_id = getattr(plan, "id", None)
                if not plan_id:
                    continue
                for event in orchestro.db.list_plan_events(plan_id)[-3:]:
                    items.append(
                        {
                            "source": f"plan:{plan_id}",
                            "event_type": getattr(event, "event_type", "?"),
                            "created_at": getattr(event, "created_at", ""),
                            "ref_id": plan_id,
                            "summary": _clip(str(getattr(event, "payload", {})), 96),
                            "payload": getattr(event, "payload", {}),
                        }
                    )
            for job in self._jobs[:8]:
                job_id = getattr(job, "id", None)
                if not job_id:
                    continue
                for event in orchestro.db.list_shell_job_events(job_id)[-3:]:
                    items.append(
                        {
                            "source": f"job:{job_id}",
                            "event_type": getattr(event, "event_type", "?"),
                            "created_at": getattr(event, "created_at", ""),
                            "ref_id": job_id,
                            "summary": _clip(str(getattr(event, "payload", {})), 96),
                            "payload": getattr(event, "payload", {}),
                        }
                    )
            for approval in self._approvals[:8]:
                items.append(
                    {
                        "source": f"approval:{getattr(approval, 'id', '?')}",
                        "event_type": f"approval_{getattr(approval, 'status', '?')}",
                        "created_at": getattr(approval, "created_at", ""),
                        "ref_id": getattr(approval, "id", "-"),
                        "summary": _clip(f"{getattr(approval, 'tool_name', '?')} {getattr(approval, 'argument', '')}", 96),
                        "payload": {
                            "tool_name": getattr(approval, "tool_name", None),
                            "argument": getattr(approval, "argument", None),
                            "pattern": getattr(approval, "pattern", None),
                        },
                    }
                )
            items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
            return items[:40]

        def _refresh_dashboard(self) -> None:
            if self._status_message and time.monotonic() >= self._status_until:
                self._status_message = None
                self._status_until = 0.0
            self._runs = orchestro.db.list_runs(limit=20)
            self._sessions = orchestro.db.list_sessions(limit=12)
            self._plans = orchestro.db.list_plans(limit=12)
            self._approvals = orchestro.db.list_approval_requests(status="pending", limit=12)
            self._jobs = orchestro.db.list_shell_jobs(limit=12)
            self._activity_items = self._build_activity_items()
            if self.selected_run_index >= len(self._runs):
                self.selected_run_index = max(0, len(self._runs) - 1)
            if self.selected_session_index >= len(self._sessions):
                self.selected_session_index = max(0, len(self._sessions) - 1)
            if self.selected_plan_index >= len(self._plans):
                self.selected_plan_index = max(0, len(self._plans) - 1)
            if self.selected_approval_index >= len(self._approvals):
                self.selected_approval_index = max(0, len(self._approvals) - 1)
            if self.selected_job_index >= len(self._jobs):
                self.selected_job_index = max(0, len(self._jobs) - 1)
            if self.selected_activity_index >= len(self._activity_items):
                self.selected_activity_index = max(0, len(self._activity_items) - 1)
            selected_run = self._selected_run()
            selected_run_id = getattr(selected_run, "id", None) if selected_run is not None else None
            selected_session = self._selected_session()
            selected_session_id = getattr(selected_session, "id", None) if selected_session is not None else None
            selected_plan = self._selected_plan()
            selected_plan_id = getattr(selected_plan, "id", None) if selected_plan is not None else None
            selected_approval = self._selected_approval()
            selected_job = self._selected_job()
            selected_job_id = getattr(selected_job, "id", None) if selected_job is not None else None
            selected_label = selected_run_id
            if self.view_mode == "sessions":
                selected_label = selected_session_id
            elif self.view_mode == "plans":
                selected_label = selected_plan_id
            elif self.view_mode == "approvals":
                selected_label = getattr(selected_approval, "id", None)
            elif self.view_mode in {"jobs", "review"}:
                selected_label = selected_job_id
            elif self.view_mode == "activity":
                selected_label = str((self._selected_activity() or {}).get("source", "-"))
            elif self.view_mode == "integrations":
                selected_label = "system"
            run_events = orchestro.db.list_events(selected_run_id) if selected_run_id else []
            session_runs = orchestro.db.list_session_runs(selected_session_id, limit=50) if selected_session_id else []
            plan_steps = orchestro.db.list_plan_steps(selected_plan_id) if selected_plan_id else []
            plan_events = orchestro.db.list_plan_events(selected_plan_id) if selected_plan_id else []
            job_events = orchestro.db.list_shell_job_events(selected_job_id) if selected_job_id else []
            job_inputs = orchestro.db.list_shell_job_inputs(job_id=selected_job_id, status="pending", limit=10) if selected_job_id else []
            review_run = orchestro.db.get_run(getattr(selected_job, "run_id", "")) if self.view_mode == "review" and getattr(selected_job, "run_id", None) else selected_run
            review_run_id = getattr(review_run, "id", None) if review_run is not None else None
            review_events = orchestro.db.list_events(review_run_id) if review_run_id else []
            child_runs = orchestro.db.list_child_runs(review_run_id, limit=20) if review_run_id else []
            diff_title, diff_patch = extract_run_diff(review_run)
            diff_sections = split_diff_files(diff_patch)
            if diff_sections:
                if self._selected_diff_index >= len(diff_sections):
                    self._selected_diff_index = len(diff_sections) - 1
                diff_label, selected_patch = diff_sections[self._selected_diff_index]
                diff_title = f"{diff_title} [{self._selected_diff_index + 1}/{len(diff_sections)}] {diff_label}"
                diff_patch = selected_patch
            else:
                self._selected_diff_index = 0
            statuses = orchestro.backend_statuses()
            mcp_status, lsp_status = self._integration_cache
            if self.view_mode == "integrations":
                mcp_status, lsp_status = self._load_integrations()
                self._integration_cache = (mcp_status, lsp_status)
            hero = format_hero(
                run_count=len(self._runs),
                session_count=len(self._sessions),
                plan_count=len(self._plans),
                mode=self.view_mode,
                selected_label=selected_label,
                backend=backend,
                model_override=model_override,
                strategy=strategy,
                busy=self._busy,
            )
            if self.view_mode == "sessions":
                detail = format_session_detail(selected_session, session_runs)
            elif self.view_mode == "plans":
                detail = format_plan_detail(selected_plan, plan_steps, plan_events)
            elif self.view_mode == "approvals":
                detail = format_approval_detail(selected_approval)
            elif self.view_mode == "jobs":
                detail = format_job_detail(selected_job, job_events, job_inputs)
            elif self.view_mode == "review":
                detail = (
                    f"{format_review_detail(review_run, review_events, child_runs)}\n\n"
                    f"{format_diff_file_list(diff_sections, self._selected_diff_index)}\n\n"
                    f"{format_diff_patch(diff_patch, title=diff_title)}"
                )
            elif self.view_mode == "activity":
                detail = format_activity_detail(self._selected_activity())
            elif self.view_mode == "integrations":
                detail = format_integrations_detail(
                    plugin_loaded=orchestro.plugins.loaded,
                    plugin_load_errors=orchestro.plugins.load_errors,
                    plugin_hook_errors=orchestro.plugins.hooks.last_errors,
                    mcp_status=mcp_status,
                    lsp_status=lsp_status,
                )
            else:
                detail = format_run_detail(selected_run, run_events, self._live_output.get(selected_run_id or "", None))
            if self._editor_visible:
                detail = f"{format_editor_banner(mode=self._editor_mode, context=self._editor_context)}\n\n{detail}"
            if self._last_error:
                detail = f"{detail}\n\nlast error:\n{self._last_error}"
            if self.view_mode == "review":
                nav_panel = format_review_nav(
                    jobs=self._jobs,
                    job_index=self.selected_job_index,
                    diff_sections=diff_sections,
                    diff_index=self._selected_diff_index,
                    focus=self._review_focus,
                )
            elif self.view_mode == "activity":
                nav_panel = format_activity_nav(self._activity_items, self.selected_activity_index)
            else:
                nav_panel = format_nav_panel(
                    mode=self.view_mode,
                    runs=self._runs,
                    sessions=self._sessions,
                    plans=self._plans,
                    approvals=self._approvals,
                    jobs=self._jobs,
                    run_index=self.selected_run_index,
                    session_index=self.selected_session_index,
                    plan_index=self.selected_plan_index,
                    approval_index=self.selected_approval_index,
                    job_index=self.selected_job_index,
                )
            ops = format_ops_panel(
                statuses=statuses,
                sessions=self._sessions,
                plans=self._plans,
                approvals=self._approvals,
                jobs=self._jobs,
                mode=self.view_mode,
                backend=backend,
                model_override=model_override,
                strategy=strategy,
                domain=domain,
                cwd=resolved_cwd,
                autonomous=autonomous,
                busy=self._busy,
                review_focus=self._review_focus,
                editor_visible=self._editor_visible,
                recent_actions=self._recent_actions,
                status_message=self._status_message,
            )
            self.query_one("#hero", Static).update(hero)
            if self._palette_visible:
                suggestions = ["", "Palette suggestions:"]
                if self._palette_suggestions:
                    suggestions.extend(f"  - {item}" for item in self._palette_suggestions)
                elif self._palette_history:
                    suggestions.extend(f"  - {item}" for item in self._palette_history[:5])
                else:
                    suggestions.append("  - focus review")
                    suggestions.append("  - focus integrations")
                    suggestions.append("  - approve")
                ops = f"{ops}\n" + "\n".join(suggestions)
            self.query_one("#nav-pane", Static).update(nav_panel)
            self.query_one("#detail-pane", Static).update(detail)
            self.query_one("#ops-pane", Static).update(ops)
            for button_id, (label, _command, enabled) in action_bar_state(
                mode=self.view_mode,
                editor_visible=self._editor_visible,
                review_focus=self._review_focus,
            ).items():
                button = self.query_one(f"#{button_id}", Button)
                button.label = label or " "
                button.disabled = not enabled

        def _execute_palette_command(self, raw: str) -> None:
            command, arg = parse_palette_command(raw)
            if command == "noop":
                self.action_close_palette()
                return
            if command == "focus" and arg:
                target = arg.lower()
                if target in {"runs", "sessions", "plans", "approvals", "jobs", "review", "integrations", "activity"}:
                    self.view_mode = target
                    self._last_error = None
                else:
                    self._last_error = f"unknown focus target: {arg}"
            elif command == "open" and arg:
                self._open_palette_target(arg)
            elif command == "session-title":
                session = self._selected_session()
                if session is None:
                    self._last_error = "no session selected"
                elif not arg:
                    self._last_error = "session-title requires text"
                else:
                    orchestro.db.update_session(session_id=getattr(session, "id"), title=arg)
                    self._last_error = None
                    self._record_action(f"updated session title for {getattr(session, 'id', '?')}")
            elif command == "session-summary":
                session = self._selected_session()
                if session is None:
                    self._last_error = "no session selected"
                elif not arg:
                    self._last_error = "session-summary requires text"
                else:
                    orchestro.db.update_session(session_id=getattr(session, "id"), summary=arg)
                    self._last_error = None
                    self._record_action(f"updated session summary for {getattr(session, 'id', '?')}")
            elif command == "refresh":
                self._last_error = None
            elif command == "review-focus":
                if self.view_mode != "review":
                    self._last_error = "review-focus only works in review mode"
                elif arg not in {"targets", "files"}:
                    self._last_error = "review-focus requires 'targets' or 'files'"
                else:
                    self._review_focus = arg
                    self._last_error = None
                    self._record_action(f"review focus set to {arg}")
            elif command == "target":
                if self.view_mode != "review":
                    self._last_error = "target only works in review mode"
                elif not arg:
                    self._last_error = "target requires an index"
                else:
                    self._select_review_target(arg)
            elif command == "file":
                if self.view_mode != "review":
                    self._last_error = "file only works in review mode"
                elif not arg:
                    self._last_error = "file requires an index"
                else:
                    self._select_review_file(arg)
            elif command == "approve":
                approval = self._selected_approval()
                if approval is None:
                    self._last_error = "no approval selected"
                else:
                    orchestro.db.resolve_approval_request(request_id=getattr(approval, "id"), status="approved", resolution_note="approved-from-tui")
                    self._last_error = None
                    self._record_action(f"approved {getattr(approval, 'tool_name', '?')} request")
            elif command == "deny":
                approval = self._selected_approval()
                if approval is None:
                    self._last_error = "no approval selected"
                else:
                    orchestro.db.resolve_approval_request(request_id=getattr(approval, "id"), status="denied", resolution_note="denied-from-tui")
                    self._last_error = None
                    self._record_action(f"denied {getattr(approval, 'tool_name', '?')} request")
            elif command == "pause":
                job = self._selected_job()
                if job is None:
                    self._last_error = "no job selected"
                else:
                    orchestro.db.request_shell_job_pause(job_id=getattr(job, "id"), reason="paused-from-tui")
                    self._last_error = None
                    self._record_action(f"pause requested for job {getattr(job, 'id', '?')}")
            elif command == "resume":
                job = self._selected_job()
                if job is None:
                    self._last_error = "no job selected"
                else:
                    orchestro.db.request_shell_job_resume(job_id=getattr(job, "id"), reason="resumed-from-tui")
                    self._last_error = None
                    self._record_action(f"resume requested for job {getattr(job, 'id', '?')}")
            elif command == "cancel":
                job = self._selected_job()
                if job is None:
                    self._last_error = "no job selected"
                else:
                    orchestro.db.request_shell_job_cancel(job_id=getattr(job, "id"), reason="canceled-from-tui")
                    self._last_error = None
                    self._record_action(f"cancel requested for job {getattr(job, 'id', '?')}")
            elif command == "archive-session":
                session = self._selected_session()
                if session is None:
                    self._last_error = "no session selected"
                else:
                    orchestro.db.update_session(session_id=getattr(session, "id"), status="archived")
                    self._last_error = None
                    self._record_action(f"archived session {getattr(session, 'id', '?')}")
            elif command == "activate-session":
                session = self._selected_session()
                if session is None:
                    self._last_error = "no session selected"
                else:
                    orchestro.db.update_session(session_id=getattr(session, "id"), status="active")
                    self._last_error = None
                    self._record_action(f"activated session {getattr(session, 'id', '?')}")
            elif command == "advance-plan":
                plan = self._selected_plan()
                if plan is None:
                    self._last_error = "no plan selected"
                else:
                    orchestro.db.advance_plan(getattr(plan, "id"))
                    self._last_error = None
                    self._record_action(f"advanced plan {getattr(plan, 'id', '?')}")
            elif command == "block-plan":
                plan = self._selected_plan()
                if plan is None:
                    self._last_error = "no plan selected"
                else:
                    orchestro.db.update_plan_status(plan_id=getattr(plan, "id"), status="blocked")
                    self._last_error = None
                    self._record_action(f"blocked plan {getattr(plan, 'id', '?')}")
            elif command == "plan-add":
                plan = self._selected_plan()
                if plan is None:
                    self._last_error = "no plan selected"
                elif not arg:
                    self._last_error = "plan-add requires '<title> | <details>' or '<title>'"
                else:
                    title, details = self._split_title_details(arg)
                    orchestro.db.insert_plan_step(
                        plan_id=getattr(plan, "id"),
                        after_sequence_no=int(getattr(plan, "current_step_no", 1)),
                        title=title,
                        details=details,
                    )
                    self._last_error = None
                    self._record_action(f"added plan step to {getattr(plan, 'id', '?')}: {title}")
            elif command == "plan-edit":
                plan = self._selected_plan()
                if plan is None:
                    self._last_error = "no plan selected"
                elif not arg:
                    self._last_error = "plan-edit requires '<seq> | <title> | <details>'"
                else:
                    seq, title, details = self._parse_plan_edit(arg)
                    if seq is None or not title:
                        self._last_error = "plan-edit requires '<seq> | <title> | <details>'"
                    else:
                        orchestro.db.update_plan_step(
                            plan_id=getattr(plan, "id"),
                            sequence_no=seq,
                            title=title,
                            details=details,
                        )
                        self._last_error = None
                        self._record_action(f"updated plan step {seq} in {getattr(plan, 'id', '?')}")
            elif command == "plan-drop":
                plan = self._selected_plan()
                if plan is None:
                    self._last_error = "no plan selected"
                elif not arg:
                    self._last_error = "plan-drop requires a sequence number"
                else:
                    try:
                        seq = int(arg.strip())
                    except ValueError:
                        self._last_error = "plan-drop requires a numeric sequence number"
                    else:
                        orchestro.db.delete_plan_step(plan_id=getattr(plan, "id"), sequence_no=seq)
                        self._last_error = None
                        self._record_action(f"dropped plan step {seq} from {getattr(plan, 'id', '?')}")
            elif command == "clear-error":
                self._last_error = None
            else:
                self._last_error = f"unknown palette command: {command}"
            self.action_close_palette()
            self._refresh_dashboard()

        def _open_palette_target(self, query: str) -> None:
            lowered = query.lower().strip()
            if not lowered:
                self._last_error = "open requires a search query"
                return
            candidates: list[tuple[str, str]] = []
            run_map: dict[str, int] = {}
            session_map: dict[str, int] = {}
            plan_map: dict[str, int] = {}
            approval_map: dict[str, int] = {}
            job_map: dict[str, int] = {}
            for index, run in enumerate(self._runs):
                key = f"run:{getattr(run, 'id', '')}"
                label = getattr(run, "goal", "") or ""
                candidates.append((key, label))
                run_map[key] = index
            for index, session in enumerate(self._sessions):
                key = f"session:{getattr(session, 'id', '')}"
                label = getattr(session, "title", None) or ""
                candidates.append((key, label))
                session_map[key] = index
            for index, plan in enumerate(self._plans):
                key = f"plan:{getattr(plan, 'id', '')}"
                label = getattr(plan, "goal", "") or ""
                candidates.append((key, label))
                plan_map[key] = index
            for index, approval in enumerate(self._approvals):
                key = f"approval:{getattr(approval, 'id', '')}"
                label = getattr(approval, "tool_name", "") or ""
                candidates.append((key, label))
                approval_map[key] = index
            for index, job in enumerate(self._jobs):
                key = f"job:{getattr(job, 'id', '')}"
                label = getattr(job, "goal", "") or ""
                candidates.append((key, label))
                job_map[key] = index
            ranked = rank_palette_matches(query, candidates)
            if ranked:
                key, _label = ranked[0]
                if key in run_map:
                    self.view_mode = "runs"
                    self.selected_run_index = run_map[key]
                    self._last_error = None
                    return
                if key in session_map:
                    self.view_mode = "sessions"
                    self.selected_session_index = session_map[key]
                    self._last_error = None
                    return
                if key in plan_map:
                    self.view_mode = "plans"
                    self.selected_plan_index = plan_map[key]
                    self._last_error = None
                    return
                if key in approval_map:
                    self.view_mode = "approvals"
                    self.selected_approval_index = approval_map[key]
                    self._last_error = None
                    return
                if key in job_map:
                    self.view_mode = "jobs"
                    self.selected_job_index = job_map[key]
                    self._last_error = None
                    return
            self._last_error = f"no palette match for: {query}"

        @staticmethod
        def _split_title_details(raw: str) -> tuple[str, str | None]:
            if "\n" in raw and "|" not in raw:
                lines = [line.rstrip() for line in raw.splitlines()]
                title = lines[0].strip() if lines else ""
                detail_lines = [line for line in lines[1:] if line.strip()]
                details = "\n".join(detail_lines) if detail_lines else None
                return title, details
            parts = [part.strip() for part in raw.split("|", maxsplit=1)]
            title = parts[0]
            details = parts[1] if len(parts) > 1 and parts[1] else None
            return title, details

        @staticmethod
        def _parse_plan_edit(raw: str) -> tuple[int | None, str | None, str | None]:
            parts = [part.strip() for part in raw.split("|", maxsplit=2)]
            if len(parts) < 2:
                return None, None, None
            try:
                seq = int(parts[0])
            except ValueError:
                return None, None, None
            title = parts[1] or None
            details = parts[2] if len(parts) > 2 and parts[2] else None
            return seq, title, details

        def _load_integrations(self) -> tuple[dict[str, object] | None, dict[str, object] | None]:
            from orchestro.mcp_client import MCPClientManager
            from orchestro.lsp_client import LSPManager

            mcp_status: dict[str, object] | None = None
            lsp_status: dict[str, object] | None = None

            mcp_manager = MCPClientManager()
            configs = mcp_manager.load_config()
            if configs:
                mcp_manager.start_all(configs)
                try:
                    mcp_status = mcp_manager.status()
                finally:
                    mcp_manager.stop_all()

            lsp_manager = LSPManager()
            lsp_configs = lsp_manager.load_config()
            if lsp_configs:
                lsp_status = lsp_manager.status()

            return mcp_status, lsp_status

        def _run_goal(self, goal: str) -> None:
            try:
                prepared = orchestro.start_run(
                    RunRequest(
                        goal=goal,
                        backend_name=backend,
                        strategy_name=strategy,
                        working_directory=resolved_cwd,
                        metadata={
                            **({"domain": domain} if domain else {}),
                            "context_providers": list(context_providers),
                            **({"backend_model": model_override} if model_override else {}),
                        },
                        autonomous=autonomous,
                    )
                )
                run_id = prepared.run_id
                self.call_from_thread(self._refresh_dashboard)
                self.call_from_thread(self._select_after_start, run_id)
                streaming = prepared.backend.capabilities().get("streaming", False)
                if streaming:
                    buffer: list[str] = []

                    def on_chunk(chunk: str) -> None:
                        buffer.append(chunk)
                        self._live_output[run_id] = "".join(buffer)
                        self.call_from_thread(self._refresh_dashboard)

                    orchestro.execute_prepared_run(prepared, on_chunk=on_chunk)
                else:
                    orchestro.execute_prepared_run(prepared)
            except Exception as exc:
                self.call_from_thread(self._finish_run, None, str(exc))
            else:
                self.call_from_thread(self._finish_run, run_id, None)

        def _select_after_start(self, run_id: str) -> None:
            self._refresh_dashboard()
            self._set_selected_run_by_id(run_id)
            self._refresh_dashboard()

        def _finish_run(self, run_id: str | None, error: str | None) -> None:
            if run_id is not None:
                self._live_output.pop(run_id, None)
                self._record_action(f"completed run {run_id}")
            if error:
                self._set_status(f"run failed: {_clip(error, 88)}", ttl=6.0)
            self._last_error = error
            self._busy = False
            self._refresh_dashboard()

    OrchestroTUI().run()
    return 0
