from __future__ import annotations

from datetime import datetime

from orchestro.scheduler import cron_is_due, parse_cron


def test_parse_cron_wildcards():
    parsed = parse_cron("* * * * *")
    assert all(v is None for v in parsed.values())


def test_parse_cron_comma_separated():
    parsed = parse_cron("0,15,30 * * * *")
    assert parsed["minute"] == {0, 15, 30}


def test_parse_cron_ranges():
    parsed = parse_cron("* 9-17 * * *")
    assert parsed["hour"] == set(range(9, 18))


def test_cron_is_due_matches_current_minute():
    now = datetime(2025, 6, 15, 10, 30)
    assert cron_is_due("30 10 * * *", now=now) is True


def test_cron_is_due_does_not_match_wrong_minute():
    now = datetime(2025, 6, 15, 10, 30)
    assert cron_is_due("0 10 * * *", now=now) is False
