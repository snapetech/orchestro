from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestro.db import OrchestroDB

RATING_RANK = {"good": 2, "edit": 1, "skip": 0, "bad": -1}
MIN_RATING_RANK = {"good": 2, "edit": 1, "bad": -1}


@dataclass(slots=True)
class PreferenceExample:
    prompt: str
    chosen: str
    rejected: str | None = None
    domain: str | None = None
    source: str = ""
    metadata: dict | None = None


@dataclass(slots=True)
class ExportConfig:
    min_rating: str = "good"
    include_edits: bool = True
    include_corrections: bool = True
    domain: str | None = None
    format: str = "jsonl"
    limit: int = 0


def collect_preference_pairs(db: OrchestroDB, config: ExportConfig) -> list[PreferenceExample]:
    threshold = MIN_RATING_RANK.get(config.min_rating, RATING_RANK.get(config.min_rating, 2))
    interactions = db.list_interactions(limit=999_999_999)
    goal_buckets: dict[str, list[tuple[str, str, str | None, int]]] = defaultdict(list)
    for interaction in interactions:
        if config.domain and interaction.domain != config.domain:
            continue
        rating_str = interaction.rating
        if not rating_str:
            continue
        rank = RATING_RANK.get(rating_str, -2)
        goal_buckets[interaction.query_text].append(
            (interaction.response_text, rating_str, interaction.domain, rank)
        )

    examples: list[PreferenceExample] = []
    for prompt, entries in goal_buckets.items():
        positives = [(resp, rating, domain) for resp, rating, domain, rank in entries if rank >= threshold]
        negatives = [(resp, rating, domain) for resp, rating, domain, rank in entries if rank < threshold]

        if positives and negatives:
            for chosen_resp, chosen_rating, domain in positives:
                for rejected_resp, _rejected_rating, _ in negatives:
                    examples.append(PreferenceExample(
                        prompt=prompt,
                        chosen=chosen_resp,
                        rejected=rejected_resp,
                        domain=domain,
                        source="rating",
                        metadata={"chosen_rating": chosen_rating},
                    ))
        elif positives:
            for chosen_resp, chosen_rating, domain in positives:
                source = "edit" if chosen_rating == "edit" else "rating"
                examples.append(PreferenceExample(
                    prompt=prompt,
                    chosen=chosen_resp,
                    domain=domain,
                    source=source,
                    metadata={"chosen_rating": chosen_rating},
                ))

    if config.include_corrections:
        corrections = db.list_corrections(limit=999_999_999, domain=config.domain)
        for correction in corrections:
            examples.append(PreferenceExample(
                prompt=correction.context,
                chosen=correction.right_answer,
                rejected=correction.wrong_answer,
                domain=correction.domain,
                source="correction",
                metadata={"severity": correction.severity, "correction_id": correction.id},
            ))

    if config.limit > 0:
        examples = examples[: config.limit]

    return examples


def export_jsonl(examples: list[PreferenceExample], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            record = {
                "prompt": ex.prompt,
                "chosen": ex.chosen,
                "rejected": ex.rejected,
                "domain": ex.domain,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def export_dpo(examples: list[PreferenceExample], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            if ex.rejected is None:
                continue
            record = {
                "prompt": ex.prompt,
                "chosen": ex.chosen,
                "rejected": ex.rejected,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def export_sft(examples: list[PreferenceExample], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            record = {
                "messages": [
                    {"role": "user", "content": ex.prompt},
                    {"role": "assistant", "content": ex.chosen},
                ],
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


EXPORTERS = {
    "jsonl": export_jsonl,
    "dpo": export_dpo,
    "sft": export_sft,
}


def export_stats(examples: list[PreferenceExample]) -> dict:
    by_source: dict[str, int] = defaultdict(int)
    by_domain: dict[str, int] = defaultdict(int)
    paired = 0
    unpaired = 0
    for ex in examples:
        by_source[ex.source or "unknown"] += 1
        by_domain[ex.domain or "none"] += 1
        if ex.rejected is not None:
            paired += 1
        else:
            unpaired += 1
    return {
        "total": len(examples),
        "paired": paired,
        "unpaired": unpaired,
        "by_source": dict(by_source),
        "by_domain": dict(by_domain),
    }
