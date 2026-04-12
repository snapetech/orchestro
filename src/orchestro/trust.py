from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from orchestro.paths import data_dir

TRUST_AUTO = "auto"
TRUST_CONFIRM = "confirm"
TRUST_DENY = "deny"

VALID_TIERS = {TRUST_AUTO, TRUST_CONFIRM, TRUST_DENY}


@dataclass(frozen=True, slots=True)
class TrustPolicy:
    tool_overrides: dict[str, str] = field(default_factory=dict)
    domain_overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    session_overrides: dict[str, str] = field(default_factory=dict)


def _trust_json_path(dir_path: Path | None = None) -> Path:
    base = dir_path if dir_path is not None else data_dir()
    return base / "trust.json"


def load_trust_policy(dir_path: Path | None = None) -> TrustPolicy:
    path = _trust_json_path(dir_path)
    if not path.exists():
        return TrustPolicy()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return TrustPolicy(
        tool_overrides=raw.get("tool_overrides", {}),
        domain_overrides=raw.get("domain_overrides", {}),
        session_overrides=raw.get("session_overrides", {}),
    )


def save_trust_policy(policy: TrustPolicy, dir_path: Path | None = None) -> None:
    path = _trust_json_path(dir_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tool_overrides": policy.tool_overrides,
        "domain_overrides": policy.domain_overrides,
    }
    if policy.session_overrides:
        payload["session_overrides"] = policy.session_overrides
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def resolve_trust_tier(
    tool_name: str,
    *,
    policy: TrustPolicy,
    domain: str | None = None,
    base_tier: str = TRUST_AUTO,
) -> str:
    tier = base_tier
    denied = tier == TRUST_DENY

    if tool_name in policy.tool_overrides:
        override = policy.tool_overrides[tool_name]
        if override == TRUST_DENY:
            denied = True
        if not denied:
            tier = override

    if domain and domain in policy.domain_overrides:
        domain_map = policy.domain_overrides[domain]
        if tool_name in domain_map:
            override = domain_map[tool_name]
            if override == TRUST_DENY:
                denied = True
            if not denied:
                tier = override

    if tool_name in policy.session_overrides:
        override = policy.session_overrides[tool_name]
        if override == TRUST_DENY:
            denied = True
        if not denied:
            tier = override

    if denied:
        return TRUST_DENY
    return tier
