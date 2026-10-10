"""
pragmatic_context_adapter.py — Pragmatic Context Assembly & Prompt Projection Layer

Phase 15.5 Deliverable under ADR-026 (Architecture Gate Approved & Frozen):
- Serializes Phase 15.1 Speech Act Interpretation, Phase 15.2 Epistemic Treatment,
  Phase 15.3 Social Contradiction Analysis, and Phase 15.4 Verification Dispatch
  into a governed XML prompt context: `<pragmatic_epistemic_context>`.
- Enforces Constitutional Directives:
  - Rule 12: LLM generates dialogue but does not define reality.
  - Watchpoint: ACCEPT_SOCIAL != Memory Writing.
  - Lock 5: Zero Lie-Detector Sycophancy (warm, natural presence; no cross-examination).
  - Lock 6: Anti-Compensatory Hallucination (explicit list of forbidden bridge facts).
- Bitwise determinism: formatted cleanly, fully testable, pure read projection.
- Zero database writes, zero LLM calls, zero network calls, zero mutation authority.
"""

from __future__ import annotations

import hashlib
import xml.sax.saxutils as saxutils
from typing import Optional

from app.reality.epistemic_policy_models import EpistemicTreatmentDecision
from app.reality.social_contradiction_models import SocialDiscrepancyAnalysis
from app.reality.speech_act_models import PragmaticInterpretation
from app.reality.verification_dispatcher_models import VerificationDispatchEnvelope


class PragmaticContextAdapter:
    """
    Pure deterministic serializer projecting Phase 15 pragmatic analysis
    into the governed reality prompt context.
    """

    @classmethod
    def render_xml(
        cls,
        interpretation: PragmaticInterpretation,
        treatment: EpistemicTreatmentDecision,
        contradiction_analysis: Optional[SocialDiscrepancyAnalysis] = None,
        dispatch_envelope: Optional[VerificationDispatchEnvelope] = None,
    ) -> str:
        """
        Render a governed `<pragmatic_epistemic_context>` XML block.
        """
        lines = [
            "<pragmatic_epistemic_context>",
            "  <constitutional_directives>",
            "    - Rule 11 & 12: The LLM generates authentic conversational language but does NOT define reality.",
            "    - Watchpoint: Conversational acceptance (ACCEPT_SOCIAL) is strictly for current-turn dialogue context; never write to long-term memory or canonical biography.",
            "    - Lock 5: Speak with natural companion warmth and gentle curiosity; NEVER act as a courtroom interrogator, polygraph, or adversarial fact-checker.",
            "    - Lock 6: When surface discrepancies or logistical tensions arise, NEVER invent unsupported bridge facts (e.g. fake holidays, dropped classes, secret moves). Ask the user or banter playfully.",
            "  </constitutional_directives>",
        ]

        # Speech act block
        sec_act = f' secondary="{interpretation.secondary_act.value}"' if interpretation.secondary_act else ""
        prop_escaped = saxutils.escape(interpretation.literal_proposition or "")
        lines.append(
            f'  <speech_act primary="{interpretation.primary_act.value}"{sec_act} '
            f'tone="{interpretation.social_tone}" ambiguity="{str(interpretation.ambiguity_flag).lower()}">'
        )
        if prop_escaped:
            lines.append(f"    <literal_proposition>{prop_escaped}</literal_proposition>")
        summary_escaped = saxutils.escape(interpretation.pragmatic_intent_summary)
        lines.append(f"    <intent_summary>{summary_escaped}</intent_summary>")
        lines.append("  </speech_act>")

        # Epistemic treatment block
        lines.append(
            f'  <epistemic_treatment kind="{treatment.treatment.value}" '
            f'working_context_accept="{str(treatment.working_context_accept).lower()}" '
            f'requires_repair_inquiry="{str(treatment.requires_repair_inquiry).lower()}" '
            f'teasing_recommended="{str(treatment.teasing_tone_recommended).lower()}">'
        )
        rationale_escaped = saxutils.escape(treatment.rationale)
        lines.append(f"    <rationale>{rationale_escaped}</rationale>")
        lines.append("  </epistemic_treatment>")

        # Social contradiction / tension block
        if contradiction_analysis:
            lines.append(
                f'  <social_discrepancy type="{contradiction_analysis.discrepancy_type.value}" '
                f'severity="{contradiction_analysis.severity.value}" '
                f'repair_strategy="{contradiction_analysis.repair_strategy.value}" '
                f'genuine_contradiction="{str(contradiction_analysis.is_genuine_contradiction).lower()}">'
            )
            guidance_escaped = saxutils.escape(contradiction_analysis.inquiry_prompt_guidance)
            lines.append(f"    <inquiry_guidance>{guidance_escaped}</inquiry_guidance>")

            # Lock 6 forbidden bridge facts
            if contradiction_analysis.forbidden_compensatory_assumptions:
                lines.append("    <forbidden_compensatory_assumptions>")
                for assumption in contradiction_analysis.forbidden_compensatory_assumptions:
                    assump_escaped = saxutils.escape(assumption)
                    lines.append(f"      <prohibited>{assump_escaped}</prohibited>")
                lines.append("    </forbidden_compensatory_assumptions>")
            lines.append("  </social_discrepancy>")

        # External verification status block
        if dispatch_envelope:
            req_id = dispatch_envelope.verification_request.request_id if dispatch_envelope.verification_request else "none"
            lines.append(
                f'  <verification_dispatch status="{dispatch_envelope.dispatch_status.value}" '
                f'request_id="{req_id}">'
            )
            lines.append(f"    <rationale>{saxutils.escape(dispatch_envelope.rationale)}</rationale>")
            lines.append("  </verification_dispatch>")

        lines.append("</pragmatic_epistemic_context>")
        return "\n".join(lines)

    @classmethod
    def compute_context_hash(cls, xml_str: str) -> str:
        """Compute bitwise deterministic SHA-256 hash of serialized pragmatic context."""
        return hashlib.sha256(xml_str.encode("utf-8")).hexdigest()
