"""Integration test for storage_server's ChromaDB tools via MCPClient.

Note: the first run downloads the `all-MiniLM-L6-v2` sentence-transformers
model (~80MB) if it isn't already cached, so this test can be slow the first
time it executes.
"""
from __future__ import annotations

import json

import pytest

from backend.core.mcp_client import MCPClient

pytestmark = pytest.mark.slow

pytest.importorskip("chromadb", reason="chromadb not installed")


def test_upsert_and_query_vector_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_TUTOR_CHROMA_DIR", str(tmp_path / "chroma"))

    client = MCPClient("mcp_servers.storage_server.server")
    try:
        client.start()

        documents = [
            "Photosynthesis converts sunlight, water, and carbon dioxide into "
            "glucose and oxygen inside the chloroplasts of plant cells.",
            "Mitochondria are the organelles responsible for producing ATP "
            "through cellular respiration.",
        ]
        ids = ["topic-photosynthesis", "topic-mitochondria"]

        upsert_result = json.loads(client.call(
            "upsert_to_vector_db",
            documents=documents,
            ids=ids,
            metadatas=[{"title": "Photosynthesis"}, {"title": "Mitochondria"}],
        ))
        assert upsert_result == {"status": "ok", "count": 2}

        query_result = json.loads(client.call(
            "query_vector_db",
            query_text="How do plants turn sunlight into energy?",
            n_results=1,
        ))
        assert query_result["ids"][0][0] == "topic-photosynthesis"
    finally:
        client.close()
