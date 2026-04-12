from __future__ import annotations

from orchestro.mcp_server import OrchestrOMCPServer


class TestHandleInitialize:
    def test_returns_expected_fields(self, tmp_db):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_initialize({})
        assert "protocolVersion" in result
        assert "capabilities" in result
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "orchestro-memory"


class TestHandleToolsList:
    def test_returns_expected_tool_names(self, tmp_db):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_tools_list()
        names = [t["name"] for t in result["tools"]]
        assert "search_memory" in names
        assert "get_facts" in names
        assert "get_corrections" in names
        assert "record_correction" in names
        assert "get_postmortems" in names


class TestHandleResourcesList:
    def test_returns_expected_uris(self, tmp_db):
        server = OrchestrOMCPServer(tmp_db)
        result = server.handle_resources_list()
        uris = [r["uri"] for r in result["resources"]]
        assert "orchestro://facts" in uris
        assert "orchestro://corrections" in uris
        assert "orchestro://postmortems" in uris
