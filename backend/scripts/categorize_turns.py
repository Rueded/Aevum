import json

path = "d:/Aevum/Aevum/scratch_phase183_candidate_eval.json"
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Qualitative analysis criteria:
# improved: distinctly more natural, reduced AI-trope/essay structure, authentic presence, good friction/closure
# unchanged: both gave acceptable/similar answers without distinct delta
# regressed: baseline was more authentic, or candidate had inconsistency/repetition
# ambiguous: trade-off between style and content

results = []
for t in data["replay_35turns"]:
    turn = t["turn"]
    u = t["user"]
    b = t["baseline_assistant"]
    c = t["candidate_assistant"]
    dec = t.get("decision", {})
    
    # Classifications based on detailed review
    if turn in [3, 4, 10, 14, 20, 23, 24, 28, 31, 35]:
        cat = "unchanged" # Both good or similar
    elif turn in [26]:
        cat = "regressed" # Candidate agreed with user and contradicted morning routine, repeated question
    elif turn in [1, 2, 8, 16, 21, 25]:
        cat = "ambiguous" # Good tone, but leaked trailing question or partial echo
    else:
        cat = "improved" # 5, 6, 7, 9, 11, 12, 13, 15, 17, 18, 19, 22, 27, 29, 30, 32, 33, 34
    
    results.append((turn, cat, u, b, c, dec))

print("Turn-by-turn counts:")
from collections import Counter
counts = Counter(r[1] for r in results)
print(counts)
for r in results:
    if r[1] in ["regressed", "ambiguous"]:
        print(f"Turn {r[0]:02d} [{r[1]}]: User: {r[2][:25]} | Cand: {r[4][:40]}...")
