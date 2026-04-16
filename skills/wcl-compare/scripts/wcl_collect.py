#!/usr/bin/env python3
"""WCL data collector — fetches all analysis data for one player in one fight.

Usage:
    python3 wcl_collect.py <report_code> <fight_id> <player_name> [-o output.json]

Outputs a structured JSON with all data needed for comparative analysis.
"""

import argparse
import json
import re
import sys
from wcl_client import get_token, query


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_report_url(url_or_code: str) -> tuple[str, int | None]:
    """Extract report code and fight ID from a WCL URL or plain code.

    Returns (code, fight_id) where fight_id may be None.
    """
    # Full URL: https://www.warcraftlogs.com/reports/ABC123?fight=5
    m = re.search(r"reports/([A-Za-z0-9]+)", url_or_code)
    if m:
        code = m.group(1)
        fm = re.search(r"fight=(\d+)", url_or_code)
        fight_id = int(fm.group(1)) if fm else None
        return code, fight_id
    # Plain code
    return url_or_code.strip(), None


def paginate_events(report_code: str, fight_id: int, token: str, **kwargs) -> list[dict]:
    """Fetch all events with automatic pagination.

    kwargs are passed into the events() query: dataType, sourceID, targetID,
    hostilityType, useAbilityIDs, etc.
    """
    params = []
    for k, v in kwargs.items():
        if isinstance(v, str):
            params.append(f'{k}: {v}')
        elif isinstance(v, bool):
            params.append(f'{k}: {"true" if v else "false"}')
        else:
            params.append(f'{k}: {v}')
    param_str = ", ".join(params)

    all_events = []
    start_time = 0
    while True:
        q = f"""
        query($code: String!) {{
          reportData {{
            report(code: $code) {{
              events(
                fightIDs: [{fight_id}],
                startTime: {start_time},
                endTime: 999999999,
                limit: 10000,
                {param_str}
              ) {{
                data
                nextPageTimestamp
              }}
            }}
          }}
        }}
        """
        result = query(q, variables={"code": report_code}, token=token)
        events = result["data"]["reportData"]["report"]["events"]
        all_events.extend(events["data"])
        if events["nextPageTimestamp"] is None:
            break
        start_time = events["nextPageTimestamp"]
    return all_events


# ── Core collection ──────────────────────────────────────────────────────────

def collect_report_meta(code: str, fight_id: int, token: str) -> dict:
    """Fetch report-level metadata: title, zone, fight info, all players, NPCs."""
    result = query("""
    query($code: String!) {
      reportData {
        report(code: $code) {
          title
          startTime
          endTime
          zone { name id }
          fights(fightIDs: [%d]) {
            id name encounterID kill difficulty
            startTime endTime
            bossPercentage fightPercentage
            phaseTransitions { id startTime }
            enemyNPCs { id gameID }
          }
          masterData {
            actors(type: "Player") { id name subType server }
            npcs: actors(type: "NPC") { id name subType }
          }
        }
      }
    }
    """ % fight_id, variables={"code": code}, token=token)
    return result["data"]["reportData"]["report"]


def find_player(meta: dict, player_name: str) -> dict | None:
    """Find a player by name (case-insensitive) in report metadata."""
    actors = meta["masterData"]["actors"]
    # Exact match first
    for a in actors:
        if a["name"].lower() == player_name.lower():
            return a
    # Partial match
    for a in actors:
        if player_name.lower() in a["name"].lower():
            return a
    return None


def find_boss_id(meta: dict, fight_id: int) -> int | None:
    """Find the boss NPC actor ID for the fight."""
    fight = meta["fights"][0] if meta["fights"] else None
    if not fight:
        return None
    enemy_npc_ids = {n["id"] for n in fight.get("enemyNPCs", [])}
    npcs = meta["masterData"].get("npcs", [])
    for npc in npcs:
        if npc["id"] in enemy_npc_ids and npc.get("subType") == "Boss":
            return npc["id"]
    # Fallback: first enemy NPC
    if enemy_npc_ids and npcs:
        for npc in npcs:
            if npc["id"] in enemy_npc_ids:
                return npc["id"]
    return None


def collect_combatant_info(code: str, fight_id: int, source_id: int, token: str) -> dict:
    """Fetch CombatantInfo: stats, gear, talents."""
    result = query("""
    query($code: String!) {
      reportData {
        report(code: $code) {
          events(
            dataType: CombatantInfo,
            fightIDs: [%d],
            sourceID: %d,
            startTime: 0, endTime: 999999999,
            limit: 1
          ) { data }
        }
      }
    }
    """ % (fight_id, source_id), variables={"code": code}, token=token)
    events = result["data"]["reportData"]["report"]["events"]["data"]
    if not events:
        return {}
    info = events[0]
    # Extract the fields we need
    SLOTS = [
        "Head", "Neck", "Shoulder", "Shirt", "Chest", "Waist", "Legs", "Feet",
        "Wrist", "Hands", "Ring 1", "Ring 2", "Trinket 1", "Trinket 2",
        "Back", "Main Hand", "Off Hand", "Tabard",
    ]
    gear = []
    for i, g in enumerate(info.get("gear", [])):
        slot = SLOTS[i] if i < len(SLOTS) else f"Slot {i}"
        gear.append({
            "slot": slot,
            "id": g.get("id", 0),
            "itemLevel": g.get("itemLevel", 0),
            "permanentEnchant": g.get("permanentEnchant", 0),
            "temporaryEnchant": g.get("temporaryEnchant", 0),
            "gems": [gem.get("id", 0) for gem in g.get("gems", [])],
        })
    return {
        "specID": info.get("specID"),
        "intellect": info.get("intellect", 0),
        "agility": info.get("agility", 0),
        "strength": info.get("strength", 0),
        "stamina": info.get("stamina", 0),
        "critSpell": info.get("critSpell", 0),
        "critMelee": info.get("critMelee", 0),
        "hasteSpell": info.get("hasteSpell", 0),
        "hasteMelee": info.get("hasteMelee", 0),
        "mastery": info.get("mastery", 0),
        "versatilityDamageDone": info.get("versatilityDamageDone", 0),
        "versatilityDamageReduction": info.get("versatilityDamageReduction", 0),
        "speed": info.get("speed", 0),
        "leech": info.get("leech", 0),
        "gear": gear,
        "talentTree": info.get("talentTree", []),
    }


def collect_tables(code: str, fight_id: int, source_id: int, token: str) -> dict:
    """Fetch summary tables: damage, buffs, enemy debuffs."""
    result = query("""
    query($code: String!) {
      reportData {
        report(code: $code) {
          dmgDone: table(dataType: DamageDone, fightIDs: [%d], sourceID: %d)
          dmgAll: table(dataType: DamageDone, fightIDs: [%d])
          buffTable: table(dataType: Buffs, fightIDs: [%d], sourceID: %d)
          enemyDebuffs: table(dataType: Debuffs, fightIDs: [%d], hostilityType: Enemies)
        }
      }
    }
    """ % (fight_id, source_id, fight_id, fight_id, source_id, fight_id),
        variables={"code": code}, token=token)
    rr = result["data"]["reportData"]["report"]
    return {
        "damageDone": rr["dmgDone"]["data"],
        "damageDoneAll": rr["dmgAll"]["data"],
        "buffs": rr["buffTable"]["data"],
        "enemyDebuffs": rr["enemyDebuffs"]["data"],
    }


def collect_player_data(
    code: str, fight_id: int, source_id: int, boss_id: int | None,
    fight_start: int, fight_end: int, token: str,
) -> dict:
    """Collect all event-level data for a player."""
    print(f"  Collecting cast events...", file=sys.stderr)
    casts = paginate_events(code, fight_id, token,
        dataType="Casts", sourceID=source_id, useAbilityIDs=False)

    print(f"  Collecting damage events (all targets)...", file=sys.stderr)
    dmg_all = paginate_events(code, fight_id, token,
        dataType="DamageDone", sourceID=source_id, useAbilityIDs=False)

    dmg_boss = []
    if boss_id:
        print(f"  Collecting damage events (boss only, targetID={boss_id})...", file=sys.stderr)
        dmg_boss = paginate_events(code, fight_id, token,
            dataType="DamageDone", sourceID=source_id, targetID=boss_id, useAbilityIDs=False)

    print(f"  Collecting buff events...", file=sys.stderr)
    buffs = paginate_events(code, fight_id, token,
        dataType="Buffs", sourceID=source_id, useAbilityIDs=False)

    print(f"  Collecting summon events...", file=sys.stderr)
    summons = paginate_events(code, fight_id, token,
        dataType="Summons", sourceID=source_id, useAbilityIDs=False)

    return {
        "casts": casts,
        "damage_all": dmg_all,
        "damage_boss": dmg_boss,
        "buffs": buffs,
        "summons": summons,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def collect(report_code: str, fight_id: int, player_name: str, token: str | None = None) -> dict:
    """Main entry point: collect all data for one player in one fight.

    Returns a structured dict ready for JSON serialization.
    """
    if token is None:
        token = get_token()

    print(f"Collecting data for {player_name} in {report_code} fight #{fight_id}...",
          file=sys.stderr)

    # 1. Report metadata
    print("  Fetching report metadata...", file=sys.stderr)
    meta = collect_report_meta(report_code, fight_id, token)
    fight = meta["fights"][0] if meta["fights"] else None
    if not fight:
        raise ValueError(f"Fight #{fight_id} not found in report {report_code}")

    fight_start = fight["startTime"]
    fight_end = fight["endTime"]
    duration = (fight_end - fight_start) / 1000

    # 2. Find player
    player = find_player(meta, player_name)
    if not player:
        all_names = [a["name"] for a in meta["masterData"]["actors"]]
        raise ValueError(
            f"Player '{player_name}' not found. Available: {', '.join(all_names)}"
        )
    source_id = player["id"]
    print(f"  Found: {player['name']} ({player['subType']}) ID={source_id}", file=sys.stderr)

    # 3. Find boss
    boss_id = find_boss_id(meta, fight_id)
    if boss_id:
        # Find boss name
        npcs = meta["masterData"].get("npcs", [])
        boss_name = next((n["name"] for n in npcs if n["id"] == boss_id), "Unknown")
        print(f"  Boss: {boss_name} (ID={boss_id})", file=sys.stderr)
    else:
        boss_name = fight["name"]
        print(f"  Boss ID not found, using fight name: {boss_name}", file=sys.stderr)

    # 4. CombatantInfo
    print("  Fetching combatant info...", file=sys.stderr)
    combatant = collect_combatant_info(report_code, fight_id, source_id, token)

    # 5. Summary tables
    print("  Fetching summary tables...", file=sys.stderr)
    tables = collect_tables(report_code, fight_id, source_id, token)

    # 6. Event-level data
    events = collect_player_data(
        report_code, fight_id, source_id, boss_id,
        fight_start, fight_end, token,
    )

    # 7. Rate limit check
    rl = query("{ rateLimitData { limitPerHour pointsSpentThisHour pointsResetIn } }", token=token)
    rate_limit = rl["data"]["rateLimitData"]
    print(f"  API points used: {rate_limit['pointsSpentThisHour']}/{rate_limit['limitPerHour']}",
          file=sys.stderr)

    return {
        "report": {
            "code": report_code,
            "title": meta.get("title", ""),
            "zone": meta.get("zone", {}),
        },
        "fight": {
            "id": fight_id,
            "name": fight["name"],
            "encounterID": fight["encounterID"],
            "difficulty": fight["difficulty"],
            "kill": fight["kill"],
            "duration": duration,
            "startTime": fight_start,
            "endTime": fight_end,
            "bossPercentage": fight.get("bossPercentage"),
            "phaseTransitions": fight.get("phaseTransitions", []),
        },
        "player": {
            "name": player["name"],
            "class": player["subType"],
            "server": player.get("server", ""),
            "sourceID": source_id,
            "specID": combatant.get("specID"),
        },
        "boss": {
            "name": boss_name,
            "id": boss_id,
        },
        "stats": {
            "intellect": combatant.get("intellect", 0),
            "agility": combatant.get("agility", 0),
            "strength": combatant.get("strength", 0),
            "stamina": combatant.get("stamina", 0),
            "critSpell": combatant.get("critSpell", 0),
            "critMelee": combatant.get("critMelee", 0),
            "hasteSpell": combatant.get("hasteSpell", 0),
            "hasteMelee": combatant.get("hasteMelee", 0),
            "mastery": combatant.get("mastery", 0),
            "versatilityDamageDone": combatant.get("versatilityDamageDone", 0),
            "versatilityDamageReduction": combatant.get("versatilityDamageReduction", 0),
            "speed": combatant.get("speed", 0),
            "leech": combatant.get("leech", 0),
        },
        "gear": combatant.get("gear", []),
        "talentTree": combatant.get("talentTree", []),
        "tables": tables,
        "events": events,
        "rateLimit": rate_limit,
    }


def main():
    parser = argparse.ArgumentParser(description="Collect WCL analysis data for a player.")
    parser.add_argument("report", help="WCL report URL or code")
    parser.add_argument("fight_id", nargs="?", type=int, default=None,
                        help="Fight ID (extracted from URL if not given)")
    parser.add_argument("player", help="Player name")
    parser.add_argument("-o", "--output", default=None, help="Output JSON file (default: stdout)")
    args = parser.parse_args()

    code, url_fight_id = parse_report_url(args.report)
    fight_id = args.fight_id or url_fight_id
    if fight_id is None:
        print("Error: fight ID required (via URL ?fight=N or as argument)", file=sys.stderr)
        sys.exit(1)

    token = get_token()
    data = collect(code, fight_id, args.player, token)

    output = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
