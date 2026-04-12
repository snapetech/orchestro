from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandMeta:
    name: str
    aliases: tuple[str, ...] = ()
    category: str = "general"
    help: str = ""
    usage: str = ""


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, CommandMeta] = {}
        self._aliases: dict[str, str] = {}

    def register(self, meta: CommandMeta) -> None:
        self._commands[meta.name] = meta
        for alias in meta.aliases:
            self._aliases[alias] = meta.name

    def resolve(self, name: str) -> CommandMeta | None:
        if name in self._commands:
            return self._commands[name]
        canonical = self._aliases.get(name)
        if canonical:
            return self._commands.get(canonical)
        return None

    def list_commands(self, *, category: str | None = None) -> list[CommandMeta]:
        commands = list(self._commands.values())
        if category:
            commands = [c for c in commands if c.category == category]
        return sorted(commands, key=lambda c: (c.category, c.name))

    def categories(self) -> list[str]:
        return sorted(set(c.category for c in self._commands.values()))

    def format_help(self) -> str:
        lines: list[str] = []
        for cat in self.categories():
            lines.append(f"\n  {cat}")
            lines.append(f"  {'─' * len(cat)}")
            for cmd in self.list_commands(category=cat):
                alias_text = f" ({', '.join(cmd.aliases)})" if cmd.aliases else ""
                help_text = f"  {cmd.help}" if cmd.help else ""
                lines.append(f"    /{cmd.name}{alias_text}{help_text}")
        lines.append("")
        return "\n".join(lines)


def build_default_registry() -> CommandRegistry:
    registry = CommandRegistry()

    _runs = [
        CommandMeta("runs", aliases=("history",), category="runs", help="List recent runs"),
        CommandMeta("show", category="runs", help="Show one run and its events"),
        CommandMeta("rate", category="runs", help="Rate a run or event"),
        CommandMeta("note", category="runs", help="Attach or update a note on a run"),
        CommandMeta("summary", category="runs", help="Attach or update a summary on a run"),
        CommandMeta("changes", category="runs", help="Show git changes for a run"),
        CommandMeta("retry", category="runs", help="Retry a failed run"),
        CommandMeta("children", category="runs", help="List child runs for a parent run"),
        CommandMeta("delegate", category="runs", help="Run a delegated child task under a parent run"),
        CommandMeta("last", category="runs", help="Show the last run"),
        CommandMeta("review", category="runs", help="Show unrated runs"),
        CommandMeta("escalate", category="runs", help="Escalate a job or run to a stronger backend"),
    ]

    _planning = [
        CommandMeta("plan", category="planning", help="Create a plan for a goal"),
        CommandMeta("plan_show", category="planning", help="Show a plan and its steps"),
        CommandMeta("plan_run", category="planning", help="Run the current step of a plan"),
        CommandMeta("plan_add", category="planning", help="Insert a step into a plan"),
        CommandMeta("plan_edit", category="planning", help="Edit an existing plan step"),
        CommandMeta("plan_drop", category="planning", help="Delete one plan step"),
        CommandMeta("plan_bg", category="planning", help="Run a plan step in the background"),
        CommandMeta("plan_step_replan", category="planning", help="Replan a plan from one step forward"),
        CommandMeta("replan", category="planning", help="Regenerate remaining plan steps"),
        CommandMeta("plans", category="planning", help="List plans"),
    ]

    _jobs = [
        CommandMeta("bg", category="jobs", help="Run a goal in the background"),
        CommandMeta("jobs", category="jobs", help="List background jobs"),
        CommandMeta("fg", category="jobs", help="Show output of a background job"),
        CommandMeta("wait", category="jobs", help="Wait for a background job to finish"),
        CommandMeta("watch", category="jobs", help="Stream events for a background job"),
        CommandMeta("cancel", category="jobs", help="Cancel a background job"),
        CommandMeta("pause", category="jobs", help="Pause a running job"),
        CommandMeta("resume", category="jobs", help="Resume a paused job"),
        CommandMeta("job_show", category="jobs", help="Show one job and its events"),
        CommandMeta("inject", category="jobs", help="Queue operator input for a job"),
    ]

    _tools = [
        CommandMeta("tool", category="tools", help="Run one local tool"),
        CommandMeta("tools", category="tools", help="List available local tools"),
        CommandMeta("verifiers", category="tools", help="List available verifiers"),
        CommandMeta("mcp_status", category="tools", help="Show MCP server connections and tools"),
        CommandMeta("lsp_status", category="tools", help="Show LSP server connections and languages"),
    ]

    _memory = [
        CommandMeta("facts", category="memory", help="List stored facts"),
        CommandMeta("facts_sync", category="memory", help="Write accepted facts to facts.md"),
        CommandMeta("corrections", category="memory", help="List stored corrections"),
        CommandMeta("search", category="memory", help="Search interactions and corrections"),
        CommandMeta("postmortems", category="memory", help="List failure postmortems"),
        CommandMeta("interactions", category="memory", help="List stored interactions"),
    ]

    _context = [
        CommandMeta("context", category="context", help="Show or set context providers"),
        CommandMeta("instructions", category="context", help="Show loaded instruction files"),
        CommandMeta("constitutions", category="context", help="Show loaded constitution files"),
    ]

    _backends = [
        CommandMeta("backend", category="backends", help="Show or set the active backend"),
        CommandMeta("backends", category="backends", help="Show backend profiles and reachability"),
        CommandMeta("aliases", category="backends", help="Show model aliases"),
    ]

    _sessions = [
        CommandMeta("session", category="sessions", help="Manage sessions (new, resume, list, fork, compact)"),
    ]

    _approvals = [
        CommandMeta("approvals", category="approvals", help="List stored tool approval patterns"),
        CommandMeta("approval_requests", category="approvals", help="List pending or resolved approval requests"),
        CommandMeta("approve", category="approvals", help="Approve or deny an approval request"),
    ]

    _benchmarks = [
        CommandMeta("bench", category="benchmarks", help="Run a benchmark suite"),
        CommandMeta("bench_matrix", category="benchmarks", help="Run a suite across multiple backends"),
        CommandMeta("bench_local", category="benchmarks", help="Run a suite across local profile tiers"),
        CommandMeta("benchmark_runs", category="benchmarks", help="List stored benchmark runs"),
        CommandMeta("benchmark_compare", category="benchmarks", help="Compare two benchmark runs"),
    ]

    _training = [
        CommandMeta("export_preferences", category="training", help="Export preference training data"),
        CommandMeta("export_stats", category="training", help="Show stats about available preference data"),
    ]

    _scheduling = [
        CommandMeta("schedule", category="scheduling", help="Manage scheduled tasks (add, list, toggle, delete)"),
        CommandMeta("escalations", category="scheduling", help="Show recent escalation events"),
    ]

    _navigation = [
        CommandMeta("pwd", category="navigation", help="Print working directory"),
        CommandMeta("cd", category="navigation", help="Change working directory"),
        CommandMeta("ls", category="navigation", help="List directory contents"),
        CommandMeta("findfile", category="navigation", help="Find files by name substring"),
    ]

    _config = [
        CommandMeta("mode", category="config", help="Switch between act and plan modes"),
        CommandMeta("strategy", category="config", help="Show or set the active strategy"),
        CommandMeta("domain", category="config", help="Show or set the active domain"),
        CommandMeta("autonomous", category="config", help="Toggle autonomous mode"),
        CommandMeta("plugins", category="config", help="List loaded plugins and hooks"),
        CommandMeta("routing_stats", category="config", help="Show data-driven routing statistics"),
        CommandMeta("tasks", category="config", help="List sub-agent coordination tasks"),
        CommandMeta("trust", category="config", help="Show effective trust tiers"),
        CommandMeta("trust_set", category="config", help="Set a session trust override for a tool"),
    ]

    _shell = [
        CommandMeta("quit", aliases=("exit",), category="shell", help="Exit the shell"),
        CommandMeta("help", category="shell", help="Show this help"),
    ]

    _inspection = [
        CommandMeta("cost", category="inspection", help="Show session or shell token totals"),
    ]

    for group in (
        _runs, _planning, _jobs, _tools, _memory, _context,
        _backends, _sessions, _approvals, _benchmarks, _training,
        _scheduling, _navigation, _config, _inspection, _shell,
    ):
        for meta in group:
            registry.register(meta)

    return registry
