# TUI Implementation Plan

This document turns the TUI vision into buildable phases.

## Table Of Contents

1. [Scope](#scope)
2. [Architecture](#architecture)
3. [Phases](#phases)
4. [Milestones](#milestones)
5. [Design System Notes](#design-system-notes)
6. [Known Risks](#known-risks)

## Scope

The TUI will be a first-class Orchestro surface alongside:

- the plain CLI
- the interactive shell
- the FastAPI service

The shell remains important for fallback and advanced scripting. The TUI becomes the preferred daily-driver operator surface.

## Architecture

Implementation target:

- Python
- Textual for the full-screen interface
- lazy import so the base install still works without TUI extras

Separation of concerns:

- `src/orchestro/tui.py`: presentation layer, formatting helpers, app wiring
- `src/orchestro/orchestrator.py`: unchanged execution engine
- `src/orchestro/cli.py`: `tui` command and argument parsing
- `docs/tui.md`: product intent

The TUI should consume existing Orchestro services rather than invent parallel logic.

## Phases

### Phase 0: Foundations

Ship now:

- optional `textual` dependency
- `orchestro tui` command
- full-screen layout skeleton
- run list
- active run detail
- backend status panel
- composer for new runs
- live refresh loop

Out of scope for this phase:

- approval inbox
- diff review UI
- editable plan board
- palette and themes

### Phase 1: Daily Driver

- session list and session focus
- plan list and current-step visibility
- better transcript rendering
- keyboard navigation across panes
- explicit backend/model/mode strip
- review and rating actions

### Phase 2: Operator Control

- approval inbox
- pending shell job controls
- pause, resume, cancel, inject operator input
- reroute and escalate actions
- cooldown and retry visuals

### Phase 3: Evidence And Review

- diff viewer
- tool-call cards
- verifier and test results
- change summaries
- run replay timeline

### Phase 4: Integrations And Memory

- MCP tools and server health panel
- LSP language/server health panel
- plugin hooks and failures
- retrieval provenance
- facts, corrections, and collections browser

### Phase 5: Polish

- command palette
- saved layouts
- compact mode
- focus mode
- richer theming
- benchmark and canary deck

## Milestones

### Milestone A

The TUI is a viable replacement for `ask` plus `runs` plus `show`.

### Milestone B

The TUI is a viable replacement for the shell for normal daily work.

### Milestone C

The TUI is the best way to operate Orchestro, with the shell reserved for specialist workflows and fallback.

## Design System Notes

Visual requirements:

- distinct pane borders and titles
- high-signal status strip
- readable empty states
- clear active selection treatment
- elegant severity colors for degraded or blocked states

Motion requirements:

- subtle load and refresh transitions
- obvious busy or blocked state changes
- no ornamental animation that slows reading

## Known Risks

- Textual API drift: keep the TUI isolated and lazily imported.
- Feature sprawl: do not jump to Phase 3 before Phase 1 is solid.
- Logic duplication: the TUI must call Orchestro services, not reimplement orchestration policy.
- Approval complexity: v0 should not pretend to support approval workflows it does not yet expose well.

## Immediate Build Order

1. land `orchestro tui`
2. make the run list and detail view pleasant
3. make prompt execution stable
4. add session and plan awareness
5. add approval and job control

Reference: [TUI Vision](tui.md), [Shell Mode](shell.md), [Architecture](architecture.md)
