# Healer Analysis Modules

When the collected data shows `player.role == "healer"`, use these modules instead of the DPS-specific ones. Modules A (Overview & Stats) and G (Buff Coverage) remain the same for both roles.

## Module B (Healer): Healing Breakdown

Replace damage breakdown with healing analysis:
- Ability healing % comparison from `tables.healingDone.entries`
- Overhealing % per ability — high overhealing on key spells suggests poor timing or snipe issues
- Effective healing (total - overheal) comparison
- Total HPS comparison (from `tables.healingDoneAll`)

## Module C (Healer): Cast Efficiency (CPM)

Same approach as DPS, but the passive ability exclusion list differs by healer spec. Key considerations:
- Healer CPM is typically lower than DPS because healers triage — they don't always have a target to heal
- Large GCD gaps (> 3s) are less meaningful for healers; focus instead on gaps during high-damage phases
- Track DPS spell usage: good healers weave damage between heals (e.g., Holy Shock, Smite, Wrath)

## Module D (Healer): Cooldown Timing

Replace opener analysis — healers don't have a fixed opener. Instead:
- Map each major healing cooldown use to the fight timeline
- Identify what boss mechanic triggered each CD use
- Compare CD timing against the benchmark: are CDs used proactively (before damage) or reactively (after)?
- Check if CDs overlap unnecessarily (wasted throughput)
- Calculate theoretical max uses vs actual uses

Common healer CDs by spec (verify with guide search):
- Holy Paladin: Avenging Wrath, Daybreak, Divine Toll
- Restoration Druid: Tranquility, Flourish, Incarnation
- Holy Priest: Divine Hymn, Apotheosis, Holy Word: Salvation
- Discipline Priest: Evangelism/Spirit Shell, Power Word: Barrier, Rapture
- Restoration Shaman: Spirit Link Totem, Healing Tide Totem, Ascendance
- Mistweaver Monk: Revival/Restoral, Invoke Yu'lon, Celestial Conduit
- Preservation Evoker: Dream Flight, Rewind, Stasis

## Module E (Healer): Mana Efficiency

Replace DoT uptime analysis:
- Track mana-intensive spell usage patterns
- Compare total casts of expensive vs efficient heals
- Healer mana management is a key differentiator — running OOM means dead raid members

## Module F (Healer): Overhealing Analysis

Deeper dive into overhealing patterns:
- Use `events.healing_all` to analyze overhealing per spell over time
- Identify periods where overhealing spikes (competing with other healers, or healing when no damage)
- HoT sniping: if HoTs are consistently overhealing, they may be applied too late

## Module H (Healer): Damage Contribution

Many healer specs are expected to contribute DPS during downtime:
- Total damage done and DPS contribution
- Compare damage ability usage between the two healers
- Low DPS filler usage during low-damage phases = lost value

## Healer-Specific Considerations for Benchmark Selection

HPS rankings are more context-dependent than DPS rankings because:
- Healing output depends on how much damage the raid takes (fight duration, strategy, other healers)
- A healer with lower HPS in a clean kill may actually be better than one padding in a messy kill
- Team composition matters more: 3-heal vs 4-heal setups drastically change individual HPS

When reporting benchmark comparisons, always note these caveats.
