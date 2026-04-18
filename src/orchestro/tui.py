from __future__ import annotations

import difflib
import threading
import time
from dataclasses import dataclass
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


@dataclass(frozen=True)
class WorkspaceSurface:
    primary_mode: str
    detail: str
    panes: tuple[str, str, str, str]


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


def composer_placeholder(view_mode: str, primary_mode: str) -> str:
    if primary_mode == "Review":
        return "Review mode: use the palette for target/file jumps, or switch decks to run a new goal."
    if primary_mode == "Plan":
        return "Plan mode: create or refine tasks, then use palette or buttons to advance execution."
    if primary_mode == "Ops":
        return "Ops mode: monitor approvals, jobs, activity, and integrations. Use the palette for control actions."
    if primary_mode == "Act":
        return "Act mode: describe the coding task, investigation, or tool-using objective and press Enter."
    if view_mode == "sessions":
        return "Session mode: continue the selected thread or switch to runs/plans for active execution."
    return "Ask Orchestro... Enter runs a goal. 1-8 switch workspaces. j/k move selection."


def derive_primary_mode(view_mode: str, *, busy: bool = False) -> str:
    if view_mode == "review":
        return "Review"
    if view_mode == "plans":
        return "Plan"
    if view_mode in {"approvals", "jobs", "integrations", "activity"}:
        return "Ops"
    if busy and view_mode in {"runs", "sessions"}:
        return "Act"
    return "Chat"


def format_mission_strip(
    *,
    primary_mode: str,
    workspace_mode: str,
    objective: str | None,
    backend: str,
    model_override: str | None,
    strategy: str,
    busy: bool,
    autonomous: bool,
    selected_label: str | None,
    approval_count: int,
    job_count: int,
    recent_status: str | None,
) -> str:
    state = "RUNNING" if busy else "READY"
    model = model_override or "-"
    objective_text = _clip(objective or "No active objective selected.", 120)
    selected = selected_label or "-"
    autonomy = "AUTO" if autonomous else "GUIDED"
    status_line = recent_status or f"{approval_count} approvals | {job_count} jobs"
    return "\n".join(
        [
            f" Mission  {objective_text}",
            f" Mode  {primary_mode} / {workspace_mode.upper()}   State  {state}   Control  {autonomy}",
            f" Backend  {backend}   Model  {model}   Strategy  {strategy}   Selected  {selected}",
            f" Status  {status_line}",
        ]
    )


def format_left_rail(
    *,
    view_mode: str,
    primary_mode: str,
    runs: list[object],
    sessions: list[object],
    plans: list[object],
    approvals: list[object],
    jobs: list[object],
    activity_items: list[dict[str, object]],
    statuses: list[dict[str, object]],
    run_index: int,
    session_index: int,
    plan_index: int,
    approval_index: int,
    job_index: int,
    activity_index: int,
    diff_sections: list[tuple[str, dict[str, object]]],
    diff_index: int,
    review_focus: str,
) -> str:
    lines = [
        " ORCHESTRO",
        "",
        " Focus",
        f"  mode {primary_mode}",
        f"  deck {view_mode}",
        "",
        " Alerts",
        f"  approvals {len(approvals)}",
        f"  jobs {len(jobs)}",
        f"  degraded {sum(1 for status in statuses if not status.get('reachable') or status.get('temporarily_unavailable'))}",
        "",
        " Selection",
    ]
    if view_mode == "runs":
        if not runs:
            lines.append("  no runs")
        else:
            lines.extend(f"  {format_run_line(run, selected=index == run_index)}" for index, run in enumerate(runs[:10]))
    elif view_mode == "sessions":
        if not sessions:
            lines.append("  no sessions")
        else:
            lines.extend(
                f"  {format_session_line(session, selected=index == session_index)}"
                for index, session in enumerate(sessions[:10])
            )
    elif view_mode == "plans":
        if not plans:
            lines.append("  no plans")
        else:
            lines.extend(f"  {format_plan_line(plan, selected=index == plan_index)}" for index, plan in enumerate(plans[:10]))
    elif view_mode == "approvals":
        if not approvals:
            lines.append("  no approvals")
        else:
            lines.extend(
                f"  {format_approval_line(approval, selected=index == approval_index)}"
                for index, approval in enumerate(approvals[:10])
            )
    elif view_mode == "jobs":
        if not jobs:
            lines.append("  no jobs")
        else:
            lines.extend(f"  {format_job_line(job, selected=index == job_index)}" for index, job in enumerate(jobs[:10]))
    elif view_mode == "review":
        lines.append(f"  focus {review_focus}")
        lines.append("  targets")
        review_jobs = [
            job for job in jobs if getattr(job, "status", "") in {"running", "paused", "failed", "cancel_requested"}
        ]
        if not review_jobs:
            lines.append("    none")
        else:
            lines.extend(f"    {format_job_line(job, selected=index == job_index)}" for index, job in enumerate(review_jobs[:6]))
        lines.append("")
        lines.append("  files")
        if not diff_sections:
            lines.append("    none")
        else:
            for index, (label, _patch) in enumerate(diff_sections[:8]):
                marker = ">" if index == diff_index else " "
                lines.append(f"    {marker} {_clip(label, 34)}")
    elif view_mode == "integrations":
        lines.append("  backend health")
        for status in statuses[:8]:
            state = "cooldown" if status.get("temporarily_unavailable") else ("up" if status.get("reachable") else "down")
            lines.append(f"   - {_clip(status['name'], 18)} {state}")
    elif view_mode == "activity":
        if not activity_items:
            lines.append("  no activity")
        else:
            lines.extend(
                f"  {format_activity_line(item, selected=index == activity_index)}"
                for index, item in enumerate(activity_items[:12])
            )
    return "\n".join(lines)


def format_workspace_bar(
    *,
    primary_mode: str,
    view_mode: str,
    selected_label: str | None,
    review_focus: str,
    selected_file: str | None,
    busy: bool,
    autonomous: bool,
    tray_focus: str | None,
    tray_expanded: bool,
) -> str:
    modes = [
        ("runs", "Runs"),
        ("sessions", "Sessions"),
        ("plans", "Plans"),
        ("review", "Review"),
        ("approvals", "Approvals"),
        ("jobs", "Jobs"),
        ("integrations", "Integrations"),
        ("activity", "Activity"),
    ]
    tabs = []
    for key, label in modes:
        if key == view_mode:
            tabs.append(f"[ {label.upper()} ]")
        else:
            tabs.append(label)
    selected = selected_label or "-"
    selected_file_label = _clip(selected_file or "-", 36)
    status_bits = [
        f"primary {primary_mode}",
        f"selected {selected}",
        f"review-focus {review_focus}",
        f"file {selected_file_label}",
        f"tray {(tray_focus or 'overview').upper()}:{'max' if tray_expanded else 'grid'}",
        f"state {'running' if busy else 'ready'}",
        f"control {'auto' if autonomous else 'guided'}",
    ]
    return "\n".join(["  ".join(tabs), " | ".join(status_bits)])


def format_command_meta(
    *,
    backend: str,
    model_override: str | None,
    strategy: str,
    domain: str | None,
    providers: list[str],
    autonomous: bool,
    primary_mode: str,
    nav_visible: bool,
    ops_visible: bool,
    tray_focus: str | None,
    tray_expanded: bool,
) -> str:
    provider_text = ", ".join(providers[:4]) if providers else "none"
    if len(providers) > 4:
        provider_text += ", ..."
    layout = f"layout nav:{'on' if nav_visible else 'off'} ops:{'on' if ops_visible else 'off'}"
    tray = f"tray {(tray_focus or 'overview')}:{'max' if tray_expanded else 'grid'}"
    return (
        f"compose on {primary_mode.lower()} | backend {backend} | model {model_override or '-'} | "
        f"strategy {strategy} | domain {domain or '-'} | providers {provider_text} | "
        f"control {'auto' if autonomous else 'guided'} | {layout} | {tray}"
    )


def format_mode_guide(
    *,
    primary_mode: str,
    view_mode: str,
    editor_visible: bool,
    review_focus: str,
    busy: bool,
    selected_label: str | None,
    status_message: str | None,
    tray_focus: str | None,
    tray_expanded: bool,
) -> str:
    selected = selected_label or "-"
    if editor_visible:
        hint = "Editor active: Ctrl+S saves, Esc closes. Workspace controls now operate on the editor."
    elif primary_mode == "Review":
        hint = (
            f"Review {selected}. Focus is {review_focus}. Use workspace controls or palette prev-target/next-target "
            "and file/target jumps."
        )
    elif primary_mode == "Plan":
        hint = (
            f"Plan {selected}. Use Prev Step / Next Step to move the active step, then Advance or Add Step "
            "from workspace controls."
        )
    elif primary_mode == "Ops":
        hint = (
            f"Ops surface {view_mode}. Use workspace controls for approval, job, activity, or integration flow "
            "without leaving the deck."
        )
    elif primary_mode == "Act":
        hint = (
            f"Active execution on {selected}. Watch execution timeline, touched files, and result stream while the run "
            f"is {'running' if busy else 'ready'}."
        )
    else:
        hint = (
            f"Chat context on {selected}. Use the composer for the next prompt and the workspace switcher when the task "
            "moves into plan, review, or ops."
        )
    status = status_message or ("busy" if busy else "ready")
    tray = f"tray {(tray_focus or 'overview').upper()} {'max' if tray_expanded else 'grid'}"
    return f"{primary_mode} / {view_mode} | selected {selected} | status {status} | {tray}\n{hint}"


def format_help_overlay(
    *,
    primary_mode: str,
    view_mode: str,
    review_focus: str,
    nav_visible: bool,
    ops_visible: bool,
    tray_focus: str | None,
    tray_expanded: bool,
) -> str:
    return compose_workspace(
        [
            format_card(
                "Quick Help",
                [
                    "Global Keys",
                    "",
                    "  1-8        switch workspace",
                    "  j / k      move selection",
                    "  Ctrl+P     open palette",
                    "  F1         toggle help",
                    "  Ctrl+H     toggle left rail",
                    "  Ctrl+L     toggle ops dock",
                    "  z          focus center / restore side panes",
                    "  Ctrl+1-4   focus tray pane",
                    "  Ctrl+0     tray overview",
                    "  q          quit",
                ],
            ),
            format_card(
                "Mode Guide",
                [
                    f"Current Mode: {primary_mode} / {view_mode}",
                    "",
                    f"tray focus: {(tray_focus or 'overview').upper()} ({'max' if tray_expanded else 'grid'})",
                    "",
                    *(
                        [
                            f"review focus: {review_focus}",
                            "Tab toggles target/file focus.",
                            "[ / ] moves the current diff file.",
                            "pick <n> activates a visible selector item.",
                        ]
                        if primary_mode == "Review"
                        else [
                            "e edits, a adds, x drops the current plan item.",
                            "pick <n> activates a visible selector item.",
                            "Workspace controls stay context-aware.",
                        ]
                        if primary_mode == "Plan"
                        else [
                            "pick <n> selects the visible approval/job/integration/activity item.",
                            "Use palette commands like approve, deny, pause, resume, cancel.",
                        ]
                        if primary_mode == "Ops"
                        else [
                            "Enter submits the current prompt.",
                            "pick <n> activates a visible selector item.",
                            "Workspace switcher changes deck.",
                        ]
                    ),
                ],
            ),
            format_card(
                "Layout",
                [
                    f"left rail: {'visible' if nav_visible else 'hidden'}",
                    f"ops dock:  {'visible' if ops_visible else 'hidden'}",
                    "",
                    "Use z to focus the center workspace when you want a cleaner reading or editing surface.",
                ],
            ),
        ]
    )


def workspace_switcher_state(view_mode: str) -> dict[str, tuple[str, str, bool]]:
    items = [
        ("ws-runs", "runs", "Runs"),
        ("ws-sessions", "sessions", "Sessions"),
        ("ws-plans", "plans", "Plans"),
        ("ws-review", "review", "Review"),
        ("ws-approvals", "approvals", "Approvals"),
        ("ws-jobs", "jobs", "Jobs"),
        ("ws-integrations", "integrations", "Integrations"),
        ("ws-activity", "activity", "Activity"),
    ]
    state: dict[str, tuple[str, str, bool]] = {}
    for button_id, mode, label in items:
        state[button_id] = (label, f"focus-{mode}", mode == view_mode)
    return state


def workspace_tray_state(
    labels: list[str],
    *,
    focus: str | None,
    expanded: bool,
) -> dict[str, tuple[str, str | None, bool, bool]]:
    slots = ["a", "b", "c", "d"]
    state: dict[str, tuple[str, str | None, bool, bool]] = {}
    for index, slot in enumerate(slots):
        label = labels[index] if index < len(labels) else f"Pane {index + 1}"
        state[f"tp-{slot}"] = (_clip(label, 16), f"focus-tray:{slot}", focus == slot, bool(label))
    state["tp-max"] = (
        "Overview" if expanded else "Maximize",
        "toggle-tray-max",
        expanded,
        True,
    )
    return state


def workspace_controls_state(
    *,
    mode: str,
    editor_visible: bool,
    review_focus: str,
) -> dict[str, tuple[str, str | None, bool]]:
    if editor_visible:
        return {
            "wc-1": ("Save", "save-editor", True),
            "wc-2": ("Close", "close-editor", True),
            "wc-3": ("", None, False),
            "wc-4": ("", None, False),
            "wc-5": ("Palette", "toggle-palette", True),
        }
    if mode == "review":
        toggle = "Focus Files" if review_focus == "targets" else "Focus Targets"
        prev_label = "Prev Target" if review_focus == "targets" else "Prev File"
        next_label = "Next Target" if review_focus == "targets" else "Next File"
        return {
            "wc-1": (toggle, "toggle-review-focus", True),
            "wc-2": (prev_label, "review-prev", True),
            "wc-3": (next_label, "review-next", True),
            "wc-4": ("Jobs", "focus-jobs", True),
            "wc-5": ("Palette", "toggle-palette", True),
        }
    if mode == "plans":
        return {
            "wc-1": ("Prev Step", "prev-plan-step", True),
            "wc-2": ("Next Step", "next-plan-step", True),
            "wc-3": ("Advance", "advance-plan", True),
            "wc-4": ("Add Step", "add-plan-step", True),
            "wc-5": ("Palette", "toggle-palette", True),
        }
    if mode == "sessions":
        return {
            "wc-1": ("Edit Title", "edit-session-title", True),
            "wc-2": ("Edit Summary", "edit-session-summary", True),
            "wc-3": ("Archive", "archive-session", True),
            "wc-4": ("Activate", "activate-session", True),
            "wc-5": ("Palette", "toggle-palette", True),
        }
    if mode == "approvals":
        return {
            "wc-1": ("Approve", "approve", True),
            "wc-2": ("Deny", "deny", True),
            "wc-3": ("Activity", "focus-activity", True),
            "wc-4": ("", None, False),
            "wc-5": ("Palette", "toggle-palette", True),
        }
    if mode == "jobs":
        return {
            "wc-1": ("Pause", "pause", True),
            "wc-2": ("Resume", "resume", True),
            "wc-3": ("Cancel", "cancel", True),
            "wc-4": ("Review", "focus-review", True),
            "wc-5": ("Palette", "toggle-palette", True),
        }
    if mode == "integrations":
        return {
            "wc-1": ("Refresh", "refresh", True),
            "wc-2": ("Runs", "focus-runs", True),
            "wc-3": ("Jobs", "focus-jobs", True),
            "wc-4": ("", None, False),
            "wc-5": ("Palette", "toggle-palette", True),
        }
    if mode == "activity":
        return {
            "wc-1": ("Refresh", "refresh", True),
            "wc-2": ("Review", "focus-review", True),
            "wc-3": ("Approvals", "focus-approvals", True),
            "wc-4": ("Jobs", "focus-jobs", True),
            "wc-5": ("Palette", "toggle-palette", True),
        }
    if mode == "runs":
        return {
            "wc-1": ("Refresh", "refresh", True),
            "wc-2": ("Plans", "focus-plans", True),
            "wc-3": ("Review", "focus-review", True),
            "wc-4": ("Activity", "focus-activity", True),
            "wc-5": ("Palette", "toggle-palette", True),
        }
    return {
        "wc-1": ("Refresh", "refresh", True),
        "wc-2": ("Runs", "focus-runs", True),
        "wc-3": ("Plans", "focus-plans", True),
        "wc-4": ("Review", "focus-review", True),
        "wc-5": ("Palette", "toggle-palette", True),
    }


def contextual_selector_state(
    *,
    mode: str,
    review_focus: str,
    integration_focus: str | None,
    runs: list[object],
    run_index: int,
    sessions: list[object],
    session_index: int,
    plans: list[object],
    plan_index: int,
    plan_steps: list[object],
    approvals: list[object],
    approval_index: int,
    jobs: list[object],
    job_index: int,
    activity_items: list[dict[str, object]],
    activity_index: int,
    diff_sections: list[tuple[str, dict[str, object]]],
    diff_index: int,
    integration_options: list[tuple[str, str]],
) -> dict[str, tuple[str, str | None, bool]]:
    def _window(length: int, selected: int, size: int = 6) -> tuple[int, int]:
        if length <= size:
            return 0, length
        start = max(0, min(selected - size // 2, length - size))
        return start, start + size

    items: list[tuple[str, str | None, bool]] = []
    if mode == "runs":
        start, end = _window(len(runs), run_index)
        for index in range(start, end):
            label = _clip(getattr(runs[index], "goal", "") or getattr(runs[index], "id", "?"), 18)
            items.append((label, f"select-run:{index}", index == run_index))
    elif mode == "sessions":
        start, end = _window(len(sessions), session_index)
        for index in range(start, end):
            label = _clip(getattr(sessions[index], "title", None) or getattr(sessions[index], "id", "?"), 18)
            items.append((label, f"select-session:{index}", index == session_index))
    elif mode == "plans":
        start, end = _window(len(plan_steps), max(0, int(plan_index if not plan_steps else 0)))
        current_step_no = int(getattr(plans[plan_index], "current_step_no", 1)) if plans and plan_index < len(plans) else 1
        selected_idx = 0
        for idx, step in enumerate(plan_steps):
            if int(getattr(step, "sequence_no", 0)) == current_step_no:
                selected_idx = idx
                break
        start, end = _window(len(plan_steps), selected_idx)
        for index in range(start, end):
            seq = int(getattr(plan_steps[index], "sequence_no", index + 1))
            label = _clip(f"{seq}. {getattr(plan_steps[index], 'title', '-')}", 18)
            items.append((label, f"select-plan-step:{seq}", seq == current_step_no))
    elif mode == "review":
        if review_focus == "files":
            start, end = _window(len(diff_sections), diff_index)
            for index in range(start, end):
                label = _clip(diff_sections[index][0], 18)
                items.append((label, f"select-review-file:{index + 1}", index == diff_index))
        else:
            review_jobs = [job for job in jobs if getattr(job, "status", "") in {"running", "paused", "failed", "cancel_requested"}]
            selected_id = getattr(jobs[job_index], "id", None) if jobs and job_index < len(jobs) else None
            review_selected = 0
            for idx, job in enumerate(review_jobs):
                if getattr(job, "id", None) == selected_id:
                    review_selected = idx
                    break
            start, end = _window(len(review_jobs), review_selected)
            for index in range(start, end):
                label = _clip(getattr(review_jobs[index], "goal", "") or getattr(review_jobs[index], "id", "?"), 18)
                items.append((label, f"select-review-target:{index + 1}", index == review_selected))
    elif mode == "approvals":
        start, end = _window(len(approvals), approval_index)
        for index in range(start, end):
            label = _clip(getattr(approvals[index], "tool_name", "?"), 18)
            items.append((label, f"select-approval:{index}", index == approval_index))
    elif mode == "jobs":
        start, end = _window(len(jobs), job_index)
        for index in range(start, end):
            label = _clip(getattr(jobs[index], "goal", "") or getattr(jobs[index], "id", "?"), 18)
            items.append((label, f"select-job:{index}", index == job_index))
    elif mode == "activity":
        start, end = _window(len(activity_items), activity_index)
        for index in range(start, end):
            label = _clip(str(activity_items[index].get("summary", "")) or str(activity_items[index].get("source", "?")), 18)
            items.append((label, f"select-activity:{index}", index == activity_index))
    elif mode == "integrations":
        selected_idx = 0
        for idx, (_label, slug) in enumerate(integration_options):
            if slug == integration_focus:
                selected_idx = idx
                break
        start, end = _window(len(integration_options), selected_idx)
        for index in range(start, end):
            label, slug = integration_options[index]
            items.append((_clip(label, 18), f"select-integration:{slug}", slug == integration_focus))
    else:
        items = []
    state: dict[str, tuple[str, str | None, bool]] = {}
    for slot in range(6):
        button_id = f"sel-{slot + 1}"
        if slot < len(items):
            state[button_id] = items[slot]
        else:
            state[button_id] = ("", None, False)
    return state


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
    focus: str | None = None,
) -> str:
    plugin_lines = ["Plugins:"]
    if not plugin_loaded:
        plugin_lines.append("  loaded: none")
    else:
        for meta in plugin_loaded[:8]:
            plugin_lines.append(f"  - {getattr(meta, 'name', '?')} {getattr(meta, 'version', '')}".rstrip())
    if plugin_load_errors:
        plugin_lines.append("  load errors:")
        for item in plugin_load_errors[:6]:
            plugin_lines.append(f"    - {item.get('plugin', '?')}: {_clip(item.get('error'), 90)}")
    if plugin_hook_errors:
        plugin_lines.append("  hook errors:")
        for item in plugin_hook_errors[:6]:
            plugin_lines.append(f"    - {item.get('hook', '?')} / {item.get('plugin', '?')}: {_clip(item.get('error'), 80)}")

    mcp_lines = ["MCP:"]
    if not mcp_status:
        mcp_lines.append("  unavailable")
    else:
        mcp_lines.append(f"  connected: {', '.join(mcp_status.get('connected', [])) or 'none'}")
        mcp_lines.append(f"  degraded: {', '.join(mcp_status.get('degraded', [])) or 'none'}")
        if mcp_status.get("degraded_details"):
            for name, detail in sorted(mcp_status["degraded_details"].items()):
                mcp_lines.append(f"    - {name}: {_clip(detail, 88)}")
        mcp_lines.append(f"  tools: {mcp_status.get('tool_count', 0)}")

    lsp_lines = ["LSP:"]
    if not lsp_status:
        lsp_lines.append("  unavailable")
    else:
        lsp_lines.append(f"  configured: {', '.join(lsp_status.get('configured', [])) or 'none'}")
        lsp_lines.append(f"  degraded: {', '.join(lsp_status.get('degraded', [])) or 'none'}")
        if lsp_status.get("degraded_details"):
            for name, detail in sorted(lsp_status["degraded_details"].items()):
                lsp_lines.append(f"    - {name}: {_clip(detail, 88)}")
        lsp_lines.append(f"  languages: {', '.join(lsp_status.get('supported_languages', [])) or 'none'}")

    blocks = {
        "plugins": plugin_lines,
        "mcp": mcp_lines,
        "lsp": lsp_lines,
    }
    preferred = focus if focus in blocks else None
    ordered = [preferred] if preferred else []
    ordered.extend(key for key in ("plugins", "mcp", "lsp") if key != preferred)
    lines = ["Integrations", "", f"focus: {preferred or 'overview'}"]
    for key in ordered:
        lines.extend([""] + blocks[key])
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


def format_card(title: str, body: list[str]) -> str:
    content = body or ["-"]
    width = max(len(title) + 4, *(len(line) for line in content), 24)
    border = "=" * min(max(width, 24), 88)
    lines = [border, f"[ {title.upper()} ]", border]
    lines.extend(content)
    lines.append(border)
    return "\n".join(lines).rstrip()


def compose_workspace(cards: list[str]) -> str:
    return "\n\n".join(card for card in cards if card.strip())


def format_metric_bar(label: str, value: int, total: int, *, width: int = 16) -> str:
    safe_total = max(total, 1)
    filled = min(width, max(0, round((value / safe_total) * width)))
    bar = "#" * filled + "." * (width - filled)
    return f"{label:<8} [{bar}] {value}/{total}"


def format_plan_lane(title: str, items: list[str]) -> list[str]:
    lines = [title]
    if not items:
        lines.append("  - none")
    else:
        lines.extend(f"  - {item}" for item in items)
    return lines


def format_file_tree(labels: list[str], *, selected_index: int | None = None) -> list[str]:
    if not labels:
        return ["No changed files."]
    grouped: dict[str, list[tuple[int, str]]] = {}
    for index, label in enumerate(labels):
        parts = label.split()
        candidate = parts[-1] if parts else label
        normalized = candidate[2:] if candidate.startswith(("a/", "b/")) else candidate
        parts = [part for part in normalized.split("/") if part]
        group = parts[0] if len(parts) > 1 else "root"
        grouped.setdefault(group, []).append((index, parts[-1] if parts else normalized))
    lines: list[str] = []
    for group in sorted(grouped):
        lines.append(f"{group}/")
        for index, leaf in grouped[group]:
            marker = ">" if selected_index == index else " "
            lines.append(f"  {marker} {index + 1:>2}. {leaf}")
    return lines


def format_timeline(title: str, items: list[str]) -> list[str]:
    lines = [title]
    if not items:
        lines.append("  - none")
        return lines
    for item in items:
        lines.append(f"  * {item}")
    return lines


def format_state_pills(items: list[str]) -> list[str]:
    if not items:
        return ["(none)"]
    return [" | ".join(item.strip() for item in items if item.strip())]


def format_agent_loop(
    *,
    primary_mode: str,
    busy: bool,
    approvals: int = 0,
    jobs: int = 0,
    reroutes: int = 0,
    retries: int = 0,
    tools: int = 0,
    status_message: str | None = None,
) -> list[str]:
    if primary_mode == "Review":
        steps = ["Inspect", "Diff", "Verify", "Decide"]
    elif primary_mode == "Plan":
        steps = ["Scope", "Board", "Sequence", "Execute"]
    elif primary_mode == "Ops":
        steps = ["Watch", "Gate", "Recover", "Learn"]
    elif busy:
        steps = ["Think", "Inspect", "Edit", "Verify"]
    else:
        steps = ["Ready", "Prompt", "Route", "Run"]
    trail = " -> ".join(steps)
    metrics = [
        f"approvals {approvals}",
        f"jobs {jobs}",
        f"tools {tools}",
        f"reroutes {reroutes}",
        f"retries {retries}",
    ]
    lines = [trail, "", *format_state_pills(metrics)]
    if status_message:
        lines.extend(["", f"latest: {status_message}"])
    return lines


def format_workspace_widget(title: str, lines: list[str]) -> str:
    body = lines or ["-"]
    return "\n".join([title, "", *body])


def format_checklist(title: str, items: list[tuple[str, bool]]) -> list[str]:
    lines = [title]
    if not items:
        lines.append("  [ ] none")
        return lines
    for label, done in items:
        mark = "x" if done else " "
        lines.append(f"  [{mark}] {label}")
    return lines


def format_signal_meter(label: str, value: int, total: int, *, width: int = 10) -> str:
    safe_total = max(total, 1)
    safe_value = max(0, min(value, safe_total))
    filled = min(width, max(0, round((safe_value / safe_total) * width)))
    bar = "#" * filled + "." * (width - filled)
    return f"{label:<10} [{bar}] {safe_value}/{safe_total}"


def format_mode_status_summary(
    *,
    primary_mode: str,
    selected_label: str | None,
    busy: bool,
    status_message: str | None,
    controls_hint: str,
    metrics: list[str],
) -> list[str]:
    lines = [
        f"mode: {primary_mode}",
        f"selected: {selected_label or '-'}",
        f"state: {'running' if busy else 'ready'}",
        f"status: {status_message or '-'}",
        "",
        f"controls: {controls_hint}",
    ]
    if metrics:
        lines.extend(["", *metrics])
    return lines


def format_review_widgets(
    *,
    diff_sections: list[tuple[str, dict[str, object]]],
    selected_diff_index: int,
    events: list[dict[str, object]],
) -> tuple[str, str, str, str]:
    file_lines = format_file_tree([label for label, _patch in diff_sections], selected_index=selected_diff_index)
    selected_file = (
        diff_sections[selected_diff_index][0]
        if diff_sections and selected_diff_index < len(diff_sections)
        else "-"
    )
    summary_lines = format_mode_status_summary(
        primary_mode="Review",
        selected_label=selected_file,
        busy=False,
        status_message=None,
        controls_hint="wc-1 toggles target/file focus; wc-2/wc-3 move selection",
        metrics=[
            f"files: {len(diff_sections)}",
            f"tool calls: {sum(1 for event in events if event.get('event_type') == 'tool_called')}",
            f"approvals: {sum(1 for event in events if event.get('event_type') == 'approval_requested')}",
        ],
    )
    review_signal_lines = [
        format_signal_meter("evidence", min(len(events), 6), 6),
        format_signal_meter("risk", sum(1 for event in events if event.get("event_type") in {"approval_requested", "backend_auto_rerouted", "retry_scheduled"}), 6),
    ]
    evidence_lines = [
        f"selected file: {selected_file}",
        f"file index: {selected_diff_index + 1}/{len(diff_sections) or 1}",
        f"tool calls: {sum(1 for event in events if event.get('event_type') == 'tool_called')}",
        f"approvals: {sum(1 for event in events if event.get('event_type') == 'approval_requested')}",
        f"reroutes: {sum(1 for event in events if event.get('event_type') == 'backend_auto_rerouted')}",
        f"retries: {sum(1 for event in events if event.get('event_type') == 'retry_scheduled')}",
        "",
        "move: wc-2 / wc-3 or prev-target / next-target",
    ]
    checklist_lines = format_checklist(
        "Review Checklist",
        [
            ("diff loaded", bool(diff_sections)),
            ("tool evidence present", any(event.get("event_type") == "tool_called" for event in events)),
            ("approval gates inspected", any(event.get("event_type") == "approval_requested" for event in events)),
            ("reroutes inspected", any(event.get("event_type") == "backend_auto_rerouted" for event in events)),
        ],
    )
    timeline_lines = format_timeline(
        "Latest Review Events",
        [
            f"{event.get('event_type', '?')}: {_clip(str(event.get('payload', {})), 72)}"
            for event in events[-6:]
        ],
    )
    return (
        format_workspace_widget("Review Status", summary_lines + ["", *review_signal_lines]),
        format_workspace_widget("Changed Files", file_lines + ["", "legend: '>' marks the active file"]),
        format_workspace_widget("Evidence", evidence_lines + ["", *checklist_lines]),
        format_workspace_widget("Review Timeline", timeline_lines),
    )


def format_chat_widgets(
    *,
    run: object | None,
    events: list[dict[str, object]],
    recent_actions: list[str] | None,
    status_message: str | None,
) -> tuple[str, str, str, str]:
    metadata = getattr(run, "metadata", {}) or {} if run is not None else {}
    summary_lines = format_mode_status_summary(
        primary_mode="Chat",
        selected_label=getattr(run, "id", None) if run is not None else None,
        busy=False,
        status_message=status_message,
        controls_hint="composer submits next turn; workspace switcher changes deck",
        metrics=[
            f"context events: {sum(1 for event in events if event.get('event_type') in {'instruction_context_loaded', 'context_providers_selected'})}",
            f"recent actions: {len(recent_actions or [])}",
        ],
    )
    chat_signal_lines = [
        format_signal_meter("context", min(sum(1 for event in events if event.get("event_type") in {"instruction_context_loaded", "context_providers_selected"}), 4), 4),
        format_signal_meter("momentum", min(len(recent_actions or []), 4), 4),
    ]
    context_lines = [
        f"run: {getattr(run, 'id', '-') if run is not None else '-'}",
        f"backend: {getattr(run, 'backend_name', '-') if run is not None else '-'}",
        f"model: {metadata.get('backend_model') or '-'}",
        f"domain: {metadata.get('domain') or '-'}",
        f"status: {getattr(run, 'status', '-') if run is not None else '-'}",
    ]
    memory_lines = []
    for event in events:
        if event.get("event_type") in {"instruction_context_loaded", "context_providers_selected"}:
            memory_lines.append(_clip(str(event.get("payload", {})), 88))
    context_checklist = format_checklist(
        "Context Checklist",
        [
            ("run selected", run is not None),
            ("memory loaded", bool(memory_lines)),
            ("recent activity available", bool(recent_actions)),
        ],
    )
    suggestion_lines = [f"- {item}" for item in (recent_actions or [])[:4]]
    if status_message:
        suggestion_lines.insert(0, f"status: {status_message}")
    if not suggestion_lines:
        suggestion_lines = [
            "- ask for a summary",
            "- ask for a plan",
            "- switch to review after a coding run",
        ]
    suggestion_lines.extend(["", "controls: workspace switcher changes deck, composer submits next turn"])
    return (
        format_workspace_widget("Chat Status", summary_lines + ["", *chat_signal_lines]),
        format_workspace_widget("Conversation Context", context_lines),
        format_workspace_widget("Loaded Context", (memory_lines or ["No retrieved context loaded yet."]) + ["", *context_checklist]),
        format_workspace_widget("Suggested Next Moves", suggestion_lines),
    )


def format_act_widgets(
    *,
    run: object | None,
    events: list[dict[str, object]],
    diff_sections: list[tuple[str, dict[str, object]]],
    selected_diff_index: int,
    live_output: str | None,
) -> tuple[str, str, str, str]:
    summary_lines = format_mode_status_summary(
        primary_mode="Act",
        selected_label=getattr(run, "id", None) if run is not None else None,
        busy=True,
        status_message=getattr(run, "status", None) if run is not None else None,
        controls_hint="watch timeline, use review deck for diffs, workspace controls move file focus",
        metrics=[
            f"events: {len(events)}",
            f"files: {len(diff_sections)}",
            f"reroutes: {sum(1 for event in events if event.get('event_type') == 'backend_auto_rerouted')}",
            f"retries: {sum(1 for event in events if event.get('event_type') == 'retry_scheduled')}",
        ],
    )
    act_signal_lines = [
        format_signal_meter("trace", min(len(events), 8), 8),
        format_signal_meter("files", min(len(diff_sections), 6), 6),
        format_signal_meter("output", 1 if (live_output or getattr(run, "final_output", None)) else 0, 1),
    ]
    trace_lines = [
        f"{event.get('event_type', '?')}: {_clip(str(event.get('payload', {})), 76)}"
        for event in events[-6:]
    ] or ["No execution trace yet."]
    tool_calls = sum(1 for event in events if event.get("event_type") == "tool_called")
    tool_results = sum(1 for event in events if event.get("event_type") == "tool_result")
    trace_lines.extend(
        [
            "",
            f"tool calls: {tool_calls}",
            f"tool results: {tool_results}",
        ]
    )
    file_lines = format_file_tree([label for label, _patch in diff_sections], selected_index=selected_diff_index)
    if diff_sections:
        file_lines.extend(["", f"selected file: {diff_sections[selected_diff_index][0]}", "controls: wc-2 / wc-3 move file focus"])
    output = (live_output or getattr(run, "final_output", None) or "").splitlines()
    output_lines = output[:8] or ["No live output yet."]
    output_lines.extend(
        [
            "",
            *format_checklist(
                "Execution Checklist",
                [
                    ("trace visible", bool(events)),
                    ("file evidence visible", bool(diff_sections)),
                    ("output visible", bool(live_output or getattr(run, "final_output", None))),
                ],
            ),
        ]
    )
    return (
        format_workspace_widget("Act Status", summary_lines + ["", *act_signal_lines]),
        format_workspace_widget("Execution Timeline", format_timeline("Latest Execution", trace_lines)),
        format_workspace_widget("Touched Files", file_lines),
        format_workspace_widget("Result Stream", output_lines),
    )


def format_plan_widgets(
    *,
    steps: list[object],
    current_step_no: int | None,
) -> tuple[str, str, str, str]:
    lanes = {"Done": [], "Active": [], "Pending": [], "Blocked": []}
    for step in steps[:12]:
        status = str(getattr(step, "status", "pending") or "pending")
        item = f"{getattr(step, 'sequence_no', '?')}. {getattr(step, 'title', '-')}"
        if getattr(step, "sequence_no", None) == current_step_no and status not in {"done", "blocked"}:
            lanes["Active"].append(item)
        elif status == "done":
            lanes["Done"].append(item)
        elif status == "blocked":
            lanes["Blocked"].append(item)
        else:
            lanes["Pending"].append(item)
    board_lines = [
        *format_plan_lane("Done", lanes["Done"]),
        "",
        *format_plan_lane("Active", lanes["Active"]),
        "",
        *format_plan_lane("Pending", lanes["Pending"]),
        "",
        *format_plan_lane("Blocked", lanes["Blocked"]),
    ]
    progress_lines = [
        format_metric_bar("done", len(lanes["Done"]), len(steps)),
        format_metric_bar("active", len(lanes["Active"]), len(steps)),
        format_metric_bar("pending", len(lanes["Pending"]), len(steps)),
        format_metric_bar("blocked", len(lanes["Blocked"]), len(steps)),
    ]
    current_step = next(
        (step for step in steps if getattr(step, "sequence_no", None) == current_step_no),
        None,
    )
    summary_lines = format_mode_status_summary(
        primary_mode="Plan",
        selected_label=str(current_step_no) if current_step_no is not None else None,
        busy=False,
        status_message=None,
        controls_hint="wc-1/wc-2 move step selection; wc-3 advances; wc-4 adds a step",
        metrics=[
            f"total: {len(steps)}",
            f"done: {len(lanes['Done'])}",
            f"active: {len(lanes['Active'])}",
            f"blocked: {len(lanes['Blocked'])}",
        ],
    )
    plan_signal_lines = [
        format_signal_meter("done", len(lanes["Done"]), len(steps) or 1),
        format_signal_meter("active", len(lanes["Active"]), len(steps) or 1),
        format_signal_meter("blocked", len(lanes["Blocked"]), len(steps) or 1),
    ]
    progress_lines.extend(
        [
            "",
            f"selected step: {current_step_no or '-'}",
            f"title: {getattr(current_step, 'title', '-') if current_step is not None else '-'}",
            f"details: {_clip(getattr(current_step, 'details', None), 64) if current_step is not None else '-'}",
            "",
            "move: wc-1 / wc-2 or prev-step / next-step",
        ]
    )
    progress_lines.extend(
        [
            "",
            *format_checklist(
                "Plan Checklist",
                [
                    ("board populated", bool(steps)),
                    ("active step selected", current_step is not None),
                    ("next move available", any(lanes[name] for name in ("Active", "Pending", "Blocked"))),
                ],
            ),
        ]
    )
    next_moves = []
    if lanes["Active"]:
        next_moves.append(f"finish {lanes['Active'][0]}")
    if lanes["Blocked"]:
        next_moves.append(f"unblock {lanes['Blocked'][0]}")
    if lanes["Pending"]:
        next_moves.append(f"queue {lanes['Pending'][0]}")
    return (
        format_workspace_widget("Plan Status", summary_lines + ["", *plan_signal_lines]),
        format_workspace_widget("Plan Board", board_lines + ["", "legend: active step appears in the Active lane"]),
        format_workspace_widget("Progress Bars", progress_lines),
        format_workspace_widget("Next Moves", next_moves or ["No next move suggestions."]),
    )


def format_ops_widgets(
    *,
    mode: str,
    job_events: list[object],
    job_inputs: list[object],
    recent_actions: list[str] | None,
    status_message: str | None,
    activity: dict[str, object] | None = None,
) -> tuple[str, str, str, str]:
    summary_lines = format_mode_status_summary(
        primary_mode="Ops",
        selected_label=str(activity.get("source")) if activity is not None else mode,
        busy=mode in {"jobs", "approvals"},
        status_message=status_message,
        controls_hint="workspace controls operate on the current ops deck",
        metrics=[
            f"job events: {len(job_events)}",
            f"pending inputs: {len(job_inputs)}",
            f"recent actions: {len(recent_actions or [])}",
        ],
    )
    ops_signal_lines = [
        format_signal_meter("events", min(len(job_events), 8), 8),
        format_signal_meter("inputs", min(len(job_inputs), 4), 4),
        format_signal_meter("actions", min(len(recent_actions or []), 5), 5),
    ]
    loop_lines = format_timeline(
        "Live Loop",
        [
            f"{getattr(event, 'event_type', '?')}: {_clip(str(getattr(event, 'payload', {})), 72)}"
            for event in job_events[-6:]
        ],
    )
    gate_lines = [
        f"pending inputs: {len(job_inputs)}",
        f"recent actions: {len(recent_actions or [])}",
        f"mode: {mode}",
        f"status: {status_message or '-'}",
        "controls: workspace controls drive the active ops deck",
    ]
    gate_lines.extend(
        [
            "",
            *format_checklist(
                "Ops Checklist",
                [
                    ("events available", bool(job_events)),
                    ("operator inputs pending", bool(job_inputs)),
                    ("recent actions visible", bool(recent_actions)),
                ],
            ),
        ]
    )
    if activity is not None:
        feed_lines = [
            f"source: {activity.get('source', '-')}",
            f"type: {activity.get('event_type', '-')}",
            f"summary: {_clip(str(activity.get('summary', '-')), 72)}",
        ]
    else:
        feed_lines = [f"- {item}" for item in (recent_actions or [])[:5]] or ["No recent actions."]
    return (
        format_workspace_widget("Ops Status", summary_lines + ["", *ops_signal_lines]),
        format_workspace_widget("Mission Feed", loop_lines),
        format_workspace_widget("Gates", gate_lines),
        format_workspace_widget("Operator Feed", feed_lines),
    )


def format_chat_workspace(
    *,
    run: object | None,
    events: list[dict[str, object]],
    live_output: str | None,
) -> str:
    if run is None:
        return compose_workspace(
            [
                format_card(
                    "Chat",
                    [
                        "No active run selected.",
                        "Use the composer below to start a conversation or coding task.",
                    ],
                )
            ]
        )
    metadata = getattr(run, "metadata", {}) or {}
    output_text = live_output if live_output is not None else getattr(run, "final_output", None)
    recent_events = events[-5:]
    tool_calls = sum(1 for event in events if event.get("event_type") == "tool_called")
    reroutes = sum(1 for event in events if event.get("event_type") == "backend_auto_rerouted")
    retries = sum(1 for event in events if event.get("event_type") == "retry_scheduled")
    return compose_workspace(
        [
            format_card(
                "Agent Loop",
                format_agent_loop(
                    primary_mode="Chat",
                    busy=False,
                    tools=tool_calls,
                    reroutes=reroutes,
                    retries=retries,
                ),
            ),
            format_card(
                "Goal",
                [
                    getattr(run, "goal", "") or "-",
                    "",
                    f"backend: {getattr(run, 'backend_name', '-')}",
                    f"model: {metadata.get('backend_model') or '-'}",
                    f"status: {getattr(run, 'status', '-')}",
                ],
            ),
            format_card(
                "Response",
                [output_text or "No output yet."] ,
            ),
            format_card(
                "Recent Events",
                [f"- {event.get('event_type', '?')}: {_clip(str(event.get('payload', {})), 120)}" for event in recent_events]
                or ["No events yet."],
            ),
        ]
    )


def format_act_workspace(
    *,
    run: object | None,
    events: list[dict[str, object]],
    live_output: str | None,
) -> str:
    if run is None:
        return compose_workspace([format_card("Act", ["No active execution."])])
    output_text = live_output if live_output is not None else getattr(run, "final_output", None)
    notable = [
        event for event in events
        if event.get("event_type") in {
            "instruction_context_loaded",
            "context_providers_selected",
            "tool_called",
            "tool_result",
            "backend_auto_rerouted",
            "retry_scheduled",
            "run_completed",
        }
    ]
    approvals = sum(1 for event in events if event.get("event_type") == "approval_requested")
    tool_calls = sum(1 for event in events if event.get("event_type") == "tool_called")
    reroutes = sum(1 for event in events if event.get("event_type") == "backend_auto_rerouted")
    retries = sum(1 for event in events if event.get("event_type") == "retry_scheduled")
    return compose_workspace(
        [
            format_card(
                "Agent Loop",
                format_agent_loop(
                    primary_mode="Act",
                    busy=True,
                    approvals=approvals,
                    tools=tool_calls,
                    reroutes=reroutes,
                    retries=retries,
                ),
            ),
            format_card(
                "Mission",
                [
                    getattr(run, "goal", "") or "-",
                    "",
                    f"status: {getattr(run, 'status', '-')}",
                    f"backend: {getattr(run, 'backend_name', '-')}",
                    f"strategy: {getattr(run, 'strategy_name', '-')}",
                ],
            ),
            format_card(
                "Execution Trace",
                [f"- {event.get('event_type', '?')}: {_clip(str(event.get('payload', {})), 120)}" for event in notable[-8:]]
                or ["No execution steps yet."],
            ),
            format_card(
                "Live Output",
                [output_text or "No streamed output yet."],
            ),
        ]
    )


def format_plan_workspace(plan: object | None, steps: list[object], events: list[object]) -> str:
    if plan is None:
        return compose_workspace([format_card("Plan", ["No plan selected."])])
    current_step = next(
        (step for step in steps if getattr(step, "sequence_no", None) == getattr(plan, "current_step_no", None)),
        None,
    )
    step_lines = []
    for step in steps[:10]:
        marker = ">" if getattr(step, "sequence_no", None) == getattr(plan, "current_step_no", None) else " "
        line = f"{marker} {getattr(step, 'sequence_no', '?')}. {getattr(step, 'title', '-')}"
        if getattr(step, "status", None):
            line += f" [{getattr(step, 'status')}]"
        step_lines.append(line)
    event_lines = [f"- {getattr(event, 'event_type', '?')}: {_clip(str(getattr(event, 'payload', {})), 120)}" for event in events[-6:]]
    current_lines = [
        f"title: {getattr(current_step, 'title', '-') if current_step else '-'}",
        f"details: {_clip(getattr(current_step, 'details', None), 140) if current_step else '-'}",
    ]
    done_count = sum(1 for step in steps if getattr(step, "status", None) == "done")
    blocked_count = sum(1 for step in steps if getattr(step, "status", None) == "blocked")
    total_steps = len(steps)
    pending_count = max(0, total_steps - done_count - blocked_count)
    plan_started = sum(1 for event in events if getattr(event, "event_type", None) == "step_selected")
    plan_blocked = sum(1 for event in events if getattr(event, "event_type", None) == "step_blocked")
    progress_lines = [
        f"total: {total_steps}",
        f"done: {done_count}",
        f"blocked: {blocked_count}",
        f"pending: {pending_count}",
        "",
        format_metric_bar("done", done_count, total_steps),
        format_metric_bar("pending", pending_count, total_steps),
        format_metric_bar("blocked", blocked_count, total_steps),
    ]
    board_columns = {"done": [], "active": [], "pending": [], "blocked": []}
    for step in steps[:12]:
        status = str(getattr(step, "status", "pending") or "pending")
        if getattr(step, "sequence_no", None) == getattr(plan, "current_step_no", None) and status not in {"done", "blocked"}:
            board_columns["active"].append(f"{getattr(step, 'sequence_no', '?')}. {getattr(step, 'title', '-')}")
        elif status == "done":
            board_columns["done"].append(f"{getattr(step, 'sequence_no', '?')}. {getattr(step, 'title', '-')}")
        elif status == "blocked":
            board_columns["blocked"].append(f"{getattr(step, 'sequence_no', '?')}. {getattr(step, 'title', '-')}")
        else:
            board_columns["pending"].append(f"{getattr(step, 'sequence_no', '?')}. {getattr(step, 'title', '-')}")
    board_lines = [
        *format_plan_lane("Done", board_columns["done"]),
        "",
        *format_plan_lane("Active", board_columns["active"]),
        "",
        *format_plan_lane("Pending", board_columns["pending"]),
        "",
        *format_plan_lane("Blocked", board_columns["blocked"]),
    ]
    next_moves = []
    if board_columns["active"]:
        next_moves.append(f"finish active step: {board_columns['active'][0]}")
    if board_columns["blocked"]:
        next_moves.append(f"resolve blocker: {board_columns['blocked'][0]}")
    if board_columns["pending"]:
        next_moves.append(f"queue next: {board_columns['pending'][0]}")
    return compose_workspace(
        [
            format_card(
                "Agent Loop",
                format_agent_loop(
                    primary_mode="Plan",
                    busy=str(getattr(plan, "status", "")) in {"active", "running"},
                    reroutes=0,
                    retries=0,
                    tools=0,
                    status_message=f"selected steps {plan_started} | blocked events {plan_blocked}",
                ),
            ),
            format_card(
                "Plan Goal",
                [
                    getattr(plan, "goal", "") or "-",
                    "",
                    f"status: {getattr(plan, 'status', '-')}",
                    f"current step: {getattr(plan, 'current_step_no', '-')}",
                    f"strategy: {getattr(plan, 'strategy_name', '-')}",
                ],
            ),
            format_card("Progress", progress_lines),
            format_card("Current Step", current_lines),
            format_card("Step Board", step_lines or ["No steps yet."]),
            format_card("Board View", board_lines),
            format_card("Next Moves", next_moves or ["No next move suggestions."]),
            format_card("Plan History", event_lines or ["No plan events yet."]),
        ]
    )


def format_review_workspace(
    *,
    run: object | None,
    review_text: str,
    diff_file_text: str,
    diff_patch_text: str,
    diff_sections: list[tuple[str, dict[str, object]]],
    selected_diff_index: int,
    events: list[dict[str, object]],
) -> str:
    if run is None:
        return compose_workspace([format_card("Review", ["No review target selected."])])
    summary_lines = review_text.splitlines()
    findings: list[str] = []
    child_lines: list[str] = []
    notable = False
    in_children = False
    for line in summary_lines:
        stripped = line.strip()
        if stripped.lower() == "notable events:":
            notable = True
            in_children = False
            continue
        if stripped.lower() == "child runs:":
            notable = False
            in_children = True
            continue
        if notable and stripped:
            findings.append(line)
        elif in_children and stripped:
            child_lines.append(line)
    tool_calls = sum(1 for event in events if event.get("event_type") == "tool_called")
    approvals = sum(1 for event in events if event.get("event_type") == "approval_requested")
    reroutes = sum(1 for event in events if event.get("event_type") == "backend_auto_rerouted")
    retries = sum(1 for event in events if event.get("event_type") == "retry_scheduled")
    selected_file = diff_sections[selected_diff_index][0] if diff_sections and selected_diff_index < len(diff_sections) else "-"
    evidence_lines = [
        f"files changed: {len(diff_sections)}",
        f"selected file: {selected_file}",
        f"tool calls: {tool_calls}",
        f"approval gates: {approvals}",
        f"reroutes: {reroutes}",
        f"retries: {retries}",
    ]
    navigator_lines = format_file_tree([label for label, _patch in diff_sections[:10]], selected_index=selected_diff_index)
    patch_lines = diff_patch_text.splitlines()
    hunk_count = sum(1 for line in patch_lines if line.startswith("@@"))
    added_count = sum(1 for line in patch_lines if line.startswith("+") and not line.startswith("+++"))
    removed_count = sum(1 for line in patch_lines if line.startswith("-") and not line.startswith("---"))
    patch_meta = [
        f"hunks: {hunk_count}",
        f"added: {added_count}",
        f"removed: {removed_count}",
    ]
    return compose_workspace(
        [
            format_card(
                "Agent Loop",
                format_agent_loop(
                    primary_mode="Review",
                    busy=False,
                    approvals=approvals,
                    tools=tool_calls,
                    reroutes=reroutes,
                    retries=retries,
                ),
            ),
            format_card("Review Summary", summary_lines[:10]),
            format_card("Evidence", evidence_lines),
            format_card("Navigator", navigator_lines),
            format_card("Findings", findings or ["No notable findings or tool events."]),
            format_card("Patch Stats", patch_meta),
            format_card("Changed Files", diff_file_text.splitlines()),
            format_card("Patch", diff_patch_text.splitlines()),
            format_card("Related Runs", child_lines or ["No child runs."]),
        ]
    )


def format_ops_workspace(
    *,
    mode: str,
    approval: object | None,
    job: object | None,
    integrations_text: str | None,
    activity: dict[str, object] | None,
    job_events: list[object],
    job_inputs: list[object],
    recent_actions: list[str] | None = None,
    status_message: str | None = None,
) -> str:
    if mode == "approvals":
        approval_lines = format_approval_detail(approval).splitlines()
        return compose_workspace(
            [
                format_card(
                    "Agent Loop",
                    format_agent_loop(
                        primary_mode="Ops",
                        busy=False,
                        approvals=1 if approval is not None else 0,
                        status_message=status_message,
                    ),
                ),
                format_card("Approval Queue", approval_lines[:8]),
                format_card("Decision", approval_lines[8:] or ["No approval details."]),
            ]
        )
    if mode == "jobs":
        job_lines = format_job_detail(job, job_events, job_inputs).splitlines()
        loop_state = [
            f"goal: {getattr(job, 'goal', '-') if job is not None else '-'}",
            f"status: {getattr(job, 'status', '-') if job is not None else '-'}",
            f"control: {getattr(job, 'control_state', '-') if job is not None else '-'}",
            f"pending inputs: {len(job_inputs)}",
        ]
        autonomy_lines = [
            f"latest status: {status_message or '-'}",
            f"recent actions tracked: {len(recent_actions or [])}",
            f"recent job events: {len(job_events)}",
            f"human gates: {len(job_inputs)}",
        ]
        mission_lines = [
            f"objective: {getattr(job, 'goal', '-') if job is not None else '-'}",
            f"latest action: {(recent_actions or ['-'])[0]}",
            f"latest event: {getattr(job_events[-1], 'event_type', '-') if job_events else '-'}",
            f"operator gate: {'open' if job_inputs else 'closed'}",
        ]
        loop_timeline = [
            f"{getattr(event, 'event_type', '?')}: {_clip(str(getattr(event, 'payload', {})), 88)}"
            for event in job_events[-6:]
        ]
        return compose_workspace(
            [
                format_card(
                    "Agent Loop",
                    format_agent_loop(
                        primary_mode="Ops",
                        busy=str(getattr(job, "status", "")) in {"running", "queued"},
                        jobs=1 if job is not None else 0,
                        approvals=len(job_inputs),
                        tools=sum(1 for event in job_events if getattr(event, "event_type", None) == "tool_called"),
                        status_message=status_message,
                    ),
                ),
                format_card("Mission Control", mission_lines),
                format_card("Loop Console", loop_state),
                format_card("Autonomy State", autonomy_lines),
                format_card("Loop Timeline", format_timeline("Latest", loop_timeline)),
                format_card("Recent Job Events", [f"- {getattr(event, 'event_type', '?')}: {_clip(str(getattr(event, 'payload', {})), 120)}" for event in job_events[-8:]] or ["No job events."]),
                format_card("Operator Inputs", [f"- {_clip(getattr(item, 'input_text', ''), 120)}" for item in job_inputs] or ["No pending operator inputs."]),
            ]
        )
    if mode == "integrations":
        text_lines = (integrations_text or "No integration data.").splitlines()
        return compose_workspace(
            [
                format_card(
                    "Agent Loop",
                    format_agent_loop(primary_mode="Ops", busy=False, status_message=status_message),
                ),
                format_card("Backend / Tooling Health", text_lines[:14]),
                format_card("Integration Detail", text_lines[14:] or ["No additional integration detail."]),
            ]
        )
    if mode == "activity":
        activity_lines = format_activity_detail(activity).splitlines()
        return compose_workspace(
            [
                format_card(
                    "Agent Loop",
                    format_agent_loop(primary_mode="Ops", busy=False, status_message=status_message),
                ),
                format_card("Activity Event", activity_lines[:8]),
                format_card("Payload", activity_lines[8:] or ["No payload."]),
            ]
        )
    return compose_workspace([format_card("Ops", ["No ops item selected."])])


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
    workspace_lines = [
        f"focus: {mode}",
        f"backend: {backend}",
        f"model: {model_override or '-'}",
        f"strategy: {strategy}",
        f"domain: {domain or '-'}",
        f"cwd: {cwd}",
        f"autonomy: {'yes' if autonomous else 'no'}",
        f"busy: {'yes' if busy else 'no'}",
    ]
    health_lines = []
    if not statuses:
        health_lines.append("none")
    else:
        reachable = sum(1 for status in statuses if status.get("reachable") and not status.get("temporarily_unavailable"))
        cooldown = sum(1 for status in statuses if status.get("temporarily_unavailable"))
        degraded = sum(1 for status in statuses if not status.get("reachable"))
        health_lines.extend(
            [
                f"reachable: {reachable}",
                f"cooldown: {cooldown}",
                f"degraded: {degraded}",
                "",
            ]
        )
        for status in statuses[:8]:
            state = "up" if status.get("reachable") else "down"
            if status.get("temporarily_unavailable"):
                state = "cooldown"
            model = _clip(str(status.get("model") or "-"), 20)
            health_lines.append(f"- {status['name']}: {state} [{model}]")
    queue_lines = [
        f"sessions: {len(sessions)}",
        f"plans: {len(plans)}",
        f"approvals: {len(approvals)}",
        f"jobs: {len(jobs)}",
        "",
        f"session: {_clip(getattr(sessions[0], 'title', None) or getattr(sessions[0], 'id', '-'), 34) if sessions else '-'}",
        f"plan: {_clip(getattr(plans[0], 'goal', None) or getattr(plans[0], 'id', '-'), 34) if plans else '-'}",
        f"approval: {_clip(getattr(approvals[0], 'tool_name', None) or '-', 34) if approvals else '-'}",
        f"job: {_clip(getattr(jobs[0], 'goal', None) or '-', 34) if jobs else '-'}",
    ]
    cards = [
        format_card("Control", workspace_lines),
        format_card("Backend Radar", health_lines),
        format_card("Queues", queue_lines),
    ]
    if status_message:
        cards.append(format_card("Status", [status_message]))
    if recent_actions:
        cards.append(format_card("Recent Actions", [f"- {item}" for item in recent_actions[:5]]))
    return compose_workspace(cards)


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
        from textual.containers import Horizontal, Vertical
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
            height: 6;
            margin: 1 1 0 1;
            padding: 1 2;
            background: #10304d;
            border: round #65d6ff;
            color: #f5f7fb;
            text-style: bold;
        }

        #workspace-bar {
            height: 4;
            margin: 1 1 0 1;
            padding: 0 2;
            background: #0b1b2b;
            border: round #3f93c6;
            color: #dff6ff;
        }

        #workspace-switcher {
            height: 3;
            margin: 0 1 1 1;
            padding: 0 1;
        }

        .workspace-btn {
            min-width: 12;
            margin-right: 1;
            background: #12324d;
            color: #dff6ff;
        }

        .workspace-btn.-active {
            background: #2c7fb8;
            text-style: bold;
        }

        #workspace-controls {
            height: 3;
            margin: 0 1 1 1;
            padding: 0 1;
        }

        .workspace-control-btn {
            min-width: 16;
            margin-right: 1;
            background: #14334a;
            color: #f7fbff;
        }

        #selector-strip {
            height: 3;
            margin: 0 1 1 1;
            padding: 0 1;
        }

        .selector-btn {
            min-width: 16;
            margin-right: 1;
            background: #17344a;
            color: #e4f3ff;
        }

        .selector-btn.-active {
            background: #3887b8;
            text-style: bold;
        }

        #tray-controls {
            height: 3;
            margin: 0 1 1 1;
            padding: 0 1;
        }

        .tray-btn {
            min-width: 14;
            margin-right: 1;
            background: #183044;
            color: #e7f4ff;
        }

        .tray-btn.-active {
            background: #4c9ed9;
            text-style: bold;
        }

        #mode-guide {
            height: 4;
            margin: 0 1 1 1;
            padding: 0 2;
            background: #0a1520;
            border: round #35566e;
            color: #d6e8f5;
        }

        #body {
            height: 1fr;
            margin: 1;
        }

        #center-stack {
            width: 2fr;
            height: 1fr;
            margin-right: 1;
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
            background: #0b1420;
            width: 28;
        }

        #detail-pane {
            border: round #65d6ff;
            background: #08111c;
            height: 3fr;
            margin-right: 0;
        }

        .mode-chat {
            border: round #64c7ff;
            background: #091626;
        }

        .mode-act {
            border: round #59d39b;
            background: #081a1a;
        }

        .mode-plan {
            border: round #f0c36a;
            background: #19140a;
        }

        .mode-review {
            border: round #ff8f70;
            background: #1a1114;
        }

        .mode-ops {
            border: round #c084fc;
            background: #14111d;
        }

        #workspace-tools {
            height: 16;
            margin-top: 1;
        }

        .tool-row {
            height: 1fr;
            margin-bottom: 1;
        }

        #tool-row-bottom {
            margin-bottom: 0;
        }

        .tool-pane {
            width: 1fr;
            height: 1fr;
            padding: 1 1;
            margin-right: 1;
            border: round #446c88;
            background: #0d1521;
            color: #d6e8f5;
            overflow: auto auto;
        }

        .tray-focus {
            border: round #f8fbff;
            background: #102033;
        }

        .tray-muted {
            tint: #7a8793 20%;
        }

        #tool-c {
            margin-right: 1;
        }

        #tool-d {
            margin-right: 0;
        }

        #ops-pane {
            margin-right: 0;
            border: round #f4a261;
            background: #17131d;
            width: 32;
        }

        #command-meta {
            height: 3;
            margin: 0 1;
            padding: 0 2;
            background: #0a1623;
            border: round #30536e;
            color: #c9dbea;
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

        #help-overlay {
            layer: overlay;
            offset: 6 4;
            width: 72;
            height: 28;
            padding: 1 2;
            border: round #ffd166;
            background: #101a27;
            color: #f8fbff;
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
            ("f1", "toggle_help", "Help"),
            ("ctrl+h", "toggle_nav_pane", "Left Rail"),
            ("ctrl+l", "toggle_ops_pane", "Ops Dock"),
            ("z", "toggle_focus_mode", "Focus Mode"),
            ("ctrl+1", "focus_tray_a", "Tray A"),
            ("ctrl+2", "focus_tray_b", "Tray B"),
            ("ctrl+3", "focus_tray_c", "Tray C"),
            ("ctrl+4", "focus_tray_d", "Tray D"),
            ("ctrl+0", "tray_overview", "Tray Overview"),
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
            self._integration_focus: str | None = "plugins"
            self._recent_actions: list[str] = []
            self._status_message: str | None = None
            self._status_until = 0.0
            self._activity_items: list[dict[str, object]] = []
            self._nav_visible = True
            self._ops_visible = True
            self._help_visible = False
            self._tray_focus: str | None = None
            self._tray_expanded = False

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            yield Static("", id="hero")
            yield Static("", id="workspace-bar")
            with Horizontal(id="workspace-switcher"):
                yield Button("Runs", id="ws-runs", classes="workspace-btn")
                yield Button("Sessions", id="ws-sessions", classes="workspace-btn")
                yield Button("Plans", id="ws-plans", classes="workspace-btn")
                yield Button("Review", id="ws-review", classes="workspace-btn")
                yield Button("Approvals", id="ws-approvals", classes="workspace-btn")
                yield Button("Jobs", id="ws-jobs", classes="workspace-btn")
                yield Button("Integrations", id="ws-integrations", classes="workspace-btn")
                yield Button("Activity", id="ws-activity", classes="workspace-btn")
            with Horizontal(id="workspace-controls"):
                yield Button("Refresh", id="wc-1", classes="workspace-control-btn")
                yield Button("Plans", id="wc-2", classes="workspace-control-btn")
                yield Button("Review", id="wc-3", classes="workspace-control-btn")
                yield Button("Activity", id="wc-4", classes="workspace-control-btn")
                yield Button("Palette", id="wc-5", classes="workspace-control-btn")
            with Horizontal(id="selector-strip"):
                yield Button("", id="sel-1", classes="selector-btn")
                yield Button("", id="sel-2", classes="selector-btn")
                yield Button("", id="sel-3", classes="selector-btn")
                yield Button("", id="sel-4", classes="selector-btn")
                yield Button("", id="sel-5", classes="selector-btn")
                yield Button("", id="sel-6", classes="selector-btn")
            with Horizontal(id="tray-controls"):
                yield Button("Pane 1", id="tp-a", classes="tray-btn")
                yield Button("Pane 2", id="tp-b", classes="tray-btn")
                yield Button("Pane 3", id="tp-c", classes="tray-btn")
                yield Button("Pane 4", id="tp-d", classes="tray-btn")
                yield Button("Maximize", id="tp-max", classes="tray-btn")
            yield Static("", id="mode-guide")
            with Horizontal(id="body"):
                yield Static("", id="nav-pane", classes="pane")
                with Vertical(id="center-stack"):
                    yield Static("", id="detail-pane", classes="pane")
                    with Vertical(id="workspace-tools"):
                        with Horizontal(id="tool-row-top", classes="tool-row"):
                            yield Static("", id="tool-a", classes="tool-pane")
                            yield Static("", id="tool-b", classes="tool-pane")
                        with Horizontal(id="tool-row-bottom", classes="tool-row"):
                            yield Static("", id="tool-c", classes="tool-pane")
                            yield Static("", id="tool-d", classes="tool-pane")
                yield Static("", id="ops-pane", classes="pane")
            yield Static("", id="command-meta")
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
            yield Static("", id="help-overlay")
            yield Footer()

        def on_mount(self) -> None:
            self._refresh_dashboard()
            self.query_one("#palette", Input).styles.display = "none"
            self.query_one("#editor", Input).styles.display = "none"
            self.query_one("#editor-area", TextArea).styles.display = "none"
            self.query_one("#help-overlay", Static).styles.display = "none"
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

        def action_toggle_help(self) -> None:
            self._help_visible = not self._help_visible
            self._apply_layout_visibility()
            self._refresh_dashboard()

        def action_toggle_nav_pane(self) -> None:
            self._nav_visible = not self._nav_visible
            self._apply_layout_visibility()
            self._refresh_dashboard()

        def action_toggle_ops_pane(self) -> None:
            self._ops_visible = not self._ops_visible
            self._apply_layout_visibility()
            self._refresh_dashboard()

        def action_toggle_focus_mode(self) -> None:
            if self._nav_visible or self._ops_visible:
                self._nav_visible = False
                self._ops_visible = False
            else:
                self._nav_visible = True
                self._ops_visible = True
            self._apply_layout_visibility()
            self._refresh_dashboard()

        def action_focus_tray_a(self) -> None:
            self._tray_focus = "a"
            self._refresh_dashboard()

        def action_focus_tray_b(self) -> None:
            self._tray_focus = "b"
            self._refresh_dashboard()

        def action_focus_tray_c(self) -> None:
            self._tray_focus = "c"
            self._refresh_dashboard()

        def action_focus_tray_d(self) -> None:
            self._tray_focus = "d"
            self._refresh_dashboard()

        def action_tray_overview(self) -> None:
            self._tray_expanded = False
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
            if self._help_visible:
                self._help_visible = False
                self._apply_layout_visibility()
                self._refresh_dashboard()
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
                "prev-step",
                "next-step",
                "prev-target",
                "next-target",
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
                "tray 1",
                "tray 2",
                "tray 3",
                "tray 4",
                "tray-max",
                "tray-overview",
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
            workspace_state = workspace_switcher_state(self.view_mode)
            if button_id in workspace_state:
                _label, command, _active = workspace_state[button_id]
                self._execute_button_command(command)
                return
            tray_state = workspace_tray_state(self._current_tray_labels(), focus=self._tray_focus, expanded=self._tray_expanded)
            if button_id in tray_state:
                _label, command, _active, enabled = tray_state[button_id]
                if enabled and command:
                    self._execute_button_command(command)
                return
            selector_state = contextual_selector_state(
                mode=self.view_mode,
                review_focus=self._review_focus,
                integration_focus=self._integration_focus,
                runs=self._runs,
                run_index=self.selected_run_index,
                sessions=self._sessions,
                session_index=self.selected_session_index,
                plans=self._plans,
                plan_index=self.selected_plan_index,
                plan_steps=orchestro.db.list_plan_steps(getattr(self._selected_plan(), "id")) if self._selected_plan() is not None else [],
                approvals=self._approvals,
                approval_index=self.selected_approval_index,
                jobs=self._jobs,
                job_index=self.selected_job_index,
                activity_items=self._activity_items,
                activity_index=self.selected_activity_index,
                diff_sections=split_diff_files(extract_run_diff(self._selected_review_run())[1]),
                diff_index=self._selected_diff_index,
                integration_options=self._integration_options(mcp_status=self._integration_cache[0], lsp_status=self._integration_cache[1]),
            )
            if button_id in selector_state:
                _label, command, enabled = selector_state[button_id]
                if enabled and command:
                    self._execute_button_command(command)
                return
            workspace_controls = workspace_controls_state(
                mode=self.view_mode,
                editor_visible=self._editor_visible,
                review_focus=self._review_focus,
            )
            if button_id in workspace_controls:
                _label, command, enabled = workspace_controls[button_id]
                if enabled and command:
                    self._execute_button_command(command)
                return

        def _execute_button_command(self, command: str) -> None:
            if command == "toggle-palette":
                self.action_toggle_palette()
                return
            if command.startswith("focus-tray:"):
                self._tray_focus = command.split(":", 1)[1]
                self._record_action(f"tray focus {self._tray_focus}")
                self._refresh_dashboard()
                return
            if command == "toggle-tray-max":
                if self._tray_focus is None:
                    self._tray_focus = "a"
                self._tray_expanded = not self._tray_expanded
                self._record_action("tray maximized" if self._tray_expanded else "tray overview restored")
                self._refresh_dashboard()
                return
            if command.startswith("pick-selector:"):
                slot = command.split(":", 1)[1]
                self._pick_selector(slot)
                return
            if command.startswith("select-run:"):
                self.selected_run_index = int(command.split(":", 1)[1])
                self._refresh_dashboard()
                return
            if command.startswith("select-session:"):
                self.selected_session_index = int(command.split(":", 1)[1])
                self._refresh_dashboard()
                return
            if command.startswith("select-approval:"):
                self.selected_approval_index = int(command.split(":", 1)[1])
                self._refresh_dashboard()
                return
            if command.startswith("select-job:"):
                self.selected_job_index = int(command.split(":", 1)[1])
                self._refresh_dashboard()
                return
            if command.startswith("select-activity:"):
                self.selected_activity_index = int(command.split(":", 1)[1])
                self._refresh_dashboard()
                return
            if command.startswith("select-integration:"):
                self._integration_focus = command.split(":", 1)[1]
                self._record_action(f"integration focus {self._integration_focus}")
                self._refresh_dashboard()
                return
            if command.startswith("select-plan-step:"):
                seq = int(command.split(":", 1)[1])
                plan = self._selected_plan()
                if plan is not None:
                    orchestro.db.select_plan_step(plan_id=getattr(plan, "id"), sequence_no=seq)
                self._refresh_dashboard()
                return
            if command.startswith("select-review-file:"):
                self._select_review_file(command.split(":", 1)[1])
                self._refresh_dashboard()
                return
            if command.startswith("select-review-target:"):
                self._select_review_target(command.split(":", 1)[1])
                self._refresh_dashboard()
                return
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
            if command == "review-prev":
                self._move_review_target(-1)
                self._refresh_dashboard()
                return
            if command == "review-next":
                self._move_review_target(1)
                self._refresh_dashboard()
                return
            if command == "prev-plan-step":
                self._move_plan_step(-1)
                self._refresh_dashboard()
                return
            if command == "next-plan-step":
                self._move_plan_step(1)
                self._refresh_dashboard()
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
            if command == "focus-review":
                self.action_switch_review()
                return
            if command == "focus-sessions":
                self.action_switch_sessions()
                return
            if command == "focus-plans":
                self.action_switch_plans()
                return
            if command == "focus-jobs":
                self.action_switch_jobs()
                return
            if command == "focus-approvals":
                self.action_switch_approvals()
                return
            if command == "focus-integrations":
                self.action_switch_integrations()
                return
            if command == "focus-activity":
                self.action_switch_activity()
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

        def _move_review_target(self, delta: int) -> None:
            review_jobs = self._review_jobs()
            if not review_jobs:
                self._last_error = "no review targets available"
                return
            if self._review_focus == "targets":
                selected_id = getattr(self._selected_job(), "id", None)
                review_index = 0
                for index, job in enumerate(review_jobs):
                    if getattr(job, "id", None) == selected_id:
                        review_index = index
                        break
                review_index = max(0, min(len(review_jobs) - 1, review_index + delta))
                chosen_id = getattr(review_jobs[review_index], "id", None)
                if chosen_id is not None:
                    for index, job in enumerate(self._jobs):
                        if getattr(job, "id", None) == chosen_id:
                            self.selected_job_index = index
                            break
                self._last_error = None
                self._record_action(f"selected review target index {review_index + 1}")
                return
            review_run = self._selected_review_run()
            _title, patch = extract_run_diff(review_run)
            diff_sections = split_diff_files(patch)
            if not diff_sections:
                self._last_error = "no diff files available"
                return
            self._selected_diff_index = max(0, min(len(diff_sections) - 1, self._selected_diff_index + delta))
            self._last_error = None
            self._record_action(f"selected diff file {self._selected_diff_index + 1}")

        def _move_plan_step(self, delta: int) -> None:
            plan = self._selected_plan()
            if plan is None:
                self._last_error = "no plan selected"
                return
            steps = orchestro.db.list_plan_steps(getattr(plan, "id"))
            if not steps:
                self._last_error = "no plan steps available"
                return
            current = int(getattr(plan, "current_step_no", 1))
            sequence_nos = [int(getattr(step, "sequence_no", 0)) for step in steps]
            if current not in sequence_nos:
                target = sequence_nos[0]
            else:
                index = sequence_nos.index(current)
                target = sequence_nos[max(0, min(len(sequence_nos) - 1, index + delta))]
            if orchestro.db.select_plan_step(plan_id=getattr(plan, "id"), sequence_no=target):
                self._last_error = None
                self._record_action(f"selected plan step {target} in {getattr(plan, 'id', '?')}")
            else:
                self._last_error = f"unable to select plan step {target}"

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
            selected_activity = self._selected_activity()
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
                selected_label = str((selected_activity or {}).get("source", "-"))
            elif self.view_mode == "integrations":
                selected_label = self._integration_focus or "overview"
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
            primary_mode = derive_primary_mode(self.view_mode, busy=self._busy)
            if self.view_mode == "activity" and selected_activity is not None:
                objective = str(selected_activity.get("summary") or selected_activity.get("event_type") or "")
            elif self.view_mode == "plans" and selected_plan is not None:
                objective = getattr(selected_plan, "goal", None)
            elif self.view_mode == "sessions" and selected_session is not None:
                objective = getattr(selected_session, "summary", None) or getattr(selected_session, "title", None)
            elif self.view_mode == "approvals" and selected_approval is not None:
                objective = getattr(selected_approval, "argument", None) or getattr(selected_approval, "tool_name", None)
            elif self.view_mode in {"jobs", "review"} and selected_job is not None:
                objective = getattr(selected_job, "goal", None)
            else:
                objective = getattr(selected_run, "goal", None)
            hero = format_mission_strip(
                primary_mode=primary_mode,
                workspace_mode=self.view_mode,
                objective=objective,
                backend=backend,
                model_override=model_override,
                strategy=strategy,
                busy=self._busy,
                autonomous=autonomous,
                selected_label=selected_label,
                approval_count=len(self._approvals),
                job_count=len(self._jobs),
                recent_status=self._status_message,
            )
            selected_file_label = (
                diff_sections[self._selected_diff_index][0]
                if diff_sections and self._selected_diff_index < len(diff_sections)
                else None
            )
            workspace_bar = format_workspace_bar(
                primary_mode=primary_mode,
                view_mode=self.view_mode,
                selected_label=selected_label,
                review_focus=self._review_focus,
                selected_file=selected_file_label,
                busy=self._busy,
                autonomous=autonomous,
                tray_focus=self._tray_focus,
                tray_expanded=self._tray_expanded,
            )
            mode_guide = format_mode_guide(
                primary_mode=primary_mode,
                view_mode=self.view_mode,
                editor_visible=self._editor_visible,
                review_focus=self._review_focus,
                busy=self._busy,
                selected_label=selected_label,
                status_message=self._status_message,
                tray_focus=self._tray_focus,
                tray_expanded=self._tray_expanded,
            )
            command_meta = format_command_meta(
                backend=backend,
                model_override=model_override,
                strategy=strategy,
                domain=domain,
                providers=context_providers,
                autonomous=autonomous,
                primary_mode=primary_mode,
                nav_visible=self._nav_visible,
                ops_visible=self._ops_visible,
                tray_focus=self._tray_focus,
                tray_expanded=self._tray_expanded,
            )
            review_summary = format_review_detail(review_run, review_events, child_runs)
            diff_file_text = format_diff_file_list(diff_sections, self._selected_diff_index)
            diff_patch_text = format_diff_patch(diff_patch, title=diff_title)
            integrations_text = format_integrations_detail(
                plugin_loaded=orchestro.plugins.loaded,
                plugin_load_errors=orchestro.plugins.load_errors,
                plugin_hook_errors=orchestro.plugins.hooks.last_errors,
                mcp_status=mcp_status,
                lsp_status=lsp_status,
                focus=self._integration_focus,
            ) if self.view_mode == "integrations" else None
            integration_options = self._integration_options(mcp_status=mcp_status, lsp_status=lsp_status)

            if primary_mode == "Review":
                surface = WorkspaceSurface(
                    primary_mode=primary_mode,
                    detail=format_review_workspace(
                    run=review_run,
                    review_text=review_summary,
                    diff_file_text=diff_file_text,
                    diff_patch_text=diff_patch_text,
                    diff_sections=diff_sections,
                    selected_diff_index=self._selected_diff_index,
                    events=review_events,
                ),
                    panes=format_review_widgets(
                        diff_sections=diff_sections,
                        selected_diff_index=self._selected_diff_index,
                        events=review_events,
                    ),
                )
            elif primary_mode == "Plan":
                surface = WorkspaceSurface(
                    primary_mode=primary_mode,
                    detail=format_plan_workspace(selected_plan, plan_steps, plan_events),
                    panes=format_plan_widgets(
                        steps=plan_steps,
                        current_step_no=getattr(selected_plan, "current_step_no", None) if selected_plan is not None else None,
                    ),
                )
            elif primary_mode == "Ops":
                surface = WorkspaceSurface(
                    primary_mode=primary_mode,
                    detail=format_ops_workspace(
                        mode=self.view_mode,
                        approval=selected_approval,
                        job=selected_job,
                        integrations_text=integrations_text,
                        activity=selected_activity,
                        job_events=job_events,
                        job_inputs=job_inputs,
                        recent_actions=self._recent_actions,
                        status_message=self._status_message,
                    ),
                    panes=format_ops_widgets(
                        mode=self.view_mode,
                        job_events=job_events,
                        job_inputs=job_inputs,
                        recent_actions=self._recent_actions,
                        status_message=self._status_message,
                        activity=selected_activity,
                    ),
                )
            elif primary_mode == "Act":
                surface = WorkspaceSurface(
                    primary_mode=primary_mode,
                    detail=format_act_workspace(
                        run=selected_run,
                        events=run_events,
                        live_output=self._live_output.get(selected_run_id or "", None),
                    ),
                    panes=format_act_widgets(
                        run=selected_run,
                        events=run_events,
                        diff_sections=diff_sections,
                        selected_diff_index=self._selected_diff_index,
                        live_output=self._live_output.get(selected_run_id or "", None),
                    ),
                )
            else:
                surface = WorkspaceSurface(
                    primary_mode=primary_mode,
                    detail=format_chat_workspace(
                        run=selected_run,
                        events=run_events,
                        live_output=self._live_output.get(selected_run_id or "", None),
                    ),
                    panes=format_chat_widgets(
                        run=selected_run,
                        events=run_events,
                        recent_actions=self._recent_actions,
                        status_message=self._status_message,
                    ),
                )
            if self._editor_visible:
                surface = WorkspaceSurface(
                    primary_mode=surface.primary_mode,
                    detail=f"{format_editor_banner(mode=self._editor_mode, context=self._editor_context)}\n\n{surface.detail}",
                    panes=surface.panes,
                )
            if self._last_error:
                surface = WorkspaceSurface(
                    primary_mode=surface.primary_mode,
                    detail=f"{surface.detail}\n\nlast error:\n{self._last_error}",
                    panes=surface.panes,
                )
            nav_panel = format_left_rail(
                view_mode=self.view_mode,
                primary_mode=primary_mode,
                runs=self._runs,
                sessions=self._sessions,
                plans=self._plans,
                approvals=self._approvals,
                jobs=self._jobs,
                activity_items=self._activity_items,
                statuses=statuses,
                run_index=self.selected_run_index,
                session_index=self.selected_session_index,
                plan_index=self.selected_plan_index,
                approval_index=self.selected_approval_index,
                job_index=self.selected_job_index,
                activity_index=self.selected_activity_index,
                diff_sections=diff_sections,
                diff_index=self._selected_diff_index,
                review_focus=self._review_focus,
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
            self.query_one("#workspace-bar", Static).update(workspace_bar)
            self.query_one("#mode-guide", Static).update(mode_guide)
            composer = self.query_one("#composer", Input)
            composer.placeholder = composer_placeholder(self.view_mode, primary_mode)
            self.query_one("#command-meta", Static).update(command_meta)
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
            self.query_one("#detail-pane", Static).update(surface.detail)
            self.query_one("#tool-a", Static).update(surface.panes[0])
            self.query_one("#tool-b", Static).update(surface.panes[1])
            self.query_one("#tool-c", Static).update(surface.panes[2])
            self.query_one("#tool-d", Static).update(surface.panes[3])
            self.query_one("#ops-pane", Static).update(ops)
            self.query_one("#help-overlay", Static).update(
                format_help_overlay(
                    primary_mode=primary_mode,
                    view_mode=self.view_mode,
                    review_focus=self._review_focus,
                    nav_visible=self._nav_visible,
                    ops_visible=self._ops_visible,
                    tray_focus=self._tray_focus,
                    tray_expanded=self._tray_expanded,
                )
            )
            self._apply_layout_visibility()
            self._apply_surface_skin(surface.primary_mode)
            self._apply_tray_layout()
            for button_id, (label, _command, active) in workspace_switcher_state(self.view_mode).items():
                button = self.query_one(f"#{button_id}", Button)
                button.label = label
                if active:
                    button.add_class("-active")
                else:
                    button.remove_class("-active")
            for button_id, (label, _command, active, enabled) in workspace_tray_state(
                self._current_tray_labels(),
                focus=self._tray_focus,
                expanded=self._tray_expanded,
            ).items():
                button = self.query_one(f"#{button_id}", Button)
                button.label = label or " "
                button.disabled = not enabled
                if active:
                    button.add_class("-active")
                else:
                    button.remove_class("-active")
            selector_state = contextual_selector_state(
                mode=self.view_mode,
                review_focus=self._review_focus,
                integration_focus=self._integration_focus,
                runs=self._runs,
                run_index=self.selected_run_index,
                sessions=self._sessions,
                session_index=self.selected_session_index,
                plans=self._plans,
                plan_index=self.selected_plan_index,
                plan_steps=plan_steps,
                approvals=self._approvals,
                approval_index=self.selected_approval_index,
                jobs=self._jobs,
                job_index=self.selected_job_index,
                activity_items=self._activity_items,
                activity_index=self.selected_activity_index,
                diff_sections=diff_sections,
                diff_index=self._selected_diff_index,
                integration_options=integration_options,
            )
            for button_id, (label, _command, active) in selector_state.items():
                button = self.query_one(f"#{button_id}", Button)
                button.label = label or " "
                button.disabled = not bool(label)
                if active:
                    button.add_class("-active")
                else:
                    button.remove_class("-active")
            for button_id, (label, _command, enabled) in workspace_controls_state(
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
            if command == "pick":
                if not arg:
                    self._last_error = "pick requires an index"
                else:
                    self._pick_selector(arg)
                self._refresh_dashboard()
                return
            if command == "tray" and arg:
                mapping = {"1": "a", "2": "b", "3": "c", "4": "d"}
                target = mapping.get(arg.strip())
                if target is None:
                    self._last_error = f"unknown tray target: {arg}"
                else:
                    self._tray_focus = target
                    self._last_error = None
                self._refresh_dashboard()
                return
            if command == "tray-max":
                self._execute_button_command("toggle-tray-max")
                return
            if command == "tray-overview":
                self._tray_expanded = False
                self._refresh_dashboard()
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
            elif command == "prev-step":
                self._move_plan_step(-1)
            elif command == "next-step":
                self._move_plan_step(1)
            elif command == "prev-target":
                self._move_review_target(-1)
            elif command == "next-target":
                self._move_review_target(1)
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

        def _integration_options(
            self,
            *,
            mcp_status: dict[str, object] | None,
            lsp_status: dict[str, object] | None,
        ) -> list[tuple[str, str]]:
            options: list[tuple[str, str]] = [("Plugins", "plugins")]
            if mcp_status is not None:
                options.append(("MCP", "mcp"))
            if lsp_status is not None:
                options.append(("LSP", "lsp"))
            if self._integration_focus not in {slug for _label, slug in options}:
                self._integration_focus = options[0][1]
            return options

        def _current_selector_state(self) -> dict[str, tuple[str, str | None, bool]]:
            selected_plan = self._selected_plan()
            selected_plan_id = getattr(selected_plan, "id", None) if selected_plan is not None else None
            plan_steps = orchestro.db.list_plan_steps(selected_plan_id) if selected_plan_id else []
            selected_job = self._selected_job()
            selected_job_id = getattr(selected_job, "id", None) if selected_job is not None else None
            review_run = orchestro.db.get_run(getattr(selected_job, "run_id", "")) if self.view_mode == "review" and getattr(selected_job, "run_id", None) else self._selected_run()
            diff_patch = extract_run_diff(review_run)[1]
            diff_sections = split_diff_files(diff_patch)
            mcp_status, lsp_status = self._integration_cache
            integration_options = self._integration_options(mcp_status=mcp_status, lsp_status=lsp_status)
            return contextual_selector_state(
                mode=self.view_mode,
                review_focus=self._review_focus,
                integration_focus=self._integration_focus,
                runs=self._runs,
                run_index=self.selected_run_index,
                sessions=self._sessions,
                session_index=self.selected_session_index,
                plans=self._plans,
                plan_index=self.selected_plan_index,
                plan_steps=plan_steps,
                approvals=self._approvals,
                approval_index=self.selected_approval_index,
                jobs=self._jobs,
                job_index=self.selected_job_index,
                activity_items=self._activity_items,
                activity_index=self.selected_activity_index,
                diff_sections=diff_sections,
                diff_index=self._selected_diff_index,
                integration_options=integration_options,
            )

        def _current_tray_labels(self) -> list[str]:
            primary_mode = derive_primary_mode(self.view_mode, busy=self._busy)
            if primary_mode == "Review":
                return ["Review Status", "Changed Files", "Evidence", "Review Timeline"]
            if primary_mode == "Plan":
                return ["Plan Status", "Plan Board", "Progress Bars", "Next Moves"]
            if primary_mode == "Ops":
                return ["Ops Status", "Mission Feed", "Gates", "Operator Feed"]
            if primary_mode == "Act":
                return ["Act Status", "Execution Timeline", "Touched Files", "Result Stream"]
            return ["Chat Status", "Conversation Context", "Loaded Context", "Suggested Next Moves"]

        @staticmethod
        def _mode_skin(primary_mode: str) -> str:
            return {
                "Chat": "mode-chat",
                "Act": "mode-act",
                "Plan": "mode-plan",
                "Review": "mode-review",
                "Ops": "mode-ops",
            }.get(primary_mode, "mode-chat")

        def _apply_layout_visibility(self) -> None:
            self.query_one("#nav-pane", Static).styles.display = "block" if self._nav_visible else "none"
            self.query_one("#ops-pane", Static).styles.display = "block" if self._ops_visible else "none"
            self.query_one("#help-overlay", Static).styles.display = "block" if self._help_visible else "none"

        def _apply_surface_skin(self, primary_mode: str) -> None:
            skin_classes = ["mode-chat", "mode-act", "mode-plan", "mode-review", "mode-ops"]
            skin = self._mode_skin(primary_mode)
            panes = [
                self.query_one("#detail-pane", Static),
                self.query_one("#tool-a", Static),
                self.query_one("#tool-b", Static),
                self.query_one("#tool-c", Static),
                self.query_one("#tool-d", Static),
                self.query_one("#nav-pane", Static),
                self.query_one("#ops-pane", Static),
            ]
            for widget in panes:
                for class_name in skin_classes:
                    widget.remove_class(class_name)
                widget.add_class(skin)

        def _apply_tray_layout(self) -> None:
            workspace_tools = self.query_one("#workspace-tools", Vertical)
            top_row = self.query_one("#tool-row-top", Horizontal)
            bottom_row = self.query_one("#tool-row-bottom", Horizontal)
            panes = {
                "a": self.query_one("#tool-a", Static),
                "b": self.query_one("#tool-b", Static),
                "c": self.query_one("#tool-c", Static),
                "d": self.query_one("#tool-d", Static),
            }
            if not self._tray_expanded:
                workspace_tools.styles.height = 16
                top_row.styles.display = "block"
                bottom_row.styles.display = "block"
                for slot, pane in panes.items():
                    pane.styles.display = "block"
                    pane.styles.width = "1fr"
                    pane.styles.margin_right = 1 if slot in {"a", "c"} else 0
                    pane.remove_class("tray-focus")
                    pane.remove_class("tray-muted")
                return
            focus = self._tray_focus or "a"
            workspace_tools.styles.height = 18
            top_row.styles.display = "block" if focus in {"a", "b"} else "none"
            bottom_row.styles.display = "block" if focus in {"c", "d"} else "none"
            for slot, pane in panes.items():
                visible = slot == focus
                pane.styles.display = "block" if visible else "none"
                if visible:
                    pane.styles.width = "1fr"
                    pane.styles.margin_right = 0
                    pane.add_class("tray-focus")
                    pane.remove_class("tray-muted")
                else:
                    pane.remove_class("tray-focus")
                    pane.add_class("tray-muted")

        def _pick_selector(self, raw_index: str) -> None:
            try:
                index = int(raw_index)
            except ValueError:
                self._last_error = f"invalid selector index: {raw_index}"
                return
            state = self._current_selector_state()
            label, command, _active = state.get(f"sel-{index}", ("", None, False))
            if not label or not command:
                self._last_error = f"selector {index} is not available"
                return
            self._last_error = None
            self._execute_button_command(command)

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
