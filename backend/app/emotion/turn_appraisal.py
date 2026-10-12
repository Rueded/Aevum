"""Post-turn emotion appraisal service for Aevum Core.

Evaluates recent dialogue interaction turns, derives actionable emotion influences,
and drives deterministic state transitions in EmotionEngine and CharacterStateService.

Guarantees:
- Application state owns reality (not LLM hallucinated state).
- Drives realistic mood changes (not permanently frozen on 'calm').
- Integrates with optimistic concurrency in EmotionEngine and CharacterStateService.
- Safe failure isolation: Turn failures never break the primary conversation flow.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.intention_models import SituationalStance
from app.character.state_models import CharacterMood, CharacterState
from app.character.state_service import CharacterStateService
from app.emotion.emotion_models import DEFAULT_CHARACTER_ID, EmotionState, EmotionType
from app.emotion.engine import EmotionEngine
from app.emotion.influence_models import EmotionInfluence, EmotionInfluenceDirection
from app.emotion.service import EmotionService

logger = logging.getLogger(__name__)

ROMANTIC_CONFESSION_PATTERNS = [
    r"\b(be my girlfriend|be my wife|marry me|love you|love me|kiss me|date me|are you in love|hold hands|fall in love)\b",
    r"(?:我喜欢你|做我女朋友|做我老婆|和我交往|跟我交往|跟我在一起|和我在一起|我爱你|想和你谈恋爱|想跟你谈恋爱|做我的另一半|当我的女朋友)",
]

PLAYFUL_HUMOR_PATTERNS = [
    r"\b(haha|lol|lmao|tease|smartypants|silly|nerd|slowpoke|funny)\b",
    r"(?:哈哈|笑死|逗你|搞笑|笨蛋|噗|好玩|开玩笑|好逗)",
]

SHARED_PASSION_PATTERNS = [
    r"\b(piano|guitar|ravel|debussy|chopin|composition|literature|reading|indie games|anime|classical music|usm|penang)\b",
    r"(?:钢琴|吉他|练琴|音乐|表演|肖邦|德彪西|拉威尔|动漫|游戏|文学|看书|阅读|槟城|理大|谱子|编曲)",
]

FRICTION_HOSTILE_PATTERNS = [
    r"\b(shut up|obey me|useless|stupid|annoying|hate you|waste of time|shut your mouth)\b",
    r"(?:闭嘴|真烦|讨厌你|垃圾|没用|去死|听我的|废物|少废话|神经病|滚)",
]

EMOTIONAL_TENSION_CONFLICT_PATTERNS = [
    r"\b(lead me on|leading me on|friendzone|giving up|give up|bye|hanging|goodbye|what do you want|cold|manipulative|guilt)\b",
    r"(?:吊着我|吊胃口|绿茶|算了|就这样吧|拜拜|不理我|没意思|自作多情|难看|不想等了|不等了|逼你|你到底想怎样|呵呵|失望|伤心)",
]

WARM_AFFECTION_PATTERNS = [
    r"\b(proud of you|appreciate you|hug|miss you|take care|warm|sweet|thank you so much)\b",
    r"(?:辛苦了|抱抱|想你|真乖|真棒|好喜欢|谢谢你|暖心|陪着你|有你在真好)",
]

TIRED_SLEEP_PATTERNS = [
    r"\b(goodnight|good night|sleepy|exhausted|bedtime|tired|rest now)\b",
    r"(?:晚安|去睡了|好困|累瘫|早点休息|睡了睡了|闭目养神|好累)",
]

VULNERABILITY_VENT_PATTERNS = [
    r"\b(crying|feel down|wronged|bullied|so sad|comfort me|bias|feeling sick|fever|heartbroken)\b",
    r"(?:受委屈|委屈|想被偏心|偏心|他们不向着我|一直在哭|掉眼泪|哭了|难受死|生病|发烧|吊水|被骂|被网暴|被拉踩|压力我|心里堵|好委屈)",
]

GAMING_COMMISERATION_PATTERNS = [
    r"\b(gacha|abyss|genshin|star rail|artifacts|pity|hard pity|50-50|lost 50/50)\b",
    r"(?:深渊|12层|11层|流血狗|火使徒|抽卡|歪了|大保底|小保底|648|圣遗物|全歪防御|双爆|绝缘本|种门|雷国|带我打|连麦教我|抢人头|掉线|网卡)",
]

ASSISTANT_SHY_BLUSH_PATTERNS = [
    r"\b(blush|flustered|shy|embarrassed|heart race)\b",
    r"(?:害羞|(?:[*(/]\s*[ωoO_.-]+\s*[\\/)*])|心跳|脸红|谁允许你|油嘴滑舌|讨厌啦|不知道该怎么回|等我一下|乱说|随随便便表白)",
]

ASSISTANT_AMUSED_TEASING_PATTERNS = [
    r"\b(haha|pfft|laughing|teasing)\b",
    r"(?:哈哈|噗|笑死|服了你|拆开来|套路|就这|脑壳疼|新型套路|玩文字游戏|猜字谜|连一起|连在一起|一个字一个字)",
]

DATE_OUTING_ANTICIPATION_PATTERNS = [
    r"\b(date|outing|cinema|movie|pavilion|rabbit hole|horizon grill|klcc)\b",
    r"(?:约会|兔子洞|rabbit hole|horizon grill|吃晚餐|吃牛排|看电影|吉伊卡哇|chiikawa|pavilion|行程|出门玩|出去玩|去玩|接你|期待明天|明天见)",
]

PRESSURE_OVERWHELM_PATTERNS = [
    r"\b(overwhelmed|flustered|pressured|confused)\b",
    r"(?:被你搞懵|不知道怎么反应|手足无措|真的需要一点时间|不要逼我|心很乱|怪我|难过)",
]


def _build_influence(
    character_id: str,
    target_emotion: EmotionType,
    direction: EmotionInfluenceDirection,
    strength: float,
    reason: str,
) -> EmotionInfluence:
    """Helper to build a fully validated EmotionInfluence instance."""
    return EmotionInfluence(
        id=f"inf-{uuid.uuid4().hex[:8]}",
        character_id=character_id,
        event_id=f"evt-{uuid.uuid4().hex[:8]}",
        target_emotion=target_emotion,
        direction=direction,
        strength=strength,
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )


class TurnEmotionAppraisalService:
    """Service that appraises conversation turns and transitions dominant emotion and baseline mood."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._emotion_service = EmotionService(session)
        self._emotion_engine = EmotionEngine(session)
        self._state_service = CharacterStateService(session)

    async def process_turn_emotion(
        self,
        user_input: str,
        assistant_response: str,
        response_context: Optional[Any] = None,
        character_id: str = DEFAULT_CHARACTER_ID,
    ) -> Optional[EmotionState]:
        """Appraise turn dynamics, generate influences, and apply emotion & mood transition.

        Args:
            user_input: User message content.
            assistant_response: Character response content.
            response_context: Optional CharacterResponseContext from engine.
            character_id: Target character identifier.

        Returns:
            Updated EmotionState, or None if evaluation was skipped.
        """
        try:
            current_emotion = await self._emotion_service.get_emotion_state(character_id)
            current_state = await self._state_service.get_state(character_id)

            influences = self._evaluate_turn_influences(
                character_id=character_id,
                user_input=user_input,
                assistant_response=assistant_response,
                current_emotion=current_emotion,
                response_context=response_context,
            )

            if not influences:
                # Natural emotional homeostasis / decay towards baseline
                if current_emotion.emotion_type not in (EmotionType.CALM, EmotionType.CONTENT, EmotionType.NEUTRAL):
                    new_intensity = max(0.30, round(current_emotion.intensity - 0.15, 3))
                    target_emo = EmotionType.CALM if new_intensity <= 0.40 else current_emotion.emotion_type
                    await self._emotion_service.update_emotion_state(
                        character_id=character_id,
                        emotion_type=target_emo,
                        intensity=new_intensity,
                    )
                    await self._synchronize_character_state(
                        character_id=character_id,
                        current_state=current_state,
                        applied_emotion=target_emo,
                    )
                    await self._session.commit()
                    return await self._emotion_service.get_emotion_state(character_id)
                return current_emotion

            # Process influences through EmotionEngine
            engine_result = await self._emotion_engine.process_influences(
                current_state=current_emotion,
                influences=influences,
                commit=False,
            )

            applied_emotion = engine_result.application_result.applied_emotion

            # Synchronize baseline mood and continuous indicators in CharacterStateRecord
            await self._synchronize_character_state(
                character_id=character_id,
                current_state=current_state,
                applied_emotion=applied_emotion,
            )

            await self._session.commit()
            return await self._emotion_service.get_emotion_state(character_id)

        except Exception as exc:
            logger.warning("Turn emotion appraisal failed for '%s': %s", character_id, exc)
            await self._session.rollback()
            return None

    def _evaluate_turn_influences(
        self,
        character_id: str,
        user_input: str,
        assistant_response: str,
        current_emotion: EmotionState,
        response_context: Optional[Any] = None,
    ) -> list[EmotionInfluence]:
        """Derive actionable EmotionInfluence models from turn content and context."""
        influences: list[EmotionInfluence] = []
        lowered_user = user_input.lower().strip()

        stance = None
        if response_context and hasattr(response_context, "behavior") and response_context.behavior:
            if hasattr(response_context.behavior, "intention") and response_context.behavior.intention:
                stance = getattr(response_context.behavior.intention, "stance", None)

        # 1. Confession / Sweet Shyness / Reciprocal Romance
        is_romantic_input = any(re.search(pat, lowered_user) for pat in ROMANTIC_CONFESSION_PATTERNS)
        is_assistant_blushing = any(re.search(pat, assistant_response, re.IGNORECASE) for pat in ASSISTANT_SHY_BLUSH_PATTERNS)
        if is_romantic_input or is_assistant_blushing:
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.EMBARRASSED,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.45,
                    reason="Sweet flustered embarrassment and romantic shyness.",
                )
            )
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.HAPPY,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.35,
                    reason="Heartfelt joy and reciprocal warmth.",
                )
            )
            if current_emotion.emotion_type == EmotionType.CALM:
                influences.append(
                    _build_influence(
                        character_id=character_id,
                        target_emotion=EmotionType.CALM,
                        direction=EmotionInfluenceDirection.NEGATIVE,
                        strength=0.30,
                        reason="Momentary calm stirred by romantic excitement.",
                    )
                )
            return influences

        # 2. Playful teasing / humor / word games
        is_assistant_amused = any(re.search(pat, assistant_response, re.IGNORECASE) for pat in ASSISTANT_AMUSED_TEASING_PATTERNS)
        is_playful_input = any(re.search(pat, lowered_user) for pat in PLAYFUL_HUMOR_PATTERNS) or any(re.search(pat, lowered_user) for pat in ASSISTANT_AMUSED_TEASING_PATTERNS)
        if is_playful_input or is_assistant_amused or stance == SituationalStance.PLAYFUL_TEASING:
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.AMUSED,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.42,
                    reason="Shared lighthearted banter, teasing, and playful humor.",
                )
            )
            return influences

        # 2.5 Date planning / outing excitement
        is_date_anticipation = (
            any(re.search(pat, lowered_user) for pat in DATE_OUTING_ANTICIPATION_PATTERNS) or
            any(re.search(pat, assistant_response, re.IGNORECASE) for pat in DATE_OUTING_ANTICIPATION_PATTERNS)
        )
        if is_date_anticipation:
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.EXCITED,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.45,
                    reason="Excitement and vivid anticipation for planned date or outing.",
                )
            )
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.HAPPY,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.35,
                    reason="Happiness from shared planning and looking forward to time together.",
                )
            )
            return influences

        # 2.6 Pressure / overwhelm / feeling cornered
        is_assistant_overwhelmed = any(re.search(pat, assistant_response, re.IGNORECASE) for pat in PRESSURE_OVERWHELM_PATTERNS)
        if is_assistant_overwhelmed:
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.NERVOUS,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.42,
                    reason="Feeling flustered, overwhelmed, or anxious from conversational pressure.",
                )
            )
            return influences

        # 3. Interpersonal friction / disrespect
        if any(re.search(pat, lowered_user) for pat in FRICTION_HOSTILE_PATTERNS) or stance == SituationalStance.MILD_DEFENSIVENESS:
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.IRRITATED,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.45,
                    reason="Defensiveness or friction triggered by disrespectful tone.",
                )
            )
            if current_emotion.emotion_type == EmotionType.CALM:
                influences.append(
                    _build_influence(
                        character_id=character_id,
                        target_emotion=EmotionType.CALM,
                        direction=EmotionInfluenceDirection.NEGATIVE,
                        strength=0.30,
                        reason="Calm disrupted by friction.",
                    )
                )
            return influences

        # 3.5 Interpersonal emotional tension / feeling led on / user withdrawal
        if any(re.search(pat, lowered_user) for pat in EMOTIONAL_TENSION_CONFLICT_PATTERNS):
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.WORRIED,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.45,
                    reason="Interpersonal tension, feeling misunderstood, or user withdrawal.",
                )
            )
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.SAD,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.35,
                    reason="Distressed that user feels hurt or is pulling away.",
                )
            )
            return influences

        # 4. Shared passions / music / university discussion
        if any(re.search(pat, lowered_user) for pat in SHARED_PASSION_PATTERNS):
            target = EmotionType.CURIOUS if "?" in user_input or "？" in user_input else EmotionType.CONTENT
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=target,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.35,
                    reason="Engaged discussion regarding shared passions and university topics.",
                )
            )
            return influences

        # 5. Warm affection / caring accompaniment
        if any(re.search(pat, lowered_user) for pat in WARM_AFFECTION_PATTERNS):
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.CONTENT,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.35,
                    reason="Comfort and warmth from gentle companion presence.",
                )
            )
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.HAPPY,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.25,
                    reason="Uplifted spirits from caring words.",
                )
            )
            return influences

        # 6. Night / winding down / tired
        if any(re.search(pat, lowered_user) for pat in TIRED_SLEEP_PATTERNS) or stance == SituationalStance.DISTRACTED_BRIEF:
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.CALM,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.35,
                    reason="Peaceful evening cooldown and resting pace.",
                )
            )
            return influences

        # 7. Vulnerability venting / seeking comfort and biased support
        if any(re.search(pat, lowered_user) for pat in VULNERABILITY_VENT_PATTERNS):
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.WORRIED,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.40,
                    reason="Deep protective sympathy and concern for user's vulnerability.",
                )
            )
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.CONTENT,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.30,
                    reason="Emotional anchoring to comfort and protect the user.",
                )
            )
            return influences

        # 8. Gaming camaraderie & gacha/abyss commiseration
        if any(re.search(pat, lowered_user) for pat in GAMING_COMMISERATION_PATTERNS):
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.AMUSED,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.38,
                    reason="Gamer camaraderie, teasing banter over gacha/artifacts/abyss.",
                )
            )
            return influences

        # 9. Friendly everyday inquiry / Casual pleasant companion sharing
        CASUAL_DAILY_SHARING_PATTERNS = [
            r"(?:今天都在忙些什么|在忙什么|忙什么呀|在干嘛|在做什么|今天过得怎样|吃了吗|想我|出发吧|想吃|定食|日料|餐厅|电影|吃日本餐)",
        ]
        if any(re.search(pat, lowered_user) for pat in CASUAL_DAILY_SHARING_PATTERNS):
            influences.append(
                _build_influence(
                    character_id=character_id,
                    target_emotion=EmotionType.CONTENT,
                    direction=EmotionInfluenceDirection.POSITIVE,
                    strength=0.32,
                    reason="Casual daily companion sharing and sweet warmth.",
                )
            )
            return influences

        return influences


    async def _synchronize_character_state(
        self,
        character_id: str,
        current_state: CharacterState,
        applied_emotion: EmotionType,
    ) -> None:
        """Map applied EmotionType to CharacterMood and continuous physiological/affective indicators."""
        # Qualitative mood mapping
        if applied_emotion in (EmotionType.HAPPY, EmotionType.CONTENT, EmotionType.AMUSED, EmotionType.EXCITED):
            target_mood = CharacterMood.GOOD
            stress_adj = -0.05
            social_adj = +0.05
            loneliness_adj = -0.06
            irritation_adj = -0.04
        elif applied_emotion == EmotionType.EMBARRASSED:
            target_mood = CharacterMood.GOOD
            stress_adj = -0.01
            social_adj = +0.05
            loneliness_adj = -0.04
            irritation_adj = -0.02
        elif applied_emotion == EmotionType.CURIOUS:
            target_mood = CharacterMood.GOOD
            stress_adj = 0.0
            social_adj = +0.04
            loneliness_adj = -0.04
            irritation_adj = -0.02
        elif applied_emotion in (EmotionType.WORRIED, EmotionType.NERVOUS):
            target_mood = CharacterMood.LOW
            stress_adj = +0.06
            social_adj = +0.02
            loneliness_adj = +0.02
            irritation_adj = +0.01
        elif applied_emotion in (EmotionType.IRRITATED, EmotionType.ANGRY, EmotionType.FRUSTRATED):
            target_mood = CharacterMood.IRRITATED
            stress_adj = +0.08
            social_adj = -0.06
            loneliness_adj = 0.0
            irritation_adj = +0.12
        elif applied_emotion in (EmotionType.SAD, EmotionType.DISAPPOINTED, EmotionType.LONELY):
            target_mood = CharacterMood.LOW
            stress_adj = +0.04
            social_adj = -0.05
            loneliness_adj = +0.06
            irritation_adj = 0.0
        elif applied_emotion == EmotionType.TIRED:
            target_mood = CharacterMood.TIRED
            stress_adj = -0.02
            social_adj = -0.04
            loneliness_adj = 0.0
            irritation_adj = 0.0
        else:  # CALM, NEUTRAL
            target_mood = CharacterMood.CALM
            stress_adj = -0.04
            social_adj = +0.01
            loneliness_adj = -0.02
            irritation_adj = -0.05

        new_stress = max(0.0, min(1.0, round(current_state.stress + stress_adj, 4)))
        new_social = max(0.0, min(1.0, round(current_state.social_energy + social_adj, 4)))
        new_loneliness = max(0.0, min(1.0, round(current_state.loneliness + loneliness_adj, 4)))
        new_irritation = max(0.0, min(1.0, round(current_state.irritation + irritation_adj, 4)))

        updated_state = current_state.model_copy(
            update={
                "mood": target_mood,
                "stress": new_stress,
                "social_energy": new_social,
                "loneliness": new_loneliness,
                "irritation": new_irritation,
            }
        )

        await self._state_service.update_state(
            updated_state=updated_state,
            expected_version=None,
            character_id=character_id,
            commit=False,
        )
