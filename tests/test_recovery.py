from __future__ import annotations

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
