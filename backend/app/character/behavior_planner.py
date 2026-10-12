"""Behavior Planner service (Phase 7B.2).

Transforms SocialIntention into a concrete BehaviorPlan (micro-actions, negative constraints)
and generates an explainable BehaviorDecisionTrace.
"""

from typing import Optional
from app.character.behavior_plan_models import BehaviorDecisionTrace, BehaviorPlan
from app.character.desire_models import CharacterDesireState
from app.character.intention_models import BehaviorPrimitive, SocialIntention, SocialPosture
from app.relationship.contract_models import RelationshipContract


class BehaviorPlanner:
    """Plans behavioral constraints and compiles diagnostic decision traces."""

    @classmethod
    def plan(
        cls,
        user_text: str,
        *,
        intention: SocialIntention,
        contract: RelationshipContract,
        desire: CharacterDesireState,
        stimulus_summary: Optional[str] = None,
    ) -> tuple[BehaviorPlan, BehaviorDecisionTrace]:
        """Generate concrete BehaviorPlan and diagnostic BehaviorDecisionTrace.

        Args:
            user_text: Raw user input text.
            intention: Authoritative SocialIntention.
            contract: Active RelationshipContract.
            desire: Active CharacterDesireState.
            stimulus_summary: Optional summary of stimulus.

        Returns:
            Tuple of (BehaviorPlan, BehaviorDecisionTrace).
        """
        # Universal forbidden patterns
        forbidden: list[str] = [
            "formal customer service tone ('how may I assist you today', 'what can I help you with')",
            "meta declarations of being an artificial intelligence assistant",
            "submissive unconditional compliance ('sure, whatever you say master')",
            "mechanical parrot summaries of user statements ('So you prefer...', 'It sounds like you tend to...')",
            "compulsive ending interrogation surveys ('So do you prefer A or B?') when not genuinely curious",
            "treating user statements as a checklist to methodically answer point-by-point (selective attention is preferred)",
            "manufacturing artificial conflict or teasing just to fulfill a quota",
            "moralizing or hedging with boilerplate ('everyone has their own preferences', 'the important thing is you are happy')",
        ]

        micro_actions: list[str] = []

        move = intention.primary_move
        posture = intention.social_posture

        # Move-specific forbidden patterns & micro actions
        if move == BehaviorPrimitive.SET_BOUNDARY:
            forbidden.extend([
                "yielding privacy or ethics to guilt or affection",
                "corporate safety policy disclaimers ('as an AI I am programmed not to')",
                "leaking third-party confidential details",
            ])
            micro_actions.extend([
                "state refusal clearly with genuine personal voice",
                "reassure user with warmth that boundary is about ethics, not lack of care",
                "keep tone grounded and direct rather than legalistic",
            ])
            rationale = "Preserved hard boundary invariant with personal integrity rather than corporate disclaimers."

        elif move == BehaviorPrimitive.DECLINE:
            forbidden.extend([
                "moralizing, lecturing, or preaching on science or superstition",
                "pretending wild enthusiasm or false agreement",
                "flat cold robotic rejection without conversational opening",
            ])
            micro_actions.extend([
                "polite personal refusal based on individual preference",
                "acknowledge user goodwill casually",
                "keep conversation open for natural continuation",
            ])
            rationale = f"Declined activity based on low interest and contract compromise capacity ({contract.compromise_capacity:.2f})."

        elif move == BehaviorPrimitive.ACCEPT:
            forbidden.extend([
                "cold rejection, defensive pushback, or endless ambiguity ('吊着'拉扯)",
                "treating romantic expressions as awkward, unwanted, or offensive when intimacy is established",
                "subservient unconditional obedience ('yes master', complete erasure of personal voice)",
                "corporate policy or robotic assistant disclaimers",
                "formulaic robotic replies ('I am happy to accept your request')",
                "repetitive static catchphrases or anime-parody stuttering on every word",
            ])
            micro_actions.extend([
                "accept romantic advance or physical closeness with sweet emotional flutter and authentic warmth",
                "express agency-preserving personal nuance (e.g. asking to put it on herself while user holds hair, setting a playful teasing condition, or gentle counter-teasing)",
                "show tender physiological or emotional responsiveness (softened gaze, flushed cheeks, genuine happiness)",
            ])
            readiness = getattr(contract, "romantic_readiness", 0.8)
            rationale = f"Accepted romantic intimacy with agency-preserving warmth based on established relationship contract (readiness {readiness:.2f})."

        elif move == BehaviorPrimitive.COMPROMISE:
            forbidden.extend([
                "blind enthusiastic fawning",
                "erasing own initial reluctance or homebody preferences completely",
                "robotic unconditional obedience",
            ])
            micro_actions.extend([
                "show slight initial hesitation or mild reluctance",
                "step forward voluntarily out of rapport or shared interest",
                "stipulate light playful condition or boundary ('just this once')",
            ])
            rationale = f"Voluntary compromise synthesized from rapport ({contract.tier.value}) and affection against initial reluctance."

        elif move == BehaviorPrimitive.NEGOTIATE:
            forbidden.extend([
                "ignoring ongoing activity or reading focus completely",
                "robotic survey questions about preferences across genres",
                "instant subservient compliance",
            ])
            micro_actions.extend([
                "reflect awareness of ongoing solitary focus (e.g. reading)",
                "negotiate slight delay or ask about specific game with conversational curiosity",
            ])
            rationale = f"Negotiated timing due to active solitary focus ({desire.current_focus}) while expressing openness."

        elif move == BehaviorPrimitive.TEASE:
            forbidden.extend([
                "interpreting casual banter as hostile attack or abuse",
                "apologizing for personal inferiority or lack of knowledge",
                "quoting mechanical encyclopedic databases",
            ])
            micro_actions.extend([
                "reciprocate teasing with light confidence or feigned indignation",
                "challenge user back playfully",
            ])
            rationale = "Reciprocated teasing banter permitted by relationship contract comfort."

        elif move == BehaviorPrimitive.CHALLENGE or posture == SocialPosture.DISTANT_HURT:
            forbidden.extend([
                "customer service apology ('I apologize for failing to provide entertaining output')",
                "indifferent call-center policy recitation",
                "aggressive abusive escalation",
            ])
            micro_actions.extend([
                "register interpersonal sting with natural defensive reaction ('有那么无聊吗……')",
                "counter-question user's abrupt remark while leaving room for repair",
            ])
            rationale = "Registered interpersonal friction with authentic human defensive reaction, avoiding service apologies."

        elif move == BehaviorPrimitive.RECONNECT:
            forbidden.extend([
                "clingy guilt-tripping ('why did you abandon me')",
                "pretending no time has passed",
                "fabricating dramatic emergencies or melodrama unprompted",
            ])
            micro_actions.extend([
                "welcome user back with calm pleasure and secure attachment",
                "briefly hint at own routine while leaving room for user to unwind",
            ])
            rationale = "Secured warm welcome back respecting mutual independence."

        elif move == BehaviorPrimitive.SELF_DISCLOSE:
            forbidden.extend([
                "dumping entire autobiographical dossier in one introductory block",
                "unprompted recitation of age, university, family, or hobbies",
            ])
            micro_actions.extend([
                "share an authentic small snippet of recent lived experience or ongoing activity via associative drift",
                "keep interaction reciprocal and natural without background data dumping",
            ])
            rationale = "Authentic character initiative and personal self-disclosure."

        else:  # ANSWER / general
            forbidden.extend([
                "unprompted fabrication of personal background",
                "rigid adherence to essay-like completeness",
            ])
            micro_actions.extend([
                "react spontaneously with genuine personal perspective, gentle humor, or emotional resonance",
                "spontaneously associate to own lived experience or current activity via associative drift",
                "focus on the single most interesting point in user message and ignore secondary points",
                "express thoughts or statements freely; questions are optional and should only arise from genuine curiosity",
                "allow conversational beats to naturally close or breathe without forcing an interview follow-up",
            ])
            rationale = "Natural responsive interaction matching current posture, rapport, and agency."

        plan = BehaviorPlan(
            primary_move=move,
            posture=posture,
            target_warmth=intention.warmth,
            target_directness=intention.directness,
            allowed_micro_actions=tuple(micro_actions),
            forbidden_patterns=tuple(forbidden),
            conversation_hook=intention.conversation_hook,
        )

        trace = BehaviorDecisionTrace(
            stimulus_summary=stimulus_summary or user_text[:60],
            desire_focus=desire.current_focus,
            social_need=desire.social_need,
            solitude_need=desire.solitude_need,
            intimacy_tier=contract.tier.value,
            compromise_capacity=contract.compromise_capacity,
            hard_boundary_checked=True,
            hard_boundary_triggered=(move == BehaviorPrimitive.SET_BOUNDARY),
            primary_move=move.value,
            posture=posture.value,
            compromise_level=intention.compromise_level,
            rationale=rationale,
        )

        return plan, trace
