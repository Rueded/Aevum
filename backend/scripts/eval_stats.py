import json
from pathlib import Path

path = Path("d:/Aevum/Aevum/scratch_phase183_candidate_eval.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

replays = data["replay_35turns"]
probes = data["probe_evaluations"]

print("=== STATISTICAL COMPARISON (35 REPLAY TURNS) ===")
base_lens = [len(t["baseline_assistant"]) for t in replays]
cand_lens = [len(t["candidate_assistant"]) for t in replays]
base_q = [t["baseline_assistant"].count("？") + t["baseline_assistant"].count("?") for t in replays]
cand_q = [t["candidate_assistant"].count("？") + t["candidate_assistant"].count("?") for t in replays]

print(f"Avg Length: Baseline = {sum(base_lens)/len(base_lens):.1f} chars | Candidate = {sum(cand_lens)/len(cand_lens):.1f} chars")
print(f"Total Questions: Baseline = {sum(base_q)} | Candidate = {sum(cand_q)}")
print(f"Turns with Questions: Baseline = {sum(1 for q in base_q if q > 0)}/35 | Candidate = {sum(1 for q in cand_q if q > 0)}/35")

decisions = [t["decision"] for t in replays if t.get("decision")]
print("\n--- Candidate Decision Distributions (35 turns) ---")
from collections import Counter
print("Commitment:", Counter(d.get("commitment") for d in decisions))
print("Energy:", Counter(d.get("energy") for d in decisions))
print("Motivation:", Counter(d.get("motivation") for d in decisions))
print("Friction:", Counter(d.get("friction") for d in decisions))
print("Curiosity:", Counter(d.get("curiosity") for d in decisions))

bubble_lens = [len(t.get("candidate_bubbles", [])) for t in replays]
print("Bubbles per turn:", Counter(bubble_lens))

# Check discrepancies between cur=False and actual question mark
cur_false_with_q = []
for t in replays:
    dec = t.get("decision", {})
    cand_text = t.get("candidate_assistant", "")
    has_q = "？" in cand_text or "?" in cand_text
    if dec.get("curiosity") is False and has_q:
        cur_false_with_q.append((t["turn"], t["user"][:20], cand_text[-30:]))
print(f"\nTurns where decision curiosity=False but speech had '？': {len(cur_false_with_q)} turns")
for turn_num, u, end in cur_false_with_q:
    print(f"  Turn {turn_num:02d}: end='{end.strip()}'")
