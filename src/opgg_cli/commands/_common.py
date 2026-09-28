"""Helpers shared by the per-game command modules."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable, Optional

import typer
from rich.console import Console

from ..client import OpggClient, OpggApiError
from ..fields import FIELDS
from ..output import render_json, render_raw, render_table
from ..parser import ParseError, parse_response

console = Console()

FIELDS_OPT = typer.Option(
    None,
    "--fields",
    help=(
        "desired_output_fields pattern from the server closed set; commas inside {...} are "
        "part of a pattern. Repeatable for multiple patterns, e.g. "
        "--fields 'data.summoner.league_stats[].{game_type,win}' --fields region."
    ),
)


def error(message: str) -> None:
    console.print(f"[red]Error:[/red] {message}")


def parse_riot_id(riot_id: str) -> tuple[str, str]:
    game_name, sep, tag_line = riot_id.partition("#")
    game_name = game_name.strip()
    tag_line = tag_line.strip()
    if not sep or not game_name or not tag_line:
        error("riot_id must be in 'gameName#tagLine' format, e.g. 'Hide on bush#KR1'.")
        raise typer.Exit(code=1)
    return game_name, tag_line


def split_field_patterns(values: Iterable[str]) -> list[str]:
    patterns: list[str] = []
    for value in values:
        depth = 0
        current: list[str] = []
        for ch in value:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth = max(depth - 1, 0)
            if ch == "," and depth == 0:
                piece = "".join(current).strip()
                if piece:
                    patterns.append(piece)
                current = []
            else:
                current.append(ch)
        piece = "".join(current).strip()
        if piece:
            patterns.append(piece)
    return patterns


def validate_fields(tool: str, values: list[str]) -> list[str]:
    allowed = FIELDS.get(tool)
    if allowed is None:
        error(f"tool '{tool}' does not support --fields.")
        raise typer.Exit(code=1)
    requested = split_field_patterns(values)
    invalid = [f for f in requested if f not in allowed]
    if invalid:
        error(
            f"invalid --fields pattern(s): {' | '.join(invalid)}. "
            f"Allowed fields for {tool} (closed set):"
        )
        for entry in allowed:
            console.print(f"  [cyan]{entry}[/cyan]")
        raise typer.Exit(code=1)
    return requested


def dig(data: Any, *keys: str) -> Any:
    cur = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def pct(value: Any, digits: int = 1) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return ""
    return f"{value * 100:.{digits}f}%"


def num(value: Any) -> str:
    return f"{value:,}" if isinstance(value, int) else ("" if value is None else str(value))


def short_date(value: Any, fmt: str = "%m-%d %H:%M") -> str:
    if not isinstance(value, str) or not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(fmt)
    except ValueError:
        return value[:16].replace("T", " ")


def as_rows(parsed: Any) -> list:
    """Best-effort row extraction: a direct list of dicts, or its first list-of-dicts value."""
    if isinstance(parsed, list):
        return [r for r in parsed if isinstance(r, dict)]
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


def run(
    tool: str,
    arguments: dict[str, Any],
    *,
    as_json: bool,
    as_raw: bool,
    lang: Optional[str],
    fields: Optional[list[str]],
    title: str,
    custom_table: Optional[Callable[[Any], None]] = None,
    lang_tools: frozenset = frozenset(),
) -> None:
    args = dict(arguments)
    if lang is not None and tool in lang_tools:
        args["lang"] = lang
    requested_fields: Optional[list[str]] = None
    if fields:
        requested_fields = validate_fields(tool, fields)
        if requested_fields:
            args["desired_output_fields"] = requested_fields
    try:
        with OpggClient() as client:
            raw = client.call_tool(tool, args)
        parsed = parse_response(raw)
    except OpggApiError as exc:
        error(str(exc))
        raise typer.Exit(code=1)
    except ParseError as exc:
        if as_raw:
            render_raw(raw)
            return
        error(f"failed to parse response: {exc}")
        raise typer.Exit(code=1)
    if as_raw:
        render_raw(raw)
    elif as_json:
        render_json(parsed)
    elif custom_table is not None and requested_fields is None:
        custom_table(parsed)
    else:
        render_table(parsed, title=title)
