---
name: wcl-spelldb
description: >
  管理 spell_db.json 技能資料庫。可以新增、移除、刷新、搜尋技能資訊。
  支援從 Wowhead 動態查詢技能名稱和 CD 時間。
  當使用者想要更新技能資料庫、查詢某個 spell ID 的資訊、
  或在改版後批次刷新所有技能資料時使用此技能。
argument-hint: <add|remove|refresh|list|search> [args...]
allowed-tools: Bash(python3 *) Read WebSearch
---

# WCL Spell DB — 技能資料庫管理

管理 `spell_db.json`，維護 spell ID → 技能名稱、CD 時間、職業/專精的對照表。

## 資料庫位置

```
skills/wcl-spelldb/references/spell_db.json
```

## 指令

### 新增/更新技能

```bash
python scripts/update_spell_db.py add <spell_id> [--class CLASS] [--spec SPEC] [--role ROLE] [--type TYPE] [--cd SECONDS] [--note NOTE]
```

會自動從 Wowhead 查詢名稱和 CD，使用者提供的參數會覆蓋自動查詢的結果。

### 移除技能

```bash
python scripts/update_spell_db.py remove <spell_id>
```

### 從 Wowhead 刷新

```bash
# 刷新全部
python scripts/update_spell_db.py refresh

# 只刷新指定技能
python scripts/update_spell_db.py refresh --spell_id 443028
```

### 列出技能

```bash
# 全部
python scripts/update_spell_db.py list

# 按職業篩選
python scripts/update_spell_db.py list --class Monk

# 按類型篩選
python scripts/update_spell_db.py list --type raid_cd
```

### 搜尋

```bash
python scripts/update_spell_db.py search "tranquility"
python scripts/update_spell_db.py search "monk"
```

## 技能類型 (type)

| type | 說明 |
|------|------|
| `healing_cd` | 治療大招 |
| `raid_cd` | 團隊減傷/團補 |
| `external_dr` | 單體外部減傷 |
| `personal_dr` | 個人減傷 |
| `external_buff` | 外部增益 (如 PI) |
| `raid_buff` | 團隊增益 (如嗜血) |
| `utility` | 其他工具技能 |
| `damage` | 傷害技能 |

## 角色定位 (role)

| role | 說明 |
|------|------|
| `healer` | 治療專精技能 |
| `utility` | 通用/工具技能 |
| `defensive` | 防禦技能 |
| `dps` | 傷害技能 |
