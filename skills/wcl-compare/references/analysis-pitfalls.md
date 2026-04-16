# Common Analysis Pitfalls

Read this reference to avoid known mistakes when analyzing WCL data.

## ilvl Calculation

When calculating average ilvl from gear data, **sanity-check the result against the player's primary stat (Intellect/Agility/Strength)**. If two players have similar primary stats but wildly different calculated ilvl, the ilvl calculation is likely wrong.

Common mistakes:
- Including empty slots (id=0) in the average
- Including Shirt/Tabard (which are often ilvl 1)
- Dividing by total slots instead of equipped slots

## Cooldown Times

**Never use training data for ability cooldown times.** WoW patches frequently change cooldown durations, rework abilities into passives, or remove them entirely.

Always get cooldown information from the guide search in Step 3. If the guide doesn't specify a CD time, look it up via WebSearch rather than guessing.

Common mistakes from stale knowledge:
- Abilities that have been reworked into passive effects (no longer actively cast)
- CD times that changed between patches (e.g., 30s → 60s)
- Talents that modify base CD times

When calculating "theoretical maximum uses", use: `ceil(fight_duration / cd_seconds)`

## Power Infusion Detection

PI has a 120s cooldown. When a Priest casts PI, both the Priest AND their target receive the buff. This means:

- A Priest's **expected self-PI count** = `ceil(fight_duration / 120)`
- PI count in the buff table matching this expected count is **normal self-cast**, not external PI
- Only PI count **exceeding** `ceil(fight_duration / 120)` indicates external PI from another Priest

**Do not** compare PI count against other major CD counts — this method is unreliable because different CDs have different cooldown durations.

Formula: `external_pi = max(0, total_pi_count - ceil(fight_duration / 120))`

## Benchmark Fairness

When the benchmark has external PI and the analyzed player does not (or vice versa), this is an **uncontrollable factor** that should be clearly noted but not counted as a player skill issue. Estimate PI's impact at ~3-5% per use window (not cumulative — PI uptime matters, not just count).
