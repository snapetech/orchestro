from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from orchestro.mcp_client import (
    MCPClientManager,
    MCPConnection,
    MCPServerConfig,
    _make_mcp_runner,
)
from orchestro.tools import ToolRegistry


# ---------------------------------------------------------------------------
# MCPServerConfig
# ---------------------------------------------------------------------------

class TestMCPServerConfig:
    def test_required_fields(self):
        cfg = MCPServerConfig(name="test", command="echo")
        assert cfg.name == "test"
        assert cfg.command == "echo"

    def test_defaults(self):
        cfg = MCPServerConfig(name="test", command="cmd")
        assert cfg.args == []
        assert cfg.working_directory is None
        assert cfg.enabled is True
        assert cfg.env is None

    def test_full_config(self):
        cfg = MCPServerConfig(
            name="my-server",
            command="/usr/bin/server",
            args=["--port", "8080"],
            working_directory="/tmp",
            enabled=False,
            env={"KEY": "VAL"},
        )
        assert cfg.args == ["--port", "8080"]
        assert cfg.working_directory == "/tmp"
        assert cfg.enabled is False
        assert cfg.env == {"KEY": "VAL"}


# ---------------------------------------------------------------------------
# MCPConnection
# ---------------------------------------------------------------------------

class TestMCPConnection:
    def _config(self, **kwargs) -> MCPServerConfig:
        return MCPServerConfig(name="test", command="cmd", **kwargs)

    def test_initial_state(self):
        conn = MCPConnection(self._config())
        assert conn.process is None
        assert conn.tools == []
        assert conn._request_id == 0
        assert conn.last_error is None

    def test_start_returns_false_when_command_fails(self):
        cfg = MCPServerConfig(name="t", command="this-command-does-not-exist-xyz")
        conn = MCPConnection(cfg)
        result = conn.start()
        assert result is False
        assert conn.last_error

    def test_stop_with_no_process_is_safe(self):
        conn = MCPConnection(self._config())
        # Should not raise
        conn.stop()

    def test_write_message_with_no_process_is_safe(self):
        conn = MCPConnection(self._config())
        # Should not raise when process is None
        conn._write_message({"jsonrpc": "2.0", "id": 1, "method": "test", "params": {}})

    def test_read_message_with_no_process_returns_none(self):
        conn = MCPConnection(self._config())
        result = conn._read_message()
        assert result is None

    def test_send_request_increments_id(self):
        conn = MCPConnection(self._config())
        # With no process, _read_message returns None → _send_request returns None
        result = conn._send_request("test", {})
        assert conn._request_id == 1
        assert result is None

    def test_call_tool_delegates_to_send_request(self):
        conn = MCPConnection(self._config())
        # No real process — just verifies call_tool goes through _send_request
        result = conn.call_tool("my_tool", {"arg": "val"})
        assert result is None  # None because no process

    def test_stop_terminates_process(self):
        proc = MagicMock()
        proc.stdin = MagicMock()
        conn = MCPConnection(self._config())
        conn.process = proc
        conn.stop()
        proc.terminate.assert_called_once()


# ---------------------------------------------------------------------------
# MCPClientManager
# ---------------------------------------------------------------------------

class TestMCPClientManager:
    def test_initial_state(self):
        mgr = MCPClientManager()
        assert mgr.connections == {}
        assert mgr.degraded == []

    def test_load_config_returns_empty_when_no_file(self, tmp_path: Path):
        mgr = MCPClientManager()
        configs = mgr.load_config(config_dir=tmp_path)
        assert configs == []

    def test_load_config_parses_servers(self, tmp_path: Path):
        payload = {
            "servers": [
                {"name": "s1", "command": "echo", "args": []},
                {"name": "s2", "command": "cat"},
            ]
        }
        (tmp_path / "mcp_servers.json").write_text(json.dumps(payload))
        mgr = MCPClientManager()
        configs = mgr.load_config(config_dir=tmp_path)
        assert len(configs) == 2
        assert configs[0].name == "s1"
        assert configs[1].name == "s2"

    def test_start_all_skips_disabled(self):
        mgr = MCPClientManager()
        cfg = MCPServerConfig(name="disabled", command="echo", enabled=False)
        mgr.start_all([cfg])
        assert "disabled" not in mgr.connections
        assert "disabled" not in mgr.degraded

    def test_start_all_marks_failed_as_degraded(self):
        mgr = MCPClientManager()
        cfg = MCPServerConfig(name="bad", command="this-does-not-exist-xyz", enabled=True)
        mgr.start_all([cfg])
        assert "bad" in mgr.degraded
        assert "bad" in mgr.degraded_details

    def test_status_structure(self):
        mgr = MCPClientManager()
        status = mgr.status()
        assert "connected" in status
        assert "degraded" in status
        assert "degraded_details" in status
        assert "tool_count" in status

    def test_status_empty_when_no_connections(self):
        mgr = MCPClientManager()
        status = mgr.status()
        assert status["connected"] == []
        assert status["tool_count"] == 0

    def test_bridge_tools_registers_tools(self):
        mgr = MCPClientManager()
        conn = MagicMock()
        conn.tools = [{"name": "do_thing", "description": "Does a thing"}]
        mgr.connections["my-server"] = conn

        registry = ToolRegistry()
        count = mgr.bridge_tools(registry)
        assert count == 1
        assert "mcp:my-server:do_thing" in registry._tools

    def test_bridge_tools_prefix_format(self):
        mgr = MCPClientManager()
        conn = MagicMock()
        conn.tools = [{"name": "search", "description": "Search things"}]
        mgr.connections["search-server"] = conn

        registry = ToolRegistry()
        mgr.bridge_tools(registry)
        tool_def = registry._tools["mcp:search-server:search"]
        assert "[MCP:search-server]" in tool_def.description

    def test_stop_all_clears_connections(self):
        mgr = MCPClientManager()
        conn = MagicMock()
        mgr.connections["srv"] = conn
        mgr.stop_all()
        conn.stop.assert_called_once()
        assert mgr.connections == {}

    def test_bridge_tools_empty_when_no_connections(self):
        mgr = MCPClientManager()
        registry = ToolRegistry()
        count = mgr.bridge_tools(registry)
        assert count == 0


# ---------------------------------------------------------------------------
# _make_mcp_runner
# ---------------------------------------------------------------------------

class TestMakeMCPRunner:
    def _conn(self, result: dict | None) -> MagicMock:
        conn = MagicMock()
        conn.config.name = "srv"
        conn.call_tool.return_value = result
        return conn

    def test_successful_text_result(self):
        conn = self._conn({
            "content": [{"type": "text", "text": "Hello from tool"}],
            "isError": False,
        })
        runner = _make_mcp_runner(conn, "my_tool")
        result = runner('{"arg": "val"}', Path("/tmp"))
        assert result.ok is True
        assert "Hello from tool" in result.output

    def test_error_result(self):
        conn = self._conn({
            "content": [{"type": "text", "text": "Error occurred"}],
            "isError": True,
        })
        runner = _make_mcp_runner(conn, "my_tool")
        result = runner("{}", Path("/tmp"))
        assert result.ok is False

    def test_none_result_is_failure(self):
        conn = self._conn(None)
        runner = _make_mcp_runner(conn, "my_tool")
        result = runner("{}", Path("/tmp"))
        assert result.ok is False
        assert "failed" in result.output.lower()

    def test_invalid_json_falls_back_to_input_key(self):
        conn = self._conn({"content": [], "isError": False})
        runner = _make_mcp_runner(conn, "my_tool")
        # Non-JSON argument should not crash
        runner("plain text argument", Path("/tmp"))
        # call_tool should have been called with {"input": "plain text argument"}
        conn.call_tool.assert_called_once_with("my_tool", {"input": "plain text argument"})

    def test_empty_argument_sends_empty_dict(self):
        conn = self._conn({"content": [], "isError": False})
        runner = _make_mcp_runner(conn, "my_tool")
        runner("  ", Path("/tmp"))
        conn.call_tool.assert_called_once_with("my_tool", {})

    def test_metadata_includes_tool_and_server(self):
        conn = self._conn({"content": [], "isError": False})
        runner = _make_mcp_runner(conn, "my_tool")
        result = runner("{}", Path("/tmp"))
        assert result.metadata["tool"] == "my_tool"
        assert result.metadata["server"] == "srv"

    def test_non_text_content_parts_ignored(self):
        conn = self._conn({
            "content": [
                {"type": "image", "data": "base64..."},
                {"type": "text", "text": "Only this"},
            ],
            "isError": False,
        })
        runner = _make_mcp_runner(conn, "my_tool")
        result = runner("{}", Path("/tmp"))
        assert result.output == "Only this"

    def test_no_content_falls_back_to_json_dump(self):
        conn = self._conn({"isError": False})
        runner = _make_mcp_runner(conn, "my_tool")
        result = runner("{}", Path("/tmp"))
        # No content key → json.dumps(result)
        assert result.ok is True
        assert result.output  # non-empty
