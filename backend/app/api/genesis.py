"""FastAPI router for Character Genesis and Blueprint operations (Phase 17.1).

Endpoints:
- GET /character/genesis/presets: Curated preset library for desktop Genesis Wizard.
- POST /character/genesis: Atomic character genesis transaction.
- GET /character/blueprint: Retrieve current Tier A character blueprint.
- PUT /character/blueprint: Update Tier A static persona in Daily Settings (bumps version, 0 mutation to experiences).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.genesis_dtos import (
    BlueprintUpdateRequest,
    CharacterCreationPayload,
    CharacterCreationResponse,
    GenesisAIGenerateRequest,
    GenesisPresetsResponse,
)
from app.character.genesis_models import CharacterBlueprintConfig
from app.character.genesis_service import (
    GenesisCompilationError,
    GenesisOrchestrationService,
)
from app.db.session import get_db_session

router = APIRouter(prefix="/character", tags=["Character Genesis"])


@router.get(
    "/genesis/presets",
    response_model=GenesisPresetsResponse,
    summary="Retrieve curated presets for character creation wizard",
)
async def get_genesis_presets() -> GenesisPresetsResponse:
    """Return preset options for archetypes, traits, speaking styles, lifestyle, and epistemic depths."""
    return GenesisOrchestrationService.get_presets()


@router.post(
    "/genesis/ai-generate",
    response_model=CharacterCreationPayload,
    summary="Auto-generate complete character genesis payload from user keywords/adjectives",
)
async def ai_generate_companion_genesis(
    req: GenesisAIGenerateRequest,
) -> CharacterCreationPayload:
    """Generate complete companion blueprint fields based on user keywords or adjectives."""
    try:
        return await GenesisOrchestrationService.generate_from_keywords(req.prompt)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI genesis generation failed: {str(e)}",
        )


@router.post(
    "/genesis",
    response_model=CharacterCreationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute atomic companion genesis",
)
async def create_companion_genesis(
    payload: CharacterCreationPayload,
    db: AsyncSession = Depends(get_db_session),
) -> CharacterCreationResponse:
    """Execute atomic companion genesis.
    
    Guarantees:
    - Atomic all-or-nothing: either all records (Tier A, Tier B, Tier C initial baseline) succeed or all roll back.
    - Zero continuous psychological sliders: discrete semantic parameters only.
    - Seeds initial awakening greeting.
    """
    try:
        return await GenesisOrchestrationService.execute_atomic_genesis(
            db=db,
            payload=payload,
            character_id="aevum",
            user_id="user",
        )
    except GenesisCompilationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Atomic genesis failed: {str(e)}",
        )


@router.get(
    "/blueprint",
    response_model=CharacterBlueprintConfig,
    summary="Retrieve current Tier A character blueprint",
)
async def get_character_blueprint(
    db: AsyncSession = Depends(get_db_session),
) -> CharacterBlueprintConfig:
    """Retrieve the current Tier A CharacterBlueprintConfig for the companion."""
    blueprint = await GenesisOrchestrationService.get_blueprint(db=db, character_id="aevum")
    if blueprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No character blueprint found. Companion has not undergone genesis.",
        )
    return blueprint


@router.put(
    "/blueprint",
    response_model=CharacterBlueprintConfig,
    summary="Update Tier A character blueprint in Daily Settings",
)
async def update_character_blueprint(
    update_req: BlueprintUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> CharacterBlueprintConfig:
    """Update Tier A static character description in Daily Settings.
    
    Hard Invariants:
    - Bumps version (optimistic evolution).
    - Strictly NEVER modifies or overwrites runtime relationships, experiences, or memories.
    """
    try:
        return await GenesisOrchestrationService.update_blueprint(
            db=db,
            update_req=update_req,
            character_id="aevum",
        )
    except GenesisCompilationError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Blueprint update failed: {str(e)}",
        )
