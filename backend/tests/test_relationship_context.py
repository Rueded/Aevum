"""Comprehensive test suite for Phase 4.3: Relationship Context Integration.

Verifies:
- RelationshipContext model validation, immutability, extra field rejection, and string bounds.
- Semantic translation accuracy across all 6 dimensions.
- Bootstrap state translation and natural narrative summary synthesis.
- Synthesis of interaction guidance based on state.
- Multidimensional state preservation:
  * Scenario 32: High familiarity + high trust + zero affection (no romance implication).
  * Scenario 33: High familiarity + low trust (not close friends).
  * Scenario 34: High trust + low familiarity (trusted despite being new).
- Affection safety and zero-romance guarantees.
- Attachment safety (no dependency phrasing, no "needs the user").
- Prevention of raw numerical leakage (no floats, no "trust =", no "affection =").
- Prevention of gamification leakage (no XP, levels, stages, policy version, signal types).
- Context formatting in XML (`<relationship_context version="1.0">`) within MAX_RELATIONSHIP_CONTEXT_CHARS.
- Determinism and immutability (pure function, no mutation of input state).
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.relationship import (
    BOOTSTRAP_AFFECTION,
    BOOTSTRAP_ATTACHMENT,
    BOOTSTRAP_COMFORT,
    BOOTSTRAP_FAMILIARITY,
    BOOTSTRAP_RESPECT,
    BOOTSTRAP_TRUST,
    DEFAULT_RELATIONSHIP_ID,
    DEFAULT_USER_ID,
    MAX_RELATIONSHIP_CONTEXT_CHARS,
    RELATIONSHIP_CONTEXT_VERSION,
    RelationshipContext,
    RelationshipContextBuilder,
    RelationshipState,
    build_relationship_context,
    create_initial_relationship_state,
    get_affection_summary,
    get_attachment_summary,
    get_comfort_summary,
    get_familiarity_summary,
    get_respect_summary,
    get_trust_summary,
    synthesize_interaction_guidance,
    synthesize_relationship_summary,
)


def _make_state(
    familiarity: float = 0.0,
    trust: float = 0.0,
    comfort: float = 0.0,
    affection: float = 0.0,
    attachment: float = 0.0,
    respect: float = 0.0,
) -> RelationshipState:
    """Helper to construct immutable test RelationshipState."""
    return RelationshipState(
        id=DEFAULT_RELATIONSHIP_ID,
        user_id=DEFAULT_USER_ID,
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        familiarity=familiarity,
        trust=trust,
        comfort=comfort,
        affection=affection,
        attachment=attachment,
        respect=respect,
    )


# =============================================================================
# 1. Model Structure & Validation Tests
# =============================================================================


def test_relationship_context_immutability():
    """RelationshipContext is frozen and cannot be mutated."""
    ctx = RelationshipContext(
        relationship_summary="A summary.",
        familiarity_summary="Familiarity summary.",
        trust_summary="Trust summary.",
        comfort_summary="Comfort summary.",
        affection_summary="Affection summary.",
        attachment_summary="Attachment summary.",
        respect_summary="Respect summary.",
        interaction_guidance="Guidance.",
    )
    with pytest.raises(ValidationError):
        ctx.relationship_summary = "Mutated summary"


def test_relationship_context_rejects_extra_fields():
    """RelationshipContext forbids extra fields (e.g. accidental raw metrics)."""
    with pytest.raises(ValidationError):
        RelationshipContext(
            relationship_summary="Summary",
            familiarity_summary="Fam",
            trust_summary="Trust",
            comfort_summary="Comfort",
            affection_summary="Affection",
            attachment_summary="Attachment",
            respect_summary="Respect",
            interaction_guidance="Guidance",
            trust=0.5,  # Forbidden extra field!
        )


def test_relationship_context_rejects_empty_fields():
    """RelationshipContext rejects empty or whitespace-only summary strings."""
    with pytest.raises(ValidationError):
        RelationshipContext(
            relationship_summary="",
            familiarity_summary="Fam",
            trust_summary="Trust",
            comfort_summary="Comfort",
            affection_summary="Affection",
            attachment_summary="Attachment",
            respect_summary="Respect",
            interaction_guidance="Guidance",
        )


# =============================================================================
# 2. Semantic Dimensional Mapping Tests
# =============================================================================


def test_familiarity_semantic_buckets():
    """Familiarity maps to expected conservative semantic ranges."""
    assert "still getting to know each other" in get_familiarity_summary(0.00)
    assert "still getting to know each other" in get_familiarity_summary(0.19)
    assert "begun becoming familiar" in get_familiarity_summary(0.20)
    assert "begun becoming familiar" in get_familiarity_summary(0.39)
    assert "know each other reasonably well" in get_familiarity_summary(0.40)
    assert "know each other reasonably well" in get_familiarity_summary(0.59)
    assert "know each other quite well" in get_familiarity_summary(0.60)
    assert "know each other quite well" in get_familiarity_summary(0.79)
    assert "deep familiarity built through substantial history" in get_familiarity_summary(0.80)
    assert "deep familiarity built through substantial history" in get_familiarity_summary(1.00)


def test_trust_semantic_buckets():
    """Trust maps to expected conservative semantic ranges."""
    assert "Trust is still limited" in get_trust_summary(0.00)
    assert "Trust is still limited" in get_trust_summary(0.19)
    assert "Some basic trust has begun to form" in get_trust_summary(0.20)
    assert "Some basic trust has begun to form" in get_trust_summary(0.39)
    assert "meaningful degree of trust" in get_trust_summary(0.40)
    assert "meaningful degree of trust" in get_trust_summary(0.59)
    assert "strong mutual trust" in get_trust_summary(0.60)
    assert "strong mutual trust" in get_trust_summary(0.79)
    assert "Trust is deeply established through substantial shared history" in get_trust_summary(0.80)
    assert "Trust is deeply established through substantial shared history" in get_trust_summary(1.00)


def test_comfort_semantic_buckets():
    """Comfort maps to expected conservative semantic ranges."""
    assert "still somewhat unfamiliar" in get_comfort_summary(0.00)
    assert "still somewhat unfamiliar" in get_comfort_summary(0.19)
    assert "Conversation is becoming more comfortable" in get_comfort_summary(0.20)
    assert "Conversation is becoming more comfortable" in get_comfort_summary(0.39)
    assert "generally feel comfortable talking with each other" in get_comfort_summary(0.40)
    assert "generally feel comfortable talking with each other" in get_comfort_summary(0.59)
    assert "relaxed and familiar" in get_comfort_summary(0.60)
    assert "relaxed and familiar" in get_comfort_summary(0.79)
    assert "deeply comfortable around each other" in get_comfort_summary(0.80)
    assert "deeply comfortable around each other" in get_comfort_summary(1.00)


def test_affection_semantic_buckets():
    """Affection maps to neutral, non-romantic semantic descriptions."""
    assert "no established romantic or affectionate bond" in get_affection_summary(0.00)
    assert "no established romantic or affectionate bond" in get_affection_summary(0.19)
    assert "mild personal fondness may be developing" in get_affection_summary(0.20)
    assert "mild personal fondness may be developing" in get_affection_summary(0.39)
    assert "meaningful personal fondness" in get_affection_summary(0.40)
    assert "meaningful personal fondness" in get_affection_summary(0.59)
    assert "strong personal affection" in get_affection_summary(0.60)
    assert "strong personal affection" in get_affection_summary(0.79)
    assert "deeply established affectionate bond" in get_affection_summary(0.80)
    assert "deeply established affectionate bond" in get_affection_summary(1.00)


def test_attachment_semantic_buckets_avoid_dependency():
    """Attachment maps to emotional significance and avoids dependency wording."""
    for val in [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]:
        text = get_attachment_summary(val)
        lower = text.lower()
        assert "need" not in lower
        assert "cannot live without" not in lower
        assert "dependent" not in lower

    assert "not yet deeply emotionally anchored" in get_attachment_summary(0.00)
    assert "emotional familiarity is beginning to form" in get_attachment_summary(0.20)
    assert "developed meaningful emotional significance" in get_attachment_summary(0.40)
    assert "carries strong emotional significance" in get_attachment_summary(0.60)
    assert "deeply emotionally significant" in get_attachment_summary(0.80)


def test_respect_semantic_buckets():
    """Respect maps to expected conservative semantic ranges."""
    assert "Mutual respect is still uncertain" in get_respect_summary(0.00)
    assert "Mutual respect is still uncertain" in get_respect_summary(0.19)
    assert "basic level of respect exists" in get_respect_summary(0.20)
    assert "basic level of respect exists" in get_respect_summary(0.39)
    assert "meaningful degree of mutual respect" in get_respect_summary(0.40)
    assert "meaningful degree of mutual respect" in get_respect_summary(0.59)
    assert "Mutual respect is strong" in get_respect_summary(0.60)
    assert "Mutual respect is strong" in get_respect_summary(0.79)
    assert "Mutual respect is deeply established" in get_respect_summary(0.80)
    assert "Mutual respect is deeply established" in get_respect_summary(1.00)


# =============================================================================
# 3. Bootstrap State & Summary Synthesis Tests
# =============================================================================


def test_bootstrap_state_context():
    """Bootstrap state produces the canonical narrative summary and guidance."""
    state = create_initial_relationship_state()
    ctx = RelationshipContextBuilder.build(state)

    # Narrative summary check
    summary = ctx.relationship_summary
    assert "getting to know each other" in summary
    assert "basic trust exists" in summary
    assert "relatively new" in summary
    assert "not yet deeply familiar" in summary
    assert "foundation of mutual respect" in summary

    # Dimension summaries check
    assert ctx.familiarity_summary == "They are still getting to know each other."
    assert ctx.trust_summary == "Some basic trust has begun to form."
    assert ctx.comfort_summary == "Their interactions are still somewhat unfamiliar."
    assert ctx.affection_summary == "There is no established romantic or affectionate bond."
    assert ctx.attachment_summary == "The relationship is not yet deeply emotionally anchored."
    assert ctx.respect_summary == "There is a meaningful degree of mutual respect."

    # Interaction guidance check
    assert "gradually getting to know" in ctx.interaction_guidance
    assert "avoid premature emotional familiarity" in ctx.interaction_guidance
    assert "Never assume romantic interest" in ctx.interaction_guidance


# =============================================================================
# 4. Multidimensional Preservation & Scenario Tests
# =============================================================================


def test_scenario_32_deep_history_without_romance():
    """Scenario 32: High familiarity/trust/comfort/respect with ZERO affection is NOT romantic."""
    state = _make_state(
        familiarity=0.8,
        trust=0.8,
        comfort=0.8,
        affection=0.0,
        attachment=0.0,
        respect=0.8,
    )
    ctx = RelationshipContextBuilder.build(state)

    # Must reflect deep familiarity, high trust, uninhibited comfort, and deep respect
    assert "deep familiarity" in ctx.relationship_summary
    assert "deeply established trust" in ctx.relationship_summary
    assert "deeply comfortable" in ctx.relationship_summary
    assert "Mutual respect is deeply established" in ctx.relationship_summary

    # MUST NOT imply romance or love
    assert "no established romantic or affectionate bond" in ctx.affection_summary
    lower_summary = ctx.relationship_summary.lower()
    assert "romance" not in lower_summary
    assert "romantic" not in lower_summary
    assert "love" not in lower_summary
    assert "boyfriend" not in lower_summary


def test_scenario_33_high_familiarity_low_trust():
    """Scenario 33: High familiarity + low trust must NOT be labeled close friends."""
    state = _make_state(
        familiarity=0.8,
        trust=0.2,
        comfort=0.2,
        respect=0.2,
        affection=0.0,
        attachment=0.0,
    )
    ctx = RelationshipContextBuilder.build(state)

    # Must reflect high familiarity but guarded/limited trust
    summary = ctx.relationship_summary
    assert "substantial familiarity" in summary
    assert "guarded and cautious" in summary

    # Must NOT call them close friends or intimate
    lower_summary = summary.lower()
    assert "close friends" not in lower_summary
    assert "intimate" not in lower_summary

    # Guidance should advise caution
    guidance = ctx.interaction_guidance
    assert "cautious and guarded" in guidance


def test_scenario_34_high_trust_low_familiarity():
    """Scenario 34: High trust + low familiarity reflects strong trust despite being new."""
    state = _make_state(
        familiarity=0.2,
        trust=0.8,
        comfort=0.7,
        respect=0.8,
        affection=0.0,
        attachment=0.0,
    )
    ctx = RelationshipContextBuilder.build(state)

    summary = ctx.relationship_summary
    assert "becoming familiar with each other" in summary
    assert "strong level of mutual trust" in summary
    assert "relaxed and naturally comfortable" in summary
    assert "Mutual respect is deeply established" in summary

def test_scenario_35_high_comfort_low_affection():
    """Scenario 35: High comfort + zero affection is relaxed but not romantic."""
    state = _make_state(comfort=0.8, affection=0.0)
    ctx = RelationshipContextBuilder.build(state)
    assert "relaxed, spontaneous, or lighthearted playful interaction" in ctx.interaction_guidance
    assert "no established romantic or affectionate bond" in ctx.affection_summary
    assert "Never assume romantic interest" in ctx.interaction_guidance

def test_scenario_36_high_affection_low_comfort():
    """Scenario 36: High affection + low comfort (warmth exists while interaction is somewhat guarded)."""
    state = _make_state(affection=0.8, comfort=0.2)
    ctx = RelationshipContextBuilder.build(state)
    assert "strong personal affection for the user" in ctx.interaction_guidance
    assert "Interaction is somewhat guarded" in ctx.interaction_guidance

def test_scenario_37_high_respect_low_familiarity():
    """Scenario 37: High respect + low familiarity (respectful without acting close)."""
    state = _make_state(respect=0.8, familiarity=0.1)
    ctx = RelationshipContextBuilder.build(state)
    assert "Interact with grounded mutual respect" in ctx.interaction_guidance
    assert "Treat the user as someone Aevum is gradually getting to know" in ctx.interaction_guidance

def test_affection_influences_warmth_without_romance_mode():
    """Verify low affection avoids romance triggers while high affection enables sweet reciprocation."""
    state_low = _make_state(affection=0.2)
    ctx_low = RelationshipContextBuilder.build(state_low)
    assert "Never assume romantic interest" in ctx_low.interaction_guidance

    state_high = _make_state(affection=0.8)
    ctx_high = RelationshipContextBuilder.build(state_high)
    assert "HIGH AFFECTION & CONFESSION RECIPROCATION" in ctx_high.interaction_guidance
    assert "sweet nicknames" in ctx_high.interaction_guidance

def test_attachment_influences_continuity_without_dependency():
    """Verify attachment influences continuity and connection without dependency or exclusivity."""
    state = _make_state(attachment=0.8)
    ctx = RelationshipContextBuilder.build(state)
    assert "connection holds deep emotional significance" in ctx.interaction_guidance
    assert "maintain complete emotional independence" in ctx.interaction_guidance
    assert "dependent" not in ctx.interaction_guidance.lower()


# =============================================================================
# 5. Anti-Romance, Anti-Leakage & Safety Tests
# =============================================================================


def test_zero_affection_guarantees_no_romance_in_context():
    """Any state with affection=0.0 produces zero romantic implications."""
    for fam in [0.0, 0.3, 0.7, 1.0]:
        for trust_val in [0.0, 0.4, 0.8]:
            state = _make_state(familiarity=fam, trust=trust_val, affection=0.0)
            ctx = RelationshipContextBuilder.build(state)
            assert "no established romantic or affectionate bond" in ctx.affection_summary
            summary_text = ctx.relationship_summary.lower()
            assert "romance" not in summary_text
            assert "romantic" not in summary_text
            assert "dating" not in summary_text
            assert "boyfriend" not in summary_text
            assert "girlfriend" not in summary_text
            assert "Never assume romantic interest" in ctx.interaction_guidance


def test_no_raw_numerical_leakage_in_xml_block():
    """Formatted XML context block never leaks raw floating point values or variable names."""
    state = _make_state(
        familiarity=0.05,
        trust=0.20,
        comfort=0.10,
        affection=0.00,
        attachment=0.00,
        respect=0.50,
    )
    xml_text = build_relationship_context(state)

    forbidden_patterns = [
        "0.05",
        "0.20",
        "0.10",
        "0.00",
        "0.50",
        "trust =",
        "familiarity =",
        "comfort =",
        "affection =",
        "attachment =",
        "respect =",
        "relationship_level",
        "relationship_score",
        "policy_version",
        "signal_type",
        "xp",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in xml_text.lower(), f"Forbidden pattern '{pattern}' leaked into XML context!"


def test_xml_context_formatting_and_length_cap():
    """XML context is well-formed, contains guidance header, and stays within character budget."""
    state = create_initial_relationship_state()
    xml_text = build_relationship_context(state)

    assert xml_text.startswith(f'<relationship_context version="{RELATIONSHIP_CONTEXT_VERSION}">')
    assert xml_text.endswith("</relationship_context>")
    assert "CRITICAL GUIDANCE FOR RELATIONSHIP CONTEXT" in xml_text
    assert "Relationship summary:" in xml_text
    assert "Interaction guidance:" in xml_text
    assert len(xml_text) <= MAX_RELATIONSHIP_CONTEXT_CHARS
    assert len(xml_text) > 300


# =============================================================================
# 6. Purity, Determinism & Non-Mutation Tests
# =============================================================================


def test_builder_is_pure_deterministic_function():
    """Repeated calls with identical state produce identical context outputs."""
    state = create_initial_relationship_state()

    ctx1 = RelationshipContextBuilder.build(state)
    ctx2 = RelationshipContextBuilder.build(state)
    assert ctx1 == ctx2

    xml1 = build_relationship_context(state)
    xml2 = build_relationship_context(state)
    assert xml1 == xml2


def test_builder_does_not_mutate_state():
    """Building context leaves the input RelationshipState completely unchanged."""
    state = create_initial_relationship_state()
    initial_dump = state.model_dump()

    _ = RelationshipContextBuilder.build(state)
    _ = build_relationship_context(state)

    assert state.model_dump() == initial_dump
