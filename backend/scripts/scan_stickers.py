import os
import hashlib
from collections import defaultdict
from PIL import Image

root = "docs/stickers/images"
folder_stats = defaultdict(lambda: {"count": 0, "size": 0, "exts": defaultdict(int)})
sha_map = defaultdict(list)
corrupted = []
total_files = 0
total_size = 0

for dirpath, dirnames, filenames in os.walk(root):
    rel_dir = os.path.relpath(dirpath, root)
    for fname in filenames:
        fpath = os.path.join(dirpath, fname)
        ext = os.path.splitext(fname)[1].lower()
        if ext in (".zip", ".rar", ".7z", ".txt"):
            continue
        try:
            sz = os.path.getsize(fpath)
            total_files += 1
            total_size += sz
            folder_stats[rel_dir]["count"] += 1
            folder_stats[rel_dir]["size"] += sz
            folder_stats[rel_dir]["exts"][ext] += 1

            with open(fpath, "rb") as f:
                h = hashlib.sha256(f.read()).hexdigest()
            sha_map[h].append(fpath)
        except Exception as e:
            corrupted.append((fpath, str(e)))

exact_dup_groups = [paths for paths in sha_map.values() if len(paths) > 1]
dup_files_count = sum(len(paths) - 1 for paths in exact_dup_groups)

print("=== SCAN RESULTS ===")
print(f"Total valid sticker files: {total_files}")
print(f"Total size: {total_size / (1024*1024):.2f} MB")
print(f"Corrupted / unreadable files: {len(corrupted)}")
print(f"Exact duplicate groups: {len(exact_dup_groups)} ({dup_files_count} redundant files)")
print(f"Unique images after exact deduplication: {total_files - dup_files_count}")
print("\n=== FOLDER BREAKDOWN ===")
for folder, s in sorted(folder_stats.items(), key=lambda x: x[1]["count"], reverse=True):
    folder_name = "根目录 (菲比及各类散装表情包)" if folder == "." else folder
    ext_str = ", ".join(f"{k}: {v}" for k, v in sorted(s["exts"].items()))
    print(f"- {folder_name}: {s['count']} 张 ({s['size']/(1024*1024):.2f} MB) [{ext_str}]")
