"""Apply self-explanatory filename annotations to root stickers in docs/stickers/images.

Per user instruction:
- Filenames in docs/stickers/images root already represent the meaning of the image.
- Mark them as is_annotated=True directly unless the filename does not explain the meaning
  (e.g. pure numbers, single letters, or short non-descriptive names like 1.webp, 123.webp).
- Ensure is_favorite=True so they are prioritized highest in conversation.
"""

import json
import os
import re
import sqlite3

TAG_RULES = [
    (r"(问号|\?|？|疑惑|什么|啊？|难道说|嗯？|查查|怎么)", "问号/疑惑"),
    (r"(生气|气死|愤怒|怒|吵|骂|掀|服了|粗口|黑化|黑脸|杀了|砍|锯)", "生气/破防"),
    (r"(笑|哈|嘿|乐|偷笑|咧嘴|开心|欢呼|喜|耶|超赞|棒|太好)", "开心/整活"),
    (r"(哭|泪|呜|难过|伤心|委屈|TT|呜呜|痛|惨)", "委屈/哭泣"),
    (r"(躺|瘫|摆烂|累|困|睡|休|无力|废|倒|死)", "摆烂/疲倦"),
    (r"(抱|蹭|爱|喜欢|贴贴|摸摸|心|捧|亲|送花|乖)", "亲昵/温暖"),
    (r"(无语|汗|白眼|别致|虾头|变态|奇怪|服|不怎么样|就这|拉了|尴尬)", "无语/嫌弃"),
    (r"(赞|强|厉害|高手|神|顶|ok|棒|划算|可以|不赖|不错|不愧是我)", "认同/夸赞"),
    (r"(怼|阴阳|呵|走吧|去死|反击|开大|那咋了|那咋办|谁管你|跟你说不来|黑子)", "调侃/阴阳怪气"),
    (r"(怕|吓|慌|急|救命|不要|不行|别|达美)", "慌张/拒绝"),
]


def extract_emotion_tags(text: str) -> list[str]:
    tags = []
    for pattern, tag in TAG_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            if tag not in tags:
                tags.append(tag)
    if not tags:
        tags.append("日常/吐槽")
    return tags


EXPRESSIVE_SINGLE_CHARS = set("呃呕哇哈哦哼啊啥啾嗯嘻坏早晕杀盯赞乐哭累困顶靠草懂绝寄润溜怂慌冲服喵怒呆懵爽美切")


def is_filename_informative(fname: str) -> tuple[bool, str]:
    base = os.path.splitext(fname)[0]
    # Remove leading numeric prefixes like "1", "120-", "Screenshot "
    cleaned = re.sub(r"^\d+[-_ ]*", "", base).strip()
    # Normalize duplicate suffix like _1
    cleaned = re.sub(r"_\d+$", "", cleaned).strip()

    # Check if cleaned is pure question marks or exclamation marks
    if re.fullmatch(r"[？\?！!。.\s]+", cleaned):
        return True, cleaned

    cleaned_without_suffix = re.sub(r"[-_ ]*(?:砂狼白子|菲比|表情包).*$", "", cleaned).strip()
    if not cleaned_without_suffix:
        cleaned_without_suffix = cleaned

    chinese_chars = re.findall(r"[\u4e00-\u9fff]", cleaned_without_suffix)

    # If it contains 2 or more Chinese characters, it is self-explanatory
    if len(chinese_chars) >= 2 and cleaned_without_suffix not in ("表情包", "菲比", "图片"):
        return True, cleaned_without_suffix

    # If it contains 1 Chinese character that is intrinsically expressive
    if len(chinese_chars) == 1 and chinese_chars[0] in EXPRESSIVE_SINGLE_CHARS:
        return True, cleaned_without_suffix

    # Check for expressive internet slang or English phrases
    low = cleaned.lower()
    if any(k in low for k in ("nono", "no！no！", "wink", "baam", "okgo", "super", "ok", "dj", "vivo50", "chovy", "wpx", "mingchao", "bee")):
        return True, cleaned

    return False, cleaned


def main():
    conn = sqlite3.connect("aevum.db")
    cursor = conn.cursor()

    # Query all root stickers (series == '菲比/散装常用')
    rows = cursor.execute(
        "SELECT id, file_path, is_annotated FROM stickers WHERE series = '菲比/散装常用'"
    ).fetchall()

    annotated_count = 0
    skipped_uninformative = 0

    for stk_id, file_path, already_annotated in rows:
        fname = os.path.basename(file_path)
        is_info, cleaned_text = is_filename_informative(fname)

        if is_info:
            tags = extract_emotion_tags(cleaned_text)
            tags_json = json.dumps(tags, ensure_ascii=False)
            ocr_text = cleaned_text if len(cleaned_text) <= 25 else ""

            # Update record: mark annotated, set description, ocr text, tags, and favorite
            cursor.execute(
                """
                UPDATE stickers
                SET description = ?,
                    text_ocr = ?,
                    emotion_tags = ?,
                    is_annotated = 1,
                    is_favorite = 1
                WHERE id = ?
                """,
                (cleaned_text, ocr_text, tags_json, stk_id),
            )
            annotated_count += 1
        else:
            # Filename does not explain the meaning (needs visual recognition)
            # Ensure is_annotated = 0 so it stays queued for visual recognition
            cursor.execute(
                """
                UPDATE stickers
                SET is_favorite = 1
                WHERE id = ? AND is_annotated = 0
                """,
                (stk_id,),
            )
            skipped_uninformative += 1

    conn.commit()
    conn.close()

    # Also sync changes to backend/aevum.db
    if os.path.exists("backend/aevum.db"):
        conn_b = sqlite3.connect("backend/aevum.db")
        conn_a = sqlite3.connect("aevum.db")
        cursor_b = conn_b.cursor()
        for r in conn_a.execute("SELECT id, description, text_ocr, emotion_tags, is_annotated, is_favorite FROM stickers WHERE series = '菲比/散装常用'").fetchall():
            cursor_b.execute(
                "UPDATE stickers SET description = ?, text_ocr = ?, emotion_tags = ?, is_annotated = ?, is_favorite = ? WHERE id = ?",
                (r[1], r[2], r[3], r[4], r[5], r[0]),
            )
        conn_b.commit()
        conn_a.close()
        conn_b.close()

    print(f"Processed {len(rows)} root stickers:")
    print(f"  - Self-explanatory (annotated from filename directly): {annotated_count}")
    print(f"  - Uninformative (kept is_annotated=0 for vision recognition): {skipped_uninformative}")


if __name__ == "__main__":
    main()
