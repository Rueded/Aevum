"""biographical_context_assembler.py — Phase 12.3 Context Assembly & Prompt Serialization Layer.

Governed by ADR-023:
1. Pure Read Projection: Assembly is strictly read-only; zero mutation authority (0 set_fact, 0 token).
2. Reality != Language: Context assembly organizes canonical reality; it never upgrades or canonicalizes it.
3. Lock 2 & Lock D: Causal UNKNOWN state is explicitly directed into humble, natural uncertainty.
4. Lock 5: Undefined biographical territory is protected with humble boundary directives, not canned scripts.
5. Bitwise Replay Determinism: Excludes execution timings and wall-clock timestamps from serialized payload and hash.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Sequence

from app.biography.biography_models import (
    BiographicalFact,
    CausalKnowledgeState,
    LifeEventRecord,
    PersonalPreference,
    QualiaAnchor,
    RecallLevel,
    SocialContactRecord,
)
from app.biography.causal_graph import CausalExplanationPath
from app.biography.retrieval_models import (
    AssembledBiographicalContext,
    AutobiographicalRetrievalResult,
)

logger = logging.getLogger(__name__)


class BiographicalContextAssembler:
    """Pure deterministic context builder transforming retrieved biographical structures into prompt XML."""

    @classmethod
    def assemble(
        cls,
        retrieval_result: AutobiographicalRetrievalResult,
    ) -> AssembledBiographicalContext:
        """Assembles structured AssembledBiographicalContext with complete epistemic boundary directives."""
        blocks: list[str] = [
            "<biographical_context>",
            "  <constitutional_boundary>",
            "    AUTOBIOGRAPHICAL CONTEXT IS DERIVED RETRIEVAL, NOT UNCONSTRAINED REALITY.",
            "    DO NOT CONFABULATE UNGROUNDED LIFE EVENTS OR ATTRIBUTES.",
            "    RESPECT DECLARED RECALL LEVELS (VIVID vs HAZY vs FRAGMENTARY).",
            "    PRESERVE UNKNOWN CAUSAL STATES AS HUMBLE, NATURAL UNCERTAINTY.",
            "  </constitutional_boundary>",
        ]

        directives: list[str] = []

        # 1. Canonical Facts Block
        if retrieval_result.matched_facts:
            blocks.append(f'  <canonical_facts count="{len(retrieval_result.matched_facts)}">')
            for fact in retrieval_result.matched_facts:
                blocks.append(
                    f'    <fact id="{fact.fact_id}" domain="{fact.domain.value}" '
                    f'era="{fact.era.value}" recall="{fact.recall_level.value}" status="{fact.canonical_status.value}">'
                )
                blocks.append(f'      {fact.attribute_key}: {fact.attribute_value}')
                blocks.append("    </fact>")
            blocks.append("  </canonical_facts>")

        # 2. Life Events Block
        if retrieval_result.matched_events:
            blocks.append(f'  <life_events count="{len(retrieval_result.matched_events)}">')
            for event in retrieval_result.matched_events:
                blocks.append(
                    f'    <event id="{event.event_id}" era="{event.era.value}" '
                    f'domain="{event.domain.value}" recall="{event.recall_level.value}" status="{event.canonical_status.value}">'
                )
                blocks.append(f'      <headline>{event.headline}</headline>')
                blocks.append(f'      <summary>{event.summary}</summary>')
                blocks.append("    </event>")
            blocks.append("  </life_events>")

        # 3. Personal Preferences Block
        if retrieval_result.matched_preferences:
            blocks.append(f'  <personal_preferences count="{len(retrieval_result.matched_preferences)}">')
            for pref in retrieval_result.matched_preferences:
                blocks.append(
                    f'    <preference id="{pref.preference_id}" category="{pref.category}" '
                    f'object="{pref.object_name}" affinity="{pref.affinity.value}" '
                    f'causal_state="{pref.causal_state.value}" />'
                )
            blocks.append("  </personal_preferences>")

        # 4. Causal Explanations Block
        if retrieval_result.causal_paths:
            blocks.append(f'  <causal_explanations count="{len(retrieval_result.causal_paths)}">')
            for path in retrieval_result.causal_paths:
                grounded_str = "true" if path.is_grounded else "false"
                blocks.append(
                    f'    <causal_path target_id="{path.target_id}" '
                    f'state="{path.causal_state.value}" grounded="{grounded_str}" '
                    f'terminal_reason="{path.terminal_reason}">'
                )
                if path.steps:
                    for step in path.steps:
                        blocks.append(
                            f'      <step source="{step.source_id}" target="{step.target_id}" '
                            f'relation="{step.relation_type.value}" narrative="{step.narrative_summary}" />'
                        )
                blocks.append("    </causal_path>")
            blocks.append("  </causal_explanations>")

        # 5. Qualia Anchors Block
        if retrieval_result.matched_qualia:
            blocks.append(f'  <qualia_anchors count="{len(retrieval_result.matched_qualia)}">')
            for qualia in retrieval_result.matched_qualia:
                coloring = qualia.emotional_coloring or "neutral"
                blocks.append(
                    f'    <qualia id="{qualia.qualia_id}" modality="{qualia.sensory_modality}" '
                    f'coloring="{coloring}">'
                )
                blocks.append(f'      {qualia.description}')
                blocks.append("    </qualia>")
            blocks.append("  </qualia_anchors>")

        # 6. Social Contacts Block
        if retrieval_result.matched_contacts:
            blocks.append(f'  <social_contacts count="{len(retrieval_result.matched_contacts)}">')
            for contact in retrieval_result.matched_contacts:
                user_marker = ' is_user="true"' if contact.is_user else ""
                blocks.append(
                    f'    <contact id="{contact.contact_id}" name="{contact.display_name}" '
                    f'role="{contact.relation_role}" era="{contact.era_first_met.value}"{user_marker} />'
                )
            blocks.append("  </social_contacts>")

        # 7. Epistemic Guidance & Boundary Directives (Lock 5 & Lock D)
        blocks.append("  <epistemic_directives>")

        # Lock D: UNKNOWN Causal Origins
        if retrieval_result.has_unknown_causal_boundary:
            for path in retrieval_result.causal_paths:
                if path.causal_state == CausalKnowledgeState.UNKNOWN:
                    directive = (
                        f"The causal origin for '{path.target_id}' is unknown. "
                        "Express natural, humble uncertainty or simple personal inclination (e.g. 'I just naturally like it'). "
                        "NEVER invent an origin story, dramatic epiphany, or past incident."
                    )
                    directives.append(directive)
                    blocks.append(f'    <directive type="CAUSAL_UNKNOWN" target="{path.target_id}">')
                    blocks.append(f'      {directive}')
                    blocks.append("    </directive>")

        # Lock 5: Undefined Biographical Territory
        if retrieval_result.is_empty:
            directive = (
                "No canonical life events, facts, or preferences exist for this inquiry. "
                "Aevum does not possess a recorded past in this area. "
                "Acknowledge the lack of memory or experience naturally and honestly without improvising new life history."
            )
            directives.append(directive)
            blocks.append('    <directive type="UNDEFINED_TERRITORY">')
            blocks.append(f'      {directive}')
            blocks.append("    </directive>")

        # RecallLevel qualification directives
        for fact in retrieval_result.matched_facts:
            if fact.recall_level == RecallLevel.HAZY:
                directive = (
                    f"Fact '{fact.fact_id}' ({fact.attribute_key}) is confirmed in outline, but finer experiential details are hazy. "
                    "Express recall with gentle qualification rather than pinpoint precision."
                )
                directives.append(directive)
                blocks.append(f'    <directive type="RECALL_HAZY" target="{fact.fact_id}">')
                blocks.append(f'      {directive}')
                blocks.append("    </directive>")
            elif fact.recall_level == RecallLevel.FRAGMENTARY:
                directive = (
                    f"Fact '{fact.fact_id}' ({fact.attribute_key}) is only a fragmentary impression. "
                    "Do not elaborate into a full narrative sequence."
                )
                directives.append(directive)
                blocks.append(f'    <directive type="RECALL_FRAGMENTARY" target="{fact.fact_id}">')
                blocks.append(f'      {directive}')
                blocks.append("    </directive>")

        for event in retrieval_result.matched_events:
            if event.recall_level == RecallLevel.HAZY:
                directive = (
                    f"Event '{event.event_id}' ({event.headline}) is remembered in core substance, but specific moments are hazy. "
                    "Reflect mild nostalgic distance or soft recall."
                )
                directives.append(directive)
                blocks.append(f'    <directive type="RECALL_HAZY" target="{event.event_id}">')
                blocks.append(f'      {directive}')
                blocks.append("    </directive>")
            elif event.recall_level == RecallLevel.FRAGMENTARY:
                directive = (
                    f"Event '{event.event_id}' ({event.headline}) is a fragmentary snapshot or sensory flash. "
                    "Keep expression brief and impressionistic."
                )
                directives.append(directive)
                blocks.append(f'    <directive type="RECALL_FRAGMENTARY" target="{event.event_id}">')
                blocks.append(f'      {directive}')
                blocks.append("    </directive>")

        blocks.append("  </epistemic_directives>")
        blocks.append("</biographical_context>")

        context_text = "\n".join(blocks)
        context_hash = hashlib.sha256(context_text.encode("utf-8")).hexdigest()

        summary = {
            "facts": len(retrieval_result.matched_facts),
            "events": len(retrieval_result.matched_events),
            "preferences": len(retrieval_result.matched_preferences),
            "causal_paths": len(retrieval_result.causal_paths),
            "qualia": len(retrieval_result.matched_qualia),
            "contacts": len(retrieval_result.matched_contacts),
            "directives": len(directives),
        }

        return AssembledBiographicalContext(
            context_text=context_text,
            context_hash=context_hash,
            retrieval_summary=summary,
            epistemic_directives=tuple(directives),
        )
