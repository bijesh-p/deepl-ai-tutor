"""MCP client for dispatching tool calls to MCP servers.

Each server runs as a subprocess via stdio transport.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


_SERVER_MODULES = {
    "document_server": "mcp_servers.document_server.server",
    "assessment_server": "mcp_servers.assessment_server.server",
    "storage_server": "mcp_servers.storage_server.server",
}


class MCPClient:

    def __init__(self):
        self._sessions: dict[str, ClientSession] = {}

    async def _get_session(self, server: str) -> ClientSession:
        if server in self._sessions:
            return self._sessions[server]

        module = _SERVER_MODULES.get(server)
        if not module:
            raise ValueError(
                f"Unknown MCP server: {server!r}. "
                f"Available: {list(_SERVER_MODULES.keys())}"
            )

        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", module],
            env=None,
        )

        read_stream, write_stream = await stdio_client(server_params).__aenter__()
        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()
        await session.initialize()

        self._sessions[server] = session
        return session

    async def call(self, server: str, tool: str, **kwargs) -> dict:
        """Call a tool on the named MCP server and return parsed result."""
        session = await self._get_session(server)
        result = await session.call_tool(tool, arguments=kwargs)

        if result.content and len(result.content) > 0:
            text = result.content[0].text
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return {"raw": text}

        return {}

    async def list_tools(self, server: str) -> list[dict]:
        """List available tools on a server."""
        session = await self._get_session(server)
        result = await session.list_tools()
        return [
            {"name": t.name, "description": t.description}
            for t in result.tools
        ]

    async def close(self):
        """Close all active sessions."""
        for session in self._sessions.values():
            await session.__aexit__(None, None, None)
        self._sessions.clear()

    def call_sync(self, server: str, tool: str, **kwargs) -> dict:
        """Synchronous wrapper around call()."""
        return asyncio.run(self.call(server, tool, **kwargs))
