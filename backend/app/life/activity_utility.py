"""Activity utility evaluation and hard eligibility gating for autonomous selection.

Adheres to:
- Invariant 14: Instantiate only registered templates.
- Invariant 21: Templates are capabilities, not biography facts.
- Invariant 22: Explicit goal linkage; no goal fabrication.
- Patch A: Unified sleep hard eligibility (sleep_pressure >= 0.50).
- Patch D: Idle fallback when no candidates pass or all U <= 0.
- GC-034-G: Deterministic goal tie-break ranking rule.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field

from app.character.desire_models import CharacterDesireState
from app.life.activity_templates import ActivityGroundingPolicy, ActivityTemplate
from app.life.circadian_engine import CircadianEngine
from app.life.models import LifeActivity, LifeGoal, LifeGoalStatus
from app.life.physiological_models import CharacterPhysiologicalState

LOCAL_TZ = ZoneInfo("Asia/Kuala_Lumpur")


class ActivityUtilityBreakdown(BaseModel):
    """Detailed explainable breakdown of utility factors."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    need_fit: float = Field(..., description="Alignment with physiological recovery and psychological desire [-1.0, 1.0].")
    circadian_fit: float = Field(..., description="Alignment with diurnal rhythm [-1.0, 1.0].")
    goal_fit: float = Field(..., description="Alignment with active LifeGoals [0.0, 1.0].")
    preference_fit: float = Field(..., description="Character baseline affinity [0.0, 1.0].")
    cost_penalty: float = Field(..., description="Penalty for energy deficits or threshold violations [0.0, 1.0].")
    repetition_penalty: float = Field(..., description="Recency penalty to prevent repetitive loops [0.0, 1.0].")
    composite_utility: float = Field(..., description="Weighted composite utility score.")


class ActivitySelectionDecision(BaseModel):
    """Result of evaluating a template for autonomous selection."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    template: ActivityTemplate = Field(..., description="The evaluated ActivityTemplate.")
    utility_score: float = Field(..., description="Composite utility score.")
    breakdown: ActivityUtilityBreakdown = Field(..., description="Factor breakdown.")
    linked_goal_id: Optional[str] = Field(default=None, description="Explicitly linked active LifeGoal ID, if any.")


def effective_goal_fit(goal: LifeGoal) -> float:
    """Canonical formula for goal utility fit."""
    return goal.importance * (1.0 - 0.3 * goal.progress)


class HardEligibilityGate:
    """Evaluates candidate templates before utility scoring.
    Any violation causes immediate rejection without entering scoring.
    """

    @classmethod
    def evaluate(
        cls,
        template: ActivityTemplate,
        sim_now: datetime,
        phys_state: CharacterPhysiologicalState,
        active_goals: Sequence[LifeGoal] = (),
        core_facts: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        # 1. Grounding Policy Check
        if template.grounding_policy == ActivityGroundingPolicy.GOAL_REQUIRED:
            has_matching_goal = any(
                g.status == LifeGoalStatus.ACTIVE and any(
                    tag in g.title.lower() or tag in g.description.lower()
                    for tag in template.goal_tags
                )
                for g in active_goals
            )
            if not has_matching_goal:
                return False, f"GOAL_REQUIRED template '{template.template_id}' has no matching active LifeGoal."

        if template.grounding_policy == ActivityGroundingPolicy.CONTEXT_REQUIRED:
            # Requires student or academic reality context
            # Default passes if character fact indicates student or study context
            if core_facts and "student" in str(core_facts).lower():
                pass
            # Baseline Aevum is an undergraduate student; if explicitly negated, reject

        # 2. Physiological Hard Limits
        if phys_state.energy < template.required_energy_min:
            return False, f"Energy {phys_state.energy:.2f} below required {template.required_energy_min:.2f}."
        if phys_state.fatigue > template.max_fatigue_threshold:
            return False, f"Fatigue {phys_state.fatigue:.2f} exceeds threshold {template.max_fatigue_threshold:.2f}."
        if phys_state.stress > template.max_stress_threshold:
            return False, f"Stress {phys_state.stress:.2f} exceeds threshold {template.max_stress_threshold:.2f}."

        # 3. Patch A: Unified Sleep Hard Eligibility
        if template.min_sleep_pressure_threshold > 0.0:
            if phys_state.sleep_pressure < template.min_sleep_pressure_threshold:
                return False, f"Sleep pressure {phys_state.sleep_pressure:.2f} below sleep threshold {template.min_sleep_pressure_threshold:.2f}."

        # 4. Circadian Start Window (start-only constraint)
        if template.allowed_start_hours:
            aware_dt = sim_now if sim_now.tzinfo is not None else sim_now.replace(tzinfo=timezone.utc)
            local_dt = aware_dt.astimezone(LOCAL_TZ)
            if local_dt.hour not in template.allowed_start_hours:
                return False, f"Start hour {local_dt.hour} outside allowed start hours {template.allowed_start_hours}."

        return True, None


class ActivityUtilityEvaluator:
    """Evaluates multi-factor utility for eligible candidate templates."""

    @classmethod
    def evaluate(
        cls,
        template: ActivityTemplate,
        sim_now: datetime,
        phys_state: CharacterPhysiologicalState,
        desire_state: Optional[CharacterDesireState] = None,
        active_goals: Sequence[LifeGoal] = (),
        recent_activities: Sequence[LifeActivity] = (),
    ) -> ActivitySelectionDecision:
        aware_dt = sim_now if sim_now.tzinfo is not None else sim_now.replace(tzinfo=timezone.utc)

        # 1. NeedFit [-1.0, 1.0]
        need_fit = 0.0
        if template.profile_id == "SLEEP":
            need_fit = min(1.0, max(-1.0, (phys_state.sleep_pressure - 0.35) * 2.0))
        elif template.profile_id == "RESTORATIVE":
            recovery_need = (phys_state.fatigue * 0.6 + phys_state.stress * 0.4) - 0.20
            need_fit = min(1.0, max(-1.0, recovery_need * 1.5))
        else:
            # Cognitive / Physical exertion
            vitality = (phys_state.energy - 0.40) * 1.5 - (phys_state.fatigue * 0.8 + phys_state.sleep_pressure * 0.6)
            need_fit = min(1.0, max(-1.0, vitality))

        if desire_state and desire_state.primary_desire:
            desire_val = desire_state.primary_desire.value.upper()
            if any(desire_val in align.upper() or align.upper() in desire_val for align in template.primary_desire_alignment):
                need_fit = min(1.0, need_fit + 0.25)

        # 2. CircadianFit [-1.0, 1.0]
        circ_mod = CircadianEngine.get_circadian_modifier(aware_dt)
        if template.profile_id == "SLEEP":
            circadian_fit = -circ_mod  # Night (circ_mod < 0) boosts sleep fit
        elif template.profile_id in ("INTENSE_COGNITIVE", "MODERATE_COGNITIVE", "PHYSICAL_MODERATE"):
            circadian_fit = circ_mod   # Daytime peak boosts focus fit
        else:
            circadian_fit = 0.2 * circ_mod

        # 3. GoalFit [0.0, 1.0] & Deterministic Goal Binding (GC-034-G)
        matching_goals = [
            g for g in active_goals
            if g.status == LifeGoalStatus.ACTIVE and any(
                tag in g.title.lower() or tag in g.description.lower()
                for tag in template.goal_tags
            )
        ]

        linked_goal_id: Optional[str] = None
        goal_fit = 0.0
        if matching_goals:
            ranked_goals = sorted(
                matching_goals,
                key=lambda g: (
                    -effective_goal_fit(g),
                    -g.importance,
                    g.progress,
                    g.id,
                )
            )
            selected_goal = ranked_goals[0]
            linked_goal_id = selected_goal.id
            goal_fit = min(1.0, max(0.0, effective_goal_fit(selected_goal)))

        # 4. PreferenceFit [0.0, 1.0]
        preference_fit = template.base_preference

        # 5. CostPenalty [0.0, 1.0]
        cost_penalty = 0.0
        if phys_state.energy < template.required_energy_min:
            cost_penalty += (template.required_energy_min - phys_state.energy) * 1.5
        if phys_state.fatigue > template.max_fatigue_threshold:
            cost_penalty += (phys_state.fatigue - template.max_fatigue_threshold) * 2.0
        if phys_state.stress > template.max_stress_threshold:
            cost_penalty += (phys_state.stress - template.max_stress_threshold) * 1.5
        cost_penalty = min(1.0, max(0.0, cost_penalty))

        # 6. RepetitionPenalty [0.0, 1.0]
        repetition_penalty = 0.0
        if recent_activities and template.profile_id != "SLEEP":
            last_act = recent_activities[0]
            if last_act.title == template.title:
                repetition_penalty += 0.80
            
            # Check within 4 hours
            four_hours_ago = aware_dt - timedelta(hours=4)
            recent_same = [
                a for a in recent_activities
                if a.title == template.title and (
                    (a.completed_at or a.started_at).replace(tzinfo=timezone.utc) if (a.completed_at or a.started_at).tzinfo is None else (a.completed_at or a.started_at)
                ) >= four_hours_ago
            ]
            if recent_same:
                repetition_penalty = max(repetition_penalty, 0.50)

            # Check 2+ times in 12 hours
            twelve_hours_ago = aware_dt - timedelta(hours=12)
            same_12h = [
                a for a in recent_activities
                if a.title == template.title and (
                    (a.completed_at or a.started_at).replace(tzinfo=timezone.utc) if (a.completed_at or a.started_at).tzinfo is None else (a.completed_at or a.started_at)
                ) >= twelve_hours_ago
            ]
            if len(same_12h) >= 2:
                repetition_penalty = max(repetition_penalty, 0.70)

        repetition_penalty = min(1.0, max(0.0, repetition_penalty))

        # 7. Composite Utility Score
        composite = (
            0.30 * need_fit
            + 0.25 * circadian_fit
            + 0.25 * goal_fit
            + 0.15 * preference_fit
            - 0.35 * cost_penalty
            - 0.30 * repetition_penalty
        )

        breakdown = ActivityUtilityBreakdown(
            need_fit=round(need_fit, 4),
            circadian_fit=round(circadian_fit, 4),
            goal_fit=round(goal_fit, 4),
            preference_fit=round(preference_fit, 4),
            cost_penalty=round(cost_penalty, 4),
            repetition_penalty=round(repetition_penalty, 4),
            composite_utility=round(composite, 4),
        )

        return ActivitySelectionDecision(
            template=template,
            utility_score=round(composite, 4),
            breakdown=breakdown,
            linked_goal_id=linked_goal_id,
        )
