from datetime import datetime, timezone
from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import (
    LifeStateRecord,
    LifeActivityRecord,
    LifePlanRecord,
    LifeEventRecord,
    LifeGoalRecord,
    CharacterPhysiologicalRecord,
    StateTransitionAuditRecord,
)
import json
from app.life.physiological_models import (
    CharacterPhysiologicalState,
    PhysiologicalBand,
    StateTransitionRecord,
    StateTransitionTrigger,
)
from app.life.clock import SimulationClock, RealTimeClock
from app.life.models import (
    LifeState,
    LifeActivity,
    LifePlan,
    LifeEvent,
    LifeGoal,
    LifeActivityType,
    LifeActivityStatus,
    LifePlanStatus,
    LifeEventType,
    LifeGoalStatus,
)
from app.life.state_machine import LifeStateMachine, InvalidStateTransitionError

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class OptimisticConcurrencyError(Exception):
    """Raised when an update fails due to a version mismatch."""
    pass

class LifeService:
    def __init__(self, session: AsyncSession, clock: Optional[SimulationClock] = None):
        self.session = session
        self.clock = clock or RealTimeClock()

    async def get_life_state(self, character_id: str = "aevum") -> LifeState:
        record = await self.session.get(LifeStateRecord, character_id)
        if not record:
            record = LifeStateRecord(
                id=character_id,
                character_id=character_id,
                current_activity="IDLE",
                current_location="HOME",
                status="ACTIVE",
            )
            self.session.add(record)
            await self.session.flush()
        return LifeState.model_validate(record, from_attributes=True)

    async def update_life_state(self, character_id: str, current_activity: str, current_location: str, expected_version: int) -> LifeState:
        record = await self.session.get(LifeStateRecord, character_id)
        if not record:
            raise ValueError(f"Life state for {character_id} not found.")
        if record.version != expected_version:
            raise OptimisticConcurrencyError(f"Version mismatch. Expected {expected_version}, got {record.version}.")
        
        record.current_activity = current_activity
        record.current_location = current_location
        record.version += 1
        record.updated_at = self.clock.now()
        await self.session.flush()
        return LifeState.model_validate(record, from_attributes=True)

    async def create_activity(
        self,
        character_id: str,
        activity_type: LifeActivityType,
        title: str,
        description: str,
        location: str,
        importance: float = 0.5,
        planned_end_at: Optional[datetime] = None,
        plan_id: Optional[str] = None,
        goal_id: Optional[str] = None,
        started_at: Optional[datetime] = None,
    ) -> LifeActivity:
        record = LifeActivityRecord(
            character_id=character_id,
            activity_type=activity_type.value,
            title=title,
            description=description,
            location=location,
            status=LifeActivityStatus.ONGOING.value,
            importance=importance,
            started_at=started_at or self.clock.now(),
            planned_end_at=planned_end_at,
            plan_id=plan_id,
            goal_id=goal_id,
            created_at=self.clock.now(),
        )
        self.session.add(record)
        await self.session.flush()
        return LifeActivity.model_validate(record, from_attributes=True)

    async def get_activity(self, activity_id: str) -> Optional[LifeActivity]:
        record = await self.session.get(LifeActivityRecord, activity_id)
        if record:
            return LifeActivity.model_validate(record, from_attributes=True)
        return None

    async def list_activities(self, character_id: str) -> List[LifeActivity]:
        stmt = select(LifeActivityRecord).where(LifeActivityRecord.character_id == character_id).order_by(LifeActivityRecord.started_at.desc())
        result = await self.session.scalars(stmt)
        return [LifeActivity.model_validate(r, from_attributes=True) for r in result]

    async def update_activity_status(
        self,
        activity_id: str,
        status: LifeActivityStatus,
        completed_at: Optional[datetime] = None,
    ) -> LifeActivity:
        record = await self.session.get(LifeActivityRecord, activity_id)
        if not record:
            raise ValueError(f"Activity {activity_id} not found.")
        current_status = LifeActivityStatus(record.status)
        should_update = LifeStateMachine.validate_activity_transition(current_status, status)
        if should_update:
            record.status = status.value
            if status == LifeActivityStatus.COMPLETED:
                record.completed_at = completed_at or self.clock.now()
            await self.session.flush()
        return LifeActivity.model_validate(record, from_attributes=True)

    async def create_plan(
        self,
        character_id: str,
        title: str,
        description: str,
        importance: float = 0.5,
        planned_start: Optional[datetime] = None,
        planned_end: Optional[datetime] = None,
        goal_id: Optional[str] = None,
    ) -> LifePlan:
        record = LifePlanRecord(
            character_id=character_id,
            title=title,
            description=description,
            importance=importance,
            planned_start=planned_start,
            planned_end=planned_end,
            goal_id=goal_id,
            created_at=self.clock.now(),
            updated_at=self.clock.now(),
        )
        self.session.add(record)
        await self.session.flush()
        return LifePlan.model_validate(record, from_attributes=True)

    async def get_plan(self, plan_id: str) -> Optional[LifePlan]:
        record = await self.session.get(LifePlanRecord, plan_id)
        if record:
            return LifePlan.model_validate(record, from_attributes=True)
        return None

    async def list_plans(self, character_id: str) -> List[LifePlan]:
        stmt = select(LifePlanRecord).where(LifePlanRecord.character_id == character_id).order_by(LifePlanRecord.created_at.desc())
        result = await self.session.scalars(stmt)
        return [LifePlan.model_validate(r, from_attributes=True) for r in result]

    async def update_plan_status(self, plan_id: str, status: LifePlanStatus) -> LifePlan:
        record = await self.session.get(LifePlanRecord, plan_id)
        if not record:
            raise ValueError(f"Plan {plan_id} not found.")
        current_status = LifePlanStatus(record.status)
        should_update = LifeStateMachine.validate_plan_transition(current_status, status)
        if should_update:
            record.status = status.value
            record.updated_at = self.clock.now()
            await self.session.flush()
        return LifePlan.model_validate(record, from_attributes=True)

    async def create_event(
        self,
        character_id: str,
        event_type: LifeEventType,
        title: str,
        description: str,
        significance: float = 0.5,
        occurred_at: Optional[datetime] = None,
        plan_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> LifeEvent:
        if idempotency_key is not None:
            stmt = select(LifeEventRecord).where(LifeEventRecord.idempotency_key == idempotency_key)
            existing = (await self.session.scalars(stmt)).first()
            if existing:
                return LifeEvent.model_validate(existing, from_attributes=True)

        record = LifeEventRecord(
            character_id=character_id,
            event_type=event_type.value,
            title=title,
            description=description,
            significance=significance,
            plan_id=plan_id,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at or self.clock.now(),
            created_at=self.clock.now(),
        )
        self.session.add(record)
        await self.session.flush()
        return LifeEvent.model_validate(record, from_attributes=True)

    async def get_event(self, event_id: str) -> Optional[LifeEvent]:
        record = await self.session.get(LifeEventRecord, event_id)
        if record:
            return LifeEvent.model_validate(record, from_attributes=True)
        return None

    async def list_events(self, character_id: str, limit: Optional[int] = None) -> List[LifeEvent]:
        stmt = select(LifeEventRecord).where(LifeEventRecord.character_id == character_id).order_by(LifeEventRecord.occurred_at.desc())
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.scalars(stmt)
        return [LifeEvent.model_validate(r, from_attributes=True) for r in result]

    async def create_goal(
        self,
        character_id: str,
        title: str,
        description: str,
        importance: float = 0.5,
        progress_per_completion: float = 0.10,
    ) -> LifeGoal:
        record = LifeGoalRecord(
            character_id=character_id,
            title=title,
            description=description,
            importance=importance,
            status=LifeGoalStatus.ACTIVE.value,
            progress=0.0,
            progress_per_completion=progress_per_completion,
            created_at=self.clock.now(),
            updated_at=self.clock.now(),
        )
        self.session.add(record)
        await self.session.flush()
        return LifeGoal.model_validate(record, from_attributes=True)

    async def get_goal(self, goal_id: str) -> Optional[LifeGoal]:
        record = await self.session.get(LifeGoalRecord, goal_id)
        if record:
            return LifeGoal.model_validate(record, from_attributes=True)
        return None

    async def list_goals(self, character_id: str) -> List[LifeGoal]:
        stmt = select(LifeGoalRecord).where(LifeGoalRecord.character_id == character_id).order_by(LifeGoalRecord.created_at.desc())
        result = await self.session.scalars(stmt)
        return [LifeGoal.model_validate(r, from_attributes=True) for r in result]

    async def update_goal(self, goal_id: str, status: Optional[LifeGoalStatus] = None, progress: Optional[float] = None) -> LifeGoal:
        record = await self.session.get(LifeGoalRecord, goal_id)
        if not record:
            raise ValueError(f"Goal {goal_id} not found.")
        if status is not None:
            record.status = status.value
        if progress is not None:
            record.progress = progress
        record.updated_at = self.clock.now()
        await self.session.flush()
        return LifeGoal.model_validate(record, from_attributes=True)

    async def advance_goal_progress(
        self,
        goal_id: str,
        delta: Optional[float] = None,
        settlement_time: Optional[datetime] = None,
    ) -> Optional[LifeGoal]:
        """
        Advance progress for an active LifeGoal.
        Invariants 22, Standards 25 & 26:
        - If goal not found or not ACTIVE: returns None.
        - Increments by delta if provided, else goal.progress_per_completion.
        - Clamped to [0.0, 1.0].
        - If progress reaches 1.0, transitions status to COMPLETED and creates
          an immutable SUCCESS LifeEvent with idempotency_key 'goal_completed:<goal_id>'.
        """
        record = await self.session.get(LifeGoalRecord, goal_id)
        if not record or record.status != LifeGoalStatus.ACTIVE.value:
            return None

        increment = delta if delta is not None else record.progress_per_completion
        new_progress = min(1.0, record.progress + increment)
        record.progress = new_progress
        record.updated_at = settlement_time or self.clock.now()

        if new_progress >= 1.0:
            record.status = LifeGoalStatus.COMPLETED.value
            event_key = f"goal_completed:{record.id}"
            await self.create_event(
                character_id=record.character_id,
                event_type=LifeEventType.SUCCESS,
                title=f"Achieved Goal: {record.title}",
                description=f"Aevum successfully achieved the life goal: {record.title}.",
                significance=record.importance,
                occurred_at=settlement_time or self.clock.now(),
                idempotency_key=event_key,
            )

        await self.session.flush()
        return LifeGoal.model_validate(record, from_attributes=True)

    async def initialize_aevum_life(self, character_id: str = "aevum") -> None:
        """Initialize the baseline life data for Aevum."""
        record = await self.session.get(LifeStateRecord, character_id)
        if record:
            return  # Already seeded
            
        record = LifeStateRecord(
            id=character_id,
            character_id=character_id,
            current_activity="IDLE",
            current_location="HOME",
            status="ACTIVE",
            updated_at=self.clock.now(),
        )
        self.session.add(record)
        
        goal = LifeGoalRecord(
            character_id=character_id,
            title="Improve at playing instrument",
            description="Practice regularly to improve technique and musicality.",
            status="ACTIVE",
            progress=0.0,
            progress_per_completion=0.10,
            created_at=self.clock.now(),
            updated_at=self.clock.now(),
        )
        self.session.add(goal)
        
        plan1 = LifePlanRecord(
            character_id=character_id,
            title="Practice music",
            description="Practice music sometime this week.",
            status="PLANNED",
            created_at=self.clock.now(),
            updated_at=self.clock.now(),
        )
        self.session.add(plan1)
        
        plan2 = LifePlanRecord(
            character_id=character_id,
            title="Continue reading book",
            description="Continue reading the current book.",
            status="PLANNED",
            created_at=self.clock.now(),
            updated_at=self.clock.now(),
        )
        self.session.add(plan2)

        # Seed physiological state if missing
        phys_rec = await self.session.get(CharacterPhysiologicalRecord, character_id)
        if not phys_rec:
            phys_rec = CharacterPhysiologicalRecord(
                id=character_id,
                character_id=character_id,
                energy=0.75,
                fatigue=0.15,
                stress=0.15,
                sleep_pressure=0.20,
                qualitative_band=PhysiologicalBand.STEADY.value,
                updated_at=self.clock.now(),
            )
            self.session.add(phys_rec)
        
        await self.session.flush()

    async def get_physiological_state(self, character_id: str = "aevum") -> CharacterPhysiologicalState:
        record = await self.session.get(CharacterPhysiologicalRecord, character_id)
        if not record:
            record = CharacterPhysiologicalRecord(
                id=character_id,
                character_id=character_id,
                energy=0.75,
                fatigue=0.15,
                stress=0.15,
                sleep_pressure=0.20,
                qualitative_band=PhysiologicalBand.STEADY.value,
                updated_at=self.clock.now(),
            )
            self.session.add(record)
            await self.session.flush()

        band = PhysiologicalBand(record.qualitative_band)
        return CharacterPhysiologicalState(
            energy=record.energy,
            fatigue=record.fatigue,
            stress=record.stress,
            sleep_pressure=record.sleep_pressure,
            qualitative_band=band,
            updated_at=record.updated_at,
        )

    async def update_physiological_state(
        self,
        character_id: str,
        state: CharacterPhysiologicalState,
    ) -> CharacterPhysiologicalState:
        record = await self.session.get(CharacterPhysiologicalRecord, character_id)
        if not record:
            record = CharacterPhysiologicalRecord(
                id=character_id,
                character_id=character_id,
            )
            self.session.add(record)

        record.energy = state.energy
        record.fatigue = state.fatigue
        record.stress = state.stress
        record.sleep_pressure = state.sleep_pressure
        record.qualitative_band = state.qualitative_band.value
        record.version += 1
        record.updated_at = self.clock.now()
        await self.session.flush()

        return state

    async def record_state_transition(
        self,
        record: StateTransitionRecord,
    ) -> None:
        db_rec = StateTransitionAuditRecord(
            id=record.id,
            character_id=record.character_id,
            timestamp=record.timestamp,
            trigger_type=record.trigger_type.value,
            activity_id=record.activity_id,
            time_interval_seconds=record.time_interval_seconds,
            circadian_modifier=record.circadian_modifier,
            rule_id=record.rule_id,
            reason=record.reason,
            before_state_json=json.dumps(record.before_state),
            after_state_json=json.dumps(record.after_state),
            delta_json=json.dumps(record.delta),
        )
        self.session.add(db_rec)
        await self.session.flush()

    async def list_state_transitions(
        self,
        character_id: str = "aevum",
        limit: Optional[int] = None,
    ) -> List[StateTransitionRecord]:
        stmt = select(StateTransitionAuditRecord).where(
            StateTransitionAuditRecord.character_id == character_id
        ).order_by(StateTransitionAuditRecord.timestamp.desc())
        if limit:
            stmt = stmt.limit(limit)
        results = (await self.session.scalars(stmt)).all()
        records = []
        for r in results:
            records.append(
                StateTransitionRecord(
                    id=r.id,
                    character_id=r.character_id,
                    timestamp=r.timestamp,
                    trigger_type=StateTransitionTrigger(r.trigger_type),
                    activity_id=r.activity_id,
                    time_interval_seconds=r.time_interval_seconds,
                    before_state=json.loads(r.before_state_json),
                    after_state=json.loads(r.after_state_json),
                    delta=json.loads(r.delta_json),
                    circadian_modifier=r.circadian_modifier,
                    rule_id=r.rule_id,
                    reason=r.reason,
                )
            )
        return records
