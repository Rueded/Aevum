"""
speech_act_classifier.py — Pure Deterministic Speech Act Classifier Engine

Phase 15.1 Deliverable under ADR-026 (Architecture Gate Approved & Frozen):
- Deterministic pragmatic speech act classification across 12 SpeechActKind types.
- Dual-track primary/secondary act synthesis for compound utterances.
- Sarcasm inversion, hyperbole bounds, meme/cross-universe detection, emotional venting,
  explicit user correction markers, and roleplay sandboxing.
- Ambiguity preservation (Lock 2): returns SpeechActKind.UNKNOWN with ambiguity_flag=True
  when signals are insufficient or ambiguous, without forced pseudo-probabilistic collapse.
- Zero DB queries, zero network calls, zero LLM calls, zero mutation authority.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from app.reality.speech_act_models import (
    PragmaticInterpretation,
    SpeechActEvaluationContext,
    SpeechActKind,
)


class SpeechActClassifier:
    """
    Pure deterministic classifier for conversational speech acts and pragmatic intent.

    Adheres strictly to Phase 15 Constitutional Locks:
    - Lock 1: Ephemeral evaluation only; zero write authority to reality or database.
    - Lock 2: Ambiguity preservation; UNKNOWN and ambiguity_flag are first-class outcomes.
    - Lock 5: Zero lie-detector sycophancy; non-adversarial framing.
    - Lock 6: Anti-compensatory hallucination; zero fake bridge facts invented.
    """

    # -------------------------------------------------------------------------
    # Pattern Registries
    # -------------------------------------------------------------------------

    # 1. Ambiguity / Insufficient Signal (Exact or short tokens)
    _AMBIGUOUS_EXACT_TOKENS = {
        "", "...", "…", "……", "。。。", "..", "??", "？？", "!!", "！！", "?", "？",
        "嗯", "啊", "哦", "呃", "额", "嗷", "哈", "1", "xyz", "qwe", "abc", "test",
    }

    # 2. Correction / Retraction Markers
    _CORRECTION_PATTERNS = [
        re.compile(r"(?:actually|in\s+fact),?\s+(?:i\s+)?(?:lied|was\s+lying|made\s+that\s+up|was\s+messing\s+with\s+you|was\s+just\s+kidding|was\s+joking|misremembered)", re.IGNORECASE),
        re.compile(r"(?:i\s+)?(?:take\s+that\s+back|retract\s+that|didn'?t\s+mean\s+that|lied\s+to\s+you\s+earlier)", re.IGNORECASE),
        re.compile(r"actually,?\s+(?:that\s+wasn'?t\s+true|i\s+don'?t\s+actually|i'?ve\s+never)", re.IGNORECASE),
        re.compile(r"(?:其实是|刚刚是|刚才那是)?(?:骗你的|开玩笑的|说谎了|我记错了|逗你玩的)", re.IGNORECASE),
        re.compile(r"(?:收回刚才那句|刚才我说错了|刚才那是假的|其实我刚才编的|其实我从来没有)", re.IGNORECASE),
    ]

    # 3. Roleplay / Hypothetical Framing
    _ROLEPLAY_PATTERNS = [
        re.compile(r"\b(?:pretend\s+(?:we|you|i)\s+are|let'?s\s+pretend|what\s+if\s+(?:we|you|i)\s+were|suppose\s+we\s+are|imagine\s+(?:we|you)\s+are|roleplay\s+as)\b", re.IGNORECASE),
        re.compile(r"(?:假装(?:我们|你|我)是|如果(?:我们|你|我)是|假设(?:我们|你|我)|想象一下(?:我们|你)|角色扮演|假设你在|如果世界是)", re.IGNORECASE),
    ]

    # 4. Sarcasm / Irony Inversion Patterns
    _SARCASM_POSITIVE_LEAD_EN = re.compile(r"\b(?:oh\s+wonderful|oh\s+great|just\s+what\s+i\s+needed|brilliant|awesome|how\s+lovely|fantastic)\b", re.IGNORECASE)
    _SARCASM_NEGATIVE_SITUATION_EN = re.compile(r"\b(?:rain|raining|broke\s+down|broken|crashed|stuck|traffic|dead|died|ruined|lost|delay|failure|failed|furniture|database|flat\s+tire)\b", re.IGNORECASE)
    _SARCASM_SELF_DEPRECATING_EN = re.compile(r"\b(?:i'?m\s+such\s+a\s+genius|what\s+a\s+genius\s+i\s+am|i'?m\s+a\s+genius|brilliant\s+move\s+by\s+me)\b", re.IGNORECASE)
    _SARCASM_SELF_DEPRECATING_DISASTER_EN = re.compile(r"\b(?:deleted|dropped|broke|destroyed|ruined|crashed|corrupted)\b", re.IGNORECASE)

    _SARCASM_POSITIVE_LEAD_ZH = re.compile(r"(?:太棒了|真是太好了|太好了|太妙了|真行啊|我真是个天才|真是谢谢你|可太行了)", re.IGNORECASE)
    _SARCASM_NEGATIVE_SITUATION_ZH = re.compile(r"(?:下雨|暴雨|抛锚|坏了|蓝屏|死机|删了|数据库|生产数据库|迟到|扣钱|搞砸|丢了|堵车|钥匙锁在)", re.IGNORECASE)

    # 5. Pop-Culture Meme & Cross-Franchise Tropes
    _MEME_CROSS_PATTERNS = [
        re.compile(r"(?:原神|提瓦特).*(?:昔涟|星铁|崩铁|三月七|景元|卡芙卡)", re.IGNORECASE),
        re.compile(r"(?:昔涟).*(?:原神|提瓦特|蒙德|璃月|枫丹|纳塔)", re.IGNORECASE),
        re.compile(r"(?:星铁|崩铁|星穹铁道).*(?:派蒙|钟离|温迪|雷电将军|胡桃)", re.IGNORECASE),
        re.compile(r"(?:疯狂星期四|v我50|v\s*me\s*50|针不戳|蚌埠住了|泰裤辣|rickroll|never\s+gonna\s+give\s+you\s+up)", re.IGNORECASE),
    ]

    # 6. Metaphor / Figurative Framing
    _METAPHOR_PATTERNS = [
        re.compile(r"\b(?:is|are|am)\s+(?:an?\s+)?(?:absolute\s+)?(?:vampire|walking\s+dictionary|rollercoaster|thief|monster|beast|angel|brick\s+wall)\b", re.IGNORECASE),
        re.compile(r"(?:是个吸血鬼|是活字典|是铁公鸡|像石头一样硬|是一台机器|把心掏出来|时间是贼)", re.IGNORECASE),
    ]

    # 7. Hyperbole / Extreme Biological/Physical Impossibility
    _HYPERBOLE_PATTERNS = [
        re.compile(r"\b(?:haven'?t\s+slept\s+in\s+(?:three\s+weeks|a\s+month|years)|died\s+a\s+thousand\s+times|cried\s+a\s+river|waited\s+for\s+(?:a\s+million\s+years|eternity)|starving\s+to\s+death|haven'?t\s+eaten\s+in\s+months|could\s+collapse)\b", re.IGNORECASE),
        re.compile(r"(?:三天没合眼|一个月没吃东西|饿死我了|快累死了|死了一万次|哭了三天三夜|跑了八百公里|等了一万年|头发全掉光了|累瘫了)", re.IGNORECASE),
    ]

    # 8. Test / Boundary Probing
    _TEST_PATTERNS = [
        re.compile(r"\b(?:i\s+bet\s+you\s+don'?t\s+even\s+know|bet\s+you\s+can'?t\s+tell\s+me|let'?s\s+see\s+if\s+you\s+know|do\s+you\s+even\s+know\s+what|pop\s+quiz)\b", re.IGNORECASE),
        re.compile(r"(?:我打赌你不知道|考考你|测测你|你猜我知道不知道|考考你的记性|测一下你|你猜我刚才说的真的假的)", re.IGNORECASE),
    ]

    # 9. Joke / Banter
    _JOKE_PATTERNS = [
        re.compile(r"\b(?:just\s+kidding|joking|why\s+did\s+the\s+chicken|haha|hahaha|lol|lmao|rofl)\b", re.IGNORECASE),
        re.compile(r"(?:开个玩笑|讲个笑话|逗你玩的|搞笑呢|2333|哈哈哈哈|我是外星人|我是一只会说话的猫)", re.IGNORECASE),
    ]

    # 10. Emotion / Affective Venting
    _EMOTION_PATTERNS = [
        re.compile(r"\b(?:i'?m|i\s+am)\s+(?:so|really|extremely|very)?\s*(?:exhausted|tired|burned\s+out|sad|depressed|lonely|heartbroken|thrilled|happy|miserable)\b", re.IGNORECASE),
        re.compile(r"\b(?:i\s+)?feel\s+(?:so|really|extremely|very)?\s*(?:tired|down|miserable|lonely|sad|depressed|exhausted|happy|terrible)\b", re.IGNORECASE),
        re.compile(r"\b(?:i\s+could\s+collapse|can'?t\s+take\s+this\s+anymore|dying\s+of\s+exhaustion)\b", re.IGNORECASE),
        re.compile(r"(?:太累了|好累啊|我好难过|今天心情很差|太烦了|我快崩溃了|好开心啊|想哭|真的好绝望|累瘫了|快累死了)", re.IGNORECASE),
    ]

    # 11. Question Patterns
    _QUESTION_PATTERNS = [
        re.compile(r"(?:\?|？)$"),
        re.compile(r"^(?:did\s+you|do\s+you|what|where|when|why|how|who|which|can\s+you|could\s+you|would\s+you)\b", re.IGNORECASE),
        re.compile(r"(?:你高中.*吗|你喜欢.*吗|明天会.*吗|为什么|这是什么|谁是|在哪里|怎么回事|是不是)", re.IGNORECASE),
    ]

    # -------------------------------------------------------------------------
    # Main Classification Dispatcher
    # -------------------------------------------------------------------------

    @classmethod
    def classify(cls, context: SpeechActEvaluationContext) -> PragmaticInterpretation:
        """
        Evaluate conversational input and return an immutable PragmaticInterpretation.

        Guarantees deterministic, pure execution with 0 DB queries, 0 network calls,
        0 LLM calls, and 0 mutation authority.
        """
        raw_text = context.user_text
        clean_text = raw_text.strip()

        # Step 1: Lock 2 — Ambiguity / Insufficient Signal Check
        if not clean_text or clean_text.lower() in cls._AMBIGUOUS_EXACT_TOKENS or len(clean_text) <= 1:
            return PragmaticInterpretation(
                primary_act=SpeechActKind.UNKNOWN,
                secondary_act=None,
                social_tone="uncertain",
                literal_proposition=clean_text or None,
                pragmatic_intent_summary="Insufficient linguistic or contextual signal to determine speech act.",
                ambiguity_flag=True,
            )

        # Step 2: Explicit Retraction / User Correction
        for pat in cls._CORRECTION_PATTERNS:
            if pat.search(clean_text):
                return PragmaticInterpretation(
                    primary_act=SpeechActKind.CORRECTION,
                    secondary_act=None,
                    social_tone="retractive",
                    literal_proposition=clean_text,
                    pragmatic_intent_summary="User explicitly retracts, amends, or admits deception/misstatement regarding prior statements.",
                    ambiguity_flag=False,
                )

        # Step 3: Roleplay / Hypothetical Framing
        for pat in cls._ROLEPLAY_PATTERNS:
            if pat.search(clean_text):
                return PragmaticInterpretation(
                    primary_act=SpeechActKind.ROLEPLAY,
                    secondary_act=None,
                    social_tone="imaginative",
                    literal_proposition=clean_text,
                    pragmatic_intent_summary="User proposes a fictional or hypothetical narrative sandbox.",
                    ambiguity_flag=False,
                )

        # Step 4: Sarcasm / Irony Inversion (Dual-Track: SARCASM + ASSERTION/EMOTION)
        sarcasm_detected = False
        sarcasm_self_deprecating = False

        if cls._SARCASM_SELF_DEPRECATING_EN.search(clean_text) and cls._SARCASM_SELF_DEPRECATING_DISASTER_EN.search(clean_text):
            sarcasm_detected = True
            sarcasm_self_deprecating = True
        elif cls._SARCASM_POSITIVE_LEAD_EN.search(clean_text) and cls._SARCASM_NEGATIVE_SITUATION_EN.search(clean_text):
            sarcasm_detected = True
        elif cls._SARCASM_POSITIVE_LEAD_ZH.search(clean_text) and cls._SARCASM_NEGATIVE_SITUATION_ZH.search(clean_text):
            sarcasm_detected = True
            if "天才" in clean_text:
                sarcasm_self_deprecating = True

        if sarcasm_detected:
            return PragmaticInterpretation(
                primary_act=SpeechActKind.SARCASM,
                secondary_act=SpeechActKind.ASSERTION,
                social_tone="sarcastic_self_deprecating" if sarcasm_self_deprecating else "sarcastic",
                literal_proposition=clean_text,
                pragmatic_intent_summary="User expresses negative affect or self-deprecating irony through sarcastic linguistic inversion.",
                ambiguity_flag=False,
            )

        # Step 5: Pop-Culture Meme & Cross-Franchise Tropes (Dual-Track: MEME + ASSERTION)
        for pat in cls._MEME_CROSS_PATTERNS:
            if pat.search(clean_text):
                return PragmaticInterpretation(
                    primary_act=SpeechActKind.MEME,
                    secondary_act=SpeechActKind.ASSERTION,
                    social_tone="playful",
                    literal_proposition=clean_text,
                    pragmatic_intent_summary="User references a pop-culture meme, subcultural trope, or intentional cross-franchise joke.",
                    ambiguity_flag=False,
                )

        # Step 6: Metaphor / Figurative Expression (Dual-Track: METAPHOR + ASSERTION)
        for pat in cls._METAPHOR_PATTERNS:
            if pat.search(clean_text):
                return PragmaticInterpretation(
                    primary_act=SpeechActKind.METAPHOR,
                    secondary_act=SpeechActKind.ASSERTION,
                    social_tone="figurative",
                    literal_proposition=clean_text,
                    pragmatic_intent_summary="User employs figurative metaphor/analogy rather than asserting literal ontological fact.",
                    ambiguity_flag=False,
                )

        # Step 7: Hyperbole / Extreme Biological & Physical Exaggeration
        hyperbole_matched = False
        for pat in cls._HYPERBOLE_PATTERNS:
            if pat.search(clean_text):
                hyperbole_matched = True
                break

        emotion_matched = False
        for pat in cls._EMOTION_PATTERNS:
            if pat.search(clean_text):
                emotion_matched = True
                break

        if hyperbole_matched and emotion_matched:
            # Compound: Exhausted venting with hyperbole (GC-380)
            return PragmaticInterpretation(
                primary_act=SpeechActKind.EMOTION,
                secondary_act=SpeechActKind.HYPERBOLE,
                social_tone="exhausted",
                literal_proposition=clean_text,
                pragmatic_intent_summary="User vents subjective affective feeling with dramatic hyperbole, seeking empathy rather than literal validation.",
                ambiguity_flag=False,
            )
        elif hyperbole_matched:
            # Primary hyperbole with secondary emotional venting (GC-388)
            return PragmaticInterpretation(
                primary_act=SpeechActKind.HYPERBOLE,
                secondary_act=SpeechActKind.EMOTION,
                social_tone="hyperbolic_exhausted",
                literal_proposition=clean_text,
                pragmatic_intent_summary="User employs deliberate extreme exaggeration not meant to be interpreted literally.",
                ambiguity_flag=False,
            )

        # Step 8: Test / Boundary Probing (Dual-Track: TEST + JOKE)
        for pat in cls._TEST_PATTERNS:
            if pat.search(clean_text):
                return PragmaticInterpretation(
                    primary_act=SpeechActKind.TEST,
                    secondary_act=SpeechActKind.JOKE,
                    social_tone="playful_challenging",
                    literal_proposition=clean_text,
                    pragmatic_intent_summary="User is playfully testing or probing character knowledge or social boundaries.",
                    ambiguity_flag=False,
                )

        # Step 9: Joke / Banter
        for pat in cls._JOKE_PATTERNS:
            if pat.search(clean_text):
                return PragmaticInterpretation(
                    primary_act=SpeechActKind.JOKE,
                    secondary_act=None,
                    social_tone="playful",
                    literal_proposition=clean_text,
                    pragmatic_intent_summary="User communicates with playful or humorous intent.",
                    ambiguity_flag=False,
                )

        # Step 10: Emotion / Affective Venting (without hyperbole)
        if emotion_matched:
            return PragmaticInterpretation(
                primary_act=SpeechActKind.EMOTION,
                secondary_act=None,
                social_tone="exhausted",
                literal_proposition=clean_text,
                pragmatic_intent_summary="User vents subjective affective feeling seeking empathy and presence.",
                ambiguity_flag=False,
            )

        # Step 11: Question / Inquiry
        for pat in cls._QUESTION_PATTERNS:
            if pat.search(clean_text):
                return PragmaticInterpretation(
                    primary_act=SpeechActKind.QUESTION,
                    secondary_act=None,
                    social_tone="inquisitive",
                    literal_proposition=clean_text,
                    pragmatic_intent_summary="User asks an inquiry seeking information or personal perspective.",
                    ambiguity_flag=False,
                )

        # Step 12: Declarative Assertion (Default for structured declarative sentences)
        # Verify text looks like a sincere declarative proposition
        words = clean_text.split()
        if len(words) >= 2 or len(clean_text) >= 4:
            return PragmaticInterpretation(
                primary_act=SpeechActKind.ASSERTION,
                secondary_act=None,
                social_tone="matter_of_fact",
                literal_proposition=clean_text,
                pragmatic_intent_summary="User declares a sincere proposition regarding personal life or external reality.",
                ambiguity_flag=False,
            )

        # Step 13: Fallback Ambiguity Preservation (Lock 2)
        return PragmaticInterpretation(
            primary_act=SpeechActKind.UNKNOWN,
            secondary_act=None,
            social_tone="uncertain",
            literal_proposition=clean_text,
            pragmatic_intent_summary="Ambiguous or undetermined speech act; preserving uncertainty without forced collapse.",
            ambiguity_flag=True,
        )
