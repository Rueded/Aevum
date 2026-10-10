import json
from pathlib import Path

path = Path("d:/Aevum/Aevum/scratch_phase183_candidate_eval.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("================================================================================")
print("=== 12 TARGETED SCENARIO PROBES ===")
print("================================================================================")
for p in data["probe_evaluations"]:
    print(f"\n[{p['probe_id']}] ({p['category']})")
    print(f"Goal: {p['description']}")
    print(f"User: {p['user_input']}")
    print(f"Candidate Speech:\n{p.get('candidate_response')}")
    print(f"Bubbles: {p.get('candidate_bubbles')}")
    dec = p.get("decision")
    if dec:
        print(f"Decision: attention='{dec.get('attention')}', reaction='{dec.get('reaction')}', energy={dec.get('energy')}, commitment={dec.get('commitment')}, motiv={dec.get('motivation')}, frict={dec.get('friction')}, cur={dec.get('curiosity')}")
    print("-" * 70)

print("\n================================================================================")
print("=== 35 CONTINUOUS REPLAY TURNS: BASELINE vs CANDIDATE ===")
print("================================================================================")
for t in data["replay_35turns"]:
    turn = t["turn"]
    print(f"\n--- [Turn {turn:02d}] ---")
    print(f"User: {t['user']}")
    print(f"Baseline (Phase 16.5):\n{t['baseline_assistant']}")
    print(f"Candidate (Phase 18.2):\n{t['candidate_assistant']}")
    print(f"Cand Bubbles: {t.get('candidate_bubbles')}")
    dec = t.get("decision")
    if dec:
        print(f"Cand Decision: attention='{dec.get('attention')}', reaction='{dec.get('reaction')}', energy={dec.get('energy')}, commit={dec.get('commitment')}, motiv={dec.get('motivation')}, frict={dec.get('friction')}, cur={dec.get('curiosity')}")
    print("-" * 70)
