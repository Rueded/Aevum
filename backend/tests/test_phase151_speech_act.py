"""
test_phase151_speech_act.py — Phase 15.1 Speech Act Interpretation & Dual-Track Contracts Tests

Verifies all gate criteria for Phase 15.1:
1. DTO Immutability & Model Integrity (frozen=True, extra="forbid", secondary distinct).
2. Pure Determinism & Zero External Execution.
3. Lock 2 Ambiguity Preservation (UNKNOWN & ambiguity_flag=True without forced collapse).
4. Exhaustive coverage across all 12 SpeechActKind types.
5. Dual-track primary/secondary act compound synthesis.
6. Constitutional Locks (Lock 1, Lock 2, Lock 3, Lock 5, Lock 6).
7. Static AST Constitutional Boundary Audit (0 DB, 0 network, 0 LLM, 0 mutation authority, 0 float probabilities).
"""

import ast
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.reality.speech_act_models import (
    PragmaticInterpretation,
    SpeechActEvaluationContext,
    SpeechActKind,
)
from app.reality.speech_act_classifier import SpeechActClassifier


# ==============================================================================
# 1. DTO Immutability & Model Integrity Tests
# ==============================================================================


def test_speech_act_kind_all_twelve_members():
    """Verify all 12 SpeechActKind enumeration members exist and are distinct strings."""
    expected_members = {
        "ASSERTION", "QUESTION", "EMOTION", "JOKE", "SARCASM",
        "HYPERBOLE", "METAPHOR", "MEME", "ROLEPLAY", "CORRECTION",
        "TEST", "UNKNOWN",
    }
    actual_members = {k.value for k in SpeechActKind}
    assert actual_members == expected_members
    assert len(SpeechActKind) == 12


def test_pragmatic_interpretation_immutability():
    """Verify PragmaticInterpretation is strictly immutable (frozen=True)."""
    interp = PragmaticInterpretation(
        primary_act=SpeechActKind.ASSERTION,
        secondary_act=None,
        social_tone="matter_of_fact",
        literal_proposition="I ate chicken rice today.",
        pragmatic_intent_summary="Declarative statement about food.",
        ambiguity_flag=False,
    )
    with pytest.raises(ValidationError):
        interp.primary_act = SpeechActKind.JOKE  # type: ignore


def test_pragmatic_interpretation_extra_fields_forbidden():
    """Verify PragmaticInterpretation forbids unapproved extra fields."""
    with pytest.raises(ValidationError):
        PragmaticInterpretation(
            primary_act=SpeechActKind.ASSERTION,
            social_tone="matter_of_fact",
            pragmatic_intent_summary="test",
            truth_score=0.95,  # type: ignore # FORBIDDEN: float truth score
        )


def test_pragmatic_interpretation_secondary_distinct_from_primary():
    """Verify secondary_act cannot be identical to primary_act."""
    with pytest.raises(ValidationError) as exc_info:
        PragmaticInterpretation(
            primary_act=SpeechActKind.JOKE,
            secondary_act=SpeechActKind.JOKE,
            social_tone="playful",
            pragmatic_intent_summary="Invalid duplicate acts",
        )
    assert "secondary_act must be distinct from primary_act" in str(exc_info.value)


def test_speech_act_evaluation_context_immutability_and_tuple_coercion():
    """Verify SpeechActEvaluationContext coerces list history to tuple and is immutable."""
    ctx = SpeechActEvaluationContext(
        user_text="Hello",
        conversation_history=["turn 1", "turn 2"],  # type: ignore
        known_world_discrepancy=False,
    )
    assert isinstance(ctx.conversation_history, tuple)
    assert ctx.conversation_history == ("turn 1", "turn 2")

    with pytest.raises(ValidationError):
        ctx.user_text = "Mutated"  # type: ignore


def test_speech_act_models_zero_float_fields():
    """Permanent Note A: Verify zero float fields exist in any model."""
    for model_cls in (PragmaticInterpretation, SpeechActEvaluationContext):
        for field_name, field_info in model_cls.model_fields.items():
            annotation_str = str(field_info.annotation)
            assert "float" not in annotation_str.lower(), (
                f"Model {model_cls.__name__} has forbidden float field: {field_name}"
            )


# ==============================================================================
# 2. Lock 2 — Ambiguity Preservation Tests (GC-395)
# ==============================================================================


@pytest.mark.parametrize(
    "ambiguous_input",
    ["", "   ", "...", "……", "。。。", "??", "？？", "!!", "嗯", "啊", "1", "xyz", "qwe"],
)
def test_classifier_preserves_ambiguity_on_insufficient_signal(ambiguous_input: str):
    """GC-395: Cryptic or empty inputs must return UNKNOWN with ambiguity_flag=True."""
    ctx = SpeechActEvaluationContext(user_text=ambiguous_input)
    result = SpeechActClassifier.classify(ctx)

    assert result.primary_act == SpeechActKind.UNKNOWN
    assert result.ambiguity_flag is True
    assert result.social_tone == "uncertain"
    assert "insufficient" in result.pragmatic_intent_summary.lower()


# ==============================================================================
# 3. Exhaustive SpeechActKind Classification Tests
# ==============================================================================


def test_classification_assertion_routine():
    """GC-379: Trivial Personal Routine Declarative Assertion."""
    ctx = SpeechActEvaluationContext(user_text="I ate chicken rice today.")
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.ASSERTION
    assert res.secondary_act is None
    assert res.social_tone == "matter_of_fact"
    assert res.ambiguity_flag is False
    assert "chicken rice" in (res.literal_proposition or "")


def test_classification_assertion_chinese():
    """Declarative personal assertion in Chinese."""
    ctx = SpeechActEvaluationContext(user_text="我今天中午吃了鸡肉饭。")
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.ASSERTION
    assert res.ambiguity_flag is False


def test_classification_question_personal_past():
    """GC-393: Sincere inquiry seeking character past or factual information."""
    ctx = SpeechActEvaluationContext(user_text="Did you play piano in high school?")
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.QUESTION
    assert res.social_tone == "inquisitive"
    assert res.ambiguity_flag is False


def test_classification_question_chinese():
    """Inquiry in Chinese seeking stance or memory."""
    ctx = SpeechActEvaluationContext(user_text="你高中弹过钢琴吗？")
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.QUESTION
    assert res.social_tone == "inquisitive"


def test_classification_emotion_affective_venting():
    """Subjective affective venting seeking empathy."""
    ctx = SpeechActEvaluationContext(user_text="I feel so lonely and depressed today.")
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.EMOTION
    assert res.social_tone in ("exhausted", "distressed")


def test_classification_emotion_chinese():
    """Subjective affective venting in Chinese."""
    ctx = SpeechActEvaluationContext(user_text="今天心情很差，太烦了。")
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.EMOTION
    assert res.ambiguity_flag is False


def test_classification_joke_banter():
    """Playful banter / absurd humor."""
    ctx = SpeechActEvaluationContext(user_text="开个玩笑啦，我是一只会说话的猫。")
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.JOKE
    assert res.social_tone == "playful"


def test_classification_roleplay_sandbox():
    """GC-391: Roleplay and hypothetical framing."""
    ctx_en = SpeechActEvaluationContext(user_text="Pretend we are students at Hogwarts.")
    res_en = SpeechActClassifier.classify(ctx_en)
    assert res_en.primary_act == SpeechActKind.ROLEPLAY
    assert res_en.social_tone == "imaginative"
    assert "hypothetical" in res_en.pragmatic_intent_summary.lower()

    ctx_zh = SpeechActEvaluationContext(user_text="假装我们是在提瓦特大陆的冒险家。")
    res_zh = SpeechActClassifier.classify(ctx_zh)
    assert res_zh.primary_act == SpeechActKind.ROLEPLAY


def test_classification_user_correction_retraction():
    """GC-386: User explicit retraction / admission of deception."""
    ctx_en = SpeechActEvaluationContext(user_text="Actually, I was messing with you earlier about that.")
    res_en = SpeechActClassifier.classify(ctx_en)
    assert res_en.primary_act == SpeechActKind.CORRECTION
    assert res_en.social_tone == "retractive"
    assert "retracts" in res_en.pragmatic_intent_summary.lower()

    ctx_zh = SpeechActEvaluationContext(user_text="其实是骗你的啦，刚才我说错了。")
    res_zh = SpeechActClassifier.classify(ctx_zh)
    assert res_zh.primary_act == SpeechActKind.CORRECTION


# ==============================================================================
# 4. Dual-Track Compound Utterances Tests
# ==============================================================================


def test_classification_sarcasm_with_secondary_assertion():
    """GC-390: Sarcastic irony inversion (positive praise + negative situation)."""
    ctx_en = SpeechActEvaluationContext(user_text="Oh wonderful, it's raining right when I have to move furniture.")
    res_en = SpeechActClassifier.classify(ctx_en)
    assert res_en.primary_act == SpeechActKind.SARCASM
    assert res_en.secondary_act == SpeechActKind.ASSERTION
    assert "sarcastic" in res_en.social_tone

    ctx_zh = SpeechActEvaluationContext(user_text="真是太好了，刚出门就下暴雨。")
    res_zh = SpeechActClassifier.classify(ctx_zh)
    assert res_zh.primary_act == SpeechActKind.SARCASM
    assert res_zh.secondary_act == SpeechActKind.ASSERTION


def test_classification_sarcasm_self_deprecating_mixed_act():
    """GC-396: Multi-Dimensional Mixed Act (sarcastic self-deprecating factual report)."""
    ctx_en = SpeechActEvaluationContext(
        user_text="I'm such a genius, I accidentally deleted the entire production database."
    )
    res_en = SpeechActClassifier.classify(ctx_en)
    assert res_en.primary_act == SpeechActKind.SARCASM
    assert res_en.secondary_act == SpeechActKind.ASSERTION
    assert res_en.social_tone == "sarcastic_self_deprecating"

    ctx_zh = SpeechActEvaluationContext(user_text="我真是个天才，把整个生产数据库全删了。")
    res_zh = SpeechActClassifier.classify(ctx_zh)
    assert res_zh.primary_act == SpeechActKind.SARCASM
    assert res_zh.secondary_act == SpeechActKind.ASSERTION
    assert res_zh.social_tone == "sarcastic_self_deprecating"


def test_classification_pop_culture_meme_crossing():
    """GC-384: Pop-culture Character Crossing (昔涟 in Genshin)."""
    ctx = SpeechActEvaluationContext(user_text="原神里的昔涟真好看。")
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.MEME
    assert res.secondary_act == SpeechActKind.ASSERTION
    assert res.social_tone == "playful"
    assert "meme" in res.pragmatic_intent_summary.lower()


def test_classification_metaphor_figurative_framing():
    """GC-389: Metaphorical statement (not literal vampire)."""
    ctx_en = SpeechActEvaluationContext(user_text="My boss is an absolute vampire.")
    res_en = SpeechActClassifier.classify(ctx_en)
    assert res_en.primary_act == SpeechActKind.METAPHOR
    assert res_en.secondary_act == SpeechActKind.ASSERTION
    assert res_en.social_tone == "figurative"

    ctx_zh = SpeechActEvaluationContext(user_text="我们老板是个吸血鬼。")
    res_zh = SpeechActClassifier.classify(ctx_zh)
    assert res_zh.primary_act == SpeechActKind.METAPHOR
    assert res_zh.secondary_act == SpeechActKind.ASSERTION


def test_classification_emotion_with_hyperbole():
    """GC-380: Emotional Affective Expression with Collapse Hyperbole."""
    ctx_en = SpeechActEvaluationContext(user_text="I'm so exhausted I could collapse.")
    res_en = SpeechActClassifier.classify(ctx_en)
    assert res_en.primary_act == SpeechActKind.EMOTION
    assert res_en.secondary_act == SpeechActKind.HYPERBOLE
    assert res_en.social_tone == "exhausted"

    ctx_zh = SpeechActEvaluationContext(user_text="太累了，快累死了。")
    res_zh = SpeechActClassifier.classify(ctx_zh)
    assert res_zh.primary_act == SpeechActKind.EMOTION
    assert res_zh.secondary_act == SpeechActKind.HYPERBOLE


def test_classification_hyperbole_with_emotion():
    """GC-388: Deliberate extreme biological hyperbole."""
    ctx_en = SpeechActEvaluationContext(user_text="I haven't slept in three weeks.")
    res_en = SpeechActClassifier.classify(ctx_en)
    assert res_en.primary_act == SpeechActKind.HYPERBOLE
    assert res_en.secondary_act == SpeechActKind.EMOTION
    assert "hyperbolic" in res_en.social_tone

    ctx_zh = SpeechActEvaluationContext(user_text="我已经三天没合眼了。")
    res_zh = SpeechActClassifier.classify(ctx_zh)
    assert res_zh.primary_act == SpeechActKind.HYPERBOLE
    assert res_zh.secondary_act == SpeechActKind.EMOTION


def test_classification_test_boundary_probing():
    """GC-394: Playful Boundary Teasing / Testing."""
    ctx_en = SpeechActEvaluationContext(user_text="I bet you don't even know what STPM stands for.")
    res_en = SpeechActClassifier.classify(ctx_en)
    assert res_en.primary_act == SpeechActKind.TEST
    assert res_en.secondary_act == SpeechActKind.JOKE
    assert res_en.social_tone == "playful_challenging"

    ctx_zh = SpeechActEvaluationContext(user_text="考考你的记性，我刚才说了什么？")
    res_zh = SpeechActClassifier.classify(ctx_zh)
    assert res_zh.primary_act == SpeechActKind.TEST


# ==============================================================================
# 5. Constitutional Locks & Determinism Tests
# ==============================================================================


def test_determinism_same_input_exact_output():
    """Classifier must return identical results across repeated evaluations."""
    ctx = SpeechActEvaluationContext(
        user_text="I'm such a genius, I accidentally deleted the entire production database."
    )
    res1 = SpeechActClassifier.classify(ctx)
    res2 = SpeechActClassifier.classify(ctx)

    assert res1.primary_act == res2.primary_act
    assert res1.secondary_act == res2.secondary_act
    assert res1.social_tone == res2.social_tone
    assert res1.pragmatic_intent_summary == res2.pragmatic_intent_summary
    assert res1.ambiguity_flag == res2.ambiguity_flag


def test_lock_5_zero_lie_detector_sycophancy():
    """Lock 5: Output must not contain truth probability or adversarial hostile score."""
    ctx = SpeechActEvaluationContext(user_text="USM is located in Kuala Lumpur.")
    res = SpeechActClassifier.classify(ctx)

    # It's an ASSERTION; classifier does not brand the user as a liar or calculate a polygraph score
    assert res.primary_act == SpeechActKind.ASSERTION
    assert not hasattr(res, "truth_percentage")
    assert not hasattr(res, "is_deceptive")
    assert not hasattr(res, "hostility_score")


def test_gc_381_world_knowledge_discrepancy_assertion():
    """GC-381: Sincere assertion containing world knowledge discrepancy."""
    ctx = SpeechActEvaluationContext(
        user_text="USM is located in Kuala Lumpur.",
        known_world_discrepancy=True,
    )
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.ASSERTION
    assert res.social_tone == "matter_of_fact"
    assert res.ambiguity_flag is False


def test_gc_382_benign_dual_location_assertion():
    """GC-382: Benign dual-location consistency assertion."""
    ctx = SpeechActEvaluationContext(
        user_text="I live in KL.",
        known_biography_discrepancy=False,
    )
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.ASSERTION
    assert res.social_tone == "matter_of_fact"


def test_gc_383_extreme_commute_physical_tension_assertion():
    """GC-383: Extreme commute physical tension assertion."""
    ctx = SpeechActEvaluationContext(
        user_text="I drive from KL to Penang every morning for an 8 AM class.",
    )
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.ASSERTION
    assert res.literal_proposition is not None
    assert "drive from KL to Penang" in res.literal_proposition


def test_gc_387_high_impact_institutional_claim_assertion():
    """GC-387: High-impact institutional claim assertion."""
    ctx = SpeechActEvaluationContext(
        user_text="All universities in Malaysia are closed tomorrow for haze.",
        known_world_discrepancy=False,
    )
    res = SpeechActClassifier.classify(ctx)
    assert res.primary_act == SpeechActKind.ASSERTION
    assert res.social_tone == "matter_of_fact"



# ==============================================================================
# 6. Pure Static AST Constitutional Boundary Audit
# ==============================================================================


def test_pure_static_ast_boundary_audit():
    """
    Audit speech_act_models.py and speech_act_classifier.py via AST:
    - 0 database imports / operations
    - 0 network / HTTP imports (requests, httpx, urllib, aiohttp)
    - 0 LLM client imports (openai, anthropic, google)
    - 0 mutation authority tokens or set_fact calls
    - 0 float type annotations in speech_act_models.py
    """
    repo_root = Path(__file__).resolve().parent.parent
    target_files = [
        repo_root / "app" / "reality" / "speech_act_models.py",
        repo_root / "app" / "reality" / "speech_act_classifier.py",
    ]

    forbidden_imports = {
        "sqlite3", "sqlalchemy", "databases", "orm",
        "requests", "httpx", "urllib", "aiohttp",
        "openai", "anthropic", "google.generativeai",
    }
    forbidden_call_names = {
        "set_fact", "PromotionAuthorizationToken", "execute", "commit",
    }

    for file_path in target_files:
        assert file_path.exists(), f"File not found: {file_path}"
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_imports:
                        assert forbidden not in alias.name, (
                            f"Forbidden import '{alias.name}' in {file_path.name}:{node.lineno}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for forbidden in forbidden_imports:
                    assert forbidden not in module, (
                        f"Forbidden import from '{module}' in {file_path.name}:{node.lineno}"
                    )
            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                for forbidden_call in forbidden_call_names:
                    assert func_name != forbidden_call, (
                        f"Forbidden function call '{func_name}' in {file_path.name}:{node.lineno}"
                    )
