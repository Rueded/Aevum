"""Deterministic World Knowledge & Plausibility Rules for Reality & Belief Engine (Phase 7B.3).

Provides objective reference points for external geography, physical reality, game lore,
and typical Malaysian educational timelines.

Distinguishes:
- STATIC_FACT: Immutable objective truths (e.g. USM main campus in Penang, Sun rises in East).
- PLAUSIBILITY_RULE: Common typical priors (e.g. STPM duration ~1.5 years). These are
  guidelines for evaluating plausibility, NOT hard rejections for real-world variations.
- ENTITY_RELATION: Established pop-culture / lore entity memberships.
- TEMPORAL_RULE: Plausible calendar sequence rules.
"""

import enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class KnowledgeKind(str, enum.Enum):
    """Categorical epistemological kind of external world knowledge."""

    STATIC_FACT = "STATIC_FACT"            # Immutable, verifiable objective fact
    PLAUSIBILITY_RULE = "PLAUSIBILITY_RULE"# Typical sociological/academic prior (non-rigid)
    ENTITY_RELATION = "ENTITY_RELATION"    # Entity lore or universe attribution
    TEMPORAL_RULE = "TEMPORAL_RULE"        # Calendar and chronological sequence prior


class WorldKnowledgeItem(BaseModel):
    """Immutable domain item representing external world knowledge."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(..., description="Unique knowledge key.")
    value: Any = Field(..., description="Standard authoritative value or range.")
    kind: KnowledgeKind = Field(..., description="Epistemological kind.")
    description: str = Field(default="", description="Contextual description.")
    domain_category: Optional[str] = Field(default=None, description="Optional domain category.")

    @model_validator(mode="before")
    @classmethod
    def handle_fact_value_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "fact_value" in data and "value" not in data:
                data = dict(data)
                data["value"] = data.pop("fact_value")
        return data

    @property
    def fact_value(self) -> Any:
        """Alias for value."""
        return self.value


class WorldKnowledgeRegistry:
    """Declarative registry of deterministic validation knowledge and plausibility rules."""

    _REGISTRY: dict[str, WorldKnowledgeItem] = {}

    @classmethod
    def register(
        cls,
        key_or_item: Any,
        value: Any = None,
        kind: Optional[KnowledgeKind] = None,
        description: str = "",
        domain_category: Optional[str] = None,
    ) -> None:
        """Register a knowledge entry."""
        if isinstance(key_or_item, WorldKnowledgeItem):
            cls._REGISTRY[key_or_item.key] = key_or_item
        else:
            cls._REGISTRY[str(key_or_item)] = WorldKnowledgeItem(
                key=str(key_or_item),
                value=value,
                kind=kind or KnowledgeKind.STATIC_FACT,
                description=description,
                domain_category=domain_category,
            )

    @classmethod
    def lookup(cls, key: str) -> Optional[WorldKnowledgeItem]:
        """Look up knowledge entry by key."""
        return cls._REGISTRY.get(key)

    @classmethod
    def get(cls, key: str) -> Optional[WorldKnowledgeItem]:
        """Convenience alias for lookup."""
        return cls._REGISTRY.get(key)

    @classmethod
    def is_static_fact(cls, key: str) -> bool:
        """Check if key represents an immutable static fact."""
        item = cls.lookup(key)
        return item is not None and item.kind == KnowledgeKind.STATIC_FACT


# --- Seed Authoritative Reference Knowledge ---

# 1. Malaysian Higher Education Campuses (Static Facts)
WorldKnowledgeRegistry.register(
    "world.usm.main_campus",
    value="Penang",
    kind=KnowledgeKind.STATIC_FACT,
    description="Universiti Sains Malaysia (USM) Main Campus is in Gelugor/Minden, Penang.",
)
WorldKnowledgeRegistry.register(
    "world.usm.engineering_campus",
    value="Nibong Tebal",
    kind=KnowledgeKind.STATIC_FACT,
    description="USM Engineering Campus is in Nibong Tebal, Penang mainland.",
)
WorldKnowledgeRegistry.register(
    "world.usm.health_campus",
    value="Kubang Kerian",
    kind=KnowledgeKind.STATIC_FACT,
    description="USM Health Campus is in Kubang Kerian, Kelantan.",
)
WorldKnowledgeRegistry.register(
    "world.usm.kl_centre",
    value="Kuala Lumpur",
    kind=KnowledgeKind.STATIC_FACT,
    description="USM MoHE / Postgraduate Collaboration Centre in Kuala Lumpur (not undergraduate campus).",
)
WorldKnowledgeRegistry.register(
    "world.um.main_campus",
    value="Kuala Lumpur",
    kind=KnowledgeKind.STATIC_FACT,
    description="Universiti Malaya (UM) Main Campus is in Kuala Lumpur.",
)

# 2. Basic Physical / Natural Facts (Static Facts)
WorldKnowledgeRegistry.register(
    "world.astronomy.sun_rises",
    value="East",
    kind=KnowledgeKind.STATIC_FACT,
    description="The Sun rises in the East due to Earth's prograde rotation.",
)
WorldKnowledgeRegistry.register(
    "world.astronomy.sun_sets",
    value="West",
    kind=KnowledgeKind.STATIC_FACT,
    description="The Sun sets in the West.",
)

# 3. Game / Pop-Culture Lore (Entity Relations)
WorldKnowledgeRegistry.register(
    "lore.game.xianlian.game",
    value="Honkai_Star_Rail",
    kind=KnowledgeKind.ENTITY_RELATION,
    description="Xianlian (昔涟) is a character in Honkai: Star Rail, not Genshin Impact.",
)
WorldKnowledgeRegistry.register(
    "lore.game.xianlian",
    value="Honkai_Star_Rail",
    kind=KnowledgeKind.ENTITY_RELATION,
    description="Xianlian (昔涟) is a character in Honkai: Star Rail, not Genshin Impact.",
)

# 4. Malaysian Educational Plausibility Priors (Guidelines, Not Rigid Rejections)
WorldKnowledgeRegistry.register(
    "education.malaysia.spm.typical_age",
    value=17,
    kind=KnowledgeKind.PLAUSIBILITY_RULE,
    description="SPM examination is typically taken in Form 5 at age 17.",
)
WorldKnowledgeRegistry.register(
    "education.malaysia.stpm.typical_duration",
    value=1.5,
    kind=KnowledgeKind.PLAUSIBILITY_RULE,
    description="STPM (Form 6) typically spans approximately 1.5 years (3 semesters).",
)
WorldKnowledgeRegistry.register(
    "education.malaysia.stpm_duration",
    value=1.5,
    kind=KnowledgeKind.PLAUSIBILITY_RULE,
    description="STPM (Form 6) typically spans approximately 1.5 years (3 semesters).",
)
WorldKnowledgeRegistry.register(
    "education.malaysia.typical_undergrad_entry_age",
    value=(19, 21),
    kind=KnowledgeKind.PLAUSIBILITY_RULE,
    description="Typical university undergraduate entry age ranges from 19 to 21 depending on pre-u pathway.",
)
