"""
observation_adapters.py — External Observation Adapters & Protocols

Phase 9.3 Deliverable under Architecture Gate v0.2:
- Decouples external observation collection from cognitive epistemic evaluation (Issue 5).
- Adapters observe and package external data strictly as ExternalObservation.
- Adapters possess ZERO authority to declare truth, compute epistemic status, or mutate reality.
- Provides WorldKnowledgeObservationAdapter for deterministic local institutional lookup.
- Provides InMemoryObservationAdapter for deterministic unit testing and fixture injection.

Zero network calls, zero database writes, zero LLM dependencies, zero mutation authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Protocol, Sequence
from uuid import uuid4

from app.reality.verification_models import (
    ExternalObservation,
    SourceAuthority,
    SourceKind,
    VerificationProvenance,
)
from app.reality.world_knowledge import WorldKnowledgeRegistry, WorldKnowledgeItem


class ObservationAdapterProtocol(Protocol):
    """
    Protocol for external observation sources.
    Collects raw observations without judging epistemic credibility or validity.
    """

    def observe(
        self,
        claim_key: str,
        allowed_source_kinds: tuple[SourceKind, ...],
        limit: int = 5,
        target_entity_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> tuple[ExternalObservation, ...]:
        """Collect external observations matching the claim_key or entity."""
        ...


class WorldKnowledgeObservationAdapter:
    """
    Adapter that draws read-only observations from the deterministic WorldKnowledgeRegistry.
    Represents verified primary institutional rules and official public records.
    """

    def __init__(self, registry: Optional[type[WorldKnowledgeRegistry]] = None) -> None:
        self._registry = registry or WorldKnowledgeRegistry

    def observe(
        self,
        claim_key: str,
        allowed_source_kinds: tuple[SourceKind, ...],
        limit: int = 5,
        target_entity_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> tuple[ExternalObservation, ...]:
        now = datetime.now(timezone.utc)
        observations: list[ExternalObservation] = []

        # Check if public registry or institutional portal source kinds are allowed
        valid_kinds = {SourceKind.PUBLIC_REGISTRY, SourceKind.INSTITUTIONAL_PORTAL}
        permitted = any(k in valid_kinds for k in allowed_source_kinds)
        if not permitted:
            return ()

        # Direct key lookup or fallback match
        item: Optional[WorldKnowledgeItem] = self._registry.get(claim_key)
        if item is None and not claim_key.startswith("world."):
            item = self._registry.get(f"world.{claim_key}")
        if item is None:
            raw_reg = getattr(self._registry, "_REGISTRY", {})
            tokens = set(t.lower() for t in claim_key.replace("_", ".").split(".") if len(t) > 2)
            for reg_k, reg_item in raw_reg.items():
                reg_tokens = set(t.lower() for t in reg_k.replace("_", ".").split(".") if len(t) > 2)
                if len(tokens & reg_tokens) >= 2:
                    item = reg_item
                    break
        if item is not None:
            provenance = VerificationProvenance(
                source_id="world_knowledge_registry",
                source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
                source_kind=SourceKind.PUBLIC_REGISTRY,
                retrieval_timestamp=now,
                source_uri_or_identifier=f"world_knowledge://{item.key}",
                raw_content_digest_sha256=None,
            )
            obs = ExternalObservation(
                observation_id=f"obs-wk-{uuid4().hex[:10]}",
                source_provenance=provenance,
                observed_content_snippet=item.description or f"{item.key}: {item.value}",
                structured_payload={"key": item.key, "value": item.value, "kind": item.kind.value},
                observed_at=now,
                temporal_anchor=None,
                observed_entity_name=None,
            )
            observations.append(obs)

        return tuple(observations[:limit])


class InMemoryObservationAdapter:
    """
    Deterministic in-memory observation adapter for unit tests, fixtures,
    and mock verification pipelines.
    """

    def __init__(self, seed_observations: Optional[Sequence[ExternalObservation]] = None) -> None:
        self._observations: list[ExternalObservation] = list(seed_observations or [])

    def add_observation(self, observation: ExternalObservation) -> None:
        self._observations.append(observation)

    def observe(
        self,
        claim_key: str,
        allowed_source_kinds: tuple[SourceKind, ...],
        limit: int = 5,
        target_entity_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> tuple[ExternalObservation, ...]:
        results: list[ExternalObservation] = []

        for obs in self._observations:
            # Check source kind permission
            if obs.source_provenance.source_kind not in allowed_source_kinds:
                continue

            # Key or snippet match
            key_in_payload = obs.structured_payload.get("key") == claim_key
            key_in_snippet = claim_key in obs.observed_content_snippet

            # Entity match if specified
            entity_match = True
            if target_entity_name is not None:
                entity_match = (
                    obs.observed_entity_name == target_entity_name
                    or target_entity_name in obs.observed_content_snippet
                )

            if (key_in_payload or key_in_snippet) and entity_match:
                results.append(obs)

            if len(results) >= limit:
                break

        return tuple(results)
