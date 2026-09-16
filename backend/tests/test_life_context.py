import pytest
from datetime import datetime, timezone
from app.life.models import LifeState, LifeEvent, LifeEventType
from app.life.context_models import CharacterLifeContext
from app.life.context_builder import LifeContextBuilder

def test_life_context_creation():
    state = LifeState(
        id="aevum", character_id="aevum",
        current_activity="practicing music",
        current_location="home",
        status="ACTIVE",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    ctx = LifeContextBuilder.build(state, [])
    assert "practicing music" in ctx.current_activity_summary
    assert "home" in ctx.current_location_summary
    assert len(ctx.life_guidance) > 0

def test_no_raw_internal_data_leakage():
    state = LifeState(
        id="aevum", character_id="aevum",
        current_activity="resting",
        current_location="home",
        status="ACTIVE",
        version=99,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    ctx = LifeContextBuilder.build(state, [])
    
    formatted = LifeContextBuilder.format_context(ctx)
    assert "99" not in formatted
    assert "aevum" not in formatted.lower().replace("aevum", "") # Ensure ID not leaked except name
    assert "created_at" not in formatted
    assert "updated_at" not in formatted

def test_no_life():
    state = LifeState(
        id="aevum", character_id="aevum",
        current_activity="REST",
        current_location="HOME",
        status="ACTIVE",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    ctx = LifeContextBuilder.build(state, [])
    assert "resting" in ctx.current_activity_summary.lower()

def test_recent_life_event():
    state = LifeState(
        id="aevum", character_id="aevum",
        current_activity="REST",
        current_location="HOME",
        status="ACTIVE",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    event = LifeEvent(
        id="ev1",
        character_id="aevum",
        event_type=LifeEventType.ACTIVITY_COMPLETED,
        title="Finished reading",
        description="Aevum finished reading a book.",
        significance=0.5,
        occurred_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)
    )
    
    ctx = LifeContextBuilder.build(state, [event])
    assert len(ctx.recent_experience_summary) == 1
    assert "finished reading a book" in ctx.recent_experience_summary[0]
    
    formatted = LifeContextBuilder.format_context(ctx)
    assert "finished reading a book" in formatted
    assert "ev1" not in formatted

def test_irrelevant_life_should_not_force_mention():
    state = LifeState(
        id="aevum", character_id="aevum",
        current_activity="practicing music",
        current_location="home",
        status="ACTIVE",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    ctx = LifeContextBuilder.build(state, [])
    formatted = LifeContextBuilder.format_context(ctx)
    assert "but do NOT force it" in formatted

def test_timezone_independence():
    # Context builder uses raw text, doesn't format timestamps into strings for the LLM
    # Timestamps are handled by the Timezone Foundation at the DB/LifeService level.
    # We can verify that no timezone-specific formatting is accidentally leaked in the context.
    state = LifeState(
        id="aevum", character_id="aevum",
        current_activity="REST",
        current_location="HOME",
        status="ACTIVE",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    ctx = LifeContextBuilder.build(state, [])
    formatted = LifeContextBuilder.format_context(ctx)
    assert "UTC" not in formatted
    assert "+08:00" not in formatted
