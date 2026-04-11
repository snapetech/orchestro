from __future__ import annotations

from dataclasses import dataclass

RecoveryStep = str


@dataclass(frozen=True, slots=True)
class RecoveryRecipe:
    category: str
    steps: tuple[RecoveryStep, ...]

    def step_for_failure(self, failure_index: int) -> RecoveryStep:
        if 0 <= failure_index < len(self.steps):
            return self.steps[failure_index]
        return "abandon"


RECIPES: dict[str, RecoveryRecipe] = {
    "backend_timeout": RecoveryRecipe(
        category="backend_timeout",
        steps=("retry_same", "retry_different_backend", "escalate"),
    ),
    "backend_unreachable": RecoveryRecipe(
        category="backend_unreachable",
        steps=("retry_different_backend", "escalate"),
    ),
    "context_overflow": RecoveryRecipe(
        category="context_overflow",
        steps=("compact_context", "retry_same", "escalate"),
    ),
    "tool_crash": RecoveryRecipe(
        category="tool_crash",
        steps=("retry_same", "simplify_strategy", "escalate"),
    ),
    "approval_timeout": RecoveryRecipe(
        category="approval_timeout",
        steps=("escalate",),
    ),
    "workspace_conflict": RecoveryRecipe(
        category="workspace_conflict",
        steps=("escalate",),
    ),
    "general_failure": RecoveryRecipe(
        category="general_failure",
        steps=("retry_same", "abandon"),
    ),
}


def recovery_recipe_for(category: str) -> RecoveryRecipe:
    return RECIPES.get(category, RECIPES["general_failure"])
