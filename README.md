# ParseHealer

> *Your parse needs healing? We got you.*

A [Claude Code](https://claude.ai/claude-code) plugin that analyzes World of Warcraft raid performance using Warcraft Logs data — DPS/healer log comparison, spell database management, and automated raid CD scheduling.

## What It Does

- Pulls complete fight data from the [Warcraft Logs API v2](https://www.warcraftlogs.com/api/docs)
- Automatically searches current spec guides (Wowhead, Icy Veins, Method, Maxroll) for rotation priorities
- Compares your performance against a benchmark player or a manually specified log
- Analyzes: cast efficiency, cooldown usage, DoT uptime, opener sequence, buff coverage, stat optimization
- Smart benchmark selection: filters out padded rankings by matching fight duration and external buff conditions
- Manages a static spell database with Wowhead integration for raid cooldown tracking
- Auto-schedules raid damage reduction CDs based on team damage taken analysis with talent validation

## Requirements

- [Claude Code](https://claude.ai/claude-code) (CLI, desktop app, or IDE extension)
- Python 3.11+
- A free [Warcraft Logs API key](https://www.warcraftlogs.com/api/clients)

## Installation

```bash
# In Claude Code, run:
/plugin marketplace add vwvwbg/parse-healer
/plugin install parse-healer@parse-healer
```

Then set up your WCL API credentials:

```
/wcl-setup
```

Claude will walk you through getting and configuring your API key.

## Usage

### `/wcl-compare` — Log Analysis

```
# Compare two specific logs
/wcl-compare https://www.warcraftlogs.com/reports/ABC?fight=5 PlayerA https://www.warcraftlogs.com/reports/XYZ?fight=10 PlayerB

# Analyze one player — auto-find a matching benchmark from rankings
/wcl-compare https://www.warcraftlogs.com/reports/ABC?fight=5 PlayerA
```

### `/wcl-timeline` — STT Timeline Generator

```
# Mode 1: Extract specific player spell casts
/wcl-timeline arw7HCtQWfxpALjz 5 Rathuxmk "Celestial Conduit,Restoral"

# Mode 2: Auto-schedule raid CDs from damage taken
/wcl-timeline dkrhX9tJDmqAzFRB 21
```

### `/wcl-spelldb` — Spell Database Management

```
/wcl-spelldb add 115310 --class Monk --spec Mistweaver --type raid_cd
/wcl-spelldb list --class Monk
/wcl-spelldb refresh
/wcl-spelldb search "tranquility"
```

## How Benchmark Selection Works

When you provide only one log, ParseHealer searches the WCL rankings for the same boss/spec/difficulty and picks a benchmark that:

- Is ranked ~#4-15 (avoids #1-3 which are often artificially optimized)
- Has similar fight duration (not suspiciously short)
- Has matching external buff conditions (if you don't have an Augmentation Evoker, neither should the benchmark)

## Analysis Modules

| Module | What It Checks |
|--------|---------------|
| Overview & Stats | ilvl, secondary stats, enchants, gems, trinkets |
| Damage Breakdown | Ability damage distribution comparison |
| Cast Efficiency | CPM, GCD gaps, per-ability usage rates |
| Opener Analysis | First 35s spell sequence vs guide recommendation |
| Cooldown Utilization | CD timing, alignment, gaps between uses |
| DoT/Debuff Uptime | Boss debuff coverage from damage tick analysis |
| Buff Coverage | Raid buffs, consumables, external buffs, proc uptimes |
| Channel Analysis | Channeled spell clipping (when applicable) |

## Technical Stack

- **Language**: Python 3.11+
- **API**: Warcraft Logs API v2 (GraphQL, OAuth2 client credentials)
- **Data source**: Wowhead tooltip API (for spell DB updates)
- **Shared client**: All skills share `skills/wcl-compare/scripts/wcl_client.py` for WCL auth and queries

## Project Structure

```
parse-healer/
├── .claude-plugin/
│   └── plugin.json                   # Plugin manifest
├── skills/
│   ├── wcl-setup/
│   │   └── SKILL.md                  # API credential setup wizard
│   ├── wcl-compare/
│   │   ├── SKILL.md                  # Main log analysis skill
│   │   ├── scripts/
│   │   │   ├── wcl_client.py         # WCL API v2 client (shared)
│   │   │   ├── wcl_collect.py        # Data collection
│   │   │   └── wcl_find_benchmark.py # Smart benchmark finder
│   │   └── references/
│   │       ├── data-format.md        # JSON data structure docs
│   │       ├── analysis-pitfalls.md  # Known analysis mistakes
│   │       └── healer-modules.md     # Healer-specific modules
│   ├── wcl-spelldb/
│   │   ├── SKILL.md                  # Spell DB management skill
│   │   ├── references/
│   │   │   └── spell_db.json         # Static spell database
│   │   └── scripts/
│   │       └── update_spell_db.py    # Add/remove/refresh/search spells
│   └── wcl-timeline/
│       ├── SKILL.md                  # Timeline & raid CD scheduler skill
│       ├── references/
│       │   └── stt.md               # STT format reference
│       └── scripts/
│           ├── wcl_timeline.py       # Player spell cast timeline
│           └── wcl_raid_cd.py        # Auto raid CD scheduling
├── stt/                              # Generated STT output (gitignored)
├── requirements.txt
└── .env.example
```

## Key Conventions

- **STT output** goes to `stt/` directory (gitignored)
- **spell_db.json** is the single source of truth for raid cooldown info (spell ID, name, class, spec, CD, type)
- **Script execution**: Always use `python3` with full script paths. All scripts handle Windows UTF-8 encoding.
- **WCL URL parsing**: Scripts accept both full URLs (`https://www.warcraftlogs.com/reports/ABC#fight=5`) and bare report codes.
- **Class name normalization**: WCL API returns `"DeathKnight"` / `"DemonHunter"` (no space); spell_db uses `"Death Knight"` / `"Demon Hunter"` (with space). Scripts handle this automatically.

## Credential Storage

ParseHealer looks for WCL credentials in this order:

1. Environment variables (`WCL_CLIENT_ID`, `WCL_CLIENT_SECRET`)
2. `.env` file in `skills/wcl-compare/scripts/`
3. `~/.config/parse-healer/.env`

The `/wcl-setup` skill handles this automatically.

## License

MIT
