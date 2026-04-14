# Instructions And Constitutions

Orchestro has two different context layers that are easy to confuse:

- instructions
- constitutions

They are loaded from different places and serve different purposes.

## Table Of Contents

1. [Instructions](#instructions)
2. [Constitutions](#constitutions)
3. [Lookup Order](#lookup-order)
4. [Suggested Usage Pattern](#suggested-usage-pattern)
5. [Examples](#examples)

## Instructions

Instructions are general operator or project guidance.

Loaded sources:

- global instructions: `.orchestro/global.md`
- project instructions: nearest `ORCHESTRO.md` walking up from the working directory

Implementation: [`src/orchestro/instructions.py`](../src/orchestro/instructions.py)

Use instructions for:

- coding conventions
- repo-specific workflow rules
- operator style and preferences
- project assumptions

## Constitutions

Constitutions are domain-specific rule bundles.

Loaded sources for a given domain:

- project constitution: nearest `constitutions/<domain>.md`
- global constitution: `.orchestro/constitutions/<domain>.md`

Implementation: [`src/orchestro/constitutions.py`](../src/orchestro/constitutions.py)

Use constitutions for:

- domain rules
- safety boundaries
- workflow constraints for a specific subject area
- evaluation rules that should apply only in a given domain

## Lookup Order

Instructions:

1. global `.orchestro/global.md`
2. nearest project `ORCHESTRO.md`

Constitutions:

1. nearest project `constitutions/<domain>.md`
2. global `.orchestro/constitutions/<domain>.md`

Both layers are loaded into the run context when relevant and recorded in run events.

## Suggested Usage Pattern

Use:

- `ORCHESTRO.md` for repo-local execution and coding rules
- `.orchestro/global.md` for your own standing operator preferences
- `constitutions/<domain>.md` for domain-specific rules inside a repo
- `.orchestro/constitutions/<domain>.md` for reusable cross-project constitutions

Avoid putting everything into one giant file. The separation exists so domain rules do not pollute every run.

## Examples

### `.orchestro/global.md`

```md
Prefer concise answers.
Call out risks before implementation.
When editing code, verify with tests when feasible.
```

### `ORCHESTRO.md`

```md
Use Python 3.12 features.
Add tests for new modules.
Do not bypass OrchestroDB for persistence.
```

### `constitutions/coding.md`

```md
Prioritize behavioral regressions and missing tests.
Prefer minimal changes over broad refactors unless explicitly requested.
```

Related docs:

- [Getting Started](getting-started.md)
- [Architecture](architecture.md)
- [Shell Mode](shell.md)
