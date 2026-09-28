from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

console = Console()

DEFAULT_TABLE_ROWS = 20
_MAX_COLUMNS = 15
_MAX_CELL_CHARS = 48
_MAX_TREE_CHILDREN = 40
_MAX_TREE_DEPTH = 10


def render_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def render_raw(text: str) -> None:
    print(text)


def _split_fields(fields: str | None) -> list[str] | None:
    if not fields:
        return None
    return [f.strip() for f in fields.split(",") if f.strip()]


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        text = value
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        return str(value)
    if len(text) > _MAX_CELL_CHARS:
        return text[: _MAX_CELL_CHARS - 1] + "…"
    return text


def _collect_record_lists(data: Any, out: list, depth: int = 0) -> None:
    if depth > _MAX_TREE_DEPTH:
        return
    if isinstance(data, dict):
        for v in data.values():
            _collect_record_lists(v, out, depth + 1)
    elif isinstance(data, list):
        if data and isinstance(data[0], dict):
            out.append(data)
        for v in data:
            _collect_record_lists(v, out, depth + 1)


def _short(value: Any) -> str:
    text = _cell(value)
    return text.replace("\n", " ")


def _fill_tree(node: Tree, data: Any, depth: int = 0) -> None:
    if isinstance(data, dict):
        items = list(data.items())
        for k, v in items[:_MAX_TREE_CHILDREN]:
            if isinstance(v, (dict, list)) and v:
                branch = node.add(f"[cyan]{k}[/cyan]")
                _fill_tree(branch, v, depth + 1)
            else:
                node.add(f"[cyan]{k}[/cyan]: {_short(v)}")
        if len(items) > _MAX_TREE_CHILDREN:
            node.add(f"… {len(items) - _MAX_TREE_CHILDREN} more keys")
    elif isinstance(data, list):
        for i, v in enumerate(data[:_MAX_TREE_CHILDREN]):
            if isinstance(v, (dict, list)) and v:
                branch = node.add(f"[dim]{i}[/dim]")
                _fill_tree(branch, v, depth + 1)
            else:
                node.add(_short(v))
        if len(data) > _MAX_TREE_CHILDREN:
            node.add(f"… {len(data) - _MAX_TREE_CHILDREN} more items")
    else:
        node.label += f" {_short(data)}"


def render_table(data: Any, title: str = "Result", limit: int = DEFAULT_TABLE_ROWS) -> None:
    candidates: list = []
    _collect_record_lists(data, candidates)
    rows = max(candidates, key=len) if candidates else None
    if not rows:
        tree = Tree(f"[bold]{title}[/bold]")
        _fill_tree(tree, data)
        console.print(tree)
        return
    rows = rows[:limit]
    columns: list[str] = []
    for row in rows:
        for k in row.keys():
            if k not in columns:
                columns.append(k)
    columns = columns[:_MAX_COLUMNS]
    table = Table(title=f"{title} ({len(rows)} rows)", header_style="bold cyan")
    for col in columns:
        table.add_column(col, overflow="fold")
    for row in rows:
        table.add_row(*[_cell(row.get(col)) for col in columns])
    console.print(table)


def common_options() -> tuple:
    """Returns (--json, --raw, --lang, --fields) typer options for command signatures."""
    return (
        typer.Option(False, "--json", help="Print parsed output as JSON."),
        typer.Option(False, "--raw", help="Print the raw MCP response text."),
        typer.Option("en_US", "--lang", help="Locale code, e.g. en_US, ko_KR."),
        typer.Option(
            None,
            "--fields",
            help="Comma-separated desired_output_fields (server-defined closed set).",
        ),
    )


def emit(
    parsed: Any = None,
    raw: str | None = None,
    *,
    as_json: bool = False,
    as_raw: bool = False,
    title: str = "Result",
) -> None:
    if as_raw and raw is not None:
        render_raw(raw)
        return
    if as_json:
        render_json(parsed if parsed is not None else raw)
        return
    if parsed is not None:
        render_table(parsed, title=title)
        return
    if raw is not None:
        render_raw(raw)
