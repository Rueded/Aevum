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
)
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

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class OptimisticConcurrencyError(Exception):
    """Raised when an update fails due to a version mismatch."""
    pass

class LifeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_life_state(self, character_id: str = "aevum") -> LifeState:
        record = await self.session.get(LifeStateRecord, character_id)
        if not record:
            record = LifeStateRecord(
                id=character_id,
                character_id=character_id,
                current_activity="REST",
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
        record.updated_at = utc_now()
        await self.session.flush()
        return LifeState.model_validate(record, from_attributes=True)

    async def create_activity(self, character_id: str, activity_type: LifeActivityType, title: str, description: str, location: str, importance: float = 0.5, planned_end_at: Optional[datetime] = None, plan_id: Optional[str] = None) -> LifeActivity:
        record = LifeActivityRecord(
            character_id=character_id,
            activity_type=activity_type.value,
            title=title,
            description=description,
            location=location,
            status=LifeActivityStatus.ONGOING.value,
            importance=importance,
            planned_end_at=planned_end_at,
            plan_id=plan_id,
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

    async def update_activity_status(self, activity_id: str, status: LifeActivityStatus) -> LifeActivity:
        record = await self.session.get(LifeActivityRecord, activity_id)
        if not record:
            raise ValueError(f"Activity {activity_id} not found.")
        record.status = status.value
        if status == LifeActivityStatus.COMPLETED:
            record.completed_at = utc_now()
        await self.session.flush()
        return LifeActivity.model_validate(record, from_attributes=True)

    async def create_plan(self, character_id: str, title: str, description: str, importance: float = 0.5, planned_start: Optional[datetime] = None, planned_end: Optional[datetime] = None) -> LifePlan:
        record = LifePlanRecord(
            character_id=character_id,
            title=title,
            description=description,
            importance=importance,
            planned_start=planned_start,
            planned_end=planned_end,
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
        record.status = status.value
        record.updated_at = utc_now()
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
        record = LifeEventRecord(
            character_id=character_id,
            event_type=event_type.value,
            title=title,
            description=description,
            significance=significance,
            plan_id=plan_id,
            idempotency_key=idempotency_key,
        )
        if occurred_at is not None:
            record.occurred_at = occurred_at
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

    async def create_goal(self, character_id: str, title: str, description: str, importance: float = 0.5) -> LifeGoal:
        record = LifeGoalRecord(
            character_id=character_id,
            title=title,
            description=description,
            importance=importance,
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
        record.updated_at = utc_now()
        await self.session.flush()
        return LifeGoal.model_validate(record, from_attributes=True)

    async def initialize_aevum_life(self, character_id: str = "aevum") -> None:
        """Initialize the baseline life data for Aevum."""
        # Check if already initialized by looking for the state
        record = await self.session.get(LifeStateRecord, character_id)
        if record:
            return  # Already seeded
            
        # Create LifeState
        record = LifeStateRecord(
            id=character_id,
            character_id=character_id,
            current_activity="REST",
            current_location="HOME",
            status="ACTIVE",
        )
        self.session.add(record)
        
        # Create Goal
        goal = LifeGoalRecord(
            character_id=character_id,
            title="Improve at playing instrument",
            description="Practice regularly to improve technique and musicality.",
            status="ACTIVE",
        )
        self.session.add(goal)
        
        # Create Plans
        plan1 = LifePlanRecord(
            character_id=character_id,
            title="Practice music",
            description="Practice music sometime this week.",
            status="PLANNED",
        )
        self.session.add(plan1)
        
        plan2 = LifePlanRecord(
            character_id=character_id,
            title="Continue reading book",
            description="Continue reading the current book.",
            status="PLANNED",
        )
        self.session.add(plan2)
        
        await self.session.flush()
