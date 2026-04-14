from __future__ import annotations

import pytest

from orchestro.recovery import RECIPES, RecoveryRecipe, recovery_recipe_for


def test_each_category_returns_a_recipe():
    for category in RECIPES:
        recipe = recovery_recipe_for(category)
        assert isinstance(recipe, RecoveryRecipe)
        assert recipe.category == category
        assert len(recipe.steps) > 0


def test_step_for_failure_returns_correct_steps():
    recipe = recovery_recipe_for("backend_timeout")
    assert recipe.step_for_failure(0) == "retry_same"
    assert recipe.step_for_failure(1) == "retry_different_backend"
    assert recipe.step_for_failure(2) == "escalate"


def test_step_for_failure_past_end_returns_abandon():
    recipe = recovery_recipe_for("backend_timeout")
    assert recipe.step_for_failure(100) == "abandon"
    assert recipe.step_for_failure(-1) == "abandon"


def test_unknown_category_falls_back_to_general_failure():
    recipe = recovery_recipe_for("totally_unknown_category")
    assert recipe.category == "general_failure"
    assert recipe.steps == ("retry_same", "abandon")


# ---------------------------------------------------------------------------
# Per-recipe verification
# ---------------------------------------------------------------------------

def test_backend_unreachable_recipe_steps():
    recipe = recovery_recipe_for("backend_unreachable")
    assert recipe.steps[0] == "retry_different_backend"


def test_context_overflow_starts_with_compact():
    recipe = recovery_recipe_for("context_overflow")
    assert recipe.steps[0] == "compact_context"


def test_tool_crash_starts_with_retry_same():
    recipe = recovery_recipe_for("tool_crash")
    assert recipe.steps[0] == "retry_same"


def test_approval_timeout_only_escalates():
    recipe = recovery_recipe_for("approval_timeout")
    assert recipe.steps == ("escalate",)


def test_workspace_conflict_only_escalates():
    recipe = recovery_recipe_for("workspace_conflict")
    assert recipe.steps == ("escalate",)


def test_all_recipes_end_with_escalate_or_abandon():
    terminal = {"escalate", "abandon"}
    for recipe in RECIPES.values():
        assert recipe.steps[-1] in terminal, (
            f"Recipe {recipe.category!r} ends with {recipe.steps[-1]!r}"
        )


def test_recovery_recipe_is_frozen():
    recipe = recovery_recipe_for("backend_timeout")
    with pytest.raises((AttributeError, TypeError)):
        recipe.category = "changed"  # type: ignore[misc]


def test_step_index_zero_valid_for_all():
    for category, recipe in RECIPES.items():
        step = recipe.step_for_failure(0)
        assert isinstance(step, str)
        assert step  # non-empty
