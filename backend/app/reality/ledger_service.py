"""Service for generating structured Reality Ledger projections from Character Core."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.character.core_service import CharacterCoreService
from app.reality.ledger_models import LedgerItem, RealityLedgerProjection
from app.reality.models import CoreFactItem, FactStatus, LedgerTier


class RealityLedgerService:
    """Provides categorized multi-tier projections of character reality."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._core_service = CharacterCoreService(session)

    async def get_ledger(self, character_id: str = "aevum") -> RealityLedgerProjection:
        """Construct the three-tier reality ledger projection from persistent core facts."""
        core = await self._core_service.get_core(character_id)

        green: list[LedgerItem] = []
        yellow: list[LedgerItem] = []
        red: list[LedgerItem] = []

        total_confidence = 0.0
        locked_count = 0
        candidate_count = 0

        for key, fact in core.facts.items():
            item = self._fact_to_ledger_item(fact)
            total_confidence += fact.epistemic_confidence
            if fact.is_locked:
                locked_count += 1
            if fact.status == FactStatus.CANDIDATE:
                candidate_count += 1

            if fact.tier == LedgerTier.USER_EDITABLE:
                green.append(item)
            elif fact.tier == LedgerTier.SYSTEM_INTEGRITY:
                red.append(item)
            else:
                yellow.append(item)

        total_facts = len(core.facts)
        avg_conf = (total_confidence / total_facts) if total_facts > 0 else 1.0

        return RealityLedgerProjection(
            character_id=character_id,
            green_user_editable=green,
            yellow_aevum_emergent=yellow,
            red_system_integrity=red,
            total_facts=total_facts,
            locked_count=locked_count,
            candidate_count=candidate_count,
            average_confidence=round(avg_conf, 4),
        )

    def _fact_to_ledger_item(self, fact: CoreFactItem) -> LedgerItem:
        return LedgerItem(
            key=fact.key,
            category=fact.category,
            value=fact.value,
            tier=fact.tier,
            source=fact.source,
            authority=fact.authority,
            status=fact.status,
            confidence=fact.epistemic_confidence,
            locked=fact.locked,
            explanation=fact.explanation,
            created_at=fact.created_at.isoformat(),
            updated_at=fact.updated_at.isoformat(),
        )
