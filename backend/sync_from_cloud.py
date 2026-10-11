import os
import shutil
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

# Load local environment
load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY", "").strip()

if not api_key:
    print("❌ 错误: 本地 .env 文件中未找到 GEMINI_API_KEY。")
    exit(1)

cloud_url = "https://aevum-1mcy.onrender.com/sync/download-database"
db_path = Path(__file__).parent / "aevum.db"
backup_path = Path(__file__).parent / "aevum.db.bak"

print(f"📥 正在从云端下载最新数据库 ({cloud_url})...")
req = urllib.request.Request(
    cloud_url,
    headers={"X-Sync-Key": api_key},
    method="GET",
)

try:
    with urllib.request.urlopen(req) as resp:
        content = resp.read()
        if len(content) < 100:
            print("❌ 下载的数据异常或过小。")
            exit(1)

        # Backup current local DB first
        if db_path.exists():
            shutil.copy2(db_path, backup_path)

        # Write to temp file first to verify SQLite integrity
        temp_path = Path(__file__).parent / "aevum_download.tmp"
        with open(temp_path, "wb") as f:
            f.write(content)

        con = sqlite3.connect(str(temp_path))
        cur = con.cursor()
        cur.execute("SELECT count(*) FROM messages")
        msg_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM memories")
        mem_count = cur.fetchone()[0]
        con.close()

        # Clean WAL / SHM
        for ext in ["aevum.db-wal", "aevum.db-shm"]:
            wal_file = Path(__file__).parent / ext
            if wal_file.exists():
                try:
                    os.remove(wal_file)
                except Exception:
                    pass

        # Overwrite local DB
        shutil.move(temp_path, db_path)

        print("\n✅ 云端数据下载并同步到本地成功！")
        print(f"📦 当前本地数据库：共 {msg_count} 条对话历史，{mem_count} 条沉淀记忆")
        print("（已在本地生成安全备份 aevum.db.bak）")

except urllib.error.HTTPError as e:
    err_body = e.read().decode("utf-8", errors="ignore")
    print(f"❌ 下载失败 (HTTP {e.code}): {err_body}")
except Exception as e:
    print(f"❌ 发生异常: {e}")
