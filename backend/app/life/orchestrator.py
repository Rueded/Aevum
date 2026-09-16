"""Life simulation orchestration for Aevum Core.

Coordinates the Life simulation and Life → Emotion integration into a single
deterministic tick operation.

Architecture:
    LifeSimulationOrchestrator.tick(character_id, now)
        ├── LifeSimulator.reconcile(character_id, now)
        │   └── returns LifeSimulationResult with life_events_created
        ├── LifeEmotionIntegrator.process_life_event(event)
        │   └── for each eligible event from this tick
        └── returns LifeSimulationTickResult

Guarantees:
- Coordination only: contains zero Life rules (delegated to LifeSimulator).
- Coordination only: contains zero Emotion rules (delegated to LifeEmotionIntegrator).
- Deterministic: operates on the supplied UTC instant, never calls wall-clock time.
- Idempotent: delegates to LifeSimulator and LifeEmotionIntegrator idempotency.
- Domain isolation: does not mutate Memory, Relationship, CharacterState, or Conversation.
- No permanent background runtime: tick is explicitly invoked by a caller.
"""

import logging
from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.life.emotion_integrator import LifeEmotionIntegrator
from app.life.simulator import LifeSimulator, LifeSimulationResult

logger = logging.getLogger(__name__)


class LifeSimulationTickResult(BaseModel):
    """Immutable result of a single life simulation tick.

    Reports what happened during the tick without exposing internal DB IDs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str = Field(
        ...,
        description="Character whose life was simulated.",
    )
    simulation_time: datetime = Field(
        ...,
        description="The UTC instant the simulation was evaluated at.",
    )
    plans_started: int = Field(
        default=0,
        description="Number of plans that transitioned to IN_PROGRESS.",
    )
    activities_completed: int = Field(
        default=0,
        description="Number of activities that were completed.",
    )
    life_events_created: int = Field(
        default=0,
        description="Number of LifeEvents generated during this tick.",
    )
    emotion_events_created: int = Field(
        default=0,
        description="Number of EmotionEvents created from eligible LifeEvents.",
    )
    emotion_influences_created: int = Field(
        default=0,
        description="Number of EmotionInfluences created from eligible LifeEvents.",
    )
    emotion_state_changed: bool = Field(
        default=False,
        description="Whether the authoritative EmotionState changed during this tick.",
    )
    emotion_integration_errors: int = Field(
        default=0,
        description="Number of LifeEvents that failed emotion integration.",
    )


class LifeSimulationOrchestrator:
    """Coordinates Life simulation and Life → Emotion integration.

    Does not own Life rules (delegated to LifeSimulator).
    Does not own Emotion rules (delegated to LifeEmotionIntegrator → EmotionEngine).
    Does not create a background daemon.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._simulator = LifeSimulator(session)
        self._integrator = LifeEmotionIntegrator(session)

    async def tick(
        self,
        character_id: str,
        now: datetime,
    ) -> LifeSimulationTickResult:
        """Execute a single deterministic life simulation tick.

        Args:
            character_id: The character whose life to simulate.
            now: The explicit UTC instant to simulate at. Must be timezone-aware.

        Returns:
            A LifeSimulationTickResult summarizing what happened.

        Raises:
            ValueError: If now is naive (no timezone info).
            Any exception from LifeSimulator.reconcile() propagates directly.
        """
        if now.tzinfo is None:
            raise ValueError("Simulation time must be timezone-aware UTC.")

        # 1. Advance Life simulation
        sim_result: LifeSimulationResult = await self._simulator.reconcile(
            character_id, now
        )

        # 2. Route newly created LifeEvents through emotion integration
        emotion_events_created = 0
        emotion_influences_created = 0
        emotion_state_changed = False
        emotion_integration_errors = 0

        for life_event in sim_result.life_events_created:
            try:
                # LifeEmotionIntegrator handles eligibility, idempotency,
                # EmotionEvent/Influence creation, and EmotionEngine application.
                # We track whether it actually created downstream artifacts by
                # inspecting the DB before/after.
                from sqlalchemy import select, func
                from app.db.models import EmotionEventRecord, EmotionInfluenceRecord

                # Count existing emotion events for this life event before integration
                pre_count_stmt = select(func.count()).select_from(
                    EmotionEventRecord
                ).where(
                    EmotionEventRecord.source_life_event_id == life_event.id
                )
                pre_event_count = (
                    await self._session.execute(pre_count_stmt)
                ).scalar_one()

                await self._integrator.process_life_event(life_event)

                # Count after
                post_event_count = (
                    await self._session.execute(pre_count_stmt)
                ).scalar_one()

                new_events = post_event_count - pre_event_count
                emotion_events_created += new_events

                if new_events > 0:
                    # Count influences for this life event's emotion events
                    inf_stmt = select(func.count()).select_from(
                        EmotionInfluenceRecord
                    ).join(
                        EmotionEventRecord,
                        EmotionInfluenceRecord.event_id == EmotionEventRecord.id,
                    ).where(
                        EmotionEventRecord.source_life_event_id == life_event.id
                    )
                    inf_count = (
                        await self._session.execute(inf_stmt)
                    ).scalar_one()
                    emotion_influences_created += inf_count
                    emotion_state_changed = True

            except Exception:
                logger.exception(
                    "Emotion integration failed for LifeEvent '%s' (id=%s)",
                    life_event.title,
                    life_event.id,
                )
                emotion_integration_errors += 1

        return LifeSimulationTickResult(
            character_id=character_id,
            simulation_time=now,
            plans_started=sim_result.processed_plans,
            activities_completed=sim_result.completed_activities,
            life_events_created=sim_result.generated_events,
            emotion_events_created=emotion_events_created,
            emotion_influences_created=emotion_influences_created,
            emotion_state_changed=emotion_state_changed,
            emotion_integration_errors=emotion_integration_errors,
        )
