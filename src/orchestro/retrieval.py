from __future__ import annotations

import os
import re
from dataclasses import dataclass

from orchestro.db import OrchestroDB, SearchHit
from orchestro.embeddings import build_embedding_provider


@dataclass(slots=True)
class RetrievalBundle:
    context_text: str | None
    lexical_hits: list[SearchHit]
    semantic_hits: list[SearchHit]
    postmortem_hits: list[SearchHit]
    selected_hits: list[SearchHit]

    def metadata(self) -> dict[str, object]:
        return {
            "lexical_hits": [
                {
                    "source_type": hit.source_type,
                    "source_id": hit.source_id,
                    "domain": hit.domain,
                    "score": hit.score,
                    "title": hit.title,
                }
                for hit in self.lexical_hits
            ],
            "semantic_hits": [
                {
                    "source_type": hit.source_type,
                    "source_id": hit.source_id,
                    "domain": hit.domain,
                    "score": hit.score,
                    "title": hit.title,
                }
                for hit in self.semantic_hits
            ],
            "selected_hits": [
                {
                    "source_type": hit.source_type,
                    "source_id": hit.source_id,
                    "domain": hit.domain,
                    "score": hit.score,
                    "title": hit.title,
                }
                for hit in self.selected_hits
            ],
            "postmortem_hits": [
                {
                    "source_type": hit.source_type,
                    "source_id": hit.source_id,
                    "domain": hit.domain,
                    "score": hit.score,
                    "title": hit.title,
                }
                for hit in self.postmortem_hits
            ],
        }


class RetrievalBuilder:
    def __init__(self, db: OrchestroDB) -> None:
        self.db = db

    def build(
        self,
        query: str,
        *,
        limit: int = 6,
        domain: str | None = None,
        providers: list[str] | None = None,
    ) -> RetrievalBundle:
        provider_set = set(providers or ["lexical", "semantic", "corrections", "interactions", "postmortems"])
        search_kind = self._search_kind(provider_set)
        lexical_hits = (
            self.db.search(query=query, kind=search_kind, limit=limit, domain=domain)
            if "lexical" in provider_set and search_kind is not None
            else []
        )
        semantic_hits = (
            self._semantic_hits(query=query, limit=limit, domain=domain, kind=search_kind)
            if "semantic" in provider_set and search_kind is not None
            else []
        )
        postmortem_hits = (
            self.db.search_postmortems(query=query, limit=min(limit, 3), domain=domain)
            if "postmortems" in provider_set
            else []
        )
        deduped = self._dedupe_hits(lexical_hits + semantic_hits + postmortem_hits)
        if not deduped:
            return RetrievalBundle(
                context_text=None,
                lexical_hits=lexical_hits,
                semantic_hits=semantic_hits,
                postmortem_hits=postmortem_hits,
                selected_hits=[],
            )

        corrections: list[SearchHit] = []
        interactions: list[SearchHit] = []
        postmortems: list[SearchHit] = []
        for hit in deduped:
            if hit.source_type == "correction":
                corrections.append(hit)
            elif hit.source_type == "interaction":
                interactions.append(hit)
            elif hit.source_type == "postmortem":
                postmortems.append(hit)

        lines = [
            "Use the following retrieved local memory when it is relevant.",
            "Prefer explicit corrections over vague prior examples.",
            "If a retrieved correction conflicts with a general assumption, follow the correction.",
        ]
        if corrections:
            lines.append("")
            lines.append("Important Corrections:")
            for hit in corrections[:3]:
                prefix = "MUST NOT REPEAT" if hit.domain and domain and hit.domain == domain else "CORRECTION"
                lines.append(f"- {prefix} [{hit.domain or '-'}] {hit.title}: {hit.snippet}")
        if interactions:
            lines.append("")
            lines.append("Past Interactions:")
            for hit in interactions[:3]:
                lines.append(f"- [{hit.domain or '-'}] {hit.title}: {hit.snippet}")
        if postmortems:
            lines.append("")
            lines.append("Relevant Failure Lessons:")
            for hit in postmortems[:3]:
                lines.append(f"- [{hit.domain or '-'}] {hit.title}: {hit.snippet}")

        return RetrievalBundle(
            context_text="\n".join(lines),
            lexical_hits=lexical_hits,
            semantic_hits=semantic_hits,
            postmortem_hits=postmortem_hits,
            selected_hits=deduped,
        )

    def _semantic_hits(self, *, query: str, limit: int, domain: str | None, kind: str) -> list[SearchHit]:
        provider_name = os.environ.get("ORCHESTRO_RETRIEVAL_PROVIDER", "hash")
        try:
            status = self.db.vector_status()
            if not status.get("enabled"):
                return []
            embedder = build_embedding_provider(provider_name)
            query_result = embedder.embed(query)
            return self.db.semantic_search(
                query_embedding=query_result.embedding_blob,
                model_name=query_result.model_name,
                kind=kind,
                limit=limit,
                domain=domain,
            )
        except Exception:
            return []

    def _search_kind(self, providers: set[str]) -> str | None:
        include_interactions = "interactions" in providers
        include_corrections = "corrections" in providers
        if include_interactions and include_corrections:
            return "all"
        if include_interactions:
            return "interactions"
        if include_corrections:
            return "corrections"
        return None

    def _dedupe_hits(self, hits: list[SearchHit]) -> list[SearchHit]:
        seen: set[tuple[str, str]] = set()
        seen_interaction_shapes: set[tuple[str | None, str]] = set()
        deduped: list[SearchHit] = []
        for hit in hits:
            key = (hit.source_type, hit.source_id)
            if key in seen:
                continue
            if hit.source_type == "interaction":
                shape = (hit.domain, self._normalize_text(hit.title))
                if shape in seen_interaction_shapes:
                    continue
                seen_interaction_shapes.add(shape)
            seen.add(key)
            deduped.append(hit)
        return deduped

    def _normalize_text(self, value: str) -> str:
        tokens = re.findall(r"[A-Za-z0-9_]+", value.lower())
        return " ".join(tokens)
