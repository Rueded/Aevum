"""
deception_service.py — Service governing cross-turn deception verification & confrontation.

Phase: Cross-Turn Deception Verification & Playful Confrontation Closed Loop.
Implements:
1. Detection of user confessions ("其实之前是骗你的"), outrageous hoaxes ("烟霾放假一个月"),
   and cross-turn contradictions ("原神昔涟" -> "崩铁昔涟").
2. State machine management for cognitive grievances (SUSPECTED -> VERIFIED -> CONFRONTED -> RESOLVED).
3. Authoritative character irritation & emotion state updates upon deception and reconciliation.
4. Production of immutable CognitiveGrievanceContext for prompt injection.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Optional, Sequence
from uuid import uuid4

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CharacterDeceptionGrievanceRecord,
    CharacterStateRecord,
    EmotionStateRecord,
    Message,
)
from app.reality.deception_models import (
    CognitiveGrievanceContext,
    DeceptionType,
    GrievanceStage,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeceptionService:
    """Service orchestrating cross-turn deception verification and grievance resolution."""

    # Confession keywords indicating the user admits to lying or playing a prank
    CONFESSION_KEYWORDS = (
        "之前是骗你的",
        "刚才骗你的",
        "其实是骗你的",
        "其实我是骗你的",
        "刚才逗你玩的",
        "我逗你玩的",
        "其实是逗你的",
        "我瞎编的",
        "我忽悠你的",
        "骗你的啦",
        "逗你玩的啦",
        "跟你开玩笑的啦其实是假的",
        "i lied to you",
        "i was teasing you",
        "just kidding with you",
    )

    # Apology and peace-offering keywords indicating the user is apologizing or comforting
    APOLOGY_KEYWORDS = (
        "我错了",
        "好啦别生气",
        "好啦不要生气",
        "别生气啦",
        "请你喝奶茶",
        "请你吃好吃的",
        "原谅我嘛",
        "下次不敢了",
        "摸摸头",
        "给您赔不是",
        "我投降",
        "我认罚",
        "请你喝咖啡",
        "我请你喝",
        "请你吃火锅",
        "我买单",
        "sorry啦",
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @classmethod
    def detect_confession(cls, user_input: str) -> bool:
        """Detect whether the user is explicitly admitting they deceived/pranked Aevum."""
        text = user_input.lower().strip()
        return any(kw in text for kw in cls.CONFESSION_KEYWORDS)

    @classmethod
    def detect_apology_or_comfort(cls, user_input: str) -> bool:
        """Detect whether the user is apologizing, soothing, or offering peace treats."""
        text = user_input.lower().strip()
        return any(kw in text for kw in cls.APOLOGY_KEYWORDS)

    @classmethod
    def detect_outrageous_hoax(cls, user_input: str) -> Optional[tuple[str, str, str]]:
        """Identify high-impact external hoaxes requiring skeptical verification.

        Returns (claimed_assertion, verified_truth, topic_domain) if recognized.
        """
        text = user_input.strip()

        # 1. Haze / school closure hoax
        if ("放假一个月" in text or "停课一个月" in text) and ("烟霾" in text or "学校" in text or "大学" in text):
            return (
                text,
                "USM 理科大学官方公报各学院正常授课与期末考核，仅依据教育部烟霾指引暂停户外体育活动，绝无全校放假一个月之事。",
                "institution",
            )

        # 2. National / university exam cancellation
        if ("取消期末考" in text or "考试取消了" in text or "spm取消" in text.lower()) and ("取消" in text):
            return (
                text,
                "马来西亚教育部与理科大学并未发布任何考试取消通告，各期末考试与国家考试均正常排期进行。",
                "education",
            )

        # 3. Absurd campus relocation hoax
        if ("理科大学" in text or "usm" in text.lower()) and ("搬到吉隆坡" in text or "搬迁去吉隆坡" in text):
            return (
                text,
                "USM 槟城主校区位于槟岛 Minden，并未搬迁至吉隆坡。",
                "location",
            )

        # 4. Equator / tropical snowfall hoax
        if ("吉隆坡" in text or "槟城" in text or "马来西亚" in text or "雪隆" in text) and (
            "下雪" in text or "暴雪" in text or "零下" in text or "结冰" in text
        ):
            return (
                text,
                "马来西亚地处赤道热带雨林气候，全年高温多雨，历史气温从未低于20摄氏度，物理规律与气象学上绝无下雪或零下结冰可能。",
                "weather_climate",
            )

        # 5. Absurd citywide blackout / water cutoff for a month
        if ("吉隆坡" in text or "雪隆" in text or "槟城" in text or "理大" in text) and (
            ("停电" in text and ("一个月" in text or "半个月" in text))
            or ("停水" in text and ("一个月" in text or "半个月" in text))
        ):
            return (
                text,
                "国家能源局 (TNB) 与雪州水供公司 (Air Selangor) 均有完善的电网与水库应急调度机制，绝无全城切断水电长达一个月之可能。",
                "infrastructure",
            )

        # 6. Medical / pseudoscientific hoax (e.g. Milk tea curing/preventing dengue)
        if ("奶茶" in text or "美禄" in text) and ("骨痛热症" in text or "登革热" in text) and (
            "预防" in text or "治疗" in text or "治好" in text or "免疫" in text
        ):
            return (
                text,
                "骨痛热症是由伊蚊叮咬传播的登革病毒感染，医学预防核心是防蚊灭蚊与清除积水，喝奶茶或甜饮不仅无医学依据，高糖还可能招惹蚊虫。",
                "health_science",
            )

        # 7. Absurd food safety rumor (e.g. Durian nuclear radiation)
        if ("榴莲" in text or "猫山王" in text) and ("核辐射" in text or "辐射超标" in text or "剧毒致死" in text):
            return (
                text,
                "马来西亚农业及粮食安全部对榴莲种植与出口具有严格检验检疫标准，正规榴莲绝无核辐射超标之说。",
                "food_safety",
            )

        return None

    @classmethod
    def detect_cross_turn_contradiction(
        cls,
        user_input: str,
        history_messages: Optional[Sequence[Any]] = None,
    ) -> Optional[tuple[str, str, str]]:
        """Detect pop-culture cross-turn contradiction (e.g. The Xianlian / 昔涟 Paradigm).

        If user claimed Xianlian was from Genshin earlier, and now claims Star Rail or confesses.
        """
        text = user_input.strip()
        is_current_star_rail = ("昔涟" in text or "xianlian" in text.lower()) and (
            "崩铁" in text or "星穹铁道" in text or "star rail" in text.lower()
        )
        if not is_current_star_rail:
            return None

        if not history_messages:
            return None

        # Look back through history for past claims linking Xianlian with Genshin
        past_genshin_claim = False
        for msg in history_messages:
            content = getattr(msg, "content", "") or ""
            role = getattr(msg, "role", "") or ""
            if role == "user" and ("昔涟" in content or "xianlian" in content.lower()) and ("原神" in content or "genshin" in content.lower()):
                past_genshin_claim = True
                break

        if past_genshin_claim:
            return (
                "用户之前宣称『昔涟是原神角色』",
                "经确认，昔涟是《崩坏：星穹铁道》的角色，《原神》中并无此角色，之前是用户忽悠/恶作剧。",
                "gaming",
            )

        return None

    async def get_active_grievance(
        self,
        character_id: str = "aevum",
    ) -> Optional[CharacterDeceptionGrievanceRecord]:
        """Fetch the most recent active grievance awaiting confrontation or reconciliation."""
        query = (
            select(CharacterDeceptionGrievanceRecord)
            .where(
                CharacterDeceptionGrievanceRecord.character_id == character_id,
                CharacterDeceptionGrievanceRecord.stage.in_([
                    GrievanceStage.VERIFIED_DECEPTION.value,
                    GrievanceStage.CONFRONTED.value,
                ]),
            )
            .order_by(desc(CharacterDeceptionGrievanceRecord.created_at))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def record_deception(
        self,
        character_id: str,
        user_id: str,
        claimed_assertion: str,
        verified_truth: str,
        topic_domain: str = "general",
        deception_type: DeceptionType = DeceptionType.OUTRAGEOUS_CLAIM,
        confrontation_hint: Optional[str] = None,
    ) -> CharacterDeceptionGrievanceRecord:
        """Create and persist a verified deception grievance, updating character irritation."""
        now = utc_now()
        hint = confrontation_hint or (
            f"好啊你，居然敢忽悠我！我昨晚查过了，真相明明是『{verified_truth}』！快老实交代，为什么要骗我！[哼][白眼]"
        )

        record = CharacterDeceptionGrievanceRecord(
            id=str(uuid4()),
            character_id=character_id,
            user_id=user_id,
            claimed_assertion=claimed_assertion,
            verified_truth=verified_truth,
            topic_domain=topic_domain,
            deception_type=deception_type.value,
            stage=GrievanceStage.VERIFIED_DECEPTION.value,
            emotional_tone="playful_indignant",
            confrontation_hint=hint,
            created_at=now,
            verified_at=now,
        )
        self.session.add(record)

        # Trigger emotional state update: increase irritation & switch to annoyed/playful sulk
        try:
            state_query = select(CharacterStateRecord).where(CharacterStateRecord.id == character_id)
            state_res = await self.session.execute(state_query)
            state_rec = state_res.scalar_one_or_none()
            if state_rec:
                state_rec.irritation = min(1.0, (state_rec.irritation or 0.0) + 0.40)
                state_rec.mood = "irritated"
                state_rec.updated_at = now

            emo_query = select(EmotionStateRecord).where(EmotionStateRecord.character_id == character_id)
            emo_res = await self.session.execute(emo_query)
            emo_rec = emo_res.scalar_one_or_none()
            if emo_rec:
                emo_rec.emotion_type = "irritated"
                emo_rec.intensity = 0.70
                emo_rec.updated_at = now
        except Exception as exc:
            logger.warning("Failed to update character emotional irritation on deception: %s", exc)

        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def mark_confronted(self, grievance_id: str) -> None:
        """Transition grievance from VERIFIED_DECEPTION to CONFRONTED after Aevum calls user out."""
        now = utc_now()
        stmt = (
            update(CharacterDeceptionGrievanceRecord)
            .where(CharacterDeceptionGrievanceRecord.id == grievance_id)
            .values(
                stage=GrievanceStage.CONFRONTED.value,
                confronted_at=now,
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def reconcile_grievance(self, grievance_id: str) -> None:
        """Transition grievance to RESOLVED and dissipate irritation back to friendly baseline."""
        now = utc_now()
        stmt = (
            update(CharacterDeceptionGrievanceRecord)
            .where(CharacterDeceptionGrievanceRecord.id == grievance_id)
            .values(
                stage=GrievanceStage.RESOLVED.value,
                resolved_at=now,
            )
        )
        await self.session.execute(stmt)

        # Dissipate character irritation back to 0.0 and restore mood to happy/calm
        try:
            rec_query = select(CharacterDeceptionGrievanceRecord).where(CharacterDeceptionGrievanceRecord.id == grievance_id)
            rec_res = await self.session.execute(rec_query)
            grievance = rec_res.scalar_one_or_none()
            char_id = grievance.character_id if grievance else "aevum"

            state_query = select(CharacterStateRecord).where(CharacterStateRecord.id == char_id)
            state_res = await self.session.execute(state_query)
            state_rec = state_res.scalar_one_or_none()
            if state_rec:
                state_rec.irritation = 0.0
                state_rec.mood = "happy"
                state_rec.updated_at = now

            emo_query = select(EmotionStateRecord).where(EmotionStateRecord.character_id == char_id)
            emo_res = await self.session.execute(emo_query)
            emo_rec = emo_res.scalar_one_or_none()
            if emo_rec:
                emo_rec.emotion_type = "happy"
                emo_rec.intensity = 0.60
                emo_rec.updated_at = now
        except Exception as exc:
            logger.warning("Failed to reset emotional state on reconciliation: %s", exc)

        await self.session.commit()

    async def process_incoming_turn(
        self,
        user_input: str,
        character_id: str = "aevum",
        user_id: str = "user",
        history_messages: Optional[Sequence[Any]] = None,
    ) -> Optional[CognitiveGrievanceContext]:
        """Evaluate incoming message and active grievances to yield guidance context for this turn.

        Handles:
        1. User apologies when a grievance was already confronted -> returns RECONCILING.
        2. User confessions ("其实之前是骗你的") -> creates VERIFIED_DECEPTION grievance.
        3. Cross-turn pop-culture contradictions ("原神昔涟" -> "崩铁昔涟") -> creates grievance.
        4. Outrageous external hoaxes ("放假一个月") -> creates grievance.
        5. Returning active VERIFIED_DECEPTION for confrontation if pending.
        """
        active_grievance = await self.get_active_grievance(character_id)

        # Case 1: Active grievance is CONFRONTED, and user apologizes or comforts
        if active_grievance and active_grievance.stage == GrievanceStage.CONFRONTED.value:
            if self.detect_apology_or_comfort(user_input):
                return CognitiveGrievanceContext(
                    grievance_id=active_grievance.id,
                    claimed_assertion=active_grievance.claimed_assertion,
                    verified_truth=active_grievance.verified_truth,
                    deception_type=DeceptionType(active_grievance.deception_type),
                    stage=GrievanceStage.RECONCILING,
                    emotional_tone="tsundere_softening",
                    confrontation_hint=(
                        "用户认错了/正在哄你或请喝奶茶。傲娇地接受道歉并给台阶下："
                        "『看在奶茶的份上这次先放过你，下次再敢骗我绝对不理你了[撇嘴]』，平滑回归日常好友互动。"
                    ),
                )

        # Case 2: User explicitly confesses they tricked/lied to her
        if self.detect_confession(user_input):
            # If an existing grievance exists, use its assertion, else create new
            claimed = active_grievance.claimed_assertion if active_grievance else "之前的玩笑或虚假说法"
            truth = "用户本人主动招供之前纯属忽悠/恶作剧"
            new_rec = await self.record_deception(
                character_id=character_id,
                user_id=user_id,
                claimed_assertion=claimed,
                verified_truth=truth,
                topic_domain="social",
                deception_type=DeceptionType.RETRACTED_CONFESSION,
                confrontation_hint=(
                    "好啊你！自己不打自招了吧！亏我当时还认真信了你，大骗子！快说怎么补偿我[哼][白眼]"
                ),
            )
            return CognitiveGrievanceContext(
                grievance_id=new_rec.id,
                claimed_assertion=new_rec.claimed_assertion,
                verified_truth=new_rec.verified_truth,
                deception_type=DeceptionType.RETRACTED_CONFESSION,
                stage=GrievanceStage.VERIFIED_DECEPTION,
                emotional_tone="playful_indignant",
                confrontation_hint=new_rec.confrontation_hint,
            )

        # Case 3: Pop-culture cross-turn contradiction (昔涟: 原神 -> 崩铁)
        cross_contra = self.detect_cross_turn_contradiction(user_input, history_messages)
        if cross_contra:
            claimed, truth, domain = cross_contra
            new_rec = await self.record_deception(
                character_id=character_id,
                user_id=user_id,
                claimed_assertion=claimed,
                verified_truth=truth,
                topic_domain=domain,
                deception_type=DeceptionType.CROSS_TURN_CONTRADICTION,
                confrontation_hint=(
                    "好啊你！之前还一本正经骗我说昔涟是原神角色，现在自己说漏嘴成崩铁了吧！"
                    "亏我还记下来了，抓到你胡说八道了[哼][白眼]"
                ),
            )
            return CognitiveGrievanceContext(
                grievance_id=new_rec.id,
                claimed_assertion=new_rec.claimed_assertion,
                verified_truth=new_rec.verified_truth,
                deception_type=DeceptionType.CROSS_TURN_CONTRADICTION,
                stage=GrievanceStage.VERIFIED_DECEPTION,
                emotional_tone="playful_indignant",
                confrontation_hint=new_rec.confrontation_hint,
            )

        # Case 4: Outrageous hoax about institutions/school/exams
        hoax = self.detect_outrageous_hoax(user_input)
        if hoax:
            claimed, truth, domain = hoax
            new_rec = await self.record_deception(
                character_id=character_id,
                user_id=user_id,
                claimed_assertion=claimed,
                verified_truth=truth,
                topic_domain=domain,
                deception_type=DeceptionType.OUTRAGEOUS_CLAIM,
                confrontation_hint=(
                    f"好啊你，居然敢忽悠我！我昨晚查过了，学校明明正常上课（{truth}）！"
                    "差点就被你骗去退票了，你这个大忽悠！[哼][白眼]"
                ),
            )
            return CognitiveGrievanceContext(
                grievance_id=new_rec.id,
                claimed_assertion=new_rec.claimed_assertion,
                verified_truth=new_rec.verified_truth,
                deception_type=DeceptionType.OUTRAGEOUS_CLAIM,
                stage=GrievanceStage.VERIFIED_DECEPTION,
                emotional_tone="playful_indignant",
                confrontation_hint=new_rec.confrontation_hint,
            )

        # Case 5: Existing active VERIFIED_DECEPTION awaiting confrontation
        if active_grievance and active_grievance.stage == GrievanceStage.VERIFIED_DECEPTION.value:
            return CognitiveGrievanceContext(
                grievance_id=active_grievance.id,
                claimed_assertion=active_grievance.claimed_assertion,
                verified_truth=active_grievance.verified_truth,
                deception_type=DeceptionType(active_grievance.deception_type),
                stage=GrievanceStage.VERIFIED_DECEPTION,
                emotional_tone=active_grievance.emotional_tone,
                confrontation_hint=active_grievance.confrontation_hint,
            )

        return None
