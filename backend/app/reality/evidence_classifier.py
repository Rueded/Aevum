"""Evidence Classifier for Phase 7D.5 — Biographical Signal Detection.

Pure function module. No DB. No session. Synchronous. Fully testable in isolation.

Detects whether a user message contains a biographical assertion about Aevum
and, if so, identifies which fact slot is being implied.

SCOPE LOCKED (7D.5 Architecture Gate):
Only the 5 trigger patterns already validated by the Phase 7B.3 test suite
are implemented. Do NOT expand to new biography domains in this phase.

  Patterns:
    education.university      — GC-013 trigger area
    education.year            — GC-014 trigger area
    education.pathway         — GC-015 trigger area
    lifestyle.commute_mode    — GC-016 trigger area
    preferences.study_beverage— GC-017 trigger area

Questions, casual conversation, and input without a clear biographical
assertion must always return the NO_SIGNAL result.
"""

from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING

from app.reality.candidate_models import (
    InferenceEdgeType,
    InferenceScope,
    RealityTaxonomy,
)

if TYPE_CHECKING:
    from app.character.core_models import CharacterCore


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceClassificationResult:
    """Immutable result of biographical signal classification for one turn.

    has_biographical_signal=False means no CandidateHypothesis should be
    created for this turn (via this classifier).
    """

    has_biographical_signal: bool
    slot_name: Optional[str]            # e.g. "education.university"
    claimed_value: Optional[Any]        # extracted claim if parseable, else None
    inference_scope: InferenceScope
    inference_edge_type: InferenceEdgeType
    reality_taxonomy: RealityTaxonomy


# Canonical no-signal result — returned for all non-triggering input.
_NO_SIGNAL = EvidenceClassificationResult(
    has_biographical_signal=False,
    slot_name=None,
    claimed_value=None,
    inference_scope=InferenceScope.DIRECT,
    inference_edge_type=InferenceEdgeType.DIRECT_ATTRIBUTE,
    reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
)


# ---------------------------------------------------------------------------
# Pattern helpers
# ---------------------------------------------------------------------------


def _has_any(text: str, keywords: list[str]) -> bool:
    """Return True if any keyword appears in text (case-insensitive substring)."""
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def _has_all(text: str, keyword_groups: list[list[str]]) -> bool:
    """Return True if at least one keyword from every group appears in text."""
    lower = text.lower()
    return all(any(kw in lower for kw in group) for group in keyword_groups)


# ---------------------------------------------------------------------------
# Pattern guard: reject pure questions
# ---------------------------------------------------------------------------
# If the input is predominantly a question without an assertion, it should
# not generate a candidate even if it contains trigger keywords.
_QUESTION_MARKERS = [
    "吗", "吧", "？", "?", "呢", "哦吗", "对吗", "是吗",
    "what is", "do you", "are you", "is your", "which",
]


def _is_probably_question(text: str) -> bool:
    """Heuristic: return True if the text reads as a question without assertion.

    This catches "你学什么专业?" patterns which contain trigger words
    ("大学", "专业") but are asking about Aevum rather than asserting.
    """
    lower = text.lower()
    # If any question marker appears AND no first-person assertion markers
    has_q_marker = any(q in lower for q in _QUESTION_MARKERS)
    # First-person markers suggest the *user* is making a claim or asking
    # about Aevum's biography (could be either). We apply a stricter check:
    # if the sentence ends with a question mark (Chinese or ASCII), treat it
    # as a question.
    ends_with_question = text.rstrip().endswith("?") or text.rstrip().endswith("？")
    return has_q_marker and ends_with_question


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class EvidenceClassifier:
    """Biographical signal detector for per-turn candidate hypothesis generation.

    Implementation note:
    Trigger patterns are derived from the 5 patterns that were already
    validated in Phase 7B.3 (RealityBeliefEngine._formulate_candidate_from_stimulus).
    They are re-expressed here against the 7D.1 CandidateHypothesis model.
    """

    @classmethod
    def classify(
        cls,
        user_input: str,
        core: Optional["CharacterCore"] = None,
    ) -> EvidenceClassificationResult:
        """Classify user input for biographical signal about Aevum.

        Args:
            user_input: Raw user message for the current turn.
            core: Optional CharacterCore; used to avoid re-creating candidates
                  for already-canonical facts. If None, skipped.

        Returns:
            EvidenceClassificationResult with has_biographical_signal=True
            if a pattern matched, False otherwise.
        """
        text = user_input.strip()
        if not text:
            return _NO_SIGNAL

        # Quick question guard — questions are not assertions
        if _is_probably_question(text):
            return _NO_SIGNAL

        # ------------------------------------------------------------------
        # Pattern 4 (checked FIRST): lifestyle.commute_mode
        # Trigger: user asks how Aevum gets to school/class
        # Checked before education.university to prevent "学校" substring
        # in commute phrases from triggering the university pattern first.
        # 7B.3 legacy GC-016 equivalent
        # ------------------------------------------------------------------
        if _has_all(text, [
            ["去学校", "去上课", "去大学", "上课", "commute", "go to school",
             "go to class", "getting to", "get to school"],
            ["怎么去", "怎么走", "how do", "how to get", "walk", "bus", "ride",
             "drive", "cycle", "mrt", "grab", "交通", "走路", "骑车", "坐车",
             "开车", "公交", "公共交通"],
        ]):
            if core and hasattr(core, "facts"):
                existing = core.facts.get("lifestyle.commute_mode")
                if existing is not None:
                    return _NO_SIGNAL
            return EvidenceClassificationResult(
                has_biographical_signal=True,
                slot_name="lifestyle.commute_mode",
                claimed_value=None,
                inference_scope=InferenceScope.DIRECT,
                inference_edge_type=InferenceEdgeType.DIRECT_ATTRIBUTE,
                reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
            )

        # ------------------------------------------------------------------
        # Pattern 1: education.university
        # Trigger: user discusses what university or major Aevum studies
        # 7B.3 legacy GC-013 equivalent
        # ------------------------------------------------------------------
        if _has_all(text, [
            ["大学", "university", "uni", "college", "usm", "um", "学校"],
            ["读", "学", "念", "就读", "study", "studying", "attend", "attending",
             "在读", "professional", "course", "课程", "专业", "major", "faculty"],
        ]):
            # Check if already canonical to avoid duplicate candidates
            if core and hasattr(core, "facts"):
                existing = core.facts.get("education.university")
                if existing is not None:
                    return _NO_SIGNAL
            return EvidenceClassificationResult(
                has_biographical_signal=True,
                slot_name="education.university",
                claimed_value=None,   # value not directly parseable from trigger
                inference_scope=InferenceScope.LOCAL,
                inference_edge_type=InferenceEdgeType.STRUCTURAL_DEPENDENCY,
                reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
            )

        # ------------------------------------------------------------------
        # Pattern 2: education.year
        # Trigger: user mentions STPM / pre-u alongside year of study
        # 7B.3 legacy GC-014 equivalent
        # ------------------------------------------------------------------
        if _has_all(text, [
            ["stpm", "pre-u", "预科", "a level", "a-level", "form 6", "第六年级",
             "高中", "理科"],
            ["大几", "year", "几年级", "年级", "second year", "first year",
             "third year", "大一", "大二", "大三", "semester", "semesters"],
        ]):
            if core and hasattr(core, "facts"):
                existing = core.facts.get("education.year")
                if existing is not None:
                    return _NO_SIGNAL
            return EvidenceClassificationResult(
                has_biographical_signal=True,
                slot_name="education.year",
                claimed_value=None,
                inference_scope=InferenceScope.DEPENDENT,
                inference_edge_type=InferenceEdgeType.TEMPORAL_DEPENDENCY,
                reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
            )

        # ------------------------------------------------------------------
        # Pattern 3: education.pathway
        # Trigger: user mentions SPM alongside post-secondary pathway
        # 7B.3 legacy GC-015 equivalent
        # ------------------------------------------------------------------
        if _has_all(text, [
            ["spm", "中五", "o level", "o-level"],
            ["升学", "pathway", "路线", "after", "继续", "进入", "选择",
             "foundation", "matric", "matriculation", "diploma", "stpm"],
        ]):
            if core and hasattr(core, "facts"):
                existing = core.facts.get("education.pathway")
                if existing is not None:
                    return _NO_SIGNAL
            return EvidenceClassificationResult(
                has_biographical_signal=True,
                slot_name="education.pathway",
                claimed_value=None,
                inference_scope=InferenceScope.LOCAL,
                inference_edge_type=InferenceEdgeType.STRUCTURAL_DEPENDENCY,
                reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
            )

        # ------------------------------------------------------------------
        # Pattern 5: preferences.study_beverage
        # Trigger: user mentions reading/studying alongside a drink preference
        # 7B.3 legacy GC-017 equivalent
        # ------------------------------------------------------------------
        if _has_all(text, [
            ["看书", "读书", "study", "studying", "做功课", "做作业",
             "homework", "revision", "revise", "温习"],
            ["茶", "咖啡", "tea", "coffee", "喝", "drink", "beverage",
             "水", "milo", "teh", "kopi", "奶茶", "milk tea", "水瓶"],
        ]):
            if core and hasattr(core, "facts"):
                existing = core.facts.get("preferences.study_beverage")
                if existing is not None:
                    return _NO_SIGNAL
            return EvidenceClassificationResult(
                has_biographical_signal=True,
                slot_name="preferences.study_beverage",
                claimed_value=None,
                inference_scope=InferenceScope.DIRECT,
                inference_edge_type=InferenceEdgeType.BEHAVIORAL_CORRELATE,
                reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
            )

        # ------------------------------------------------------------------
        # No pattern matched
        # ------------------------------------------------------------------
        return _NO_SIGNAL
