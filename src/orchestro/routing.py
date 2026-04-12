from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestro.db import OrchestroDB


# ---------------------------------------------------------------------------
# Query classifier
# ---------------------------------------------------------------------------

_TASK_TYPE_SIGNALS: dict[str, list[str]] = {
    "code": [
        r"\b(write|fix|debug|implement|refactor|function|class|def |import |syntax|compile"
        r"|test|pytest|unittest|lint|format|sql|query|schema|migration|api|endpoint)\b",
    ],
    "math": [
        r"\b(calculate|compute|solve|equation|formula|integral|derivative|probability"
        r"|statistics|matrix|vector|sum|product|percentage|convert)\b",
    ],
    "search": [
        r"\b(find|search|lookup|retrieve|what is|who is|where is|when did|list|enumerate"
        r"|show me|give me|examples of)\b",
    ],
    "analysis": [
        r"\b(analyze|analyse|compare|evaluate|assess|review|explain|why|how does"
        r"|pros and cons|trade-?off|summarize|summarise)\b",
    ],
    "creative": [
        r"\b(write|draft|compose|generate|create|brainstorm|story|essay|poem|email"
        r"|letter|blog|document|outline)\b",
    ],
}

# Backend capability hints — backends can advertise strengths via their profile names.
_BACKEND_TASK_HINTS: dict[str, set[str]] = {
    "vllm-coding": {"code"},
    "ollama-code": {"code"},
    "vllm-fast": {"search", "creative"},
    "vllm-balanced": {"analysis", "math", "search", "code"},
    "ollama-amd": {"creative"},
}


def classify_query(goal: str) -> str:
    """Return the dominant task type for *goal*: code/math/search/analysis/creative/chat."""
    lower = goal.lower()
    scores: dict[str, int] = {}
    for task_type, patterns in _TASK_TYPE_SIGNALS.items():
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, lower))
        if count > 0:
            scores[task_type] = count
    if not scores:
        return "chat"
    return max(scores, key=lambda k: scores[k])


@dataclass(slots=True)
class RoutingStats:
    backend: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    avg_tokens: float = 0.0
    positive_ratings: int = 0
    negative_ratings: int = 0
    success_rate: float = 0.0


def collect_routing_stats(
    db: OrchestroDB,
    *,
    domain: str | None = None,
    min_runs: int = 5,
) -> dict[str, RoutingStats]:
    with db.connect() as conn:
        if domain:
            rows = conn.execute(
                """
                SELECT
                    r.backend_name,
                    COUNT(*) AS total,
                    SUM(CASE WHEN r.status = 'done' THEN 1 ELSE 0 END) AS ok,
                    SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) AS fail,
                    AVG(r.total_tokens) AS avg_tok
                FROM runs r
                WHERE json_extract(r.metadata_json, '$.domain') = ?
                GROUP BY r.backend_name
                """,
                (domain,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    r.backend_name,
                    COUNT(*) AS total,
                    SUM(CASE WHEN r.status = 'done' THEN 1 ELSE 0 END) AS ok,
                    SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) AS fail,
                    AVG(r.total_tokens) AS avg_tok
                FROM runs r
                GROUP BY r.backend_name
                """,
            ).fetchall()

        rating_rows = conn.execute(
            """
            SELECT
                r.backend_name,
                SUM(CASE WHEN rt.rating = 'good' THEN 1 ELSE 0 END) AS pos,
                SUM(CASE WHEN rt.rating = 'bad' THEN 1 ELSE 0 END) AS neg
            FROM ratings rt
            JOIN runs r ON rt.target_type = 'run' AND rt.target_id = r.id
            GROUP BY r.backend_name
            """,
        ).fetchall()

    ratings_map: dict[str, tuple[int, int]] = {}
    for rr in rating_rows:
        ratings_map[rr["backend_name"]] = (int(rr["pos"]), int(rr["neg"]))

    stats: dict[str, RoutingStats] = {}
    for row in rows:
        total = int(row["total"])
        if total < min_runs:
            continue
        ok = int(row["ok"])
        fail = int(row["fail"])
        avg_tok = float(row["avg_tok"]) if row["avg_tok"] is not None else 0.0
        pos, neg = ratings_map.get(row["backend_name"], (0, 0))
        rate = ok / total if total > 0 else 0.0
        stats[row["backend_name"]] = RoutingStats(
            backend=row["backend_name"],
            total_runs=total,
            successful_runs=ok,
            failed_runs=fail,
            avg_tokens=avg_tok,
            positive_ratings=pos,
            negative_ratings=neg,
            success_rate=rate,
        )
    return stats


def suggest_backend(
    stats: dict[str, RoutingStats],
    *,
    goal: str,
    domain: str | None = None,
    available: set[str],
) -> str | None:
    task_type = classify_query(goal)
    # Prefer backends with a known capability match for this task type.
    task_preferred: list[str] = []
    for backend_name, task_hints in _BACKEND_TASK_HINTS.items():
        if backend_name in available and task_type in task_hints:
            task_preferred.append(backend_name)

    # Score candidates by success rate and task preference.
    candidates = [s for name, s in stats.items() if name in available]
    if not candidates:
        # No history yet — fall back to task-type hint alone.
        return task_preferred[0] if task_preferred else None
    candidates.sort(key=lambda s: (
        -int(s.backend in task_preferred),
        -s.success_rate,
        s.avg_tokens,
    ))
    best = candidates[0]
    # Require a minimum success rate regardless of task hint. A backend
    # that fails more than half the time is not a useful suggestion.
    if best.success_rate <= 0.5:
        return None
    return best.backend


def format_routing_report(stats: dict[str, RoutingStats]) -> str:
    if not stats:
        return "No routing stats available (not enough runs recorded)."
    header = (
        f"{'Backend':<24} {'Runs':>6} {'OK':>6} {'Fail':>6} "
        f"{'Rate':>7} {'AvgTok':>9} {'+':>4} {'-':>4}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for s in sorted(stats.values(), key=lambda s: -s.success_rate):
        lines.append(
            f"{s.backend:<24} {s.total_runs:>6} {s.successful_runs:>6} {s.failed_runs:>6} "
            f"{s.success_rate:>6.1%} {s.avg_tokens:>9.0f} {s.positive_ratings:>4} {s.negative_ratings:>4}"
        )
    return "\n".join(lines)
