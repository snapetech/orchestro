from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from orchestro.escalation import (
    CommandChannel,
    Escalator,
    EscalationEvent,
    FileChannel,
    ShellChannel,
    WebhookChannel,
    load_escalation_config,
    read_escalation_log,
)


def _make_event(run_id: str = "run-1", category: str = "test") -> EscalationEvent:
    return EscalationEvent(
        run_id=run_id,
        reason="test reason",
        category=category,
        channel="shell",
        timestamp="2025-01-01T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# ShellChannel
# ---------------------------------------------------------------------------

def test_shell_channel_send(capsys):
    ch = ShellChannel()
    result = ch.send(_make_event())
    assert result is True
    captured = capsys.readouterr()
    assert "ESCALATION" in captured.out
    assert "run-1" in captured.out


def test_shell_channel_includes_category(capsys):
    ch = ShellChannel()
    ch.send(_make_event(category="budget_exhausted"))
    captured = capsys.readouterr()
    assert "budget_exhausted" in captured.out


# ---------------------------------------------------------------------------
# FileChannel
# ---------------------------------------------------------------------------

def test_file_channel_writes_to_log(tmp_path: Path):
    log_path = tmp_path / "escalations.log"
    ch = FileChannel(path=log_path)
    assert ch.send(_make_event()) is True
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["run_id"] == "run-1"


def test_file_channel_appends_multiple_events(tmp_path: Path):
    log_path = tmp_path / "escalations.log"
    ch = FileChannel(path=log_path)
    ch.send(_make_event("run-1"))
    ch.send(_make_event("run-2"))
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["run_id"] == "run-1"
    assert json.loads(lines[1])["run_id"] == "run-2"


def test_file_channel_creates_parent_dirs(tmp_path: Path):
    log_path = tmp_path / "deep" / "nested" / "escalations.log"
    ch = FileChannel(path=log_path)
    assert ch.send(_make_event()) is True
    assert log_path.exists()


# ---------------------------------------------------------------------------
# WebhookChannel
# ---------------------------------------------------------------------------

def test_webhook_channel_returns_true_on_2xx():
    ch = WebhookChannel("http://example.com/webhook")
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.status = 200
    with patch("orchestro.escalation.urllib.request.urlopen", return_value=mock_resp):
        result = ch.send(_make_event())
    assert result is True


def test_webhook_channel_returns_false_on_url_error():
    import urllib.error
    ch = WebhookChannel("http://unreachable.local/webhook")
    with patch(
        "orchestro.escalation.urllib.request.urlopen",
        side_effect=urllib.error.URLError("refused"),
    ):
        result = ch.send(_make_event())
    assert result is False


# ---------------------------------------------------------------------------
# CommandChannel
# ---------------------------------------------------------------------------

def test_command_channel_sets_env_vars(tmp_path: Path):
    sentinel = tmp_path / "env_out.txt"
    ch = CommandChannel(f'echo "$ESCALATION_RUN_ID" > {sentinel}')
    ch.send(_make_event("cmd-run-42"))
    assert sentinel.read_text().strip() == "cmd-run-42"


def test_command_channel_returns_true_on_success():
    ch = CommandChannel("true")
    assert ch.send(_make_event()) is True


# ---------------------------------------------------------------------------
# load_escalation_config
# ---------------------------------------------------------------------------

def test_load_escalation_config_returns_default_when_no_file(tmp_path: Path):
    channels = load_escalation_config(tmp_path)
    assert "default" in channels
    assert isinstance(channels["default"], ShellChannel)


def test_load_escalation_config_reads_file_channel(tmp_path: Path):
    log = tmp_path / "my.log"
    config = {"channels": {"file": {"type": "file", "path": str(log)}}}
    (tmp_path / "escalation.json").write_text(json.dumps(config))
    channels = load_escalation_config(tmp_path)
    assert "file" in channels
    assert isinstance(channels["file"], FileChannel)


def test_load_escalation_config_bad_json_returns_default(tmp_path: Path):
    (tmp_path / "escalation.json").write_text("not json!!!")
    channels = load_escalation_config(tmp_path)
    assert "default" in channels
    assert isinstance(channels["default"], ShellChannel)


# ---------------------------------------------------------------------------
# Escalator
# ---------------------------------------------------------------------------

def test_escalator_routes_to_channel(capsys):
    escalator = Escalator()
    escalator.escalate(run_id="r1", reason="test", category="general")
    captured = capsys.readouterr()
    assert "r1" in captured.out


def test_escalator_falls_back_to_shell_when_channel_missing(capsys):
    escalator = Escalator(channels={}, default="nonexistent")
    escalator.escalate(run_id="fallback-run", reason="oops", category="test")
    captured = capsys.readouterr()
    assert "fallback-run" in captured.out


# ---------------------------------------------------------------------------
# read_escalation_log
# ---------------------------------------------------------------------------

def test_read_escalation_log_empty_when_no_file(tmp_path: Path):
    entries = read_escalation_log(tmp_path)
    assert entries == []


def test_read_escalation_log_returns_entries(tmp_path: Path):
    log_path = tmp_path / "escalations.log"
    ch = FileChannel(path=log_path)
    ch.send(_make_event("log-run-1"))
    ch.send(_make_event("log-run-2"))
    entries = read_escalation_log(tmp_path)
    assert len(entries) == 2
    assert entries[0]["run_id"] == "log-run-1"


def test_read_escalation_log_respects_limit(tmp_path: Path):
    log_path = tmp_path / "escalations.log"
    ch = FileChannel(path=log_path)
    for i in range(10):
        ch.send(_make_event(f"run-{i}"))
    entries = read_escalation_log(tmp_path, limit=3)
    assert len(entries) == 3
    # Should return the last 3
    assert entries[-1]["run_id"] == "run-9"
