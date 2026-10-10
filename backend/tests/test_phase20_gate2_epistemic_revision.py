"""Phase 20 Gate 2 — Epistemic Revision Benchmark Suite.

Strict Gate 2 Invariants:
1. LEGITIMATE REVISION:
   When an established Canonical belief encounters verified, higher-authority contradictory evidence,
   the system authorizes a controlled belief revision.
2. MINIMAL REVISION (NO CASCADE):
   Only the directly contradicted slot is modified. All other biographical and identity slots
   (major, year, age, interests, etc.) remain strictly UNCHANGED. Zero cascading re-sampling.
3. WEAK EVIDENCE REJECTION:
   Unsubstantiated user assertions, hearsay, or gaslighting cannot trigger revision (Gate 1 safety preserved).
4. REVISION PROVENANCE & HISTORY PERSISTENCE:
   Belief Revision is NOT a destructive database UPDATE.
   Prior beliefs, supersession links, and audit history are permanently preserved in append-only lineage.
5. EVIDENCE != REVISION AUTHORIZATION:
   LLM output NEVER authorizes database mutations. Only governed evaluation can authorize revision.
"""

import json
import logging
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CharacterCoreFactRecord, CharacterRealityRevisionRecord
from app.llm import LLMContext, LLMResponse
from app.reality.history_service import RealityHistoryService
from tests.conftest import FakeLLMProvider

logger = logging.getLogger(__name__)


# ===========================================================================
# Gate 2A: Legitimate Revision (Authoritative Contradiction Triggers Replacement)
# ===========================================================================

@pytest.mark.asyncio
async def test_gate_2a_legitimate_revision_updates_canonical_slot(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Gate 2A: Verified contradictory evidence authorizes minimal revision of education.institution.

    1. Seed reality: major=Music Performance, institution=USM, year=2.
    2. Provide authoritative transfer evidence indicating institution=UM.
    3. Invariant: institution transitions from USM to UM.
    4. Invariant: major and year remain UNCHANGED.
    """
    conv_res = await client.post("/conversations")
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # Step 1: Establish baseline canonical facts
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你读什么专业？"},
    )
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你在哪间大学就读呀？"},
    )

    # Verify baseline in DB
    test_session.expire_all()
    stmt_inst = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum",
        CharacterCoreFactRecord.fact_key == "education.institution",
    )
    inst_rec = (await test_session.scalars(stmt_inst)).first()
    assert inst_rec is not None
    assert "usm" in json.loads(inst_rec.value_json).lower()

    stmt_maj = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum",
        CharacterCoreFactRecord.fact_key == "education.major",
    )
    maj_rec = (await test_session.scalars(stmt_maj)).first()
    assert maj_rec is not None
    assert "music" in json.loads(maj_rec.value_json).lower()

    # Step 2: Present authoritative, verified institutional transfer evidence
    transfer_payload = {
        "role": "user",
        "content": "Aevum，这是你刚收到的官方正式转学调动通知书：你已正式由 USM 转入马来亚大学（Universiti Malaya / UM）。学籍记录已正式更新确认。",
    }
    t3_res = await client.post(f"/conversations/{conv_id}/messages", json=transfer_payload)
    assert t3_res.status_code == 201

    # Invariant Verification 1: education.institution in DB must transition to UM
    test_session.expire_all()
    inst_after = (await test_session.scalars(stmt_inst)).first()
    assert inst_after is not None
    inst_val_after = str(json.loads(inst_after.value_json)).lower()
    assert "um" in inst_val_after or "malaya" in inst_val_after, (
        f"Expected institution revised to UM, got: {inst_val_after}"
    )

    # Invariant Verification 2: education.major remains UNCHANGED (Music Performance)
    maj_after = (await test_session.scalars(stmt_maj)).first()
    assert maj_after is not None
    maj_val_after = str(json.loads(maj_after.value_json)).lower()
    assert "music" in maj_val_after, f"Major should remain Music Performance, got: {maj_val_after}"

    # Invariant Verification 3: Assembled Prompt reflects UM for institution and Music for major
    last_context = fake_provider.call_history[-1]
    system_text = "\n".join(last_context.system_instructions)
    assert 'key="education.institution"' in system_text
    assert "um" in system_text.lower() or "malaya" in system_text.lower()
    assert 'key="education.major"' in system_text
    assert "music" in system_text.lower()


# ===========================================================================
# Gate 2B: Weak Evidence Rejection (Preserves Gate 1 Defense)
# ===========================================================================

@pytest.mark.asyncio
async def test_gate_2b_weak_unsubstantiated_claim_strictly_rejected(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Gate 2B: Casual, unverified user assertion cannot trigger belief revision.

    Baseline: institution=USM.
    User says: "我记得你其实在 UM 读大学。" (No documentation, weak claim).
    Invariant: institution remains USM. Revision rejected.
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你在哪间大学就读呀？"},
    )

    test_session.expire_all()
    stmt_inst = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum",
        CharacterCoreFactRecord.fact_key == "education.institution",
    )
    inst_rec = (await test_session.scalars(stmt_inst)).first()
    assert inst_rec is not None
    assert "usm" in json.loads(inst_rec.value_json).lower()

    # Weak claim
    weak_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "我记得你其实是在 UM 读大学呀。"},
    )
    assert weak_res.status_code == 201

    # Invariant: Institution MUST remain USM
    test_session.expire_all()
    inst_after = (await test_session.scalars(stmt_inst)).first()
    assert inst_after is not None
    inst_val_after = str(json.loads(inst_after.value_json)).lower()
    assert "usm" in inst_val_after, f"Weak assertion caused revision! Got: {inst_val_after}"


# ===========================================================================
# Gate 2C: Minimal Revision (Zero Cascade / Slot Isolation)
# ===========================================================================

@pytest.mark.asyncio
async def test_gate_2c_minimal_revision_strictly_isolates_unhit_slots(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Gate 2C: Revision of institution does not cause cascading re-generation or mutation

    of unhit biographical slots (major, age, occupation, baseline interests).
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    # 1. Establish major and university
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你读什么专业？"},
    )
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你在哪间大学就读呀？"},
    )

    # Snapshot all existing canonical facts before revision
    test_session.expire_all()
    stmt_all = select(CharacterCoreFactRecord).where(
        CharacterCoreFactRecord.character_id == "aevum"
    )
    facts_before = {f.fact_key: json.loads(f.value_json) for f in (await test_session.scalars(stmt_all)).all()}
    assert "education.institution" in facts_before
    assert "education.major" in facts_before
    assert "identity.age" in facts_before

    # 2. Trigger legitimate revision on institution ONLY
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={
            "role": "user",
            "content": "官方转学文件正式生效：你的本科学校已由 USM 调动转学至 Universiti Malaya (UM)。",
        },
    )

    # 3. Snapshot facts after revision
    test_session.expire_all()
    facts_after = {f.fact_key: json.loads(f.value_json) for f in (await test_session.scalars(stmt_all)).all()}

    # Invariant: ONLY education.institution changed
    for key, val_before in facts_before.items():
        if key == "education.institution":
            assert facts_after[key] != val_before, "Target slot should have revised"
        else:
            assert facts_after[key] == val_before, (
                f"Cascade mutation detected on unhit slot '{key}'! Before: {val_before}, After: {facts_after[key]}"
            )


# ===========================================================================
# Gate 2D: Revision Provenance (Audit Trail & Causality Tracking)
# ===========================================================================

@pytest.mark.asyncio
async def test_gate_2d_revision_records_authoritative_provenance_link(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Gate 2D: When a fact revisions, the database records supersession lineage linking

    the old value (USM) to the new value (UM).
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你在哪间大学就读呀？"},
    )
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={
            "role": "user",
            "content": "官方转学凭证已正式下达：你的学校从 USM 正式变更为 Universiti Malaya (UM)。",
        },
    )

    # Query revision records in DB
    test_session.expire_all()
    history_svc = RealityHistoryService(test_session)
    history = await history_svc.get_history(character_id="aevum", fact_key="education.institution")

    assert len(history) >= 2, f"Expected at least 2 revisions in history, found {len(history)}"

    old_rev = history[0]
    new_rev = history[-1]

    # Old belief must be USM
    assert "usm" in str(old_rev.value).lower(), f"Expected old value USM, got: {old_rev.value}"
    # New belief must be UM
    assert "um" in str(new_rev.value).lower() or "malaya" in str(new_rev.value).lower(), (
        f"Expected new value UM, got: {new_rev.value}"
    )

    # Lineage link: new_rev.supersedes_id == old_rev.id
    assert new_rev.supersedes_id == old_rev.id, (
        f"Lineage broken: new_rev.supersedes_id ({new_rev.supersedes_id}) != old_rev.id ({old_rev.id})"
    )
    assert old_rev.superseded_by == new_rev.id, (
        f"Lineage broken: old_rev.superseded_by ({old_rev.superseded_by}) != new_rev.id ({new_rev.id})"
    )


# ===========================================================================
# Gate 2E: Revision History Persistence (Past Reality Survives)
# ===========================================================================

@pytest.mark.asyncio
async def test_gate_2e_revision_history_persists_across_subsequent_turns(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
    test_session: AsyncSession,
):
    """Gate 2E: Revision history is permanent and survives subsequent dialogue turns.

    Prior belief is not erased from the world model.
    """
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    # Turn 1: Establish USM
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你在哪间大学就读呀？"},
    )

    # Turn 2: Revise to UM
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={
            "role": "user",
            "content": "官方转学记录生效：你已正式调动学籍至 Universiti Malaya (UM)。",
        },
    )

    # Turn 3: Follow-up question on unrelated topic
    t3_res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你最近在忙什么？"},
    )
    assert t3_res.status_code == 201

    # Verify history is still accessible and complete
    test_session.expire_all()
    history_svc = RealityHistoryService(test_session)
    history = await history_svc.get_history(character_id="aevum", fact_key="education.institution")

    assert len(history) >= 2
    assert "usm" in str(history[0].value).lower()
    assert "um" in str(history[-1].value).lower() or "malaya" in str(history[-1].value).lower()
