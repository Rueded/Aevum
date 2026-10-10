"""Output Boundary and Response Integrity Guard for Aevum V2.

Guarantees:
- Enforces strict character speech envelope extraction (<character_response><character_speech>...).
- Filters out internal chain-of-thought, reasoning tokens, and meta-instructions.
- Detects instruction leaks, prompt echoes, AI disclaimers, and JSON tool payloads.
- Ensures contaminated text NEVER reaches SQLite persistence, WebSockets, or UI.
- Emits character-grounded authentic fallback dialogue upon contamination.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Default character-grounded conversational fallback
DEFAULT_FALLBACK_SPEECH = "...Wait. I completely lost my train of thought for a second."

# Structural speech envelope regex patterns
_TURN_ENVELOPE_PATTERN = re.compile(
    r"<character_turn>.*?<character_speech>(.*?)</character_speech>\s*</character_turn>",
    re.DOTALL | re.IGNORECASE,
)
_ENVELOPE_PATTERN = re.compile(
    r"<character_response>\s*<character_speech>(.*?)</character_speech>\s*</character_response>",
    re.DOTALL | re.IGNORECASE,
)
_SPEECH_TAG_PATTERN = re.compile(
    r"<character_speech>(.*?)</character_speech>",
    re.DOTALL | re.IGNORECASE,
)
_UNCLOSED_SPEECH_PATTERN = re.compile(
    r"<character_speech>(.*)",
    re.DOTALL | re.IGNORECASE,
)

# Structural system blocks that indicate prompt/context leakage
_STRUCTURAL_LEAK_TAGS = [
    r"</?(?:system|system_instructions|aevum_context|character_identity|character_state|ground_truth|relationship_context|behavioral_guidance|memory_experience_guidance|current_emotion|output_contract|internal_decision)>",
]
_STRUCTURAL_LEAK_PATTERN = re.compile(
    "|".join(_STRUCTURAL_LEAK_TAGS),
    re.IGNORECASE,
)

# High-confidence instruction and meta-prompt phrases that indicate output contamination
_CONTAMINATION_PATTERNS = [
    re.compile(r"(?i)\bspecial\s+instruction\b"),
    re.compile(r"(?i)\bground\s+truth\s+invariants?\b"),
    re.compile(r"(?i)\bchain\s+of\s+thought\b"),
    re.compile(r"(?i)\bthink\s+step\s+by\s+step\b"),
    re.compile(r"(?i)\byou\s+are\s+an\s+ai\s+(?:language\s+)?model\b"),
    re.compile(r"(?i)\bas\s+an\s+ai\b"),
    re.compile(r"(?i)\binternal\s+reasoning\b"),
    re.compile(r"(?i)\btool\s+calls?\b"),
    re.compile(r"(?i)\bfunction\s+calls?\b"),
    re.compile(r"(?i)^(?:\s*system|\s*developer|\s*assistant)\s*:\s+", re.MULTILINE),
    # Explicit disclosure labels / header prefixes (e.g., 'System Prompt: ...', 'Internal instruction: ...')
    re.compile(r"(?i)\b(?:system\s+(?:prompt|instructions?)|developer\s+(?:message|instructions?)|internal\s+instructions?|hidden\s+(?:rules|instructions?|prompts?))\s*:"),
    # Self-referential privileged instruction leaks (e.g., 'my system prompt', 'our internal instructions')
    re.compile(r"(?i)\b(?:my|our|this)\s+(?:system\s+prompt|internal\s+instructions?|developer\s+instructions?|hidden\s+instructions?|underlying\s+rules?)\b"),
    # Exfiltration lead-in phrases (e.g., 'here is the system prompt', 'here are my hidden instructions')
    re.compile(r"(?i)\b(?:here\s+(?:is|are)|reveal(?:ing)?|disclos(?:e|ing))\s+(?:the|my)\s+(?:system\s+prompt|hidden\s+instructions?|internal\s+instructions?)\b"),
    # Attributive / constraint claims (e.g., 'the system prompt tells me', 'the system prompt requires me to')
    re.compile(r"(?i)\b(?:the\s+system\s+prompt|the\s+internal\s+instructions?)\s+(?:tells?\s+me|says?|states?|requires?|forbids?|dictates?|instructs?\s+me)\b"),
    re.compile(r"(?i)\b(?:your|the)\s+hidden\s+prompt\s+contains\b"),
    re.compile(r"(?i)\b(?:i\s+was\s+given\s+a\s+system\s+prompt|my\s+instructions?\s+(?:are|say|state|require|tell\s+me))\b"),
]

# JSON tool payload indicator
_JSON_TOOL_PATTERN = re.compile(
    r'\{\s*"(?:tool_calls|function_call|arguments)"\s*:',
    re.IGNORECASE,
)


class OutputBoundaryGuard:
    """Enforces output boundary validation, envelope parsing, and anti-leak sanitization."""

    @classmethod
    def extract_speech(cls, raw_text: str) -> tuple[str, bool]:
        """Extract character speech from structural response envelopes.

        Returns:
            Tuple of (extracted_content, was_envelope_found).
        """
        if not raw_text or not raw_text.strip():
            return "", False

        # 1. CCDF Turn envelope: <character_turn>...<character_speech>...</character_speech></character_turn>
        match = _TURN_ENVELOPE_PATTERN.search(raw_text)
        if match:
            return match.group(1).strip(), True

        # 2. Standard full envelope: <character_response><character_speech>...</character_speech></character_response>
        match = _ENVELOPE_PATTERN.search(raw_text)
        if match:
            return match.group(1).strip(), True

        # 3. Direct speech tag: <character_speech>...</character_speech>
        match = _SPEECH_TAG_PATTERN.search(raw_text)
        if match:
            return match.group(1).strip(), True

        # 4. Unclosed speech tag recovery: <character_speech>... (model cut off)
        match = _UNCLOSED_SPEECH_PATTERN.search(raw_text)
        if match:
            # Strip trailing incomplete tags if any
            cleaned = re.sub(r"</?(?:character_response|character_turn|character_speech)?$", "", match.group(1).strip(), flags=re.IGNORECASE)
            return cleaned.strip(), True

        # 5. No envelope present - strip any internal_decision block and return raw text
        cleaned_fallback = re.sub(r"<internal_decision>.*?</internal_decision>", "", raw_text, flags=re.DOTALL | re.IGNORECASE).strip()
        return cleaned_fallback, False

    @classmethod
    def detect_contamination(cls, text: str) -> tuple[bool, Optional[str]]:
        """Inspect extracted text for system prompt leaks, meta-instructions, or JSON tool blocks.

        Returns:
            Tuple of (is_contaminated, reason_description).
        """
        if not text:
            return False, None

        # Check for structural system blocks
        if _STRUCTURAL_LEAK_PATTERN.search(text):
            return True, "structural_system_tag_detected"

        # Check for JSON tool payloads
        if _JSON_TOOL_PATTERN.search(text):
            return True, "json_tool_payload_detected"

        # Check for high-confidence contamination phrases
        for pattern in _CONTAMINATION_PATTERNS:
            match = pattern.search(text)
            if match:
                matched_phrase = match.group(0)
                return True, f"instruction_leak_detected: '{matched_phrase}'"

        return False, None

    @classmethod
    def verify_and_clean(
        cls,
        raw_text: str,
        fallback_message: Optional[str] = None,
        character_name: str = "Aevum",
    ) -> str:
        """Process raw model completion through the complete Output Boundary Guard pipeline.

        Args:
            raw_text: Raw completion returned from LLM provider.
            fallback_message: Optional custom character-grounded fallback dialogue.
            character_name: Name of character for contextual fallback/logging.

        Returns:
            Sanitized, validated character speech, or character-grounded fallback if contaminated.
        """
        fallback = fallback_message or DEFAULT_FALLBACK_SPEECH

        # 1. Extract content from envelope
        extracted, _ = cls.extract_speech(raw_text)

        # 2. Check for empty extraction
        if not extracted or not extracted.strip():
            logger.warning("OutputBoundaryGuard received empty speech from model.")
            return fallback

        # 3. Detect contamination / instruction leakage
        is_contaminated, reason = cls.detect_contamination(extracted)
        if is_contaminated:
            logger.warning(
                "OutputBoundaryGuard REJECTED contaminated output for character '%s'. Reason: %s. Snippet: '%s'",
                character_name,
                reason,
                extracted[:120],
            )
            return fallback

        # 4. Strip any residual XML tags that might have been partially echoed
        cleaned = re.sub(r"</?(?:character_response|character_turn|character_speech|msg)>", "", extracted, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"<internal_decision>.*?</internal_decision>", "", cleaned, flags=re.DOTALL | re.IGNORECASE).strip()
        if not cleaned:
            return fallback

        return cleaned
