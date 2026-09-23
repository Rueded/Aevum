import logging
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)
from app.life.clock import SimulationClock, RealTimeClock
from app.life.models import (
    LifeActivityStatus,
    LifePlanStatus,
    LifeEventType,
    LifeActivityType,
    LifeEvent,
)
from app.db.models import (
    LifePlanRecord,
    LifeActivityRecord,
    LifeEventRecord,
)
from app.life.circadian_engine import CircadianEngine
from app.life.physiological_models import (
    CANONICAL_ACTIVITY_PROFILES,
    StateTransitionTrigger,
    map_activity_to_profile,
)
from app.life.state_dynamics import StateDynamicsEngine
from app.life.services import LifeService

class LifeSimulationResult(BaseModel):
    processed_plans: int = 0
    started_activities: int = 0
    completed_activities: int = 0
    generated_events: int = 0
    updated_goals: int = 0
    life_events_created: List[LifeEvent] = Field(default_factory=list)

class LifeSimulator:
    """
    Deterministic Life Simulator.
    Reconciles scheduled plans, ongoing activities, and factual life events.
    Adheres to Invariants 11 (unidirectional/idempotent) and 12 (factual immutable events).
    """
    def __init__(self, session: AsyncSession, clock: Optional[SimulationClock] = None):
        self.session = session
        self.clock = clock or RealTimeClock()
        self.service = LifeService(session, self.clock)

    async def _complete_overdue_activities(
        self, character_id: str, sim_now: datetime, result: LifeSimulationResult
    ) -> int:
        """
        Complete ongoing activities whose planned_end_at is past or equal to sim_now.
        Uses authoritative settlement time (planned_end_at when present, sim_now as fallback).
        """
        stmt = select(LifeActivityRecord).where(
            LifeActivityRecord.character_id == character_id,
            LifeActivityRecord.status == LifeActivityStatus.ONGOING.value,
            LifeActivityRecord.planned_end_at.is_not(None),
            LifeActivityRecord.planned_end_at <= sim_now,
        ).order_by(LifeActivityRecord.planned_end_at.asc())

        ongoing_activities = (await self.session.scalars(stmt)).all()
        completed_count = 0

        for activity in ongoing_activities:
            settlement_time = activity.planned_end_at if activity.planned_end_at is not None else sim_now

            await self.service.update_activity_status(
                activity.id,
                LifeActivityStatus.COMPLETED,
                completed_at=settlement_time,
            )
            result.completed_activities += 1
            completed_count += 1

            # Revert LifeState to IDLE if currently executing this activity
            state = await self.service.get_life_state(character_id)
            if state.current_activity == activity.title:
                await self.service.update_life_state(
                    character_id,
                    current_activity="IDLE",
                    current_location="HOME",
                    expected_version=state.version,
                )

            # Generate immutable LifeEvent with idempotency key
            event_key = f"activity_completed:{activity.id}"
            stmt_ev = select(LifeEventRecord).where(LifeEventRecord.idempotency_key == event_key)
            existing_ev = (await self.session.scalars(stmt_ev)).first()
            if not existing_ev:
                life_event = await self.service.create_event(
                    character_id=character_id,
                    event_type=LifeEventType.ACTIVITY_COMPLETED,
                    title=f"Completed {activity.title}",
                    description=f"Aevum completed the activity: {activity.title}",
                    significance=activity.importance,
                    occurred_at=settlement_time,
                    plan_id=activity.plan_id,
                    idempotency_key=event_key,
                )
                result.life_events_created.append(life_event)
                result.generated_events += 1

            # Invariant 22 & Standards 25-26: Advance goal progress if activity has explicit goal_id
            if activity.goal_id:
                updated_goal = await self.service.advance_goal_progress(
                    activity.goal_id,
                    settlement_time=settlement_time,
                )
                if updated_goal:
                    result.updated_goals += 1

            # Complete associated plan if applicable
            if activity.plan_id:
                plan = await self.service.get_plan(activity.plan_id)
                if plan and plan.status != LifePlanStatus.COMPLETED:
                    await self.service.update_plan_status(plan.id, LifePlanStatus.COMPLETED)

            # Invariant 17: Apply physiological wear for the activity duration
            if activity.started_at:
                start_dt = activity.started_at
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                settle_dt = settlement_time
                if settle_dt.tzinfo is None:
                    settle_dt = settle_dt.replace(tzinfo=timezone.utc)
                act_duration = (settle_dt - start_dt).total_seconds()
                if act_duration > 0:
                    curr_phys = await self.service.get_physiological_state(character_id)
                    profile = map_activity_to_profile(activity.activity_type, activity.title)
                    circ_mod = CircadianEngine.get_circadian_modifier(settle_dt)
                    trigger = StateTransitionTrigger.SLEEP_CYCLE if profile.profile_id == "SLEEP" else StateTransitionTrigger.ACTIVITY_INTERVAL
                    new_phys, trans_rec = StateDynamicsEngine.evaluate_interval(
                        curr_phys,
                        act_duration,
                        profile,
                        circadian_modifier=circ_mod,
                        activity_id=activity.id,
                        trigger_type=trigger,
                        current_time=settle_dt,
                    )
                    await self.service.update_physiological_state(character_id, new_phys)
                    await self.service.record_state_transition(trans_rec)

            # Phase 7C.4: Contextual social encounter evaluation (Lock-in Item 4 & Invariant 15.4)
            try:
                from app.social.encounter_engine import SocialEncounterEngine
                from app.life.activity_templates import get_template_by_title

                tmpl = get_template_by_title(activity.title)
                slug = tmpl.template_id if tmpl else activity.activity_type.lower()
                loc = getattr(activity, "location", "HOME") or "HOME"
                phys = await self.service.get_physiological_state(character_id)

                await SocialEncounterEngine.evaluate_activity_encounter(
                    session=self.session,
                    character_id=character_id,
                    activity_title=activity.title,
                    activity_id_slug=slug,
                    location=loc,
                    sim_time=settlement_time,
                    activity_uuid=activity.id,
                    physiological_state=phys,
                )
            except Exception as exc:
                logger.error("Social encounter evaluation safe skip: %s", exc, exc_info=True)

        return completed_count

    async def _start_due_plans(
        self, character_id: str, sim_now: datetime, result: LifeSimulationResult
    ) -> int:
        """
        Start plans whose planned_start is due (planned_start <= sim_now).
        Invariant 12: Emits plan_started event only upon actual transition during reconciliation.
        """
        stmt_plans = select(LifePlanRecord).where(
            LifePlanRecord.character_id == character_id,
            LifePlanRecord.status == LifePlanStatus.PLANNED.value,
            LifePlanRecord.planned_start.is_not(None),
            LifePlanRecord.planned_start <= sim_now,
        ).order_by(LifePlanRecord.planned_start.asc())

        due_plans = (await self.session.scalars(stmt_plans)).all()
        started_count = 0

        for plan in due_plans:
            # Invariant 24 & Standard 27: Verify character does not already have an ongoing activity
            stmt_ongoing = select(LifeActivityRecord).where(
                LifeActivityRecord.character_id == character_id,
                LifeActivityRecord.status == LifeActivityStatus.ONGOING.value,
            )
            ongoing_act = (await self.session.scalars(stmt_ongoing)).first()
            if ongoing_act is not None:
                logger.debug(
                    "Character '%s' already has ongoing activity '%s'; cannot start concurrent plan '%s'.",
                    character_id,
                    ongoing_act.title,
                    plan.title,
                )
                break

            # Check if an activity for this plan already exists
            stmt_act = select(LifeActivityRecord).where(
                LifeActivityRecord.plan_id == plan.id
            )
            existing_act = (await self.session.scalars(stmt_act)).first()
            if not existing_act:
                # Transition plan from PLANNED to IN_PROGRESS
                await self.service.update_plan_status(plan.id, LifePlanStatus.IN_PROGRESS)
                result.processed_plans += 1

                # Start activity
                start_time = plan.planned_start if plan.planned_start is not None else sim_now
                act = await self.service.create_activity(
                    character_id=character_id,
                    activity_type=LifeActivityType.OTHER,
                    title=plan.title,
                    description=plan.description,
                    location="HOME",
                    importance=plan.importance,
                    planned_end_at=plan.planned_end,
                    plan_id=plan.id,
                    started_at=start_time,
                )
                result.started_activities += 1
                started_count += 1

                # Update LifeState to active activity
                state = await self.service.get_life_state(character_id)
                await self.service.update_life_state(
                    character_id,
                    current_activity=act.title,
                    current_location=act.location,
                    expected_version=state.version,
                )

                # Create immutable LifeEvent for actual plan start
                plan_event_key = f"plan_started:{plan.id}"
                stmt_pev = select(LifeEventRecord).where(LifeEventRecord.idempotency_key == plan_event_key)
                existing_pev = (await self.session.scalars(stmt_pev)).first()
                if not existing_pev:
                    life_event = await self.service.create_event(
                        character_id=character_id,
                        event_type=LifeEventType.OTHER,
                        title=f"Started {act.title}",
                        description=f"Aevum started planned activity: {act.title}",
                        significance=plan.importance,
                        occurred_at=start_time,
                        plan_id=plan.id,
                        idempotency_key=plan_event_key,
                    )
                    result.life_events_created.append(life_event)
                    result.generated_events += 1

        return started_count

    async def reconcile(self, character_id: str, now: Optional[datetime] = None) -> LifeSimulationResult:
        sim_now = now or self.clock.now()
        result = LifeSimulationResult()

        # 1. Complete existing overdue activities
        await self._complete_overdue_activities(character_id, sim_now, result)

        # 2. Start due plans
        newly_started = await self._start_due_plans(character_id, sim_now, result)

        # 3. If any activities were newly started, complete them if already overdue (e.g. offline gaps)
        if newly_started > 0:
            await self._complete_overdue_activities(character_id, sim_now, result)

        # 4. Integrate remaining idle elapsed time (e.g. offline gaps between completed activities and sim_now)
        # Invariant 17: Interval attribution without phantom events
        curr_phys = await self.service.get_physiological_state(character_id)
        phys_updated = curr_phys.updated_at
        if phys_updated.tzinfo is None:
            phys_updated = phys_updated.replace(tzinfo=timezone.utc)
        sim_aware = sim_now
        if sim_aware.tzinfo is None:
            sim_aware = sim_aware.replace(tzinfo=timezone.utc)
        idle_seconds = (sim_aware - phys_updated).total_seconds()
        if idle_seconds >= 60.0:
            idle_profile = CANONICAL_ACTIVITY_PROFILES["RESTORATIVE"]
            circ_mod = CircadianEngine.get_circadian_modifier(sim_aware)
            new_phys, trans_rec = StateDynamicsEngine.evaluate_interval(
                curr_phys,
                idle_seconds,
                idle_profile,
                circadian_modifier=circ_mod,
                trigger_type=StateTransitionTrigger.RECONCILIATION_OFFLINE_GAP,
                current_time=sim_aware,
            )
            await self.service.update_physiological_state(character_id, new_phys)
            await self.service.record_state_transition(trans_rec)

        # Single transaction boundary: atomicity across state transition, idempotency, and LifeEvent creation
        await self.session.flush()
        return result

async def reconcile_current_life(
    session: AsyncSession,
    character_id: str = "aevum",
    clock: Optional[SimulationClock] = None,
) -> LifeSimulationResult:
    simulator = LifeSimulator(session, clock=clock)
    return await simulator.reconcile(character_id)
