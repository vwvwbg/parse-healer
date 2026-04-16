---
name: wcl-compare
description: Analyze WoW DPS performance by comparing Warcraft Logs data against top-ranked players and spec guides
argument-hint: <report_url> <player> [<report2_url> <player2>]
allowed-tools: Bash(python3 *) Read WebSearch
---

# WCL Compare — Warcraft Logs DPS Analysis

Compare two players' performance on the same boss fight using Warcraft Logs data.

## Usage

```
/wcl-compare <report1_url> <player1> [<report2_url> <player2>]
```

**Mode A — Dual log:** Both reports and players specified manually.
**Mode B — Single log:** Only one report + player given; auto-find a benchmark from WCL rankings.

## Arguments

The user input is in: $ARGUMENTS

## Execution Steps

Follow these steps IN ORDER. Do NOT skip any step.

### Step 0: Version Check

Use WebSearch to determine the current WoW patch and season:
```
Search: "World of Warcraft current patch version <current_year>"
```
Note the patch number (e.g., 12.0.1 Midnight Season 1) for guide searches.

### Step 1: Parse Input & Identify Players

Parse the report URL(s) to extract report code and fight ID.

First, locate the scripts directory:
```bash
SCRIPTS_DIR="$(find ~/.claude/plugins/cache/parse-healer -type d -name scripts -path '*/wcl-compare/*' 2>/dev/null | head -1)"
```

Run `wcl_collect.py` for each player:
```bash
python3 "$SCRIPTS_DIR/wcl_collect.py" "<report_url>" <player_name> -o /tmp/wcl_player1.json
```

From the output JSON, identify:
- Player class and spec (from `player.class` and `player.specID`)
- Boss name and encounter ID
- Fight difficulty

### Step 2: Auto-Find Benchmark (Single Log Mode Only)

If only one report was provided, find a benchmark player:
```bash
python3 "$SCRIPTS_DIR/wcl_find_benchmark.py" /tmp/wcl_player1.json
```

The script outputs the benchmark's report code, fight ID, and player name.
Then collect that player's data:
```bash
python3 "$SCRIPTS_DIR/wcl_collect.py" "<benchmark_report_code>" <fight_id> <benchmark_name> -o /tmp/wcl_player2.json
```

When reporting the benchmark selection, explain WHY this player was chosen (rank, matching conditions, etc.).

### Step 3: Search Class/Spec Guides

Use WebSearch to find the current rotation guide for the identified spec. Search for 2-3 sources:

```
Search 1: "<spec_name> <class_name> rotation guide <patch_version> <expansion_name>"
Search 2: "<spec_name> <class_name> priority list opener <expansion_name> <year>"
```

Target sites: Wowhead, Icy Veins, Method, Maxroll

Extract and note these key points:
1. **Opener sequence** — Exact spell order for the opening burst
2. **Priority list** — Which abilities take priority over others
3. **Must-maintain debuffs/DoTs** — What needs to be kept up and target uptime
4. **Key cooldowns and alignment** — What CDs should be used together
5. **Stat priority** — Which secondary stats are valued
6. **Common mistakes** — Known pitfalls for this spec
7. **Channeled/cast mechanics** — Any spec-specific mechanics (e.g., Mind Flay clipping rules for Shadow Priest, Chaos Bolt usage for Destro Lock)

Summarize these findings BEFORE proceeding to analysis so the user can see the reference framework.

### Step 4: Analyze Data

Load both JSON files and perform the following analysis modules. For each module, read the relevant data from the JSON files using Python.

The JSON structure (from `wcl_collect.py`):
- `fight` — duration, startTime, endTime, encounterID, difficulty
- `player` — name, class, specID, sourceID
- `boss` — name, id
- `stats` — intellect, critSpell, hasteSpell, mastery, versatilityDamageDone, etc.
- `gear` — array of {slot, id, itemLevel, permanentEnchant, gems}
- `tables.damageDone` — damage table with sourceID filter (entries = abilities)
- `tables.damageDoneAll` — damage table without filter (entries = players, each with abilities)
- `tables.buffs` — buff uptime table (auras array)
- `tables.enemyDebuffs` — all debuffs on enemies (auras array, no source filter)
- `events.casts` — all cast events (type: "cast" or "begincast")
- `events.damage_all` — all damage events
- `events.damage_boss` — damage events on boss target only
- `events.buffs` — buff apply/remove events
- `events.summons` — summon events

All event timestamps are ABSOLUTE (milliseconds since epoch). Use `fight.startTime` to convert to relative time.

#### Module A: Overview & Stats
- Average ilvl (exclude Shirt/Tabard), stat comparison
- Enchant/gem completeness check
- Trinket identification
- Total DPS comparison

#### Module B: Damage Breakdown
- Ability damage % comparison (from `tables.damageDone.entries`)
- For the "all players" table, find the specific player entry for total damage/DPS
- Identify % differences in key abilities

#### Module C: Cast Efficiency (CPM)
- Count casts from `events.casts` where `type == "cast"`, EXCLUDE passive abilities (identify by spec — e.g., "Shadowy Apparition", "Tentacle Slam" for Shadow Priest)
- Calculate CPM (casts per minute)
- Per-ability CPM comparison
- GCD gaps > 3 seconds

#### Module D: Opener Analysis
- Extract first 35 seconds of casts
- Compare against the guide's recommended opener
- Identify deviations, wasted GCDs, wrong ordering
- Calculate burst window DPS (first 35s, boss damage only)

#### Module E: Key Cooldown Utilization
- For each major cooldown the guide identifies, analyze:
  - Number of uses vs theoretical maximum
  - Timing of each use
  - Gap analysis between uses
  - Whether CDs are properly aligned with each other

#### Module F: DoT/Debuff Uptime (if applicable)
- Use `events.damage_boss` to calculate DoT uptime on boss
- Group damage ticks by ability, identify gaps between ticks
- A gap > 2.5x median tick interval = downtime
- Report uptime % and list significant downtime windows

#### Module G: Buff Coverage
- From `tables.buffs.auras`, categorize buffs:
  - Raid buffs (Fortitude, Intellect, etc.)
  - Consumables (Flask, Food, Vantus Rune, weapon oil)
  - Self CDs (spec-specific major CDs)
  - External buffs (Ebon Might, Prescience, external PI)
  - Passive/proc effects
- Highlight missing consumables or significant uptime differences

#### Module H: Channeled Spell Analysis (if applicable)
- Only if the spec has channeled damage spells (Mind Flay, Drain Soul, etc.)
- Use `events.damage_boss` (NOT cast events) to count actual damage ticks per channel
- Determine ticks-per-GCD from the data
- Identify premature clips of important channeled abilities

### Step 5: Present Results

Structure your output as follows:

1. **Context** — Patch version, spec guides referenced (with source links), boss and difficulty
2. **Player Profiles** — Stats, ilvl, external conditions (Aug, PI)
3. **Analysis Results** — Each module's findings, with tables and specific timestamps
4. **Root Cause Summary** — Categorize DPS gap into:
   - Uncontrollable factors (team comp, fight duration, gear)
   - Improvable factors (rotation, CD usage, DoT uptime, etc.)
5. **Actionable Recommendations** — Ordered by estimated impact, referencing the guide's best practices

## Important Notes

- All timestamps from the JSON are in ABSOLUTE milliseconds. Convert to relative seconds: `(event_timestamp - fight.startTime) / 1000`
- Cast events: `type == "cast"` = completed cast, `type == "begincast"` = cast start (for cast-time spells). For channeled spells, "cast" events represent GCD-units of channeling, NOT individual ticks.
- For channeled spell tick analysis, ALWAYS use `events.damage_boss` or `events.damage_all`, never `events.casts`.
- The `tables.damageDone` with sourceID has `entries` = abilities (each with name, total, hitCount, etc.). Without sourceID (`tables.damageDoneAll`), `entries` = players, each containing an `abilities` sub-array.
- Do NOT trust Claude's training data for game mechanics. Always verify with WebSearch for current patch info.
- When presenting findings, always compare against the guide's recommendations, not just between the two players.
