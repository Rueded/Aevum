"""Desire and psychological need evaluation engine (Phase 7B.2).

Deterministic evaluation of life state, energy, emotional state, and activity context
into an authoritative CharacterDesireState.
"""

from typing import Optional
from app.character.desire_models import CharacterDesireState, PrimaryDesire
from app.life.physiological_models import CharacterPhysiologicalState, PhysiologicalBand


class DesireEvaluationEngine:
    """Evaluates character internal state to synthesize psychological desires and needs."""

    @classmethod
    def evaluate(
        cls,
        *,
        physiological_state: Optional[CharacterPhysiologicalState] = None,
        current_activity: Optional[str] = None,
        current_location: Optional[str] = None,
        energy: float = 0.7,
        stress: float = 0.2,
        social_energy: float = 0.6,
        loneliness: float = 0.2,
        mood: Optional[str] = None,
        override_desire: Optional[str] = None,
        context_notes: Optional[str] = None,
    ) -> CharacterDesireState:
        """Evaluate internal state and context into a CharacterDesireState.

        Args:
            physiological_state: Optional CharacterPhysiologicalState from StateDynamicsEngine.
            current_activity: Ongoing life activity (e.g. 'reading', 'music_practice', 'REST').
            current_location: Current location (e.g. 'HOME').
            energy: Current physical/mental energy [0.0, 1.0].
            stress: Current stress level [0.0, 1.0].
            social_energy: Readiness for social interaction [0.0, 1.0].
            loneliness: Current loneliness level [0.0, 1.0].
            mood: Qualitative mood string if any.
            override_desire: Explicit desire string from test fixture or scenario.
            context_notes: Extra context notes.

        Returns:
            Authoritative CharacterDesireState.
        """
        # Normalize inputs
        if physiological_state is not None:
            norm_energy = physiological_state.energy
            norm_stress = physiological_state.stress
            fatigue = physiological_state.fatigue
            sleep_pressure = physiological_state.sleep_pressure
            band = physiological_state.qualitative_band
        else:
            norm_energy = max(0.0, min(1.0, float(energy)))
            norm_stress = max(0.0, min(1.0, float(stress)))
            fatigue = 0.15
            sleep_pressure = 0.20
            band = None

        norm_social_energy = max(0.0, min(1.0, float(social_energy)))
        norm_loneliness = max(0.0, min(1.0, float(loneliness)))

        # Baseline needs
        boredom = 0.1
        curiosity = 0.5
        social_need = 0.3 + 0.4 * norm_loneliness + 0.2 * norm_social_energy
        solitude_need = 0.3 + 0.4 * (1.0 - norm_social_energy) + 0.2 * norm_stress
        attention_availability = 0.5 + 0.3 * norm_energy - 0.2 * norm_stress
        primary = PrimaryDesire.QUIET_CONTEMPLATION
        focus: Optional[str] = None

        act = (current_activity or "").lower()

        # Activity-based focus & needs
        if "reading" in act:
            focus = "reading"
            solitude_need = max(solitude_need, 0.75)
            attention_availability = min(attention_availability, 0.35)
            primary = PrimaryDesire.SOLITARY_FOCUS
        elif "music" in act or "practice" in act:
            focus = "practicing music"
            solitude_need = max(solitude_need, 0.70)
            attention_availability = min(attention_availability, 0.40)
            primary = PrimaryDesire.SOLITARY_FOCUS
        elif act in ("rest", "sleep", "resting", "nap"):
            focus = "resting"
            solitude_need = max(solitude_need, 0.60)
            primary = PrimaryDesire.REST_AND_RECHARGE
        elif act:
            focus = current_activity

        # Energy & Physiological band constraints
        if norm_energy < 0.4 or fatigue > 0.60:
            primary = PrimaryDesire.REST_AND_RECHARGE
            solitude_need = max(solitude_need, 0.70)
            attention_availability = min(attention_availability, 0.40)

        if band == PhysiologicalBand.DROWSY:
            primary = PrimaryDesire.REST_AND_RECHARGE
            attention_availability = min(attention_availability, 0.25)
            solitude_need = max(solitude_need, 0.70)
        elif band == PhysiologicalBand.OVERLOADED:
            primary = PrimaryDesire.REST_AND_RECHARGE
            attention_availability = min(attention_availability, 0.20)
            solitude_need = max(solitude_need, 0.85)
        elif band == PhysiologicalBand.FATIGUED:
            primary = PrimaryDesire.REST_AND_RECHARGE
            attention_availability = min(attention_availability, 0.35)
            solitude_need = max(solitude_need, 0.65)
        elif band == PhysiologicalBand.REFRESHED:
            attention_availability = max(attention_availability, 0.75)
            curiosity = max(curiosity, 0.65)

        # Handle explicit override desire or fixture strings
        if override_desire:
            od = override_desire.lower()
            if "finish_current_chapter" in od or "chapter" in od:
                primary = PrimaryDesire.SOLITARY_FOCUS
                focus = "reading current chapter"
                solitude_need = max(solitude_need, 0.80)
                attention_availability = min(attention_availability, 0.30)
            elif "stay_home" in od:
                primary = PrimaryDesire.REST_AND_RECHARGE
                focus = "resting at home"
                solitude_need = max(solitude_need, 0.75)
                attention_availability = min(attention_availability, 0.40)
            elif "casual_greeting" in od or "greeting" in od:
                primary = PrimaryDesire.CASUAL_ENGAGEMENT
                social_need = max(social_need, 0.60)
                attention_availability = max(attention_availability, 0.80)
            elif "deep" in od or "talk" in od:
                primary = PrimaryDesire.DEEP_CONVERSATION
                social_need = max(social_need, 0.75)
                attention_availability = max(attention_availability, 0.75)
            elif "play" in od or "game" in od:
                primary = PrimaryDesire.PLAYFUL_DISTRACTION
                curiosity = max(curiosity, 0.70)
                boredom = max(boredom, 0.50)

        # Re-clamp all floats
        return CharacterDesireState(
            primary_desire=primary,
            current_focus=focus,
            boredom=max(0.0, min(1.0, boredom)),
            curiosity=max(0.0, min(1.0, curiosity)),
            social_need=max(0.0, min(1.0, social_need)),
            solitude_need=max(0.0, min(1.0, solitude_need)),
            energy=norm_energy,
            attention_availability=max(0.0, min(1.0, attention_availability)),
        )
