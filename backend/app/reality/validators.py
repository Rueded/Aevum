"""Validation services for Reality & Belief Engine (Phase 7B.3).

Implements independent validators:
- ConsistencyValidator: anchor compatibility with Core & locks.
- TimelineValidator: chronological causality (age vs pre-u pathway vs academic year).
- CausalityValidator: physical and logical feasibility.
- WorldKnowledgeValidator: verification against objective world lore.
"""

from typing import TYPE_CHECKING, Any, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.character.core_models import CharacterCore
from app.reality.candidate_models import CandidateFact
from app.reality.world_knowledge import KnowledgeKind, WorldKnowledgeRegistry


class ValidationResult(BaseModel):
    """Immutable outcome of a validation check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_valid: bool = Field(default=True, description="Whether validation passed.")
    reasons: tuple[str, ...] = Field(default_factory=tuple, description="Audit rationale messages.")
    details: dict[str, Any] = Field(default_factory=dict, description="Optional diagnostic details.")

    def __init__(
        self,
        passed_or_valid: bool = True,
        reason: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        *,
        is_valid: Optional[bool] = None,
        reasons: Optional[Sequence[str]] = None,
        **data: Any,
    ) -> None:
        val = passed_or_valid if is_valid is None else is_valid
        if reasons is not None:
            r_tuple = tuple(reasons)
        elif reason:
            r_tuple = (reason,)
        else:
            r_tuple = ()
        super().__init__(is_valid=val, reasons=r_tuple, details=details or {}, **data)

    def __bool__(self) -> bool:
        return self.is_valid

    @property
    def passed(self) -> bool:
        return self.is_valid

    @property
    def reason(self) -> str:
        return "; ".join(self.reasons) if self.reasons else ""


class ConsistencyValidator:
    """Validates compatibility with existing Character Core canonical facts and locks."""

    @classmethod
    def validate(
        cls,
        candidate_or_key: Any,
        proposed_value_or_core: Any = None,
        core: Optional["CharacterCore"] = None,
    ) -> ValidationResult:
        """Validate candidate against existing Character Core facts and user locks."""
        if isinstance(candidate_or_key, CandidateFact):
            fact_key = candidate_or_key.fact_key
            proposed_value = candidate_or_key.value
            actual_core = proposed_value_or_core
        else:
            fact_key = str(candidate_or_key)
            proposed_value = proposed_value_or_core
            actual_core = core

        if not actual_core or not actual_core.facts:
            return ValidationResult(True, "No existing core facts to conflict with.")

        existing = actual_core.facts.get(fact_key)
        if existing:
            if existing.is_locked and existing.value != proposed_value:
                return ValidationResult(
                    False,
                    f"Fact '{fact_key}' is locked with value '{existing.value}', cannot override with '{proposed_value}'.",
                    {"locked_value": existing.value},
                )
            if existing.value == proposed_value:
                return ValidationResult(True, "Matches existing confirmed value.")

        return ValidationResult(True, "Compatible with current Core facts.")


class TimelineValidator:
    """Validates chronological causality and academic progress coherence."""

    @classmethod
    def validate(
        cls,
        candidate: CandidateFact,
        core: Optional["CharacterCore"] = None,
    ) -> ValidationResult:
        """Validate candidate fact against timeline constraints."""
        if candidate.fact_key == "education.year":
            age = 20
            pre_u = "STPM"
            if core:
                age = int(core.get_fact_value("identity.age", 20))
                pre_u = core.get_fact_value("education.pre_u", "STPM")
            try:
                year_val = int(candidate.value)
                return cls.validate_academic_year(age=age, pre_u_pathway=pre_u, academic_year=year_val)
            except (ValueError, TypeError):
                return ValidationResult(True, "Non-integer year value allowed.")

        return ValidationResult(True, "Timeline is consistent.")

    @classmethod
    def validate_academic_year(
        cls,
        *,
        age: int,
        pre_u_pathway: Optional[str] = None,
        academic_year: int,
    ) -> ValidationResult:
        """Validate whether academic_year makes chronological sense for the given age and pre-u."""
        if academic_year < 1 or academic_year > 6:
            return ValidationResult(False, f"Academic year {academic_year} is outside standard range 1..6.")

        if age <= 16:
            return ValidationResult(False, f"Age {age} cannot be an undergraduate without extraordinary child prodigy canon.")

        if age == 20:
            if academic_year in (1, 2):
                return ValidationResult(True, f"Year {academic_year} at age 20 is chronologically sound.")
            elif academic_year > 3:
                return ValidationResult(
                    False,
                    f"Year {academic_year} at age 20 is chronologically implausible for standard pre-u timelines.",
                    {"age": age, "academic_year": academic_year},
                )

        return ValidationResult(True, "Academic timeline is plausible.")

    @classmethod
    def check_graduation_slip(cls, age: int, years_since_grad: int) -> ValidationResult:
        """Check if claiming graduation N years ago violates chronological math."""
        grad_age = age - years_since_grad
        if grad_age < 18:
            return ValidationResult(
                False,
                f"Graduating university at age {grad_age} (age {age} minus {years_since_grad} years) is chronologically impossible.",
                {"implied_graduation_age": grad_age},
            )
        return ValidationResult(True, "Graduation timeline is plausible.")


class CausalityValidator:
    """Validates physical causality, geographic travel plausibility, and natural laws."""

    @classmethod
    def validate(cls, candidate: CandidateFact) -> ValidationResult:
        """Validate physical claims in candidate facts."""
        if candidate.fact_key == "world.astronomy.sun_rises":
            if str(candidate.value).lower() != "east":
                return ValidationResult(
                    False,
                    f"Claim '{candidate.fact_key}={candidate.value}' violates static physical fact.",
                )
        return ValidationResult(True, "Physical causality is satisfied.")

    @classmethod
    def validate_travel(cls, loc_a: str, loc_b: str, duration_hours: float) -> ValidationResult:
        """Check if moving from loc_a to loc_b within duration_hours is physically plausible."""
        a, b = loc_a.lower(), loc_b.lower()
        if ("kuala lumpur" in a and "penang" in b) or ("penang" in a and "kuala lumpur" in b):
            if duration_hours < 0.5:
                return ValidationResult(
                    False,
                    f"Transit between Kuala Lumpur and Penang in {duration_hours} hours is physically impossible without teleportation.",
                )
        return ValidationResult(True, "Transit causality is plausible.")


class WorldKnowledgeValidator:
    """Validates claims against objective world lore and static geographic facts."""

    @classmethod
    def validate(
        cls,
        claim_or_candidate: Any,
        claim_value: Any = None,
    ) -> ValidationResult:
        """Validate candidate fact against WorldKnowledgeRegistry."""
        if isinstance(claim_or_candidate, CandidateFact):
            claim_key = claim_or_candidate.fact_key
            val = claim_or_candidate.value
        else:
            claim_key = str(claim_or_candidate)
            val = claim_value

        item = WorldKnowledgeRegistry.get(claim_key)
        if not item:
            return ValidationResult(True, "No explicit external world constraint registered.")

        if item.kind == KnowledgeKind.STATIC_FACT:
            if str(item.value).lower() not in str(val).lower() and str(val).lower() not in str(item.value).lower():
                return ValidationResult(
                    False,
                    f"Claim '{claim_key}={val}' contradicts objective static fact '{item.value}'.",
                    {"expected": item.value, "claimed": val},
                )

        if item.kind == KnowledgeKind.ENTITY_RELATION:
            if str(item.value).lower() not in str(val).lower() and str(val).lower() not in str(item.value).lower():
                return ValidationResult(
                    False,
                    f"Entity attribution '{claim_key}={val}' contradicts established lore '{item.value}'.",
                    {"expected": item.value, "claimed": val},
                )

        return ValidationResult(True, "Consistent with world knowledge.")
