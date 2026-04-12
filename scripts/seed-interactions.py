#!/usr/bin/env python3
"""
seed-interactions.py — Bootstrap rated interactions for training export testing.

Inserts synthetic interactions with ratings into the Orchestro database so
the training export pipeline (orchestro export-preferences) has real data
to work with.

Usage:
    python scripts/seed-interactions.py [--count N] [--db PATH]

    --count N   Number of interactions to insert (default: 100)
    --db PATH   Path to SQLite database (default: .orchestro/orchestro.db)

The seeded interactions cover a realistic mix of domains, strategies, and
quality levels. Roughly 70% receive a 'good' rating, 20% 'bad', and 10%
no rating — matching a plausible daily-use distribution.

After seeding, verify with:
    orchestro facts
    orchestro review --limit 20
    orchestro export-preferences --format dpo --output /tmp/prefs.jsonl
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from uuid import uuid4

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestro.db import OrchestroDB
from orchestro.paths import db_path


DOMAINS = ["coding", "writing", "devops", "research", "data", None]

STRATEGIES = [
    "direct",
    "direct",
    "direct",
    "critique-revise",
    "tool-loop",
    "self-consistency",
    "verified",
]

BACKENDS = [
    "vllm-fast",
    "vllm-balanced",
    "vllm-coding",
    "ollama-amd",
    "mock",
]

CODING_QUERIES = [
    "Write a Python function to parse ISO 8601 dates without external libraries.",
    "Refactor this function to handle None inputs gracefully.",
    "Write a pytest fixture that creates a temporary SQLite database.",
    "Explain why this list comprehension has O(n²) complexity.",
    "Add type annotations to this class without changing its behavior.",
    "Write a context manager that times a block of code.",
    "Fix the off-by-one error in this binary search implementation.",
    "Write a decorator that retries a function up to N times on exception.",
    "Convert this callback-style API to use async/await.",
    "Write a SQL query to find duplicate rows by (email, created_date).",
    "Explain the difference between __str__ and __repr__.",
    "Write a generator that yields batches of N items from an iterable.",
    "Add logging to this module without changing the public interface.",
    "Write a Makefile target that runs tests and linting in one command.",
    "Explain when to use dataclasses vs NamedTuple vs TypedDict.",
]

WRITING_QUERIES = [
    "Write a changelog entry for the new fact-review feature.",
    "Draft a README section explaining the retrieval pipeline.",
    "Write a commit message for a change that adds streaming support.",
    "Draft a brief incident postmortem for a backend timeout.",
    "Write a one-paragraph explanation of constitutional AI for a technical audience.",
    "Draft a PR description for the query classifier change.",
    "Write a migration guide for users upgrading from v1 to v2 of the DB schema.",
    "Write a brief design doc for the approval review workflow.",
]

DEVOPS_QUERIES = [
    "Write a kubectl command to scale vllm-fast to 2 replicas.",
    "Explain how to check if a Kubernetes pod is in CrashLoopBackOff.",
    "Write a bash script that waits for a service to become healthy.",
    "How do I rotate a Kubernetes secret without restarting the pod?",
    "Write a port-forward cleanup trap for a bash script.",
    "Explain the difference between a Deployment and a StatefulSet.",
    "How do I check resource utilization for all pods in a namespace?",
]

RESEARCH_QUERIES = [
    "What are the key differences between DPO and PPO for RLHF?",
    "Summarize the main approaches to context-length extension in LLMs.",
    "What is the constitutional AI approach and how does it differ from RLHF?",
    "Explain the difference between retrieval-augmented generation and fine-tuning.",
    "What are the tradeoffs between quantization approaches for local inference?",
    "Summarize what is known about catastrophic forgetting in fine-tuning.",
]

DATA_QUERIES = [
    "Write a SQL query to compute the 7-day rolling average of run counts.",
    "Explain how to detect schema drift in a SQLite database.",
    "Write a query to find the top 5 backends by success rate with at least 10 runs.",
    "How do I export a SQLite table to a JSONL file efficiently?",
    "Write a query that joins ratings to interactions and computes average score by domain.",
]

GOOD_RESPONSES = [
    "Here is a clean implementation:\n\n```python\ndef parse_date(s: str) -> datetime:\n    # handles ISO 8601 without external libs\n    return datetime.fromisoformat(s.replace('Z', '+00:00'))\n```\n\nThis covers the common case. For full RFC 3339 compliance you'd need to handle fractional seconds separately.",
    "The issue is the loop starts at index 0 and goes to len(items), but the valid range is 0 to len(items)-1. Change `range(len(items))` to `range(len(items)-1)` or use `enumerate` with a guard.",
    "Use a context manager:\n\n```python\n@contextmanager\ndef timer(label: str) -> Iterator[None]:\n    start = time.monotonic()\n    try:\n        yield\n    finally:\n        elapsed = time.monotonic() - start\n        print(f'{label}: {elapsed:.3f}s')\n```",
    "The time complexity is O(n²) because for each element in the outer list (O(n)), the `in` check on the inner list is O(n). Use a set for O(1) lookups.",
    "Rolling average query:\n\n```sql\nSELECT date, AVG(cnt) OVER (ORDER BY date ROWS 6 PRECEDING) AS avg_7d\nFROM daily_run_counts\nORDER BY date;\n```",
]

BAD_RESPONSES = [
    "I'm not able to help with that.",
    "Here's a solution:\n\n```python\nfor i in range(100):\n    print(i)\n```\n\nThis should work.",
    "The answer to your question is complex and depends on many factors. Generally speaking, you should consider the tradeoffs carefully before deciding.",
    "Unfortunately I don't have enough context to answer this question fully.",
    "This is a well-known problem. There are several approaches you could take.",
]


def seed(db: OrchestroDB, count: int, rng: random.Random) -> None:
    all_queries = (
        [(q, "coding") for q in CODING_QUERIES]
        + [(q, "writing") for q in WRITING_QUERIES]
        + [(q, "devops") for q in DEVOPS_QUERIES]
        + [(q, "research") for q in RESEARCH_QUERIES]
        + [(q, "data") for q in DATA_QUERIES]
    )

    inserted = 0
    rated_good = 0
    rated_bad = 0

    for _ in range(count):
        query, domain = rng.choice(all_queries)
        strategy = rng.choice(STRATEGIES)
        backend = rng.choice(BACKENDS)

        run_id = str(uuid4())

        db.create_run(
            run_id=run_id,
            goal=query,
            backend_name=backend,
            strategy_name=strategy,
            working_directory="/home/keith/Documents/code/orchestro",
            metadata={"domain": domain},
        )

        # Simulate token usage.
        prompt_tokens = rng.randint(200, 2000)
        completion_tokens = rng.randint(50, 800)
        db.update_run_token_usage(
            run_id=run_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

        # Pick a response.
        roll = rng.random()
        if roll < 0.75:
            response = rng.choice(GOOD_RESPONSES)
        else:
            response = rng.choice(BAD_RESPONSES)

        db.complete_run(run_id=run_id, final_output=response)

        # 80% of runs get rated; of those, ~85% get 'good'.
        if rng.random() < 0.80:
            rating = "good" if rng.random() < 0.85 else "bad"
            db.add_rating(
                rating_id=str(uuid4()),
                target_type="run",
                target_id=run_id,
                rating=rating,
                note=None,
            )
            if rating == "good":
                rated_good += 1
            else:
                rated_bad += 1

        inserted += 1

    print(f"Seeded {inserted} interactions: {rated_good} good ratings, {rated_bad} bad ratings.")
    print(f"Unrated: {inserted - rated_good - rated_bad}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed rated interactions for training export testing."
    )
    parser.add_argument("--count", type=int, default=100, help="Number of interactions to insert.")
    parser.add_argument("--db", type=Path, default=None, help="Path to SQLite database.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    args = parser.parse_args()

    db_file = args.db or db_path()
    print(f"Database: {db_file}")

    db = OrchestroDB(db_file)
    rng = random.Random(args.seed)

    seed(db, args.count, rng)

    # Show summary stats.
    with db.connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
        rated = conn.execute("SELECT COUNT(*) FROM ratings WHERE target_type = 'run'").fetchone()[0]
    print(f"Total interactions in DB: {total}")
    print(f"Total rated runs: {rated}")
    if total >= 500:
        print("Entry condition for preference training met (≥500 rated interactions).")
    else:
        need = 500 - total
        print(f"Need {need} more interactions to meet the training entry condition.")
        print(f"Run again with --count {need} to reach the threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
