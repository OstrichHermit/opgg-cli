[English](README_EN.md) | 简体中文

# opgg-cli

**Op.gg 数据的命令行工具：英雄联盟 / 云顶之弈 / 无畏契约**

在终端里直接查询 OP.GG 的对局数据——无需 API key，无需浏览器，无需了解 MCP 协议。

## 特性

- **29 个命令全覆盖**：英雄联盟 17 个、云顶之弈 6 个、无畏契约 6 个
- **精美表格**：默认输出为精心挑选列的终端表格，一眼可读
- **机器可读**：`--json` 输出结构化 JSON，适合脚本和 AI agent；`--raw` 输出原始响应
- **无需 API key**：直连 OP.GG 官方 MCP 端点，协议对接已内置
- **字段裁剪**：`--fields` 按服务端封闭集裁剪响应，显著减小输出体积
- **多语言**：`--lang` 支持本地化数据（en_US / zh_CN / ko_KR 等）

## 安装

要求 Python 3.10+。

**从源码安装（当前推荐，尚未发布 PyPI）：**

```bash
git clone https://github.com/OstrichHermit/opgg-cli
cd opgg-cli
pip install .
```

**以下方式即将发布（Coming soon）：**

```bash
# 推荐
pipx install opgg-cli

# 或
uv tool install opgg-cli

# 或
pip install opgg-cli
```

安装后即可使用 `opgg` 命令：

```bash
opgg --version
opgg --help
```

## 快速上手

```bash
# 查询召唤师档案：段位、LP、胜率
opgg lol profile "Hide on bush#KR1" kr

# 无畏契约排位排行榜（KR 区）
opgg valorant leaderboard kr

# 最近对局历史（带 KDA、补刀、经济、评分）
opgg lol matches "Hide on bush#KR1" kr --limit 5

# LCK 战队积分榜
opgg lol esports-standings lck
```

示例输出（真实运行结果）：

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

## 命令总览

### 英雄联盟（lol，17 个命令）

| 命令 | 说明 | 关键参数 |
| --- | --- | --- |
| `opgg lol profile <riot_id> <region>` | 召唤师档案：段位、LP、胜率、英雄池 | `riot_id` 格式 `gameName#tagLine`；region 如 `KR`、`NA`、`EUW` |
| `opgg lol matches <riot_id> <region>` | 最近对局历史与逐场数据 | `--limit` 上限（服务端接受 2-20） |
| `opgg lol game-detail <region> <game_id> <created_at>` | 单场对局详情：双方队伍、选手、出装、禁用 | `--focus-riot-id` 标记目标选手；`created_at` 为 ISO-8601 时间戳 |
| `opgg lol champion-analysis <champion> <position>` | 英雄胜率/出场率、出装、符文、连招、克制与配合 | `--game-mode`（ranked/flex/urf/aram/nexus_blitz）、`--tier`（如 challenger，`all` 省略） |
| `opgg lol champion-synergies <champion>` | 与队友位置的配合推荐（胜率 + 角色契合度） | `--my-position`、`--synergy-position` |
| `opgg lol lane-matchup` | 对线指导：技巧、符文与出装时间点 | `--my-champion`、`--opponent-champion`、`--position` |
| `opgg lol pro-player <player_name> <region>` | 按选手别名查 Riot ID | `--return-suggestions` 精确别名未命中时返回近似项 |
| `opgg lol champion-leaderboard <region> <champion>` | 某区域某英雄的大师+ 玩家排行榜 | — |
| `opgg lol champions` | 全英雄 id、key、名称与发布日期 | `--lang` |
| `opgg lol champion-details` | 最多 10 个英雄的技能、贴士、背景与属性 | `--champions`（可重复传，如 `--champions ANNIE --champions OLAF`） |
| `opgg lol discounted-skins` | 正在打折的皮肤 | `--champion` 可选过滤 |
| `opgg lol items` | 本地化装备：id、名称、描述、合成树、金币 | `--map`（SUMMONERS_RIFT / HOWLING_ABYSS 等） |
| `opgg lol lane-meta` | 分路英雄梯度与胜/出场/禁用率、KDA | `--position`（默认 all） |
| `opgg lol skin-stats <champion>` | 英雄皮肤按游玩量或拥有量排名 | `--sort-by`（play / ownership） |
| `opgg lol aram-augments` | 大乱斗强化符文数据（3 级以上，含本地化） | `--champion-id`（如 81 = Ezreal） |
| `opgg lol esports-schedules` | 英雄联盟电竞赛程（未开赛）或赛果（已结束） | `--mode`（schedule/result）、`--league`（lck/lpl/lec/worlds 等）、`--team-name`、`--limit`（result 模式 1-50） |
| `opgg lol esports-standings <short_name>` | 某联赛的最新战队积分榜 | short_name 如 `lck`、`kespa`、`ewc` |

### 云顶之弈（tft，6 个命令）

| 命令 | 说明 | 关键参数 |
| --- | --- | --- |
| `opgg tft champion-build <champion_id>` | 弈子出装推荐 | champion_id 如 `DA_18_Ahri`、`TFT18_Akali` |
| `opgg tft play-style <region> <puuid>` | 玩家对局风格：羁绊、名次与倾向 | puuid 可从 `opgg lol profile ... --json` 的 `data.summoner.puuid` 获取 |
| `opgg tft augments` | 全部强化符文（本地化名称、描述、等级） | `--lang` |
| `opgg tft item-champions <item_id>` | 适合装配某件装备的弈子（含胜率/选取率） | item_id 如 `DA_HextechGunblade` |
| `opgg tft item-recipes` | 装备合成配方（散件 → 成装） | `--lang` |
| `opgg tft meta-decks` | 当前版本主流阵容：羁绊、弈子与名次数据 | — |

### 无畏契约（valorant，6 个命令）

| 命令 | 说明 | 关键参数 |
| --- | --- | --- |
| `opgg valorant agent-comp <map_id>` | 某地图的特工阵容组合与梯度数据 | map_id 支持名称（如 `ascent`）或 UUID |
| `opgg valorant agent-stats` | 特工选取/胜率统计，可按地图过滤 | `--map-id` 可选 |
| `opgg valorant agents` | 全部特工及其技能 | — |
| `opgg valorant leaderboard <region>` | 无畏契约排位排行榜 | region：`ap` / `br` / `eu` / `kr` / `latam` / `na` |
| `opgg valorant maps` | 全部地图及 id 与元数据 | — |
| `opgg valorant player-matches <riot_id>` | 玩家最近的对局记录 | `riot_id` 格式 `gameName#tagLine` |

## 通用选项

所有命令都支持以下选项：

| 选项 | 说明 |
| --- | --- |
| `--json` | 以 JSON 格式输出解析后的结果。适合脚本处理和 AI agent 消费 |
| `--raw` | 输出未经处理的 MCP 原始响应文本 |
| `--fields <pattern>` | 按 `desired_output_fields` 裁剪响应字段。模式取自服务端定义的封闭集，花括号内的逗号属于模式本身；可重复传入多个模式（如 `--fields 'data.summoner.league_stats[].{game_type,win}' --fields region`）。传入非法值会报错并列出该命令的全部合法值。建议配合 `--json` 使用（使用 `--fields` 时表格回退为通用渲染） |
| `--lang <locale>` | 本地化语言代码，如 `en_US`、`zh_CN`、`ko_KR`。仅对支持本地化的命令生效（如 champions、items、augments），其余命令忽略该参数 |
| `--version` / `-V` | 显示版本号并退出 |

## AI agent / MCP 说明

- **数据来源是 OP.GG 官方 MCP 端点**（`https://mcp-api.op.gg/mcp`）。本工具内置了完整的 MCP 协议对接——会话初始化、工具调用、SSE 响应解析与传输层重试——**用户无需了解 MCP，也无需运行任何 MCP server**，像用普通 CLI 一样调用即可。
- `--json` 输出为稳定的结构化 JSON，方便脚本与 AI agent 直接消费。
- `--fields` 字段裁剪可以显著减小响应体积，在 agent 场景下有助于节省上下文窗口。
- 每条命令都是独立进程、独立会话，无本地状态，适合被程序化批量调用。

## 数据来源与免责声明

- 本项目为**非官方**工具，与 Riot Games、OP.GG 均无隶属关系，也未获得任何授权或背书。
- 所有数据实时来自 OP.GG（通过其官方公开 MCP 端点），数据的准确性与可用性由 OP.GG 提供。
- 请合理使用：命令之间存在速率限制保护，请勿高频批量请求。
- 本项目基于 [MIT License](LICENSE) 开源。

## License

[MIT](LICENSE) © 2026 OstrichHermit
