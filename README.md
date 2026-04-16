# ParseHealer

> *Your parse needs healing? We got you.*

A [Claude Code](https://claude.ai/claude-code) skill that analyzes World of Warcraft DPS performance by comparing Warcraft Logs data against top-ranked players and current spec guides.

## What It Does

- Pulls complete fight data from the [Warcraft Logs API v2](https://www.warcraftlogs.com/api/docs)
- Automatically searches current spec guides (Wowhead, Icy Veins, Method, Maxroll) for rotation priorities
- Compares your performance against a benchmark player or a manually specified log
- Analyzes: cast efficiency, cooldown usage, DoT uptime, opener sequence, buff coverage, stat optimization
- Smart benchmark selection: filters out padded rankings by matching fight duration and external buff conditions

## Requirements

- [Claude Code](https://claude.ai/claude-code) (the CLI tool by Anthropic)
- Python 3.11+
- A free [Warcraft Logs API key](https://www.warcraftlogs.com/api/clients)

## Setup

```bash
git clone <this-repo> parse-healer
cd parse-healer
pip install -r requirements.txt

# Set your WCL API credentials
cp .env.example .env
# Edit .env with your client ID and secret

# Or export directly:
export WCL_CLIENT_ID=your_id
export WCL_CLIENT_SECRET=your_secret
```

## Usage

Launch Claude Code from the project directory:

```bash
cd parse-healer
claude
```

Then use the skill:

```
# Compare two specific logs
/wcl-compare https://www.warcraftlogs.com/reports/ABC?fight=5 PlayerA https://www.warcraftlogs.com/reports/XYZ?fight=10 PlayerB

# Analyze one player — auto-find a matching benchmark from rankings
/wcl-compare https://www.warcraftlogs.com/reports/ABC?fight=5 PlayerA
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

## Project Structure

```
parse-healer/
├── .claude/skills/wcl-compare/
│   └── SKILL.md              # Claude Code skill definition
├── wcl_client.py             # WCL API v2 client
├── wcl_collect.py            # Data collection (outputs JSON)
├── wcl_find_benchmark.py     # Smart benchmark finder
├── requirements.txt
└── .env.example
```

## License

MIT
