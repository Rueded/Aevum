"""Genesis DTOs and semantic declaration schemas for Aevum Core (Phase 17.1).

Enforces the core principles:
- "We are creating a living person, not rolling an RPG stat sheet."
- GC-419: No continuous psychological state sliders (0-100 sliders banned).
- GC-422: Epistemic Seed Declarations != Auto Heard-Of (semantic depth mapping).
- GC-423: Relationship Archetypes as presets, not closed enums (allows custom narrative backstory).
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class SemanticEpistemicDepth(str, Enum):
    """User-declared depth of relationship/exposure to an interest/domain at genesis."""
    PROFICIENT_LIVED = "PROFICIENT_LIVED"        # 擅长 / 长期接触 -> EXPERIENCED + SELF_EXPERIENCE
    FAMILIAR_KNOWLEDGEABLE = "FAMILIAR"          # 熟悉 / 有一定了解 -> EXPERIENCED / 高熟悉度
    HEARD_OF_AWARE = "HEARD_OF_AWARE"            # 听说过 / 知道一些 -> HEARD_OF + WORLD_KNOWLEDGE
    CURIOUS_BEGINNER = "CURIOUS_BEGINNER"        # 刚开始感兴趣 -> HEARD_OF + 好奇探索
    UNFAMILIAR_OPEN = "UNFAMILIAR_OPEN"          # 完全不了解，但愿探索 -> UNFAMILIAR


class EpistemicSeedDeclaration(BaseModel):
    """Single declared epistemic seed topic with declared depth and optional qualia note."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    topic: str = Field(min_length=1, max_length=50, description="Domain or topic key (e.g. 'classical_piano').")
    depth: SemanticEpistemicDepth = Field(
        default=SemanticEpistemicDepth.HEARD_OF_AWARE,
        description="Declared exposure depth.",
    )
    detail_note: str = Field(
        default="",
        max_length=200,
        description="Optional backstory note for this skill/interest (e.g. '自幼学琴十年').",
    )


class SemanticFamiliarityLevel(str, Enum):
    """Discrete qualitative levels for initial familiarity at genesis."""
    STRANGER = "STRANGER"              # 素昧平生 (familiarity = 0.05)
    SLIGHTLY_ACQUAINTED = "ACQUAINTED" # 点头之交 (familiarity = 0.20)
    FAMILIAR = "FAMILIAR"              # 彼此熟稔 (familiarity = 0.50)
    INTIMATELY_FAMILIAR = "INTIMATE"   # 深厚知己 (familiarity = 0.80)


class SemanticTrustLevel(str, Enum):
    """Discrete qualitative levels for initial trust disposition at genesis."""
    CAUTIOUS = "CAUTIOUS"              # 慢热审慎 (trust = 0.10, comfort = 0.05)
    OPEN_NEUTRAL = "OPEN_NEUTRAL"      # 温和开放 (trust = 0.25, comfort = 0.15)
    INHERENT_TRUST = "INHERENT_TRUST"  # 天然信赖 (trust = 0.65, comfort = 0.60)


class GenesisAIGenerateRequest(BaseModel):
    """User prompt containing keywords or adjectives for auto-generating character genesis."""
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Keywords, adjectives, personality traits, or brief background wishes.",
    )


class CharacterCreationPayload(BaseModel):
    """Unified payload for companion character genesis.
    
    Contains:
    - Tier A: Identity, personality, lifestyle, speech style, innate boundaries, epistemic seeds.
    - Tier B: Relationship genesis origin (archetype, qualitative familiarity/trust, narrative meeting backstory).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Tier A Identity & Persona
    name: str = Field(min_length=1, max_length=50, description="Companion display name.")
    age: int = Field(ge=14, le=100, default=21, description="Companion age (natural human years).")
    occupation: str = Field(min_length=1, max_length=100, description="Companion occupation/role.")
    lifestyle_rhythm: str = Field(
        default="晨型作息，偏好安静的书房与琴房空间。",
        max_length=200,
        description="Daily lifestyle rhythm context.",
    )
    background_story: str = Field(
        default="",
        max_length=1000,
        description="Foundational personal background and origin story.",
    )
    core_traits: list[str] = Field(
        min_length=1,
        max_length=10,
        description="Curated core personality traits (e.g. ['thoughtful', 'independent', 'playful']).",
    )
    speaking_style: str = Field(
        default="自然平实，语调从容，偶尔轻快打趣。",
        max_length=200,
        description="Communication style demeanor.",
    )
    epistemic_seeds: list[EpistemicSeedDeclaration] = Field(
        default_factory=list,
        description="Declared skills, interests, and curiosity topics.",
    )
    innate_boundaries: list[str] = Field(
        default_factory=lambda: [
            "不参与虚假媚俗模拟，保持真实尊严与独立思考。",
            "珍视个人隐私与个人空间界限。",
        ],
        description="Immutable behavioral and dignity boundaries.",
    )

    # Tier B Relationship Genesis
    relationship_archetype: str = Field(
        default="NEW_ACQUAINTANCE",
        max_length=100,
        description="Relationship archetype key (e.g. 'NEW_ACQUAINTANCE', 'CLASSMATE', 'CO_TENANT', or custom).",
    )
    familiarity_level: SemanticFamiliarityLevel = Field(
        default=SemanticFamiliarityLevel.STRANGER,
        description="Discrete semantic familiarity anchor.",
    )
    trust_level: SemanticTrustLevel = Field(
        default=SemanticTrustLevel.OPEN_NEUTRAL,
        description="Discrete semantic trust anchor.",
    )
    meeting_backstory: str = Field(
        default="刚刚相识，初次交流。",
        max_length=1000,
        description="Narrative context of how the companion and user encountered each other.",
    )


class BlueprintUpdateRequest(BaseModel):
    """Payload for modifying Tier A static persona framing in Daily Settings.
    
    Hard Invariants:
    - Only alters Tier A identity and communication style framing.
    - Strictly forbids updating relationship metrics or historical experiences.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    identity_summary: str | None = Field(default=None, max_length=1000)
    lifestyle_rhythm: str | None = Field(default=None, max_length=200)
    core_traits: list[str] | None = Field(default=None, min_length=1, max_length=10)
    communication_style: list[str] | None = Field(default=None, max_length=5)
    speaking_style: list[str] | str | None = Field(default=None)
    innate_boundaries: list[str] | None = Field(default=None, max_length=10)


class CharacterCreationResponse(BaseModel):
    """Response returned upon successful atomic character genesis."""
    model_config = ConfigDict(frozen=True)

    success: bool = True
    character_id: str
    blueprint_version: int
    relationship_archetype: str
    initial_awakening_greeting: str
    snapshot: dict[str, Any]


class GenesisPresetsResponse(BaseModel):
    """Preset library providing curated options for the desktop Genesis Wizard."""
    model_config = ConfigDict(frozen=True)

    archetype_presets: list[dict[str, str]]
    trait_presets: list[str]
    speaking_style_presets: list[dict[str, str]]
    lifestyle_presets: list[dict[str, str]]
    epistemic_depth_options: list[dict[str, str]]
    familiarity_options: list[dict[str, str]]
    trust_options: list[dict[str, str]]
