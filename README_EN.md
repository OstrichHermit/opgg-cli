# opgg-cli

**Op.gg data from your command line: League of Legends / TFT / Valorant**

Op.gg 数据的命令行工具：英雄联盟 / 云顶之弈 / 无畏契约

English | [简体中文](README.md)

Query OP.GG esports data straight from the terminal — no API key, no browser, no MCP knowledge required.

## Features

- **All 30 commands**: League of Legends (18, incl. fuzzy search), TFT (6), Valorant (6)
- **Beautiful tables**: default output is curated, readable terminal tables
- **Machine-readable**: `--json` prints structured JSON for scripts and AI agents; `--raw` prints the untouched response
- **No API key**: talks directly to the official OP.GG MCP endpoint; all protocol handling is built in
- **Field trimming**: `--fields` trims responses against the server-side closed set to shrink output
- **Localization**: `--lang` for localized data (en_US / zh_CN / ko_KR and more)

## Actively maintained

This project is actively maintained: whenever OP.GG updates its official MCP endpoint or data interfaces, this CLI follows up with synchronized updates to keep every command working. If an upstream change breaks something, please open an issue.

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/OstrichHermit/opgg-cli
cd opgg-cli
pip install .
```

For development, use `pip install -e .` (source changes take effect immediately). PyPI release: coming soon.

### Install as an Agent Skill (optional)

This repo ships with an Agent Skill (`skills/opgg-cli/SKILL.md`). Copy it into your AI agent's skills directory so the agent picks up the tool automatically. Claude Code example:

```bash
cp -r skills/opgg-cli ~/.claude/skills/opgg-cli
```

After installing, the `opgg` command is available:

```bash
opgg --version
opgg --help
```

## Quick start

```bash
# Fuzzy-search a summoner (no #tagLine needed)
opgg lol search "ARE YOU OK"

# Summoner profile: rank, tier, LP, win rate
opgg lol profile "Hide on bush#KR1" kr

# Valorant competitive leaderboard (KR)
opgg valorant leaderboard kr

# Recent match history (KDA, CS, gold, OP score)
opgg lol matches "Hide on bush#KR1" kr --limit 5

# LCK team standings
opgg lol esports-standings lck
```

Sample output (real runs):

```text
$ opgg lol profile "Hide on bush#KR1" kr
            Profile Hide on bush#KR1 (Level 941)
┌────────────┬──────────────┬───────┬─────┬──────┬──────────┐
│ Queue      │ Tier         │    LP │ Win │ Lose │ Win Rate │
├────────────┼──────────────┼───────┼─────┼──────┼──────────┤
│ SOLORANKED │ CHALLENGER-1 │ 2,097 │ 419 │  348 │    54.6% │
│ FLEXRANKED │ UNRANKED     │       │     │      │          │
└────────────┴──────────────┴───────┴─────┴──────┴──────────┘

$ opgg valorant leaderboard kr
                    Leaderboard KR (top 100 of 5000)
┌──────┬─────────────────────────┬─────────┬────────┬──────┬──────────┬───────┐
│ Rank │ Player                  │ Tier    │ Rating │ Wins │ Win Rate │ Level │
├──────┼─────────────────────────┼─────────┼────────┼──────┼──────────┼───────┤
│    1 │ 박박박#민 경            │ Radiant │  1,029 │  122 │    73.8% │   120 │
│    2 │ 바람이 상쾌한 하늘      │ Radiant │  1,010 │  139 │    69.8% │   634 │
│      │ 아래#tuyu               │         │        │      │          │       │
│    3 │ 한태이#taei             │ Radiant │    908 │   72 │    77.4% │   371 │
│    4 │ 맏 디#아랫지방          │ Radiant │    879 │  124 │    61.2% │   561 │
│    5 │ 강의해줄게팔로우해라mux │ Radiant │    840 │   66 │    69.5% │   385 │
│      │ xwx#인스타              │         │        │      │          │       │
└──────┴─────────────────────────┴─────────┴────────┴──────┴──────────┴───────┘
```

## Command reference

### League of Legends (`lol`, 18 commands)

| Command | Description | Key options |
| --- | --- | --- |
| `opgg lol search <query>` | Fuzzy-search summoners without a `#tagLine`; returns Riot ID / level / tier / LP | `--region` (web region code, lowercase e.g. `kr`, `na`, default `kr`). This command uses OP.GG's public web data source; all others use the official MCP endpoint |
| `opgg lol profile <riot_id> <region>` | Summoner profile: rank, tier, LP, win rate and champion pool | `riot_id` as `gameName#tagLine`; region e.g. `KR`, `NA`, `EUW` |
| `opgg lol matches <riot_id> <region>` | Recent match history with per-game stats | `--limit` (server accepts 2-20) |
| `opgg lol game-detail <region> <game_id> <created_at>` | Full match detail: teams, participants, builds and bans | `--focus-riot-id` flags the target participant; `created_at` is an ISO-8601 timestamp |
| `opgg lol champion-analysis <champion> <position>` | Champion stats, builds, runes, combos, counters and synergies | `--game-mode` (ranked/flex/urf/aram/nexus_blitz), `--tier` (e.g. challenger; `all` omits the filter) |
| `opgg lol champion-synergies <champion>` | Synergy recommendations (win rate + role fit) with an ally lane | `--my-position`, `--synergy-position` |
| `opgg lol lane-matchup` | Lane matchup guidance: tips, runes and item timings | `--my-champion`, `--opponent-champion`, `--position` |
| `opgg lol pro-player <player_name> <region>` | Look up a pro player alias and return their Riot ID | `--return-suggestions` includes close matches |
| `opgg lol champion-leaderboard <region> <champion>` | Top master+ players for a champion in a region | — |
| `opgg lol champions` | Every champion's id, key, name and release date | `--lang` |
| `opgg lol champion-details` | Ability, tip, lore and stat metadata for up to 10 champions | `--champions` repeatable (e.g. `--champions ANNIE --champions OLAF`) |
| `opgg lol discounted-skins` | Champion skins currently on sale | `--champion` optional filter |
| `opgg lol items` | Localized items: ids, names, descriptions, build trees, gold costs | `--map` (SUMMONERS_RIFT / HOWLING_ABYSS etc.) |
| `opgg lol lane-meta` | Lane-by-lane champion tiers with win/pick/ban rates and KDA | `--position` (default all) |
| `opgg lol skin-stats <champion>` | A champion's skins ranked by play count or ownership | `--sort-by` (play / ownership) |
| `opgg lol aram-augments` | ARAM augment stats (tier 3+) with localized names | `--champion-id` (e.g. 81 = Ezreal) |
| `opgg lol esports-schedules` | LoL esports schedules (upcoming) or results (completed) | `--mode` (schedule/result), `--league` (lck/lpl/lec/worlds etc.), `--team-name`, `--limit` (result mode, 1-50) |
| `opgg lol esports-standings <short_name>` | Latest team standings for a LoL league | short_name e.g. `lck`, `kespa`, `ewc` |

### Teamfight Tactics (`tft`, 6 commands)

| Command | Description | Key options |
| --- | --- | --- |
| `opgg tft champion-build <champion_id>` | Item build recommendations for a TFT champion | champion_id e.g. `DA_18_Ahri`, `TFT18_Akali` |
| `opgg tft play-style <region> <puuid>` | A player's TFT play style: traits, placements and tendencies | puuid from `opgg lol profile ... --json` (`data.summoner.puuid`) |
| `opgg tft augments` | All TFT augments with localized names, descriptions and tiers | `--lang` |
| `opgg tft item-champions <item_id>` | Champions that can equip a TFT item, with win/pick rates | item_id e.g. `DA_HextechGunblade` |
| `opgg tft item-recipes` | TFT item combination recipes (components to full items) | `--lang` |
| `opgg tft meta-decks` | Current TFT meta decks with traits, units and placement stats | — |

### Valorant (`valorant`, 6 commands)

| Command | Description | Key options |
| --- | --- | --- |
| `opgg valorant agent-comp <map_id>` | Agent compositions and tier stats for a map | map_id accepts a name (e.g. `ascent`) or UUID |
| `opgg valorant agent-stats` | Agent pick/win statistics, optionally filtered by map | `--map-id` optional |
| `opgg valorant agents` | All Valorant agents with roles and abilities | — |
| `opgg valorant leaderboard <region>` | Valorant competitive leaderboard | region: `ap` / `br` / `eu` / `kr` / `latam` / `na` |
| `opgg valorant maps` | All Valorant maps with ids and metadata | — |
| `opgg valorant player-matches <riot_id>` | A player's recent Valorant matches | `riot_id` as `gameName#tagLine` |

## Global options

Every command supports:

| Option | Description |
| --- | --- |
| `--json` | Print the parsed output as JSON. Ideal for scripts and AI agents |
| `--raw` | Print the raw MCP response text |
| `--fields <pattern>` | Trim the response via `desired_output_fields`. Patterns come from a server-defined closed set; commas inside `{...}` belong to the pattern. Repeatable for multiple patterns (e.g. `--fields 'data.summoner.league_stats[].{game_type,win}' --fields region`). Invalid values fail with the full list of legal patterns for that command. Best paired with `--json` (with `--fields` the table falls back to the generic renderer) |
| `--lang <locale>` | Locale code, e.g. `en_US`, `zh_CN`, `ko_KR`. Only commands that support localization honor it (e.g. champions, items, augments); others ignore it |
| `--version` / `-V` | Show version and exit |

## AI agents / MCP

- **The data source is the official OP.GG MCP endpoint** (`https://mcp-api.op.gg/mcp`). This CLI ships the full MCP protocol handling — session initialization, tool calls, SSE response parsing and transport retries — so **you don't need to know MCP or run any MCP server**. It behaves like any ordinary CLI.
- `--json` output is stable, structured JSON that scripts and AI agents can consume directly.
- `--fields` trimming keeps responses small, which matters for agent context windows.
- Every invocation is a standalone process with its own session and no local state, making batch/programmatic use straightforward.

## Data source & disclaimer

- This is an **unofficial** tool. It is not affiliated with, endorsed by, or sponsored by Riot Games or OP.GG.
- All data comes live from OP.GG: the `search` command uses OP.GG's public web data source, everything else goes through its official public MCP endpoint; accuracy and availability are provided by OP.GG.
- Be reasonable: the CLI already throttles between requests — avoid high-frequency batch hammering.
- Released under the [MIT License](LICENSE).

## License

[MIT](LICENSE) © 2026 OstrichHermit
