from __future__ import annotations

from orchestro.quality import (
    QUALITY_LEVELS,
    QUALITY_RANK,
    promote_quality,
    quality_from_rating,
    quality_from_strategy,
)


# ---------------------------------------------------------------------------
# quality_from_strategy
# ---------------------------------------------------------------------------

def test_quality_from_strategy_returns_correct_levels():
    assert quality_from_strategy("critique-revise") == "self-checked"
    assert quality_from_strategy("verified") == "tool-verified"
    assert quality_from_strategy("direct") == "unverified"
    assert quality_from_strategy("unknown-thing") == "unverified"


def test_quality_from_strategy_empty_string():
    result = quality_from_strategy("")
    assert result == "unverified"


def test_quality_from_strategy_all_non_matching_return_unverified():
    for name in ("plan-execute", "debate", "pipeline", "custom"):
        assert quality_from_strategy(name) == "unverified"


# ---------------------------------------------------------------------------
# quality_from_rating
# ---------------------------------------------------------------------------

def test_quality_from_rating_promotes_on_good():
    result = quality_from_rating("good", "unverified")
    assert result == "operator-reviewed"


def test_quality_from_rating_promotes_on_great():
    result = quality_from_rating("great", "unverified")
    assert result == "operator-reviewed"


def test_quality_from_rating_promotes_on_5():
    result = quality_from_rating("5", "unverified")
    assert result == "operator-reviewed"


def test_quality_from_rating_promotes_on_4():
    result = quality_from_rating("4", "unverified")
    assert result == "operator-reviewed"


def test_quality_from_rating_does_not_demote():
    result = quality_from_rating("bad", "operator-edited")
    assert result == "operator-edited"


def test_quality_from_rating_bad_keeps_current():
    result = quality_from_rating("bad", "self-checked")
    assert result == "self-checked"


def test_quality_from_rating_no_downgrade_on_negative():
    result = quality_from_rating("1", "tool-verified")
    assert result == "tool-verified"


# ---------------------------------------------------------------------------
# promote_quality
# ---------------------------------------------------------------------------

def test_promote_quality_upgrades():
    assert promote_quality("unverified", "tool-verified") == "tool-verified"
    assert promote_quality("tool-verified", "unverified") == "tool-verified"
    assert promote_quality("self-checked", "self-checked") == "self-checked"


def test_promote_quality_highest_wins():
    assert promote_quality("unverified", "operator-edited") == "operator-edited"
    assert promote_quality("operator-edited", "unverified") == "operator-edited"


def test_promote_quality_equal_keeps_current():
    for level in QUALITY_LEVELS:
        assert promote_quality(level, level) == level


def test_promote_quality_unknown_level_treated_as_zero():
    # Unknown level has no rank → treated as 0; real level should win
    result = promote_quality("nonexistent", "self-checked")
    assert result == "self-checked"


# ---------------------------------------------------------------------------
# QUALITY_LEVELS / QUALITY_RANK
# ---------------------------------------------------------------------------

def test_quality_levels_ordering():
    for i in range(len(QUALITY_LEVELS) - 1):
        assert QUALITY_RANK[QUALITY_LEVELS[i]] < QUALITY_RANK[QUALITY_LEVELS[i + 1]]


def test_all_quality_levels_have_rank():
    for level in QUALITY_LEVELS:
        assert level in QUALITY_RANK


def test_quality_rank_values_are_unique():
    ranks = list(QUALITY_RANK.values())
    assert len(ranks) == len(set(ranks))
