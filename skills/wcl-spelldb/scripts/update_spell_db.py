#!/usr/bin/env python3
"""
update_spell_db.py — 更新 spell_db.json 中的技能資訊。

支援三種模式：
  1. 查詢單個 spell：從 Wowhead 取得資訊並新增/更新到 DB
  2. 批次刷新：重新驗證 DB 中所有 spell 的名稱和 CD
  3. 列出 DB 內容：按職業/類型分類顯示

用法:
    python update_spell_db.py add <spell_id> [--class CLASS] [--spec SPEC] [--role ROLE] [--type TYPE] [--note NOTE]
    python update_spell_db.py remove <spell_id>
    python update_spell_db.py refresh [--spell_id ID]
    python update_spell_db.py list [--class CLASS] [--type TYPE]
    python update_spell_db.py search <keyword>
"""

import argparse
import io
import json
import os
import re
import sys
import time

import requests

# Windows UTF-8 相容
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# spell_db.json 的路徑
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "..", "references", "spell_db.json")
DB_PATH = os.path.normpath(DB_PATH)

WOWHEAD_TOOLTIP_URL = "https://nether.wowhead.com/tooltip/spell/{spell_id}"
WOWHEAD_SPELL_URL = "https://www.wowhead.com/spell={spell_id}"

# Wowhead class/spec 映射（用於從 tooltip 解析）
CLASS_COLORS = {
    "Death Knight": "#C41E3A", "Demon Hunter": "#A330C9", "Druid": "#FF7C0A",
    "Evoker": "#33937F", "Hunter": "#AAD372", "Mage": "#3FC7EB",
    "Monk": "#00FF98", "Paladin": "#F48CBA", "Priest": "#FFFFFF",
    "Rogue": "#FFF468", "Shaman": "#0070DD", "Warlock": "#8788EE",
    "Warrior": "#C69B6D",
}


def load_db() -> dict:
    """載入 spell_db.json。"""
    if not os.path.exists(DB_PATH):
        return {
            "_meta": {
                "patch": "12.1",
                "game_version": "The War Within Season 2",
                "updated": time.strftime("%Y-%m-%d"),
                "note": "Healer major CDs + common raid utility. Use /wcl-spelldb to update."
            },
            "spells": {}
        }
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db: dict):
    """儲存 spell_db.json。"""
    db["_meta"]["updated"] = time.strftime("%Y-%m-%d")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print(f"Saved to {DB_PATH}")


def fetch_wowhead_tooltip(spell_id: int) -> dict | None:
    """從 Wowhead tooltip API 取得技能基本資訊。"""
    url = WOWHEAD_TOOLTIP_URL.format(spell_id=spell_id)
    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  Warning: Failed to fetch Wowhead data for spell {spell_id}: {e}", file=sys.stderr)
        return None


def parse_tooltip(data: dict, spell_id: int) -> dict:
    """從 Wowhead tooltip 回應中解析技能資訊。"""
    info = {
        "name": data.get("name", f"Unknown-{spell_id}"),
        "cd": 0,
    }

    tooltip_html = data.get("tooltip", "")

    # 嘗試從 tooltip 中解析 CD
    # 常見格式: "X sec cooldown", "X min cooldown"
    cd_match = re.search(r"(\d+(?:\.\d+)?)\s*min(?:ute)?\s*cooldown", tooltip_html, re.IGNORECASE)
    if cd_match:
        info["cd"] = int(float(cd_match.group(1)) * 60)
    else:
        cd_match = re.search(r"(\d+(?:\.\d+)?)\s*sec(?:ond)?\s*cooldown", tooltip_html, re.IGNORECASE)
        if cd_match:
            info["cd"] = int(float(cd_match.group(1)))

    return info


def fetch_spell_info(spell_id: int) -> dict | None:
    """取得指定 spell ID 的完整資訊。"""
    print(f"  Fetching spell {spell_id} from Wowhead...", file=sys.stderr)
    data = fetch_wowhead_tooltip(spell_id)
    if data is None:
        print(f"  Spell {spell_id} not found on Wowhead.", file=sys.stderr)
        return None

    info = parse_tooltip(data, spell_id)
    print(f"  Found: {info['name']} (CD: {info['cd']}s)", file=sys.stderr)
    return info


def cmd_add(args):
    """新增或更新一個 spell 到 DB。"""
    db = load_db()
    spell_id = str(args.spell_id)

    # 先從 Wowhead 查詢基本資訊
    wh_info = fetch_spell_info(int(spell_id))

    existing = db["spells"].get(spell_id, {})
    entry = {
        "name": wh_info["name"] if wh_info else existing.get("name", f"Unknown-{spell_id}"),
        "class": args.cls or existing.get("class", "Unknown"),
        "spec": args.spec or existing.get("spec", "Unknown"),
        "role": args.role or existing.get("role", "healer"),
        "cd": wh_info["cd"] if (wh_info and wh_info["cd"] > 0) else existing.get("cd", 0),
        "type": args.type or existing.get("type", "healing_cd"),
        "note": args.note or existing.get("note", ""),
    }

    # 允許使用者覆蓋 CD
    if args.cd is not None:
        entry["cd"] = args.cd

    # 允許使用者覆蓋名稱
    if args.name:
        entry["name"] = args.name

    action = "Updated" if spell_id in db["spells"] else "Added"
    db["spells"][spell_id] = entry
    save_db(db)
    print(f"{action} [{spell_id}] {entry['name']} ({entry['class']}/{entry['spec']}, CD={entry['cd']}s)")


def cmd_remove(args):
    """從 DB 移除一個 spell。"""
    db = load_db()
    spell_id = str(args.spell_id)
    if spell_id in db["spells"]:
        removed = db["spells"].pop(spell_id)
        save_db(db)
        print(f"Removed [{spell_id}] {removed['name']}")
    else:
        print(f"Spell {spell_id} not found in DB.")


def cmd_refresh(args):
    """從 Wowhead 重新驗證 DB 中技能的名稱和 CD。"""
    db = load_db()

    if args.spell_id:
        # 只刷新指定的 spell
        targets = {str(args.spell_id): db["spells"].get(str(args.spell_id))}
        if targets[str(args.spell_id)] is None:
            print(f"Spell {args.spell_id} not found in DB.")
            return
    else:
        targets = db["spells"]

    updated_count = 0
    for sid, entry in targets.items():
        wh_info = fetch_spell_info(int(sid))
        if wh_info is None:
            print(f"  [{sid}] {entry['name']} — Wowhead returned nothing, skipping")
            continue

        changes = []
        if wh_info["name"] != entry["name"]:
            changes.append(f"name: {entry['name']} → {wh_info['name']}")
            entry["name"] = wh_info["name"]
        if wh_info["cd"] > 0 and wh_info["cd"] != entry.get("cd", 0):
            changes.append(f"cd: {entry.get('cd', 0)}s → {wh_info['cd']}s")
            entry["cd"] = wh_info["cd"]

        if changes:
            print(f"  [{sid}] {entry['name']} — {', '.join(changes)}")
            updated_count += 1
        else:
            print(f"  [{sid}] {entry['name']} — no changes")

        # 避免太頻繁請求
        time.sleep(0.3)

    if updated_count > 0:
        save_db(db)
        print(f"\nRefreshed {updated_count} spell(s).")
    else:
        print("\nNo changes detected.")


def cmd_list(args):
    """列出 DB 中的技能。"""
    db = load_db()
    spells = db["spells"]

    # 篩選
    filtered = {}
    for sid, entry in spells.items():
        if args.cls and entry.get("class", "").lower() != args.cls.lower():
            continue
        if args.type and entry.get("type", "") != args.type:
            continue
        if args.spec and entry.get("spec", "").lower() != args.spec.lower():
            continue
        filtered[sid] = entry

    if not filtered:
        print("No spells match the filter.")
        return

    # 按 class → type → name 排序
    sorted_spells = sorted(filtered.items(),
                           key=lambda x: (x[1].get("class", ""), x[1].get("type", ""), x[1].get("name", "")))

    current_class = None
    print(f"\n{'ID':>8}  {'CD':>5}  {'Type':<15}  {'Name':<40}  {'Spec':<15}  Note")
    print("-" * 110)
    for sid, entry in sorted_spells:
        cls = entry.get("class", "Unknown")
        if cls != current_class:
            current_class = cls
            print(f"\n  [{cls}]")
        cd_str = f"{entry.get('cd', 0)}s" if entry.get('cd', 0) > 0 else "-"
        print(f"{sid:>8}  {cd_str:>5}  {entry.get('type', ''):.<15}  "
              f"{entry.get('name', ''):.<40}  {entry.get('spec', ''):.<15}  {entry.get('note', '')}")

    print(f"\nTotal: {len(filtered)} spell(s)")
    print(f"DB path: {DB_PATH}")


def cmd_search(args):
    """搜尋 DB 中的技能（名稱模糊匹配）。"""
    db = load_db()
    keyword = args.keyword.lower()

    results = []
    for sid, entry in db["spells"].items():
        if (keyword in entry.get("name", "").lower()
                or keyword in entry.get("class", "").lower()
                or keyword in entry.get("spec", "").lower()
                or keyword in entry.get("note", "").lower()
                or keyword in sid):
            results.append((sid, entry))

    if not results:
        print(f"No spells matching '{args.keyword}'.")
        return

    print(f"\nFound {len(results)} spell(s) matching '{args.keyword}':\n")
    for sid, entry in sorted(results, key=lambda x: x[1].get("name", "")):
        cd_str = f"{entry.get('cd', 0)}s" if entry.get('cd', 0) > 0 else "-"
        print(f"  [{sid}] {entry.get('name', '')} — {entry.get('class', '')}/{entry.get('spec', '')} "
              f"CD={cd_str} type={entry.get('type', '')} | {entry.get('note', '')}")


def main():
    parser = argparse.ArgumentParser(description="管理 spell_db.json 技能資料庫")
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="新增或更新一個技能")
    p_add.add_argument("spell_id", type=int, help="Spell ID")
    p_add.add_argument("--name", help="覆蓋技能名稱")
    p_add.add_argument("--class", dest="cls", help="職業名 (e.g., Monk, Priest)")
    p_add.add_argument("--spec", help="專精名 (e.g., Mistweaver, Holy)")
    p_add.add_argument("--role", help="角色定位 (healer/utility/defensive/dps)")
    p_add.add_argument("--cd", type=int, help="覆蓋 CD 秒數")
    p_add.add_argument("--type", help="技能類型 (healing_cd/raid_cd/external_dr/personal_dr/utility/damage/raid_buff)")
    p_add.add_argument("--note", help="備註說明")

    # remove
    p_rm = sub.add_parser("remove", help="移除一個技能")
    p_rm.add_argument("spell_id", type=int, help="Spell ID")

    # refresh
    p_ref = sub.add_parser("refresh", help="從 Wowhead 重新驗證技能資訊")
    p_ref.add_argument("--spell_id", type=int, help="只刷新指定 spell（不指定則全部刷新）")

    # list
    p_list = sub.add_parser("list", help="列出資料庫中的技能")
    p_list.add_argument("--class", dest="cls", help="篩選職業")
    p_list.add_argument("--spec", help="篩選專精")
    p_list.add_argument("--type", help="篩選類型")

    # search
    p_search = sub.add_parser("search", help="搜尋技能")
    p_search.add_argument("keyword", help="搜尋關鍵字")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args)
    elif args.command == "remove":
        cmd_remove(args)
    elif args.command == "refresh":
        cmd_refresh(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "search":
        cmd_search(args)


if __name__ == "__main__":
    main()
