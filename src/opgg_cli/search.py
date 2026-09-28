"""Fuzzy summoner search via the OP.GG website (Next.js RSC payload).

This is a website-scraping data source, separate from the official MCP API in client.py.
"""

from __future__ import annotations

import json
import re
import time
from typing import Optional

import httpx

SEARCH_URL = "https://www.op.gg/lol/summoners/search"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = (3.0, 6.0, 9.0)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)

_RSC_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
_ESCAPE_RE = re.compile(r"\\u\{([0-9a-fA-F]+)\}|\\u([0-9a-fA-F]{4})|\\(.)", re.S)
_RECORD_MARKER = '"data":{"id":'
_SUMMONER_KEYS = ("game_name", "tagline")
_STRING_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


class OpggSearchError(Exception):
    """The search page could not be fetched or parsed."""


class OpggSearchClient:
    """Stateless HTML client for the OP.GG summoner search page."""

    def __init__(self, timeout: float = 60.0):
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        )

    def __enter__(self) -> OpggSearchClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def close(self) -> None:
        self._client.close()

    def fetch(self, query: str, region: str) -> str:
        params = {"q": query, "region": region}
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._client.get(SEARCH_URL, params=params)
                if resp.status_code >= 500 and attempt < MAX_RETRIES:
                    last_exc = OpggSearchError(f"HTTP {resp.status_code}")
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    continue
                if resp.status_code >= 400:
                    raise OpggSearchError(f"search page returned HTTP {resp.status_code}: {resp.url}")
                try:
                    return resp.text
                except UnicodeDecodeError as exc:
                    raise OpggSearchError(f"failed to decode search page body: {exc}")
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
        raise OpggSearchError(f"search request failed after {MAX_RETRIES} retries: {last_exc}")


def _unescape_chunk(chunk: str) -> str:
    def repl(match: re.Match) -> str:
        if match.group(1):
            return chr(int(match.group(1), 16))
        if match.group(2):
            return chr(int(match.group(2), 16))
        return _STRING_ESCAPES.get(match.group(3), match.group(3))

    text = _ESCAPE_RE.sub(repl, chunk)
    if any(0xD800 <= ord(c) <= 0xDFFF for c in text):
        text = _combine_surrogate_pairs(text)
    return text


def _combine_surrogate_pairs(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        cp = ord(text[i])
        if 0xD800 <= cp <= 0xDBFF and i + 1 < len(text) and 0xDC00 <= ord(text[i + 1]) <= 0xDFFF:
            out.append(chr(0x10000 + ((cp - 0xD800) << 10) + (ord(text[i + 1]) - 0xDC00)))
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def extract_rsc_text(html: str) -> str:
    chunks = _RSC_CHUNK_RE.findall(html)
    if not chunks:
        raise OpggSearchError(
            "OP.GG page format changed: no Next.js RSC payload (self.__next_f.push) found in the search page"
        )
    return "".join(_unescape_chunk(chunk) for chunk in chunks)


def _match_object(text: str, start: int) -> Optional[int]:
    """Return the end index (exclusive) of the {...} object starting at `start`, else None."""
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def parse_summoners(rsc_text: str) -> list[dict]:
    summoners: list[dict] = []
    seen_markers = 0
    pos = 0
    while True:
        idx = rsc_text.find(_RECORD_MARKER, pos)
        if idx < 0:
            break
        seen_markers += 1
        start = idx + len('"data":')
        end = _match_object(rsc_text, start)
        if end is None:
            pos = idx + 1
            continue
        pos = end
        try:
            obj = json.loads(rsc_text[start:end])
        except ValueError:
            continue
        if isinstance(obj, dict) and all(key in obj for key in _SUMMONER_KEYS):
            summoners.append(obj)
    if seen_markers and not summoners:
        raise OpggSearchError(
            "OP.GG page format changed: search records were found but none could be parsed as summoners"
        )
    return summoners
