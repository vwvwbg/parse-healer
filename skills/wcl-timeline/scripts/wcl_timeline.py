#!/usr/bin/env python3
"""
wcl_timeline.py — 從 Warcraft Logs 報告中提取指定技能的施放時間，
                   生成 STT (ShengTangTools) 格式的時間軸方案。

用法:
    python wcl_timeline.py <report_code> <fight_id> <player_name> <spell_names_or_ids> [-o output.txt] [--role-tag 织雾1]

範例:
    python wcl_timeline.py arw7HCtQWfxpALjz 5 Rathuxmk "Celestial Conduit,Restoral,Invoke Yu'lon, the Jade Serpent"
    python wcl_timeline.py arw7HCtQWfxpALjz 5 Rathuxmk "443028,388615,322118"
    python wcl_timeline.py arw7HCtQWfxpALjz 5 Rathuxmk "443028,Restoral" -o timeline.txt --role-tag 奶僧1
"""

import argparse
import io
import json
import os
import sys
import re

# 確保 stdout 使用 UTF-8 編碼（Windows 相容）
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 將 wcl-compare 的 scripts 目錄加入 path，以複用 wcl_client
COMPARE_SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "wcl-compare", "scripts")
sys.path.insert(0, os.path.abspath(COMPARE_SCRIPTS))

from wcl_client import get_token, query as wcl_query

# spell_db.json 路徑
SPELL_DB_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "wcl-spelldb", "references", "spell_db.json"
))


def load_spell_db() -> dict:
    """載入靜態技能資料庫。"""
    if not os.path.exists(SPELL_DB_PATH):
        return {}
    try:
        with open(SPELL_DB_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)
        return db.get("spells", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def parse_report_url(url_or_code: str):
    """從完整 URL 或單純 report code 中解析出 report_code。"""
    # 完整 URL: https://www.warcraftlogs.com/reports/arw7HCtQWfxpALjz#fight=5
    m = re.match(r"https?://.*warcraftlogs\.com/reports/([A-Za-z0-9]+)", url_or_code)
    if m:
        return m.group(1)
    return url_or_code


def collect_casts(token: str, report_code: str, fight_id: int, source_id: int,
                  start_time: int, end_time: int):
    """從 WCL API 收集指定玩家的所有施法事件。"""
    gql = """
    query($code: String!, $fightID: Int!, $sourceID: Int!, $startTime: Float!, $endTime: Float!) {
        reportData {
            report(code: $code) {
                events(
                    fightIDs: [$fightID]
                    sourceID: $sourceID
                    startTime: $startTime
                    endTime: $endTime
                    dataType: Casts
                    limit: 10000
                ) {
                    data
                    nextPageTimestamp
                }
            }
        }
    }
    """
    all_events = []
    current_start = start_time
    while True:
        result = wcl_query(gql, {
            "code": report_code,
            "fightID": fight_id,
            "sourceID": source_id,
            "startTime": current_start,
            "endTime": end_time,
        }, token=token)
        events_data = result["data"]["reportData"]["report"]["events"]
        all_events.extend(events_data["data"])
        npt = events_data.get("nextPageTimestamp")
        if npt is None:
            break
        current_start = npt
    return all_events


def get_fight_and_player(token: str, report_code: str, fight_id: int, player_name: str):
    """取得戰鬥資訊與玩家 sourceID。"""
    gql = """
    query($code: String!, $fightID: Int!) {
        reportData {
            report(code: $code) {
                fights(fightIDs: [$fightID]) {
                    id name encounterID difficulty kill
                    startTime endTime
                }
                masterData {
                    actors(type: "Player") {
                        id name type subType server
                    }
                    abilities {
                        gameID name type
                    }
                }
            }
        }
    }
    """
    result = wcl_query(gql, {"code": report_code, "fightID": fight_id}, token=token)
    report = result["data"]["reportData"]["report"]

    fights = report["fights"]
    if not fights:
        print(f"Error: Fight #{fight_id} not found in report {report_code}", file=sys.stderr)
        sys.exit(1)
    fight = fights[0]

    actors = report["masterData"]["actors"]
    player = None
    for a in actors:
        if a["name"].lower() == player_name.lower():
            player = a
            break
    if not player:
        names = [a["name"] for a in actors]
        print(f"Error: Player '{player_name}' not found. Available: {', '.join(names)}", file=sys.stderr)
        sys.exit(1)

    # 建立 gameID -> name 的映射表
    ability_map = {}
    for ab in report["masterData"].get("abilities", []):
        ability_map[ab["gameID"]] = ab["name"]

    return fight, player, ability_map


def parse_spell_filters(spell_input: str):
    """解析使用者輸入的技能篩選條件，支援技能名稱或 spell ID，逗號分隔。
    
    回傳: (name_set, id_set) — 分別是要匹配的名稱集合和 ID 集合。
    """
    names = set()
    ids = set()
    # 先用逗號分隔，但要處理技能名中可能含逗號的情況（如 "Invoke Yu'lon, the Jade Serpent"）
    # 策略：先嘗試以數字 ID 分割，剩下的作為名稱匹配
    parts = [p.strip() for p in spell_input.split(",") if p.strip()]

    i = 0
    while i < len(parts):
        part = parts[i]
        # 純數字 → spell ID
        if part.isdigit():
            ids.add(int(part))
            i += 1
        else:
            # 嘗試貪婪匹配：往後合併直到找到下一個純數字或結尾
            combined = part
            j = i + 1
            while j < len(parts) and not parts[j].isdigit():
                # 檢查合併後是否更像一個完整技能名
                combined = combined + ", " + parts[j]
                j += 1
            # 如果原始 part 本身看起來就是個合理的技能名，優先用短的
            # 但如果下一個 part 開頭是小寫（如 "the Jade Serpent"），合併
            final_name = part
            k = i + 1
            while k < len(parts) and not parts[k].isdigit():
                next_part = parts[k]
                if next_part and next_part[0].islower():
                    final_name = final_name + ", " + next_part
                    k += 1
                else:
                    break
            names.add(final_name.lower())
            i = k
    return names, ids


def format_time(seconds: float) -> str:
    """將秒數格式化為 MM:SS。"""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


def generate_stt_timeline(player_name: str, boss_name: str, report_code: str,
                          fight_id: int, role_tag: str,
                          filtered_events: list) -> str:
    """生成 STT 格式的時間軸文本。"""
    lines = []
    lines.append("[方案]")
    lines.append(f"名称={boss_name} - {role_tag}CD轴")
    lines.append(f"作者={player_name} ({report_code} #{fight_id})")
    lines.append("")
    lines.append("[人员]")
    lines.append(f"{role_tag}={player_name}")
    lines.append("")
    lines.append("[时间轴]")
    lines.append("")

    for ts, spell_id, spell_name in filtered_events:
        time_str = format_time(ts)
        lines.append(f"{{time:{time_str}}} {{{role_tag}}}{{spell:{spell_id}}}")

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="從 WCL 報告提取指定技能施放時間，生成 STT 時間軸方案"
    )
    parser.add_argument("report", help="WCL report code 或完整 URL")
    parser.add_argument("fight_id", type=int, help="Fight ID")
    parser.add_argument("player", help="玩家角色名")
    parser.add_argument("spells", help="要篩選的技能名稱或 spell ID，逗號分隔")
    parser.add_argument("-o", "--output", help="輸出檔案路徑（不指定則輸出到 stdout）")
    parser.add_argument("--role-tag", default=None,
                        help="STT 人員標籤（預設使用玩家名）")
    args = parser.parse_args()

    report_code = parse_report_url(args.report)
    spell_names, spell_ids = parse_spell_filters(args.spells)

    print(f"Connecting to Warcraft Logs API...", file=sys.stderr)
    token = get_token()

    print(f"Fetching fight #{args.fight_id} from {report_code}...", file=sys.stderr)
    fight, player, ability_map = get_fight_and_player(token, report_code, args.fight_id, args.player)

    boss_name = fight["name"]
    start_time = fight["startTime"]
    end_time = fight["endTime"]
    source_id = player["id"]
    duration = (end_time - start_time) / 1000

    print(f"  Boss: {boss_name}, Duration: {duration:.1f}s", file=sys.stderr)
    print(f"  Player: {player['name']} (ID={source_id})", file=sys.stderr)
    print(f"  Spell filters — names: {spell_names or '(none)'}, IDs: {spell_ids or '(none)'}", file=sys.stderr)

    print(f"Collecting cast events...", file=sys.stderr)
    casts = collect_casts(token, report_code, args.fight_id, source_id, start_time, end_time)
    print(f"  Total cast events: {len(casts)}", file=sys.stderr)

    # 篩選匹配的技能
    filtered = []
    matched_spells = set()
    for e in casts:
        if e.get("type") != "cast":
            continue
        sid = e.get("abilityGameID", 0)
        name = ability_map.get(sid, f"Unknown-{sid}")
        t = (e["timestamp"] - start_time) / 1000

        if sid in spell_ids or name.lower() in spell_names:
            filtered.append((t, sid, name))
            matched_spells.add(f"{name} [{sid}]")

    filtered.sort(key=lambda x: x[0])

    print(f"  Matched {len(filtered)} casts from: {', '.join(sorted(matched_spells))}", file=sys.stderr)

    if not filtered:
        # 列出所有可用技能供使用者參考
        all_spells = {}
        for e in casts:
            if e.get("type") == "cast":
                sid = e.get("abilityGameID", 0)
                name = ability_map.get(sid, f"Unknown-{sid}")
                if sid not in all_spells:
                    all_spells[sid] = {"name": name, "count": 0}
                all_spells[sid]["count"] += 1
        print("\nNo matching spells found. Available spells:", file=sys.stderr)
        for sid, info in sorted(all_spells.items(), key=lambda x: -x[1]["count"]):
            print(f"  [{sid}] {info['name']} ({info['count']}x)", file=sys.stderr)
        sys.exit(1)

    # 生成 STT 時間軸
    role_tag = args.role_tag or player["name"]
    output = generate_stt_timeline(
        player["name"], boss_name, report_code,
        args.fight_id, role_tag, filtered
    )

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\nSaved to {args.output}", file=sys.stderr)
    else:
        print(output)

    # 載入 spell DB 以提供額外資訊
    spell_db = load_spell_db()

    # 輸出摘要
    print(f"\n=== Summary ===", file=sys.stderr)
    print(f"Boss: {boss_name} ({duration:.0f}s)", file=sys.stderr)
    for spell_str in sorted(matched_spells):
        count = sum(1 for _, sid, name in filtered if f"{name} [{sid}]" == spell_str)
        # 從 spell_db 取得額外資訊
        sid_num = spell_str.split("[")[-1].rstrip("]")
        db_entry = spell_db.get(sid_num, {})
        cd_info = f" (CD={db_entry['cd']}s)" if db_entry.get("cd") else ""
        class_info = f" [{db_entry['class']}/{db_entry['spec']}]" if db_entry.get("class") else ""
        print(f"  {spell_str}{cd_info}{class_info}: {count}x", file=sys.stderr)

    # 如果有技能不在 spell_db 中，提示使用者
    missing = []
    for _, sid, name in filtered:
        if str(sid) not in spell_db and sid not in [m[0] for m in missing]:
            missing.append((sid, name))
    if missing:
        print(f"\n  Note: {len(missing)} spell(s) not in spell_db.json:", file=sys.stderr)
        for sid, name in missing:
            print(f"    [{sid}] {name} — run: /wcl-spelldb add {sid}", file=sys.stderr)


if __name__ == "__main__":
    main()
