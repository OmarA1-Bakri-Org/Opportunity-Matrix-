"""Rube MCP client for calling Composio tools via streamable-http."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RubeClient:
    """Minimal MCP streamable-http client for Rube."""

    def __init__(self, url: str = "https://rube.app/mcp", token: str = ""):
        self.url = url
        self.token = token
        self._session_id: str | None = None
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    def _parse_response(self, resp: httpx.Response) -> dict | None:
        """Parse JSON or SSE response."""
        if "mcp-session-id" in resp.headers:
            self._session_id = resp.headers["mcp-session-id"]

        ct = resp.headers.get("content-type", "")
        if "text/event-stream" in ct:
            last_data = None
            for line in resp.text.split("\n"):
                line = line.strip()
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    if payload:
                        try:
                            last_data = json.loads(payload)
                        except json.JSONDecodeError:
                            pass
            return last_data
        else:
            try:
                return resp.json()
            except Exception:
                return None

    async def _post(self, body: dict, client: httpx.AsyncClient) -> dict | None:
        resp = await client.post(self.url, json=body, headers=self._headers())
        return self._parse_response(resp)

    async def _initialize(self, client: httpx.AsyncClient) -> None:
        init_msg = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "opportunity-matrix", "version": "0.1.0"},
            },
            "id": self._next_id(),
        }
        await self._post(init_msg, client)

        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        await self._post(notif, client)

    async def execute_tools(self, tools: list[dict]) -> list[dict]:
        """Execute tool slugs via RUBE_MULTI_EXECUTE_TOOL. Returns list of results."""
        async with httpx.AsyncClient(timeout=60) as client:
            await self._initialize(client)

            msg = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "RUBE_MULTI_EXECUTE_TOOL",
                    "arguments": {
                        "tools": tools,
                        "sync_response_to_workbench": False,
                        "memory": {},
                        "current_step": "COLLECTING_SIGNALS",
                        "thought": "Collecting market signals for Opportunity Matrix",
                    },
                },
                "id": self._next_id(),
            }
            result = await self._post(msg, client)

            if not result:
                return []

            # MCP result is in result.result.content
            if "result" in result:
                content = result["result"]
                if isinstance(content, dict) and "content" in content:
                    # MCP tool results have content array with text items
                    for item in content["content"]:
                        if item.get("type") == "text":
                            try:
                                parsed = json.loads(item["text"])
                            except (json.JSONDecodeError, TypeError):
                                return [item["text"]]
                            # Unwrap Rube MULTI_EXECUTE envelope:
                            # {data: {data: {results: [{response: {...}, tool_slug, ...}]}}}
                            return self._unwrap_rube_results(parsed)
                if isinstance(content, list):
                    return content
                return [content]

            if "error" in result:
                logger.error(f"Rube error: {result['error']}")
            return []

    @staticmethod
    def _unwrap_rube_results(parsed: Any) -> list[dict]:
        """Extract per-tool result dicts from Rube MULTI_EXECUTE response envelope.

        The Rube response structure is:
            {data: {data: {results: [{response: {...}, tool_slug: str, index: int}, ...]}, ...}}

        Returns the list of per-tool result dicts (the items inside ``results``).
        If the structure doesn't match, returns the parsed value wrapped in a list.
        """
        if not isinstance(parsed, dict):
            return [parsed] if parsed else []

        # Navigate: data -> data -> results
        outer_data = parsed.get("data", parsed)
        if isinstance(outer_data, dict):
            inner_data = outer_data.get("data", outer_data)
            if isinstance(inner_data, dict):
                results = inner_data.get("results", [])
                if isinstance(results, list) and results:
                    return results

        # Fallback: return as single-element list
        return [parsed]

    async def health_check(self) -> bool:
        """Check if Rube MCP is reachable."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    self.url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-03-26",
                            "capabilities": {},
                            "clientInfo": {"name": "opportunity-matrix", "version": "0.1.0"},
                        },
                        "id": 1,
                    },
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception:
            return False
