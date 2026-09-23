"""Autonomous activity selector for Aevum Core.

Adheres to:
- Invariant 14: Selector only instantiates registered ActivityTemplates.
- Invariant 21: Templates are capabilities, not facts.
- Invariant 22: Explicit goal linkage; no goal fabrication.
- Invariant 23: Grounded selection via Hard Eligibility Gate.
- Invariant 24: Single active activity & decision point gating.
- Standard 27: Database-level concurrency safety via partial unique index.
- Standard 28: Instantiation atomicity across LifeActivity and LifeState.
- Patch D: Idle fallback when no candidates pass or all U <= 0.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, List, Optional, Sequence
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.desire_models import CharacterDesireState
from app.db.models import LifeActivityRecord, LifeStateRecord
from app.life.activity_templates import CANONICAL_ACTIVITY_TEMPLATES, ActivityTemplate
from app.life.activity_utility import (
    ActivitySelectionDecision,
    ActivityUtilityEvaluator,
    HardEligibilityGate,
)
from app.life.models import LifeActivity, LifeActivityStatus, LifeGoal, LifeGoalStatus
from app.life.physiological_models import CharacterPhysiologicalState
from app.life.services import LifeService

logger = logging.getLogger(__name__)


class AutonomousActivitySelector:
    """Selects and instantiates grounded activities for a character at decision points."""

    def __init__(self, session: AsyncSession, service: LifeService):
        self.session = session
        self.service = service

    async def can_select(self, character_id: str) -> bool:
        """Verify character is at an authoritative decision point (IDLE, zero ongoing activities)."""
        state = await self.service.get_life_state(character_id)
        if state.current_activity not in (None, "IDLE"):
            return False

        stmt = select(LifeActivityRecord).where(
            LifeActivityRecord.character_id == character_id,
            LifeActivityRecord.status == LifeActivityStatus.ONGOING.value,
        )
        ongoing = (await self.session.scalars(stmt)).first()
        return ongoing is None

    def evaluate_candidates(
        self,
        sim_now: datetime,
        phys_state: CharacterPhysiologicalState,
        desire_state: Optional[CharacterDesireState] = None,
        active_goals: Sequence[LifeGoal] = (),
        recent_activities: Sequence[LifeActivity] = (),
        core_facts: Optional[Dict[str, str]] = None,
    ) -> List[ActivitySelectionDecision]:
        """Evaluate all candidate templates through Hard Eligibility Gate and Utility Evaluator."""
        decisions: List[ActivitySelectionDecision] = []

        for template in CANONICAL_ACTIVITY_TEMPLATES.values():
            eligible, reason = HardEligibilityGate.evaluate(
                template=template,
                sim_now=sim_now,
                phys_state=phys_state,
                active_goals=active_goals,
                core_facts=core_facts,
            )
            if not eligible:
                logger.debug("Template '%s' rejected by Hard Eligibility Gate: %s", template.template_id, reason)
                continue

            decision = ActivityUtilityEvaluator.evaluate(
                template=template,
                sim_now=sim_now,
                phys_state=phys_state,
                desire_state=desire_state,
                active_goals=active_goals,
                recent_activities=recent_activities,
            )
            decisions.append(decision)

        # Sort descending by composite utility score
        decisions.sort(key=lambda d: d.utility_score, reverse=True)
        return decisions

    def select_best(
        self,
        sim_now: datetime,
        phys_state: CharacterPhysiologicalState,
        desire_state: Optional[CharacterDesireState] = None,
        active_goals: Sequence[LifeGoal] = (),
        recent_activities: Sequence[LifeActivity] = (),
        core_facts: Optional[Dict[str, str]] = None,
    ) -> Optional[ActivitySelectionDecision]:
        """Select the highest-utility viable candidate (U > 0). Returns None if none eligible (Patch D)."""
        decisions = self.evaluate_candidates(
            sim_now=sim_now,
            phys_state=phys_state,
            desire_state=desire_state,
            active_goals=active_goals,
            recent_activities=recent_activities,
            core_facts=core_facts,
        )
        if not decisions:
            return None

        best = decisions[0]
        if best.utility_score <= 0.0:
            logger.debug("Top candidate '%s' has non-positive utility (%.4f); remaining IDLE.", best.template.template_id, best.utility_score)
            return None

        return best

    async def instantiate_autonomous_activity(
        self,
        character_id: str,
        decision: ActivitySelectionDecision,
        start_time: datetime,
    ) -> Optional[LifeActivity]:
        """
        Instantiate selected template into an ONGOING LifeActivity.
        Adheres to Standards 27 & 28:
        - Revalidates single active activity constraint.
        - Inserts LifeActivity and updates LifeState atomically.
        - Handles DB partial unique index violation cleanly on race condition.
        """
        # Re-verify decision point constraint
        state = await self.service.get_life_state(character_id)
        if state.current_activity not in (None, "IDLE"):
            return None

        stmt_ongoing = select(LifeActivityRecord).where(
            LifeActivityRecord.character_id == character_id,
            LifeActivityRecord.status == LifeActivityStatus.ONGOING.value,
        )
        if (await self.session.scalars(stmt_ongoing)).first():
            return None

        aware_start = start_time if start_time.tzinfo is not None else start_time.replace(tzinfo=timezone.utc)
        planned_end = aware_start + timedelta(minutes=decision.template.default_duration_minutes)

        # Use savepoint (begin_nested) to safely catch IntegrityError without poisoning session
        try:
            async with self.session.begin_nested():
                record = LifeActivityRecord(
                    character_id=character_id,
                    activity_type=decision.template.activity_type.value,
                    title=decision.template.title,
                    description=decision.template.description,
                    location=decision.template.default_location,
                    status=LifeActivityStatus.ONGOING.value,
                    importance=decision.template.base_preference,
                    started_at=aware_start,
                    planned_end_at=planned_end,
                    goal_id=decision.linked_goal_id,
                    created_at=self.service.clock.now(),
                )
                self.session.add(record)
                await self.session.flush()

                # Update LifeState in same atomic boundary (Standard 28)
                await self.service.update_life_state(
                    character_id=character_id,
                    current_activity=record.title,
                    current_location=record.location,
                    expected_version=state.version,
                )
                await self.session.flush()

            return LifeActivity.model_validate(record, from_attributes=True)
        except IntegrityError as exc:
            logger.warning("Concurrency race detected on autonomous activity instantiation: %s", exc)
            return None

    async def select_and_start_activity(
        self,
        character_id: str = "aevum",
        sim_now: Optional[datetime] = None,
        desire_state: Optional[CharacterDesireState] = None,
        core_facts: Optional[Dict[str, str]] = None,
    ) -> Optional[LifeActivity]:
        """End-to-end autonomous activity selection and instantiation at decision point."""
        now = sim_now or self.service.clock.now()

        # Decision Point Check (Invariant 24)
        if not await self.can_select(character_id):
            return None

        phys_state = await self.service.get_physiological_state(character_id)
        all_goals = await self.service.list_goals(character_id)
        active_goals = [g for g in all_goals if g.status == LifeGoalStatus.ACTIVE]
        recent_acts = await self.service.list_activities(character_id)

        decision = self.select_best(
            sim_now=now,
            phys_state=phys_state,
            desire_state=desire_state,
            active_goals=active_goals,
            recent_activities=recent_acts,
            core_facts=core_facts,
        )

        if decision is None:
            return None

        return await self.instantiate_autonomous_activity(character_id, decision, now)
