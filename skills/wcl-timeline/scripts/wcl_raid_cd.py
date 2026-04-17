#!/usr/bin/env python3
"""
wcl_raid_cd.py — 根據 WCL 報告的團隊受傷數據，自動排程減傷/治療 CD，
                  生成 STT 格式的時間軸方案。

流程:
  1. 從 WCL 取得全團 DamageTaken 事件
  2. 以 5 秒窗口聚合，識別高傷害峰值
  3. 偵測團隊組成（職業/專精）
  4. 從 spell_db.json 匹配可用的團隊 CD
  5. 貪心算法自動排程 CD 到傷害峰值
  6. 生成 STT 時間軸

用法:
    python wcl_raid_cd.py <report_code> <fight_id> [-o output.txt] [--top N] [--pre-cast SEC] [--types raid_cd,healing_cd]
"""

import argparse
import io
import json
import os
import re
import sys
from collections import defaultdict

# Windows UTF-8 相容
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 複用 wcl_client
COMPARE_SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "wcl-compare", "scripts")
sys.path.insert(0, os.path.abspath(COMPARE_SCRIPTS))

from wcl_client import get_token, query as wcl_query

# spell_db.json 路徑
SPELL_DB_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "wcl-spelldb", "references", "spell_db.json"
))

# WCL API 回傳的 class 名稱可能無空格（如 "DeathKnight"），需要正規化為 spell_db 使用的格式
CLASS_NAME_MAP = {
    "DeathKnight": "Death Knight",
    "DemonHunter": "Demon Hunter",
    "Death Knight": "Death Knight",
    "Demon Hunter": "Demon Hunter",
}


def normalize_class(cls: str) -> str:
    """將 WCL API 的 class 名稱正規化為 spell_db 格式。"""
    return CLASS_NAME_MAP.get(cls, cls)


# 職業/專精 → 中文 role-tag 映射
ROLE_TAG_MAP = {
    ("Druid", "Restoration"): "奶德",
    ("Paladin", "Holy"): "奶骑",
    ("Priest", "Holy"): "神牧",
    ("Priest", "Discipline"): "戒律",
    ("Shaman", "Restoration"): "奶萨",
    ("Monk", "Mistweaver"): "织雾",
    ("Evoker", "Preservation"): "龙人",
    ("Warrior", None): "战士",
    ("Death Knight", None): "DK",
    ("Demon Hunter", None): "DH",
}


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
    """從完整 URL 或 report code 中解析出 report_code 和可選的 fight_id。"""
    m = re.match(r"https?://.*warcraftlogs\.com/reports/([A-Za-z0-9]+)(?:#fight=(\d+))?", url_or_code)
    if m:
        code = m.group(1)
        fid = int(m.group(2)) if m.group(2) else None
        return code, fid
    return url_or_code, None


def get_fight_and_roster(token: str, report_code: str, fight_id: int):
    """取得戰鬥資訊與完整團隊組成（含職業/專精）。"""
    gql = """
    query($code: String!, $fightID: Int!) {
        reportData {
            report(code: $code) {
                fights(fightIDs: [$fightID]) {
                    id name encounterID difficulty kill
                    startTime endTime
                }
                playerDetails(fightIDs: [$fightID])
            }
        }
    }
    """
    result = wcl_query(gql, {"code": report_code, "fightID": fight_id}, token=token)
    report = result["data"]["reportData"]["report"]

    fights = report["fights"]
    if not fights:
        print(f"Error: Fight #{fight_id} not found.", file=sys.stderr)
        sys.exit(1)
    fight = fights[0]

    # playerDetails 回傳分組的玩家資訊: {tanks: [...], healers: [...], dps: [...]}
    pd = report["playerDetails"]
    if isinstance(pd, dict) and "data" in pd:
        groups = pd["data"]["playerDetails"]
    elif isinstance(pd, dict) and "playerDetails" in pd:
        groups = pd["playerDetails"]
    else:
        groups = pd if isinstance(pd, dict) else {}

    # 合併所有分組為一個 roster
    roster = []
    for role_group, players in groups.items():
        for p in players:
            spec = p["specs"][0]["spec"] if p.get("specs") else "Unknown"
            roster.append({
                "id": p["id"],
                "name": p["name"],
                "type": p.get("type", "Unknown"),      # class name: "Monk", "Warrior"...
                "subType": spec,                        # spec name: "Mistweaver", "Holy"...
                "role_group": role_group,                # "tanks", "healers", "dps"
            })

    return fight, roster


def fetch_damage_taken(token: str, report_code: str, fight_id: int,
                       start_time: int, end_time: int):
    """取得全團 DamageTaken 事件。"""
    gql = """
    query($code: String!, $fightID: Int!, $startTime: Float!, $endTime: Float!) {
        reportData {
            report(code: $code) {
                events(
                    fightIDs: [$fightID]
                    startTime: $startTime
                    endTime: $endTime
                    dataType: DamageTaken
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
    page = 0
    while True:
        page += 1
        print(f"  Fetching damage taken events (page {page})...", file=sys.stderr)
        result = wcl_query(gql, {
            "code": report_code,
            "fightID": fight_id,
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


def fetch_player_casts(token: str, report_code: str, fight_id: int,
                      start_time: int, end_time: int) -> dict:
    """取得該場戰鬥中每個玩家實際施放的技能 ID 集合。

    回傳: {sourceID: set(abilityGameID, ...), ...}
    """
    gql = """
    query($code: String!, $fightID: Int!, $startTime: Float!, $endTime: Float!) {
        reportData {
            report(code: $code) {
                events(
                    fightIDs: [$fightID]
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
    player_abilities = defaultdict(set)
    current_start = start_time
    page = 0
    while True:
        page += 1
        print(f"  Fetching cast events (page {page})...", file=sys.stderr)
        result = wcl_query(gql, {
            "code": report_code,
            "fightID": fight_id,
            "startTime": current_start,
            "endTime": end_time,
        }, token=token)
        events_data = result["data"]["reportData"]["report"]["events"]
        for ev in events_data["data"]:
            sid = ev.get("sourceID")
            aid = ev.get("abilityGameID")
            if sid is not None and aid is not None:
                player_abilities[sid].add(aid)
        npt = events_data.get("nextPageTimestamp")
        if npt is None:
            break
        current_start = npt
    return dict(player_abilities)


def find_damage_peaks(events: list, start_time: int, end_time: int,
                      window_sec: int = 5, top_n: int = 15):
    """以滑動窗口找出團隊受傷峰值。

    回傳: [(window_center_sec, total_damage), ...] 按傷害量排序
    """
    duration = (end_time - start_time) / 1000
    # 將事件聚合到 1 秒桶
    buckets = defaultdict(int)
    for e in events:
        t_sec = (e["timestamp"] - start_time) / 1000
        bucket = int(t_sec)
        amount = e.get("amount", 0)
        buckets[bucket] += amount

    # 滑動窗口求和
    max_bucket = int(duration) + 1
    windows = []
    for i in range(max_bucket):
        total = sum(buckets.get(i + j, 0) for j in range(window_sec))
        if total > 0:
            center = i + window_sec / 2
            windows.append((center, total))

    # 排序：傷害最高的在前
    windows.sort(key=lambda x: -x[1])

    # 合併相鄰峰值（10 秒內只保留最高的）
    merged = []
    used_times = set()
    for center, dmg in windows:
        # 檢查是否與已選的峰值太近
        too_close = False
        for used_center in used_times:
            if abs(center - used_center) < 10:
                too_close = True
                break
        if not too_close:
            merged.append((center, dmg))
            used_times.add(center)
        if len(merged) >= top_n:
            break

    return merged


def get_role_tag(cls: str, spec: str) -> str:
    """根據職業/專精取得中文 role-tag。"""
    tag = ROLE_TAG_MAP.get((cls, spec))
    if tag:
        return tag
    # fallback: 嘗試只用 class
    tag = ROLE_TAG_MAP.get((cls, None))
    if tag:
        return tag
    return cls


def match_cds_to_roster(spell_db: dict, roster: list, cd_types: list,
                        player_casts: dict = None):
    """根據團隊組成和 spell_db，匹配每個玩家可用的團隊 CD。

    若提供 player_casts（{sourceID: set(abilityGameID)}），會驗證天賦：
    只有玩家在戰鬥中實際施放過的技能才會被納入排程。

    回傳: [(player_name, role_tag, spell_id, spell_name, cd_seconds), ...]
    """
    available_cds = []
    skipped = []
    for player in roster:
        p_class = normalize_class(player.get("type", ""))
        p_spec = player.get("subType", "")
        p_name = player["name"]
        p_id = player.get("id")

        # 該玩家在戰鬥中施放過的技能集合
        cast_set = set()
        if player_casts and p_id is not None:
            cast_set = player_casts.get(p_id, set())

        for sid, spell in spell_db.items():
            s_class = spell.get("class", "")
            s_spec = spell.get("spec", "")
            s_type = spell.get("type", "")

            # 只選指定類型的 CD
            if s_type not in cd_types:
                continue

            # 匹配職業
            if s_class != p_class:
                continue

            # 匹配專精（"all" 表示任何專精都能用）
            if s_spec != "all" and s_spec != p_spec:
                continue

            # 天賦驗證：檢查該玩家是否實際施放過此技能
            if player_casts is not None and cast_set is not None:
                spell_id_int = int(sid)
                if spell_id_int not in cast_set:
                    skipped.append((p_name, spell["name"], sid))
                    continue

            role_tag = get_role_tag(p_class, p_spec)

            available_cds.append({
                "player": p_name,
                "role_tag": role_tag,
                "spell_id": sid,
                "spell_name": spell["name"],
                "cd_seconds": spell.get("cd", 180),
                "type": s_type,
            })

    if skipped:
        print(f"\n  Skipped (not cast / talent not selected):", file=sys.stderr)
        for name, sname, sid in skipped:
            print(f"    {name}: {sname} [{sid}]", file=sys.stderr)

    return available_cds


def schedule_cds(peaks: list, available_cds: list, pre_cast: float = 5.0,
                 fight_duration: float = 300.0):
    """貪心排程：為每個傷害峰值分配可用 CD。

    Args:
        peaks: [(center_sec, total_damage), ...] 按傷害量排序
        available_cds: 可用 CD 列表
        pre_cast: 提前幾秒開 CD
        fight_duration: 戰鬥持續時間

    回傳: [(cast_time_sec, player, role_tag, spell_id, spell_name, peak_damage), ...]
    """
    # 為每個 CD 建立狀態追蹤器
    # key: (player, spell_id), value: next_available_time
    cd_tracker = {}
    for cd in available_cds:
        key = (cd["player"], cd["spell_id"])
        cd_tracker[key] = 0.0  # 開戰即可用

    # 計算每個玩家同類 role_tag 的編號
    tag_counter = defaultdict(int)
    player_tags = {}
    for cd in available_cds:
        key = (cd["player"], cd["role_tag"])
        if key not in player_tags:
            tag_counter[cd["role_tag"]] += 1
            player_tags[key] = f"{cd['role_tag']}{tag_counter[cd['role_tag']]}"

    assignments = []

    # 按傷害量排序處理峰值（最大的優先分配 CD）
    for peak_time, peak_dmg in peaks:
        cast_time = max(0, peak_time - pre_cast)

        # 找出此時間點可用的 CD，優先 raid_cd > healing_cd
        candidates = []
        for cd in available_cds:
            key = (cd["player"], cd["spell_id"])
            if cd_tracker[key] <= cast_time:
                priority = 0 if cd["type"] == "raid_cd" else 1
                candidates.append((priority, cd["cd_seconds"], cd, key))

        # 按優先級排序：raid_cd 優先，同優先級中 CD 短的優先（可以多次使用）
        candidates.sort(key=lambda x: (x[0], x[1]))

        if candidates:
            _, _, best_cd, best_key = candidates[0]
            tag_key = (best_cd["player"], best_cd["role_tag"])
            role_tag = player_tags.get(tag_key, best_cd["role_tag"])

            assignments.append({
                "time": cast_time,
                "player": best_cd["player"],
                "role_tag": role_tag,
                "spell_id": best_cd["spell_id"],
                "spell_name": best_cd["spell_name"],
                "peak_damage": peak_dmg,
                "peak_time": peak_time,
            })

            # 更新 CD 追蹤器
            cd_tracker[best_key] = cast_time + best_cd["cd_seconds"]

    # 按時間排序
    assignments.sort(key=lambda x: x["time"])
    return assignments, player_tags


def format_time(seconds: float) -> str:
    """將秒數格式化為 MM:SS。"""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


def generate_stt(boss_name: str, report_code: str, fight_id: int,
                 assignments: list, player_tags: dict) -> str:
    """生成 STT 格式的時間軸。"""
    lines = []
    lines.append("[方案]")
    lines.append(f"名称={boss_name} - 自动减伤排程")
    lines.append(f"作者=auto ({report_code} #{fight_id})")
    lines.append("")

    # 人員區塊
    lines.append("[人员]")
    # 收集所有用到的 role_tag
    used_tags = set()
    for a in assignments:
        used_tags.add(a["role_tag"])
    # 按 tag 排序輸出
    tag_to_player = {}
    for (player, base_tag), full_tag in player_tags.items():
        if full_tag in used_tags:
            tag_to_player[full_tag] = player
    for tag in sorted(tag_to_player.keys()):
        lines.append(f"{tag}={tag_to_player[tag]}")
    lines.append("")

    # 時間軸
    lines.append("[时间轴]")
    lines.append("")
    for a in assignments:
        time_str = format_time(a["time"])
        lines.append(f"{{time:{time_str}}} {{{a['role_tag']}}}{{spell:{a['spell_id']}}}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="根據 WCL 團隊受傷數據自動排程減傷 CD，生成 STT 時間軸"
    )
    parser.add_argument("report", help="WCL report code 或完整 URL")
    parser.add_argument("fight_id", nargs="?", type=int, default=None,
                        help="Fight ID（可從 URL 自動解析）")
    parser.add_argument("-o", "--output", help="輸出檔案路徑")
    parser.add_argument("--top", type=int, default=15,
                        help="最多排程幾個傷害峰值（預設 15）")
    parser.add_argument("--window", type=int, default=5,
                        help="傷害聚合窗口秒數（預設 5）")
    parser.add_argument("--pre-cast", type=float, default=5.0,
                        help="提前幾秒開 CD（預設 5）")
    parser.add_argument("--types", default="raid_cd,healing_cd",
                        help="要納入排程的技能類型，逗號分隔（預設 raid_cd,healing_cd）")
    args = parser.parse_args()

    # 解析 report
    report_code, url_fight_id = parse_report_url(args.report)
    fight_id = args.fight_id or url_fight_id
    if fight_id is None:
        print("Error: fight_id is required (provide as argument or in URL #fight=N)", file=sys.stderr)
        sys.exit(1)

    cd_types = [t.strip() for t in args.types.split(",")]

    # 連接 API
    print("Connecting to Warcraft Logs API...", file=sys.stderr)
    token = get_token()

    # 取得戰鬥資訊和團隊組成
    print(f"Fetching fight #{fight_id} from {report_code}...", file=sys.stderr)
    fight, roster = get_fight_and_roster(token, report_code, fight_id)

    boss_name = fight["name"]
    start_time = fight["startTime"]
    end_time = fight["endTime"]
    duration = (end_time - start_time) / 1000

    print(f"  Boss: {boss_name}, Duration: {duration:.1f}s", file=sys.stderr)
    print(f"  Roster: {len(roster)} players", file=sys.stderr)

    # 顯示團隊組成
    class_spec_count = defaultdict(int)
    for p in roster:
        key = f"{p['type']}/{p['subType']}"
        class_spec_count[key] += 1
    for cs, count in sorted(class_spec_count.items()):
        print(f"    {cs}: {count}", file=sys.stderr)

    # 載入 spell_db
    spell_db = load_spell_db()
    if not spell_db:
        print("Error: spell_db.json not found or empty.", file=sys.stderr)
        sys.exit(1)

    # 取得玩家施放紀錄（用於天賦驗證）
    print(f"\nFetching player casts for talent validation...", file=sys.stderr)
    player_casts = fetch_player_casts(token, report_code, fight_id, start_time, end_time)
    print(f"  Collected casts from {len(player_casts)} sources", file=sys.stderr)

    # 匹配可用 CD（天賦驗證：只納入實際施放過的技能）
    available_cds = match_cds_to_roster(spell_db, roster, cd_types, player_casts)
    print(f"\n  Available CDs ({len(available_cds)} total):", file=sys.stderr)
    for cd in sorted(available_cds, key=lambda x: (x["role_tag"], x["spell_name"])):
        print(f"    {cd['player']} ({cd['role_tag']}): {cd['spell_name']} [{cd['spell_id']}] "
              f"CD={cd['cd_seconds']}s [{cd['type']}]", file=sys.stderr)

    if not available_cds:
        print("\nNo matching CDs found for this roster. Check spell_db.json.", file=sys.stderr)
        sys.exit(1)

    # 取得全團受傷事件
    print(f"\nFetching raid damage taken events...", file=sys.stderr)
    damage_events = fetch_damage_taken(token, report_code, fight_id, start_time, end_time)
    print(f"  Total damage events: {len(damage_events)}", file=sys.stderr)

    if not damage_events:
        print("No damage taken events found.", file=sys.stderr)
        sys.exit(1)

    # 計算總受傷量
    total_damage = sum(e.get("amount", 0) for e in damage_events)
    print(f"  Total damage taken: {total_damage:,.0f}", file=sys.stderr)

    # 找出傷害峰值
    peaks = find_damage_peaks(damage_events, start_time, end_time,
                              window_sec=args.window, top_n=args.top)
    print(f"\n  Top {len(peaks)} damage peaks ({args.window}s windows):", file=sys.stderr)
    for i, (center, dmg) in enumerate(sorted(peaks, key=lambda x: x[0])):
        pct = dmg / total_damage * 100
        print(f"    #{i+1} {format_time(center)}: {dmg:>12,.0f} ({pct:.1f}%)", file=sys.stderr)

    # 排程 CD
    print(f"\nScheduling CDs (pre-cast={args.pre_cast}s)...", file=sys.stderr)
    assignments, player_tags = schedule_cds(peaks, available_cds,
                                             pre_cast=args.pre_cast,
                                             fight_duration=duration)
    print(f"  Assigned {len(assignments)} CDs:", file=sys.stderr)
    for a in assignments:
        print(f"    {format_time(a['time'])} {a['role_tag']} → {a['spell_name']} "
              f"[{a['spell_id']}] (peak@{format_time(a['peak_time'])} "
              f"dmg={a['peak_damage']:,.0f})", file=sys.stderr)

    # 生成 STT
    output = generate_stt(boss_name, report_code, fight_id, assignments, player_tags)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\nSaved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
