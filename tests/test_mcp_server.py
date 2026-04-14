from __future__ import annotations

import pytest

from orchestro.db import OrchestroDB
from orchestro.mcp_server import OrchestrOMCPServer


# ---------------------------------------------------------------------------
# handle_initialize
# ---------------------------------------------------------------------------

class TestHandleInitialize:
    def test_returns_expected_fields(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_initialize({})
        assert "protocolVersion" in result
        assert "capabilities" in result
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "orchestro-memory"

    def test_protocol_version_is_string(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_initialize({})
        assert isinstance(result["protocolVersion"], str)

    def test_capabilities_has_tools_and_resources(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_initialize({})
        caps = result["capabilities"]
        assert "tools" in caps
        assert "resources" in caps


# ---------------------------------------------------------------------------
# handle_tools_list
# ---------------------------------------------------------------------------

class TestHandleToolsList:
    def test_returns_expected_tool_names(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_list()
        names = [t["name"] for t in result["tools"]]
        assert "search_memory" in names
        assert "get_facts" in names
        assert "get_corrections" in names
        assert "record_correction" in names
        assert "get_postmortems" in names

    def test_each_tool_has_input_schema(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        for tool in server.handle_tools_list()["tools"]:
            assert "inputSchema" in tool, f"tool {tool['name']} missing inputSchema"

    def test_record_correction_requires_fields(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        tools = {t["name"]: t for t in server.handle_tools_list()["tools"]}
        schema = tools["record_correction"]["inputSchema"]
        required = schema.get("required", [])
        assert "context" in required
        assert "wrong_answer" in required
        assert "right_answer" in required


# ---------------------------------------------------------------------------
# handle_tools_call — search_memory
# ---------------------------------------------------------------------------

class TestHandleToolsCallSearchMemory:
    def test_no_results_returns_none_found(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_call({"name": "search_memory", "arguments": {"query": "xyzzy_not_found"}})
        text = result["content"][0]["text"]
        assert "No results" in text

    def test_returns_content_block(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_call({"name": "search_memory", "arguments": {"query": "anything"}})
        assert "content" in result
        assert result["content"][0]["type"] == "text"


# ---------------------------------------------------------------------------
# handle_tools_call — get_facts
# ---------------------------------------------------------------------------

class TestHandleToolsCallGetFacts:
    def test_empty_db_returns_no_facts(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_call({"name": "get_facts", "arguments": {}})
        text = result["content"][0]["text"]
        assert "No facts" in text

    def test_returns_stored_fact(self, tmp_db: OrchestroDB):
        tmp_db.add_fact(
            fact_id="f1", fact_key="capital", fact_value="Paris", source="test", status="confirmed"
        )
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_call({"name": "get_facts", "arguments": {}})
        text = result["content"][0]["text"]
        assert "capital" in text
        assert "Paris" in text


# ---------------------------------------------------------------------------
# handle_tools_call — get_corrections
# ---------------------------------------------------------------------------

class TestHandleToolsCallGetCorrections:
    def test_empty_db_returns_no_corrections(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_call({"name": "get_corrections", "arguments": {}})
        text = result["content"][0]["text"]
        assert "No corrections" in text

    def test_returns_stored_correction(self, tmp_db: OrchestroDB):
        tmp_db.add_correction(
            correction_id="c1",
            context="Paris is in Germany",
            wrong_answer="Germany",
            right_answer="France",
            domain="geography",
            severity="medium",
            source_run_id=None,
        )
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_call({"name": "get_corrections", "arguments": {}})
        text = result["content"][0]["text"]
        assert "Paris is in Germany" in text
        assert "Germany" in text
        assert "France" in text

    def test_domain_filter_passed(self, tmp_db: OrchestroDB):
        tmp_db.add_correction(
            correction_id="c1", context="ctx", wrong_answer="w", right_answer="r",
            domain="science", severity="low", source_run_id=None,
        )
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_call(
            {"name": "get_corrections", "arguments": {"domain": "geography"}}
        )
        # No geography corrections, so should return empty message
        text = result["content"][0]["text"]
        assert "No corrections" in text


# ---------------------------------------------------------------------------
# handle_tools_call — record_correction
# ---------------------------------------------------------------------------

class TestHandleToolsCallRecordCorrection:
    def test_stores_correction_and_returns_id(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_call({
            "name": "record_correction",
            "arguments": {
                "context": "The earth is flat",
                "wrong_answer": "flat",
                "right_answer": "spherical",
            },
        })
        text = result["content"][0]["text"]
        assert "Correction recorded" in text
        # Verify it was actually stored
        corrections = tmp_db.list_corrections(limit=10)
        assert any(c.context == "The earth is flat" for c in corrections)

    def test_optional_domain_stored(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        server.handle_tools_call({
            "name": "record_correction",
            "arguments": {
                "context": "ctx",
                "wrong_answer": "w",
                "right_answer": "r",
                "domain": "physics",
            },
        })
        corrections = tmp_db.list_corrections(limit=10, domain="physics")
        assert len(corrections) == 1
        assert corrections[0].domain == "physics"


# ---------------------------------------------------------------------------
# handle_tools_call — get_postmortems
# ---------------------------------------------------------------------------

class TestHandleToolsCallGetPostmortems:
    def test_empty_returns_no_postmortems(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_call({"name": "get_postmortems", "arguments": {}})
        text = result["content"][0]["text"]
        assert "No postmortems" in text

    def test_limit_argument_accepted(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        # Should not raise even with an explicit limit
        result = server.handle_tools_call({"name": "get_postmortems", "arguments": {"limit": 5}})
        assert "content" in result


# ---------------------------------------------------------------------------
# handle_tools_call — unknown tool
# ---------------------------------------------------------------------------

class TestHandleToolsCallUnknown:
    def test_unknown_tool_returns_is_error(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_call({"name": "nonexistent_tool_xyz", "arguments": {}})
        assert result.get("isError") is True
        assert "Unknown tool" in result["content"][0]["text"]


# ---------------------------------------------------------------------------
# handle_resources_list
# ---------------------------------------------------------------------------

class TestHandleResourcesList:
    def test_returns_expected_uris(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_resources_list()
        uris = [r["uri"] for r in result["resources"]]
        assert "orchestro://facts" in uris
        assert "orchestro://corrections" in uris
        assert "orchestro://postmortems" in uris

    def test_each_resource_has_mime_type(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        for resource in server.handle_resources_list()["resources"]:
            assert "mimeType" in resource


# ---------------------------------------------------------------------------
# handle_resources_read
# ---------------------------------------------------------------------------

class TestHandleResourcesRead:
    def test_read_facts_resource(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_resources_read({"uri": "orchestro://facts"})
        assert "contents" in result
        contents = result["contents"]
        assert len(contents) == 1
        assert contents[0]["uri"] == "orchestro://facts"
        assert "text" in contents[0]

    def test_read_corrections_resource(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_resources_read({"uri": "orchestro://corrections"})
        assert "contents" in result
        assert result["contents"][0]["uri"] == "orchestro://corrections"

    def test_read_postmortems_resource(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_resources_read({"uri": "orchestro://postmortems"})
        assert "contents" in result
        assert result["contents"][0]["uri"] == "orchestro://postmortems"

    def test_read_unknown_resource_returns_error_text(self, tmp_db: OrchestroDB):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_resources_read({"uri": "orchestro://unknown"})
        text = result["contents"][0]["text"]
        assert "Unknown resource" in text

    def test_read_facts_includes_stored_fact(self, tmp_db: OrchestroDB):
        tmp_db.add_fact(
            fact_id="f1", fact_key="speed_of_light", fact_value="299792458 m/s",
            source="physics", status="confirmed"
        )
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_resources_read({"uri": "orchestro://facts"})
        text = result["contents"][0]["text"]
        assert "speed_of_light" in text
        assert "299792458 m/s" in text
