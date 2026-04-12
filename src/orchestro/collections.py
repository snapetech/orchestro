from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from orchestro.db import OrchestroDB


class ChunkingStrategy(ABC):
    @abstractmethod
    def chunk(self, text: str, *, source_ref: str = "") -> list[tuple[str, str]]:
        """Returns list of (content, source_ref) tuples."""


class ParagraphChunker(ChunkingStrategy):
    def chunk(self, text: str, *, source_ref: str = "") -> list[tuple[str, str]]:
        raw_paragraphs = re.split(r"\n\n+", text.strip())
        merged: list[str] = []
        for para in raw_paragraphs:
            para = para.strip()
            if not para:
                continue
            if merged and len(merged[-1]) < 100:
                merged[-1] = merged[-1] + "\n\n" + para
            else:
                merged.append(para)
        results: list[tuple[str, str]] = []
        for para in merged:
            if len(para) > 2000:
                para = para[:2000]
            results.append((para, source_ref))
        return results


class MarkdownChunker(ChunkingStrategy):
    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def chunk(self, text: str, *, source_ref: str = "") -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        last_pos = 0
        last_heading = source_ref
        for match in self._HEADING_RE.finditer(text):
            if match.start() > last_pos:
                body = text[last_pos:match.start()].strip()
                if body:
                    sections.append((body, last_heading))
            last_heading = match.group(2).strip()
            last_pos = match.end()
        tail = text[last_pos:].strip()
        if tail:
            sections.append((tail, last_heading))

        merged: list[tuple[str, str]] = []
        for content, ref in sections:
            if merged and len(merged[-1][0]) < 100:
                prev_content, prev_ref = merged[-1]
                merged[-1] = (prev_content + "\n\n" + content, prev_ref)
            else:
                merged.append((content, ref))
        return merged


def ingest_collection(
    db: OrchestroDB,
    collection_id: str,
    text: str,
    *,
    strategy: ChunkingStrategy,
    source_ref: str = "",
) -> int:
    chunks = strategy.chunk(text, source_ref=source_ref)
    for seq, (content, ref) in enumerate(chunks):
        chunk_id = str(uuid4())
        db.add_collection_chunk(
            chunk_id=chunk_id,
            collection_id=collection_id,
            content=content,
            source_ref=ref,
            sequence=seq,
        )
    db.update_collection_stats(collection_id)
    return len(chunks)


def ingest_file(
    db: OrchestroDB,
    collection_id: str,
    file_path: Path,
    *,
    strategy: ChunkingStrategy | None = None,
) -> int:
    text = file_path.read_text(encoding="utf-8")
    if strategy is None:
        strategy = MarkdownChunker() if file_path.suffix == ".md" else ParagraphChunker()
    return ingest_collection(
        db,
        collection_id,
        text,
        strategy=strategy,
        source_ref=file_path.name,
    )


def ingest_directory(
    db: OrchestroDB,
    collection_id: str,
    dir_path: Path,
    *,
    extensions: list[str] | None = None,
) -> int:
    allowed = set(extensions or [".md", ".txt", ".rst"])
    total = 0
    for path in sorted(dir_path.rglob("*")):
        if path.is_file() and path.suffix in allowed:
            total += ingest_file(db, collection_id, path)
    return total
