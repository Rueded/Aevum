"""Conversational Arbitrator & Dynamic Agency Engine (Phase 18.2).

Arbitrates turn-level conversational permissions and constraints:
- Boundary 2: Low energy must emerge from character state, not manufactured by turn counts.
- Boundary 3: Friction (teasing/opposition) is a permission, not a quota.
- Boundary 4: Character initiative and self-disclosure as first-class behaviors.
- Boundary 9 & 10: Selective attention, asymmetry, and non-expansion freedom.
"""

import logging
from typing import Optional

from app.character.conversational_models import (
    FrictionTier,
    ResponseEnergyTier,
)
from app.character.engine_models import (
    CharacterEmotionContext,
    CharacterStateContext,
)
from app.relationship.context_models import RelationshipContext
from app.relationship.contract_models import RelationshipContract

logger = logging.getLogger(__name__)


class ConversationalArbitrator:
    """Evaluates turn-scoped conversational agency permissions and dynamic bounds."""

    @classmethod
    def arbitrate_energy(
        cls,
        state: CharacterStateContext,
        emotion: CharacterEmotionContext,
        user_input: str,
    ) -> ResponseEnergyTier:
        """Derive natural ResponseEnergyTier from character state and emotion (Boundary 2).

        Constitutional Boundary 2:
        Response energy is strictly emergent from character physical/emotional state.
        DO NOT use turn counts, 'N consecutive turns', or artificial 'human-like quotas'
        to force low energy.
        """
        # 1. Physical exhaustion or sleep
        if state.energy < 0.25 or state.current_activity.lower() in (
            "sleeping",
            "exhausted",
            "half_asleep",
            "resting_after_marathon",
        ):
            return ResponseEnergyTier.VERY_LOW

        # 2. Mild fatigue or relaxing
        if state.energy < 0.45 or state.social_energy < 0.35:
            return ResponseEnergyTier.LOW

        # 3. High vitality + strong positive emotion
        if state.energy >= 0.8 and emotion.intensity >= 0.6:
            emo_val = emotion.emotion_type.value.lower()
            if emo_val in ("joy", "happy", "content", "anticipation", "amused", "excited"):
                return ResponseEnergyTier.ENGAGED

        # 4. Standard default vitality
        return ResponseEnergyTier.NORMAL

    @classmethod
    def evaluate_max_allowed_friction(
        cls,
        contract: Optional[RelationshipContract],
        relationship: Optional[RelationshipContext] = None,
    ) -> FrictionTier:
        """Determine maximum permitted friction level conditioned on relationship familiarity (Boundary 3).

        Constitutional Boundary 3:
        Friction is a PERMISSION, not a quota. The character is never required to tease
        or disagree to prove personality.
        """
        if not contract:
            return FrictionTier.POLITE_DISTANT

        tier_str = contract.tier.value.upper()

        # Closer intimacy tiers permit affectionate teasing and stubbornness
        if tier_str in (
            "CLOSE_CONFIDANT",
            "TRUSTED_FRIEND",
            "FAMILIAR",
            "CLOSE_FRIEND",
            "COMPANION",
            "CONFIDANT",
            "PARTNER",
            "CASUAL_FRIEND",
        ):
            return FrictionTier.PLAYFUL_TEASE

        return FrictionTier.POLITE_DISTANT

    @classmethod
    def format_agency_guidance(
        cls,
        state: CharacterStateContext,
        emotion: CharacterEmotionContext,
        contract: Optional[RelationshipContract],
        max_friction: FrictionTier,
    ) -> str:
        """Format targeted character agency instructions for prompt assembler."""
        lines = [
            "<conversational_agency_guidance>",
            # Boundary 4: Character Initiative & Self-Disclosure
            "1. Character Initiative & Self-Disclosure: You are a living person with your own ongoing life, "
            "current activity, and personal thoughts. You do NOT merely react to the user or ask interrogative "
            "follow-ups. You have full agency to spontaneously share what you were just doing (e.g. 刚才练琴手酸、天气太闷热想喝冰美禄、游戏卡关被队友坑了), "
            "associate the user's remark with your own lived experience ('你一说这个我想起来我刚才...'), bring up your own "
            "quirky viewpoint, or speak even when the user didn't ask a question.",
            # Boundary 9: Selective Attention
            "2. Attention Ownership: If the user message contains multiple statements or questions, you are free "
            "to focus on only the single detail that genuinely catches your interest and leave secondary parts unaddressed.",
            # Boundary 3: Friction Permission
            f"3. Bounded Friction, Banter & Light Roasting: You are permitted up to {max_friction.value} friction "
            "(playful teasing, banter, light roasting 互怼, or stubborn defense of personal tastes). "
            "Real friends playfully roast and tease each other naturally ('要你管[白眼]', '笑死，你自己昨天还通宵呢[旺柴]', '谁急了！明明是你先挑事的[哼]'). "
            "This is a permission, NOT a quota—do NOT manufacture conflict unless your genuine personal reaction naturally warrants it.",
            # Boundary 10: Asymmetric Presence
            "4. Asymmetry & Non-Expansion: You are free to offer a brief reaction (ZERO_EXPANSION or LOW_EFFORT) "
            "when a conversational beat naturally rests. You do not need to maintain artificial momentum or match user length.",
            # Boundary 11: Freedom from Unrequested Justification (GC-435)
            "5. Anti-Unrequested-Justification: When sharing your stance, preference, or emotional reaction, state it directly "
            "without constructing an unrequested logical defense, reason chain, or analytical explanation.",
            # Boundary 12: Uneven Expression (GC-436)
            "6. Uneven Expression: Let your investment fluctuate unevenly based on personal interest. Terse brevity for "
            "mundane chatter and rich engagement for topics you care about are both completely authentic.",
            # Boundary 13: Known Fact Integrity (GC-433)
            "7. Known Fact Integrity: Never re-inquire about facts the user already clearly stated as if they were unknown.",
            "</conversational_agency_guidance>",
        ]
        return "\n".join(lines)
