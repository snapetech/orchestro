from __future__ import annotations

import json
import os
import select
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from orchestro.paths import data_dir
from orchestro.tools import ToolDefinition, ToolRegistry, ToolResult


@dataclass(slots=True)
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    working_directory: str | None = None
    enabled: bool = True
    env: dict[str, str] | None = None


class MCPConnection:
    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self.process: subprocess.Popen | None = None
        self.tools: list[dict] = []
        self._request_id = 0

    def start(self) -> bool:
        try:
            self.process = subprocess.Popen(
                [self.config.command] + self.config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.config.working_directory,
                env={**os.environ, **(self.config.env or {})},
            )
            resp = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "orchestro", "version": "0.1.0"},
            })
            if resp is None:
                return False
            self._send_notification("notifications/initialized", {})
            tools_resp = self._send_request("tools/list", {})
            if tools_resp and "tools" in tools_resp:
                self.tools = tools_resp["tools"]
            return True
        except Exception:
            return False

    def call_tool(self, name: str, arguments: dict) -> dict | None:
        return self._send_request("tools/call", {"name": name, "arguments": arguments})

    def stop(self) -> None:
        if self.process:
            try:
                self._send_notification("notifications/cancelled", {})
            except Exception:
                pass
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def _send_request(self, method: str, params: dict) -> dict | None:
        self._request_id += 1
        msg = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        self._write_message(msg)
        resp = self._read_message()
        if resp is None:
            return None
        if "error" in resp:
            return None
        return resp.get("result")

    def _send_notification(self, method: str, params: dict) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        self._write_message(msg)

    def _write_message(self, msg: dict) -> None:
        if self.process is None or self.process.stdin is None:
            return
        body = json.dumps(msg).encode()
        header = f"Content-Length: {len(body)}\r\n\r\n".encode()
        self.process.stdin.write(header + body)
        self.process.stdin.flush()

    def _read_message(self, timeout: float = 10.0) -> dict | None:
        if self.process is None or self.process.stdout is None:
            return None
        stdout_fd = self.process.stdout.fileno()
        ready, _, _ = select.select([stdout_fd], [], [], timeout)
        if not ready:
            return None
        headers = b""
        while True:
            byte = self.process.stdout.read(1)
            if not byte:
                return None
            headers += byte
            if headers.endswith(b"\r\n\r\n"):
                break
        content_length = 0
        for line in headers.decode().split("\r\n"):
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
                break
        if content_length == 0:
            return None
        body = self.process.stdout.read(content_length)
        if len(body) < content_length:
            return None
        return json.loads(body)


class MCPClientManager:
    def __init__(self) -> None:
        self.connections: dict[str, MCPConnection] = {}
        self.degraded: list[str] = []

    def load_config(self, config_dir: Path | None = None) -> list[MCPServerConfig]:
        config_path = (config_dir or data_dir()) / "mcp_servers.json"
        if not config_path.exists():
            return []
        with open(config_path) as f:
            data = json.load(f)
        return [MCPServerConfig(**s) for s in data.get("servers", [])]

    def start_all(self, configs: list[MCPServerConfig]) -> None:
        for config in configs:
            if not config.enabled:
                continue
            conn = MCPConnection(config)
            if conn.start():
                self.connections[config.name] = conn
            else:
                self.degraded.append(config.name)

    def bridge_tools(self, registry: ToolRegistry) -> int:
        count = 0
        for server_name, conn in self.connections.items():
            for tool in conn.tools:
                mcp_tool_name = f"mcp:{server_name}:{tool['name']}"
                description = tool.get("description", "")
                runner = _make_mcp_runner(conn, tool["name"])
                definition = ToolDefinition(
                    name=mcp_tool_name,
                    description=f"[MCP:{server_name}] {description}",
                    approval="confirm",
                    runner=runner,
                )
                registry._tools[mcp_tool_name] = definition
                count += 1
        return count

    def stop_all(self) -> None:
        for conn in self.connections.values():
            conn.stop()
        self.connections.clear()

    def status(self) -> dict:
        return {
            "connected": list(self.connections.keys()),
            "degraded": self.degraded,
            "tool_count": sum(len(c.tools) for c in self.connections.values()),
        }


def _make_mcp_runner(conn: MCPConnection, tool_name: str) -> Callable[[str, Path], ToolResult]:
    def runner(argument: str, cwd: Path) -> ToolResult:
        del cwd
        try:
            arguments = json.loads(argument) if argument.strip() else {}
        except json.JSONDecodeError:
            arguments = {"input": argument}
        result = conn.call_tool(tool_name, arguments)
        if result is None:
            return ToolResult(ok=False, output="MCP tool call failed", metadata={"tool": tool_name})
        content_parts = result.get("content", [])
        text_parts = [p.get("text", "") for p in content_parts if isinstance(p, dict) and p.get("type") == "text"]
        output = "\n".join(text_parts) if text_parts else json.dumps(result)
        is_error = result.get("isError", False)
        return ToolResult(ok=not is_error, output=output, metadata={"tool": tool_name, "server": conn.config.name})
    return runner
