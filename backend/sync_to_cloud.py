import os
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

db_path = Path(__file__).parent / "aevum.db"
if not db_path.exists():
    print(f"❌ 错误: 未找到本地数据库文件: {db_path}")
    exit(1)

print("🔄 正在整合本地 SQLite 数据 (WAL Checkpoint)...")
con = sqlite3.connect(str(db_path))
con.execute("PRAGMA wal_checkpoint(TRUNCATE);")
cur = con.cursor()
cur.execute("SELECT count(*) FROM messages")
msg_count = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM memory_items")
mem_count = cur.fetchone()[0]
con.close()

print(f"📦 准备上传: 共 {msg_count} 条对话历史，{mem_count} 条沉淀记忆...")

cloud_url = "https://aevum-1mcy.onrender.com/sync/upload-database"
boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"

with open(db_path, "rb") as f:
    file_bytes = f.read()

body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="aevum.db"\r\n'
    f"Content-Type: application/x-sqlite3\r\n\r\n"
).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

req = urllib.request.Request(
    cloud_url,
    data=body,
    headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "X-Sync-Key": api_key,
    },
    method="POST",
)

try:
    print(f"🚀 正在上传至云端 {cloud_url} ...")
    with urllib.request.urlopen(req) as resp:
        res = resp.read().decode("utf-8")
        print("\n✅ 同步成功！")
        print(f"云端返回: {res}")
        print("\n现在手机打开 Aevum App，即可看到完整的电脑聊天历史、记忆与好感度进度！")
except urllib.error.HTTPError as e:
    err_body = e.read().decode("utf-8")
    print(f"❌ 上传失败 (HTTP {e.code}): {err_body}")
except Exception as e:
    print(f"❌ 发生异常: {e}")
