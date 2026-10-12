import sqlite3

con = sqlite3.connect("backend/aevum.db")
cur = con.cursor()

print("--- character_blueprints columns ---")
cur.execute("PRAGMA table_info(character_blueprints)")
print([c[1] for c in cur.fetchall()])

print("\n--- character_blueprints for aevum or latest ---")
cur.execute("SELECT * FROM character_blueprints WHERE character_id = 'aevum'")
rows = cur.fetchall()
print(f"aevum blueprints ({len(rows)}):")
for r in rows:
    print(r)

print("\n--- character_core_facts for aevum ---")
cur.execute("SELECT fact_key, value_json FROM character_core_facts WHERE character_id = 'aevum'")
for r in cur.fetchall():
    print(r[0], ":", r[1])

print("\n--- character_definitions for aevum ---")
cur.execute("SELECT * FROM character_definitions WHERE id = 'aevum'")
for r in cur.fetchall():
    print(r)

print("\n--- prompt_assembler check ---")
con.close()
