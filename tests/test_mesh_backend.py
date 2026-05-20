"""Tests for the Orchestro Mesh backend + feedback emitter.

These tests stub urllib so the suite stays self-contained — they do not
require an actual orchestro-mesh gateway to be reachable.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass

import pytest

from orchestro.backends import mesh as mesh_module
from orchestro.backends.mesh import MeshBackend
from orchestro import mesh_feedback
from orchestro.models import RunRequest


@dataclass
class _StubResp:
    body: bytes
    status: int = 200

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> "_StubResp":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def close(self) -> None:
        return None

    def __iter__(self):
        return iter(self.body.splitlines(keepends=True))


def _canned_completion(request_id: str = "req-123", node: str = "local-mock-node", model: str = "m") -> bytes:
    body = {
        "id": "completion-1",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hello back"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "orchestro_mesh": {
            "request_id": request_id,
            "node_id": node,
            "model_id": model,
            "attempts": 1,
            "credit_cost": 0.008,
        },
    }
    return json.dumps(body).encode("utf-8")


def test_mesh_backend_run_extracts_metadata(monkeypatch):
    seen: dict = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _StubResp(_canned_completion(request_id="req-abc", node="n1", model="m"))

    monkeypatch.setattr(mesh_module.request, "urlopen", fake_urlopen)

    backend = MeshBackend(
        gateway_url="http://gateway:8765",
        token="tok",
        requester="keith",
        model="m",
    )
    run_request = RunRequest(
        goal="say hi",
        backend_name="mesh",
        metadata={"backend_model": "m", "mesh_task_class": "coding", "mesh_sensitivity": "public"},
    )
    response = backend.run(run_request)

    assert seen["url"] == "http://gateway:8765/v1/chat/completions"
    assert seen["headers"]["authorization"] == "Bearer tok"
    assert seen["headers"]["x-orchestro-requester"] == "keith"
    assert seen["body"]["task_class"] == "coding"
    assert seen["body"]["sensitivity"] == "public"
    assert seen["body"]["model"] == "m"

    assert response.output_text == "hello back"
    assert response.metadata["mesh_request_id"] == "req-abc"
    assert response.metadata["mesh_node_id"] == "n1"
    assert response.metadata["mesh_model_id"] == "m"
    assert response.metadata["mesh_gateway_url"] == "http://gateway:8765/v1"
    assert response.metadata["mesh_token"] == "tok"
    assert response.metadata["mesh_requester"] == "keith"
    assert response.prompt_tokens == 5
    assert response.completion_tokens == 3


def test_mesh_backend_normalizes_gateway_url():
    backend = MeshBackend(gateway_url="http://gateway:8765", token="t")
    url, _, _, _ = backend._resolve()
    assert url == "http://gateway:8765/v1"
    backend2 = MeshBackend(gateway_url="http://gateway:8765/v1", token="t")
    url2, _, _, _ = backend2._resolve()
    assert url2 == "http://gateway:8765/v1"


def test_mesh_backend_requires_gateway_url(monkeypatch):
    monkeypatch.delenv("ORCHESTRO_MESH_GATEWAY_URL", raising=False)
    backend = MeshBackend(gateway_url=None, token=None)
    with pytest.raises(RuntimeError, match="ORCHESTRO_MESH_GATEWAY_URL"):
        backend.run(RunRequest(goal="hi", backend_name="mesh"))


def test_mesh_feedback_rating_math():
    from orchestro.verifiers import VerificationResult

    def vr(passed: bool, errors=None, warnings=None, verifier="v"):
        return VerificationResult(
            passed=passed, verifier=verifier, errors=errors or [], warnings=warnings or []
        )

    assert mesh_feedback.rating_from_results([]) == 0.5
    assert mesh_feedback.rating_from_results([vr(True)]) == 1.0
    assert mesh_feedback.rating_from_results([vr(False)]) == 0.0
    assert mesh_feedback.rating_from_results([vr(True), vr(False)]) == 0.5
    assert mesh_feedback.rating_from_results([vr(True), vr(True), vr(False)]) == pytest.approx(2 / 3)


def test_mesh_feedback_warning_penalty():
    from orchestro.verifiers import VerificationResult

    def vr(warnings):
        return VerificationResult(passed=True, verifier="v", errors=[], warnings=warnings)

    # No warnings → 1.0; 1 warning → 0.9; 4 warnings → 0.6; many warnings floor at 0.6.
    assert mesh_feedback.rating_from_results([vr([])]) == 1.0
    assert mesh_feedback.rating_from_results([vr(["w1"])]) == pytest.approx(0.9)
    assert mesh_feedback.rating_from_results([vr(["w"] * 4)]) == pytest.approx(0.6)
    assert mesh_feedback.rating_from_results([vr(["w"] * 50)]) == pytest.approx(0.6)


def test_mesh_feedback_per_verifier_weights():
    from orchestro.verifiers import VerificationResult

    def vr(passed: bool, verifier: str):
        return VerificationResult(passed=passed, verifier=verifier, errors=[], warnings=[])

    items = [vr(True, "lint"), vr(False, "tests")]
    # Equal weight → 0.5
    assert mesh_feedback.rating_from_results(items) == 0.5
    # Tests heavily weighted → closer to 0
    assert mesh_feedback.rating_from_results(items, weights={"tests": 4.0}) == pytest.approx(1.0 / 5.0)
    # Zero-weighted verifier is excluded entirely
    assert mesh_feedback.rating_from_results(items, weights={"lint": 0.0}) == 0.0


def test_mesh_feedback_env_weights_apply(monkeypatch):
    from orchestro.verifiers import VerificationResult

    def vr(passed: bool, verifier: str):
        return VerificationResult(passed=passed, verifier=verifier, errors=[], warnings=[])

    monkeypatch.setenv("ORCHESTRO_MESH_VERIFIER_WEIGHTS", '{"tests": 9, "lint": 1}')
    items = [vr(True, "lint"), vr(False, "tests")]
    assert mesh_feedback.rating_from_results(items) == pytest.approx(0.1)


def test_mesh_feedback_invalid_env_weights_falls_back(monkeypatch):
    from orchestro.verifiers import VerificationResult

    monkeypatch.setenv("ORCHESTRO_MESH_VERIFIER_WEIGHTS", "not-json")
    items = [VerificationResult(passed=True, verifier="v", errors=[], warnings=[])]
    assert mesh_feedback.rating_from_results(items) == 1.0


def test_mesh_feedback_skips_when_no_request_id():
    from orchestro.models import BackendResponse
    from orchestro.verifiers import VerificationResult

    response = BackendResponse(output_text="x", metadata={"backend": "openai-compat"})
    result = VerificationResult(passed=True, verifier="v", errors=[], warnings=[])
    assert mesh_feedback.maybe_report(response, [result]) is False


def test_mesh_feedback_posts_to_correct_url(monkeypatch):
    from orchestro.models import BackendResponse
    from orchestro.verifiers import VerificationResult

    seen: dict = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _StubResp(b'{"ok":true}')

    monkeypatch.setattr(mesh_feedback.request, "urlopen", fake_urlopen)

    response = BackendResponse(
        output_text="x",
        metadata={
            "mesh_request_id": "req-xyz",
            "mesh_gateway_url": "http://gateway:8765/v1",
            "mesh_token": "tok",
            "mesh_requester": "keith",
        },
    )
    results = [
        VerificationResult(passed=False, verifier="python-syntax", errors=["bad indent"], warnings=[]),
        VerificationResult(passed=True, verifier="json-structure", errors=[], warnings=[]),
    ]
    assert mesh_feedback.maybe_report(response, results) is True
    assert seen["url"] == "http://gateway:8765/v1/feedback/req-xyz"
    assert seen["headers"]["authorization"] == "Bearer tok"
    assert seen["headers"]["x-orchestro-requester"] == "keith"
    assert seen["body"]["rating"] == 0.5
    assert "python-syntax" in seen["body"]["verifier"]
    assert "bad indent" in seen["body"]["notes"]


def test_mesh_feedback_swallows_network_errors(monkeypatch):
    from urllib import error

    from orchestro.models import BackendResponse
    from orchestro.verifiers import VerificationResult

    def boom(req, timeout=None):
        raise error.URLError("connection refused")

    monkeypatch.setattr(mesh_feedback.request, "urlopen", boom)
    response = BackendResponse(
        output_text="x",
        metadata={
            "mesh_request_id": "req-xyz",
            "mesh_gateway_url": "http://gateway:8765/v1",
        },
    )
    result = VerificationResult(passed=True, verifier="v", errors=[], warnings=[])
    # Should NOT raise.
    assert mesh_feedback.maybe_report(response, [result]) is False


def test_default_backends_registers_mesh():
    from orchestro.backend_profiles import build_default_backends

    backends = build_default_backends()
    assert "mesh" in backends
    assert isinstance(backends["mesh"], MeshBackend)
