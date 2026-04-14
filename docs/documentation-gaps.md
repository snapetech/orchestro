# Documentation Gaps

This file exists so remaining doc debt is explicit.

## Closed In This Pass

The previous first-order gaps are now covered by:

- [Plugins](plugins.md)
- [MCP](mcp.md)
- [LSP](lsp.md)
- [API Operations](api-operations.md)
- [Collections](collections.md)
- [Benchmarks](benchmarks.md)
- [Shell Mode](shell.md)

## Remaining Risks And Next Gaps

No major missing documentation area is currently tracked.

What remains is maintenance work:

- keep command examples aligned with `--help`
- keep backend docs aligned with vendor CLI changes
- keep schema docs aligned with future migrations
- add more examples when new workflows land

## Drift Risks To Watch

- `.env.example` comments versus actual backend wrapper behavior
- exact counts in docs, especially test totals
- command examples that duplicate `--help` output
- backend capability claims when vendor CLIs change behavior
- routing claims that depend on live environment state

## Rule For Future Updates

When a feature adds a new persistent object, status surface, or operator workflow, add or update a focused doc in `docs/` instead of expanding `README.md` into another monolith.
