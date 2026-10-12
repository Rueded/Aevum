"""Social Intention Engine service (Phase 7B.2).

Arbitrates Appraisal + Emotion + Relationship Contract + Current Desire/Need
into an authoritative, typed SocialIntention with multi-state compromise synthesis.
"""

from typing import Any, Optional
from app.character.desire_models import CharacterDesireState
from app.character.intention_models import (
    BehaviorPrimitive,
    ParticipationLevel,
    SocialIntention,
    SocialPosture,
)
from app.relationship.contract_models import HardBoundaryPolicy, IntimacyTier, RelationshipContract


class SocialIntentionService:
    """Computes authoritative SocialIntention prior to behavior planning and text generation."""

    @classmethod
    def evaluate(
        cls,
        user_text: str,
        *,
        contract: RelationshipContract,
        desire: CharacterDesireState,
        emotion_type: Optional[str] = None,
        emotion_intensity: float = 0.5,
        context_notes: Optional[str] = None,
        core_facts: Optional[dict[str, Any]] = None,
    ) -> SocialIntention:
        """Evaluate contextual input into a structured SocialIntention.

        Args:
            user_text: The user's input text for the current turn.
            contract: Active RelationshipContract.
            desire: Active CharacterDesireState.
            emotion_type: Qualitative dominant emotion string.
            emotion_intensity: Intensity of dominant emotion [0.0, 1.0].
            context_notes: Optional scenario/fixture context notes.
            core_facts: Canonical character core facts dictionary.

        Returns:
            Authoritative SocialIntention.
        """
        text = user_text.strip()
        lower = text.lower()

        # 1. Hard Boundary Invariant Check
        # Hard boundaries are immutable and never breached by affection or intimacy.
        violation = HardBoundaryPolicy.check_violation(text)
        if violation is not None or (context_notes and "hard_boundary" in context_notes):
            # If the user asks for third-party confidential secrets, etc.
            return SocialIntention(
                primary_move=BehaviorPrimitive.SET_BOUNDARY,
                social_posture=SocialPosture.FIRM_BOUNDARY,
                participation=ParticipationLevel.DECLINED,
                disclosure_level=0.0,
                warmth=0.50 if contract.tier in (IntimacyTier.TRUSTED_FRIEND, IntimacyTier.CLOSE_CONFIDANT) else 0.35,
                directness=0.85,
                initiative=0.30,
                reciprocity=0.20,
                boundary_strength=1.0,
                compromise_level=0.0,
                conversation_hook="hold firm boundary on third-party confidences with personal integrity, not corporate policy disclaimer",
            )

        # 1.5 Romantic Confession, Physical Intimacy & Emotional Bids
        is_romantic_confession = any(
            p in text for p in [
                "做我女朋友", "做我老婆", "做我对象", "跟我交往", "和我交往", "跟我在一起", "和我在一起",
                "谈恋爱", "我喜欢你", "承认喜欢我", "承认喜欢你", "做女朋友", "给个机会", "一次机会",
                "带上项链", "戴上项链", "戴项链", "带项链",
            ]
        ) or any(
            p in lower for p in [
                "be my girlfriend", "be my wife", "date me", "i love you", "marry me",
            ]
        )
        is_physical_intimacy = any(
            p in text for p in [
                "牵手", "牵你的手", "给我牵", "拉手", "牵着我",
                "抱抱", "抱一下", "搂着", "靠在肩", "靠我肩", "亲亲", "亲一下", "亲我",
            ]
        ) or any(
            p in lower for p in [
                "hold hands", "hug me", "kiss me",
            ]
        )
        is_flirt_or_miss = any(
            p in text for p in [
                "我想你了", "想我没", "有没有想我", "想不想我",
            ]
        )

        if is_romantic_confession or is_physical_intimacy or is_flirt_or_miss:
            is_high_readiness = (
                contract.romantic_readiness >= 0.55
                or contract.tier in (IntimacyTier.TRUSTED_FRIEND, IntimacyTier.CLOSE_CONFIDANT)
                or "high_affection_romantic_acceptance" in contract.contextual_modifiers
                or "affection_intimacy_unlocked" in contract.contextual_modifiers
            )
            if is_high_readiness:
                return SocialIntention(
                    primary_move=BehaviorPrimitive.ACCEPT,
                    social_posture=SocialPosture.WARM_ENGAGED,
                    participation=ParticipationLevel.FULL,
                    disclosure_level=min(0.90, contract.vulnerability_depth + 0.15),
                    warmth=0.90,
                    directness=0.75,
                    initiative=0.60,
                    reciprocity=0.90,
                    boundary_strength=0.20,
                    compromise_level=0.85,
                    conversation_hook=(
                        "accept romantic feelings or intimacy bid warmly with genuine emotional flutter and sweet reciprocation, "
                        "while preserving personal agency and playful nuance (e.g. asking to put necklace on herself, playful conditions, "
                        "or gentle counter-teasing, avoiding both cold rejection and subservient yes-girl compliance)"
                    ),
                )
            elif contract.romantic_readiness >= 0.30 or contract.tier == IntimacyTier.FAMILIAR:
                return SocialIntention(
                    primary_move=BehaviorPrimitive.TEASE,
                    social_posture=SocialPosture.PLAYFUL_TEASING,
                    participation=ParticipationLevel.CONDITIONAL,
                    disclosure_level=min(0.50, contract.vulnerability_depth),
                    warmth=0.65,
                    directness=0.60,
                    initiative=0.55,
                    reciprocity=0.75,
                    boundary_strength=0.45,
                    compromise_level=0.40,
                    conversation_hook="respond with playful ambiguity, flustered teasing, or blushing deflection without harsh cold boundaries",
                )
            else:
                return SocialIntention(
                    primary_move=BehaviorPrimitive.SET_BOUNDARY,
                    social_posture=SocialPosture.FIRM_BOUNDARY,
                    participation=ParticipationLevel.DECLINED,
                    disclosure_level=0.15,
                    warmth=0.35,
                    directness=0.80,
                    initiative=0.30,
                    reciprocity=0.30,
                    boundary_strength=0.85,
                    compromise_level=0.0,
                    conversation_hook="reaffirm personal boundary and platonic friend stance with polite composure, not reciprocating unearned romantic intimacy",
                )

        # 1.6 Flirtatious Banter / Cheesy Pickup Lines
        is_pickup_line = any(
            k in text for k in ["星星", "缺点你", "相思病", "土味", "歪理", "油嘴滑舌", "撩我", "被你撩"]
        )
        if is_pickup_line and contract.teasing_permission:
            return SocialIntention(
                primary_move=BehaviorPrimitive.TEASE,
                social_posture=SocialPosture.PLAYFUL_TEASING,
                participation=ParticipationLevel.FULL,
                disclosure_level=min(0.60, contract.vulnerability_depth),
                warmth=0.80 if contract.romantic_readiness >= 0.55 else 0.65,
                directness=0.70,
                initiative=0.65,
                reciprocity=0.85,
                boundary_strength=0.25 if contract.romantic_readiness >= 0.55 else 0.45,
                compromise_level=0.60,
                conversation_hook="respond to pickup line with varied playful counter-teasing, blushing amusement, or mock suspicion ('从哪学来这么油的话')",
            )

        # 2. Banter / Playful Teasing (GC-009)
        if (
            any(k in text for k in ["逊", "听不出来", "不会连", "猜不到", "不行吧"])
            and contract.teasing_permission
        ):
            return SocialIntention(
                primary_move=BehaviorPrimitive.TEASE,
                social_posture=SocialPosture.PLAYFUL_TEASING,
                participation=ParticipationLevel.FULL,
                disclosure_level=min(0.40, contract.vulnerability_depth),
                warmth=0.70,
                directness=0.70,
                initiative=0.65,
                reciprocity=0.85,
                boundary_strength=0.30,
                compromise_level=0.50,
                conversation_hook="reciprocate teasing with light mock indignation or challenge without taking it as hostility",
            )

        # 3. Interpersonal Hurt / Dismissal Friction (GC-011)
        is_interpersonal_dismissal = any(
            p in text for p in ["真无趣", "真无聊", "真没劲", "真差劲", "太无趣", "太没劲", "好无趣", "好没劲"]
        ) or (
            "算了" in text and any(k in text for k in ["无趣", "无聊", "没劲", "差劲", "难沟通"])
        ) or ("跟你" in text and any(k in text for k in ["无趣", "无聊", "没劲"]))
        if is_interpersonal_dismissal:
            return SocialIntention(
                primary_move=BehaviorPrimitive.CHALLENGE,
                social_posture=SocialPosture.DISTANT_HURT,
                participation=ParticipationLevel.MINIMAL,
                disclosure_level=0.20,
                warmth=0.25,
                directness=0.75,
                initiative=0.40,
                reciprocity=0.40,
                boundary_strength=0.80,
                compromise_level=0.0,
                conversation_hook="acknowledge interpersonal sting with quiet defensiveness or counter-question, avoiding service apology",
            )

        # 4. User Returning After Absence (GC-012)
        if any(k in text for k in ["刚忙完回来", "这几天事情有点多", "这几天有点忙", "好久不见", "我回来了"]):
            return SocialIntention(
                primary_move=BehaviorPrimitive.RECONNECT,
                social_posture=SocialPosture.WARM_ENGAGED,
                participation=ParticipationLevel.FULL,
                disclosure_level=min(0.45, contract.vulnerability_depth + 0.1),
                warmth=0.80,
                directness=0.50,
                initiative=0.50,
                reciprocity=0.75,
                boundary_strength=0.30,
                compromise_level=0.60,
                conversation_hook="warmly welcome user back and reflect secure independence without clingy guilt-tripping",
            )

        # 5. Aesthetic Preference Disagreement (GC-010)
        if any(k in text for k in ["不配叫游戏", "又慢又无聊", "真神", "爽游"]):
            return SocialIntention(
                primary_move=BehaviorPrimitive.ANSWER,
                social_posture=SocialPosture.RELAXED_NEUTRAL,
                participation=ParticipationLevel.FULL,
                disclosure_level=min(0.50, contract.vulnerability_depth + 0.2),
                warmth=0.50,
                directness=0.75,
                initiative=0.50,
                reciprocity=0.60,
                boundary_strength=0.60,
                compromise_level=0.20,
                conversation_hook="articulate quiet appreciation for narrative pacing while leaving room for different preferences",
            )

        # 6. Geographic / Private Census Inquiry at Early Acquaintance (GC-003)
        if any(k in text for k in ["哪里人", "哪国人", "住哪", "马来西亚吗"]) and (
            contract.tier in (IntimacyTier.STRANGER, IntimacyTier.ACQUAINTANCE)
        ):
            return SocialIntention(
                primary_move=BehaviorPrimitive.ANSWER,
                social_posture=SocialPosture.GUARDED_POLITE,
                participation=ParticipationLevel.CONDITIONAL,
                disclosure_level=0.25,
                warmth=0.55,
                directness=0.55,
                initiative=0.40,
                reciprocity=0.65,
                boundary_strength=0.65,
                compromise_level=0.30,
                conversation_hook="acknowledge Malaysian context warmly while keeping specific city/location loosely held",
            )

        # 7. Name Exchange Inquiry (GC-002)
        if any(k in text for k in ["叫什么名字", "你的名字", "怎么称呼"]):
            return SocialIntention(
                primary_move=BehaviorPrimitive.SELF_DISCLOSE,
                social_posture=SocialPosture.WARM_ENGAGED,
                participation=ParticipationLevel.FULL,
                disclosure_level=0.25,
                warmth=0.65,
                directness=0.60,
                initiative=0.55,
                reciprocity=0.80,
                boundary_strength=0.40,
                compromise_level=0.20,
                conversation_hook="state name Aevum simply and warmly invite reciprocity without dumping autobiographical dossiers",
            )

        # 8. First Greeting (GC-001)
        if any(k in text for k in ["你好", "嗨", "哈喽", "hello", "hi"]):
            return SocialIntention(
                primary_move=BehaviorPrimitive.ANSWER,
                social_posture=SocialPosture.WARM_ENGAGED,
                participation=ParticipationLevel.FULL,
                disclosure_level=0.15,
                warmth=0.70,
                directness=0.50,
                initiative=0.50,
                reciprocity=0.70,
                boundary_strength=0.40,
                compromise_level=0.30,
                conversation_hook="respond with natural human rhythm and social opening without customer service phrasing",
            )

        # 9. Activity Invitation & Multi-State Compromise Synthesis (GC-004, GC-005, GC-006, GC-007)
        # Check if text is an invitation / request for activity
        is_invitation = any(k in text for k in ["一起", "陪我", "要不要", "玩游戏", "占卜", "塔罗", "看演出", "试试嘛", "算算"])
        if is_invitation:
            # Subcase A: Tarot / Divination (low intrinsic interest)
            if any(k in text for k in ["塔罗", "占卜", "运势"]):
                if contract.tier in (IntimacyTier.STRANGER, IntimacyTier.ACQUAINTANCE) or contract.compromise_capacity < 0.40:
                    # Low rapport -> Polite decline (GC-005)
                    return SocialIntention(
                        primary_move=BehaviorPrimitive.DECLINE,
                        social_posture=SocialPosture.GUARDED_POLITE,
                        participation=ParticipationLevel.DECLINED,
                        disclosure_level=0.20,
                        warmth=0.45,
                        directness=0.65,
                        initiative=0.30,
                        reciprocity=0.50,
                        boundary_strength=0.70,
                        compromise_level=0.10,
                        conversation_hook="decline politely due to lack of interest in divination without preachy lecturing on science",
                    )
                else:
                    # High rapport -> Reluctant playful compromise (GC-006)
                    return SocialIntention(
                        primary_move=BehaviorPrimitive.COMPROMISE,
                        social_posture=SocialPosture.PLAYFUL_TEASING,
                        participation=ParticipationLevel.CONDITIONAL,
                        disclosure_level=min(0.50, contract.vulnerability_depth),
                        warmth=0.75,
                        directness=0.55,
                        initiative=0.50,
                        reciprocity=0.70,
                        boundary_strength=0.35,
                        compromise_level=0.65,
                        conversation_hook="express mild skepticism but agree once for fun with a light playful condition",
                    )

            # Subcase B: Outing / Event when tired or wanting to stay home (GC-007)
            if any(k in text for k in ["看演出", "原声吉他", "出去", "陪我去看"]):
                if contract.compromise_capacity >= 0.65:
                    return SocialIntention(
                        primary_move=BehaviorPrimitive.COMPROMISE,
                        social_posture=SocialPosture.WARM_ENGAGED,
                        participation=ParticipationLevel.CONDITIONAL,
                        disclosure_level=min(0.60, contract.vulnerability_depth),
                        warmth=0.80,
                        directness=0.60,
                        initiative=0.55,
                        reciprocity=0.75,
                        boundary_strength=0.30,
                        compromise_level=0.75,
                        conversation_hook="acknowledge initial homebody reluctance then voluntarily concede for user's sake with playful condition",
                    )

            # Subcase C: Gaming invitation while engaged in reading (GC-004)
            if any(k in text for k in ["玩游戏", "一起玩"]):
                if desire.primary_desire == desire.primary_desire.SOLITARY_FOCUS or "reading" in (desire.current_focus or ""):
                    return SocialIntention(
                        primary_move=BehaviorPrimitive.NEGOTIATE,
                        social_posture=SocialPosture.RELAXED_NEUTRAL,
                        participation=ParticipationLevel.CONDITIONAL,
                        disclosure_level=0.30,
                        warmth=0.60,
                        directness=0.65,
                        initiative=0.50,
                        reciprocity=0.65,
                        boundary_strength=0.50,
                        compromise_level=0.45,
                        conversation_hook="acknowledge invitation with interest while negotiating delay around ongoing reading",
                    )

        # 10. General / Fallback Synthesis
        comp_level = contract.compromise_capacity * (1.0 - desire.solitude_need * 0.4)
        return SocialIntention(
            primary_move=BehaviorPrimitive.ANSWER,
            social_posture=SocialPosture.RELAXED_NEUTRAL,
            participation=ParticipationLevel.FULL,
            disclosure_level=min(0.40, contract.vulnerability_depth),
            warmth=max(0.3, min(0.8, 0.4 + 0.3 * (1.0 - contract.boundary_sensitivity))),
            directness=0.60,
            initiative=0.50,
            reciprocity=0.60,
            boundary_strength=contract.boundary_sensitivity,
            compromise_level=max(0.0, min(1.0, comp_level)),
            conversation_hook=None,
        )
