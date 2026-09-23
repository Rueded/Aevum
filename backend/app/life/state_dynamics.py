"""State Dynamics Engine (Phase 7C.2).

Authoritative engine governing physiological and wear states.
Enforces:
- Invariant 13 & 16: Sole writer of physiological state.
- Invariant 17: Time interval attribution (zero double-counting).
- Invariant 18: Derived qualitative presentation band.
- Guardrail 1: Baseline anti-drift isolation (acute state cannot rewrite baseline).
- Guardrail 2: Circadian single-source attribution.
"""

from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
import uuid

from app.life.physiological_models import (
    ActivityPhysiologicalProfile,
    CANONICAL_ACTIVITY_PROFILES,
    CharacterPhysiologicalState,
    PhysiologicalBand,
    StateTransitionRecord,
    StateTransitionTrigger,
)


class PhysiologicalBandClassifier:
    """Pure derived classifier mapping continuous metrics to qualitative bands (Invariant 18)."""

    @classmethod
    def classify(
        cls,
        *,
        energy: float,
        fatigue: float,
        stress: float,
        sleep_pressure: float,
    ) -> PhysiologicalBand:
        # Overloaded: high fatigue combined with elevated stress
        if fatigue >= 0.70 and stress >= 0.55:
            return PhysiologicalBand.OVERLOADED

        # Drowsy: high sleep pressure, or moderate sleep pressure with moderate fatigue
        if sleep_pressure >= 0.75 or (sleep_pressure >= 0.60 and fatigue >= 0.45):
            return PhysiologicalBand.DROWSY

        # Fatigued: high exertion wear or depleted energy
        if fatigue >= 0.60 or energy <= 0.30:
            return PhysiologicalBand.FATIGUED

        # Refreshed: high energy, minimal wear and low stress
        if energy >= 0.70 and fatigue <= 0.25 and stress <= 0.30:
            return PhysiologicalBand.REFRESHED

        # Steady: default balanced baseline
        return PhysiologicalBand.STEADY


class StateDynamicsEngine:
    """
    Sole authority for physiological state transitions.
    Computes deterministic state evolution from time intervals and discrete acute events.
    """

    # Static baseline targets (Guardrail 1: baseline is preserved and stable)
    BASELINE_ENERGY = 0.75
    BASELINE_FATIGUE = 0.15
    BASELINE_STRESS = 0.15
    BASELINE_SLEEP_PRESSURE = 0.10

    @classmethod
    def evaluate_interval(
        cls,
        before_state: CharacterPhysiologicalState,
        duration_seconds: float,
        profile: ActivityPhysiologicalProfile,
        circadian_modifier: float = 0.0,
        activity_id: Optional[str] = None,
        trigger_type: StateTransitionTrigger = StateTransitionTrigger.ACTIVITY_INTERVAL,
        current_time: Optional[datetime] = None,
    ) -> Tuple[CharacterPhysiologicalState, StateTransitionRecord]:
        """
        Integrate physiological effects over a continuous time interval.
        Enforces Invariant 17: Time interval attribution happens exactly once per span.
        """
        now = current_time or datetime.now(timezone.utc)
        dt_hours = max(0.0, duration_seconds / 3600.0)

        curr_energy = before_state.energy
        curr_fatigue = before_state.fatigue
        curr_stress = before_state.stress
        curr_sleep_pressure = before_state.sleep_pressure

        if dt_hours > 0.0:
            # 1. Direct profile rates (Guardrail 1: Non-sleep relaxation relaxes towards baseline, not below it)
            if profile.energy_rate > 0.0 and profile.profile_id != "SLEEP":
                curr_energy = min(cls.BASELINE_ENERGY, curr_energy + profile.energy_rate * dt_hours)
            else:
                curr_energy += profile.energy_rate * dt_hours

            if profile.fatigue_rate < 0.0 and profile.profile_id != "SLEEP":
                curr_fatigue = max(cls.BASELINE_FATIGUE, curr_fatigue + profile.fatigue_rate * dt_hours)
            else:
                curr_fatigue += profile.fatigue_rate * dt_hours

            if profile.stress_rate < 0.0 and profile.profile_id != "SLEEP":
                curr_stress = max(cls.BASELINE_STRESS, curr_stress + profile.stress_rate * dt_hours)
            else:
                curr_stress += profile.stress_rate * dt_hours

            curr_sleep_pressure += profile.sleep_pressure_rate * dt_hours

            # 2. Bounded passive recovery towards baseline (Guardrail 1: bounded anti-drift pull)
            if profile.recovery_rate > 0.0:
                pull = min(1.0, profile.recovery_rate * dt_hours)
                if curr_energy < cls.BASELINE_ENERGY:
                    curr_energy += pull * (cls.BASELINE_ENERGY - curr_energy)
                if curr_fatigue > cls.BASELINE_FATIGUE:
                    curr_fatigue -= pull * (curr_fatigue - cls.BASELINE_FATIGUE)
                if curr_stress > cls.BASELINE_STRESS:
                    curr_stress -= pull * (curr_stress - cls.BASELINE_STRESS)

        # Clamp all values strictly to [0.0, 1.0]
        new_energy = max(0.0, min(1.0, curr_energy))
        new_fatigue = max(0.0, min(1.0, curr_fatigue))
        new_stress = max(0.0, min(1.0, curr_stress))
        new_sleep_pressure = max(0.0, min(1.0, curr_sleep_pressure))

        # One-way derived presentation band (Invariant 18)
        new_band = PhysiologicalBandClassifier.classify(
            energy=new_energy,
            fatigue=new_fatigue,
            stress=new_stress,
            sleep_pressure=new_sleep_pressure,
        )

        after_state = CharacterPhysiologicalState(
            energy=new_energy,
            fatigue=new_fatigue,
            stress=new_stress,
            sleep_pressure=new_sleep_pressure,
            qualitative_band=new_band,
            updated_at=now,
        )

        # Provenance audit record (zero LLM free-text)
        before_dict = {
            "energy": before_state.energy,
            "fatigue": before_state.fatigue,
            "stress": before_state.stress,
            "sleep_pressure": before_state.sleep_pressure,
        }
        after_dict = {
            "energy": after_state.energy,
            "fatigue": after_state.fatigue,
            "stress": after_state.stress,
            "sleep_pressure": after_state.sleep_pressure,
        }
        delta_dict = {k: round(after_dict[k] - before_dict[k], 4) for k in before_dict}

        rule_id = f"profile.{profile.profile_id}.v1"
        mins = round(duration_seconds / 60.0, 1)
        reason = f"Applied profile '{profile.profile_id}' over {mins}m interval"

        record = StateTransitionRecord(
            id=str(uuid.uuid4()),
            character_id="aevum",
            timestamp=now,
            trigger_type=trigger_type,
            activity_id=activity_id,
            time_interval_seconds=duration_seconds,
            before_state=before_dict,
            after_state=after_dict,
            delta=delta_dict,
            circadian_modifier=circadian_modifier,
            rule_id=rule_id,
            reason=reason,
        )

        return after_state, record

    @classmethod
    def evaluate_acute_event(
        cls,
        before_state: CharacterPhysiologicalState,
        event_type_str: str,
        significance: float = 0.5,
        current_time: Optional[datetime] = None,
    ) -> Tuple[CharacterPhysiologicalState, Optional[StateTransitionRecord]]:
        """
        Evaluate discrete acute shocks.
        Invariant 17: ACTIVITY_COMPLETED produces 0 duplicate fatigue/energy wear by default.
        """
        now = current_time or datetime.now(timezone.utc)
        ev = event_type_str.upper()

        # Invariant 17: Routine completion events add zero duplicate fatigue
        if ev in ("ACTIVITY_COMPLETED", "PLAN_COMPLETED", "ROUTINE", "OTHER"):
            return before_state, None

        curr_energy = before_state.energy
        curr_fatigue = before_state.fatigue
        curr_stress = before_state.stress
        curr_sleep_pressure = before_state.sleep_pressure
        rule_id = ""

        if ev == "SETBACK":
            curr_stress += 0.15 * significance
            curr_energy -= 0.08 * significance
            rule_id = "acute.setback.v1"
        elif ev == "SUCCESS":
            curr_stress = max(0.0, curr_stress - 0.15 * significance)
            curr_energy = min(1.0, curr_energy + 0.10 * significance)
            rule_id = "acute.success.v1"
        else:
            return before_state, None

        new_energy = max(0.0, min(1.0, curr_energy))
        new_fatigue = max(0.0, min(1.0, curr_fatigue))
        new_stress = max(0.0, min(1.0, curr_stress))
        new_sleep_pressure = max(0.0, min(1.0, curr_sleep_pressure))

        new_band = PhysiologicalBandClassifier.classify(
            energy=new_energy,
            fatigue=new_fatigue,
            stress=new_stress,
            sleep_pressure=new_sleep_pressure,
        )

        after_state = CharacterPhysiologicalState(
            energy=new_energy,
            fatigue=new_fatigue,
            stress=new_stress,
            sleep_pressure=new_sleep_pressure,
            qualitative_band=new_band,
            updated_at=now,
        )

        before_dict = {
            "energy": before_state.energy,
            "fatigue": before_state.fatigue,
            "stress": before_state.stress,
            "sleep_pressure": before_state.sleep_pressure,
        }
        after_dict = {
            "energy": after_state.energy,
            "fatigue": after_state.fatigue,
            "stress": after_state.stress,
            "sleep_pressure": after_state.sleep_pressure,
        }
        delta_dict = {k: round(after_dict[k] - before_dict[k], 4) for k in before_dict}

        record = StateTransitionRecord(
            id=str(uuid.uuid4()),
            character_id="aevum",
            timestamp=now,
            trigger_type=StateTransitionTrigger.ACUTE_EVENT,
            activity_id=None,
            time_interval_seconds=0.0,
            before_state=before_dict,
            after_state=after_dict,
            delta=delta_dict,
            circadian_modifier=0.0,
            rule_id=rule_id,
            reason=f"Acute event '{ev}' applied shock",
        )

        return after_state, record
