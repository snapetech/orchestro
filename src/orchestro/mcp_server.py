from __future__ import annotations

import json
import sys
from uuid import uuid4

from orchestro.db import OrchestroDB
from orchestro.paths import db_path


def read_message() -> dict | None:
    header_line = sys.stdin.readline()
    if not header_line:
        return None
    while header_line.strip():
        if header_line.lower().startswith("content-length:"):
            length = int(header_line.split(":", 1)[1].strip())
        header_line = sys.stdin.readline()
        if not header_line:
            return None
    body = sys.stdin.read(length)
    if not body:
        return None
    return json.loads(body)


def write_message(msg: dict) -> None:
    body = json.dumps(msg)
    sys.stdout.write(f"Content-Length: {len(body)}\r\n\r\n{body}")
    sys.stdout.flush()


def _format_facts(db: OrchestroDB) -> str:
    facts = db.list_facts(limit=200)
    if not facts:
        return "No facts stored."
    lines = []
    for f in facts:
        lines.append(f"- {f.fact_key}: {f.fact_value}")
    return "\n".join(lines)


def _format_corrections(db: OrchestroDB, domain: str | None = None) -> str:
    corrections = db.list_corrections(limit=200, domain=domain)
    if not corrections:
        return "No corrections stored."
    lines = []
    for c in corrections:
        domain_tag = f"[{c.domain}] " if c.domain else ""
        lines.append(f"- {domain_tag}{c.context} | wrong: {c.wrong_answer} | right: {c.right_answer}")
    return "\n".join(lines)


def _format_postmortems(db: OrchestroDB, limit: int = 20) -> str:
    postmortems = db.list_postmortems(limit=limit)
    if not postmortems:
        return "No postmortems stored."
    lines = []
    for p in postmortems:
        domain_tag = f"[{p.domain}] " if p.domain else ""
        lines.append(f"- {domain_tag}[{p.category}] {p.summary}: {p.error_message}")
    return "\n".join(lines)


class OrchestrOMCPServer:
    def __init__(self, db: OrchestroDB) -> None:
        self.db = db

    def handle_initialize(self, params: dict) -> dict:
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {"listChanged": False},
            },
            "serverInfo": {"name": "orchestro-memory", "version": "0.1.0"},
        }

    def handle_tools_list(self) -> dict:
        return {
            "tools": [
                {
                    "name": "search_memory",
                    "description": "Search Orchestro memory (interactions, corrections, facts)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "kind": {
                                "type": "string",
                                "enum": ["all", "interactions", "corrections"],
                            },
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "get_facts",
                    "description": "Get all stored facts",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "get_corrections",
                    "description": "Get stored corrections, optionally filtered by domain",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"domain": {"type": "string"}},
                    },
                },
                {
                    "name": "record_correction",
                    "description": "Propose a correction",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "context": {"type": "string"},
                            "wrong_answer": {"type": "string"},
                            "right_answer": {"type": "string"},
                            "domain": {"type": "string"},
                        },
                        "required": ["context", "wrong_answer", "right_answer"],
                    },
                },
                {
                    "name": "get_postmortems",
                    "description": "Get recent failure postmortems",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer"}},
                    },
                },
            ]
        }

    def handle_tools_call(self, params: dict) -> dict:
        name = params["name"]
        args = params.get("arguments", {})

        if name == "search_memory":
            query = args["query"]
            kind = args.get("kind", "all")
            hits = self.db.search(query=query, kind=kind, limit=10)
            if not hits:
                text = "No results found."
            else:
                lines = []
                for h in hits:
                    domain_tag = f"[{h.domain}] " if h.domain else ""
                    lines.append(f"- {domain_tag}({h.source_type}) {h.title}: {h.snippet}")
                text = "\n".join(lines)

        elif name == "get_facts":
            text = _format_facts(self.db)

        elif name == "get_corrections":
            text = _format_corrections(self.db, domain=args.get("domain"))

        elif name == "record_correction":
            correction_id = str(uuid4())
            self.db.add_correction(
                correction_id=correction_id,
                context=args["context"],
                wrong_answer=args["wrong_answer"],
                right_answer=args["right_answer"],
                domain=args.get("domain"),
                severity="normal",
                source_run_id=None,
            )
            text = f"Correction recorded: {correction_id}"

        elif name == "get_postmortems":
            limit = args.get("limit", 20)
            text = _format_postmortems(self.db, limit=limit)

        else:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True,
            }

        return {"content": [{"type": "text", "text": text}]}

    def handle_resources_list(self) -> dict:
        return {
            "resources": [
                {
                    "uri": "orchestro://facts",
                    "name": "Facts",
                    "mimeType": "text/plain",
                },
                {
                    "uri": "orchestro://corrections",
                    "name": "Corrections",
                    "mimeType": "text/plain",
                },
                {
                    "uri": "orchestro://postmortems",
                    "name": "Postmortems",
                    "mimeType": "text/plain",
                },
            ]
        }

    def handle_resources_read(self, params: dict) -> dict:
        uri = params["uri"]
        if uri == "orchestro://facts":
            text = _format_facts(self.db)
        elif uri == "orchestro://corrections":
            text = _format_corrections(self.db)
        elif uri == "orchestro://postmortems":
            text = _format_postmortems(self.db)
        else:
            text = f"Unknown resource: {uri}"
        return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": text}]}

    def run(self) -> None:
        while True:
            msg = read_message()
            if msg is None:
                break
            method = msg.get("method", "")
            params = msg.get("params", {})
            msg_id = msg.get("id")

            if method == "initialize":
                result = self.handle_initialize(params)
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                result = self.handle_tools_list()
            elif method == "tools/call":
                result = self.handle_tools_call(params)
            elif method == "resources/list":
                result = self.handle_resources_list()
            elif method == "resources/read":
                result = self.handle_resources_read(params)
            else:
                write_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                })
                continue

            if msg_id is not None:
                write_message({"jsonrpc": "2.0", "id": msg_id, "result": result})


def main() -> None:
    db = OrchestroDB(db_path())
    server = OrchestrOMCPServer(db)
    server.run()


if __name__ == "__main__":
    main()
