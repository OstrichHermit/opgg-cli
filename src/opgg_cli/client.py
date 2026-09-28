from __future__ import annotations

import time

import httpx

from . import __version__

MCP_URL = "https://mcp-api.op.gg/mcp"
PROTOCOL_VERSION = "2025-06-18"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = (3.0, 6.0, 9.0)


class OpggApiError(Exception):
    """A tool call failed (JSON-RPC error or transport failure after retries)."""


class OpggClient:
    """One process-lifetime client: new MCP session per instance, discard after use."""

    def __init__(self, timeout: float = 60.0):
        self._client = httpx.Client(
            timeout=timeout,
            base_url=MCP_URL,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        self._session_id: str | None = None
        self._initialized = False
        self._next_id = 0

    def __enter__(self) -> OpggClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def close(self) -> None:
        self._client.close()

    def _post(self, payload: dict) -> httpx.Response:
        headers = {"Mcp-Session-Id": self._session_id} if self._session_id else {}
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._client.post(MCP_URL, json=payload, headers=headers)
                if resp.status_code >= 500 and attempt < MAX_RETRIES:
                    last_exc = OpggApiError(f"HTTP {resp.status_code}")
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    continue
                return resp
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
        raise OpggApiError(f"request failed after {MAX_RETRIES} retries: {last_exc}")

    @staticmethod
    def _decode_json(resp: httpx.Response) -> dict:
        import json

        if "text/event-stream" in resp.headers.get("content-type", ""):
            for line in reversed(resp.text.splitlines()):
                if line.startswith("data:"):
                    data = line[len("data:"):].strip()
                    if data:
                        return json.loads(data)
            raise OpggApiError("empty SSE response")
        try:
            return resp.json()
        except ValueError:
            raise OpggApiError(
                f"non-JSON response (HTTP {resp.status_code}): {resp.text[:200]!r}"
            )

    def _ensure_session(self) -> None:
        if self._initialized:
            return
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "opgg-cli", "version": __version__},
            },
        }
        resp = self._post(payload)
        if resp.status_code >= 400:
            raise OpggApiError(f"initialize failed: HTTP {resp.status_code}")
        body = self._decode_json(resp)
        if "error" in body:
            raise OpggApiError(f"initialize error: {body['error'].get('message')}")
        self._session_id = resp.headers.get("mcp-session-id")
        # The initialized notification replies 202 with an empty body: never parse it.
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    def call_tool(self, name: str, arguments: dict) -> str:
        self._ensure_session()
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        resp = self._post(payload)
        body = self._decode_json(resp)
        if "error" in body:
            raise OpggApiError(f"{name}: {body['error'].get('message', body['error'])}")
        result = body.get("result") or {}
        content = result.get("content") or []
        if result.get("isError"):
            msg = content[0].get("text") if content and isinstance(content[0], dict) else str(result)
            raise OpggApiError(f"{name}: {msg}")
        if not content or not isinstance(content[0], dict) or "text" not in content[0]:
            raise OpggApiError(f"{name}: response has no text content")
        return content[0]["text"]
