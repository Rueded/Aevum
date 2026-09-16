from datetime import datetime
from typing import List
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.life.models import LifeActivityStatus, LifePlanStatus, LifeEventType, LifeActivityType, LifeEvent
from app.db.models import LifeStateRecord, LifePlanRecord, LifeActivityRecord, LifeEventRecord
from app.life.services import LifeService

class LifeSimulationResult(BaseModel):
    processed_plans: int = 0
    started_activities: int = 0
    completed_activities: int = 0
    generated_events: int = 0
    updated_goals: int = 0
    life_events_created: List[LifeEvent] = Field(default_factory=list)

class LifeSimulator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.service = LifeService(session)

    async def reconcile(self, character_id: str, now: datetime) -> LifeSimulationResult:
        result = LifeSimulationResult()
        
        # 1. Complete overdue activities
        stmt = select(LifeActivityRecord).where(
            LifeActivityRecord.character_id == character_id,
            LifeActivityRecord.status == LifeActivityStatus.ONGOING.value,
            LifeActivityRecord.planned_end_at <= now
        ).order_by(LifeActivityRecord.planned_end_at.asc())
        
        ongoing_activities = (await self.session.scalars(stmt)).all()
        
        for activity in ongoing_activities:
            activity.status = LifeActivityStatus.COMPLETED.value
            activity.completed_at = now
            result.completed_activities += 1
            
            # Update LifeState to REST if it was doing this activity
            state = await self.service.get_life_state(character_id)
            if state.current_activity == activity.title:
                await self.service.update_life_state(
                    character_id, 
                    current_activity="REST", 
                    current_location="HOME", 
                    expected_version=state.version
                )
            
            # Generate LifeEvent exactly once
            life_event = await self.service.create_event(
                character_id=character_id,
                event_type=LifeEventType.ACTIVITY_COMPLETED,
                title=f"Completed {activity.title}",
                description=f"Aevum completed the activity: {activity.title}",
                significance=0.5
            )
            result.life_events_created.append(life_event)
            result.generated_events += 1
            
            # Update plan status if applicable
            if activity.plan_id:
                plan = await self.service.get_plan(activity.plan_id)
                if plan and plan.status != LifePlanStatus.COMPLETED:
                    await self.service.update_plan_status(plan.id, LifePlanStatus.COMPLETED)

        # 2. Start due plans
        stmt = select(LifePlanRecord).where(
            LifePlanRecord.character_id == character_id,
            LifePlanRecord.status == LifePlanStatus.PLANNED.value,
            LifePlanRecord.planned_start <= now
        ).order_by(LifePlanRecord.planned_start.asc())
        
        due_plans = (await self.session.scalars(stmt)).all()
        
        for plan in due_plans:
            plan.status = LifePlanStatus.IN_PROGRESS.value
            plan.updated_at = now
            result.processed_plans += 1
            
            # Start Activity
            # First check if we already have an activity for this plan to ensure idempotency
            stmt_act = select(LifeActivityRecord).where(
                LifeActivityRecord.plan_id == plan.id
            )
            existing_act = (await self.session.scalars(stmt_act)).first()
            if not existing_act:
                act = await self.service.create_activity(
                    character_id=character_id,
                    activity_type=LifeActivityType.OTHER, # Default or derive
                    title=plan.title,
                    description=plan.description,
                    location="HOME", # Default
                    importance=plan.importance,
                    planned_end_at=plan.planned_end,
                    plan_id=plan.id
                )
                result.started_activities += 1
                
                # Update LifeState
                state = await self.service.get_life_state(character_id)
                await self.service.update_life_state(
                    character_id, 
                    current_activity=act.title, 
                    current_location=act.location, 
                    expected_version=state.version
                )
                
                # Create Event
                life_event = await self.service.create_event(
                    character_id=character_id,
                    event_type=LifeEventType.OTHER,
                    title=f"Started {act.title}",
                    description=f"Aevum started planned activity: {act.title}",
                    significance=0.5
                )
                result.life_events_created.append(life_event)
                result.generated_events += 1

        await self.session.flush()
        return result

async def reconcile_current_life(session: AsyncSession, character_id: str = "aevum") -> LifeSimulationResult:
    from app.core.time import now_utc
    simulator = LifeSimulator(session)
    return await simulator.reconcile(character_id, now_utc())
