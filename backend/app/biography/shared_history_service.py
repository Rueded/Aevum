"""shared_history_service.py — Phase 12.4 Longitudinal Shared History Service & Context Assembler.

Governed by ADR-023:
1. Constitutional Axiom: "Shared History records what Aevum and the user experienced together;
   it does not rewrite what Aevum was before the relationship."
2. Lock 4 & Lock F: Strict Relational Isolation. All episodes are HistoryScope.SHARED_WITH_USER.
3. Lock 6: Segregated Promotion Authority. SharedHistoryService holds independent promotion authority
   for shared episodes, completely decoupled from BiographyPromotionService (zero PromotionAuthorizationToken).
4. Watchpoint: Scope-first retrieval. Shared history queries operate strictly within the shared domain.
5. Rule 16 Integration: Injects multi-axis relationship dynamics into dual-track longitudinal context.
6. Bitwise Replay Determinism: Excludes runtime timestamps from prompt XML and SHA-256 hash.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional, Sequence

from app.biography.biography_models import (
    CanonicalStatus,
    HistoryScope,
    LifeEra,
    RecallLevel,
)
from app.biography.retrieval_models import AssembledBiographicalContext
from app.biography.shared_history_models import (
    AssembledLongitudinalContext,
    SharedEpisodeType,
    SharedHistoryCandidate,
    SharedHistoryEpisode,
    SharedHistoryQuery,
)

logger = logging.getLogger(__name__)


class SharedHistoryService:
    """Independent promotion authority and query engine for shared history episodes (Lock 6)."""

    MAX_SHARED_EPISODES: int = 4

    def __init__(self) -> None:
        self._episodes: dict[str, SharedHistoryEpisode] = {}

    @property
    def total_episodes_count(self) -> int:
        """Returns the number of stored canonical shared episodes."""
        return len(self._episodes)

    # ========================================================================
    # Independent Promotion Authority (Lock 6)
    # ========================================================================

    def promote_candidate(self, candidate: SharedHistoryCandidate) -> SharedHistoryEpisode:
        """Promotes a validated SharedHistoryCandidate into a canonical SharedHistoryEpisode.

        Strict Constitutional Invariant (Lock 6):
        This service has ZERO authority to author or mutate Aevum's personal biography facts.
        It NEVER touches BiographyPromotionService, NEVER uses PromotionAuthorizationToken,
        and NEVER mutates HistoryScope.AEVUM_PERSONAL records.
        """
        if not candidate.session_anchor or not candidate.session_anchor.strip():
            raise ValueError("Candidate rejection: session_anchor is mandatory for SharedHistoryEpisode")

        if "user" not in candidate.participants or "aevum" not in candidate.participants:
            raise ValueError("Candidate rejection: participants must include both 'user' and 'aevum'")

        episode_id = candidate.candidate_id
        if not episode_id.startswith("ep_"):
            episode_id = f"ep_{episode_id}"

        # Deduplication check
        for existing in self._episodes.values():
            if existing.session_anchor == candidate.session_anchor and existing.title == candidate.title:
                logger.info("Shared episode already promoted for session %s: %s", candidate.session_anchor, candidate.title)
                return existing

        episode = SharedHistoryEpisode(
            episode_id=episode_id,
            scope=HistoryScope.SHARED_WITH_USER,
            episode_type=candidate.episode_type,
            title=candidate.title,
            summary=candidate.summary,
            session_anchor=candidate.session_anchor,
            turn_range=candidate.turn_range,
            participants=candidate.participants,
            key_learnings=candidate.key_learnings,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.VIVID,
            created_at_era=LifeEra.ADULTHOOD,
        )

        self._episodes[episode.episode_id] = episode
        return episode

    def register_episode(self, episode: SharedHistoryEpisode) -> None:
        """Directly registers an already constructed SharedHistoryEpisode."""
        if episode.scope != HistoryScope.SHARED_WITH_USER:
            raise ValueError(
                f"Lock 4 Violation: Cannot register episode with scope '{episode.scope}' into SharedHistoryService"
            )
        self._episodes[episode.episode_id] = episode

    # ========================================================================
    # Scope-First Query & Retrieval
    # ========================================================================

    def query_episodes(self, query: SharedHistoryQuery) -> tuple[SharedHistoryEpisode, ...]:
        """Scope-first query strictly bounded within HistoryScope.SHARED_WITH_USER."""
        scored: list[tuple[int, SharedHistoryEpisode]] = []

        for ep in self._episodes.values():
            score = self._score_episode(ep, query)
            if score > 0:
                scored.append((score, ep))

        # Deterministic sort: -score, then episode_id ascending
        scored.sort(key=lambda pair: (-pair[0], pair[1].episode_id))
        return tuple(ep for _, ep in scored[: self.MAX_SHARED_EPISODES])

    def get_episode_by_id(self, episode_id: str) -> Optional[SharedHistoryEpisode]:
        """Retrieves a shared episode by ID."""
        return self._episodes.get(episode_id)

    def get_recent_episodes(self, limit: int = 4) -> tuple[SharedHistoryEpisode, ...]:
        """Retrieves recent shared episodes sorted deterministically by ID."""
        episodes = sorted(self._episodes.values(), key=lambda ep: ep.episode_id, reverse=True)
        return tuple(episodes[:limit])

    def _score_episode(self, episode: SharedHistoryEpisode, query: SharedHistoryQuery) -> int:
        matched = False
        score = 0

        # Session anchor exact match
        if query.session_anchor is not None:
            if episode.session_anchor == query.session_anchor:
                score += 30
                matched = True
            elif not query.keywords:
                return 0

        # Episode type exact match
        if query.episode_type is not None:
            if episode.episode_type == query.episode_type:
                score += 30
                matched = True
            elif not query.keywords and query.session_anchor is None:
                return 0

        # Keywords match
        if query.keywords:
            kw_hits = 0
            haystack = f"{episode.title} {episode.summary} {' '.join(episode.key_learnings)}".lower()
            for kw in query.keywords:
                if kw.lower() in haystack:
                    kw_hits += 1
            if kw_hits > 0:
                score += min(40, kw_hits * 20)
                matched = True

        # Direct string presence
        if episode.title.lower() in query.raw_query.lower():
            score += 25
            matched = True

        if not matched:
            return 0

        # RecallLevel weighting
        if episode.recall_level == RecallLevel.VIVID:
            score += 10
        elif episode.recall_level == RecallLevel.HAZY:
            score += 5

        return min(100, max(0, score))


class LongitudinalContextAssembler:
    """Pure deterministic context builder merging Track 1 (Personal) and Track 2 (Shared)."""

    @classmethod
    def assemble(
        cls,
        personal_context: AssembledBiographicalContext,
        shared_episodes: Sequence[SharedHistoryEpisode] = (),
        relational_metrics: Optional[dict[str, float]] = None,
    ) -> AssembledLongitudinalContext:
        """Assembles structured AssembledLongitudinalContext with complete dual-track separation."""
        blocks: list[str] = [
            "<longitudinal_context>",
            "  <constitutional_boundary>",
            "    LONGITUDINAL CONTEXT IS DERIVED PRESENTATION OF DUAL-TRACK REALITY.",
            "    PERSONAL BIOGRAPHY AND SHARED HISTORY ARE MUTUALLY ISOLATED TRACKS.",
            "    SHARED EXPERIENCES DO NOT ALTER OR RETROACTIVELY EDIT AEVUM'S PERSONAL PAST.",
            "  </constitutional_boundary>",
            "",
            "  <!-- Track 1: Personal Autobiographical World -->",
            "  <personal_biography_track>",
        ]

        # Embed Track 1 (indenting internal lines for clean XML structure)
        for line in personal_context.context_text.splitlines():
            blocks.append(f"    {line}")
        blocks.append("  </personal_biography_track>")
        blocks.append("")

        # Embed Track 2: Shared History with User
        blocks.append("  <!-- Track 2: Longitudinal Shared History with User -->")
        blocks.append(f'  <shared_history_track count="{len(shared_episodes)}">')
        if shared_episodes:
            for ep in shared_episodes:
                blocks.append(
                    f'    <episode id="{ep.episode_id}" type="{ep.episode_type.value}" '
                    f'session="{ep.session_anchor}" recall="{ep.recall_level.value}">'
                )
                blocks.append(f'      <title>{ep.title}</title>')
                blocks.append(f'      <summary>{ep.summary}</summary>')
                if ep.key_learnings:
                    blocks.append(f'      <learnings count="{len(ep.key_learnings)}">')
                    for item in ep.key_learnings:
                        blocks.append(f'        <learning>{item}</learning>')
                    blocks.append("      </learnings>")
                blocks.append("    </episode>")
        blocks.append("  </shared_history_track>")
        blocks.append("")

        # Rule 16: Relational Dynamics
        blocks.append("  <!-- Relational Dynamics (Rule 16 Multidimensional Dynamics) -->")
        if relational_metrics:
            blocks.append('  <relational_dynamics_track status="ACTIVE">')
            for metric_name in sorted(relational_metrics.keys()):
                val = relational_metrics[metric_name]
                blocks.append(f'    <metric name="{metric_name}" value="{val:.4f}" />')
            blocks.append("  </relational_dynamics_track>")
        else:
            blocks.append('  <relational_dynamics_track status="UNSPECIFIED" />')

        blocks.append("</longitudinal_context>")

        longitudinal_xml = "\n".join(blocks)
        context_hash = hashlib.sha256(longitudinal_xml.encode("utf-8")).hexdigest()

        return AssembledLongitudinalContext(
            personal_context=personal_context,
            shared_episodes=tuple(shared_episodes),
            relational_metrics=relational_metrics,
            longitudinal_xml=longitudinal_xml,
            context_hash=context_hash,
        )
