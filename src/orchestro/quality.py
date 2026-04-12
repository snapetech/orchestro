from __future__ import annotations

QUALITY_LEVELS = (
    "unverified",
    "self-checked",
    "tool-verified",
    "operator-reviewed",
    "operator-edited",
)

QUALITY_RANK = {level: i for i, level in enumerate(QUALITY_LEVELS)}


def quality_from_strategy(strategy_name: str) -> str:
    if strategy_name == "critique-revise":
        return "self-checked"
    if strategy_name == "verified":
        return "tool-verified"
    return "unverified"


def quality_from_rating(rating: str, current: str) -> str:
    rating_level = "operator-reviewed" if rating in ("good", "great", "5", "4") else current
    if QUALITY_RANK.get(rating_level, 0) > QUALITY_RANK.get(current, 0):
        return rating_level
    return current


def promote_quality(current: str, new: str) -> str:
    if QUALITY_RANK.get(new, 0) > QUALITY_RANK.get(current, 0):
        return new
    return current
