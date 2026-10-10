"""Repository managing persistence for unconfirmed candidate facts and evidence families (Phase 7D.1).

Enforces strict separation: candidate facts are stored in `character_candidate_facts` and
are NEVER directly accessible by CharacterCoreService as canonical truth.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CharacterBiographyPromotionRecord,
    CharacterCandidateFactRecord,
    CharacterChoiceRecord,
    EvidenceFamilyRecord,
)
from app.reality.biography_promotion_models import BiographyPromotionRecord
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateHypothesisSet,
    CandidateLifecycleState,
    EvidenceFamily,
    InferenceEdgeType,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.choice_models import (
    ChoiceDecisionResult,
    ChoiceRationaleCode,
    CompetitionState,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CandidateRepository:
    """Async database repository for multi-session candidate hypotheses and evidence families."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # =========================================================================
    # Evidence Family Persistence (Invariant: different sessions != independent evidence)
    # =========================================================================

    async def get_evidence_family_by_key(self, cluster_key: str) -> Optional[EvidenceFamily]:
        """Lookup an existing evidence family by normalized cluster key."""
        stmt = select(EvidenceFamilyRecord).where(EvidenceFamilyRecord.cluster_key == cluster_key)
        res = await self._session.execute(stmt)
        record = res.scalar_one_or_none()
        if record is None:
            return None
        return self._record_to_evidence_family(record)

    async def get_evidence_family(self, family_id: str) -> Optional[EvidenceFamily]:
        """Lookup an existing evidence family by ID."""
        stmt = select(EvidenceFamilyRecord).where(EvidenceFamilyRecord.id == family_id)
        res = await self._session.execute(stmt)
        record = res.scalar_one_or_none()
        if record is None:
            return None
        return self._record_to_evidence_family(record)

    async def record_evidence(
        self,
        source_type: str,
        cluster_key: str,
        session_id: Optional[str] = None,
    ) -> EvidenceFamily:
        """Register an observation into an EvidenceFamily.

        If an evidence family with the same cluster_key already exists, increments
        mention_count and records session_id, but preserves family_id (independent_evidence_weight = 1).
        """
        stmt = select(EvidenceFamilyRecord).where(EvidenceFamilyRecord.cluster_key == cluster_key)
        res = await self._session.execute(stmt)
        record = res.scalar_one_or_none()

        now = _utc_now()
        if record is not None:
            # Existing family: update mention count and append session if new
            record.mention_count += 1
            record.last_observed_at = now
            sessions: list[str] = json.loads(record.session_ids_json or "[]")
            if session_id and session_id not in sessions:
                sessions.append(session_id)
                record.session_ids_json = json.dumps(sessions)
            await self._session.flush()
            return self._record_to_evidence_family(record)

        # New family
        family_id = f"ef_{uuid.uuid4().hex[:12]}"
        sessions = [session_id] if session_id else []
        new_record = EvidenceFamilyRecord(
            id=family_id,
            source_type=source_type,
            cluster_key=cluster_key,
            mention_count=1,
            session_ids_json=json.dumps(sessions),
            first_observed_at=now,
            last_observed_at=now,
        )
        self._session.add(new_record)
        await self._session.flush()
        return self._record_to_evidence_family(new_record)

    # =========================================================================
    # Candidate Hypothesis Persistence
    # =========================================================================

    async def save_candidate(self, candidate: CandidateHypothesis) -> CandidateHypothesis:
        """Persist a candidate hypothesis in character_candidate_facts.

        Transitions GENERATED candidate to PERSISTED if not already in a more specific state.
        """
        stmt = select(CharacterCandidateFactRecord).where(
            CharacterCandidateFactRecord.id == candidate.candidate_id
        )
        res = await self._session.execute(stmt)
        record = res.scalar_one_or_none()

        now = _utc_now()
        target_lifecycle = candidate.lifecycle_state
        if target_lifecycle == CandidateLifecycleState.GENERATED:
            target_lifecycle = CandidateLifecycleState.PERSISTED

        val_json = json.dumps(candidate.proposed_value, default=str)
        plaus_json = json.dumps(candidate.plausibility.model_dump(), default=str)
        prov_json = json.dumps(candidate.provenance.model_dump(), default=str)
        fam_ids = [fam.family_id for fam in candidate.evidence_families] or list(candidate.provenance.evidence_family_ids)
        fam_ids_json = json.dumps(fam_ids)
        meta_json = json.dumps(candidate.selection_metadata) if candidate.selection_metadata else None

        if record is not None:
            # Update
            record.slot_name = candidate.slot_name
            record.value_json = val_json
            record.reality_taxonomy = candidate.reality_taxonomy.value
            record.inference_depth = candidate.inference_depth
            record.inference_edge_type = candidate.inference_edge_type.value
            record.lifecycle_state = target_lifecycle.value
            record.is_quarantined = candidate.is_quarantined
            record.quarantine_reason = candidate.quarantine_reason
            record.composite_plausibility = candidate.plausibility.composite_plausibility_score
            record.plausibility_json = plaus_json
            record.provenance_json = prov_json
            record.evidence_family_ids_json = fam_ids_json
            record.supersedes_id = candidate.supersedes_id
            record.superseded_by_id = candidate.superseded_by_id
            record.updated_at = now
            record.stale_at = candidate.stale_at
            record.selection_metadata_json = meta_json
        else:
            # Insert
            record = CharacterCandidateFactRecord(
                id=candidate.candidate_id,
                character_id=candidate.entity_id,
                slot_name=candidate.slot_name,
                value_json=val_json,
                reality_taxonomy=candidate.reality_taxonomy.value,
                inference_depth=candidate.inference_depth,
                inference_edge_type=candidate.inference_edge_type.value,
                lifecycle_state=target_lifecycle.value,
                is_quarantined=candidate.is_quarantined,
                quarantine_reason=candidate.quarantine_reason,
                composite_plausibility=candidate.plausibility.composite_plausibility_score,
                plausibility_json=plaus_json,
                provenance_json=prov_json,
                evidence_family_ids_json=fam_ids_json,
                supersedes_id=candidate.supersedes_id,
                superseded_by_id=candidate.superseded_by_id,
                created_at=candidate.created_at or now,
                updated_at=now,
                stale_at=candidate.stale_at,
                selection_metadata_json=meta_json,
            )
            self._session.add(record)

        await self._session.flush()
        return candidate.model_copy(
            update={
                "lifecycle_state": target_lifecycle,
                "updated_at": now,
            }
        )

    async def get_candidate(self, candidate_id: str) -> Optional[CandidateHypothesis]:
        """Fetch candidate hypothesis by deterministic ID."""
        stmt = select(CharacterCandidateFactRecord).where(
            CharacterCandidateFactRecord.id == candidate_id
        )
        res = await self._session.execute(stmt)
        record = res.scalar_one_or_none()
        if record is None:
            return None
        return await self._record_to_candidate(record)

    async def get_candidates_for_slot(
        self,
        character_id: str,
        slot_name: str,
    ) -> list[CandidateHypothesis]:
        """Fetch all candidates (active, pruned, superseded, etc.) for an attribute slot."""
        stmt = (
            select(CharacterCandidateFactRecord)
            .where(
                CharacterCandidateFactRecord.character_id == character_id,
                CharacterCandidateFactRecord.slot_name == slot_name,
            )
            .order_by(CharacterCandidateFactRecord.created_at.asc())
        )
        res = await self._session.execute(stmt)
        records = res.scalars().all()
        candidates: list[CandidateHypothesis] = []
        for r in records:
            candidates.append(await self._record_to_candidate(r))
        return candidates

    async def get_hypothesis_set(
        self,
        character_id: str,
        slot_name: str,
    ) -> CandidateHypothesisSet:
        """Construct CandidateHypothesisSet containing all persisted candidates for a slot."""
        candidates = await self.get_candidates_for_slot(character_id, slot_name)
        cand_map = {c.candidate_id: c for c in candidates}
        return CandidateHypothesisSet(
            slot_name=slot_name,
            entity_id=character_id,
            candidates=cand_map,
        )

    async def update_candidate_lifecycle(
        self,
        candidate_id: str,
        state: CandidateLifecycleState,
        quarantine_reason: Optional[str] = None,
    ) -> Optional[CandidateHypothesis]:
        """Transition candidate lifecycle state in database."""
        stmt = select(CharacterCandidateFactRecord).where(
            CharacterCandidateFactRecord.id == candidate_id
        )
        res = await self._session.execute(stmt)
        record = res.scalar_one_or_none()
        if record is None:
            return None

        record.lifecycle_state = state.value
        record.updated_at = _utc_now()
        if quarantine_reason is not None:
            record.is_quarantined = True
            record.quarantine_reason = quarantine_reason

        await self._session.flush()
        return await self._record_to_candidate(record)

    async def get_all_active_candidates(
        self,
        character_id: str,
        active_states: Optional[list[CandidateLifecycleState]] = None,
    ) -> list[CandidateHypothesis]:
        """Fetch all non-terminal candidates for a character across all slots.

        Args:
            character_id: The character whose candidates to fetch.
            active_states: Which lifecycle states to include. Defaults to
                GENERATED, PERSISTED, ACTIVE, PROMOTABLE.

        Returns:
            List of CandidateHypothesis objects ordered by creation time (ascending).

        Raises:
            Any SQLAlchemy or database exception — propagated directly to caller.

        FAILURE CONTRACT:
            This method NEVER converts a DB exception into an empty list [].
            A successful query returning [] means "no candidates exist".
            A raised exception means "candidate state could not be determined".
            The caller (RealityOrchestrationService) is responsible for wrapping
            this in CandidateRepositoryUnavailableError to preserve that distinction.
        """
        if active_states is None:
            active_states = [
                CandidateLifecycleState.GENERATED,
                CandidateLifecycleState.PERSISTED,
                CandidateLifecycleState.ACTIVE,
                CandidateLifecycleState.PROMOTABLE,
            ]
        state_values = [s.value for s in active_states]
        stmt = (
            select(CharacterCandidateFactRecord)
            .where(
                CharacterCandidateFactRecord.character_id == character_id,
                CharacterCandidateFactRecord.lifecycle_state.in_(state_values),
            )
            .order_by(CharacterCandidateFactRecord.created_at.asc())
        )
        res = await self._session.execute(stmt)
        records = res.scalars().all()
        candidates: list[CandidateHypothesis] = []
        for r in records:
            candidates.append(await self._record_to_candidate(r))
        return candidates

    # =========================================================================
    # Helpers
    # =========================================================================


    def _record_to_evidence_family(self, record: EvidenceFamilyRecord) -> EvidenceFamily:
        sessions: list[str] = json.loads(record.session_ids_json or "[]")
        return EvidenceFamily(
            family_id=record.id,
            source_type=record.source_type,
            cluster_key=record.cluster_key,
            mention_count=record.mention_count,
            session_ids=tuple(sessions),
            first_observed_at=record.first_observed_at,
            last_observed_at=record.last_observed_at,
        )

    async def _record_to_candidate(self, record: CharacterCandidateFactRecord) -> CandidateHypothesis:
        val = json.loads(record.value_json)
        plaus_dict = json.loads(record.plausibility_json)
        prov_dict = json.loads(record.provenance_json)
        fam_ids: list[str] = json.loads(record.evidence_family_ids_json or "[]")

        # Load linked evidence families
        fams: list[EvidenceFamily] = []
        for fid in fam_ids:
            fam = await self.get_evidence_family(fid)
            if fam is not None:
                fams.append(fam)

        plausibility = PlausibilityBreakdown(**plaus_dict)
        provenance = ProvenanceLineage(**prov_dict)
        meta_dict = json.loads(record.selection_metadata_json) if getattr(record, "selection_metadata_json", None) else None

        return CandidateHypothesis(
            candidate_id=record.id,
            entity_id=record.character_id,
            slot_name=record.slot_name,
            proposed_value=val,
            reality_taxonomy=RealityTaxonomy(record.reality_taxonomy),
            inference_depth=record.inference_depth,
            inference_edge_type=InferenceEdgeType(record.inference_edge_type),
            plausibility=plausibility,
            provenance=provenance,
            evidence_families=tuple(fams),
            lifecycle_state=CandidateLifecycleState(record.lifecycle_state),
            is_quarantined=record.is_quarantined,
            quarantine_reason=record.quarantine_reason,
            supersedes_id=record.supersedes_id,
            superseded_by_id=record.superseded_by_id,
            created_at=record.created_at.replace(tzinfo=timezone.utc) if record.created_at and record.created_at.tzinfo is None else record.created_at,
            updated_at=record.updated_at.replace(tzinfo=timezone.utc) if record.updated_at and record.updated_at.tzinfo is None else record.updated_at,
            stale_at=record.stale_at.replace(tzinfo=timezone.utc) if record.stale_at and record.stale_at.tzinfo is None else record.stale_at,
            selection_metadata=meta_dict,
        )

    # =========================================================================
    # Choice Decision Provenance Persistence (Phase 7D.2)
    # =========================================================================

    async def save_choice_decision(
        self,
        decision: ChoiceDecisionResult,
    ) -> CharacterChoiceRecord:
        """Persist a ChoiceDecisionResult and update candidate lifecycle states.
        
        Strict Invariants:
        - Choice records are stored in character_choice_records (never canonical core facts).
        - Selected candidate and archived unselected candidates are updated in character_candidate_facts.
        """
        # 1. Update selected candidate if present
        if decision.selected_candidate is not None:
            await self.save_candidate(decision.selected_candidate)

        # 2. Update archived unselected candidates
        for archived in decision.archived_unselected_candidates:
            await self.save_candidate(archived)

        # 3. Create persistent ChoiceRecord
        now = _utc_now()
        record = CharacterChoiceRecord(
            id=decision.decision_id,
            character_id=decision.entity_id,
            slot_name=decision.slot_name,
            candidate_set_id=decision.candidate_set_id,
            selected_candidate_id=decision.selected_candidate_id,
            unselected_candidate_ids_json=json.dumps(list(decision.unselected_candidate_ids)),
            decision_model_version=decision.decision_model_version,
            competition_state=decision.competition_state.value,
            competition_margin=decision.competition_margin,
            choice_margin=decision.choice_margin,
            rationale_code=decision.rationale_code.value,
            rationale_description=decision.rationale_description,
            candidate_ids_json=json.dumps(list(decision.candidate_ids_considered)),
            plausibility_scores_json=json.dumps(decision.plausibility_scores),
            factor_inputs_json=json.dumps(decision.factor_inputs),
            factor_contributions_json=json.dumps(decision.factor_contributions),
            choice_scores_json=json.dumps(decision.choice_scores),
            provenance_references_json=json.dumps(list(decision.provenance_references)),
            created_at=decision.decision_timestamp or now,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_choice_decisions(
        self,
        slot_name: Optional[str] = None,
        character_id: str = "aevum",
    ) -> list[ChoiceDecisionResult]:
        """Query choice decisions by slot or character."""
        stmt = select(CharacterChoiceRecord).where(
            CharacterChoiceRecord.character_id == character_id
        )
        if slot_name:
            stmt = stmt.where(CharacterChoiceRecord.slot_name == slot_name)
        stmt = stmt.order_by(CharacterChoiceRecord.created_at.desc())

        res = await self._session.execute(stmt)
        records = res.scalars().all()
        results: list[ChoiceDecisionResult] = []
        for rec in records:
            res_obj = await self._record_to_choice_decision(rec)
            results.append(res_obj)
        return results

    async def get_choice_decision(self, decision_id: str) -> Optional[ChoiceDecisionResult]:
        """Fetch single choice decision by ID."""
        stmt = select(CharacterChoiceRecord).where(CharacterChoiceRecord.id == decision_id)
        res = await self._session.execute(stmt)
        rec = res.scalar_one_or_none()
        if rec is None:
            return None
        return await self._record_to_choice_decision(rec)

    async def _record_to_choice_decision(self, record: CharacterChoiceRecord) -> ChoiceDecisionResult:
        cand_ids = tuple(json.loads(record.candidate_ids_json or "[]"))
        unsel_ids = tuple(json.loads(record.unselected_candidate_ids_json or "[]"))
        plaus_scores = json.loads(record.plausibility_scores_json or "{}")
        factor_inputs = json.loads(record.factor_inputs_json or "{}")
        factor_contribs = json.loads(record.factor_contributions_json or "{}")
        choice_scores = json.loads(record.choice_scores_json or "{}")
        prov_refs = tuple(json.loads(record.provenance_references_json or "[]"))

        selected_cand: Optional[CandidateHypothesis] = None
        if record.selected_candidate_id:
            selected_cand = await self.get_candidate(record.selected_candidate_id)

        archived_list: list[CandidateHypothesis] = []
        for uid in unsel_ids:
            c = await self.get_candidate(uid)
            if c:
                archived_list.append(c)

        return ChoiceDecisionResult(
            decision_id=record.id,
            entity_id=record.character_id,
            slot_name=record.slot_name,
            candidate_set_id=record.candidate_set_id,
            candidate_ids_considered=cand_ids,
            selected_candidate_id=record.selected_candidate_id,
            unselected_candidate_ids=unsel_ids,
            selected_candidate=selected_cand,
            archived_unselected_candidates=tuple(archived_list),
            decision_timestamp=record.created_at,
            decision_model_version=record.decision_model_version,
            competition_state=CompetitionState(record.competition_state),
            competition_margin=record.competition_margin,
            plausibility_scores=plaus_scores,
            factor_inputs=factor_inputs,
            factor_contributions=factor_contribs,
            choice_scores=choice_scores,
            choice_margin=record.choice_margin,
            rationale_code=ChoiceRationaleCode(record.rationale_code),
            rationale_description=record.rationale_description,
            is_non_canonical=True,
            provenance_references=prov_refs,
        )

    # =========================================================================
    # Biography Promotion Persistence (Phase 7D.3)
    # =========================================================================

    async def save_biography_promotion(
        self,
        record: BiographyPromotionRecord,
    ) -> CharacterBiographyPromotionRecord:
        """Persist a BiographyPromotionRecord as authoritative proof of canonical promotion."""
        stmt = select(CharacterBiographyPromotionRecord).where(
            CharacterBiographyPromotionRecord.id == record.promotion_id
        )
        res = await self._session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing is not None:
            return existing

        now = _utc_now()
        db_record = CharacterBiographyPromotionRecord(
            id=record.promotion_id,
            character_id=record.character_id,
            slot_name=record.slot_name,
            candidate_id=record.candidate_id,
            choice_decision_id=record.choice_decision_id,
            promoted_value_json=json.dumps(record.promoted_value, default=str),
            policy_version=record.policy_version,
            decision_model_version=record.decision_model_version,
            previous_canonical_state_json=json.dumps(record.previous_canonical_state, default=str) if record.previous_canonical_state is not None else None,
            new_canonical_state_json=json.dumps(record.new_canonical_state, default=str),
            gates_passed_json=json.dumps(list(record.gates_passed)),
            provenance_references_json=json.dumps(list(record.provenance_references)),
            authorization_code=record.authorization_code,
            created_at=record.created_at or now,
        )
        self._session.add(db_record)
        await self._session.flush()
        return db_record

    async def get_biography_promotion_by_candidate(
        self,
        candidate_id: str,
        character_id: str = "aevum",
    ) -> Optional[BiographyPromotionRecord]:
        """Lookup biography promotion record for a candidate ID."""
        stmt = select(CharacterBiographyPromotionRecord).where(
            CharacterBiographyPromotionRecord.character_id == character_id,
            CharacterBiographyPromotionRecord.candidate_id == candidate_id,
        )
        res = await self._session.execute(stmt)
        rec = res.scalar_one_or_none()
        if rec is None:
            return None
        return self._record_to_biography_promotion(rec)

    async def get_biography_promotions(
        self,
        character_id: str = "aevum",
        slot_name: Optional[str] = None,
    ) -> list[BiographyPromotionRecord]:
        """Fetch all biography promotion records for a character, optionally filtered by slot."""
        stmt = select(CharacterBiographyPromotionRecord).where(
            CharacterBiographyPromotionRecord.character_id == character_id
        )
        if slot_name:
            stmt = stmt.where(CharacterBiographyPromotionRecord.slot_name == slot_name)
        stmt = stmt.order_by(CharacterBiographyPromotionRecord.created_at.asc())

        res = await self._session.execute(stmt)
        records = res.scalars().all()
        return [self._record_to_biography_promotion(r) for r in records]

    def _record_to_biography_promotion(
        self,
        record: CharacterBiographyPromotionRecord,
    ) -> BiographyPromotionRecord:
        val = json.loads(record.promoted_value_json)
        prev_val = json.loads(record.previous_canonical_state_json) if record.previous_canonical_state_json else None
        new_val = json.loads(record.new_canonical_state_json)
        gates = tuple(json.loads(record.gates_passed_json or "[]"))
        prov = tuple(json.loads(record.provenance_references_json or "[]"))

        return BiographyPromotionRecord(
            promotion_id=record.id,
            character_id=record.character_id,
            slot_name=record.slot_name,
            candidate_id=record.candidate_id,
            choice_decision_id=record.choice_decision_id,
            promoted_value=val,
            policy_version=record.policy_version,
            decision_model_version=record.decision_model_version,
            previous_canonical_state=prev_val,
            new_canonical_state=new_val,
            gates_passed=gates,
            provenance_references=prov,
            authorization_code=record.authorization_code,
            is_idempotent_replay=False,
            created_at=record.created_at,
        )
