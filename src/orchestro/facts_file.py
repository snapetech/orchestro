from __future__ import annotations

from pathlib import Path

from orchestro.db import FactRecord


def render_facts(records: list[FactRecord]) -> str:
    lines = [
        "# Facts",
        "",
        "Canonical accepted facts for Orchestro.",
        "This file is generated from the SQLite fact store by `orchestro facts-sync`.",
        "",
    ]
    accepted = [record for record in records if record.status == "accepted"]
    if not accepted:
        lines.append("_No accepted facts yet._")
        lines.append("")
        return "\n".join(lines)

    grouped: dict[str, list[FactRecord]] = {}
    for record in accepted:
        grouped.setdefault(record.fact_key, []).append(record)

    for fact_key in sorted(grouped):
        lines.append(f"## {fact_key}")
        lines.append("")
        for record in sorted(grouped[fact_key], key=lambda item: item.updated_at, reverse=True):
            source = f" ({record.source})" if record.source else ""
            lines.append(f"- {record.fact_value}{source}")
        lines.append("")
    return "\n".join(lines)


def sync_facts_file(path: Path, records: list[FactRecord]) -> None:
    path.write_text(render_facts(records), encoding="utf-8")
