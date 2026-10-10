"""Conversational Response Parser for CCDF Protocol (Phase 18.1).

Parses <character_turn> containing compact <internal_decision> metadata
and <character_speech> surface text, strictly honoring GC-425 to GC-431.
"""

import logging
import re
from typing import Optional
from pydantic import ValidationError

from app.character.conversational_models import (
    ConversationalMotivation,
    FrictionTier,
    ResponseCommitmentTier,
    ResponseEnergyTier,
    TurnConversationalDecision,
)

logger = logging.getLogger(__name__)


class ParsedCharacterTurn:
    """Container for parsed turn output."""

    def __init__(
        self,
        speech_text: str,
        speech_bubbles: list[str],
        decision: Optional[TurnConversationalDecision] = None,
        is_legacy_format: bool = False,
        introspection_warning: Optional[str] = None,
    ):
        self.speech_text = speech_text
        self.speech_bubbles = speech_bubbles
        self.decision = decision
        self.is_legacy_format = is_legacy_format
        self.introspection_warning = introspection_warning

    def __repr__(self) -> str:
        return (
            f"<ParsedCharacterTurn bubbles={len(self.speech_bubbles)} "
            f"has_decision={self.decision is not None} legacy={self.is_legacy_format}>"
        )


class ConversationalResponseParser:
    """Parser for CCDF character_turn XML contracts."""

    # Maximum allowed raw characters inside <internal_decision> to prevent CoT essays (GC-431)
    MAX_INTERNAL_DECISION_CHARS = 600

    @classmethod
    def parse(cls, raw_output: str) -> ParsedCharacterTurn:
        """Parse raw model output into speech and optional decision metadata.

        Gracefully degrades to legacy formats or raw text if XML is malformed.
        """
        if not raw_output or not raw_output.strip():
            return ParsedCharacterTurn(
                speech_text="",
                speech_bubbles=[],
                decision=None,
            )

        text = raw_output.strip()

        # 1. Check for <internal_decision>
        decision: Optional[TurnConversationalDecision] = None
        introspection_warning: Optional[str] = None

        decision_match = re.search(
            r"<internal_decision>(.*?)</internal_decision>",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if decision_match:
            decision_raw = decision_match.group(1).strip()
            # GC-431 Guard: Check for reasoning essay bloat
            if len(decision_raw) > cls.MAX_INTERNAL_DECISION_CHARS:
                introspection_warning = (
                    f"GC-431 Warning: <internal_decision> exceeded {cls.MAX_INTERNAL_DECISION_CHARS} chars "
                    f"({len(decision_raw)} chars). CoT bloat detected."
                )
                logger.warning(introspection_warning)

            decision = cls._parse_decision_block(decision_raw)

        # 2. Extract <character_speech>
        speech_match = re.search(
            r"<character_speech>(.*?)</character_speech>",
            text,
            re.DOTALL | re.IGNORECASE,
        )

        is_legacy = False
        if speech_match:
            speech_raw = speech_match.group(1).strip()
            # Check if this was wrapped in legacy <character_response>
            if "<character_response>" in text and not decision_match:
                is_legacy = True
        else:
            # Fallback 1: Check legacy <character_response> without speech tag
            legacy_resp_match = re.search(
                r"<character_response>(.*?)</character_response>",
                text,
                re.DOTALL | re.IGNORECASE,
            )
            if legacy_resp_match:
                speech_raw = legacy_resp_match.group(1).strip()
                is_legacy = True
            else:
                # Fallback 2: Raw plain text (clean any unclosed tags)
                speech_raw = re.sub(r"<[^>]+>", "", text).strip()
                is_legacy = True

        # 3. Extract speech bubbles (GC-426: realization-driven splitting)
        bubbles = cls._extract_bubbles(speech_raw)
        speech_text = "\n\n".join(bubbles) if bubbles else speech_raw

        return ParsedCharacterTurn(
            speech_text=speech_text,
            speech_bubbles=bubbles,
            decision=decision,
            is_legacy_format=is_legacy,
            introspection_warning=introspection_warning,
        )

    @classmethod
    def _parse_decision_block(cls, raw: str) -> Optional[TurnConversationalDecision]:
        """Parses key-value pairs inside <internal_decision> into TurnConversationalDecision."""
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        kv: dict[str, str] = {}

        for line in lines:
            # Match "key: value" or "key = value"
            m = re.match(r"^([a-zA-Z_]+)\s*[:=]\s*(.*)$", line)
            if m:
                k = m.group(1).lower().strip()
                v = m.group(2).strip()
                kv[k] = v

        if not kv:
            return None

        try:
            # Resolve attention & reaction
            attention = kv.get("attention") or kv.get("focus") or "general_vibe"
            reaction = kv.get("reaction") or kv.get("affect") or "neutral_presence"

            # Resolve commitment
            commitment_raw = (kv.get("commitment") or "PARTIAL_FLOW").upper()
            commitment = getattr(ResponseCommitmentTier, commitment_raw, ResponseCommitmentTier.PARTIAL_FLOW)

            # Resolve energy
            energy_raw = (kv.get("energy") or "NORMAL").upper()
            energy = getattr(ResponseEnergyTier, energy_raw, ResponseEnergyTier.NORMAL)

            # Resolve motivation
            motivation_raw = (kv.get("motivation") or "GENUINE_SHARING").upper()
            motivation = getattr(ConversationalMotivation, motivation_raw, ConversationalMotivation.GENUINE_SHARING)

            # Resolve friction
            friction_raw = (kv.get("friction") or "POLITE_DISTANT").upper()
            friction = getattr(FrictionTier, friction_raw, FrictionTier.POLITE_DISTANT)

            # Resolve curiosity (GC-425)
            curiosity_str = kv.get("curiosity", "false").lower()
            curiosity = curiosity_str in ("true", "1", "yes")

            # Resolve ignored elements
            ignored_raw = kv.get("ignored", "") or kv.get("ignored_elements", "")
            ignored_elements = [item.strip() for item in ignored_raw.split(",") if item.strip()] if ignored_raw else []

            # Resolve momentum anchor
            momentum_anchor = kv.get("momentum") or kv.get("momentum_anchor") or None

            return TurnConversationalDecision(
                attention=attention[:120],
                reaction=reaction[:120],
                commitment=commitment,
                energy=energy,
                motivation=motivation,
                friction=friction,
                curiosity=curiosity,
                ignored_elements=ignored_elements,
                momentum_anchor=momentum_anchor[:120] if momentum_anchor else None,
            )
        except (ValidationError, Exception) as e:
            logger.warning(f"Failed to parse TurnConversationalDecision from metadata: {e}")
            return None

    @classmethod
    def extract_bubbles(cls, raw: str) -> list[str]:
        """Extracts individual speech bubbles from raw character speech.

        Supports:
        1. Explicit <msg>...</msg> tags.
        2. Natural multi-line bursts (split by newlines).
        3. Conversational burst splitting by expressive punctuation (!?~。), keeping emojis intact.
        """
        if not raw or not raw.strip():
            return []

        clean_raw = raw.strip()

        # 1. Check for explicit <msg> tags
        msg_matches = re.findall(r"<msg>(.*?)</msg>", clean_raw, re.DOTALL | re.IGNORECASE)
        if msg_matches:
            bubbles = [m.strip() for m in msg_matches if m.strip()]
            if bubbles:
                return bubbles

        # 2. Check for multi-line inputs (both \n\n and \n)
        lines = [line.strip() for line in clean_raw.splitlines() if line.strip()]
        if len(lines) > 1:
            return lines

        # 3. Single paragraph: check for natural short conversational bursts
        # E.g. "刚到家！今天地铁居然故障了[苦涩] 累死我了~"
        if len(clean_raw) > 15:
            pattern = r'([^!！?？~\n]+(?:\[[^\]]+\])?[!！?？~]+|[^。.\n]+(?:\[[^\]]+\])?[。.]+)'
            chunks = re.findall(pattern, clean_raw)
            if 2 <= len(chunks) <= 4:
                combined_len = sum(len(c.strip()) for c in chunks)
                if combined_len >= len(clean_raw.replace(" ", "")) * 0.8:
                    return [c.strip() for c in chunks if c.strip()]

        return [clean_raw]

    # Backwards-compatible private alias
    _extract_bubbles = extract_bubbles
