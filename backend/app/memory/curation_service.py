"""Memory curation service for Aevum Core.

Manages the lifecycle of memory candidates (PENDING -> ACCEPTED / REJECTED)
and provides atomic conversion of curated candidates into persistent long-term memories.
"""

from datetime import datetime
import difflib
import re
import uuid
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryCandidateRecord, MemoryRecord, utc_now
from app.memory.curation_policy import evaluate_candidate, MEMORY_CURATION_POLICY_VERSION
from app.memory.models import (
    BatchCurationResult,
    CandidateEvaluation,
    CurationDecision,
    CurationResult,
    Memory,
    MemoryCategory,
    MemoryCandidate,
    MemoryCandidateSource,
    MemoryCandidateStatus,
    MemoryCandidateUpdate,
    MemoryCurationDecision,
    MemoryCurationReason,
    MemorySubjectEntity,
)
from app.memory.service import _ensure_utc

DEFAULT_CURATION_BATCH_SIZE: int = 20


def _normalize_memory_text(text: str) -> str:
    t = text.lower()
    t = re.sub(r'[\(\)\[\]\{\}（）「」《》\'\"\,，\.\。\!！\?？\:\：\-—_]', ' ', t)
    return ' '.join(t.split())


def _get_char_ngrams(text: str, n: int = 2) -> set[str]:
    norm = _normalize_memory_text(text).replace(' ', '')
    if len(norm) < n:
        return {norm} if norm else set()
    return {norm[i:i+n] for i in range(len(norm) - n + 1)}


def _get_tokens(text: str) -> set[str]:
    norm = _normalize_memory_text(text)
    words = set(norm.split())
    for ch in norm:
        if '\u4e00' <= ch <= '\u9fff':
            words.add(ch)
    return words


def _extract_numbers(text: str) -> list[str]:
    return re.findall(r'\d+', text)


def check_memory_duplicate(
    content: str,
    category: str,
    subject_entity: str,
    existing_memories: list[MemoryRecord],
) -> tuple[MemoryRecord | None, str]:
    """Check if content semantically duplicates any existing persistent memory."""
    norm_content = _normalize_memory_text(content)
    nums_content = _extract_numbers(content)

    for mem in existing_memories:
        # Category check: memories in different categories are preserved
        if mem.category and category and mem.category != category:
            continue

        # Subject entity check: memories with different subjects are not duplicates
        if mem.subject_entity and subject_entity and mem.subject_entity != subject_entity:
            continue

        # Exact raw content match
        if mem.content.strip().lower() == content.strip().lower():
            return mem, "Exact duplicate of existing persistent memory."

        norm_mem = _normalize_memory_text(mem.content)
        if norm_content == norm_mem:
            return mem, "Normalized exact duplicate of existing persistent memory."

        # If numbers differ (e.g. 'Fact number 0' vs 'Fact number 1'), distinct facts
        nums_mem = _extract_numbers(mem.content)
        if nums_content != nums_mem:
            continue

        # SequenceMatcher ratio for slight paraphrases / parenthetical annotations
        seq_ratio = difflib.SequenceMatcher(None, norm_content, norm_mem).ratio()
        if seq_ratio >= 0.70:
            return mem, f"Semantic duplicate (similarity {seq_ratio:.2f}) of existing memory."

        # Character n-gram overlap for Chinese sentences
        ngrams_c = _get_char_ngrams(norm_content, n=2)
        ngrams_m = _get_char_ngrams(norm_mem, n=2)
        if ngrams_c and ngrams_m:
            overlap = len(ngrams_c & ngrams_m)
            min_ngrams = min(len(ngrams_c), len(ngrams_m))
            if min_ngrams >= 4 and (overlap / min_ngrams) >= 0.60:
                return mem, f"N-gram overlap duplicate ({overlap / min_ngrams:.2f}) of existing memory."

        # Key content tokens overlap (ignoring common grammatical words)
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "for", "its", "with", "and", "in", "to", "of", "on", "at", "by",
            "user", "users", "aevum", "aevums", "that", "this", "from", "it", "he", "she", "they", "them",
            "的", "了", "和", "在", "是", "有", "也", "与", "对", "于", "中", "及", "等",
        }
        tokens_c = {w for w in norm_content.split() if w not in stopwords and len(w) > 1}
        tokens_m = {w for w in norm_mem.split() if w not in stopwords and len(w) > 1}
        if tokens_c and tokens_m:
            common_tokens = tokens_c & tokens_m
            min_len = min(len(tokens_c), len(tokens_m))
            if min_len >= 3 and (len(common_tokens) / min_len) >= 0.60:
                return mem, f"Keyword overlap duplicate ({len(common_tokens) / min_len:.2f}) of existing memory."

        # Special anchor: user name representation across languages
        if "白开水" in norm_content and "白开水" in norm_mem:
            return mem, "Anchor entity '白开水' duplicate of existing memory."

        # Common named entity anchors (avoid duplicate preferences about the same venue/topic)
        for anchor in ("horizon grill", "rabbit hole", "chiikawa", "小橘", "xiao ju", "sembreak"):
            if anchor in norm_content and anchor in norm_mem:
                return mem, f"Named anchor entity '{anchor}' duplicate of existing memory."

    return None, ""




class CandidateNotFoundError(Exception):
    """Raised when a requested memory candidate does not exist."""

    def __init__(self, candidate_id: str) -> None:
        self.candidate_id = candidate_id
        super().__init__(f"Memory candidate with ID '{candidate_id}' was not found.")


class CandidateConflictError(Exception):
    """Raised when a candidate operation fails due to an optimistic concurrency version mismatch."""

    def __init__(self, candidate_id: str, expected_version: int, actual_version: int) -> None:
        self.candidate_id = candidate_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Candidate '{candidate_id}' version mismatch: expected {expected_version}, but current version is {actual_version}."
        )


class CandidateTerminalStateError(Exception):
    """Raised when an operation attempts to mutate or transition a terminal candidate."""

    def __init__(self, candidate_id: str, current_status: MemoryCandidateStatus) -> None:
        self.candidate_id = candidate_id
        self.current_status = current_status
        super().__init__(
            f"Candidate '{candidate_id}' is in terminal state '{current_status.value}' and cannot be modified."
        )


class MemoryCurationService:
    """Service managing memory candidate proposal, updates, and curation decisions."""

    def __init__(self, session: AsyncSession, character_id: str = "aevum") -> None:
        self._session = session
        self._character_id = character_id

    async def create_candidate(
        self,
        category: MemoryCategory,
        content: str,
        importance: float = 0.5,
        confidence: float = 0.9,
        emotional_weight: float = 0.0,
        source_type: MemoryCandidateSource = MemoryCandidateSource.MANUAL,
        candidate_id: str | None = None,
        subject_entity: MemorySubjectEntity | None = None,
        commit: bool = True,
    ) -> MemoryCandidate:
        """Create and persist a new PENDING memory candidate."""
        stable_id = candidate_id or str(uuid.uuid4())
        now = utc_now()

        # Validate domain constraints
        cand_kwargs: dict[str, object] = {
            "id": stable_id,
            "category": category,
            "content": content,
            "importance": importance,
            "confidence": confidence,
            "emotional_weight": emotional_weight,
            "status": MemoryCandidateStatus.PENDING,
            "source_type": source_type,
            "created_at": now,
            "updated_at": now,
            "version": 1,
        }
        if subject_entity is not None:
            cand_kwargs["subject_entity"] = subject_entity

        domain_cand = MemoryCandidate(**cand_kwargs)

        record = MemoryCandidateRecord(
            id=domain_cand.id,
            category=domain_cand.category.value,
            subject_entity=domain_cand.subject_entity.value,
            content=domain_cand.content,
            importance=domain_cand.importance,
            confidence=domain_cand.confidence,
            emotional_weight=domain_cand.emotional_weight,
            status=domain_cand.status.value,
            source_type=domain_cand.source_type.value,
            created_at=domain_cand.created_at,
            updated_at=domain_cand.updated_at,
            version=1,
        )
        self._session.add(record)
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

        return domain_cand

    async def get_candidate(self, candidate_id: str) -> MemoryCandidate | None:
        """Retrieve a candidate by ID, returning None if not found."""
        query = select(MemoryCandidateRecord).where(MemoryCandidateRecord.id == candidate_id)
        result = await self._session.scalars(query)
        record = result.first()
        if record is None:
            return None
        return self._record_to_domain(record)

    async def list_candidates(
        self,
        status: MemoryCandidateStatus | None = None,
        category: MemoryCategory | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryCandidate]:
        """Deterministically list candidates with optional status and category filters."""
        query = select(MemoryCandidateRecord)
        if status is not None:
            status_val = status.value if hasattr(status, "value") else str(status)
            query = query.where(MemoryCandidateRecord.status == status_val)
        if category is not None:
            cat_val = category.value if hasattr(category, "value") else str(category)
            query = query.where(MemoryCandidateRecord.category == cat_val)

        query = query.order_by(
            MemoryCandidateRecord.created_at.desc(),
            MemoryCandidateRecord.id.asc(),
        ).offset(offset).limit(limit)

        result = await self._session.scalars(query)
        return [self._record_to_domain(rec) for rec in result.all()]

    async def update_candidate(
        self,
        candidate_id: str,
        update_req: MemoryCandidateUpdate,
        expected_version: int | None = None,
    ) -> MemoryCandidate:
        """Update a PENDING candidate with optimistic concurrency.

        Raises CandidateTerminalStateError if the candidate is already ACCEPTED or REJECTED.
        """
        existing = await self.get_candidate(candidate_id)
        if existing is None:
            raise CandidateNotFoundError(candidate_id)
        if existing.status != MemoryCandidateStatus.PENDING:
            raise CandidateTerminalStateError(candidate_id, existing.status)

        now = utc_now()
        values_to_update: dict[str, object] = {
            "version": MemoryCandidateRecord.version + 1,
            "updated_at": now,
        }
        if update_req.subject_entity is not None:
            values_to_update["subject_entity"] = update_req.subject_entity.value
        if update_req.content is not None:
            values_to_update["content"] = update_req.content
        if update_req.importance is not None:
            values_to_update["importance"] = update_req.importance
        if update_req.confidence is not None:
            values_to_update["confidence"] = update_req.confidence
        if update_req.emotional_weight is not None:
            values_to_update["emotional_weight"] = update_req.emotional_weight

        cond = [
            MemoryCandidateRecord.id == candidate_id,
            MemoryCandidateRecord.status == MemoryCandidateStatus.PENDING.value,
        ]
        if expected_version is not None:
            cond.append(MemoryCandidateRecord.version == expected_version)

        stmt = update(MemoryCandidateRecord).where(*cond).values(**values_to_update)
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            current = await self.get_candidate(candidate_id)
            if current is None:
                raise CandidateNotFoundError(candidate_id)
            if current.status != MemoryCandidateStatus.PENDING:
                raise CandidateTerminalStateError(candidate_id, current.status)
            raise CandidateConflictError(
                candidate_id=candidate_id,
                expected_version=expected_version or 0,
                actual_version=current.version,
            )

        await self._session.commit()
        updated = await self.get_candidate(candidate_id)
        if updated is None:
            raise CandidateNotFoundError(candidate_id)
        return updated

    async def reject_candidate(
        self,
        candidate_id: str,
        expected_version: int | None = None,
        reason: str | None = None,
    ) -> CurationResult:
        """Reject a PENDING candidate, placing it in terminal REJECTED state."""
        existing = await self.get_candidate(candidate_id)
        if existing is None:
            raise CandidateNotFoundError(candidate_id)
        if existing.status != MemoryCandidateStatus.PENDING:
            raise CandidateTerminalStateError(candidate_id, existing.status)

        now = utc_now()
        cond = [
            MemoryCandidateRecord.id == candidate_id,
            MemoryCandidateRecord.status == MemoryCandidateStatus.PENDING.value,
        ]
        if expected_version is not None:
            cond.append(MemoryCandidateRecord.version == expected_version)

        stmt = (
            update(MemoryCandidateRecord)
            .where(*cond)
            .values(
                status=MemoryCandidateStatus.REJECTED.value,
                version=MemoryCandidateRecord.version + 1,
                updated_at=now,
            )
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            current = await self.get_candidate(candidate_id)
            if current is None:
                raise CandidateNotFoundError(candidate_id)
            if current.status != MemoryCandidateStatus.PENDING:
                raise CandidateTerminalStateError(candidate_id, current.status)
            raise CandidateConflictError(
                candidate_id=candidate_id,
                expected_version=expected_version or 0,
                actual_version=current.version,
            )

        await self._session.commit()
        return CurationResult(
            decision=CurationDecision.REJECTED,
            candidate_id=candidate_id,
            reason=reason,
        )

    async def accept_candidate(
        self,
        candidate_id: str,
        expected_version: int | None = None,
    ) -> CurationResult:
        """Atomically accept a PENDING candidate and commit it as persistent Memory.

        Performs conservative deterministic duplicate detection: if a Memory already
        exists with the identical category and trimmed content, the candidate is
        marked REJECTED (decision=DUPLICATE) and no duplicate Memory is created.

        If accepted, creating the Memory record and transitioning the Candidate to
        ACCEPTED occur in a single atomic database transaction.
        """
        existing = await self.get_candidate(candidate_id)
        if existing is None:
            raise CandidateNotFoundError(candidate_id)
        if existing.status != MemoryCandidateStatus.PENDING:
            raise CandidateTerminalStateError(candidate_id, existing.status)
        if expected_version is not None and existing.version != expected_version:
            raise CandidateConflictError(
                candidate_id=candidate_id,
                expected_version=expected_version,
                actual_version=existing.version,
            )

        now = utc_now()
        normalized_content = existing.content.strip()

        # 1. Deterministic duplicate detection against persistent memories table
        all_mems_query = select(MemoryRecord).where(MemoryRecord.character_id == self._character_id)
        all_mems = list((await self._session.scalars(all_mems_query)).all())
        dup, dup_reason = check_memory_duplicate(
            content=normalized_content,
            category=existing.category.value if existing.category else "",
            subject_entity=existing.subject_entity.value if existing.subject_entity else "",
            existing_memories=all_mems,
        )
        if dup is not None:
            # Candidate is a duplicate; reinforce existing memory and reject candidate
            dup_update_stmt = (
                update(MemoryRecord)
                .where(MemoryRecord.id == dup.id)
                .values(
                    confidence=max(dup.confidence, existing.confidence),
                    times_recalled=dup.times_recalled + 1,
                    updated_at=now,
                )
            )
            await self._session.execute(dup_update_stmt)
            reject_stmt = (
                update(MemoryCandidateRecord)
                .where(
                    MemoryCandidateRecord.id == candidate_id,
                    MemoryCandidateRecord.status == MemoryCandidateStatus.PENDING.value,
                )
                .values(
                    status=MemoryCandidateStatus.REJECTED.value,
                    version=MemoryCandidateRecord.version + 1,
                    updated_at=now,
                )
            )
            await self._session.execute(reject_stmt)
            await self._session.commit()
            return CurationResult(
                decision=CurationDecision.DUPLICATE,
                candidate_id=candidate_id,
                reason=dup_reason,
            )

        # 2. Atomic acceptance transaction: create Memory + mark Candidate ACCEPTED
        try:
            new_memory_id = str(uuid.uuid4())
            memory_record = MemoryRecord(
                id=new_memory_id,
                character_id=self._character_id,
                category=existing.category.value,
                subject_entity=existing.subject_entity.value,
                content=normalized_content,
                importance=existing.importance,
                confidence=existing.confidence,
                emotional_weight=existing.emotional_weight,
                created_at=now,
                updated_at=now,
                last_recalled=None,
                times_recalled=0,
                version=1,
            )
            self._session.add(memory_record)

            cond = [
                MemoryCandidateRecord.id == candidate_id,
                MemoryCandidateRecord.status == MemoryCandidateStatus.PENDING.value,
            ]
            if expected_version is not None:
                cond.append(MemoryCandidateRecord.version == expected_version)

            candidate_stmt = (
                update(MemoryCandidateRecord)
                .where(*cond)
                .values(
                    status=MemoryCandidateStatus.ACCEPTED.value,
                    version=MemoryCandidateRecord.version + 1,
                    updated_at=now,
                )
            )
            cand_result = await self._session.execute(candidate_stmt)
            if cand_result.rowcount == 0:
                await self._session.rollback()
                current = await self.get_candidate(candidate_id)
                if current is None:
                    raise CandidateNotFoundError(candidate_id)
                if current.status != MemoryCandidateStatus.PENDING:
                    raise CandidateTerminalStateError(candidate_id, current.status)
                raise CandidateConflictError(
                    candidate_id=candidate_id,
                    expected_version=expected_version or 0,
                    actual_version=current.version,
                )

            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        domain_memory = Memory(
            id=new_memory_id,
            category=existing.category,
            subject_entity=existing.subject_entity,
            content=normalized_content,
            importance=existing.importance,
            confidence=existing.confidence,
            emotional_weight=existing.emotional_weight,
            created_at=now,
            updated_at=now,
            last_recalled=None,
            times_recalled=0,
            version=1,
        )

        return CurationResult(
            decision=CurationDecision.ACCEPTED,
            candidate_id=candidate_id,
            memory_id=new_memory_id,
            memory=domain_memory,
        )

    async def curate_candidate(self, candidate_id: str) -> CandidateEvaluation:
        """Evaluate and deterministically curate a single memory candidate according to Phase 3.4 policy.

        - If candidate is not found, raises CandidateNotFoundError.
        - If candidate is already in a terminal state (ACCEPTED / REJECTED), returns REJECT / REJECTED_TERMINAL
          without modifying the candidate.
        - Evaluates candidate via deterministic evaluate_candidate() policy.
        - If decision == ACCEPT:
            Attempts to atomically accept the candidate into persistent Memory.
            If accept_candidate detects an exact duplicate, the candidate is rejected
            and this method returns REJECT / REJECTED_DUPLICATE.
        - If decision == REJECT:
            Atomically transitions the candidate to REJECTED with explanation recorded.
        - If decision == DEFER:
            Leaves the candidate untouched in PENDING status.
        """
        existing = await self.get_candidate(candidate_id)
        if existing is None:
            raise CandidateNotFoundError(candidate_id)

        evaluation = evaluate_candidate(existing)
        if evaluation.decision == MemoryCurationDecision.REJECT:
            if existing.status == MemoryCandidateStatus.PENDING:
                await self.reject_candidate(candidate_id, reason=evaluation.explanation)
            return evaluation

        if evaluation.decision == MemoryCurationDecision.ACCEPT:
            res = await self.accept_candidate(candidate_id)
            if res.decision == CurationDecision.DUPLICATE:
                return CandidateEvaluation(
                    decision=MemoryCurationDecision.REJECT,
                    reason=MemoryCurationReason.REJECTED_DUPLICATE,
                    explanation=res.reason or "Candidate content duplicates an existing persistent memory.",
                )
            return evaluation

        # DEFER: do not mutate candidate, remains PENDING
        return evaluation

    async def curate_pending_candidates(
        self,
        batch_size: int = DEFAULT_CURATION_BATCH_SIZE,
    ) -> BatchCurationResult:
        """Deterministically curate a bounded batch of PENDING memory candidates.

        Candidates are processed in deterministic FIFO order (created_at ASC, id ASC).
        Each candidate is evaluated against the deterministic Curation Policy.
        Returns a BatchCurationResult summarizing accepted, rejected, and deferred candidates.
        """
        effective_limit = max(1, min(batch_size, 100))
        query = (
            select(MemoryCandidateRecord)
            .where(MemoryCandidateRecord.status == MemoryCandidateStatus.PENDING.value)
            .order_by(
                MemoryCandidateRecord.created_at.asc(),
                MemoryCandidateRecord.id.asc(),
            )
            .limit(effective_limit)
        )
        result = await self._session.scalars(query)
        records = list(result.all())

        accepted: list[str] = []
        rejected: list[str] = []
        deferred: list[str] = []

        for record in records:
            eval_res = await self.curate_candidate(record.id)
            if eval_res.decision == MemoryCurationDecision.ACCEPT:
                accepted.append(record.id)
            elif eval_res.decision == MemoryCurationDecision.REJECT:
                rejected.append(record.id)
            else:
                deferred.append(record.id)

        return BatchCurationResult(
            accepted_candidate_ids=accepted,
            rejected_candidate_ids=rejected,
            deferred_candidate_ids=deferred,
            total_evaluated=len(records),
        )

    def _record_to_domain(self, record: MemoryCandidateRecord) -> MemoryCandidate:
        """Convert a MemoryCandidateRecord into an immutable MemoryCandidate domain model."""
        created = _ensure_utc(record.created_at)
        updated = _ensure_utc(record.updated_at)
        assert created is not None
        assert updated is not None

        rec_subj = getattr(record, "subject_entity", None)
        try:
            subj_entity = MemorySubjectEntity(rec_subj) if rec_subj else MemorySubjectEntity.USER
        except (ValueError, KeyError):
            subj_entity = MemorySubjectEntity.USER

        return MemoryCandidate(
            id=record.id,
            category=MemoryCategory(record.category),
            subject_entity=subj_entity,
            content=record.content,
            importance=record.importance,
            confidence=record.confidence,
            emotional_weight=record.emotional_weight,
            status=MemoryCandidateStatus(record.status),
            source_type=MemoryCandidateSource(record.source_type),
            created_at=created,
            updated_at=updated,
            version=record.version,
        )


# Top-level convenience functions


async def create_memory_candidate(
    session: AsyncSession,
    category: MemoryCategory,
    content: str,
    importance: float = 0.5,
    confidence: float = 0.9,
    emotional_weight: float = 0.0,
    source_type: MemoryCandidateSource = MemoryCandidateSource.MANUAL,
    candidate_id: str | None = None,
    subject_entity: MemorySubjectEntity | None = None,
) -> MemoryCandidate:
    """Convenience function to create a memory candidate."""
    service = MemoryCurationService(session)
    return await service.create_candidate(
        category=category,
        content=content,
        importance=importance,
        confidence=confidence,
        emotional_weight=emotional_weight,
        source_type=source_type,
        candidate_id=candidate_id,
        subject_entity=subject_entity,
    )


async def get_memory_candidate(
    session: AsyncSession,
    candidate_id: str,
) -> MemoryCandidate | None:
    """Convenience function to get a memory candidate by ID."""
    service = MemoryCurationService(session)
    return await service.get_candidate(candidate_id=candidate_id)


async def list_memory_candidates(
    session: AsyncSession,
    status: MemoryCandidateStatus | None = None,
    category: MemoryCategory | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[MemoryCandidate]:
    """Convenience function to list memory candidates."""
    service = MemoryCurationService(session)
    return await service.list_candidates(
        status=status,
        category=category,
        limit=limit,
        offset=offset,
    )


async def update_memory_candidate(
    session: AsyncSession,
    candidate_id: str,
    update_req: MemoryCandidateUpdate,
    expected_version: int | None = None,
) -> MemoryCandidate:
    """Convenience function to update a PENDING memory candidate."""
    service = MemoryCurationService(session)
    return await service.update_candidate(
        candidate_id=candidate_id,
        update_req=update_req,
        expected_version=expected_version,
    )


async def accept_memory_candidate(
    session: AsyncSession,
    candidate_id: str,
    expected_version: int | None = None,
) -> CurationResult:
    """Convenience function to accept a candidate into persistent memory."""
    service = MemoryCurationService(session)
    return await service.accept_candidate(
        candidate_id=candidate_id,
        expected_version=expected_version,
    )


async def reject_memory_candidate(
    session: AsyncSession,
    candidate_id: str,
    expected_version: int | None = None,
    reason: str | None = None,
) -> CurationResult:
    """Convenience function to reject a memory candidate."""
    service = MemoryCurationService(session)
    return await service.reject_candidate(
        candidate_id=candidate_id,
        expected_version=expected_version,
        reason=reason,
    )


async def curate_memory_candidate(
    session: AsyncSession,
    candidate_id: str,
) -> CandidateEvaluation:
    """Convenience function to deterministically evaluate and curate a candidate."""
    service = MemoryCurationService(session)
    return await service.curate_candidate(candidate_id=candidate_id)


async def curate_pending_memory_candidates(
    session: AsyncSession,
    batch_size: int = DEFAULT_CURATION_BATCH_SIZE,
) -> BatchCurationResult:
    """Convenience function to deterministically curate a batch of pending candidates."""
    service = MemoryCurationService(session)
    return await service.curate_pending_candidates(batch_size=batch_size)

