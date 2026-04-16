#!/usr/bin/env python3
"""Find a suitable benchmark player from WCL rankings.

Given a player's fight data, searches WCL rankings for a comparable top player
with similar external buff conditions (Aug Evoker, external PI, fight duration).

Usage:
    python3 wcl_find_benchmark.py <collected_json>

Outputs the benchmark player's report code, fight ID, and name.
"""

import argparse
import json
import sys
from wcl_client import get_token, query


# WCL spec IDs → class/spec names (common DPS specs)
SPEC_NAMES = {
    62: ("Mage", "Arcane"), 63: ("Mage", "Fire"), 64: ("Mage", "Frost"),
    65: ("Paladin", "Holy"), 66: ("Paladin", "Protection"), 70: ("Paladin", "Retribution"),
    71: ("Warrior", "Arms"), 72: ("Warrior", "Fury"), 73: ("Warrior", "Protection"),
    102: ("Druid", "Balance"), 103: ("Druid", "Feral"), 104: ("Druid", "Guardian"),
    105: ("Druid", "Restoration"),
    250: ("DeathKnight", "Blood"), 251: ("DeathKnight", "Frost"), 252: ("DeathKnight", "Unholy"),
    253: ("Hunter", "BeastMastery"), 254: ("Hunter", "Marksmanship"), 255: ("Hunter", "Survival"),
    256: ("Priest", "Discipline"), 257: ("Priest", "Holy"), 258: ("Priest", "Shadow"),
    259: ("Rogue", "Assassination"), 260: ("Rogue", "Outlaw"), 261: ("Rogue", "Subtlety"),
    262: ("Shaman", "Elemental"), 263: ("Shaman", "Enhancement"), 264: ("Shaman", "Restoration"),
    265: ("Warlock", "Affliction"), 266: ("Warlock", "Demonology"), 267: ("Warlock", "Destruction"),
    268: ("Monk", "Brewmaster"), 269: ("Monk", "Windwalker"), 270: ("Monk", "Mistweaver"),
    577: ("DemonHunter", "Havoc"), 581: ("DemonHunter", "Vengeance"),
    1467: ("Evoker", "Devastation"), 1468: ("Evoker", "Preservation"), 1473: ("Evoker", "Augmentation"),
}

# Buff names indicating external augmentation
AUG_BUFFS = {"Ebon Might", "Prescience", "Shifting Sands"}
EXT_PI_BUFF = "Power Infusion"


def detect_external_conditions(collected: dict) -> dict:
    """Detect external buff conditions from collected data."""
    buffs = collected["tables"]["buffs"].get("auras", [])
    duration = collected["fight"]["duration"]

    has_aug = False
    aug_uptime = 0
    ext_pi_count = 0

    for b in buffs:
        name = b.get("name", "")
        if name in AUG_BUFFS:
            has_aug = True
            if name == "Ebon Might":
                aug_uptime = b.get("totalUptime", 0) / 1000 / duration * 100

        # Detect external PI: if PI uses > Voidform uses (or similar CD count), likely external
        if name == EXT_PI_BUFF:
            ext_pi_count = b.get("totalUses", 0)

    # Count self-PI (should match major CD count)
    voidform_count = 0
    for b in buffs:
        if b.get("name") in ("Voidform", "Dark Ascension", "Metamorphosis",
                              "Combustion", "Icy Veins", "Avenging Wrath",
                              "Celestial Alignment", "Pillar of Frost",
                              "Summon Demonic Tyrant", "Deathborne"):
            voidform_count = max(voidform_count, b.get("totalUses", 0))

    has_ext_pi = ext_pi_count > voidform_count if voidform_count > 0 else False

    return {
        "has_aug": has_aug,
        "aug_uptime": aug_uptime,
        "has_ext_pi": has_ext_pi,
        "pi_count": ext_pi_count,
        "major_cd_count": voidform_count,
    }


def get_rankings(encounter_id: int, difficulty: int, class_name: str, spec_name: str,
                 token: str, page: int = 1) -> dict:
    """Fetch character rankings from WCL."""
    result = query("""
    query {
      worldData {
        encounter(id: %d) {
          name
          characterRankings(
            specName: "%s"
            className: "%s"
            difficulty: %d
            metric: dps
            page: %d
          )
        }
      }
    }
    """ % (encounter_id, spec_name, class_name, difficulty, page), token=token)
    return result["data"]["worldData"]["encounter"]


def check_candidate_buffs(report_code: str, fight_id: int, source_id: int, token: str) -> dict:
    """Quick check a candidate's buff table for external conditions."""
    result = query("""
    query($code: String!) {
      reportData {
        report(code: $code) {
          fights(fightIDs: [%d]) { startTime endTime }
          buffTable: table(dataType: Buffs, fightIDs: [%d], sourceID: %d)
        }
      }
    }
    """ % (fight_id, fight_id, source_id), variables={"code": report_code}, token=token)

    rr = result["data"]["reportData"]["report"]
    fight = rr["fights"][0] if rr["fights"] else None
    if not fight:
        return {"error": "fight not found"}

    duration = (fight["endTime"] - fight["startTime"]) / 1000
    auras = rr["buffTable"]["data"].get("auras", [])

    has_aug = False
    aug_uptime = 0
    pi_count = 0

    for a in auras:
        name = a.get("name", "")
        if name in AUG_BUFFS:
            has_aug = True
            if name == "Ebon Might":
                aug_uptime = a.get("totalUptime", 0) / 1000 / duration * 100
        if name == EXT_PI_BUFF:
            pi_count = a.get("totalUses", 0)

    return {
        "duration": duration,
        "has_aug": has_aug,
        "aug_uptime": aug_uptime,
        "pi_count": pi_count,
    }


def find_source_id(report_code: str, fight_id: int, player_name: str, token: str) -> int | None:
    """Find a player's sourceID in a report."""
    result = query("""
    query($code: String!) {
      reportData {
        report(code: $code) {
          masterData {
            actors(type: "Player") { id name subType }
          }
        }
      }
    }
    """, variables={"code": report_code}, token=token)
    actors = result["data"]["reportData"]["report"]["masterData"]["actors"]
    for a in actors:
        if a["name"] == player_name:
            return a["id"]
    # Partial match
    for a in actors:
        if player_name.lower() in a["name"].lower():
            return a["id"]
    return None


def find_benchmark(collected: dict, token: str | None = None, verbose: bool = True) -> dict | None:
    """Find a suitable benchmark player from WCL rankings.

    Returns dict with: report_code, fight_id, player_name, source_id, dps, duration
    or None if no suitable benchmark found.
    """
    if token is None:
        token = get_token()

    encounter_id = collected["fight"]["encounterID"]
    difficulty = collected["fight"]["difficulty"]
    player_duration = collected["fight"]["duration"]
    spec_id = collected["player"].get("specID")

    if not spec_id or spec_id not in SPEC_NAMES:
        print(f"Unknown specID: {spec_id}", file=sys.stderr)
        return None

    class_name, spec_name = SPEC_NAMES[spec_id]
    my_conditions = detect_external_conditions(collected)

    if verbose:
        print(f"Looking for benchmark: {class_name} {spec_name} on encounter {encounter_id} "
              f"(D{difficulty})", file=sys.stderr)
        print(f"Player conditions: Aug={'Yes' if my_conditions['has_aug'] else 'No'} "
              f"({my_conditions['aug_uptime']:.0f}%), "
              f"ExtPI={'Yes' if my_conditions['has_ext_pi'] else 'No'}, "
              f"Duration={player_duration:.0f}s", file=sys.stderr)

    # Fetch rankings
    enc = get_rankings(encounter_id, difficulty, class_name, spec_name, token)
    rankings = enc.get("characterRankings", {}).get("rankings", [])

    if not rankings:
        print("No rankings found.", file=sys.stderr)
        return None

    if verbose:
        print(f"Found {len(rankings)} rankings, filtering...", file=sys.stderr)

    # Calculate median duration from top 20
    durations = [r.get("duration", 0) / 1000 for r in rankings[:20]]
    median_dur = sorted(durations)[len(durations) // 2] if durations else player_duration

    # Filter candidates
    candidates = []
    for i, r in enumerate(rankings):
        rank = i + 1
        dur = r.get("duration", 0) / 1000
        report_code = r.get("report", {}).get("code", "")
        fight_id = r.get("report", {}).get("fightID", 0)
        name = r.get("name", "?")
        dps = r.get("amount", 0)

        # Skip #1-3 (likely padded)
        if rank <= 3:
            if verbose:
                print(f"  Skip #{rank} {name} ({dps:,.0f} DPS, {dur:.0f}s) — top 3, likely optimized",
                      file=sys.stderr)
            continue

        # Skip fights that are too short (< median * 0.7)
        if dur < median_dur * 0.7:
            if verbose:
                print(f"  Skip #{rank} {name} ({dps:,.0f} DPS, {dur:.0f}s) — too short "
                      f"(< {median_dur * 0.7:.0f}s)", file=sys.stderr)
            continue

        # Skip fights that are much longer than median (> median * 1.5)
        if dur > median_dur * 1.5:
            if verbose:
                print(f"  Skip #{rank} {name} ({dps:,.0f} DPS, {dur:.0f}s) — too long",
                      file=sys.stderr)
            continue

        candidates.append({
            "rank": rank,
            "name": name,
            "dps": dps,
            "duration": dur,
            "report_code": report_code,
            "fight_id": fight_id,
        })

        # Collect up to 8 candidates
        if len(candidates) >= 8:
            break

    if not candidates:
        print("No suitable candidates after filtering.", file=sys.stderr)
        return None

    if verbose:
        print(f"  {len(candidates)} candidates passed duration filter", file=sys.stderr)

    # Check top 3 candidates' buff conditions
    best = None
    best_score = -1

    for c in candidates[:5]:
        if verbose:
            print(f"  Checking #{c['rank']} {c['name']} ({c['dps']:,.0f} DPS, "
                  f"{c['duration']:.0f}s)...", file=sys.stderr)

        source_id = find_source_id(c["report_code"], c["fight_id"], c["name"], token)
        if not source_id:
            if verbose:
                print(f"    Could not find sourceID, skipping", file=sys.stderr)
            continue

        cond = check_candidate_buffs(c["report_code"], c["fight_id"], source_id, token)
        if "error" in cond:
            continue

        # Score: prefer matching external conditions
        score = 100 - c["rank"]  # Higher rank = slightly better

        # Aug matching: big bonus if conditions match
        if my_conditions["has_aug"] == cond["has_aug"]:
            score += 50
        else:
            score -= 30

        # Duration similarity bonus
        dur_diff = abs(c["duration"] - player_duration) / player_duration
        score -= dur_diff * 20

        if verbose:
            print(f"    Aug={'Yes' if cond['has_aug'] else 'No'} "
                  f"({cond['aug_uptime']:.0f}%), PI×{cond['pi_count']}, "
                  f"score={score:.0f}", file=sys.stderr)

        if score > best_score:
            best_score = score
            best = {**c, "source_id": source_id, "conditions": cond}

    if best and verbose:
        print(f"\n  Selected: #{best['rank']} {best['name']} "
              f"({best['dps']:,.0f} DPS, {best['duration']:.0f}s) "
              f"score={best_score:.0f}", file=sys.stderr)

    return best


def main():
    parser = argparse.ArgumentParser(description="Find a WCL benchmark player.")
    parser.add_argument("collected_json", help="JSON from wcl_collect.py")
    args = parser.parse_args()

    with open(args.collected_json, encoding="utf-8") as f:
        collected = json.load(f)

    token = get_token()
    result = find_benchmark(collected, token)

    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("No suitable benchmark found.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
