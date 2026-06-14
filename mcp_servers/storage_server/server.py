"""MCP server for storage (SQLite + ChromaDB).

Exposes tools for persisting modules and semantic search.
Run standalone: PYTHONPATH=. uv run python -m mcp_servers.storage_server.server
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("storage_server")

_DB_PATH = os.environ.get("AI_TUTOR_DB_PATH", "data/ai_tutor.db")
_CHROMA_DIR = os.environ.get("AI_TUTOR_CHROMA_DIR", "data/chroma")


def _get_db() -> sqlite3.Connection:
    path = _DB_PATH
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_chroma_collection():
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    Path(_CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=_CHROMA_DIR)
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    return client.get_or_create_collection(
        name="document_chunks",
        embedding_function=ef,
    )


@mcp.tool()
def save_module_to_db(
    module_id: str,
    title: str,
    source_filename: str,
    module_json: str,
    question_bank_json: str,
    created_by: str,
) -> str:
    """Save a learning module and its question bank to SQLite."""
    conn = _get_db()
    conn.execute(
        """
        INSERT OR REPLACE INTO modules
            (module_id, title, source_filename, module_json, question_bank_json, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (module_id, title, source_filename, module_json, question_bank_json, created_by),
    )
    conn.commit()
    conn.close()
    return json.dumps({"status": "ok", "module_id": module_id})


@mcp.tool()
def upsert_to_vector_db(
    documents: list[str],
    ids: list[str],
    metadatas: list[dict] | None = None,
) -> str:
    """Upsert document chunks into ChromaDB for semantic search."""
    collection = _get_chroma_collection()
    kwargs = {"documents": documents, "ids": ids}
    if metadatas:
        kwargs["metadatas"] = metadatas
    collection.upsert(**kwargs)
    return json.dumps({"status": "ok", "count": len(documents)})


@mcp.tool()
def query_vector_db(
    query_text: str,
    n_results: int = 5,
    where_filter: dict | None = None,
) -> str:
    """Query ChromaDB for semantically similar document chunks."""
    collection = _get_chroma_collection()
    kwargs = {"query_texts": [query_text], "n_results": n_results}
    if where_filter:
        kwargs["where"] = where_filter
    results = collection.query(**kwargs)
    return json.dumps({
        "documents": results.get("documents", []),
        "ids": results.get("ids", []),
        "distances": results.get("distances", []),
    })


if __name__ == "__main__":
    mcp.run()
