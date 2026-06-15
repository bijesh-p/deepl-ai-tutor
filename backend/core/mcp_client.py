"""Synchronous client for the project's MCP tool servers.

Each MCPClient starts its server as a subprocess once (on a background
asyncio event loop thread) and keeps the session open for reuse across
calls — this avoids repeatedly paying the import/startup cost of heavy
servers like storage_server (ChromaDB + sentence-transformers).

Usage:
    from backend.core.mcp_client import get_client

    result_json = get_client("storage_server").call(
        "upsert_to_vector_db", documents=[...], ids=[...], metadatas=[...]
    )
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_SERVER_MODULES = {
    "document_server": "mcp_servers.document_server.server",
    "storage_server": "mcp_servers.storage_server.server",
    "assessment_server": "mcp_servers.assessment_server.server",
}


class MCPClient:
    """Synchronous handle to a single MCP server subprocess."""

    def __init__(self, server_module: str):
        self._server_module = server_module
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session: ClientSession | None = None
        self._shutdown_event: asyncio.Event | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None

    def start(self) -> None:
        """Spawn the server subprocess and open an MCP session (idempotent)."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"mcp-{self._server_module}"
        )
        self._thread.start()
        self._ready.wait()
        if self._error is not None:
            raise self._error

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except BaseException as exc:  # noqa: BLE001 - surfaced via self._error
            self._error = exc
            self._ready.set()

    async def _main(self) -> None:
        """Connect, serve calls, and disconnect — all in one task.

        anyio cancel scopes must be entered and exited by the same task, so
        the whole connection lifecycle (including teardown on close()) runs
        here. call() dispatches into this task's session via
        run_coroutine_threadsafe; close() wakes the shutdown_event below.
        """
        self._shutdown_event = asyncio.Event()
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", self._server_module],
            env={**os.environ},
        )
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    self._ready.set()
                    await self._shutdown_event.wait()
        except BaseException as exc:  # noqa: BLE001 - surfaced via self._error
            self._error = exc
            self._ready.set()
            raise

    def call(self, tool_name: str, **kwargs) -> str:
        """Call a tool and return its text content (a JSON-encoded string)."""
        if self._thread is None:
            self.start()
        future = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(tool_name, kwargs), self._loop
        )
        result = future.result()
        if result.isError:
            raise RuntimeError(f"{tool_name} failed: {result.content}")
        for block in result.content:
            if block.type == "text":
                return block.text
        raise RuntimeError(f"{tool_name} returned no text content")

    def close(self) -> None:
        """Tear down the session, subprocess, and background thread."""
        if self._loop is None or self._thread is None:
            return
        self._loop.call_soon_threadsafe(self._shutdown_event.set)
        self._thread.join(timeout=10)
        self._thread = None


_clients: dict[str, MCPClient] = {}
_clients_lock = threading.Lock()


def get_client(server_name: str) -> MCPClient:
    """Return a lazily-started singleton MCPClient for the named server."""
    if server_name not in _SERVER_MODULES:
        raise ValueError(
            f"Unknown MCP server: {server_name!r}. Known servers: {list(_SERVER_MODULES)}"
        )
    with _clients_lock:
        client = _clients.get(server_name)
        if client is None:
            client = MCPClient(_SERVER_MODULES[server_name])
            client.start()
            _clients[server_name] = client
        return client


def close_all() -> None:
    """Close every cached MCPClient (for test teardown)."""
    with _clients_lock:
        for client in _clients.values():
            client.close()
        _clients.clear()
