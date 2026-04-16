---
name: wcl-compare
description: >
  Analyze World of Warcraft DPS or Healer performance using Warcraft Logs data.
  Compares a player's log against a benchmark (another log or auto-selected
  from WCL rankings) across 8 dimensions including damage/healing breakdown,
  cast efficiency, cooldown usage, buff coverage, and more.
  Automatically detects whether the player is DPS or Healer and adjusts analysis
  accordingly (HPS, overhealing, mana efficiency for healers).
  Use this skill whenever the user wants to analyze a WCL log, compare two
  players' DPS or HPS, review raid performance, diagnose DPS/healing issues,
  or understand why their parse is low. Also use when the user pastes a
  warcraftlogs.com URL.
argument-hint: <report_url> <player> [<report2_url> <player2>]
allowed-tools: Bash(python3 *) Read WebSearch
---

# WCL Compare — Warcraft Logs DPS Analysis

Compare a player's boss fight performance against a benchmark using Warcraft Logs data, current spec guides, and 8 analysis modules.

## Modes

```
/wcl-compare <report_url> <player> [<report2_url> <player2>]
```

- **Dual log** — Both reports and players specified. Compares directly.
- **Single log** — One report + player. Auto-finds a matching benchmark from WCL rankings (skips top 3 to avoid padded logs, matches fight duration and external buff conditions).

## Arguments

The user input is in: $ARGUMENTS

## Scripts

All Python scripts are in the `scripts/` subdirectory of this skill:

```bash
SCRIPTS_DIR="${CLAUDE_SKILL_DIR}/scripts"
```

Use `$SCRIPTS_DIR/wcl_collect.py`, `$SCRIPTS_DIR/wcl_find_benchmark.py`, and `$SCRIPTS_DIR/wcl_client.py`.

## Execution Steps

Follow these steps in order.

### Step 0: Version Check

Use WebSearch to find the current WoW patch and season:
```
Search: "World of Warcraft current patch version <current_year>"
```

### Step 1: Collect Player Data

Parse the report URL(s) to extract report code and fight ID, then collect data:

```bash
python3 "$SCRIPTS_DIR/wcl_collect.py" "<report_url>" <player_name> -o /tmp/wcl_player1.json
```

From the output, identify the player's class, spec, boss name, difficulty, and **role** (`player.role` = "healer" or "dps"). The role is auto-detected from specID.

### Step 2: Auto-Find Benchmark (Single Log Only)

If only one report was provided:

```bash
python3 "$SCRIPTS_DIR/wcl_find_benchmark.py" /tmp/wcl_player1.json
```

The script outputs the benchmark's report code, fight ID, and player name. Collect that player's data:

```bash
python3 "$SCRIPTS_DIR/wcl_collect.py" "<benchmark_report_code>" <fight_id> <benchmark_name> -o /tmp/wcl_player2.json
```

Explain why this benchmark was chosen (rank, matching conditions, etc.).

### Step 3: Search Spec Guides

Use WebSearch to find 2-3 guides for the identified spec from Wowhead, Icy Veins, Method, or Maxroll.

**For DPS specs**, extract: opener sequence, priority list, DoT/debuff requirements, cooldown alignment, stat priority, common mistakes, channeled spell mechanics.

**For Healer specs**, extract: healing priority/triage order, cooldown timing (which CDs for which boss mechanics), mana management tips, expected DPS filler rotation, stat priority, common mistakes.

### Step 4: Analyze Data

Load both JSON files and run the analysis modules. Read `references/data-format.md` for the JSON structure details and `references/analysis-pitfalls.md` for known mistakes to avoid (ilvl calculation, CD times, PI detection).

**If the player is a healer** (`player.role == "healer"`), read `references/healer-modules.md` for healer-specific module definitions. The key differences: healing breakdown replaces damage breakdown, cooldown timing replaces opener analysis, mana efficiency replaces DoT uptime, and overhealing analysis is added.

**DPS analysis modules** (use these when `player.role == "dps"`):

#### Module A: Overview & Stats
- Average ilvl (exclude Shirt/Tabard), stat comparison, enchant/gem check, trinkets, total DPS

#### Module B: Damage Breakdown
- Ability damage % comparison from `tables.damageDone.entries`
- Identify % differences in key abilities

#### Module C: Cast Efficiency (CPM)
- Count casts from `events.casts` where `type == "cast"`, exclude passive abilities (spec-dependent)
- CPM, per-ability CPM comparison, GCD gaps > 3 seconds

#### Module D: Opener Analysis
- First 35 seconds of casts vs guide's recommended opener
- Burst window DPS (first 35s, boss damage only)

#### Module E: Cooldown Utilization
- Uses vs theoretical maximum, timing, gap analysis, alignment

#### Module F: DoT/Debuff Uptime (if applicable)
- Calculate from `events.damage_boss` tick timestamps
- Gap > 2.5x median tick interval = downtime

#### Module G: Buff Coverage (Critical)

Buff uptime differences are often the single largest explainable factor in performance gaps. Treat this module with high priority.

From `tables.buffs.auras`, categorize and compare uptime:

**Tier 1 — Must-maintain (uptime gaps directly reduce throughput):**
- Consumables (Flask, Food, Augment Rune, weapon enhancement) — should be ~100%
- Spec-specific must-maintain buffs identified from the guide search in Step 3

**Tier 2 — External buffs (affect comparison fairness):**
- Augmentation Evoker buffs, external Power Infusion, and other externals
- If one player has these and the other doesn't, note the fairness impact

**Tier 3 — Raid buffs and misc:**
- Standard raid buffs, passive/proc effects

For every Tier 1 buff with >5% uptime difference between the two players, flag it explicitly and estimate the throughput impact. Missing consumables should be called out prominently — they indicate preparation issues.

#### Module H: Channeled Spell Analysis (if applicable)
- Use `events.damage_boss` (NOT cast events) to count actual damage ticks
- Identify premature clips of important channeled abilities

### Step 5: Present Results

1. **Context** — Patch, guides referenced (with links), boss and difficulty
2. **Player Profiles** — Stats, ilvl, external conditions (Aug, PI)
3. **Analysis Results** — Each module's findings with tables and timestamps
4. **Root Cause Summary** — Uncontrollable factors (gear, comp) vs improvable factors (rotation, CDs, DoTs)
5. **Actionable Recommendations** — Ordered by estimated impact, referencing guide best practices

Always compare against the guide's recommendations, not just between the two players.
