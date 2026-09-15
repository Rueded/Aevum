"""Deterministic automatic memory curation policy for Aevum Core.

Evaluates uncurated PENDING MemoryCandidates against application-owned,
deterministic criteria to decide whether they should be accepted into persistent
Memory, rejected, or deferred (remaining PENDING).

Strictly zero LLM calls, zero semantic similarity, and zero randomness.
"""

import re

from app.memory.models import (
    CandidateEvaluation,
    MemoryCandidate,
    MemoryCandidateStatus,
    MemoryCategory,
    MemoryCurationDecision,
    MemoryCurationReason,
)

MEMORY_CURATION_POLICY_VERSION: str = "1.0.0"

# Regex patterns identifying sensitive credentials or secrets
_CREDENTIAL_PATTERNS = [
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret[_-]?key|private[_-]?key|password|passwd)\b(?:\s*[:=]|\s+is\s+)\s*\S+"
    ),
    re.compile(r"(?i)\bbearer\s+[a-zA-Z0-9_\-\.]+"),
    re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----"),
    re.compile(r"\bghp_[a-zA-Z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
    re.compile(r"\bsk-[a-zA-Z0-9_-]{20,}\b"),
]



def contains_obvious_credentials(text: str) -> bool:
    """Return True if the text contains obvious credentials, tokens, or secrets."""
    for pattern in _CREDENTIAL_PATTERNS:
        if pattern.search(text):
            return True
    return False


# Baseline quality thresholds
MIN_CONFIDENCE_THRESHOLD: float = 0.70
MIN_IMPORTANCE_THRESHOLD: float = 0.30

# Category-specific acceptance thresholds (confidence, importance)
_CATEGORY_ACCEPTANCE_THRESHOLDS: dict[MemoryCategory, tuple[float, float, MemoryCurationReason]] = {
    MemoryCategory.FACT: (0.90, 0.60, MemoryCurationReason.ACCEPTED_STABLE_FACT),
    MemoryCategory.PREFERENCE: (0.90, 0.60, MemoryCurationReason.ACCEPTED_STRONG_PREFERENCE),
    MemoryCategory.USER_GOAL: (0.90, 0.60, MemoryCurationReason.ACCEPTED_USER_GOAL),
    MemoryCategory.USER_PROBLEM: (0.90, 0.70, MemoryCurationReason.ACCEPTED_USER_PROBLEM),
    MemoryCategory.PROMISE: (0.90, 0.70, MemoryCurationReason.ACCEPTED_PROMISE),
    MemoryCategory.EVENT: (0.90, 0.70, MemoryCurationReason.ACCEPTED_EVENT),
}

# Categories requiring relational or autonomy context that cannot be safely auto-accepted
_AMBIGUOUS_CATEGORIES: set[MemoryCategory] = {
    MemoryCategory.EXPERIENCE,
    MemoryCategory.JOKE,
    MemoryCategory.RELATIONSHIP,
    MemoryCategory.CHARACTER_EVENT,
}


def evaluate_candidate(candidate: MemoryCandidate) -> CandidateEvaluation:
    """Deterministically evaluate a memory candidate according to Aevum policy v1.0.0.

    Evaluation hierarchy:
      1. Terminal status check: Non-PENDING candidates are rejected.
      2. Secret / credential check: Proposals with secrets are rejected.
      3. Minimum quality check: Low confidence (<0.70) or low importance (<0.30) are rejected.
      4. Contextual ambiguity check: Categories requiring rich relational/autonomy context are deferred.
      5. Category acceptance thresholds: Satisfying category criteria leads to ACCEPT.
      6. Insufficient salience: Candidates between minimum quality and accept criteria are deferred.
    """
    # 1. Terminal state check
    if candidate.status != MemoryCandidateStatus.PENDING:
        return CandidateEvaluation(
            decision=MemoryCurationDecision.REJECT,
            reason=MemoryCurationReason.REJECTED_TERMINAL,
            explanation=f"Candidate is in terminal state '{candidate.status.value}'.",
        )

    # 2. Defense-in-depth credential filtering
    if contains_obvious_credentials(candidate.content):
        return CandidateEvaluation(
            decision=MemoryCurationDecision.REJECT,
            reason=MemoryCurationReason.REJECTED_SECRET,
            explanation="Candidate content contains sensitive credentials or secret material.",
        )

    # 3. Minimum quality filtering
    if candidate.confidence < MIN_CONFIDENCE_THRESHOLD:
        return CandidateEvaluation(
            decision=MemoryCurationDecision.REJECT,
            reason=MemoryCurationReason.REJECTED_LOW_CONFIDENCE,
            explanation=f"Confidence {candidate.confidence:.2f} is below minimum threshold {MIN_CONFIDENCE_THRESHOLD:.2f}.",
        )

    if candidate.importance < MIN_IMPORTANCE_THRESHOLD:
        return CandidateEvaluation(
            decision=MemoryCurationDecision.REJECT,
            reason=MemoryCurationReason.REJECTED_LOW_IMPORTANCE,
            explanation=f"Importance {candidate.importance:.2f} is below minimum threshold {MIN_IMPORTANCE_THRESHOLD:.2f}.",
        )

    # 4. Contextual ambiguity check
    if candidate.category in _AMBIGUOUS_CATEGORIES:
        return CandidateEvaluation(
            decision=MemoryCurationDecision.DEFER,
            reason=MemoryCurationReason.DEFERRED_AMBIGUOUS_CATEGORY,
            explanation=f"Category '{candidate.category.value}' requires relational or autonomy context and is deferred as PENDING.",
        )

    # 5. Category-specific acceptance evaluation
    threshold_config = _CATEGORY_ACCEPTANCE_THRESHOLDS.get(candidate.category)
    if threshold_config is not None:
        min_conf, min_imp, reason = threshold_config
        if candidate.confidence >= min_conf and candidate.importance >= min_imp:
            return CandidateEvaluation(
                decision=MemoryCurationDecision.ACCEPT,
                reason=reason,
                explanation=(
                    f"Candidate satisfies {candidate.category.value} criteria "
                    f"(confidence {candidate.confidence:.2f} >= {min_conf:.2f}, "
                    f"importance {candidate.importance:.2f} >= {min_imp:.2f})."
                ),
            )

    # 6. Default to conservative deferral
    return CandidateEvaluation(
        decision=MemoryCurationDecision.DEFER,
        reason=MemoryCurationReason.DEFERRED_INSUFFICIENT_SALIENCE,
        explanation="Candidate meets baseline quality but does not satisfy category acceptance threshold; remains PENDING.",
    )
