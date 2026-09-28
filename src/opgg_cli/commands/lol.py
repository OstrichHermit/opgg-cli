from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

import typer
from rich.table import Table

from ..output import common_options, render_json, render_raw
from ..search import OpggSearchClient, OpggSearchError, extract_rsc_text, parse_summoners
from ._common import (
    FIELDS_OPT as _FIELDS_OPT,
    as_rows as _as_rows,
    console,
    dig as _dig,
    num as _num,
    parse_riot_id as _parse_riot_id,
    pct as _pct,
    run as _run_impl,
    short_date as _short_date,
)

app = typer.Typer(help="League of Legends commands", no_args_is_help=True)

_JSON_OPT, _RAW_OPT, _LANG_OPT, _ = common_options()

_LANG_TOOLS = frozenset(
    {
        "lol_get_champion_analysis",
        "lol_get_champion_synergies",
        "lol_get_lane_matchup_guide",
        "lol_get_summoner_game_detail",
        "lol_get_summoner_profile",
        "lol_list_aram_augments",
        "lol_list_champion_details",
        "lol_list_champions",
        "lol_list_discounted_skins",
        "lol_list_items",
        "lol_list_lane_meta_champions",
        "lol_list_skin_stats_for_champion",
        "lol_list_summoner_matches",
    }
)

REGION_HELP = "Server region code, e.g. KR, NA, EUW, EUNE, BR, JP, OCE, LAN, LAS, SEA."
CHAMPION_HELP = "Champion name, e.g. ANNIE, MISS_FORTUNE (spaces become underscores)."
SEARCH_RAW_OPT = typer.Option(
    False,
    "--raw",
    help="Print the extracted Next.js RSC payload text from the search page (debug).",
)


class GameMode(str, Enum):
    RANKED = "ranked"
    FLEX = "flex"
    URF = "urf"
    ARAM = "aram"
    NEXUS_BLITZ = "nexus_blitz"


class Position(str, Enum):
    ALL = "all"
    NONE = "none"
    TOP = "top"
    MID = "mid"
    JUNGLE = "jungle"
    ADC = "adc"
    SUPPORT = "support"


class MapId(str, Enum):
    SUMMONERS_RIFT = "SUMMONERS_RIFT"
    HOWLING_ABYSS = "HOWLING_ABYSS"
    NEXUS_BLITZ = "NEXUS_BLITZ"
    TEAMFIGHT_TACTICS = "TEAMFIGHT_TACTICS"
    ARENA_MAP_1 = "ARENA_MAP_1"


class SortBy(str, Enum):
    PLAY = "play"
    OWNERSHIP = "ownership"


class EsportsMode(str, Enum):
    SCHEDULE = "schedule"
    RESULT = "result"


class League(str, Enum):
    LCK = "lck"
    KESPA = "kespa"
    EWC = "ewc"
    LPL = "lpl"
    LEC = "lec"
    LCS = "lcs"
    LJL = "ljl"
    VCS = "vcs"
    CBLOL = "cblol"
    LCL = "lcl"
    LLA = "lla"
    TCL = "tcl"
    PCS = "pcs"
    LCO = "lco"
    LTA_SOUTH = "lta south"
    LTA_NORTH = "lta north"
    LCP = "lcp"
    FIRST_STAND = "first stand"
    FST = "fst"
    AL = "al"
    MSI = "msi"
    WORLDS = "worlds"
    LTA = "lta"


def _normalize_champion(name: str) -> str:
    return name.strip().upper().replace(" ", "_")


def _normalize_region(region: str) -> str:
    return region.strip().upper()


def _run(
    tool: str,
    arguments: dict[str, Any],
    *,
    as_json: bool,
    as_raw: bool,
    lang: Optional[str],
    fields: Optional[list[str]],
    title: str,
    custom_table: Optional[Callable[[Any], None]] = None,
) -> None:
    _run_impl(
        tool,
        arguments,
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title=title,
        custom_table=custom_table,
        lang_tools=_LANG_TOOLS,
    )


def _render_profile_table(parsed: Any) -> None:
    summoner = _dig(parsed, "data", "summoner") or {}
    name = "#".join(str(x) for x in (summoner.get("game_name"), summoner.get("tagline")) if x)
    title = f"Profile {name}"
    if summoner.get("level") is not None:
        title += f" (Level {summoner['level']})"
    table = Table(title=title, header_style="bold cyan")
    table.add_column("Queue", overflow="fold")
    table.add_column("Tier", overflow="fold")
    table.add_column("LP", justify="right")
    table.add_column("Win", justify="right")
    table.add_column("Lose", justify="right")
    table.add_column("Win Rate", justify="right")
    rows = summoner.get("league_stats") or []
    if not isinstance(rows, list):
        rows = []
    for stat in rows:
        if not isinstance(stat, dict):
            continue
        tier_info = stat.get("tier_info") or {}
        tier = tier_info.get("tier")
        division = tier_info.get("division")
        tier_text = "-".join(str(x) for x in (tier, division) if x) or "UNRANKED"
        win, lose = stat.get("win"), stat.get("lose")
        if isinstance(win, int) and isinstance(lose, int) and win + lose > 0:
            win_rate = f"{win / (win + lose) * 100:.1f}%"
        else:
            win_rate = ""
        table.add_row(
            str(stat.get("game_type") or ""),
            tier_text,
            _num(tier_info.get("lp")),
            _num(win),
            _num(lose),
            win_rate,
        )
    console.print(table)


def _render_matches_table(parsed: Any) -> None:
    games = _dig(parsed, "data", "game_history") or []
    if not isinstance(games, list):
        games = []
    table = Table(title=f"Matches ({len(games)} games)", header_style="bold cyan")
    table.add_column("Date", overflow="fold")
    table.add_column("Champion", overflow="fold")
    table.add_column("Position", overflow="fold")
    table.add_column("K/D/A", justify="right")
    table.add_column("KDA", justify="right")
    table.add_column("CS", justify="right")
    table.add_column("Gold", justify="right")
    table.add_column("OP Score", justify="right")
    table.add_column("Result", overflow="fold")
    for game in games:
        if not isinstance(game, dict):
            continue
        participants = game.get("participants") or []
        me = participants[0] if participants and isinstance(participants[0], dict) else {}
        stats = me.get("stats") or {}
        kill, death, assist = stats.get("kill"), stats.get("death"), stats.get("assist")
        if None not in (kill, death, assist):
            kda_text = f"{kill}/{death}/{assist}"
            if death:
                kda_value = f"{(kill + assist) / death:.2f}"
            else:
                kda_value = f"{kill + assist}.00 PERFECT" if (kill + assist) else "-"
        else:
            kda_text, kda_value = "", ""
        cs_values = [v for v in (stats.get("minion_kill"), stats.get("neutral_minion_kill")) if isinstance(v, int)]
        cs = _num(sum(cs_values)) if cs_values else ""
        created = game.get("created_at")
        try:
            date_text = datetime.fromisoformat(created).strftime("%m-%d %H:%M")
        except (TypeError, ValueError):
            date_text = created or ""
        result = stats.get("result")
        if result == "WIN":
            result_text = "[green]WIN[/green]"
        elif result == "LOSE":
            result_text = "[red]LOSS[/red]"
        else:
            result_text = str(result or "")
        table.add_row(
            date_text,
            str(me.get("champion_name") or ""),
            str(me.get("position") or ""),
            kda_text,
            kda_value,
            cs,
            _num(stats.get("gold_earned")),
            str(stats.get("op_score") if stats.get("op_score") is not None else ""),
            result_text,
        )
    console.print(table)


def _render_game_detail_table(parsed: Any) -> None:
    teams = _dig(parsed, "data", "game_detail", "teams") or []
    if not isinstance(teams, list):
        teams = []
    entries = []
    for team in teams:
        if not isinstance(team, dict):
            continue
        participants = team.get("participants") or []
        if not isinstance(participants, list):
            continue
        for participant in participants:
            if isinstance(participant, dict):
                entries.append((team.get("key"), participant))
    table = Table(title=f"Game Detail ({len(entries)} participants)", header_style="bold cyan")
    table.add_column("Team", overflow="fold")
    table.add_column("Player", overflow="fold")
    table.add_column("Champion", overflow="fold")
    table.add_column("Position", overflow="fold")
    table.add_column("K/D/A", justify="right")
    table.add_column("CS", justify="right")
    table.add_column("Gold", justify="right")
    table.add_column("OP Score", justify="right")
    table.add_column("Result", overflow="fold")
    for team_key, participant in entries:
        summoner = participant.get("summoner") or {}
        player = "#".join(str(x) for x in (summoner.get("game_name"), summoner.get("tagline")) if x)
        if participant.get("is_target"):
            player += " ★"
        stats = participant.get("stats") or {}
        kill, death, assist = stats.get("kill"), stats.get("death"), stats.get("assist")
        kda_text = f"{kill}/{death}/{assist}" if None not in (kill, death, assist) else ""
        cs_values = [v for v in (stats.get("minion_kill"), stats.get("neutral_minion_kill")) if isinstance(v, int)]
        cs = _num(sum(cs_values)) if cs_values else ""
        result = stats.get("result")
        if result == "WIN":
            result_text = "[green]WIN[/green]"
        elif result == "LOSE":
            result_text = "[red]LOSS[/red]"
        else:
            result_text = str(result or "")
        op_score = stats.get("op_score")
        table.add_row(
            str(team_key or ""),
            player,
            str(participant.get("champion_name") or ""),
            str(participant.get("position") or ""),
            kda_text,
            cs,
            _num(stats.get("gold_earned")),
            str(op_score) if op_score is not None else "",
            result_text,
        )
    console.print(table)


def _render_lane_meta_table(parsed: Any) -> None:
    positions = _dig(parsed, "data", "positions") or {}
    if not isinstance(positions, dict):
        positions = {}
    rows: list[tuple] = []
    for position, entries in positions.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rows.append(
                (
                    str(position).upper(),
                    entry.get("rank"),
                    entry.get("champion"),
                    entry.get("tier"),
                    _pct(entry.get("win_rate")),
                    _pct(entry.get("pick_rate")),
                    _pct(entry.get("ban_rate")),
                    entry.get("kda"),
                )
            )
    rows.sort(key=lambda r: (r[1] is None, r[1] if isinstance(r[1], int) else 0))
    table = Table(title=f"Lane Meta ({len(rows)} champions)", header_style="bold cyan")
    table.add_column("Position", overflow="fold")
    table.add_column("Rank", justify="right")
    table.add_column("Champion", overflow="fold")
    table.add_column("Tier", justify="right")
    table.add_column("Win Rate", justify="right")
    table.add_column("Pick Rate", justify="right")
    table.add_column("Ban Rate", justify="right")
    table.add_column("KDA", justify="right")
    for row in rows:
        table.add_row(*[("" if v is None else str(v)) for v in row])
    console.print(table)


def _render_synergies_table(parsed: Any) -> None:
    rows = _dig(parsed, "data", "synergies") or []
    if not isinstance(rows, list):
        rows = []
    table = Table(title=f"Synergies ({len(rows)} entries)", header_style="bold cyan")
    table.add_column("Ally", overflow="fold")
    table.add_column("Ally Position", overflow="fold")
    table.add_column("Win Rate", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Score Rank", justify="right")
    table.add_column("Tier", justify="right")
    for row in rows:
        if not isinstance(row, dict):
            continue
        tier_data = row.get("synergy_tier_data") or {}
        score = row.get("score")
        table.add_row(
            str(row.get("synergy_champion_name") or ""),
            str(row.get("synergy_position") or ""),
            _pct(row.get("win_rate")),
            f"{score:.2f}" if isinstance(score, (int, float)) else "",
            _num(row.get("score_rank")),
            _num(tier_data.get("tier")),
        )
    console.print(table)


def _render_champion_details_table(parsed: Any) -> None:
    rows = _dig(parsed, "data", "champions") or []
    if not isinstance(rows, list):
        rows = []
    table = Table(title=f"Champion Details ({len(rows)} champions)", header_style="bold cyan")
    table.add_column("Champion", overflow="fold")
    table.add_column("Title", overflow="fold")
    table.add_column("Tags", overflow="fold")
    table.add_column("Released", overflow="fold")
    table.add_column("Attack", justify="right")
    table.add_column("Defense", justify="right")
    table.add_column("Magic", justify="right")
    table.add_column("Difficulty", justify="right")
    for row in rows:
        if not isinstance(row, dict):
            continue
        info = row.get("info") or {}
        tags = row.get("tags") or []
        table.add_row(
            str(row.get("name") or ""),
            str(row.get("title") or ""),
            "/".join(str(t) for t in tags),
            _short_date(row.get("release_date"), "%Y-%m-%d"),
            _num(info.get("attack")),
            _num(info.get("defense")),
            _num(info.get("magic")),
            _num(info.get("difficulty")),
        )
    console.print(table)


def _render_discounted_skins_table(parsed: Any) -> None:
    rows = parsed.get("data") if isinstance(parsed, dict) else parsed
    if not isinstance(rows, list):
        rows = []
    table = Table(title=f"Discounted Skins ({len(rows)} skins)", header_style="bold cyan")
    table.add_column("Champion", overflow="fold")
    table.add_column("Skin", overflow="fold")
    table.add_column("Discount", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Start", overflow="fold")
    table.add_column("End", overflow="fold")
    for row in rows:
        if not isinstance(row, dict):
            continue
        cost = row.get("cost")
        currency = row.get("currency")
        cost_text = " ".join(str(x) for x in (cost, currency) if x)
        table.add_row(
            str(row.get("champion_name") or ""),
            str(row.get("skin_name") or ""),
            _pct(row.get("discount_rate"), 0),
            cost_text,
            _short_date(row.get("started_at"), "%m-%d"),
            _short_date(row.get("ended_at"), "%m-%d"),
        )
    console.print(table)


def _render_champion_leaderboard_table(parsed: Any) -> None:
    rows = parsed.get("leaderboard") if isinstance(parsed, dict) else None
    if not isinstance(rows, list):
        rows = []
    table = Table(title=f"Champion Leaderboard ({len(rows)} players)", header_style="bold cyan")
    table.add_column("Rank", justify="right")
    table.add_column("Player", overflow="fold")
    table.add_column("Tier", overflow="fold")
    table.add_column("LP", justify="right")
    table.add_column("Play", justify="right")
    table.add_column("Win Rate", justify="right")
    table.add_column("KDA", justify="right")
    for row in rows:
        if not isinstance(row, dict):
            continue
        summoner = row.get("summoner") or {}
        player = "#".join(str(x) for x in (summoner.get("game_name"), summoner.get("tagline")) if x)
        league_stats = summoner.get("league_stats") or []
        stat = next((s for s in league_stats if isinstance(s, dict) and s.get("game_type") == "SOLORANKED"), None)
        if stat is None and league_stats and isinstance(league_stats[0], dict):
            stat = league_stats[0]
        tier_info = (stat or {}).get("tier_info") or {}
        tier_text = "-".join(str(x) for x in (tier_info.get("tier"), tier_info.get("division")) if x)
        mcs = row.get("most_champion_stat") or {}
        play, win = mcs.get("play"), mcs.get("win")
        win_rate = f"{win / play * 100:.1f}%" if isinstance(win, (int, float)) and isinstance(play, (int, float)) and play else ""
        kill, death_v, assist = mcs.get("kill"), mcs.get("death"), mcs.get("assist")
        if None not in (kill, death_v, assist) and death_v:
            kda_text = f"{(kill + assist) / death_v:.2f}"
        elif None not in (kill, death_v, assist):
            kda_text = f"{kill + assist}.00"
        else:
            kda_text = ""
        table.add_row(
            _num(row.get("rank")),
            player,
            tier_text,
            _num(tier_info.get("lp")),
            _num(play),
            win_rate,
            kda_text,
        )
    console.print(table)


def _render_schedules_table(parsed: Any) -> None:
    rows = _as_rows(parsed)
    table = Table(title=f"Esports ({len(rows)} matches)", header_style="bold cyan")
    table.add_column("Date", overflow="fold")
    table.add_column("League", overflow="fold")
    table.add_column("Match", overflow="fold")
    table.add_column("Home", overflow="fold")
    table.add_column("Score", justify="center")
    table.add_column("Away", overflow="fold")
    table.add_column("Status", overflow="fold")
    for row in rows:
        home = row.get("homeTeam") or {}
        away = row.get("awayTeam") or {}
        score = ":".join(str(x) for x in (row.get("homeScore"), row.get("awayScore")) if x is not None)
        table.add_row(
            _short_date(row.get("scheduledAt")),
            str(row.get("league") or ""),
            str(row.get("name") or ""),
            str(home.get("name") or ""),
            score,
            str(away.get("name") or ""),
            str(row.get("status") or ""),
        )
    console.print(table)


def _render_standings_table(parsed: Any) -> None:
    rows = _as_rows(parsed)
    table = Table(title=f"Standings ({len(rows)} teams)", header_style="bold cyan")
    table.add_column("Pos", justify="right")
    table.add_column("Team", overflow="fold")
    table.add_column("Tag", overflow="fold")
    table.add_column("W", justify="right")
    table.add_column("L", justify="right")
    table.add_column("Sets", justify="center")
    table.add_column("Points", justify="right")
    for row in rows:
        team = row.get("team") or {}
        sets = "-".join(str(x) for x in (row.get("setWin"), row.get("setLose")) if x is not None)
        table.add_row(
            _num(row.get("position")),
            str(team.get("name") or ""),
            str(team.get("acronym") or ""),
            _num(row.get("win")),
            _num(row.get("lose")),
            sets,
            _num(row.get("point")),
        )
    console.print(table)


def _render_search_table(results: list[dict]) -> None:
    table = Table(title=f"Search ({len(results)} summoners)", header_style="bold cyan")
    table.add_column("Riot ID", overflow="fold")
    table.add_column("Level", justify="right")
    table.add_column("Tier", overflow="fold")
    table.add_column("LP", justify="right")
    for row in results:
        if not isinstance(row, dict):
            continue
        tier_info = row.get("solo_tier_info") or {}
        if not isinstance(tier_info, dict):
            tier_info = {}
        riot_id = "#".join(str(x) for x in (row.get("game_name"), row.get("tagline")) if x)
        tier = tier_info.get("tier")
        table.add_row(
            riot_id,
            _num(row.get("level")),
            str(tier) if tier else "UNRANKED",
            _num(tier_info.get("lp")),
        )
    console.print(table)


@app.command("search")
def search(
    query: str = typer.Argument(..., help="Fuzzy summoner name, no '#tagLine' required, e.g. 'ARE YOU OK' or 'Faker'."),
    region: str = typer.Option(
        "kr", "--region", help="Website region code in lowercase, e.g. kr, na, euw, eune, br, jp."
    ),
    as_json: bool = _JSON_OPT,
    as_raw: bool = SEARCH_RAW_OPT,
    lang: str = _LANG_OPT,
) -> None:
    """Fuzzy-search summoners via the OP.GG website data source (not the official MCP API).

    The query does not need a '#tagLine'. region is the website's lowercase region code
    (kr, na, euw, eune, br, jp, ...). PUUIDs are included in --json output.
    """
    region_code = region.strip().lower() or "kr"
    try:
        with OpggSearchClient() as client:
            html = client.fetch(query, region_code)
        rsc_text = extract_rsc_text(html)
        results = parse_summoners(rsc_text)
    except OpggSearchError as exc:
        error(str(exc))
        raise typer.Exit(code=1)
    if as_raw:
        render_raw(rsc_text)
        return
    if not results:
        console.print(f"0 results for '{query}'")
        return
    if as_json:
        render_json(results)
        return
    _render_search_table(results)


@app.command("profile")
def profile(
    riot_id: str = typer.Argument(..., help="Riot ID 'gameName#tagLine', e.g. 'Hide on bush#KR1'."),
    region: str = typer.Argument(..., help=REGION_HELP),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """Summoner profile: rank, tier, LP, win rate and champion pool."""
    game_name, tag_line = _parse_riot_id(riot_id)
    _run(
        "lol_get_summoner_profile",
        {"game_name": game_name, "tag_line": tag_line, "region": _normalize_region(region)},
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title=f"Profile {riot_id}",
        custom_table=_render_profile_table,
    )


@app.command("matches")
def matches(
    riot_id: str = typer.Argument(..., help="Riot ID 'gameName#tagLine', e.g. 'Hide on bush#KR1'."),
    region: str = typer.Argument(..., help=REGION_HELP),
    limit: Optional[int] = typer.Option(None, "--limit", help="Max matches to return (server accepts 2-20)."),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """Recent match history with per-game stats for the summoner."""
    game_name, tag_line = _parse_riot_id(riot_id)
    args: dict[str, Any] = {
        "game_name": game_name,
        "tag_line": tag_line,
        "region": _normalize_region(region),
    }
    if limit is not None:
        args["limit"] = limit
    _run(
        "lol_list_summoner_matches",
        args,
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title=f"Matches {riot_id}",
        custom_table=_render_matches_table,
    )


@app.command("game-detail")
def game_detail(
    region: str = typer.Argument(..., help=REGION_HELP),
    game_id: str = typer.Argument(..., help="Match id (from the matches command)."),
    created_at: str = typer.Argument(..., help="Match creation timestamp (ISO-8601), e.g. 2026-09-28T19:00:44+09:00."),
    focus_riot_id: Optional[str] = typer.Option(
        None, "--focus-riot-id", help="Riot ID 'gameName#tagLine' of the participant to flag with is_target=true."
    ),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """Full match detail: teams, participants, builds and bans."""
    args: dict[str, Any] = {
        "region": _normalize_region(region),
        "game_id": game_id,
        "created_at": created_at,
    }
    if focus_riot_id:
        game_name, tag_line = _parse_riot_id(focus_riot_id)
        args["focus_riot_id"] = focus_riot_id
        args["game_name"] = game_name
        args["tag_line"] = tag_line
    _run(
        "lol_get_summoner_game_detail",
        args,
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title=f"Game {game_id}",
        custom_table=_render_game_detail_table,
    )


@app.command("champion-analysis")
def champion_analysis(
    champion: str = typer.Argument(..., help=CHAMPION_HELP),
    position: Position = typer.Argument(..., help="Lane position, e.g. top, mid, jungle, adc, support."),
    game_mode: GameMode = typer.Option(GameMode.RANKED, "--game-mode", help="Game mode."),
    tier: Optional[str] = typer.Option(
        None, "--tier", help="Rank tier filter, e.g. challenger, grandmaster. 'all' omits the filter."
    ),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """Champion stats, builds, runes, combos, counters and synergies."""
    args: dict[str, Any] = {
        "champion": _normalize_champion(champion),
        "position": position.value,
        "game_mode": game_mode.value,
    }
    if tier and tier.strip().lower() != "all":
        args["tier"] = tier
    _run(
        "lol_get_champion_analysis",
        args,
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title=f"Champion Analysis {_normalize_champion(champion)} ({position.value})",
    )


@app.command("champion-synergies")
def champion_synergies(
    champion: str = typer.Argument(..., help=CHAMPION_HELP),
    my_position: Position = typer.Option(..., "--my-position", help="Your position, e.g. mid, adc."),
    synergy_position: Position = typer.Option(
        ..., "--synergy-position", help="Teammate position to get synergy recommendations for."
    ),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """Synergy recommendations (win rate + role fit) with an ally lane."""
    _run(
        "lol_get_champion_synergies",
        {
            "champion": _normalize_champion(champion),
            "my_position": my_position.value,
            "synergy_position": synergy_position.value,
        },
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title=f"Synergies {_normalize_champion(champion)} ({my_position.value} + {synergy_position.value})",
        custom_table=_render_synergies_table,
    )


@app.command("lane-matchup")
def lane_matchup(
    my_champion: str = typer.Option(..., "--my-champion", help=CHAMPION_HELP),
    opponent_champion: str = typer.Option(..., "--opponent-champion", help=CHAMPION_HELP),
    position: Position = typer.Option(..., "--position", help="Lane position, e.g. top, mid."),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
) -> None:
    """Lane matchup guidance: tips, runes and item timings."""
    _run(
        "lol_get_lane_matchup_guide",
        {
            "my_champion": _normalize_champion(my_champion),
            "opponent_champion": _normalize_champion(opponent_champion),
            "position": position.value,
        },
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=None,
        title=f"Matchup {_normalize_champion(my_champion)} vs {_normalize_champion(opponent_champion)}",
    )


@app.command("pro-player")
def pro_player(
    player_name: str = typer.Argument(..., help="Nickname, alias or real name fragment, e.g. Faker, Ruler, Deft."),
    region: str = typer.Argument(..., help="League region to constrain the lookup, e.g. KR, BR, EUNE."),
    return_suggestions: bool = typer.Option(
        False, "--return-suggestions", help="Include close matches when the exact alias is not found."
    ),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """Look up a pro player alias and return their Riot ID."""
    args: dict[str, Any] = {
        "player_name": player_name,
        "region": _normalize_region(region),
    }
    if return_suggestions:
        args["return_suggestions"] = True
    _run(
        "lol_get_pro_player_riot_id",
        args,
        as_json=as_json,
        as_raw=as_raw,
        lang=None,
        fields=None,
        title=f"Pro Player {player_name}",
    )


@app.command("champion-leaderboard")
def champion_leaderboard(
    region: str = typer.Argument(..., help=REGION_HELP),
    champion: str = typer.Argument(..., help=CHAMPION_HELP),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """Top master+ players for a champion in a region."""
    _run(
        "lol_list_champion_leaderboard",
        {"region": _normalize_region(region), "champion": _normalize_champion(champion)},
        as_json=as_json,
        as_raw=as_raw,
        lang=None,
        fields=fields,
        title=f"Leaderboard {_normalize_champion(champion)} ({_normalize_region(region)})",
        custom_table=_render_champion_leaderboard_table,
    )


@app.command("champions")
def champions(
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """Every champion's id, key, name and release date."""
    _run(
        "lol_list_champions",
        {},
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title="Champions",
    )


@app.command("champion-details")
def champion_details(
    champions: list[str] = typer.Option(
        [], "--champions", help="Champion names, repeatable (up to 10), e.g. --champions ANNIE --champions OLAF."
    ),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """Ability, tip, lore and stat metadata for up to 10 champions."""
    args: dict[str, Any] = {}
    if champions:
        args["champions"] = [_normalize_champion(c) for c in champions]
    _run(
        "lol_list_champion_details",
        args,
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title="Champion Details",
        custom_table=_render_champion_details_table,
    )


@app.command("discounted-skins")
def discounted_skins(
    champion: Optional[str] = typer.Option(None, "--champion", help=CHAMPION_HELP),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """Champion skins currently on sale."""
    args: dict[str, Any] = {}
    if champion:
        args["champion"] = _normalize_champion(champion)
    _run(
        "lol_list_discounted_skins",
        args,
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title="Discounted Skins",
        custom_table=_render_discounted_skins_table,
    )


@app.command("items")
def items(
    map_id: Optional[MapId] = typer.Option(None, "--map", help="Map identifier (default SUMMONERS_RIFT)."),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
) -> None:
    """Localized items: ids, names, descriptions, build trees, gold costs."""
    args: dict[str, Any] = {}
    if map_id is not None:
        args["map"] = map_id.value
    _run(
        "lol_list_items",
        args,
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=None,
        title=f"Items ({map_id.value if map_id else 'SUMMONERS_RIFT'})",
    )


@app.command("lane-meta")
def lane_meta(
    position: Position = typer.Option(Position.ALL, "--position", help="Lane position filter (default all)."),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """Lane-by-lane champion tiers with win/pick/ban rates and KDA."""
    _run(
        "lol_list_lane_meta_champions",
        {"position": position.value},
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title=f"Lane Meta ({position.value})",
        custom_table=_render_lane_meta_table,
    )


@app.command("skin-stats")
def skin_stats(
    champion: str = typer.Argument(..., help=CHAMPION_HELP),
    sort_by: SortBy = typer.Option(SortBy.PLAY, "--sort-by", help="Ranking metric: play (default) or ownership."),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """A champion's skins ranked by play count or ownership."""
    _run(
        "lol_list_skin_stats_for_champion",
        {"champion": _normalize_champion(champion), "sort_by": sort_by.value},
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title=f"Skin Stats {_normalize_champion(champion)} ({sort_by.value})",
    )


@app.command("aram-augments")
def aram_augments(
    champion_id: Optional[int] = typer.Option(
        None, "--champion-id", help="Champion id, e.g. 103 for Ahri, 81 for Ezreal."
    ),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
    lang: str = _LANG_OPT,
    fields: Optional[list[str]] = _FIELDS_OPT,
) -> None:
    """ARAM augment stats (tier 3+) with localized names and descriptions."""
    args: dict[str, Any] = {}
    if champion_id is not None:
        args["champion_id"] = champion_id
    _run(
        "lol_list_aram_augments",
        args,
        as_json=as_json,
        as_raw=as_raw,
        lang=lang,
        fields=fields,
        title="ARAM Augments",
    )


@app.command("esports-schedules")
def esports_schedules(
    mode: EsportsMode = typer.Option(EsportsMode.SCHEDULE, "--mode", help="schedule (upcoming) or result (completed)."),
    league: Optional[League] = typer.Option(
        None, "--league", help="League short name, e.g. lck, lpl, lec, worlds, msi."
    ),
    team_name: Optional[str] = typer.Option(
        None, "--team-name", help="Team name or acronym filter, e.g. 'T1', 'Gen.G', 'HLE'."
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", min=1, max=50, help="Max completed matches in result mode (1-50, default 50)."
    ),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """LoL esports schedules (upcoming) or results (completed)."""
    args: dict[str, Any] = {"mode": mode.value}
    if league is not None:
        args["league"] = league.value
    if team_name:
        args["team_name"] = team_name
    if limit is not None and mode == EsportsMode.RESULT:
        args["limit"] = limit
    _run(
        "lol_esports_list_schedules",
        args,
        as_json=as_json,
        as_raw=as_raw,
        lang=None,
        fields=None,
        title=f"Esports {mode.value.capitalize()}" + (f" ({league.value.upper()})" if league else ""),
        custom_table=_render_schedules_table,
    )


@app.command("esports-standings")
def esports_standings(
    short_name: str = typer.Argument(..., help="League short name, e.g. lck, kespa, ewc."),
    as_json: bool = _JSON_OPT,
    as_raw: bool = _RAW_OPT,
) -> None:
    """Latest team standings for a LoL league."""
    _run(
        "lol_esports_list_team_standings",
        {"short_name": short_name},
        as_json=as_json,
        as_raw=as_raw,
        lang=None,
        fields=None,
        title=f"Standings {short_name.upper()}",
        custom_table=_render_standings_table,
    )
