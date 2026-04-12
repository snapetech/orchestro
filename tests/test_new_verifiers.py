from __future__ import annotations

from orchestro.verifiers import SqlParseVerifier


def test_sql_parse_verifier_passes_valid_sql():
    v = SqlParseVerifier()
    result = v.verify("```sql\nSELECT id, name FROM users WHERE active = 1;\n```")
    assert result.passed is True
    assert result.errors == []


def test_sql_parse_verifier_catches_unbalanced_parens():
    v = SqlParseVerifier()
    result = v.verify("```sql\nSELECT id FROM users WHERE (active = 1 AND (role = 'admin');\n```")
    assert result.passed is False
    assert any("parenthesis" in e for e in result.errors)


def test_sql_parse_verifier_warns_delete_without_where():
    v = SqlParseVerifier()
    result = v.verify("```sql\nDELETE FROM users;\n```")
    assert result.passed is True
    assert any("DELETE without WHERE" in w for w in result.warnings)


def test_sql_parse_verifier_warns_drop_table_without_if_exists():
    v = SqlParseVerifier()
    result = v.verify("```sql\nDROP TABLE users;\n```")
    assert result.passed is True
    assert any("DROP TABLE without IF EXISTS" in w for w in result.warnings)


def test_sql_parse_verifier_passes_drop_table_with_if_exists():
    v = SqlParseVerifier()
    result = v.verify("```sql\nDROP TABLE IF EXISTS users;\n```")
    assert result.passed is True
    assert not any("DROP TABLE" in w for w in result.warnings)
