# WCL Collected Data Format

Reference for the JSON structure output by `wcl_collect.py`. Read this when you need to understand the data fields.

## Top-Level Structure

- `fight` — duration, startTime, endTime, encounterID, difficulty
- `player` — name, class, specID, sourceID
- `boss` — name, id
- `stats` — intellect, critSpell, hasteSpell, mastery, versatilityDamageDone, etc.
- `gear` — array of {slot, id, itemLevel, permanentEnchant, gems}

## Tables (Pre-Aggregated)

- `tables.damageDone` — damage table with sourceID filter; `entries` = abilities (each with name, total, hitCount, etc.)
- `tables.damageDoneAll` — damage table without sourceID filter; `entries` = players, each containing an `abilities` sub-array
- `tables.buffs` — buff uptime table; `auras` array
- `tables.enemyDebuffs` — all debuffs on enemies; `auras` array (no source filter)

## Events (Raw)

- `events.casts` — all cast events (type: "cast" or "begincast")
- `events.damage_all` — all damage events
- `events.damage_boss` — damage events on boss target only
- `events.buffs` — buff apply/remove events
- `events.summons` — summon events

## Critical: Timestamps

All event timestamps are **ABSOLUTE** (milliseconds since epoch). Convert to relative seconds:

```
relative_seconds = (event_timestamp - fight.startTime) / 1000
```

## Critical: Cast vs Damage Events

- `type == "cast"` = completed cast
- `type == "begincast"` = cast start (for cast-time spells)
- For **channeled spells**, "cast" events represent GCD-units of channeling, NOT individual ticks
- For channeled spell tick analysis, use `events.damage_boss` or `events.damage_all`, never `events.casts`

## Critical: Game Mechanics

Claude's training data may be outdated for current WoW game mechanics. Always verify with WebSearch for current patch info before making assertions about how abilities work.
