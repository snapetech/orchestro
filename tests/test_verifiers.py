from __future__ import annotations

from orchestro.verifiers import (
    JsonStructureVerifier,
    PythonSyntaxVerifier,
    VerifierRegistry,
)


def test_python_syntax_verifier_passes_valid_code():
    v = PythonSyntaxVerifier()
    result = v.verify("x = 1\nprint(x)")
    assert result.passed is True
    assert result.errors == []


def test_python_syntax_verifier_fails_invalid_code():
    v = PythonSyntaxVerifier()
    result = v.verify("def foo(:\n    pass")
    assert result.passed is False
    assert len(result.errors) > 0


def test_json_structure_verifier_passes_valid_json():
    v = JsonStructureVerifier()
    result = v.verify('{"key": "value"}')
    assert result.passed is True
    assert result.errors == []


def test_json_structure_verifier_fails_invalid_json():
    v = JsonStructureVerifier()
    result = v.verify("{bad json}")
    assert result.passed is False
    assert len(result.errors) > 0


def test_registry_verify_output_runs_multiple():
    registry = VerifierRegistry()
    results = registry.verify_output(
        '{"key": 1}',
        ["json-structure", "python-syntax"],
    )
    assert len(results) == 2
    json_result = results[0]
    assert json_result.verifier == "json-structure"
    assert json_result.passed is True
