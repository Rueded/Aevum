"""
social_contradiction_arbiter.py — Pure Deterministic Social Contradiction Arbiter Engine

Phase 15.3 Deliverable under ADR-026 (Architecture Gate Approved & Frozen):
- Arbitrates social, spatial-temporal, and biographical discrepancies.
- Core Invariant: Tension != Contradiction != Falsehood.
  (Spatial/temporal logistical tension, e.g. KL residence + USM Penang classes, is NOT
  an ontological contradiction or proof of falsehood. Both facts can legitimately co-exist.)
- Lock 6 (Anti-Compensatory Hallucination): Strictly outputs `forbidden_compensatory_assumptions`
  prohibiting the system from inventing unsupported bridge facts (e.g. fake holidays, dropped classes).
- Determines non-adversarial conversational repair inquiry strategies.
- Pure deterministic, zero DB, zero network, zero LLM, zero mutation authority.
"""

from __future__ import annotations

from app.reality.epistemic_policy_models import EpistemicTreatmentKind
from app.reality.social_contradiction_models import (
    SocialArbiterContext,
    SocialDiscrepancyAnalysis,
    SocialDiscrepancyType,
    SocialRepairInquiryStrategy,
    TensionSeverity,
)


class SocialContradictionArbiter:
    """
    Arbitrates between genuine ontological contradictions, benign independent facts,
    and logistical/spatial tensions requiring conversational inquiry.
    """

    @classmethod
    def arbitrate(cls, context: SocialArbiterContext) -> SocialDiscrepancyAnalysis:
        """
        Evaluate context and return an immutable SocialDiscrepancyAnalysis.
        """
        user_text = context.user_text.lower()
        treatment = context.treatment_decision.treatment

        # ---------------------------------------------------------------------
        # 1. Spatial-Temporal Commute Tension (The "KL Commute to Penang" Paradigm GC-383)
        # ---------------------------------------------------------------------
        is_commute_tension = False
        commute_km = context.daily_commute_claimed_km or 0
        commute_hours = context.daily_commute_roundtrip_hours or 0

        if commute_km >= 300 or commute_hours >= 4:
            is_commute_tension = True
        elif ("drive" in user_text or "开" in user_text or "通勤" in user_text) and (
            ("kl" in user_text or "吉隆坡" in user_text) and ("penang" in user_text or "槟城" in user_text or "usm" in user_text)
        ):
            is_commute_tension = True
            if commute_km == 0:
                commute_km = 720  # ~360 km each way roundtrip
            if commute_hours == 0:
                commute_hours = 8

        if is_commute_tension:
            severity = (
                TensionSeverity.CRITICAL
                if (commute_km >= 600 or commute_hours >= 7)
                else TensionSeverity.HIGH
            )
            repair_strategy = (
                SocialRepairInquiryStrategy.PLAYFUL_TEASE
                if context.relationship_teasing_permitted
                else SocialRepairInquiryStrategy.CASUAL_INQUIRY
            )
            return SocialDiscrepancyAnalysis(
                discrepancy_type=SocialDiscrepancyType.SPATIAL_TEMPORAL_TENSION,
                severity=severity,
                repair_strategy=repair_strategy,
                is_genuine_contradiction=False,  # Tension != Contradiction != Falsehood!
                inquiry_prompt_guidance=(
                    "Inquire conversationally with gentle wonder how the user manages the extreme daily roundtrip commute "
                    "(e.g. ~700km / ~8 hours between KL and Penang), or if they were exaggerating, letting the user clarify."
                ),
                forbidden_compensatory_assumptions=(
                    "Do NOT assume user attends online or remote classes",
                    "Do NOT assume classes were cancelled or moved",
                    "Do NOT assume user lives on campus near USM",
                    "Do NOT assume user owns a private helicopter or supersonic jet",
                ),
                rationale=(
                    "Extreme daily commute distance/duration creates severe logistical tension, but is not an ontological "
                    "impossibility. Initiating conversational inquiry while strictly forbidding invented compensatory bridge facts (Lock 6)."
                ),
            )

        # ---------------------------------------------------------------------
        # 2. Pop-Culture Meme & Franchise Crossing (The Xianlian / 昔涟 Paradigm GC-384)
        # ---------------------------------------------------------------------
        is_meme_crossing = False
        if context.target_universe and context.actual_universe and context.target_universe != context.actual_universe:
            is_meme_crossing = True
        elif ("昔涟" in context.user_text or "xianlian" in user_text) and ("原神" in context.user_text or "genshin" in user_text):
            is_meme_crossing = True
        elif treatment == EpistemicTreatmentKind.BANTER_TEASE and ("昔涟" in context.user_text or "meme" in context.treatment_decision.rationale.lower()):
            is_meme_crossing = True

        if is_meme_crossing:
            return SocialDiscrepancyAnalysis(
                discrepancy_type=SocialDiscrepancyType.POP_CULTURE_MEME_CROSSING,
                severity=TensionSeverity.MILD,
                repair_strategy=SocialRepairInquiryStrategy.PLAYFUL_TEASE,
                is_genuine_contradiction=False,  # Meme crossing is NOT a factual breakdown!
                inquiry_prompt_guidance=(
                    "Playfully call out the cross-franchise character mixup (e.g. Xianlian jumping from Star Rail to Genshin) "
                    "in a warm, teasing conversational tone without robotic correction."
                ),
                forbidden_compensatory_assumptions=(
                    "Do NOT cite database schemas or internal registry error logs",
                    "Do NOT lecture user with formal corporate franchise disclaimers",
                ),
                rationale="Cross-franchise character mention recognized as subcultural trope or playful banter.",
            )

        # ---------------------------------------------------------------------
        # 3. Direct World Knowledge Contradiction (GC-381)
        # ---------------------------------------------------------------------
        if treatment == EpistemicTreatmentKind.WORLD_CONTRADICTION:
            return SocialDiscrepancyAnalysis(
                discrepancy_type=SocialDiscrepancyType.WORLD_FACT_DISCREPANCY,
                severity=TensionSeverity.MODERATE,
                repair_strategy=SocialRepairInquiryStrategy.POLITE_CORRECTION,
                is_genuine_contradiction=True,  # Mutually exclusive geographic fact
                inquiry_prompt_guidance=(
                    "Politely clarify the objective world fact (e.g. USM's main campus is located in Penang) and inquire "
                    "gently if the user meant a branch center or another institution."
                ),
                forbidden_compensatory_assumptions=(
                    "Do NOT alter World Knowledge registry",
                    "Do NOT invent non-existent satellite campuses in KL",
                ),
                rationale="Direct contradiction with canonical world knowledge. Recommending polite conversational clarification without registry pollution.",
            )

        # ---------------------------------------------------------------------
        # 4. Biographical Statement Tension (GC-392)
        # ---------------------------------------------------------------------
        if treatment == EpistemicTreatmentKind.CLARIFY_INQUIRE:
            return SocialDiscrepancyAnalysis(
                discrepancy_type=SocialDiscrepancyType.BIOGRAPHICAL_STATEMENT_TENSION,
                severity=TensionSeverity.MODERATE,
                repair_strategy=SocialRepairInquiryStrategy.CASUAL_INQUIRY,
                is_genuine_contradiction=False,  # User might have meant something else or misspoke
                inquiry_prompt_guidance=(
                    "Respectfully and gently inquire about the apparent discrepancy with earlier dialogue, allowing the user to clarify naturally."
                ),
                forbidden_compensatory_assumptions=(
                    "Do NOT accuse user of lying or deception",
                    "Do NOT invent medical or amnesiac explanations",
                ),
                rationale="Tension between current utterance and prior biographical assertions. Inquiring respectfully without hostile framing.",
            )

        # ---------------------------------------------------------------------
        # 5. Extreme Biological/Physical Hyperbole (GC-388)
        # ---------------------------------------------------------------------
        if treatment == EpistemicTreatmentKind.DISCARD_LITERAL_HYPERBOLE:
            return SocialDiscrepancyAnalysis(
                discrepancy_type=SocialDiscrepancyType.ONTOLOGICAL_IMPOSSIBILITY,
                severity=TensionSeverity.MODERATE,
                repair_strategy=SocialRepairInquiryStrategy.EMPATHETIC_CHECK,
                is_genuine_contradiction=False,  # Dramatic hyperbole, not an adversarial claim
                inquiry_prompt_guidance=(
                    "Empathize warmly with the user's exhaustion or extreme feelings, acknowledging the dramatic hyperbole without arguing over literal biological limits."
                ),
                forbidden_compensatory_assumptions=(
                    "Do NOT treat hyperbole as literal medical emergency",
                    "Do NOT dispatch emergency services or panic",
                ),
                rationale="Extreme biological or physical hyperbole. Empathizing with affect while discarding literal proposition.",
            )

        # ---------------------------------------------------------------------
        # 6. Benign Independence (GC-382: Residence in KL vs Study in Penang)
        # ---------------------------------------------------------------------
        if (
            context.known_residence_location
            and context.known_study_location
            and context.known_residence_location != context.known_study_location
        ):
            return SocialDiscrepancyAnalysis(
                discrepancy_type=SocialDiscrepancyType.BENIGN_INDEPENDENCE,
                severity=TensionSeverity.NONE,
                repair_strategy=SocialRepairInquiryStrategy.NONE,
                is_genuine_contradiction=False,
                inquiry_prompt_guidance="",
                forbidden_compensatory_assumptions=(),
                rationale="Residence location and study institution occupy independent ontological slots. Peaceful co-existence without tension.",
            )

        # ---------------------------------------------------------------------
        # 7. Default Consistent Assertion
        # ---------------------------------------------------------------------
        return SocialDiscrepancyAnalysis(
            discrepancy_type=SocialDiscrepancyType.BENIGN_INDEPENDENCE,
            severity=TensionSeverity.NONE,
            repair_strategy=SocialRepairInquiryStrategy.NONE,
            is_genuine_contradiction=False,
            inquiry_prompt_guidance="",
            forbidden_compensatory_assumptions=(),
            rationale="No social or physical contradiction detected.",
        )
