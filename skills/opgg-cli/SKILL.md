---
name: opgg-cli
description: OP.GG 战绩查询命令行工具 opgg 的使用方式——查 LOL/TFT/无畏契约召唤师战绩、段位、KDA、英雄胜率出装、对线克制、云顶阵容、电竞赛程赛果，支持召唤师搜索。当用户要查游戏战绩（如"看下韩服 xxx 这个号"）、段位排名、英雄数据、电竞比赛，或提到 OP.GG、opgg 命令、Riot ID、韩服战绩时使用此 skill。
---

# OP.GG 查询（opgg）

面向 AI Agent 的 OP.GG 数据 CLI。数据源为 OP.GG 官方 MCP API + 网页搜索端点，30 个命令与官方 MCP 工具一一对应，无需 API key。

## 安装

```bash
git clone https://github.com/OstrichHermit/opgg-cli
pip install -e ./opgg-cli
```

要求 Python 3.10+，装完即有全局命令 `opgg`。具体参数拿不准就 `opgg lol <命令> --help` 查。

## 命令结构

`opgg <域> <命令> [参数]`，三个域共 30 个命令：

- **lol**（18 个）：`search`（搜召唤师）/ `profile`（段位胜率英雄池）/ `matches`（近期战绩）/ `game-detail`（单局详情）/ `champion-analysis`（英雄数据出装符文）/ `champion-synergies` / `lane-matchup`（对线克制）/ `pro-player`（选手别名反查）/ `champion-leaderboard`（英雄高分榜）/ `champions` / `champion-details` / `discounted-skins` / `items` / `lane-meta`（分路强度榜）/ `skin-stats` / `aram-augments` / `esports-schedules`（电竞赛程赛果）/ `esports-standings`（战队排名）
- **tft**（6 个）：`champion-build` / `play-style` / `augments` / `item-champions` / `item-recipes` / `meta-decks`
- **valorant**（6 个）：`agent-comp` / `agent-stats` / `agents` / `leaderboard` / `maps` / `player-matches`

## 常用示例

```bash
opgg lol search "Faker" --region kr        # 搜召唤师（唯一用 --region 选项的命令）
opgg lol profile "Faker#KR1" kr            # 段位/LP/胜率/英雄池（位置参数：Riot ID 区域）
opgg lol matches "Faker#KR1" kr            # 近期战绩：英雄/位置/KDA/CS/OP Score/胜负
opgg lol game-detail "Faker#KR1" kr --match-id <id>   # 单局双方详情
opgg lol lane-meta --tier emerald_plus     # 各路版本强度
opgg lol esports-schedules --league lck    # LCK 赛程与赛果
```

## 全局参数

- `--json` 机器可读 / `--raw` 原始文本 / `--fields` 精选字段（可重复传，有封闭集校验）/ `--lang zh` 中文文案
- 默认输出 rich 表格，宽表命令已做精选列；空结果输出空表或 0 条，属正常不是报错

## 踩坑与经验

- **搜索匹配规则**：去空格 + 忽略大小写的**精确匹配**，不是前缀模糊——搜"帅哥"能中"帅 哥"，搜"胡凯"搜不到"胡凯莉"。中文 ID 必须输完整名；不知道全名先试拼音全名
- Riot ID 带井号要加引号：`"Name#KR1"`；不确定 tag 时先 `search` 出完整 Riot ID 再查
- 服务器掐连续快速连接：CLI 已内置重试，自己写脚本批量查询时每次间隔 2s
- 本机裸域 `op.gg` 可能 DNS 解析失败，CLI 已固定走 `www.op.gg`，不要手动改回
