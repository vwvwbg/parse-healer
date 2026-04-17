---
name: wcl-timeline
description: >
  從 Warcraft Logs 報告中提取指定玩家的特定技能施放時間，
  並生成 STT (ShengTangTools) 格式的時間軸方案。
  也可根據團隊受傷數據自動偵測高傷害時段，結合團隊組成和 spell_db.json
  自動排程減傷/治療 CD 並生成 STT 時間軸。
  Mode 1: 使用者提供 WCL 報告、玩家名稱、技能時使用。
  Mode 2: 使用者只提供 WCL 報告和 fight ID，要求自動排減傷/排 CD 時使用。
argument-hint: <report_url_or_code> <fight_id> [<player_name> "<spells>" | --auto-cd]
allowed-tools: Bash(python3 *) Read
---

# WCL Timeline — STT 時間軸生成器

兩種模式：追蹤特定玩家技能 (Mode 1) 或自動排程全團減傷 CD (Mode 2)。

---

## Mode 1: 玩家技能時間軸

從 WCL 報告中提取指定玩家的技能施放時間點，生成 STT 格式時間軸。

### 使用方式

```
/wcl-timeline <report_url_or_code> <fight_id> <player_name> "<spell_names_or_ids>" [--role-tag 標籤]
```

### 參數說明

| 參數 | 必填 | 說明 |
|------|------|------|
| `report_url_or_code` | ✅ | WCL 報告的完整 URL 或 report code |
| `fight_id` | ✅ | 戰鬥 ID（從 URL 的 `#fight=N` 取得） |
| `player_name` | ✅ | 玩家角色名稱 |
| `spells` | ✅ | 要追蹤的技能，逗號分隔。支援技能名稱（英文）或 spell ID |
| `--role-tag` | ❌ | STT 方案中的角色標籤（如「織霧1」「奶德1」），預設使用玩家名 |

### 範例

```bash
python3 "$SCRIPTS_DIR/wcl_timeline.py" arw7HCtQWfxpALjz 5 Rathuxmk "Celestial Conduit,Restoral" --role-tag 织雾1 -o stt/stt_timeline.txt
```

### 技能篩選邏輯

- **純數字** → 視為 spell ID，精確匹配 `ability.guid`
- **文字** → 視為技能名稱，忽略大小寫匹配 `ability.name`
- 支援含逗號的技能名（如 `Invoke Yu'lon, the Jade Serpent`），小寫開頭的片段會自動合併
- 找不到匹配時會列出該玩家所有可用技能供參考

### Execution Steps (Mode 1)

1. Parse report code, fight ID, player name, spell filters, optional role-tag from user input.
2. Run:
   ```bash
   python3 "$SCRIPTS_DIR/wcl_timeline.py" "<report>" <fight_id> "<player>" "<spells>" --role-tag <tag> -o stt/stt_timeline.txt
   ```
3. Present: matched spell count, STT timeline content, usage instructions.
4. If no spells matched, show available spells and help user pick correct names/IDs.

---

## Mode 2: 自動減傷排程 (Raid CD Scheduler)

根據 WCL 團隊受傷數據，自動偵測高傷害時段，結合團隊組成和 `spell_db.json` 自動排程減傷/治療 CD。

**When to use**: User asks to "自動排減傷", "幫我排 CD", provides only report + fight_id without player/spells, or mentions "damage taken" / "團隊受傷".

### 使用方式

```
/wcl-timeline <report_url_or_code> <fight_id> [--top N] [--pre-cast SEC] [--types raid_cd,healing_cd]
```

### 參數說明

| 參數 | 必填 | 說明 |
|------|------|------|
| `report_url_or_code` | ✅ | WCL 報告的完整 URL 或 report code |
| `fight_id` | ✅ | 戰鬥 ID |
| `--top` | ❌ | 最多排幾個傷害峰值（預設 15） |
| `--pre-cast` | ❌ | 提前幾秒開 CD（預設 5） |
| `--types` | ❌ | 納入排程的技能類型，逗號分隔（預設 `raid_cd,healing_cd`） |

### 範例

```bash
python3 "$SCRIPTS_DIR/wcl_raid_cd.py" dkrhX9tJDmqAzFRB 21 --top 15 -o stt/stt_raid_cd.txt
```

### 排程邏輯

1. **偵測團隊組成** — 從 WCL `playerDetails` 取得每個玩家的職業/專精
2. **天賦驗證** — 從戰鬥施放記錄確認每個玩家實際擁有哪些 CD（排除未點天賦的技能）
3. **傷害分析** — 全團 DamageTaken 事件以 5 秒滑動窗口聚合，找出最高傷害峰值
4. **貪心排程** — 按傷害量排序，依序分配可用 CD（raid_cd 優先於 healing_cd，短 CD 優先以便多次使用）
5. **CD 追蹤** — 確保每個技能不會在冷卻中被重複分配

### Execution Steps (Mode 2)

1. Parse report code and fight ID from user input.
2. Run:
   ```bash
   python3 "$SCRIPTS_DIR/wcl_raid_cd.py" "<report>" <fight_id> --top <N> -o stt/stt_raid_cd.txt
   ```
3. Present to the user:
   - **團隊組成** — detected class/spec breakdown
   - **可用 CD** — matched spells from spell_db.json (after talent validation)
   - **被排除的技能** — spells skipped because the player didn't cast them (talent not selected)
   - **傷害峰值** — top N damage windows with timestamps and amounts
   - **排程結果** — each CD assignment with time, player, spell, and target peak
   - **STT 時間軸** — complete plan ready to paste into STT plugin

---

## Scripts

```bash
SCRIPTS_DIR="${CLAUDE_SKILL_DIR}/scripts"
```

| Script | Purpose |
|--------|---------|
| `wcl_timeline.py` | Mode 1: player spell cast timeline |
| `wcl_raid_cd.py` | Mode 2: auto raid CD scheduling |

Both depend on `skills/wcl-compare/scripts/wcl_client.py` for WCL API auth.

## Output

All STT output goes to `stt/` directory at project root. Format reference: `skills/wcl-timeline/references/stt.md`

Key STT syntax:
- `{time:MM:SS}` — time after pull
- `{spell:ID}` — auto-resolves to in-game spell name
- `{角色標籤}` — maps to player name via `[人员]` block
