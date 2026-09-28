from __future__ import annotations

from typing import Any, Callable, Optional

import typer
from rich.table import Table

from ..output import _cell, common_options, render_table
from ._common import as_rows as _as_rows, console, num as _num, pct as _pct, run

app = typer.Typer(help="Teamfight Tactics commands", no_args_is_help=True)

_JSON_OPT, _RAW_OPT, _LANG_OPT = common_options()[:3]

_LANG_TOOLS = frozenset(
    {
        "tft_list_augments",
        "tft_list_item_combinations",
    }
)

CHAMPION_ID_HELP = (
    "TFT champion ID, e.g. DA_18_Ahri, TFT18_Akali; use 'opgg tft item-recipes' or "
    "official docs to discover IDs."
)
ITEM_ID_HELP = (
    "TFT item ID, e.g. DA_HextechGunblade, DA_WarmogsArmor; use 'opgg tft item-recipes' "
    "or official docs to discover IDs."
)


def _run(
    tool: str,
    arguments: dict[str, Any],
    *,
    as_json: bool,
    as_raw: bool,
    lang: Optional[str],
    title: str,
    custom_table: Optional[Callable[[Any], None]] = None,
) -> None:
    run(
        tool,
        arguments,
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=None,
        title=title,
        custom_table=custom_table,
        lang_tools=_LANG_TOOLS,
    )


def _rate(value: Any) -> str:
    return _pct(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else ""


def _render_champion_build_table(parsed: Any) -> None:
    rows = _as_rows(parsed)
    table = Table(title=f"Champion Build ({len(rows)} builds)", header_style="bold cyan")
    table.add_column("Champion", overflow="fold")
    table.add_column("Build", overflow="fold")
    table.add_column("Games", justify="right")
    table.add_column("Win Rate", justify="right")
    table.add_column("Top 4", justify="right")
    table.add_column("Avg Place", justify="right")
    for row in rows:
        items = row.get("itemNames") or []
        if isinstance(items, list):
            build = " > ".join(str(i) for i in items)
        else:
            build = str(items)
        table.add_row(
            str(row.get("characterId") or ""),
            build,
            _num(row.get("itemCount")),
            _rate(row.get("winRate")),
            _rate(row.get("top4Rate")),
            "" if row.get("avgPlacement") is None else str(row.get("avgPlacement")),
        )
    console.print(table)


def _render_item_champions_table(parsed: Any) -> None:
    rows = _as_rows(parsed)
    table = Table(title=f"Item Champions ({len(rows)} champions)", header_style="bold cyan")
    table.add_column("Champion", overflow="fold")
    table.add_column("Games", justify="right")
    table.add_column("Win Rate", justify="right")
    table.add_column("Top 4", justify="right")
    table.add_column("Avg Place", justify="right")
    for row in rows:
        table.add_row(
            str(row.get("characterId") or ""),
            _num(row.get("totalCount")),
            _rate(row.get("winRate")),
            _rate(row.get("top4Rate")),
            "" if row.get("avgPlacement") is None else str(row.get("avgPlacement")),
        )
    console.print(table)


def _render_augments_table(parsed: Any) -> None:
    headers = parsed.get("headers") if isinstance(parsed, dict) else None
    rows = parsed.get("rows") if isinstance(parsed, dict) else None
    if not isinstance(headers, list) or not isinstance(rows, list) or not headers:
        render_table(parsed, title="TFT Augments")
        return
    order = [h for h in ("name", "tier", "apiName", "desc") if h in headers]
    order += [h for h in headers if h not in order and h != "imageUrl"]
    idx = {h: headers.index(h) for h in order}
    table = Table(title=f"TFT Augments ({len(rows)} rows)", header_style="bold cyan")
    for h in order:
        table.add_column(h, overflow="fold")
    for row in rows:
        if isinstance(row, dict):
            table.add_row(*[_cell(row.get(h)) for h in order])
        elif isinstance(row, (list, tuple)):
            table.add_row(*[_cell(row[idx[h]] if idx[h] < len(row) else None) for h in order])
    console.print(table)


def _render_recipes_table(parsed: Any) -> None:
    rows = _as_rows(parsed)
    table = Table(title=f"TFT Item Recipes ({len(rows)} items)", header_style="bold cyan")
    table.add_column("Item", overflow="fold")
    table.add_column("Components", overflow="fold")
    table.add_column("Category", overflow="fold")
    table.add_column("Description", overflow="fold")
    for row in rows:
        components = row.get("from")
        if not components and isinstance(row.get("org"), dict):
            components = row["org"].get("compositions")
        if isinstance(components, list):
            components_text = " + ".join(str(c) for c in components)
        else:
            components_text = str(components) if components else ""
        desc = str(row.get("desc") or "").replace("<br>", " ")
        table.add_row(
            str(row.get("name") or ""),
            components_text,
            str(row.get("category") or ""),
            desc,
        )
    console.print(table)


@app.command("champion-build")
def champion_build(
    champion_id: str = typer.Argument(..., help=CHAMPION_ID_HELP),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """Item build recommendations for a TFT champion."""
    _run(
        "tft_get_champion_item_build",
        {"champion_id": champion_id.strip()},
        as_json=as_json,
        as_raw=as_raw,
        lang=None,
        title=f"Champion Build {champion_id.strip()}",
        custom_table=_render_champion_build_table,
    )


@app.command("play-style")
def play_style(
    region: str = typer.Argument(..., help="TFT region code, lowercase, e.g. kr, br, eune."),
    puuid: str = typer.Argument(
        ...,
        help=(
            "Riot PUUID (78 chars); get it from "
            "'opgg lol profile <riot_id> <region> --json' (data.summoner.puuid)."
        ),
    ),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """A player's TFT play style: traits, placements and tendencies."""
    _run(
        "tft_get_play_style",
        {"region": region.strip().lower(), "puuid": puuid.strip()},
        as_json=as_json,
        as_raw=as_raw,
        lang=None,
        title=f"Play Style ({region.strip().lower()})",
    )


@app.command("augments")
def augments(
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
) -> None:
    """All TFT augments with localized names, descriptions and tiers."""
    _run(
        "tft_list_augments",
        {},
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        title="TFT Augments",
        custom_table=_render_augments_table,
    )


@app.command("item-champions")
def item_champions(
    item_id: str = typer.Argument(..., help=ITEM_ID_HELP),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """Champions that can equip a TFT item, with win/pick rates."""
    _run(
        "tft_list_champions_for_item",
        {"item_id": item_id.strip()},
        as_json=as_json,
        as_raw=as_raw,
        lang=None,
        title=f"Item Champions {item_id.strip()}",
        custom_table=_render_item_champions_table,
    )


@app.command("item-recipes")
def item_recipes(
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
) -> None:
    """TFT item combination recipes (components to full items)."""
    _run(
        "tft_list_item_combinations",
        {},
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        title="TFT Item Recipes",
        custom_table=_render_recipes_table,
    )


@app.command("meta-decks")
def meta_decks(
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """Current TFT meta decks with traits, units and placement stats."""
    _run(
        "tft_list_meta_decks",
        {},
        as_json=as_json,
        as_raw=as_raw,
        lang=None,
        title="TFT Meta Decks",
    )
