from __future__ import annotations

import json

from orchestro.escalation import (
    EscalationEvent,
    FileChannel,
    ShellChannel,
    load_escalation_config,
)


def _make_event() -> EscalationEvent:
    return EscalationEvent(
        run_id="run-1",
        reason="test reason",
        category="test",
        channel="shell",
        timestamp="2025-01-01T00:00:00+00:00",
    )


def test_shell_channel_send(capsys):
    ch = ShellChannel()
    result = ch.send(_make_event())
    assert result is True
    captured = capsys.readouterr()
    assert "ESCALATION" in captured.out
    assert "run-1" in captured.out


def test_file_channel_writes_to_log(tmp_path):
    log_path = tmp_path / "escalations.log"
    ch = FileChannel(path=log_path)
    assert ch.send(_make_event()) is True
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["run_id"] == "run-1"


def test_load_escalation_config_returns_default_when_no_file(tmp_path):
    channels = load_escalation_config(tmp_path)
    assert "default" in channels
    assert isinstance(channels["default"], ShellChannel)
