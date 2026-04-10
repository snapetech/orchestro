# Orchestro

Orchestro is a local-first orchestration harness for personal AI systems that improve through use.

The initial focus is:

- test-time compute scaling for small local models
- logging and review of interactions
- weekly preference tuning on user-approved outputs
- routing work across models running on a home LAN

## Phase 1 Status

The first implementation slice is in place:

- SQLite-backed run, event, and rating storage
- SQLite-backed interactions, facts, and corrections storage
- FTS-backed search over interactions and corrections
- embedding job tracking inside the same SQLite database
- a backend interface
- a working `mock` backend
- an OpenAI-compatible backend stub for local model servers
- a terminal shell and CLI commands for `ask`, `runs`, `show`, `rate`, and `review`
- a minimal FastAPI service for `/health`, `/backends`, `/runs`, and `/ask`

## Quickstart

Create a virtual environment, install the package, and use the shell:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
orchestro shell
```

Run the API server:

```bash
orchestro serve
curl http://127.0.0.1:8765/health
```

If Ollama is running in Kubernetes, bridge it locally first:

```bash
./scripts/ollama-port-forward.sh
```

Run one query directly:

```bash
orchestro ask "draft a short plan for Orchestro" --backend mock
orchestro ask "retry this once on failure" --backend subprocess-command --strategy reflect-retry
```

Stable instruction files are loaded automatically when present:

- repo or parent directory `ORCHESTRO.md`
- global `.orchestro/global.md` or `$ORCHESTRO_HOME/global.md`

Domain constitutions are loaded automatically when present:

- repo or parent directory `constitutions/<domain>.md`
- global `.orchestro/constitutions/<domain>.md` or `$ORCHESTRO_HOME/constitutions/<domain>.md`

Inspect the effective instruction layer:

```bash
orchestro instructions-show
orchestro instructions-show --cwd /path/to/project
orchestro constitutions-show payroll
```

Inside the shell, background jobs are available:

```bash
/mode plan
/plan draft a Sage 50 troubleshooting flow
/plan_add <plan-id> <after-step-no> "new step" "details"
/plan_add <plan-id> <after-step-no>
/plan_edit <plan-id> <step-no> "edited step" "details"
/plan_edit <plan-id> <step-no>
/plan_drop <plan-id> <step-no>
/plan_run
/replan <plan-id> tighten-the-plan
/plans
/plan_show <plan-id>
/context
/context instructions,lexical
/context reset
/bench
/benchmark_runs
/mode act
/bg draft a payroll note
/jobs
/wait <job-id>
/fg <job-id>
/watch <job-id|run-id>
/cancel <job-id|run-id>
/pause <job-id|run-id>
/resume <job-id|run-id>
/job_show <job-id|run-id>
/retry <run-id>
/escalate <run-id> openai-compat
/children <run-id>
/delegate <goal>
/benchmark_compare [left-id] [right-id]
/tools
/approvals
/approval_requests
/approve <request-id> <approved|denied> [pattern]
/inject <job-id|run-id> [--resume] [--replan] <note>
/plan_step_replan <plan-id> <note> [--sequence-no N]
/plan_bg <plan-id>
/tool pwd
```

The shell now distinguishes `plan` and `act` modes. In `plan` mode, plain text input creates a persisted plan instead of running immediately. `plan_run` executes the current plan step as a normal Orchestro run and advances the plan cursor on success.
By default, `plan_run` upgrades plain step execution to `reflect-retry-once`, so a step can fail once, log a structured diagnosis, and retry before the whole plan is marked blocked.
Context providers are explicit and configurable per shell session: `instructions`, `lexical`, `semantic`, `corrections`, `interactions`, `postmortems`.

If you want shell escalation into Ollama-backed chat, export the OpenAI-compatible backend vars before launching `orchestro shell`.

Shell jobs are persisted in SQLite, so `/jobs` and `/fg <job-id>` still work after restarting the shell.
Job-level event history is also persisted, and `/watch` now tails both shell-job events and run events.

Cancellation is currently cooperative for ordinary backends. For the `subprocess-command` backend, Orchestro can terminate the child process while it is running. Pause/resume is also currently implemented only for `subprocess-command`, using process signals.

The `reflect-retry` strategy will log a structured reflection event after a first failure and retry once with explicit retry guidance in context.

List or inspect recent runs:

```bash
orchestro runs
orchestro plans
orchestro plan-create "draft a bookkeeping debug flow"
orchestro plan-show <plan-id>
orchestro plan-step-add <plan-id> 1 "collect context" "inspect current repo state"
EDITOR=vi orchestro plan-step-add <plan-id> 1 --editor
orchestro plan-step-edit <plan-id> 2 "run verification" "capture failures and summarize them"
EDITOR=vi orchestro plan-step-edit <plan-id> 2 --editor
orchestro plan-step-drop <plan-id> 3
orchestro plan-step-replan <plan-id> "step failed because the scope is wrong" --sequence-no 2
orchestro ask "provider test" --backend mock --providers instructions,lexical
orchestro ask "inspect the repo and answer with a file count" --backend openai-compat --strategy tool-loop
orchestro delegate <parent-run-id> "check test coverage gaps" --backend mock
orchestro children <parent-run-id>
orchestro bench --backend mock
orchestro bench --suite benchmarks/agent.json
orchestro benchmark-runs
orchestro benchmark-compare
orchestro benchmark-compare <older-run-id> <newer-run-id>
orchestro shell-jobs
orchestro shell-job-show <job-id>
orchestro shell-job-inject <job-id> "review the last failure and avoid bash; use read_file first" --resume --replan
orchestro show <run-id>
orchestro tool-approvals
orchestro approval-requests --status pending
orchestro approval-resolve <request-id> approved --pattern "bash *"
```

Tool-loop runs now support three actions through a JSON protocol:

- `final`: return a final answer
- `tool`: call a registered local tool such as `pwd`, `ls`, `read_file`, `rg`, or `bash`
- `delegate`: spawn a child Orchestro run under the current run

Child runs are persisted through `parent_run_id`, show up in `/runs/{run_id}` from the API, and are inspectable in the shell with `/children` or from the CLI with `orchestro children`.

Failed runs now record a postmortem automatically. Those summaries are stored in SQLite, exposed through CLI/API, and can be injected back into future runs through the `postmortems` context provider.

Benchmark suites now support per-case backend, strategy, context providers, temporary environment overrides, expected statuses, and required run events. The bundled [benchmarks/agent.json](benchmarks/agent.json) suite exercises `tool-loop` and `reflect-retry` against the subprocess backend.

The agent benchmark suite also covers operator-control paths inside `tool-loop`, including approval-gated tools and injected operator notes, so regressions in those flows show up in stored benchmark runs.

Local tools are also available directly:

```bash
orchestro tools
orchestro tool-run pwd
orchestro tool-run bash "pytest -q" --approve
orchestro tool-run rg "class Orchestro" --cwd .
```

`bash` now requires explicit approval. In the shell, `/tool bash ...` prompts with `y/n/a(lways)` and `a` opens an editable default pattern like `bash printf ok` that you can widen to `bash *` or `*`. In the CLI and API, `tool-run` requires `--approve` or `approve: true` unless a stored allow-pattern already matches. Stored patterns are visible through `/approvals` or `orchestro tool-approvals`.

Background jobs now use a persisted approval queue instead of flat rejection. When a paused job hits a gated tool with no matching allow-pattern, Orchestro records an approval request, pauses the job, and waits. You can inspect and resolve these through:

- shell: `/approval_requests`, `/approve <id> approved|denied [pattern]`
- CLI: `orchestro approval-requests`, `orchestro approval-resolve ... --pattern "bash *"`
- API: `GET /approval-requests`, `POST /approval-requests/{id}/resolve` with optional `pattern`

Paused or waiting jobs can also take operator steering notes. Orchestro persists injected notes in SQLite, shows them in shell job inspection, and feeds them into the next `tool-loop` step as explicit operator context.

- shell: `/inject <job-id|run-id> [--resume] [--replan] <note>`
- CLI: `orchestro shell-job-inject <job-id> "note" [--resume] [--replan]`
- API: `POST /shell-jobs/{job_id}/inject`

If the paused run belongs to a persisted plan, `--replan` rewrites the plan from the active step forward before the job resumes. You can also replan a plan directly from its current step or a chosen step:

- shell: `/replan <plan-id> [note]`, `/plan_step_replan <plan-id> <note> [--sequence-no N]`
- CLI: `orchestro plan-step-replan <plan-id> "note" [--sequence-no N]`
- API: `POST /plans/{plan_id}/replan`

Rate a run:

```bash
orchestro rate run <run-id> good --note "useful first pass"
```

Inspect the memory tables:

```bash
orchestro interactions --limit 20
orchestro fact-add employer Lakeside --source manual
orchestro facts
orchestro facts-sync
orchestro correction-add --context "payroll calc" --wrong "EI is manual" --right "EI follows payroll tables" --domain payroll
orchestro corrections
orchestro postmortems
```

Accepted facts are also synced into [facts.md](facts.md) at the repo root.

Search and vector readiness:

```bash
orchestro search payroll --kind all
orchestro index-status
orchestro vector-status
orchestro index-embeddings --provider hash
orchestro semantic-search payroll --provider hash
```

Current retrieval works in two layers:

- SQLite FTS for lexical search
- `sqlite-vec` for semantic search once embeddings are indexed

The default verification path uses a deterministic local hash embedder so the indexing pipeline can run without an external model service.

For real embeddings, point Orchestro at an OpenAI-compatible embeddings endpoint:

```bash
export ORCHESTRO_EMBED_BASE_URL=http://127.0.0.1:11434/v1
export ORCHESTRO_EMBED_MODEL=nomic-embed-text
export ORCHESTRO_RETRIEVAL_PROVIDER=openai-compat
orchestro queue-embeddings --model-name nomic-embed-text
orchestro index-embeddings --provider openai-compat
orchestro semantic-search payroll --provider openai-compat
```

Or use the one-shot helper:

```bash
ORCHESTRO_EMBED_BASE_URL=http://127.0.0.1:11434/v1 \
ORCHESTRO_EMBED_MODEL=nomic-embed-text \
./scripts/reindex-ollama-embeddings.sh
```

For live chat against Ollama's OpenAI-compatible API:

```bash
export ORCHESTRO_OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export ORCHESTRO_OPENAI_MODEL=qwen2.5-coder:7b
orchestro ask "What payroll correction should I remember?" --backend openai-compat --domain payroll
```

When `ORCHESTRO_RETRIEVAL_PROVIDER=openai-compat` is set, Orchestro will use Ollama-backed semantic retrieval during normal `ask` runs, with domain-biased ranking and correction-first prompt context.

For real killable background work, Orchestro also supports a subprocess-backed backend:

```bash
export ORCHESTRO_SUBPROCESS_COMMAND="bash -lc 'sleep 10; printf \"%s\\n\" \"$ORCHESTRO_GOAL\"'"
orchestro ask "subprocess test" --backend subprocess-command
```

In the shell, `/cancel` can terminate that subprocess while it is running.

By default, local state is stored in `.orchestro/orchestro.db` at the repo root. Set `ORCHESTRO_HOME` to override that path.
If you want global instruction context, create `.orchestro/global.md` and Orchestro will inject it into every run.

## Planning

Initial product and implementation planning lives in:

- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/adr-sqlite-first.md`
- `docs/adr-agent-loop-patterns.md`

## License

This project uses dual licensing:

- `AGPL-3.0-or-later` for open source use
- commercial licensing is available for organizations that want to use, embed, or distribute Orchestro outside AGPL terms

See [LICENSE](LICENSE), [LICENSES/AGPL-3.0.txt](LICENSES/AGPL-3.0.txt), and [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).
