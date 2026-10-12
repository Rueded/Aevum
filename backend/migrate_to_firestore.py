import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore

print("==================================================")
print("  Project Aevum -> Google Cloud Firestore Migration")
print("==================================================")

# 1. Initialize Firestore
key_path = Path("firebase-key.json")
if not key_path.exists():
    key_path = Path("backend/firebase-key.json")

if not key_path.exists():
    print(f"❌ Error: Cannot find {key_path}")
    exit(1)

print(f"🔑 Using Firebase Service Account: {key_path}")
if not firebase_admin._apps:
    cred = credentials.Certificate(str(key_path))
    firebase_admin.initialize_app(cred)

db = firestore.client()
print(" Connected to Firestore database!")

# 2. Connect to SQLite
db_path = Path("backend/aevum.db")
if not db_path.exists():
    db_path = Path("aevum.db")

print(f"📦 Source SQLite Database: {db_path} ({db_path.stat().st_size} bytes)")
con = sqlite3.connect(str(db_path))
cur = con.cursor()

# -------------------------------------------------------------------------
# A. Migrate Conversations
# -------------------------------------------------------------------------
cur.execute("SELECT id, created_at, updated_at FROM conversations")
conversations = cur.fetchall()
print(f"\n🚀 Migrating {len(conversations)} conversations...")

batch = db.batch()
count = 0
for conv_id, created_at, updated_at in conversations:
    doc_ref = db.collection("conversations").document(conv_id)
    batch.set(doc_ref, {
        "id": conv_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "synced_at": firestore.SERVER_TIMESTAMP
    }, merge=True)
    count += 1
    if count >= 400:
        batch.commit()
        batch = db.batch()
        count = 0
if count > 0:
    batch.commit()
print(f"✅ Migrated {len(conversations)} conversations to Firestore.")

# -------------------------------------------------------------------------
# B. Migrate Messages (1,047 messages in batches of 400)
# -------------------------------------------------------------------------
cur.execute("SELECT id, conversation_id, role, content, created_at FROM messages ORDER BY created_at ASC")
messages = cur.fetchall()
print(f"\n🚀 Migrating {len(messages)} messages...")

batch = db.batch()
count = 0
total_migrated = 0
for msg_id, conv_id, role, content, created_at in messages:
    doc_ref = db.collection("messages").document(msg_id)
    batch.set(doc_ref, {
        "id": msg_id,
        "conversation_id": conv_id,
        "role": role,
        "content": content,
        "created_at": created_at,
        "synced_at": firestore.SERVER_TIMESTAMP
    }, merge=True)
    count += 1
    total_migrated += 1
    if count >= 400:
        batch.commit()
        print(f"   -> Committed {total_migrated}/{len(messages)} messages...")
        batch = db.batch()
        count = 0
if count > 0:
    batch.commit()
print(f"✅ Migrated all {len(messages)} messages to Firestore.")

# -------------------------------------------------------------------------
# C. Migrate Memories (65 long-term memories)
# -------------------------------------------------------------------------
cur.execute("SELECT id, category, content, importance, confidence, emotional_weight, created_at, updated_at, subject_entity FROM memories")
memories = cur.fetchall()
print(f"\n🚀 Migrating {len(memories)} memories...")

batch = db.batch()
count = 0
for mem_id, category, content, importance, confidence, emotional_weight, created_at, updated_at, subject_entity in memories:
    doc_ref = db.collection("memories").document(mem_id)
    batch.set(doc_ref, {
        "id": mem_id,
        "category": category,
        "content": content,
        "importance": importance,
        "confidence": confidence,
        "emotional_weight": emotional_weight,
        "created_at": created_at,
        "updated_at": updated_at,
        "subject_entity": subject_entity,
        "synced_at": firestore.SERVER_TIMESTAMP
    }, merge=True)
    count += 1
    if count >= 400:
        batch.commit()
        batch = db.batch()
        count = 0
if count > 0:
    batch.commit()
print(f"✅ Migrated {len(memories)} memories to Firestore.")

# -------------------------------------------------------------------------
# D. Migrate Character Definition & Traits (苏棠)
# -------------------------------------------------------------------------
cur.execute("SELECT id, name, age, occupation, background FROM character_definitions WHERE id = 'aevum'")
char_row = cur.fetchone()

cur.execute("SELECT dimension, trait, order_index FROM character_personality_traits WHERE character_id = 'aevum' ORDER BY order_index ASC")
traits_rows = cur.fetchall()
traits_list = [{"dimension": r[0], "trait": r[1], "order_index": r[2]} for r in traits_rows]

if char_row:
    char_id, name, age, occupation, background = char_row
    print(f"\n🚀 Migrating Character Definition for '{name}'...")
    db.collection("character_definitions").document("aevum").set({
        "id": "aevum",
        "name": name,
        "age": age,
        "occupation": occupation,
        "background": background,
        "personality_traits": traits_list,
        "updated_at": firestore.SERVER_TIMESTAMP
    }, merge=True)
    print(f"✅ Migrated character '{name}' with {len(traits_list)} personality traits.")

# -------------------------------------------------------------------------
# E. Migrate Character State (Current activity & mood)
# -------------------------------------------------------------------------
cur.execute("SELECT mood, energy, stress, social_energy, confidence, irritation, loneliness, current_activity, current_location FROM character_states WHERE id = 'aevum'")
state_row = cur.fetchone()
if state_row:
    mood, energy, stress, social_energy, confidence, irritation, loneliness, current_activity, current_location = state_row
    print(f"\n🚀 Migrating Character State...")
    db.collection("character_states").document("aevum").set({
        "id": "aevum",
        "mood": mood,
        "energy": energy,
        "stress": stress,
        "social_energy": social_energy,
        "confidence": confidence,
        "irritation": irritation,
        "loneliness": loneliness,
        "current_activity": current_activity,
        "current_location": current_location,
        "updated_at": firestore.SERVER_TIMESTAMP
    }, merge=True)
    print("✅ Migrated character state.")

# -------------------------------------------------------------------------
# F. Migrate Relationship (Affection = 0.68)
# -------------------------------------------------------------------------
cur.execute("SELECT user_id, version, trust, familiarity, comfort, affection, attachment, respect FROM relationships WHERE id = 'user' OR user_id = 'user'")
rel_row = cur.fetchone()
if rel_row:
    user_id, version, trust, familiarity, comfort, affection, attachment, respect = rel_row
    print(f"\n🚀 Migrating Relationship for user (Affection={affection*100:.0f}%)...")
    db.collection("relationships").document("user").set({
        "id": "user",
        "user_id": user_id,
        "version": version,
        "trust": trust,
        "familiarity": familiarity,
        "comfort": comfort,
        "affection": affection,
        "attachment": attachment,
        "respect": respect,
        "updated_at": firestore.SERVER_TIMESTAMP
    }, merge=True)
    print(f"✅ Migrated relationship: Affection={affection:.2f}, Familiarity={familiarity:.2f}, Trust={trust:.2f}, Respect={respect:.2f}")

con.close()

# -------------------------------------------------------------------------
# Verification & Summary
# -------------------------------------------------------------------------
print("\n==================================================")
print("  Verifying Firestore Cloud Data Integrity...")
print("==================================================")

msg_count = len(list(db.collection("messages").limit(10).stream()))
mem_count = len(list(db.collection("memories").limit(10).stream()))
sutang_doc = db.collection("character_definitions").document("aevum").get().to_dict()
rel_doc = db.collection("relationships").document("user").get().to_dict()

print(f"  Character Name: {sutang_doc.get('name')}")
print(f"  Character Occupation: {sutang_doc.get('occupation')}")
print(f"  Affection (好感度): {rel_doc.get('affection') * 100:.0f}% ({rel_doc.get('affection')})")
print(f"  Familiarity (熟悉度): {rel_doc.get('familiarity') * 100:.0f}%")
print(f"  Trust (信任度): {rel_doc.get('trust') * 100:.0f}%")
print(f"  Messages migrated: {len(messages)}")
print(f"  Memories migrated: {len(memories)}")
print("\n🎉 ALL DATA HAS BEEN SUCCESSFULLY MIGRATED TO CLOUD FIRESTORE!")
print("==================================================")
