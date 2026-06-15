"""Tests for storage_server.save_module_to_db via MCPClient.

Verifies the MCP tool delegates to backend.analytics.persistence.save_module
via backend.analytics.db.get_db, so a saved module round-trips through the
same schema/migrations used by the rest of the app. No ChromaDB/embeddings
involved, so this test is not marked slow.
"""
from __future__ import annotations

import json

from backend.analytics.db import get_db
from backend.analytics.persistence import load_module
from backend.core.mcp_client import MCPClient


def test_save_module_to_db_round_trips(tmp_path):
    db_path = str(tmp_path / "test.db")

    client = MCPClient("mcp_servers.storage_server.server")
    try:
        client.start()

        result = json.loads(client.call(
            "save_module_to_db",
            module_id="mod-1",
            title="Test Module",
            source_filename="test.pdf",
            module_json='{"module_id": "mod-1"}',
            question_bank_json="{}",
            created_by="user-1",
            db_path=db_path,
        ))
        assert result == {"status": "ok", "module_id": "mod-1"}
    finally:
        client.close()

    conn = get_db(db_path)
    try:
        row = load_module("mod-1", db=conn)
    finally:
        conn.close()

    assert row is not None
    assert row["title"] == "Test Module"
    assert row["source_filename"] == "test.pdf"
    assert row["created_by"] == "user-1"
