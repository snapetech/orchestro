# TUI Redesign Spec

This document defines the next major Orchestro TUI redesign.

It is intentionally blunt: the current TUI is functional, but it still behaves too much like a structured debug console and not enough like a daily-driver operator cockpit.

Use this document as the source of truth for the next large UI pass.

## Table Of Contents

1. [Current Problems](#current-problems)
2. [North Star](#north-star)
3. [Product Model](#product-model)
4. [Information Architecture](#information-architecture)
5. [Core Modes](#core-modes)
6. [Primary Layout](#primary-layout)
7. [Key Workflows](#key-workflows)
8. [Autonomous Loop Console](#autonomous-loop-console)
9. [Visual System](#visual-system)
10. [Interaction Model](#interaction-model)
11. [Component Inventory](#component-inventory)
12. [Rebuild Plan](#rebuild-plan)
13. [Acceptance Bar](#acceptance-bar)

## Current Problems

The current full-screen UI has several structural problems:

1. It has no dominant interaction model.
It is simultaneously a run browser, planner, review surface, shell-job monitor, approval inbox, and status board, but none of those feels primary.

2. It is text-heavy and action-light.
The operator has to parse large monospace dumps to infer state instead of the UI making state obvious.

3. The current left side is overloaded.
Runs, plans, sessions, approvals, jobs, review, integrations, and activity all compete in the same visual style.

4. The center pane is still too close to a log dump.
It should be a workspace, not just a detail screen.

5. The right side is diagnostic-heavy.
It is useful, but it reads like admin output instead of contextual assistance.

6. The TUI still has too much “remember the command” energy.
Even with the action bar and palette improvements, too much power is hidden behind knowledge of state and keyboard behavior.

7. There is still no fully realized autonomous loop surface.
Orchestro has the beginnings of self-running, approval-gated, learning-aware workflows, but they do not yet have a dedicated control console.

## North Star

The Orchestro TUI should feel like:

- a coding workspace
- a conversational agent surface
- a review console
- a planning board
- an operations cockpit
- an autonomous mission control screen

It should not feel like “three terminal panes with a lot of text in them.”

The product benchmark is:

- Codex-level evidence display
- Claude Code-level control
- Cursor-level polish
- Kilo-level energy
- an explicit claw-bot style autonomous loop console

## Product Model

The redesign should shift the TUI to a clear product model:

- center workspace: where the active task lives
- left rail: where the operator moves between work modes and artifacts
- right dock: context, approvals, health, routing, model/backend state
- bottom command surface: prompt, mode, backend, model, autonomy, cwd
- persistent live-loop strip: what the agent is doing right now

Everything should reinforce that structure.

## Information Architecture

The current deck model should be reworked into a stronger IA:

### Left Rail

- Home
- Chat
- Act
- Review
- Plan
- Ops
- Sessions
- Runs
- Jobs
- Integrations
- Activity

The left rail should use:

- grouped nav sections
- counts/badges
- visible alerts
- a strong selected state

### Center Workspace

The center pane should be mode-specific and card-based:

- conversation cards
- run cards
- live execution step cards
- plan cards
- diff/review cards
- result cards
- acceptance/verifier cards
- lessons and memory cards

This is where the user should spend most of their time.

### Right Dock

The right dock should be contextual and secondary:

- backend and model
- routing reason
- approvals
- retrieved context
- budget and tokens
- MCP/LSP/plugin health
- memory and correction signals

It should not dominate the page.

### Bottom Command Surface

The bottom bar should become the stable operator input surface:

- prompt input
- slash and palette entry
- backend pill
- model pill
- strategy pill
- autonomy mode
- cwd indicator
- trust/approval state

## Core Modes

The redesigned TUI should center on five primary modes:

### Chat

For:

- ordinary conversation
- ask/answer
- brainstorming
- instructions
- summarization

### Act

For:

- live agent execution
- tool usage
- file edits
- test runs
- routing and reroutes

### Review

For:

- changed files
- diffs
- findings
- verifier output
- acceptance checks

### Plan

For:

- step creation
- blockers
- replans
- progress tracking
- background execution

### Ops

For:

- approvals
- jobs
- integrations
- backend health
- cooldowns
- activity stream
- retries and failures

These modes should be visible in both layout and interaction language.

## Primary Layout

Recommended default layout:

### Top Mission Strip

Always visible. Should show:

- current objective
- active mode
- current loop state
- backend/model
- run/session/plan identity
- busy/blocked/waiting state

### Left Rail

18-22 columns:

- workspace identity
- main nav
- alert badges
- secondary entities

### Main Workspace

60-70% width:

- mode-specific cards
- active transcript
- execution timeline
- plan board
- review surface

### Right Dock

24-32 columns:

- approvals
- backend/model
- context provenance
- integrations
- routing/cooldown
- budget

### Bottom Input

Persistent:

- prompt entry
- command hints
- mode/backend/model/autonomy chips

## Key Workflows

### 1. Agentic Coding Run

The screen should clearly show:

- goal
- chosen backend/model
- current plan
- live execution steps
- tool calls and outcomes
- changed files
- tests
- final result

### 2. Review Workflow

The review mode should become a real workspace:

- diff file tree
- selected patch
- findings summary
- acceptance/verifier checklist
- rerun/escalate/approve actions

### 3. Planning Workflow

The plan mode should make it easy to:

- create and reorder steps
- edit details
- mark blocked
- replan
- run a single step
- inspect plan history

### 4. Job / Approval Workflow

The operator should be able to:

- see pending approvals immediately
- understand why they were requested
- batch or single approve/deny
- pause, resume, or cancel jobs
- inject operator input

### 5. Activity Monitoring

There should be one place where the operator can see:

- what just happened
- what is happening now
- what failed
- what is waiting
- what was learned

## Autonomous Loop Console

This is a differentiator and should become a first-class surface.

The autonomous loop console should show:

- mission / objective
- current loop iteration
- last decisions
- observations
- failures
- retry strategy
- lessons learned
- memory writes and corrections
- pending human gates
- stop conditions
- confidence or health

This is the Orchestro equivalent of a claw-bot mission console.

It should be inspectable, not mystical.

## Visual System

The visual direction should shift away from “every pane is a bordered dump.”

### Base Palette

- deep graphite / deep navy base
- bright cyan or electric blue for focus
- warm amber for approvals and warning states
- green for healthy progress
- red only for true failure or destructive states

### Hierarchy

- cards instead of plain dumps
- chips and badges instead of repeated bracket syntax
- fewer equal-weight boxes
- stronger selected states
- more whitespace
- cleaner section titles

### Tone

The TUI should feel like:

- development cockpit
- agent mission control
- terminal-native product UI

It should not feel like:

- logs pasted into panes
- a diagnostic dashboard only
- a generic chat terminal

## Interaction Model

The interaction model should be explicit and teachable.

### Primary Inputs

- composer
- command palette
- direct action bar
- mode switcher
- structured modal editors

### Secondary Inputs

- keyboard navigation
- review/file focus
- inline actions on selected cards

### Command Design

The user should not need to memorize hidden actions.

Every important action should be discoverable via:

- visible action bar
- context hints
- palette suggestions
- mode-aware labels

## Component Inventory

The redesigned TUI should be built from reusable presentation primitives:

- mission strip
- nav rail item
- status chip
- goal card
- plan card
- tool call card
- approval card
- diff card
- changed file tree
- test result card
- verifier card
- lesson card
- activity card
- backend radar card
- integration health card
- memory provenance card

This is a more scalable design direction than continuing to add formatting helpers that dump text blocks.

## Rebuild Plan

### Phase 1: Information Architecture Reset

- replace the current pseudo-tab nav model with a true left rail
- define the five primary modes: Chat, Act, Review, Plan, Ops
- demote diagnostics into a right dock
- make the center pane the main workspace

### Phase 2: Card-Based Workspace

- replace dense detail dumps with cards
- introduce goal, plan, tool, diff, and result cards
- standardize section titles and chip styling

### Phase 3: Review Workspace

- build file tree + patch + findings workspace
- make changed files and diffs feel first-class
- add clearer acceptance and rerun actions

### Phase 4: Plan Workspace

- move from command-driven plan editing to visible plan controls
- support reordering, block state, insertion, and step actions from the UI

### Phase 5: Ops / Autonomous Loop Console

- expand approvals and jobs into a real ops workspace
- add loop iteration view
- expose lessons learned and retry state
- show memory writes / corrections / review gates

### Phase 6: Polish And Product Feel

- rebalance borders and spacing
- improve selection and focus visuals
- refine color language
- add tasteful motion or transitions where supported
- tighten empty states and onboarding cues

## Acceptance Bar

This redesign is successful when:

1. A new operator can understand current system state in under 10 seconds.
2. The active workspace feels task-centric, not log-centric.
3. Review mode feels like a code review surface, not a text dump.
4. Autonomous execution feels observable and governable.
5. The action model is visible enough that the operator does not need to memorize the product.
6. The TUI feels like a product with identity, not an internal tool.

Related docs:

- [TUI Vision](tui.md)
- [TUI Implementation Plan](tui-plan.md)
- [Shell Mode](shell.md)
- [Backends And Routing](backends-and-routing.md)
