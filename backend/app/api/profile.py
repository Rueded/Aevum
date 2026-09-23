"""User Profile Editor and Reality Ledger API endpoints for Project Aevum.

Provides sovereign user controls to inspect, edit, lock, unlock, confirm,
and delete facts in Aevum's Character Core and Reality Ledger.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.bible_service import CharacterBibleService
from app.character.core_models import CharacterCore
from app.character.core_service import (
    AevumCanonicalNotDirectlyEditableError,
    CandidateNotEditableError,
    CharacterCoreService,
    FactLockedError,
    SystemBaselineImmutableError,
)
from app.db.session import get_db_session
from app.reality.ledger_models import RealityLedgerProjection
from app.reality.ledger_service import RealityLedgerService
from app.reality.models import CoreFactItem
from app.reality.registry import InvalidFactValueError

router = APIRouter(prefix="/character/profile", tags=["Character Profile"])


class ProfileResponse(BaseModel):
    """Full character profile including Core, Bible summary, and Reality Ledger."""

    character_id: str
    core: CharacterCore
    bible_version: int
    behavioral_guidelines: list[str]
    reasoning_guidelines: list[str]
    flaws: list[str]
    ledger: RealityLedgerProjection


class UpdateCoreFactsRequest(BaseModel):
    """Request payload for updating user-configurable core facts."""

    updates: dict[str, Any] = Field(
        ...,
        description="Key-value mapping of facts to update (e.g. {'identity.age': 22})",
    )


class FactMutationResponse(BaseModel):
    """Generic acknowledgment for mutation operations."""

    status: str
    fact_key: str
    fact: CoreFactItem | None = None


@router.get(
    "",
    response_model=ProfileResponse,
    summary="Retrieve full character profile, Bible priors, and Reality Ledger",
)
async def get_character_profile(
    character_id: str = "aevum",
    db: AsyncSession = Depends(get_db_session),
) -> ProfileResponse:
    """Retrieve full Character Core, Bible behavioral priors, and Reality Ledger."""
    core_service = CharacterCoreService(db)
    core = await core_service.get_core(character_id)

    ledger_service = RealityLedgerService(db)
    ledger = await ledger_service.get_ledger(character_id)

    bible = CharacterBibleService.get_bible()
    behavioral_lines = list(bible.behavioral_priors.social_interaction) + list(
        bible.behavioral_priors.conflict_and_hurt
    ) + list(bible.behavioral_priors.affection_and_boundaries)
    reasoning_lines = list(bible.reasoning_priors.comprehensive_synthesis) + list(
        bible.reasoning_priors.contextual_bridging
    ) + list(bible.reasoning_priors.epistemic_calibration)

    return ProfileResponse(
        character_id=character_id,
        core=core,
        bible_version=bible.version,
        behavioral_guidelines=behavioral_lines,
        reasoning_guidelines=reasoning_lines,
        flaws=list(bible.flaws.traits),
        ledger=ledger,
    )


@router.patch(
    "/core",
    response_model=ProfileResponse,
    summary="Update user-configurable core facts (single current reality)",
)
async def update_character_core(
    payload: UpdateCoreFactsRequest,
    character_id: str = "aevum",
    db: AsyncSession = Depends(get_db_session),
) -> ProfileResponse:
    """Update user-configurable facts.

    Authority Matrix:
    - USER_LOCKED: HTTP 409 Conflict (must unlock first).
    - SYSTEM_BASELINE: Allowed to edit; atomically replaces row with USER_CONFIGURED + CANONICAL.
    - USER_CONFIGURED: Allowed to edit.
    - AEVUM_CANONICAL: HTTP 409 Conflict (direct modification reserved for 7B.3 Reality Reconciliation).
    - CANDIDATE: HTTP 409 Conflict (must confirm or reject via dedicated endpoints).
    """
    if not payload.updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Updates mapping cannot be empty.",
        )

    core_service = CharacterCoreService(db)
    try:
        await core_service.bulk_update_user_fields(character_id, payload.updates)
    except FactLockedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AevumCanonicalNotDirectlyEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CandidateNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidFactValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return await get_character_profile(character_id=character_id, db=db)


@router.post(
    "/core/{fact_key:path}/lock",
    response_model=FactMutationResponse,
    summary="Lock a fact (sets authority=USER_LOCKED, locked=True)",
)
async def lock_fact(
    fact_key: str,
    character_id: str = "aevum",
    db: AsyncSession = Depends(get_db_session),
) -> FactMutationResponse:
    """Sovereign user lock on a fact. Prevents autonomous drift or LLM mutation."""
    core_service = CharacterCoreService(db)
    try:
        fact = await core_service.lock_fact(character_id, fact_key)
        return FactMutationResponse(status="locked", fact_key=fact_key, fact=fact)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/core/{fact_key:path}/unlock",
    response_model=FactMutationResponse,
    summary="Unlock a fact (sets authority=USER_CONFIGURED, locked=False)",
)
async def unlock_fact(
    fact_key: str,
    character_id: str = "aevum",
    db: AsyncSession = Depends(get_db_session),
) -> FactMutationResponse:
    """Unlock a previously locked fact."""
    core_service = CharacterCoreService(db)
    try:
        fact = await core_service.unlock_fact(character_id, fact_key)
        return FactMutationResponse(status="unlocked", fact_key=fact_key, fact=fact)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/core/{fact_key:path}/confirm",
    response_model=FactMutationResponse,
    summary="Confirm candidate fact (transitions to USER_CONFIGURED + CANONICAL)",
)
async def confirm_candidate(
    fact_key: str,
    character_id: str = "aevum",
    db: AsyncSession = Depends(get_db_session),
) -> FactMutationResponse:
    """Confirm an Aevum-inferred candidate fact into canonical reality under user authority."""
    core_service = CharacterCoreService(db)
    try:
        fact = await core_service.confirm_candidate_fact(character_id, fact_key)
        return FactMutationResponse(status="confirmed", fact_key=fact_key, fact=fact)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc


@router.post(
    "/core/{fact_key:path}/reject",
    response_model=FactMutationResponse,
    summary="Reject candidate fact (cleanly discard/remove candidate)",
)
async def reject_candidate(
    fact_key: str,
    character_id: str = "aevum",
    db: AsyncSession = Depends(get_db_session),
) -> FactMutationResponse:
    """Reject and cleanly discard a candidate fact without marking it as FALSIFIED."""
    core_service = CharacterCoreService(db)
    try:
        deleted = await core_service.reject_candidate_fact(character_id, fact_key)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidate fact '{fact_key}' not found.",
            )
        return FactMutationResponse(status="rejected", fact_key=fact_key, fact=None)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/core/{fact_key:path}",
    response_model=FactMutationResponse,
    summary="Delete an unlocked emergent or user-configured fact",
)
async def delete_fact(
    fact_key: str,
    character_id: str = "aevum",
    db: AsyncSession = Depends(get_db_session),
) -> FactMutationResponse:
    """Delete a fact. Returns 409 on locked facts and 403 on foundational baseline facts."""
    core_service = CharacterCoreService(db)
    try:
        deleted = await core_service.delete_fact(character_id, fact_key)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fact '{fact_key}' not found.",
            )
        return FactMutationResponse(status="deleted", fact_key=fact_key, fact=None)
    except FactLockedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except SystemBaselineImmutableError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
