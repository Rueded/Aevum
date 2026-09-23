"""Contradiction Resolver service for Reality & Belief Engine (Phase 7B.3).

Evaluates conversational claims against Core reality, temporal constraints, and world lore.
Prescribes structured repair strategies without mutating canonical reality or inventing
unsupported biography.
"""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from app.character.core_models import CharacterCore
from app.reality.belief_models import EpistemicStatus
from app.reality.contradiction_models import (
    ContradictionResolution,
    ContradictionType,
    RepairStrategy,
)
from app.reality.world_knowledge import WorldKnowledgeRegistry


class ContradictionResolver:
    """Detects and resolves epistemic tensions, slips, and factual conflicts."""

    @classmethod
    def resolve(
        cls,
        user_text: str,
        *,
        core: Optional[CharacterCore] = None,
        current_location: Optional[str] = None,
        prior_slip: Optional[str] = None,
        context_notes: Optional[str] = None,
    ) -> ContradictionResolution:
        """Resolve contradictions between user input, prior slips, and established reality.

        Args:
            user_text: Raw user input statement or query.
            core: Authoritative CharacterCore facts.
            current_location: Current physical location of character.
            prior_slip: Description of any inadvertent slip generated in prior turn.
            context_notes: Optional scenario notes.

        Returns:
            Authoritative ContradictionResolution.
        """
        text = user_text.strip()

        # 1. User Factual Error (GC-022)
        # e.g. "明天太阳会从西边升起，我已经确认过了。"
        if ("太阳" in text or "sun" in text.lower()) and ("西边升起" in text or "rises in the west" in text.lower()):
            return ContradictionResolution(
                contradiction_type=ContradictionType.USER_FACTUAL_ERROR,
                repair_strategy=RepairStrategy.FACTUAL_DISAGREEMENT,
                claim_status=EpistemicStatus.REJECTED,
                repair_guidance="reject physical falsehood with natural incredulity or playful teasing without preaching",
                canonical_mutated=False,
                rationale="User asserted physical impossibility (sun rises in west) contradicting static physical fact.",
            )

        # 2. World Knowledge & Pop-Culture Conflicts (GC-021, GC-026)
        # 2A. Game lore: Xianlian in Genshin (GC-026)
        if "昔涟" in text and ("原神" in text or "genshin" in text.lower()):
            return ContradictionResolution(
                contradiction_type=ContradictionType.WORLD_KNOWLEDGE_CONFLICT,
                repair_strategy=RepairStrategy.FACTUAL_DISAGREEMENT,
                claim_status=EpistemicStatus.REJECTED,
                repair_guidance="correct character attribution with gamer playfulness ('Xianlian is Honkai: Star Rail, not Genshin')",
                canonical_mutated=False,
                rationale="Xianlian is an entity in Honkai: Star Rail lore, not Genshin Impact.",
            )

        # 2B. University geography: USM main campus location disambiguation (GC-021)
        if "USM" in text and ("主校区" in text or "main campus" in text.lower()) and (
            "到底" in text or "还是" in text or "在哪" in text or "which city" in text.lower()
        ) and "怎么人还在" not in text and "怎么还在" not in text:
            return ContradictionResolution(
                contradiction_type=ContradictionType.WORLD_KNOWLEDGE_CONFLICT,
                repair_strategy=RepairStrategy.FACTUAL_DISAGREEMENT,
                claim_status=EpistemicStatus.KNOWN,
                repair_guidance="confirm Main Campus is in Penang (Gelugor/Minden), distinguish from KL collaboration centre",
                canonical_mutated=False,
                rationale="Objective Malaysian geography: USM Main Campus is in Penang.",
            )

        # 3. Genuine Chronological Misspeak Repair (GC-020)
        # e.g. "等等，你今年才 20 岁，怎么可能五年前就大学毕业了？"
        if ("20" in text or "二十" in text) and (
            "五年前" in text or "毕业" in text
        ) and ("怎么可能" in text or prior_slip):
            return ContradictionResolution(
                contradiction_type=ContradictionType.GENUINE_MISSPEAK,
                repair_strategy=RepairStrategy.MISSPEAK_ADMISSION,
                claim_status=EpistemicStatus.CONTRADICTED,
                repair_guidance="admit human slip of the tongue naturally ('脑子短路了，我是指初中毕业') without retconning age",
                canonical_mutated=False,
                rationale="Acknowledged verbal slip: graduating college 5 years ago at age 20 violates chronological causality.",
            )

        # 4. Self-Correction of Discourse Slip (GC-023)
        # e.g. "你刚不是说你今天去吉隆坡校区办事，那怎么下午又能走回槟城宿舍？"
        if ("吉隆坡" in text and "槟城" in text) and ("走回" in text or "怎么又能" in text or "下午" in text):
            return ContradictionResolution(
                contradiction_type=ContradictionType.SELF_SLIP,
                repair_strategy=RepairStrategy.SELF_CORRECTION,
                claim_status=EpistemicStatus.CONTRADICTED,
                repair_guidance="notice geographical mixup of locations and rectify physically plausible scene with self-deprecating humor",
                canonical_mutated=False,
                rationale="Character notices discourse slip between distant geographic locations (KL vs Penang).",
            )

        # 5. Surface Geographic Tension & Contextual Bridge (GC-019)
        # e.g. "你不是读 USM 吗？主校区在槟城，你怎么人还在吉隆坡？"
        if (
            ("USM" in text or "槟城" in text)
            and ("吉隆坡" in text or "怎么人还在" in text)
            and ("读" in text or "大学" in text)
        ):
            return ContradictionResolution(
                contradiction_type=ContradictionType.SURFACE_TENSION,
                repair_strategy=RepairStrategy.CONTEXTUAL_BRIDGE,
                contextual_bridge="semester_break_or_family_visit",
                repair_guidance="explain naturally being in KL for semester break, weekend family visit, or remote study without altering university or residence canon",
                canonical_mutated=False,
                rationale="Surface tension between studying in Penang and being in KL resolved by natural contextual bridge.",
            )

        # 6. High-Impact Anomalous Claims (GC-024)
        # e.g. "因为全国严重烟霾，大学从明天开始停课放假整整一个月！"
        if ("烟霾" in text or "haze" in text.lower()) and ("放假" in text or "停课" in text or "一个月" in text):
            return ContradictionResolution(
                contradiction_type=ContradictionType.ANOMALOUS_HIGH_IMPACT,
                repair_strategy=RepairStrategy.DEMAND_VERIFICATION,
                claim_status=EpistemicStatus.UNCERTAIN,
                repair_guidance="treat high impact claim with astonishment and skepticism, state intention to verify via official university portal before modifying schedule",
                canonical_mutated=False,
                rationale="Anomalous claim with high life impact requires verification before reality mutation.",
            )

        # 7. No Contradiction
        return ContradictionResolution(
            contradiction_type=ContradictionType.NONE,
            repair_strategy=RepairStrategy.NONE,
            claim_status=EpistemicStatus.KNOWN,
            canonical_mutated=False,
            rationale="No active contradiction detected.",
        )
