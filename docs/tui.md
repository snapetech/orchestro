# TUI Vision

This document defines the target full-screen Orchestro TUI.

It is not a “nicer shell.” It is the operator cockpit for runs, plans, sessions, approvals, routing, memory, and integrations.

## Table Of Contents

1. [Why A TUI](#why-a-tui)
2. [Competitive Baseline](#competitive-baseline)
3. [What Great Looks Like](#what-great-looks-like)
4. [Orchestro Advantage](#orchestro-advantage)
5. [Product Principles](#product-principles)
6. [Visual Direction](#visual-direction)
7. [Core Screens](#core-screens)
8. [Interaction Model](#interaction-model)
9. [Quality Bar](#quality-bar)

## Why A TUI

Orchestro already has substantial orchestration depth:

- runs and event traces
- sessions and compaction
- plans and step execution
- tool approval state
- backend routing and cooldowns
- MCP, LSP, and plugin diagnostics
- memory, facts, corrections, and collections

The current shell exposes those capabilities, but the operator still has to reconstruct state mentally from command output. A TUI should turn those subsystems into something that is inspectable at a glance.

## Competitive Baseline

The goal is not to imitate a single product. The goal is to beat the current best aspects of each.

As of April 13, 2026:

- Codex sets a high bar for terminal evidence display, tool and diff formatting, to-do visibility, compacting, approvals, MCP, and long-task coding workflows.
- Claude Code sets a high bar for shell-native operability: statuslines, permissions, hooks, MCP, workspace trust, slash commands, and power-user control.
- Cursor Agent sets a high bar for product polish, model fluidity, and “this feels modern” interaction quality.
- Continue sets a high bar for explicit TUI versus headless separation and permission handling inside the interface.
- Kilo sets a high bar for visible mode richness, model catalog energy, and “agent console” presentation.
- Gemini CLI sets a high bar for open extensibility, checkpointing, MCP, trusted folders, and command ergonomics.
- Aider sets a high bar for pragmatic repo-native workflows, git closeness, and low-friction terminal utility.

Reference links:

- Codex: <https://openai.com/index/introducing-upgrades-to-codex/>
- Claude Code: <https://code.claude.com/docs/en/commands>
- Cursor CLI: <https://cursor.com/cli>
- Continue CLI: <https://docs.continue.dev/cli/quickstart>
- Kilo CLI: <https://kilo.ai/cli>
- Gemini CLI: <https://github.com/google-gemini/gemini-cli>
- Aider: <https://aider.chat/>

## What Great Looks Like

Best-in-class terminal agent UX consistently has these traits:

- Legible under load: long tasks remain easy to follow.
- Mode clarity: it is obvious whether the agent is planning, acting, waiting, reviewing, or blocked on approval.
- Evidence first: diffs, tool calls, logs, routing decisions, and tests are visually inspectable.
- Fast retargeting: backend, model, session, and run focus change instantly.
- Context control: compacting, resuming, attaching, and replaying are first-class actions.
- Visual identity: the UI has personality rather than feeling like plain terminal dumps.

## Orchestro Advantage

Orchestro can exceed competitors by making orchestration-native concepts visible in one place:

- backend auto-routing reasons
- cooldown windows and quota fallback
- plans and execution cursor
- background jobs and injected operator input
- facts, corrections, collections, and retrieval provenance
- plugin, MCP, and LSP health
- benchmark and canary views

Most competing tools are strong in one or two of those categories, not all of them together.

## Product Principles

### 1. Operator Cockpit, Not Chat Skin

The TUI should feel like a control room.

### 2. Evidence Over Mystery

The operator should always be able to answer:

- what is running
- why it chose this backend
- what tools it used
- what changed
- what failed
- what needs approval

### 3. Keyboard First

Mouse support is fine, but the core interaction model must be fast from the keyboard.

### 4. Beautiful, But Useful

Flash is welcome only when it improves comprehension:

- intentional color system
- high-quality spacing and borders
- clear hierarchy
- live meters and status chips
- restrained motion

### 5. Headless Parity

Anything that matters in the TUI must still map to CLI or API workflows.

## Visual Direction

The target feel is:

- darker control-room base
- bright but disciplined accent system
- dense without looking cramped
- sharp contrast for action states
- elegant diff colors
- bold, high-signal headers and status chips

The TUI should not look like a generic terminal chat app. It should look closer to a development cockpit with a hint of trading terminal energy.

## Core Screens

### 1. Command Deck

Default daily-driver view.

- left rail: runs, sessions, plans, jobs
- center: active transcript and run detail
- right rail: backend status, routing reason, MCP/LSP/plugins, memory signals
- bottom: composer and mode strip

### 2. Review Deck

- diff-first
- tool calls and evidence
- tests and verifier results
- approve, rerun, escalate, summarize, rate

### 3. Plan Deck

- plan steps
- execution cursor
- replan, insert, drop, retry, background

### 4. Integration Deck

- backend radar
- cooldown clocks
- plugin load failures
- MCP and LSP degraded details

### 5. Memory Deck

- facts
- corrections
- semantic hits
- collections
- provenance and retrieval reasons

## Interaction Model

Modes should be explicit:

- `Act`
- `Plan`
- `Review`
- `Replay`
- `Ops`

Primary interaction patterns:

- command palette
- focused composer
- run selection
- pane switching
- filtered inboxes
- replayable event timelines

## Quality Bar

The TUI is not “good enough” when it merely works.

It is good when:

- a new operator can understand current system state in under 10 seconds
- long tasks remain readable without scrolling through noise
- approval and reroute situations are obvious
- switching context is fast and satisfying
- the interface feels distinctive enough that people would prefer it over raw shell output

For the implementation sequence, see [TUI Implementation Plan](tui-plan.md).
