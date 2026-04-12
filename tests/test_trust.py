from __future__ import annotations

import json
from pathlib import Path

from orchestro.trust import (
    TRUST_AUTO,
    TRUST_CONFIRM,
    TRUST_DENY,
    TrustPolicy,
    load_trust_policy,
    resolve_trust_tier,
)


def test_resolve_default_returns_base_tier():
    policy = TrustPolicy()
    assert resolve_trust_tier("bash", policy=policy) == TRUST_AUTO


def test_tool_overrides_override_base_tier():
    policy = TrustPolicy(tool_overrides={"bash": TRUST_CONFIRM})
    assert resolve_trust_tier("bash", policy=policy) == TRUST_CONFIRM


def test_domain_overrides_override_tool_overrides():
    policy = TrustPolicy(
        tool_overrides={"bash": TRUST_CONFIRM},
        domain_overrides={"finance": {"bash": TRUST_AUTO}},
    )
    tier = resolve_trust_tier("bash", policy=policy, domain="finance")
    assert tier == TRUST_AUTO


def test_deny_is_sticky_across_layers():
    policy = TrustPolicy(
        tool_overrides={"bash": TRUST_DENY},
        domain_overrides={"finance": {"bash": TRUST_AUTO}},
    )
    tier = resolve_trust_tier("bash", policy=policy, domain="finance")
    assert tier == TRUST_DENY


def test_session_overrides_applied():
    policy = TrustPolicy(session_overrides={"edit_file": TRUST_CONFIRM})
    assert resolve_trust_tier("edit_file", policy=policy) == TRUST_CONFIRM


def test_session_deny_is_sticky():
    policy = TrustPolicy(
        session_overrides={"bash": TRUST_DENY},
    )
    assert resolve_trust_tier("bash", policy=policy, base_tier=TRUST_AUTO) == TRUST_DENY


def test_load_trust_policy_returns_empty_when_no_file(tmp_path: Path):
    policy = load_trust_policy(tmp_path)
    assert policy == TrustPolicy()


def test_load_trust_policy_reads_file(tmp_path: Path):
    data = {
        "tool_overrides": {"bash": "confirm"},
        "domain_overrides": {"ops": {"bash": "deny"}},
        "session_overrides": {"edit_file": "auto"},
    }
    (tmp_path / "trust.json").write_text(json.dumps(data), encoding="utf-8")
    policy = load_trust_policy(tmp_path)
    assert policy.tool_overrides == {"bash": "confirm"}
    assert policy.domain_overrides == {"ops": {"bash": "deny"}}
    assert policy.session_overrides == {"edit_file": "auto"}
