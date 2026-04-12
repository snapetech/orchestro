from __future__ import annotations

from orchestro.quality import (
    QUALITY_LEVELS,
    QUALITY_RANK,
    promote_quality,
    quality_from_rating,
    quality_from_strategy,
)


def test_quality_from_strategy_returns_correct_levels():
    assert quality_from_strategy("critique-revise") == "self-checked"
    assert quality_from_strategy("verified") == "tool-verified"
    assert quality_from_strategy("direct") == "unverified"
    assert quality_from_strategy("unknown-thing") == "unverified"


def test_quality_from_rating_promotes_on_good():
    result = quality_from_rating("good", "unverified")
    assert result == "operator-reviewed"


def test_quality_from_rating_does_not_demote():
    result = quality_from_rating("bad", "operator-edited")
    assert result == "operator-edited"


def test_promote_quality_upgrades():
    assert promote_quality("unverified", "tool-verified") == "tool-verified"
    assert promote_quality("tool-verified", "unverified") == "tool-verified"
    assert promote_quality("self-checked", "self-checked") == "self-checked"


def test_quality_levels_ordering():
    for i in range(len(QUALITY_LEVELS) - 1):
        assert QUALITY_RANK[QUALITY_LEVELS[i]] < QUALITY_RANK[QUALITY_LEVELS[i + 1]]
