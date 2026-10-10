"""Deterministic Slot-Value Normalizer for Phase 8A (Autonomous Reality & Life Inference).

Strict Invariants:
- Normalizes transient raw proposal values into canonical tokens before persistence or competition.
- Prevents uncontrolled semantic variants (e.g. 'CS', 'Computer Science') from polluting CharacterCore.
- Rejects unknown or malformed values with explicit, testable failure results.
- Initial supported slots: 'education.major', 'education.pathway', 'career.aspiration'.
"""

import enum
import re
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class NormalizationStatus(str, enum.Enum):
    """Categorical status of a slot value normalization attempt."""

    VALID = "VALID"                      # Successfully matched and normalized to canonical token
    INVALID = "INVALID"                  # Slot is supported, but raw value could not be recognized
    UNSUPPORTED_SLOT = "UNSUPPORTED_SLOT"# Slot is not registered in the normalization policy


class SlotNormalizationResult(BaseModel):
    """Immutable outcome of a slot value normalization check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slot_name: str = Field(..., description="Target attribute slot evaluated.")
    raw_value: Any = Field(..., description="Original raw value prior to normalization.")
    normalized_value: Any = Field(..., description="Normalized canonical value if valid, or original raw value if invalid.")
    status: NormalizationStatus = Field(..., description="Normalization outcome status.")
    rejection_reason: Optional[str] = Field(default=None, description="Detailed explanation if invalid or unsupported.")

    @property
    def is_valid(self) -> bool:
        """True if and only if normalization produced a recognized canonical value."""
        return self.status == NormalizationStatus.VALID


class SlotValueNormalizer:
    """Pure deterministic normalizer for candidate values across supported autonomous slots."""

    # -------------------------------------------------------------------------
    # Initial Slot Definitions & Alias Mappings
    # -------------------------------------------------------------------------

    _MAJOR_ALIASES: dict[str, str] = {
        # computer_science
        "cs": "computer_science",
        "computer science": "computer_science",
        "com sci": "computer_science",
        "comp sci": "computer_science",
        "computer science (b.sc)": "computer_science",
        "bsc computer science": "computer_science",
        "computer_science": "computer_science",
        # software_engineering
        "se": "software_engineering",
        "software engineering": "software_engineering",
        "b.se": "software_engineering",
        "software dev": "software_engineering",
        "software_engineering": "software_engineering",
        # music_performance
        "music": "music_performance",
        "music performance": "music_performance",
        "piano performance": "music_performance",
        "music major": "music_performance",
        "classical music": "music_performance",
        "music degree": "music_performance",
        "music_performance": "music_performance",
        # sound_engineering
        "sound engineering": "sound_engineering",
        "audio production": "sound_engineering",
        "audio engineering": "sound_engineering",
        "music production": "sound_engineering",
        "sound_engineering": "sound_engineering",
        # digital_media
        "digital media": "digital_media",
        "digital media design": "digital_media",
        "media design": "digital_media",
        "multimedia design": "digital_media",
        "digital_media": "digital_media",
        # business_information_systems
        "bis": "business_information_systems",
        "business information systems": "business_information_systems",
        "information systems": "business_information_systems",
        "is": "business_information_systems",
        "business_information_systems": "business_information_systems",
        # electrical_engineering
        "electrical engineering": "electrical_engineering",
        "ee": "electrical_engineering",
        "electrical_engineering": "electrical_engineering",
        # multimedia
        "multimedia": "multimedia",
    }

    _PATHWAY_ALIASES: dict[str, str] = {
        # STPM
        "stpm": "STPM",
        "form 6": "STPM",
        "form six": "STPM",
        "tingkatan 6": "STPM",
        "malaysian higher school certificate": "STPM",
        # MATRIKULASI
        "matrikulasi": "MATRIKULASI",
        "matriculation": "MATRIKULASI",
        "matrik": "MATRIKULASI",
        "kpm matriculation": "MATRIKULASI",
        # FOUNDATION
        "foundation": "FOUNDATION",
        "foundation in science": "FOUNDATION",
        "foundation in arts": "FOUNDATION",
        "pre-university foundation": "FOUNDATION",
        # DIPLOMA
        "diploma": "DIPLOMA",
        "polytechnic diploma": "DIPLOMA",
        # A_LEVEL
        "a level": "A_LEVEL",
        "a-level": "A_LEVEL",
        "a_level": "A_LEVEL",
        "alevel": "A_LEVEL",
        "cambridge a level": "A_LEVEL",
    }

    _CAREER_ALIASES: dict[str, str] = {
        # software_engineer
        "software engineer": "software_engineer",
        "software developer": "software_engineer",
        "programmer": "software_engineer",
        "coder": "software_engineer",
        "swe": "software_engineer",
        "software_engineer": "software_engineer",
        # game_developer
        "game dev": "game_developer",
        "game developer": "game_developer",
        "game programmer": "game_developer",
        "game_developer": "game_developer",
        # musician
        "musician": "musician",
        "pianist": "musician",
        "composer": "musician",
        "performer": "musician",
        # sound_designer
        "sound designer": "sound_designer",
        "sound design": "sound_designer",
        "sound_designer": "sound_designer",
        # music_producer
        "music producer": "music_producer",
        "producer": "music_producer",
        "music_producer": "music_producer",
        # data_analyst
        "data analyst": "data_analyst",
        "data scientist": "data_analyst",
        "data_analyst": "data_analyst",
        # academic_researcher
        "academic researcher": "academic_researcher",
        "researcher": "academic_researcher",
        "academic": "academic_researcher",
        "academic_researcher": "academic_researcher",
    }

    _INSTITUTION_ALIASES: dict[str, str] = {
        # USM
        "usm": "Universiti Sains Malaysia (USM)",
        "universiti sains malaysia": "Universiti Sains Malaysia (USM)",
        "universiti sains malaysia (usm)": "Universiti Sains Malaysia (USM)",
        "理大": "Universiti Sains Malaysia (USM)",
        "马来西亚理科大学": "Universiti Sains Malaysia (USM)",
        # UM
        "um": "Universiti Malaya (UM)",
        "universiti malaya": "Universiti Malaya (UM)",
        "universiti malaya (um)": "Universiti Malaya (UM)",
        "马大": "Universiti Malaya (UM)",
        "马来亚大学": "Universiti Malaya (UM)",
        # Monash
        "monash": "Monash University Malaysia",
        "monash university": "Monash University Malaysia",
        "monash university malaysia": "Monash University Malaysia",
        "莫纳什": "Monash University Malaysia",
        "莫纳什大学": "Monash University Malaysia",
        "monash malaysia": "Monash University Malaysia",
    }

    _YEAR_ALIASES: dict[str, str] = {
        "year 1": "Year 1",
        "year 2": "Year 2",
        "year 3": "Year 3",
        "year 4": "Year 4",
        "1": "Year 1",
        "2": "Year 2",
        "3": "Year 3",
        "4": "Year 4",
        "大一": "Year 1",
        "大二": "Year 2",
        "大三": "Year 3",
        "大四": "Year 4",
        "first year": "Year 1",
        "second year": "Year 2",
        "third year": "Year 3",
        "fourth year": "Year 4",
    }

    @classmethod
    def _clean_str(cls, val: Any) -> str:
        """Strip surrounding quotes, lower-case, and collapse whitespace."""
        s = str(val).strip().lower()
        s = re.sub(r"\s+", " ", s)
        return s

    @classmethod
    def normalize(cls, slot_name: str, raw_value: Any) -> SlotNormalizationResult:
        """Normalize a raw proposed value according to the target slot contract."""
        if not isinstance(slot_name, str) or not slot_name.strip():
            return SlotNormalizationResult(
                slot_name=str(slot_name),
                raw_value=raw_value,
                normalized_value=raw_value,
                status=NormalizationStatus.UNSUPPORTED_SLOT,
                rejection_reason="Slot name must be a non-empty string.",
            )

        slot = slot_name.strip()

        # 1. education.major
        if slot == "education.major":
            cleaned = cls._clean_str(raw_value)
            canonical = cls._MAJOR_ALIASES.get(cleaned)
            if canonical:
                return SlotNormalizationResult(
                    slot_name=slot,
                    raw_value=raw_value,
                    normalized_value=canonical,
                    status=NormalizationStatus.VALID,
                )
            return SlotNormalizationResult(
                slot_name=slot,
                raw_value=raw_value,
                normalized_value=raw_value,
                status=NormalizationStatus.INVALID,
                rejection_reason=f"Unknown or un-normalizable major: '{raw_value}'.",
            )

        # 2. education.pathway
        if slot == "education.pathway":
            cleaned = cls._clean_str(raw_value)
            canonical = cls._PATHWAY_ALIASES.get(cleaned)
            if canonical:
                return SlotNormalizationResult(
                    slot_name=slot,
                    raw_value=raw_value,
                    normalized_value=canonical,
                    status=NormalizationStatus.VALID,
                )
            return SlotNormalizationResult(
                slot_name=slot,
                raw_value=raw_value,
                normalized_value=raw_value,
                status=NormalizationStatus.INVALID,
                rejection_reason=f"Unknown or un-normalizable pathway: '{raw_value}'.",
            )

        # 3. career.aspiration
        if slot == "career.aspiration":
            cleaned = cls._clean_str(raw_value)
            canonical = cls._CAREER_ALIASES.get(cleaned)
            if canonical:
                return SlotNormalizationResult(
                    slot_name=slot,
                    raw_value=raw_value,
                    normalized_value=canonical,
                    status=NormalizationStatus.VALID,
                )
            return SlotNormalizationResult(
                slot_name=slot,
                raw_value=raw_value,
                normalized_value=raw_value,
                status=NormalizationStatus.INVALID,
                rejection_reason=f"Unknown or un-normalizable career aspiration: '{raw_value}'.",
            )

        # 4. education.institution
        if slot in ("education.institution", "education.university"):
            cleaned = cls._clean_str(raw_value)
            canonical = cls._INSTITUTION_ALIASES.get(cleaned)
            if canonical:
                return SlotNormalizationResult(
                    slot_name=slot,
                    raw_value=raw_value,
                    normalized_value=canonical,
                    status=NormalizationStatus.VALID,
                )
            # If string is non-empty and has reasonable length, accept as valid institution string
            if isinstance(raw_value, str) and len(raw_value.strip()) >= 2:
                return SlotNormalizationResult(
                    slot_name=slot,
                    raw_value=raw_value,
                    normalized_value=raw_value.strip(),
                    status=NormalizationStatus.VALID,
                )
            return SlotNormalizationResult(
                slot_name=slot,
                raw_value=raw_value,
                normalized_value=raw_value,
                status=NormalizationStatus.INVALID,
                rejection_reason=f"Unknown or un-normalizable university institution: '{raw_value}'.",
            )

        # 5. education.year
        if slot == "education.year":
            cleaned = cls._clean_str(raw_value)
            canonical = cls._YEAR_ALIASES.get(cleaned)
            if canonical:
                return SlotNormalizationResult(
                    slot_name=slot,
                    raw_value=raw_value,
                    normalized_value=canonical,
                    status=NormalizationStatus.VALID,
                )
            if isinstance(raw_value, int) and 1 <= raw_value <= 6:
                return SlotNormalizationResult(
                    slot_name=slot,
                    raw_value=raw_value,
                    normalized_value=f"Year {raw_value}",
                    status=NormalizationStatus.VALID,
                )
            return SlotNormalizationResult(
                slot_name=slot,
                raw_value=raw_value,
                normalized_value=raw_value,
                status=NormalizationStatus.INVALID,
                rejection_reason=f"Unknown or un-normalizable academic year: '{raw_value}'.",
            )

        # 6. family & lifestyle & background slots
        if slot in (
            "family.parents_occupation",
            "family.childhood_background",
            "lifestyle.transit",
            "lifestyle.beverage",
            "education.secondary_school",
            "education.music_qualification",
        ):
            if isinstance(raw_value, str) and len(raw_value.strip()) >= 2:
                return SlotNormalizationResult(
                    slot_name=slot,
                    raw_value=raw_value,
                    normalized_value=raw_value.strip(),
                    status=NormalizationStatus.VALID,
                )
            return SlotNormalizationResult(
                slot_name=slot,
                raw_value=raw_value,
                normalized_value=raw_value,
                status=NormalizationStatus.INVALID,
                rejection_reason=f"Invalid string value for slot '{slot}': '{raw_value}'.",
            )

        # Unsupported slot
        return SlotNormalizationResult(
            slot_name=slot,
            raw_value=raw_value,
            normalized_value=raw_value,
            status=NormalizationStatus.UNSUPPORTED_SLOT,
            rejection_reason=f"Slot '{slot}' is not currently configured for autonomous normalization.",
        )
