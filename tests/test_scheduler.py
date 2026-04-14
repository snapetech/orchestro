from __future__ import annotations

from datetime import datetime

import pytest

from orchestro.scheduler import ScheduledTask, cron_is_due, parse_cron


# ---------------------------------------------------------------------------
# parse_cron
# ---------------------------------------------------------------------------

def test_parse_cron_wildcards():
    parsed = parse_cron("* * * * *")
    assert all(v is None for v in parsed.values())


def test_parse_cron_comma_separated():
    parsed = parse_cron("0,15,30 * * * *")
    assert parsed["minute"] == {0, 15, 30}


def test_parse_cron_ranges():
    parsed = parse_cron("* 9-17 * * *")
    assert parsed["hour"] == set(range(9, 18))


def test_parse_cron_returns_five_keys():
    parsed = parse_cron("* * * * *")
    assert set(parsed.keys()) == {"minute", "hour", "day", "month", "weekday"}


def test_parse_cron_single_value():
    parsed = parse_cron("5 * * * *")
    assert parsed["minute"] == {5}


def test_parse_cron_wrong_field_count_raises():
    with pytest.raises(ValueError, match="5 fields"):
        parse_cron("* * *")


def test_parse_cron_out_of_range_raises():
    with pytest.raises(ValueError):
        parse_cron("60 * * * *")  # minute max is 59


def test_parse_cron_range_out_of_bounds_raises():
    with pytest.raises(ValueError):
        parse_cron("* 0-24 * * *")  # hour max is 23


def test_parse_cron_day_range():
    parsed = parse_cron("* * 1-5 * *")
    assert parsed["day"] == {1, 2, 3, 4, 5}


def test_parse_cron_month_value():
    parsed = parse_cron("* * * 12 *")
    assert parsed["month"] == {12}


def test_parse_cron_weekday_value():
    parsed = parse_cron("* * * * 0")
    assert parsed["weekday"] == {0}


# ---------------------------------------------------------------------------
# cron_is_due
# ---------------------------------------------------------------------------

def test_cron_is_due_matches_current_minute():
    now = datetime(2025, 6, 15, 10, 30)
    assert cron_is_due("30 10 * * *", now=now) is True


def test_cron_is_due_does_not_match_wrong_minute():
    now = datetime(2025, 6, 15, 10, 30)
    assert cron_is_due("0 10 * * *", now=now) is False


def test_cron_is_due_wildcard_always_matches():
    now = datetime(2025, 1, 1, 0, 0)
    assert cron_is_due("* * * * *", now=now) is True


def test_cron_is_due_wrong_hour():
    now = datetime(2025, 6, 15, 11, 0)
    assert cron_is_due("0 10 * * *", now=now) is False


def test_cron_is_due_specific_day_matches():
    now = datetime(2025, 6, 15, 0, 0)  # day 15
    assert cron_is_due("0 0 15 * *", now=now) is True


def test_cron_is_due_specific_month_mismatch():
    now = datetime(2025, 6, 15, 0, 0)  # month 6
    assert cron_is_due("0 0 * 1 *", now=now) is False


def test_cron_is_due_comma_separated_minutes():
    now = datetime(2025, 6, 15, 10, 15)
    assert cron_is_due("0,15,30,45 * * * *", now=now) is True


# ---------------------------------------------------------------------------
# ScheduledTask
# ---------------------------------------------------------------------------

def test_scheduled_task_defaults():
    task = ScheduledTask(
        task_id="t1", name="daily", schedule="0 9 * * *", goal="Do backup"
    )
    assert task.strategy == "direct"
    assert task.autonomous is True
    assert task.enabled is True
    assert task.run_count == 0
    assert task.domain is None
    assert task.backend is None
    assert task.last_run_at is None


def test_scheduled_task_full():
    task = ScheduledTask(
        task_id="t2",
        name="weekly",
        schedule="0 0 * * 1",
        goal="Weekly report",
        backend="mock",
        strategy="direct",
        domain="analysis",
        autonomous=False,
        max_wall_time=600,
        enabled=False,
    )
    assert task.backend == "mock"
    assert task.domain == "analysis"
    assert task.autonomous is False
    assert task.enabled is False
    assert task.max_wall_time == 600
