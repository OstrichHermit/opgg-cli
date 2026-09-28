from __future__ import annotations

import re
from enum import Enum
from typing import Any, Callable, Optional

import typer
from rich.table import Table

from ..client import OpggClient, OpggApiError
from ..output import common_options
from ._common import FIELDS_OPT, as_rows, console, num as _num, parse_riot_id, run
from ..parser import ParseError, parse_response

app = typer.Typer(help="Valorant commands", no_args_is_help=True)

_JSON_OPT, _RAW_OPT = common_options()[:2]

MAP_ID_HELP = "Valorant map: name (e.g. ascent, bind, lotus) or UUID from 'opgg valorant maps'."

_UUID_RE = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")

_TIER_GROUPS = [(24, "Immortal"), (21, "Ascendant"), (18, "Diamond"), (15, "Platinum"), (12, "Gold"), (9, "Silver"), (6, "Bronze"), (3, "Iron")]


class Region(str, Enum):
    AP = "ap"
    BR = "br"
    EU = "eu"
    KR = "kr"
    LATAM = "latam"
    NA = "na"


def _resolve_map_id(map_id: str) -> str:
    value = map_id.strip()
    if _UUID_RE.match(value):
        return value
    try:
        with OpggClient() as client:
            raw = client.call_tool("valorant_list_maps", {})
        parsed = parse_response(raw)
    except (OpggApiError, ParseError):
        return value
    entries = parsed.get("data") if isinstance(parsed, dict) else parsed
    if not isinstance(entries, list):
        return value
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        mid = str(entry.get("map_id") or "")
        if not _UUID_RE.match(mid):
            continue
        if str(entry.get("name") or "").lower() == value.lower() or mid.lower() == value.lower():
            return mid
    return value


def _agent_names() -> dict[str, str]:
    try:
        with OpggClient() as client:
            raw = client.call_tool("valorant_list_agents", {})
        parsed = parse_response(raw)
    except (OpggApiError, ParseError):
        return {}
    names: dict[str, str] = {}
    for entry in as_rows(parsed):
        agent_id = entry.get("agent_id")
        name = entry.get("name")
        if agent_id and name:
            names[str(agent_id).lower()] = str(name)
    return names


def _agent_label(character_id: Any, names: dict[str, str]) -> str:
    cid = str(character_id or "")
    if not cid:
        return ""
    return names.get(cid.lower()) or cid[:8]


def _tier_name(tier: Any) -> str:
    if tier == 27:
        return "Radiant"
    if isinstance(tier, int):
        for start, name in _TIER_GROUPS:
            if tier >= start:
                return f"{name} {tier - start + 1}"
        return str(tier)
    return "" if tier is None else str(tier)


def _run(
    tool: str,
    arguments: dict[str, Any],
    *,
    as_json: bool,
    as_raw: bool,
    fields: Optional[list[str]] = None,
    title: str = "Result",
    custom_table: Optional[Callable[[Any], None]] = None,
) -> None:
    run(
        tool,
        arguments,
        as_json=as_json,
        as_raw=as_raw,
        lang=None,
        fields=fields,
        title=title,
        custom_table=custom_table,
    )


def _render_leaderboard_table(parsed: Any, region: str) -> None:
    total = parsed.get("total") if isinstance(parsed, dict) else None
    rows = parsed.get("data") if isinstance(parsed, dict) else parsed
    if not isinstance(rows, list):
        rows = []
    scope = f"top {len(rows)} of {total}" if total else f"top {len(rows)}"
    table = Table(title=f"Leaderboard {region} ({scope})", header_style="bold cyan")
    table.add_column("Rank", justify="right")
    table.add_column("Player", overflow="fold")
    table.add_column("Tier", overflow="fold")
    table.add_column("Rating", justify="right")
    table.add_column("Wins", justify="right")
    table.add_column("Win Rate", justify="right")
    table.add_column("Level", justify="right")
    for row in rows:
        if not isinstance(row, dict):
            continue
        player = "#".join(str(x) for x in (row.get("gameName"), row.get("tagLine")) if x)
        stat = row.get("stat") or {}
        wins, games = stat.get("wins"), stat.get("gameCount")
        win_rate = (
            f"{wins / games * 100:.1f}%"
            if isinstance(wins, (int, float)) and isinstance(games, (int, float)) and games and not isinstance(wins, bool)
            else ""
        )
        table.add_row(
            "" if row.get("leaderboardRank") is None else str(row.get("leaderboardRank")),
            player,
            _tier_name(row.get("competitiveTier")),
            _num(row.get("rankedRating")),
            _num(row.get("numberOfWins")),
            win_rate,
            "" if row.get("level") is None else str(row.get("level")),
        )
    console.print(table)


def _render_agent_stats_table(parsed: Any) -> None:
    names = _agent_names()
    rows = as_rows(parsed)
    table = Table(title=f"Agent Stats ({len(rows)} agents)", header_style="bold cyan")
    table.add_column("Agent", overflow="fold")
    table.add_column("Games", justify="right")
    table.add_column("Win Rate", justify="right")
    table.add_column("KDA", justify="right")
    table.add_column("ACS", justify="right")
    table.add_column("DMG/Round", justify="right")
    table.add_column("FK/FD", justify="right")
    for row in rows:
        kills, deaths, assists = row.get("kills"), row.get("deaths"), row.get("assists")
        if None not in (kills, deaths, assists) and isinstance(deaths, (int, float)) and deaths:
            kda = f"{(kills + assists) / deaths:.2f}"
        else:
            kda = ""
        damage, rounds = row.get("damage"), row.get("rounds")
        dmg_per_round = (
            f"{damage / rounds:.0f}"
            if isinstance(damage, (int, float)) and isinstance(rounds, (int, float)) and rounds
            else ""
        )
        wins, games = row.get("wins"), row.get("gameCount")
        win_rate = (
            f"{wins / games * 100:.1f}%"
            if isinstance(wins, (int, float)) and isinstance(games, (int, float)) and games and not isinstance(wins, bool)
            else ""
        )
        first_kills, first_deaths = row.get("firstKills"), row.get("firstDeaths")
        if None not in (first_kills, first_deaths) and isinstance(first_deaths, (int, float)) and first_deaths:
            fk_fd = f"{first_kills / first_deaths:.2f}"
        else:
            fk_fd = ""
        table.add_row(
            _agent_label(row.get("characterId"), names),
            _num(row.get("gameCount")),
            win_rate,
            kda,
            "" if row.get("acs") is None else str(row.get("acs")),
            dmg_per_round,
            fk_fd,
        )
    console.print(table)


def _render_player_matches_table(parsed: Any, riot_id: str) -> None:
    names = _agent_names()
    rows = as_rows(parsed)
    table = Table(title=f"Matches {riot_id} ({len(rows)} games)", header_style="bold cyan")
    table.add_column("Date", overflow="fold")
    table.add_column("Agent", overflow="fold")
    table.add_column("Queue", overflow="fold")
    table.add_column("Result", overflow="fold")
    table.add_column("K/D/A", justify="right")
    table.add_column("ACS", justify="right")
    table.add_column("Rounds", justify="center")
    for row in rows:
        won = row.get("won")
        if won is True:
            result = "[green]WIN[/green]"
        elif won is False:
            result = "[red]LOSS[/red]"
        else:
            result = "DRAW" if row.get("draw") else ""
        kda = "/".join(str(x) for x in (row.get("kills"), row.get("deaths"), row.get("assists")) if x is not None)
        table.add_row(
            str(row.get("gameStartDateTime") or "")[:16].replace("T", " "),
            _agent_label(row.get("characterId"), names),
            str(row.get("queueId") or ""),
            result,
            kda,
            "" if row.get("acs") is None else str(row.get("acs")),
            str(row.get("roundResults") or ""),
        )
    console.print(table)


@app.command("agent-comp")
def agent_comp(
    map_id: str = typer.Argument(..., help=MAP_ID_HELP),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """Agent compositions and tier stats for a map."""
    resolved = _resolve_map_id(map_id)
    _run(
        "valorant_list_agent_compositions_for_map",
        {"map_id": resolved},
        as_json=as_json,
        as_raw=as_raw,
        title=f"Agent Comp {resolved}",
    )


@app.command("agent-stats")
def agent_stats(
    map_id: Optional[str] = typer.Option(
        None, "--map-id", help="Optional map name (e.g. ascent) or UUID; see 'opgg valorant maps'."
    ),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """Agent pick/win statistics, optionally filtered by map."""
    args: dict[str, Any] = {}
    if map_id and map_id.strip():
        resolved = _resolve_map_id(map_id)
        args["map_id"] = resolved
        title = f"Agent Stats ({resolved})"
    else:
        title = "Agent Stats"
    _run(
        "valorant_list_agent_statistics",
        args,
        as_json=as_json,
        as_raw=as_raw,
        title=title,
        custom_table=_render_agent_stats_table,
    )


@app.command("agents")
def agents(
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """All Valorant agents with roles and abilities."""
    _run(
        "valorant_list_agents",
        {},
        as_json=as_json,
        as_raw=as_raw,
        title="Agents",
    )


@app.command("leaderboard")
def leaderboard(
    region: Region = typer.Argument(..., help="Leaderboard region: ap, br, eu, kr, latam or na."),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    fields: Optional[list[str]] = FIELDS_OPT,
) -> None:
    """Valorant competitive leaderboard for a region."""
    _run(
        "valorant_list_leaderboard",
        {"region": region.value},
        as_json=as_json,
        as_raw=as_raw,
        fields=fields,
        title=f"Leaderboard {region.value.upper()}",
        custom_table=lambda parsed: _render_leaderboard_table(parsed, region.value.upper()),
    )


@app.command("maps")
def maps(
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """All Valorant maps with ids and metadata."""
    _run(
        "valorant_list_maps",
        {},
        as_json=as_json,
        as_raw=as_raw,
        title="Maps",
    )


@app.command("player-matches")
def player_matches(
    riot_id: str = typer.Argument(..., help="Riot ID 'gameName#tagLine', e.g. 'Hide on bush#KR1'."),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """A player's recent Valorant matches."""
    game_name, tag_line = parse_riot_id(riot_id)
    _run(
        "valorant_list_player_matches",
        {"game_name": game_name, "tag_line": tag_line},
        as_json=as_json,
        as_raw=as_raw,
        title=f"Matches {riot_id}",
        custom_table=lambda parsed: _render_player_matches_table(parsed, riot_id),
    )
