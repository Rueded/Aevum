"""Aevum Human-likeness Evaluation Pipeline.

Calculates conversational metrics according to AEVUM_HUMANLIKE_REFACTOR_BRIEF.md:
- Bubble length median (target <= 12)
- <=10 chars % (target >= 50%)
- <=20 chars % (target >= 70%)
- Ends in question % (target <= 10%)
- Multiline bubbles count (target = 0)
- Max bubbles per turn (target <= 3)
- Turns with stickers % (target >= 30%)
- Sticker-only turns % (target >= 10%)
- Latency p50 (target <= 5.0s)
- System prompt length (target <= 6000 chars)
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import statistics
import time
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EvalHumanLikeness")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_EVAL_DIR = PROJECT_ROOT / "docs" / "eval"
SOUL_MD = PROJECT_ROOT / "AEVUM_SOUL_AND_PROGRESS.md"
BASELINE_JSON = PROJECT_ROOT / "scratch_dialogue_experiment_35turns.json"

STICKER_PATTERN = re.compile(r"\[(?:表情包[：:]?[^\]]*|旺柴|苦涩|破涕为笑|囧|Facepalm|撇嘴|害羞|奸笑|流泪|右哼哼|发呆|天啊|Doge|裂开|捂脸|Hurt|Lol|嘿哈|微笑)\]")


def is_question(text: str) -> bool:
    """Check if a response ends in a question."""
    t = text.strip()
    if not t:
        return False
    if t.endswith("?") or t.endswith("？"):
        return True
    # Strip trailing punctuation before checking question particles
    t_clean = re.sub(r"[。！!…~～]+$", "", t)
    # Common Chinese question ending particles when not followed by other sentences
    for particle in ("吗", "嘛", "么", "呢", "蛤"):
        if t_clean.endswith(particle):
            return True
    return False


def extract_bubbles_from_turn(assistant_turn: Any) -> List[str]:
    """Extract individual bubbles from assistant turn."""
    if isinstance(assistant_turn, dict):
        if "bubbles" in assistant_turn and assistant_turn["bubbles"]:
            return [b.strip() for b in assistant_turn["bubbles"] if b.strip()]
        content = assistant_turn.get("content") or assistant_turn.get("assistant") or ""
    elif isinstance(assistant_turn, str):
        content = assistant_turn
    else:
        content = str(assistant_turn)

    # If text contains double newlines, treat each chunk as a bubble/paragraph
    paras = [p.strip() for p in content.split("\n") if p.strip()]
    return paras if paras else [content.strip()] if content.strip() else []


def calculate_human_baseline(conv_json: Path = PROJECT_ROOT / "docs" / "conversation.json", soul_file: Path = SOUL_MD) -> Dict[str, Any]:
    """Parse real human conversations in docs/conversation.json (Brief §9.1b) or fallback to AEVUM_SOUL_AND_PROGRESS.md §2."""
    if conv_json.exists():
        with open(conv_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        friend_bubbles = []
        friend_turns = 0
        friend_turns_with_sticker = 0
        friend_sticker_only_turns = 0
        friend_turn_counts = []

        for sec in data:
            dialogue = sec.get("dialogue", [])
            if not dialogue:
                continue

            current_speaker = None
            current_turn = []
            for msg in dialogue:
                spk = "user" if msg.get("speaker") == "你" else "friend"
                if spk != current_speaker:
                    if current_turn and current_speaker == "friend":
                        friend_turns += 1
                        friend_turn_counts.append(len(current_turn))
                        if any("sticker" in str(m) for m in current_turn):
                            friend_turns_with_sticker += 1
                        if all("sticker" in str(m) and not m.get("content") for m in current_turn):
                            friend_sticker_only_turns += 1
                    current_speaker = spk
                    current_turn = [msg]
                else:
                    current_turn.append(msg)

                if spk == "friend" and msg.get("content"):
                    friend_bubbles.append(msg["content"].strip())

            if current_turn and current_speaker == "friend":
                friend_turns += 1
                friend_turn_counts.append(len(current_turn))
                if any("sticker" in str(m) for m in current_turn):
                    friend_turns_with_sticker += 1
                if all("sticker" in str(m) and not m.get("content") for m in current_turn):
                    friend_sticker_only_turns += 1

        f_lens = [len(b) for b in friend_bubbles]
        return {
            "metadata": {
                "source": "docs/conversation.json (friend side / her per Brief §9.1b)",
                "bubble_count": len(friend_bubbles),
                "turn_count": friend_turns,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "metrics": {
                "bubble_length_median": round(statistics.median(f_lens), 1) if f_lens else 0,
                "bubble_le_10_pct": round(sum(1 for l in f_lens if l <= 10) / len(f_lens) * 100, 1) if f_lens else 0,
                "bubble_le_20_pct": round(sum(1 for l in f_lens if l <= 20) / len(f_lens) * 100, 1) if f_lens else 0,
                "ends_with_question_pct": round(sum(1 for b in friend_bubbles if is_question(b)) / len(friend_bubbles) * 100, 1) if friend_bubbles else 0,
                "multiline_bubble_count": 0,
                "max_bubbles_per_turn": max(friend_turn_counts) if friend_turn_counts else 6,
                "avg_bubbles_per_turn": round(statistics.mean(friend_turn_counts), 2) if friend_turn_counts else 2.0,
                "turns_with_stickers_pct": round(friend_turns_with_sticker / friend_turns * 100, 1) if friend_turns else 0,
                "sticker_only_turns_pct": round(friend_sticker_only_turns / friend_turns * 100, 1) if friend_turns else 0,
            },
        }

    if not soul_file.exists():
        raise FileNotFoundError(f"Neither conversation.json nor soul file found at {soul_file}")

    with open(soul_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Section 2.1: lines 37 to 962 (0-indexed 36 to 962)
    # Section 2.3: lines 980 to 1353 (0-indexed 979 to 1353)
    human_bubbles = []
    # 2.1
    for line in lines[36:962]:
        l = line.strip()
        if l and not l.startswith("```"):
            human_bubbles.append(l)
    # 2.3
    for line in lines[979:1353]:
        l = line.strip()
        if l and not l.startswith("```"):
            human_bubbles.append(l)

    lens = [len(b) for b in human_bubbles]
    le_10 = sum(1 for l in lens if l <= 10) / len(lens) * 100 if lens else 0.0
    le_20 = sum(1 for l in lens if l <= 20) / len(lens) * 100 if lens else 0.0
    ends_q = sum(1 for b in human_bubbles if is_question(b)) / len(human_bubbles) * 100 if human_bubbles else 0.0
    contains_tag = sum(1 for b in human_bubbles if STICKER_PATTERN.search(b) or ("[" in b and "]" in b)) / len(human_bubbles) * 100 if human_bubbles else 0.0

    return {
        "metadata": {
            "source": "AEVUM_SOUL_AND_PROGRESS.md §2",
            "bubble_count": len(human_bubbles),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "notes": "Text-only chat logs; image stickers omitted in original logs per §2.4",
        },
        "metrics": {
            "bubble_length_median": round(statistics.median(lens), 1) if lens else 0,
            "bubble_le_10_pct": round(le_10, 1),
            "bubble_le_20_pct": round(le_20, 1),
            "ends_with_question_pct": round(ends_q, 1),
            "text_sticker_tag_pct": round(contains_tag, 1),
            "image_stickers_pct": None,  # Pending visual logs per Brief §9
            "multiline_bubble_count": 0,
            "max_bubbles_per_turn": 3,
        },
    }


def calculate_dialogue_metrics(
    turns: List[Dict[str, Any]],
    system_prompt_char_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Calculate evaluation metrics on a list of dialogue turns."""
    all_bubbles: List[str] = []
    bubbles_per_turn: List[int] = []
    ends_q_count = 0
    multiline_bubble_count = 0
    turns_with_stickers = 0
    sticker_only_turns = 0
    latencies: List[float] = []

    for turn in turns:
        bubbles = extract_bubbles_from_turn(turn)
        bubbles_per_turn.append(len(bubbles))
        all_bubbles.extend(bubbles)

        # Check multiline
        for b in bubbles:
            if "\n" in b:
                multiline_bubble_count += 1

        # Check ending in question on full turn
        full_content = turn.get("content") or turn.get("assistant") or ""
        if isinstance(full_content, str) and is_question(full_content):
            ends_q_count += 1

        # Check stickers
        has_sticker = False
        text_without_stickers = full_content

        # Check text tags
        if STICKER_PATTERN.search(full_content):
            has_sticker = True
            text_without_stickers = STICKER_PATTERN.sub("", text_without_stickers).strip()

        # Check structured bubbles/stickers
        if "stickers" in turn and turn["stickers"]:
            has_sticker = True

        if has_sticker:
            turns_with_stickers += 1
            if not text_without_stickers:
                sticker_only_turns += 1

        if "latency_sec" in turn and turn["latency_sec"] is not None:
            latencies.append(float(turn["latency_sec"]))

    total_turns = len(turns)
    total_bubbles = len(all_bubbles)
    bubble_lens = [len(b) for b in all_bubbles] if all_bubbles else [0]

    return {
        "turn_count": total_turns,
        "bubble_count": total_bubbles,
        "bubble_length_median": round(statistics.median(bubble_lens), 1) if bubble_lens else 0,
        "bubble_le_10_pct": round(sum(1 for l in bubble_lens if l <= 10) / total_bubbles * 100, 1) if total_bubbles else 0,
        "bubble_le_20_pct": round(sum(1 for l in bubble_lens if l <= 20) / total_bubbles * 100, 1) if total_bubbles else 0,
        "ends_with_question_pct": round(ends_q_count / total_turns * 100, 1) if total_turns else 0,
        "multiline_bubble_count": multiline_bubble_count,
        "max_bubbles_per_turn": max(bubbles_per_turn) if bubbles_per_turn else 0,
        "avg_bubbles_per_turn": round(statistics.mean(bubbles_per_turn), 2) if bubbles_per_turn else 0,
        "turns_with_stickers_pct": round(turns_with_stickers / total_turns * 100, 1) if total_turns else 0,
        "sticker_only_turns_pct": round(sticker_only_turns / total_turns * 100, 1) if total_turns else 0,
        "latency_p50": round(statistics.median(latencies), 2) if latencies else None,
        "latency_max": round(max(latencies), 2) if latencies else None,
        "system_prompt_char_count": system_prompt_char_count,
    }


async def replay_dialogue_turns(
    user_inputs: List[str],
    character_id: str = "aevum",
    db_path: Optional[Path] = None,
    delay_between_turns: float = 0.5,
) -> tuple[List[Dict[str, Any]], Optional[int]]:
    """Replay user turns against the live backend system via true online route (conversations.py:create_message)."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.character.engine import CharacterEngine
    from app.character.prompt_assembler import ResponseContextAssembler
    from app.db.session import async_session_factory

    # Capture system prompt size on a fresh context and temporarily disable sleep realism for eval
    system_prompt_char_count: Optional[int] = None
    orig_sleep_realism: bool = True
    try:
        async with async_session_factory() as s:
            ce = CharacterEngine(session=s)
            sample_ctx = await ce.build_response_context(user_inputs[0] if user_inputs else "你好", character_id, "user")
            llm_ctx = ResponseContextAssembler.assemble(sample_ctx, conversation_history=[])
            sys_instruction = "\n".join(llm_ctx.system_instructions)
            system_prompt_char_count = len(sys_instruction)

            from app.desktop.service import DesktopService
            from app.desktop.models import DesktopUserSettingsUpdate
            ds = DesktopService(s)
            curr = await ds.get_settings(character_id)
            orig_sleep_realism = getattr(curr, "sleep_realism_enabled", True)
            await ds.update_settings(DesktopUserSettingsUpdate(sleep_realism_enabled=False), character_id=character_id)
            await s.commit()
    except Exception as e:
        logger.warning("Failed to estimate system prompt size or set eval settings: %s", e)

    recorded_turns: List[Dict[str, Any]] = []
    logger.info("Starting online replay of %d turns via conversations.py:create_message...", len(user_inputs))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as client:
        # 1. Create online conversation
        conv_resp = await client.post("/conversations", json={"character_id": character_id, "title": "Online Replay Eval"})
        if conv_resp.status_code != 201:
            raise RuntimeError(f"Failed to create conversation: {conv_resp.status_code} {conv_resp.text}")
        conv_id = conv_resp.json()["id"]
        logger.info("Created online evaluation conversation: %s", conv_id)

        # 2. Sequentially send messages through POST /conversations/{id}/messages
        for idx, user_text in enumerate(user_inputs, start=1):
            logger.info("[Turn %02d/%02d] User: %s", idx, len(user_inputs), user_text)
            t0 = time.perf_counter()
            try:
                resp = await client.post(f"/conversations/{conv_id}/messages", json={"content": user_text})
                latency = round(time.perf_counter() - t0, 2)
                if resp.status_code != 201:
                    logger.error("Turn %d HTTP %d: %s", idx, resp.status_code, resp.text)
                    recorded_turns.append({
                        "turn": idx,
                        "user": user_text,
                        "assistant": f"[HTTP {resp.status_code}: {resp.text}]",
                        "bubbles": [],
                        "thought": None,
                        "latency_sec": latency,
                        "status": "error",
                    })
                    continue

                data = resp.json()
                ast_obj = data.get("assistant_response") or {}
                assistant_text = (ast_obj.get("content") or "").strip()
                bubbles = ast_obj.get("speech_bubbles") or [p.strip() for p in assistant_text.split("\n") if p.strip()]

                turn_data = {
                    "turn": idx,
                    "user": user_text,
                    "assistant": assistant_text,
                    "bubbles": bubbles,
                    "thought": None,
                    "latency_sec": latency,
                    "status": "success",
                }
                recorded_turns.append(turn_data)
                logger.info("  -> [%.2fs] Assistant (%d bubbles): %s", latency, len(bubbles), assistant_text.replace("\n", " ")[:60])
            except Exception as exc:
                latency = round(time.perf_counter() - t0, 2)
                logger.error("Turn %d failed: %s", idx, exc, exc_info=True)
                recorded_turns.append({
                    "turn": idx,
                    "user": user_text,
                    "assistant": f"[Error: {exc}]",
                    "bubbles": [],
                    "thought": None,
                    "latency_sec": latency,
                    "status": "error",
                })

            if delay_between_turns > 0 and idx < len(user_inputs):
                await asyncio.sleep(delay_between_turns)

    # Restore desktop settings
    try:
        async with async_session_factory() as s:
            from app.desktop.service import DesktopService
            from app.desktop.models import DesktopUserSettingsUpdate
            ds = DesktopService(s)
            await ds.update_settings(DesktopUserSettingsUpdate(sleep_realism_enabled=orig_sleep_realism), character_id=character_id)
            await s.commit()
    except Exception as e:
        logger.warning("Failed to restore eval settings: %s", e)

    return recorded_turns, system_prompt_char_count


def compare_reports(reports: Dict[str, Dict[str, Any]]) -> str:
    """Generate Markdown comparison table from multiple evaluation reports."""
    headers = [
        "Metric",
        "Target",
        "Human Baseline",
    ]
    report_names = list(reports.keys())
    headers.extend(report_names)

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    metric_rows = [
        ("Bubble length median", "≤ 12 字", "bubble_length_median", "{} 字"),
        ("≤10 chars %", "≥ 50%", "bubble_le_10_pct", "{}%"),
        ("≤20 chars %", "≥ 70%", "bubble_le_20_pct", "{}%"),
        ("Ends in question %", "≤ 10%", "ends_with_question_pct", "{}%"),
        ("Multiline bubbles count", "0", "multiline_bubble_count", "{}"),
        ("Max bubbles per turn", "≤ 3", "max_bubbles_per_turn", "{}"),
        ("Sticker turns %", "≥ 30%", "turns_with_stickers_pct", "{}%"),
        ("Sticker-only turns %", "≥ 10%", "sticker_only_turns_pct", "{}%"),
        ("Latency p50", "≤ 5.0s", "latency_p50", "{}s"),
        ("System prompt length", "≤ 6000", "system_prompt_char_count", "{} chars"),
    ]

    for label, target, key, fmt in metric_rows:
        row = [label, target, "-"]
        # If human baseline is among reports, handle it
        for rname in report_names:
            metrics = reports[rname].get("metrics", {})
            val = metrics.get(key)
            if val is None:
                row.append("-")
            else:
                row.append(fmt.format(val))
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Aevum Human-likeness Evaluation")
    parser.add_argument("--human", action="store_true", help="Generate docs/eval/baseline_human.json")
    parser.add_argument("--baseline-before", action="store_true", help="Evaluate scratch_dialogue_experiment_35turns.json as baseline_before")
    parser.add_argument("--replay", action="store_true", help="Replay 35 turns against live system")
    parser.add_argument("--turns-file", type=str, default=str(BASELINE_JSON), help="JSON file with user turns to replay or evaluate")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    parser.add_argument("--compare", nargs="+", help="Compare multiple eval JSON files and output markdown table")
    args = parser.parse_args()

    DOCS_EVAL_DIR.mkdir(parents=True, exist_ok=True)

    if args.human:
        logger.info("Computing human baseline from %s...", SOUL_MD)
        res = calculate_human_baseline()
        out_path = DOCS_EVAL_DIR / "baseline_human.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        logger.info("Saved human baseline to %s", out_path)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if args.baseline_before:
        logger.info("Evaluating existing 35 turns from %s...", BASELINE_JSON)
        with open(BASELINE_JSON, "r", encoding="utf-8") as f:
            turns = json.load(f)
        metrics = calculate_dialogue_metrics(turns)
        report = {
            "metadata": {
                "source": str(BASELINE_JSON),
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "phase": "Baseline (Before Refactor)",
            },
            "metrics": metrics,
            "turns": turns,
        }
        out_path = DOCS_EVAL_DIR / "baseline_before.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info("Saved baseline_before to %s", out_path)
        print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
        return

    if args.replay:
        with open(args.turns_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        user_inputs = [t["user"] for t in raw_data if "user" in t]

        logger.info("Replaying %d turns...", len(user_inputs))
        recorded_turns, prompt_size = asyncio.run(replay_dialogue_turns(user_inputs))
        metrics = calculate_dialogue_metrics(recorded_turns, system_prompt_char_count=prompt_size)

        out_path = Path(args.output) if args.output else (DOCS_EVAL_DIR / "replay_eval.json")
        report = {
            "metadata": {
                "source": args.turns_file,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "turn_count": len(recorded_turns),
            },
            "metrics": metrics,
            "turns": recorded_turns,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info("Saved replay evaluation to %s", out_path)
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return

    if args.compare:
        reports = {}
        for p in args.compare:
            path = Path(p)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = path.stem
            reports[name] = data
        print(compare_reports(reports))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
