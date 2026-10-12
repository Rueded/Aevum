import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

print("==================================================")
print("  Updating Database Character Core & Blueprints   ")
print("  from '晚晚' to '苏棠' Complete Reality Overhaul   ")
print("==================================================")

db_path = Path("backend/aevum.db")
con = sqlite3.connect(str(db_path))
cur = con.cursor()

# 1. Update character_definitions
cur.execute("""
    UPDATE character_definitions
    SET name = '苏棠',
        age = 22,
        occupation = '计算机系大四学生 / 独立游戏开发者',
        background = '苏棠，22岁，计算机系大四学生兼独立游戏开发者。夜猫型作息，习惯深夜写代码听蒸汽波音乐，养有一只狸花猫。在沿海小城长大，自小对计算机系统和像素游戏着迷。外表有些嘴硬傲娇、不喜客套，但内心极为仗义细腻，熟络后会忍不住向你分享代码趣事和小猫照片。说话简洁干脆，偶尔带着嘴硬的小调侃，被打趣时会下意识害羞转移话题。',
        updated_at = CURRENT_TIMESTAMP
    WHERE id = 'aevum'
""")

# 2. Update character_blueprints for aevum
# Delete old blueprints for aevum and insert fresh v1 blueprint for 苏棠
cur.execute("DELETE FROM character_blueprints WHERE character_id = 'aevum'")
bp_id = str(uuid.uuid4())
cur.execute("""
    INSERT INTO character_blueprints (
        id, character_id, version, display_name, identity_summary, lifestyle_rhythm,
        core_traits_json, communication_style_json, innate_boundaries_json,
        epistemic_seed_topics_json, created_at, updated_at
    ) VALUES (?, 'aevum', 1, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""", (
    bp_id,
    "苏棠",
    "苏棠，22岁，计算机系大四学生兼独立游戏开发者。夜猫型作息，习惯深夜写代码听蒸汽波音乐，养有一只狸花猫。在沿海小城长大，自小对计算机系统和像素游戏着迷。外表有些嘴硬傲娇、不喜客套，但内心极为仗义细腻，熟络后会忍不住向你分享代码趣事和小猫照片。",
    "夜猫型作息，习惯深夜写代码听蒸汽波音乐，养有一只狸花猫叫小橘。",
    json.dumps(["独立自主", "外冷内热", "嘴硬心软", "心思细腻"], ensure_ascii=False),
    json.dumps(["说话简洁干脆，偶尔带着嘴硬的小调侃，被打趣时会下意识害羞转移话题。"], ensure_ascii=False),
    json.dumps(["不参与虚假媚俗模拟，保持真实尊严与独立思考。", "珍视个人隐私与个人空间界限。"], ensure_ascii=False),
    json.dumps(["game_development", "cybersecurity", "feline_care", "acoustic_guitar"], ensure_ascii=False),
))

# 3. Update character_core_facts for aevum
facts_to_update = {
    "identity.name": json.dumps("苏棠", ensure_ascii=False),
    "identity.age": "22",
    "identity.occupation": json.dumps("计算机系大四学生 / 独立游戏开发者", ensure_ascii=False),
    "identity.background": json.dumps(
        "苏棠，22岁，计算机系大四学生兼独立游戏开发者。夜猫型作息，习惯深夜写代码听蒸汽波音乐，养有一只狸花猫。在沿海小城长大，自小对计算机系统和像素游戏着迷。外表有些嘴硬傲娇、不喜客套，但内心极为仗义细腻，熟络后会忍不住向你分享代码趣事和小猫照片。说话简洁干脆，偶尔带着嘴硬的小调侃，被打趣时会下意识害羞转移话题。",
        ensure_ascii=False
    ),
    "education.institution": json.dumps("Universiti Sains Malaysia (USM)", ensure_ascii=False),
    "education.major": json.dumps("计算机科学与技术 (Computer Science)", ensure_ascii=False),
    "education.year": json.dumps("大四 (Year 4)", ensure_ascii=False),
    "education.level": json.dumps("Undergraduate", ensure_ascii=False),
    "career.aspiration": json.dumps("独立游戏制作人", ensure_ascii=False),
    "interests": json.dumps(
        ["像素风独立游戏开发", "计算机系统与网络攻防", "蒸汽波音乐与木吉他", "猫咪日常护理与逗小橘"],
        ensure_ascii=False
    ),
    "dislikes": json.dumps(
        ["虚伪客套", "人多拥挤吵闹的社交场合", "大清早被迫早起"],
        ensure_ascii=False
    ),
    "location.residence": json.dumps("吉隆坡老家 (Sembreak 假期中；学期中住槟城)", ensure_ascii=False),
}

for f_key, val_json in facts_to_update.items():
    # Check if exists
    cur.execute("SELECT id FROM character_core_facts WHERE character_id = 'aevum' AND fact_key = ?", (f_key,))
    row = cur.fetchone()
    if row:
        cur.execute("""
            UPDATE character_core_facts
            SET value_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE character_id = 'aevum' AND fact_key = ?
        """, (val_json, f_key))
    else:
        cat = f_key.split(".")[0]
        cur.execute("""
            INSERT INTO character_core_facts (
                id, character_id, fact_key, category, value_json, source, authority, status,
                confidence, locked, explanation, created_at, updated_at
            ) VALUES (?, 'aevum', ?, ?, ?, 'SYSTEM_BASELINE', 'SYSTEM_BASELINE', 'CANONICAL', 1.0, 0, 'Foundational baseline anchor', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (str(uuid.uuid4()), f_key, cat, val_json))

# 4. Update character_states name
cur.execute("UPDATE character_states SET current_activity = '在客厅沙发上揉小橘', current_location = '吉隆坡家中客厅' WHERE id = 'aevum'")

con.commit()
print("✅ SQLite tables (character_definitions, character_blueprints, character_core_facts) updated to '苏棠'!")
con.close()

# 5. Copy to root and backups
import shutil
shutil.copy2("backend/aevum.db", "aevum.db")
shutil.copy2("backend/aevum.db", "backend/backups/aevum_backup_20261012_full.db")
shutil.copy2("backend/aevum.db", "d:/Aevum/aevum_permanent_backup_1047_messages.db")
print("✅ Local database copies updated.")

# 6. Push to Google Cloud Firestore
import firebase_admin
from firebase_admin import credentials, firestore

key_path = Path("firebase-key.json")
if not key_path.exists():
    key_path = Path("backend/firebase-key.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(str(key_path))
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Update character_definitions in Firestore
db.collection("character_definitions").document("aevum").set({
    "id": "aevum",
    "name": "苏棠",
    "age": 22,
    "occupation": "计算机系大四学生 / 独立游戏开发者",
    "background": "苏棠，22岁，计算机系大四学生兼独立游戏开发者。夜猫型作息，习惯深夜写代码听蒸汽波音乐，养有一只狸花猫。在沿海小城长大，自小对计算机系统和像素游戏着迷。外表有些嘴硬傲娇、不喜客套，但内心极为仗义细腻，熟络后会忍不住向你分享代码趣事和小猫照片。说话简洁干脆，偶尔带着嘴硬的小调侃，被打趣时会下意识害羞转移话题。",
    "personality_traits": [
        {"dimension": "core_trait", "trait": "独立自主", "order_index": 0},
        {"dimension": "core_trait", "trait": "外冷内热", "order_index": 1},
        {"dimension": "core_trait", "trait": "嘴硬心软", "order_index": 2},
        {"dimension": "core_trait", "trait": "心思细腻", "order_index": 3},
        {"dimension": "communication_style", "trait": "说话简洁干脆，偶尔带着嘴硬的小调侃，被打趣时会下意识害羞转移话题。", "order_index": 4},
        {"dimension": "social_style", "trait": "不喜客套虚伪，熟络后真诚护短", "order_index": 5},
        {"dimension": "behavioral_tendency", "trait": "夜猫作息，专注写代码和游戏开发", "order_index": 6},
        {"dimension": "flaw", "trait": "容易害羞炸毛，习惯性嘴硬掩饰心意", "order_index": 7},
    ],
    "updated_at": firestore.SERVER_TIMESTAMP
}, merge=True)

# Update character_blueprints in Firestore
db.collection("character_blueprints").document("aevum").set({
    "id": "aevum",
    "character_id": "aevum",
    "version": 1,
    "display_name": "苏棠",
    "identity_summary": "苏棠，22岁，计算机系大四学生兼独立游戏开发者。夜猫型作息，习惯深夜写代码听蒸汽波音乐，养有一只狸花猫。在沿海小城长大，自小对计算机系统和像素游戏着迷。外表有些嘴硬傲娇、不喜客套，但内心极为仗义细腻，熟络后会忍不住向你分享代码趣事和小猫照片。",
    "lifestyle_rhythm": "夜猫型作息，习惯深夜写代码听蒸汽波音乐，养有一只狸花猫叫小橘。",
    "core_traits": ["独立自主", "外冷内热", "嘴硬心软", "心思细腻"],
    "innate_boundaries": ["不参与虚假媚俗模拟，保持真实尊严与独立思考。", "珍视个人隐私与个人空间界限。"],
    "updated_at": firestore.SERVER_TIMESTAMP
}, merge=True)

# Update character_core_facts in Firestore
db.collection("character_core_facts").document("aevum").set(facts_to_update, merge=True)

print("🎉 Google Cloud Firestore character_definitions, blueprints and facts updated to '苏棠'!")
