"""Relationship contract evaluator service (Phase 7B.2).

Deterministic evaluation of RelationshipState and contextual cues into a typed
RelationshipContract with baseline permissions and situational adjustments.
"""

from typing import Optional, Sequence
from app.relationship.models import RelationshipState
from app.relationship.contract_models import IntimacyTier, RelationshipContract


class RelationshipContractEvaluator:
    """Evaluates relationship dynamics into an authoritative conversational contract."""

    @classmethod
    def evaluate(
        cls,
        *,
        relationship: Optional[RelationshipState] = None,
        familiarity: Optional[float] = None,
        trust: Optional[float] = None,
        comfort: Optional[float] = None,
        affection: Optional[float] = None,
        respect: Optional[float] = None,
        user_text: Optional[str] = None,
        energy: float = 0.7,
        context_modifiers: Optional[Sequence[str]] = None,
    ) -> RelationshipContract:
        """Evaluate relationship state and context into a RelationshipContract.

        Args:
            relationship: Authoritative RelationshipState if available.
            familiarity: Explicit familiarity override.
            trust: Explicit trust override.
            comfort: Explicit comfort override.
            affection: Explicit affection override.
            respect: Explicit respect override.
            user_text: Input message from user to check situational tone.
            energy: Current character energy level [0.0, 1.0].
            context_modifiers: Situational tags or notes.

        Returns:
            Authoritative RelationshipContract.
        """
        # Resolve metrics
        fam = familiarity if familiarity is not None else (relationship.familiarity if relationship else 0.05)
        tru = trust if trust is not None else (relationship.trust if relationship else 0.20)
        com = comfort if comfort is not None else (relationship.comfort if relationship else 0.10)
        aff = affection if affection is not None else (relationship.affection if relationship else 0.00)
        res = respect if respect is not None else (relationship.respect if relationship else 0.50)

        fam = max(0.0, min(1.0, float(fam)))
        tru = max(0.0, min(1.0, float(tru)))
        com = max(0.0, min(1.0, float(com)))
        aff = max(0.0, min(1.0, float(aff)))
        res = max(0.0, min(1.0, float(res)))

        # Determine intimacy tier
        composite = 0.4 * fam + 0.35 * tru + 0.25 * com
        if fam < 0.20 and tru < 0.40:
            tier = IntimacyTier.STRANGER
        elif fam < 0.45 or tru < 0.55:
            tier = IntimacyTier.ACQUAINTANCE
        elif fam < 0.70 or tru < 0.70:
            tier = IntimacyTier.FAMILIAR
        elif fam < 0.85 or tru < 0.85:
            tier = IntimacyTier.TRUSTED_FRIEND
        else:
            tier = IntimacyTier.CLOSE_CONFIDANT

        # Baseline permissions per tier
        if tier == IntimacyTier.STRANGER:
            teasing = False
            vulnerability = 0.10
            compromise = 0.15
            sensitivity = 0.85
            independence = 0.90
        elif tier == IntimacyTier.ACQUAINTANCE:
            teasing = False
            vulnerability = 0.25
            compromise = 0.25
            sensitivity = 0.70
            independence = 0.85
        elif tier == IntimacyTier.FAMILIAR:
            teasing = True
            vulnerability = 0.55
            compromise = 0.55
            sensitivity = 0.50
            independence = 0.75
        elif tier == IntimacyTier.TRUSTED_FRIEND:
            teasing = True
            vulnerability = 0.80
            compromise = 0.75
            sensitivity = 0.35
            independence = 0.65
        else:  # CLOSE_CONFIDANT
            teasing = True
            vulnerability = 0.95
            compromise = 0.85
            sensitivity = 0.25
            independence = 0.55

        modifiers_list: list[str] = list(context_modifiers or [])

        # Contextual adjustment 1: Affection increases compromise willingness for shared/warm activities
        if aff > 0.60:
            boost = 0.15 * aff
            compromise = min(0.90, compromise + boost)
            modifiers_list.append("high_affection_compromise_boost")

        # Contextual adjustment 2: Teasing permission situational unlock for ACQUAINTANCE with high comfort or banter
        if not teasing and com >= 0.50 and fam >= 0.30:
            teasing = True
            modifiers_list.append("comfort_enabled_banter")

        # Contextual adjustment 3: Energy fatigue dampens compromise and raises boundary sensitivity
        if energy < 0.40:
            compromise = max(0.10, compromise - 0.15)
            sensitivity = min(1.0, sensitivity + 0.15)
            modifiers_list.append("low_energy_boundary_vigilance")

        # Contextual adjustment 4: User text checks (e.g. abrupt, critical, or dismissive tone)
        if user_text:
            text = user_text.lower()
            if any(w in text for w in ["真无趣", "无聊", "没劲", "逊", "差劲", "难沟通"]):
                sensitivity = min(1.0, sensitivity + 0.20)
                compromise = max(0.05, compromise - 0.20)
                modifiers_list.append("defensive_guard_against_dismissal")

        # Contextual adjustment 5: Romantic readiness derived from affection and trust
        romantic_readiness = 0.70 * aff + 0.30 * tru
        if aff >= 0.70:
            romantic_readiness = max(romantic_readiness, aff)
            modifiers_list.append("high_affection_romantic_acceptance")
        elif aff >= 0.55:
            romantic_readiness = max(romantic_readiness, 0.60)
            modifiers_list.append("affection_intimacy_unlocked")
        elif aff < 0.30:
            romantic_readiness = min(romantic_readiness, 0.25)

        return RelationshipContract(
            tier=tier,
            teasing_permission=teasing,
            vulnerability_depth=max(0.0, min(1.0, vulnerability)),
            compromise_capacity=max(0.0, min(1.0, compromise)),
            boundary_sensitivity=max(0.0, min(1.0, sensitivity)),
            independence_weight=max(0.0, min(1.0, independence)),
            romantic_readiness=max(0.0, min(1.0, romantic_readiness)),
            contextual_modifiers=tuple(modifiers_list),
        )
