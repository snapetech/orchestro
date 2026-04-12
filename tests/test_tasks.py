from __future__ import annotations

from orchestro.tasks import TaskPacket, validate_task_packet


def test_validate_valid_packet_no_errors():
    packet = TaskPacket(objective="Implement feature X")
    errors = validate_task_packet(packet)
    assert errors == []


def test_validate_empty_objective_returns_error():
    packet = TaskPacket(objective="")
    errors = validate_task_packet(packet)
    assert any("objective" in e for e in errors)


def test_task_packet_defaults():
    packet = TaskPacket(objective="do stuff")
    assert packet.commit_policy == "none"
    assert packet.escalation_policy == "escalate"
    assert packet.max_wall_time == 900
    assert packet.reporting == "summary"
    assert packet.scope is None
    assert packet.acceptance_tests is None
    assert packet.context is None
