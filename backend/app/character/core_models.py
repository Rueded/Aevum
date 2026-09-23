"""Character Core domain models for Project Aevum.

Represents canonical, objective facts regarding Aevum's identity, education,
family baseline, location, and interests. The database (`character_core_facts`)
is the single authoritative runtime source of truth.
"""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.reality.models import CoreFactItem


class CharacterCore(BaseModel):
    """Immutable aggregate model of Character Core facts for a character."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str = Field(default="aevum", description="Target character identifier")
    facts: dict[str, CoreFactItem] = Field(
        default_factory=dict,
        description="All canonical and candidate core facts indexed by dot-notated key",
    )

    def get_fact_value(self, key: str, default: Any = None) -> Any:
        """Convenience lookup for a fact's value by dot-notated key."""
        fact = self.facts.get(key)
        return fact.value if fact is not None else default

    @property
    def identity_facts(self) -> dict[str, CoreFactItem]:
        """Projections of identity facts (name, age, occupation, background)."""
        return {k: f for k, f in self.facts.items() if f.category == "identity"}

    @property
    def family_facts(self) -> dict[str, CoreFactItem]:
        """Projections of family background facts."""
        return {k: f for k, f in self.facts.items() if f.category == "family"}

    @property
    def education_facts(self) -> dict[str, CoreFactItem]:
        """Projections of education facts (level, university, major, pathway)."""
        return {k: f for k, f in self.facts.items() if f.category == "education"}

    @property
    def location_facts(self) -> dict[str, CoreFactItem]:
        """Projections of location facts (residence, hometown)."""
        return {k: f for k, f in self.facts.items() if f.category == "location"}

    @property
    def lifestyle_facts(self) -> dict[str, CoreFactItem]:
        """Projections of daily lifestyle facts (transit, beverage, etc.)."""
        return {k: f for k, f in self.facts.items() if f.category == "lifestyle"}

    @property
    def interests(self) -> list[str]:
        """Typed projection of interests list."""
        fact = self.facts.get("interests")
        if fact and isinstance(fact.value, (list, tuple)):
            return list(fact.value)
        return []

    @property
    def dislikes(self) -> list[str]:
        """Typed projection of dislikes list."""
        fact = self.facts.get("dislikes")
        if fact and isinstance(fact.value, (list, tuple)):
            return list(fact.value)
        return []

    def get_fact(self, key: str) -> Optional[CoreFactItem]:
        """Retrieve a fact item by dot-notated key."""
        return self.facts.get(key)

    def has_fact(self, key: str) -> bool:
        """Check whether a fact exists."""
        return key in self.facts

    def is_locked(self, key: str) -> bool:
        """Check whether a fact exists and is locked by the user."""
        fact = self.facts.get(key)
        return fact.is_locked if fact else False

    def get_value(self, key: str, default: Any = None) -> Any:
        """Retrieve the value of a fact or a default."""
        fact = self.facts.get(key)
        return fact.value if fact else default
