from __future__ import annotations

from orchestro.verifiers import (
    BookkeepingVerifier,
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


def test_registry_unknown_verifier_returns_error():
    registry = VerifierRegistry()
    results = registry.verify_output("x = 1", ["unknown-verifier-xyz"])
    assert len(results) == 1
    assert results[0].passed is False
    assert "unknown verifier" in results[0].errors[0]


def test_registry_list_verifiers_includes_defaults():
    registry = VerifierRegistry()
    names = {v["name"] for v in registry.list_verifiers()}
    assert "python-syntax" in names
    assert "json-structure" in names
    assert "bookkeeping" in names


def test_python_syntax_verifier_in_code_block():
    v = PythonSyntaxVerifier()
    result = v.verify("```python\nx = 1\n```")
    assert result.passed is True
    assert result.metadata["blocks_checked"] == 1


def test_python_syntax_verifier_invalid_in_code_block():
    v = PythonSyntaxVerifier()
    result = v.verify("```python\ndef bad(:\n    pass\n```")
    assert result.passed is False
    assert len(result.errors) > 0


def test_json_verifier_checks_expected_keys():
    v = JsonStructureVerifier()
    result = v.verify('{"a": 1}', context={"expected_keys": ["a", "b"]})
    assert result.passed is False
    assert any("missing" in e for e in result.errors)


def test_json_verifier_passes_all_expected_keys():
    v = JsonStructureVerifier()
    result = v.verify('{"a": 1, "b": 2}', context={"expected_keys": ["a", "b"]})
    assert result.passed is True


# ---------------------------------------------------------------------------
# BookkeepingVerifier
# ---------------------------------------------------------------------------

class TestBookkeepingVerifier:
    def test_non_financial_text_skips(self):
        v = BookkeepingVerifier()
        result = v.verify("The sky is blue and the grass is green.")
        assert result.passed is True
        assert result.metadata.get("skipped") is True

    def test_correct_total_passes(self):
        v = BookkeepingVerifier()
        text = (
            "Item A: $10.00\n"
            "Item B: $20.00\n"
            "Total: $30.00\n"
        )
        result = v.verify(text)
        assert result.passed is True
        assert result.errors == []

    def test_incorrect_total_fails(self):
        v = BookkeepingVerifier()
        text = (
            "Item A: $10.00\n"
            "Item B: $20.00\n"
            "Total: $35.00\n"  # wrong — should be 30
        )
        result = v.verify(text)
        assert result.passed is False
        assert len(result.errors) > 0
        assert "total" in result.errors[0].lower() or "sum" in result.errors[0].lower()

    def test_balanced_ledger_passes(self):
        v = BookkeepingVerifier()
        text = (
            "Debits: $500.00\n"
            "Credits: $300.00\n"
            "Balance: $200.00\n"
        )
        result = v.verify(text)
        assert result.passed is True

    def test_unbalanced_ledger_fails(self):
        v = BookkeepingVerifier()
        text = (
            "Debits: $500.00\n"
            "Credits: $300.00\n"
            "Balance: $250.00\n"  # should be 200
        )
        result = v.verify(text)
        assert result.passed is False
        assert any("debits" in e.lower() or "balance" in e.lower() for e in result.errors)

    def test_large_round_amount_warns(self):
        v = BookkeepingVerifier()
        text = "Invoice total: $50,000\nPayment received: $50,000\n"
        result = v.verify(text)
        # Large round amounts should produce a warning
        assert any("round amount" in w or "estimate" in w for w in result.warnings)

    def test_repeated_amount_warns(self):
        v = BookkeepingVerifier()
        text = (
            "Line 1: $99.99\n"
            "Line 2: $99.99\n"
            "Line 3: $99.99\n"
            "Total: $299.97\n"
        )
        result = v.verify(text)
        # Three identical amounts should trigger the duplicate warning
        assert any("appears" in w and "times" in w for w in result.warnings)

    def test_multiple_paragraphs_checked_independently(self):
        v = BookkeepingVerifier()
        # First paragraph: correct; second: wrong
        text = (
            "Item A: $5.00\nItem B: $5.00\nTotal: $10.00\n"
            "\n"
            "Item C: $3.00\nItem D: $4.00\nTotal: $99.00\n"  # wrong
        )
        result = v.verify(text)
        assert result.passed is False
        # Only paragraph 2 should have an error
        assert any("paragraph 2" in e for e in result.errors)
        assert not any("paragraph 1" in e for e in result.errors)
