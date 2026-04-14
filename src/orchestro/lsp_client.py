from __future__ import annotations

import json
import os
import select
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from orchestro.paths import data_dir

EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".rs": "rust",
    ".ts": "typescript",
    ".js": "javascript",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
}


def file_uri(path: str) -> str:
    absolute = str(Path(path).resolve())
    return f"file://{absolute}"


def language_for_file(path: str) -> str | None:
    return EXTENSION_LANGUAGE_MAP.get(Path(path).suffix.lower())


@dataclass(slots=True)
class LSPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    root_uri: str = ""
    enabled: bool = True


class LSPConnection:
    def __init__(self, config: LSPServerConfig) -> None:
        self.config = config
        self.process: subprocess.Popen | None = None
        self._request_id = 0
        self.capabilities: dict = {}
        self._pending_diagnostics: dict[str, list[dict]] = {}
        self.last_error: str | None = None

    def start(self, workspace_root: str) -> bool:
        self.last_error = None
        try:
            self.process = subprocess.Popen(
                [self.config.command] + self.config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ},
            )
            root = self.config.root_uri or workspace_root
            root_uri = root if root.startswith("file://") else file_uri(root)
            resp = self._send_request("initialize", {
                "processId": os.getpid(),
                "rootUri": root_uri,
                "capabilities": {
                    "textDocument": {
                        "definition": {"dynamicRegistration": False},
                        "references": {"dynamicRegistration": False},
                        "hover": {"dynamicRegistration": False},
                        "documentSymbol": {"dynamicRegistration": False},
                        "diagnostic": {"dynamicRegistration": False},
                        "publishDiagnostics": {},
                    },
                    "workspace": {
                        "symbol": {"dynamicRegistration": False},
                    },
                },
            })
            if resp is None:
                self.last_error = "initialize request failed"
                self._terminate()
                return False
            self.capabilities = resp.get("capabilities", {})
            self._send_notification("initialized", {})
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self._terminate()
            return False

    def stop(self) -> None:
        if self.process is None:
            return
        try:
            self._send_request("shutdown", {})
        except Exception:
            pass
        try:
            self._send_notification("exit", {})
        except Exception:
            pass
        self._terminate()

    def diagnostics(self, file_uri_str: str) -> list[dict]:
        resp = self._send_request("textDocument/diagnostic", {
            "textDocument": {"uri": file_uri_str},
        })
        if resp and "items" in resp:
            return resp["items"]
        self._drain_notifications()
        return self._pending_diagnostics.get(file_uri_str, [])

    def definition(self, file_uri_str: str, line: int, col: int) -> list[dict]:
        resp = self._send_request("textDocument/definition", {
            "textDocument": {"uri": file_uri_str},
            "position": {"line": line, "character": col},
        })
        if resp is None:
            return []
        if isinstance(resp, dict):
            return [resp]
        if isinstance(resp, list):
            return resp
        return []

    def references(self, file_uri_str: str, line: int, col: int) -> list[dict]:
        resp = self._send_request("textDocument/references", {
            "textDocument": {"uri": file_uri_str},
            "position": {"line": line, "character": col},
            "context": {"includeDeclaration": True},
        })
        if isinstance(resp, list):
            return resp
        return []

    def hover(self, file_uri_str: str, line: int, col: int) -> dict | None:
        return self._send_request("textDocument/hover", {
            "textDocument": {"uri": file_uri_str},
            "position": {"line": line, "character": col},
        })

    def document_symbols(self, file_uri_str: str) -> list[dict]:
        resp = self._send_request("textDocument/documentSymbol", {
            "textDocument": {"uri": file_uri_str},
        })
        if isinstance(resp, list):
            return resp
        return []

    def workspace_symbols(self, query: str) -> list[dict]:
        resp = self._send_request("workspace/symbol", {"query": query})
        if isinstance(resp, list):
            return resp
        return []

    def _send_request(self, method: str, params: dict) -> dict | None:
        self._request_id += 1
        msg = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        self._write_message(msg)
        expected_id = self._request_id
        while True:
            resp = self._read_message()
            if resp is None:
                self.last_error = f"{method} request failed"
                return None
            if "id" in resp and resp["id"] == expected_id:
                if "error" in resp:
                    error = resp["error"]
                    if isinstance(error, dict):
                        self.last_error = str(error.get("message") or error)
                    else:
                        self.last_error = str(error)
                    return None
                self.last_error = None
                return resp.get("result")
            if "method" in resp and resp.get("method") == "textDocument/publishDiagnostics":
                p = resp.get("params", {})
                self._pending_diagnostics[p.get("uri", "")] = p.get("diagnostics", [])

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

    def _drain_notifications(self) -> None:
        while True:
            msg = self._read_message(timeout=0.5)
            if msg is None:
                break
            if msg.get("method") == "textDocument/publishDiagnostics":
                p = msg.get("params", {})
                self._pending_diagnostics[p.get("uri", "")] = p.get("diagnostics", [])

    def _terminate(self) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.process = None


class LSPManager:
    def __init__(self) -> None:
        self.connections: dict[str, LSPConnection] = {}
        self.configs: list[LSPServerConfig] = []
        self.degraded: list[str] = []
        self.degraded_details: dict[str, str] = {}
        self._language_map: dict[str, LSPServerConfig] = {}

    def load_config(self, data_dir_path: Path | None = None) -> list[LSPServerConfig]:
        config_path = (data_dir_path or data_dir()) / "lsp_servers.json"
        if not config_path.exists():
            return []
        with open(config_path) as f:
            data = json.load(f)
        self.configs = [LSPServerConfig(**s) for s in data.get("servers", [])]
        self._language_map = {}
        for cfg in self.configs:
            if cfg.enabled:
                for lang in cfg.languages:
                    self._language_map.setdefault(lang, cfg)
        return self.configs

    def get_connection(self, language: str, workspace_root: str) -> LSPConnection | None:
        if language in self.connections:
            conn = self.connections[language]
            if conn.process and conn.process.poll() is None:
                return conn
            del self.connections[language]

        cfg = self._language_map.get(language)
        if cfg is None:
            return None
        conn = LSPConnection(cfg)
        if conn.start(workspace_root):
            self.connections[language] = conn
            return conn
        self.degraded.append(cfg.name)
        if conn.last_error:
            self.degraded_details[cfg.name] = conn.last_error
        return None

    def stop_all(self) -> None:
        for conn in self.connections.values():
            conn.stop()
        self.connections.clear()

    def supported_languages(self) -> list[str]:
        return [lang for cfg in self.configs for lang in cfg.languages if cfg.enabled]

    def status(self) -> dict:
        active = {}
        for lang, conn in self.connections.items():
            name = conn.config.name
            if name not in active:
                active[name] = []
            active[name].append(lang)
        return {
            "configured": [c.name for c in self.configs],
            "active": active,
            "degraded": self.degraded,
            "degraded_details": self.degraded_details,
            "supported_languages": self.supported_languages(),
        }
