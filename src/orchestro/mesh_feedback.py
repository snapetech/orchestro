"""Best-effort feedback emission to an Orchestro Mesh gateway.

Reads the mesh metadata that ``MeshBackend`` stamps onto BackendResponse,
translates a list of VerificationResult into a 0..1 rating, and POSTs it
to ``POST /v1/feedback/{request_id}``. Network failures are logged and
swallowed — feedback emission must never break the orchestrator run.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Iterable
from urllib import error, request

if TYPE_CHECKING:
    from orchestro.models import BackendResponse
    from orchestro.verifiers import VerificationResult

logger = logging.getLogger(__name__)

_WARNING_PENALTY_PER = 0.1
_WARNING_FLOOR = 0.6


def _score_one(result: "VerificationResult") -> float:
    if not result.passed:
        return 0.0
    if result.warnings:
        return max(_WARNING_FLOOR, 1.0 - _WARNING_PENALTY_PER * len(result.warnings))
    return 1.0


def _env_weights() -> dict[str, float]:
    raw = os.environ.get("ORCHESTRO_MESH_VERIFIER_WEIGHTS")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("mesh_feedback.invalid_verifier_weights value=%s", raw[:120])
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[str, float] = {}
    for name, weight in parsed.items():
        try:
            out[str(name)] = max(0.0, float(weight))
        except (TypeError, ValueError):
            continue
    return out


def rating_from_results(
    results: Iterable["VerificationResult"],
    weights: dict[str, float] | None = None,
) -> float:
    """Map a verification run to a 0..1 rating.

    - A passing verifier with no warnings → 1.0; warnings deduct 0.1 each, floored at 0.6.
    - A failing verifier → 0.0 (regardless of error count, to keep the signal binary
      at the most important boundary).
    - Empty input → 0.5 (no signal).
    - ``weights`` (per-verifier name → weight) controls relative importance; values
      not in the map default to 1.0. Env override: ``ORCHESTRO_MESH_VERIFIER_WEIGHTS``
      as a JSON object.
    """
    items = list(results)
    if not items:
        return 0.5
    effective_weights = {**_env_weights(), **(weights or {})}
    total_weight = 0.0
    total_score = 0.0
    for result in items:
        weight = effective_weights.get(result.verifier, 1.0)
        if weight <= 0:
            continue
        total_score += _score_one(result) * weight
        total_weight += weight
    if total_weight <= 0:
        return 0.5
    return total_score / total_weight


def maybe_report(
    response: "BackendResponse",
    results: Iterable["VerificationResult"],
    *,
    timeout_s: float = 5.0,
    weights: dict[str, float] | None = None,
) -> bool:
    """If ``response`` was produced by MeshBackend, POST feedback. Returns True if sent.

    Reads gateway_url, token, requester, and request_id from response.metadata.
    Never raises; swallows network/HTTP errors.
    """
    meta = response.metadata or {}
    request_id = meta.get("mesh_request_id")
    gateway_url = meta.get("mesh_gateway_url")
    if not request_id or not gateway_url:
        return False
    items = list(results)
    rating = rating_from_results(items, weights=weights)
    verifier_label = ",".join(sorted({r.verifier for r in items})) or "verifier"
    payload = {
        "rating": rating,
        "verifier": verifier_label,
        "notes": _summarize_errors(items),
    }
    headers = {"Content-Type": "application/json"}
    token = meta.get("mesh_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    requester = meta.get("mesh_requester")
    if requester:
        headers["X-Orchestro-Requester"] = requester

    url = f"{gateway_url.rstrip('/')}/feedback/{request_id}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout_s) as resp:
            resp.read()
        return True
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.warning("mesh_feedback.http_error code=%s detail=%s", exc.code, detail[:200])
    except error.URLError as exc:
        logger.warning("mesh_feedback.network_error reason=%s", exc.reason)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mesh_feedback.unexpected_error error=%s", exc)
    return False


def _summarize_errors(results: Iterable["VerificationResult"]) -> str | None:
    errs: list[str] = []
    for r in results:
        if not r.passed and r.errors:
            errs.extend(r.errors[:3])
    if not errs:
        return None
    return "; ".join(errs)[:500]
