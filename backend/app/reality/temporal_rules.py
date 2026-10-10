"""Declarative World Academic Calendars and Temporal Rules (Phase 8B.2).

Constitutional Invariants:
- Invariant F (World Temporal Rules != Personal Temporal Facts): World knowledge
  rules (e.g. STPM duration, university calendars) are evaluative constraints
  for the Temporal Constraint Graph (TCG), NEVER copied directly into
  CharacterCore or CharacterBiographyRecord as personal ground truth.
- Local Advisory & Institutional Prior: Represents known or typical institutional/system
  patterns, avoiding absolute assertions of universal certainty. Web verification
  is formally deferred to Phase 9.
- Immutability & Safety: Pydantic frozen models (extra="forbid"), zero database
  mutations, zero network calls, zero token minting.
"""

from __future__ import annotations

import enum
from typing import Any, Optional, Sequence, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.reality.temporal_models import LifeStage
from app.reality.world_knowledge import KnowledgeKind, WorldKnowledgeItem, WorldKnowledgeRegistry


# =============================================================================
# Categorical Enums: Rule Scope & Constraint Type
# =============================================================================

class TemporalRuleScope(str, enum.Enum):
    """Categorical applicability scope of a temporal rule (avoids global hardcoded constants)."""

    NATIONAL_EDUCATION_SYSTEM = "NATIONAL_EDUCATION_SYSTEM"  # e.g., Malaysian national education system
    INSTITUTION_SPECIFIC = "INSTITUTION_SPECIFIC"            # e.g., Universiti Sains Malaysia (USM)
    PATHWAY_SPECIFIC = "PATHWAY_SPECIFIC"                    # e.g., STPM Form 6, Matrikulasi, Foundation
    GENERAL_ACADEMIC = "GENERAL_ACADEMIC"                    # e.g., generic undergraduate degree structure


class TemporalConstraintType(str, enum.Enum):
    """Categorical constraint mechanism enforced by this rule."""

    DURATION_BOUND = "DURATION_BOUND"              # Min/max duration in years or months
    TYPICAL_CALENDAR_WINDOW = "TYPICAL_CALENDAR_WINDOW"  # Intake/exit calendar months or semester windows
    TYPICAL_AGE_WINDOW = "TYPICAL_AGE_WINDOW"      # Typical developmental or entry age range
    STAGE_PRECEDENCE = "STAGE_PRECEDENCE"          # Required prior developmental stage


# =============================================================================
# Typed Constraint Payloads (Structured & Immutable)
# =============================================================================

class DurationBoundValue(BaseModel):
    """Typed constraint payload for DURATION_BOUND rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_years: Optional[float] = Field(default=None, ge=0.0, description="Minimum duration in years")
    max_years: Optional[float] = Field(default=None, ge=0.0, description="Maximum duration in years")
    min_months: Optional[int] = Field(default=None, ge=0, description="Minimum duration in months")
    max_months: Optional[int] = Field(default=None, ge=0, description="Maximum duration in months")
    typical_years: Optional[float] = Field(default=None, ge=0.0, description="Typical standard duration in years")

    @model_validator(mode="after")
    def validate_bounds(self) -> DurationBoundValue:
        if self.min_years is not None and self.max_years is not None:
            if self.min_years > self.max_years:
                raise ValueError(f"min_years ({self.min_years}) cannot be greater than max_years ({self.max_years}).")
        if self.min_months is not None and self.max_months is not None:
            if self.min_months > self.max_months:
                raise ValueError(f"min_months ({self.min_months}) cannot be greater than max_months ({self.max_months}).")
        return self


class CalendarWindowValue(BaseModel):
    """Typed constraint payload for TYPICAL_CALENDAR_WINDOW rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intake_months: tuple[int, ...] = Field(
        ...,
        description="Typical intake calendar months (1-12), e.g. (10,) for October",
    )
    academic_year_start_month: Optional[int] = Field(default=None, ge=1, le=12, description="Academic year start month")
    academic_year_end_month: Optional[int] = Field(default=None, ge=1, le=12, description="Academic year completion month")
    semester_count: int = Field(default=2, ge=1, le=4, description="Standard semesters per academic year")

    @model_validator(mode="after")
    def validate_months(self) -> CalendarWindowValue:
        for m in self.intake_months:
            if m < 1 or m > 12:
                raise ValueError(f"Intake month {m} is invalid; must be between 1 and 12.")
        return self


class AgeWindowValue(BaseModel):
    """Typed constraint payload for TYPICAL_AGE_WINDOW rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_age: Optional[int] = Field(default=None, ge=0, description="Minimum typical entry or milestone age")
    max_age: Optional[int] = Field(default=None, ge=0, description="Maximum typical entry or milestone age")
    typical_age: Optional[int] = Field(default=None, ge=0, description="Standard median entry or milestone age")

    @model_validator(mode="after")
    def validate_age_bounds(self) -> AgeWindowValue:
        if self.min_age is not None and self.max_age is not None:
            if self.min_age > self.max_age:
                raise ValueError(f"min_age ({self.min_age}) cannot be greater than max_age ({self.max_age}).")
        return self


class StagePrecedenceValue(BaseModel):
    """Typed constraint payload for STAGE_PRECEDENCE rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    required_preceding_stage: LifeStage = Field(..., description="Stage that must be completed prior")
    target_stage: LifeStage = Field(..., description="Stage that requires the preceding stage")
    minimum_gap_months: int = Field(default=0, ge=0, description="Minimum required transition gap in months")
    maximum_gap_months: Optional[int] = Field(default=None, ge=0, description="Optional maximum transition gap")
    applicable_pathways: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Specific pathways this precedence constraint applies to. Empty tuple indicates general/unrestricted.",
    )


ConstraintPayload = Union[
    DurationBoundValue,
    CalendarWindowValue,
    AgeWindowValue,
    StagePrecedenceValue,
]


# =============================================================================
# TemporalRuleItem Schema
# =============================================================================

class TemporalRuleItem(BaseModel):
    """Immutable domain item representing a structured World Temporal Rule (Phase 8B.2).

    Hard Invariants (Constitutional Invariant F & Gate Semantics):
    - World Temporal Rule != Personal Fact.
    - A temporal rule is an evaluative constraint for TCG, NEVER copied directly
      into CharacterCore or CharacterBiographyRecord as personal ground truth.
    - Advisory & local constraint: Represents known or typical institutional/system
      patterns, avoiding absolute assertions of universal certainty.
    - Scoped Hard Rejection Semantics (Lock 3): `is_hard_rejection = True` denotes that
      violating this constraint rejects the candidate trajectory *under its applicable
      pathway/institution scope*. It does NOT assert universal impossibility in all realities.
    - UNKNOWN Preservation (Lock 4): Insufficient information (e.g. unknown pathway/institution)
      does not match scoped rules (UNKNOWN != wildcard, UNKNOWN != false).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(..., description="Unique rule identifier, e.g. 'RULE_MY_STPM_DURATION'")
    domain: str = Field(default="education", description="Domain classification, e.g. 'education'")
    subject: str = Field(..., description="Subject of the rule, e.g. 'stpm', 'usm', 'spm'")
    constraint_type: TemporalConstraintType = Field(..., description="Categorical constraint mechanism")
    scope: TemporalRuleScope = Field(..., description="Applicability scope")
    scope_target: Optional[str] = Field(default=None, description="Specific country, institution, or pathway code")
    constraint_value: ConstraintPayload = Field(..., description="Typed constraint payload")
    description: str = Field(default="", description="Human-readable explanation of constraint semantics")
    provenance_source: str = Field(default="MALAYSIAN_MOHE_BASELINE", description="Authority or guideline origin")
    is_hard_rejection: bool = Field(
        default=False,
        description=(
            "If True, violating this constraint means the trajectory violates an applicable scoped "
            "temporal rule under its designated pathway/institution. It does NOT mean the trajectory "
            "is universally impossible in all realities (e.g. Pre-U precedence is a hard constraint "
            "for Pre-U entrants, but not for Diploma entrants). If False, the rule represents an "
            "advisory or typical sociological/institutional prior."
        ),
    )

    def applies_to_pathway(self, pathway: Optional[str]) -> bool:
        """Check if this temporal rule applies to the specified education pathway.

        Semantics (Lock 3 & Lock 4):
        - If pathway is None: A pathway-scoped rule does NOT match unrecorded/unknown
          pathways (UNKNOWN != wildcard, UNKNOWN != false). General academic rules without
          pathway restrictions apply generally.
        - If pathway is specified: Evaluated against applicable_pathways (if defined on
          StagePrecedenceValue) or scope_target (for PATHWAY_SPECIFIC rules).
        """
        if isinstance(self.constraint_value, StagePrecedenceValue) and self.constraint_value.applicable_pathways:
            if not pathway:
                return False
            norm_p = pathway.strip().upper()
            return norm_p in (p.strip().upper() for p in self.constraint_value.applicable_pathways)

        if self.scope == TemporalRuleScope.PATHWAY_SPECIFIC:
            if not pathway or not self.scope_target:
                return False
            return pathway.strip().upper() == self.scope_target.strip().upper()

        return True

    def applies_to_institution(self, institution_ref: Optional[str]) -> bool:
        """Check if this temporal rule applies to the specified institution.

        Semantics (Lock 3, Lock 4 & Lock 6):
        - If rule is INSTITUTION_SPECIFIC: Requires exact match with institution_ref.
          If institution_ref is None or empty, returns False (does not match unrecorded/unknown).
        - If rule is NOT INSTITUTION_SPECIFIC: Applies generally across institutions
          within its domain/system scope.
        """
        if self.scope == TemporalRuleScope.INSTITUTION_SPECIFIC:
            if not institution_ref or not self.scope_target:
                return False
            return institution_ref.strip().lower() == self.scope_target.strip().lower()
        return True


# =============================================================================
# TemporalRuleRegistry (Typed View & Adapter over WorldKnowledgeRegistry)
# =============================================================================

class TemporalRuleRegistry:
    """Declarative typed view and adapter over WorldKnowledgeRegistry.

    Hard Architectural Invariant (Lock 2 - No Dual Store):
    - WorldKnowledgeRegistry remains the sole canonical world knowledge store.
    - TemporalRuleRegistry does NOT maintain an independent competing factual store.
    - All registration writes to WorldKnowledgeRegistry under 'world.temporal.rule.{rule_id.lower()}'.
    - All lookups, queries, and filters view items directly from WorldKnowledgeRegistry.
    """

    @classmethod
    def register(cls, rule: TemporalRuleItem, mirror_to_world_knowledge: bool = True) -> None:
        """Register a temporal rule into WorldKnowledgeRegistry under canonical key."""
        canonical_key = f"world.temporal.rule.{rule.rule_id.lower()}"
        WorldKnowledgeRegistry.register(
            key_or_item=WorldKnowledgeItem(
                key=canonical_key,
                value=rule.model_dump(),
                kind=KnowledgeKind.TEMPORAL_RULE,
                description=rule.description,
                domain_category=rule.domain,
            )
        )
        if mirror_to_world_knowledge:
            # Maintain backward compatibility with legacy alias
            WorldKnowledgeRegistry.register(
                key_or_item=WorldKnowledgeItem(
                    key=f"temporal.rule.{rule.rule_id.lower()}",
                    value=rule.model_dump(),
                    kind=KnowledgeKind.TEMPORAL_RULE,
                    description=rule.description,
                    domain_category=rule.domain,
                )
            )

    @classmethod
    def _parse_item(cls, item: WorldKnowledgeItem) -> Optional[TemporalRuleItem]:
        """Convert a WorldKnowledgeItem to a typed TemporalRuleItem."""
        if item.kind != KnowledgeKind.TEMPORAL_RULE:
            return None
        if isinstance(item.value, TemporalRuleItem):
            return item.value
        if isinstance(item.value, dict):
            return TemporalRuleItem.model_validate(item.value)
        return None

    @classmethod
    def get(cls, rule_id: str) -> Optional[TemporalRuleItem]:
        """Look up a temporal rule by its unique rule_id via WorldKnowledgeRegistry."""
        canonical_key = f"world.temporal.rule.{rule_id.lower()}"
        item = WorldKnowledgeRegistry.lookup(canonical_key)
        if item is None:
            item = WorldKnowledgeRegistry.lookup(f"temporal.rule.{rule_id.lower()}")
        if item is None:
            return None
        return cls._parse_item(item)

    @classmethod
    def all_rules(cls) -> tuple[TemporalRuleItem, ...]:
        """Return all registered temporal rules in deterministic sorted order via WorldKnowledgeRegistry."""
        rules_by_id: dict[str, TemporalRuleItem] = {}
        for item in WorldKnowledgeRegistry._REGISTRY.values():
            if item.kind == KnowledgeKind.TEMPORAL_RULE and item.key.startswith("world.temporal.rule."):
                rule = cls._parse_item(item)
                if rule is not None:
                    rules_by_id[rule.rule_id] = rule
        return tuple(sorted(rules_by_id.values(), key=lambda r: r.rule_id))

    @classmethod
    def count(cls) -> int:
        """Return the number of unique registered temporal rules in WorldKnowledgeRegistry."""
        return len(cls.all_rules())

    @classmethod
    def find_rules(
        cls,
        domain: Optional[str] = None,
        subject: Optional[str] = None,
        scope: Optional[TemporalRuleScope] = None,
        constraint_type: Optional[TemporalConstraintType] = None,
    ) -> tuple[TemporalRuleItem, ...]:
        """Query rules matching specified filtering criteria via WorldKnowledgeRegistry."""
        results: list[TemporalRuleItem] = []
        for rule in cls.all_rules():
            if domain is not None and rule.domain != domain:
                continue
            if subject is not None and rule.subject != subject:
                continue
            if scope is not None and rule.scope != scope:
                continue
            if constraint_type is not None and rule.constraint_type != constraint_type:
                continue
            results.append(rule)
        return tuple(sorted(results, key=lambda r: r.rule_id))

    @classmethod
    def clear(cls) -> None:
        """Clear temporal rule entries from WorldKnowledgeRegistry (used in test isolation)."""
        keys_to_remove = [
            k
            for k, v in WorldKnowledgeRegistry._REGISTRY.items()
            if v.kind == KnowledgeKind.TEMPORAL_RULE
            or k.startswith("world.temporal.rule.")
            or k.startswith("temporal.rule.")
        ]
        for k in keys_to_remove:
            WorldKnowledgeRegistry._REGISTRY.pop(k, None)


# =============================================================================
# Seed Authoritative Baseline Temporal Rules (Compact & High Quality)
# =============================================================================

def _seed_baseline_temporal_rules() -> None:
    """Register compact baseline temporal rules for Malaysian education and institutions."""

    # 1. SPM Typical Examination Age
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_MY_SPM_AGE",
            domain="education",
            subject="spm",
            constraint_type=TemporalConstraintType.TYPICAL_AGE_WINDOW,
            scope=TemporalRuleScope.NATIONAL_EDUCATION_SYSTEM,
            scope_target="MALAYSIA",
            constraint_value=AgeWindowValue(typical_age=17, min_age=16, max_age=19),
            description="SPM examination is typically taken in Form 5 at age 17 in the Malaysian national curriculum.",
            provenance_source="MALAYSIAN_MOE_CURRICULUM",
            is_hard_rejection=False,
        )
    )

    # 2. STPM (Form 6) Typical Duration
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_MY_STPM_DURATION",
            domain="education",
            subject="stpm",
            constraint_type=TemporalConstraintType.DURATION_BOUND,
            scope=TemporalRuleScope.PATHWAY_SPECIFIC,
            scope_target="STPM",
            constraint_value=DurationBoundValue(
                min_years=1.5,
                max_years=2.0,
                min_months=18,
                max_months=24,
                typical_years=1.5,
            ),
            description="STPM (Form 6) post-secondary pathway typically spans 1.5 to 2.0 years across 3 semesters.",
            provenance_source="MALAYSIAN_EXAMINATIONS_COUNCIL_MPM",
            is_hard_rejection=False,
        )
    )

    # 3. Matrikulasi Typical Duration
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_MY_MATRIKULASI_DURATION",
            domain="education",
            subject="matrikulasi",
            constraint_type=TemporalConstraintType.DURATION_BOUND,
            scope=TemporalRuleScope.PATHWAY_SPECIFIC,
            scope_target="MATRIKULASI",
            constraint_value=DurationBoundValue(
                min_years=1.0,
                max_years=2.0,
                min_months=12,
                max_months=24,
                typical_years=1.0,
            ),
            description="Malaysian Matriculation programme typically spans 1 year (PST) or 2 years (PDT).",
            provenance_source="MALAYSIAN_MOE_MATRICULATION",
            is_hard_rejection=False,
        )
    )

    # 4. University Foundation (Asasi) Typical Duration
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_MY_FOUNDATION_DURATION",
            domain="education",
            subject="foundation",
            constraint_type=TemporalConstraintType.DURATION_BOUND,
            scope=TemporalRuleScope.PATHWAY_SPECIFIC,
            scope_target="FOUNDATION",
            constraint_value=DurationBoundValue(
                min_years=1.0,
                max_years=1.5,
                min_months=12,
                max_months=18,
                typical_years=1.0,
            ),
            description="University Foundation (Asasi) pre-university programmes typically span 1.0 to 1.5 years.",
            provenance_source="MALAYSIAN_MOHE_BASELINE",
            is_hard_rejection=False,
        )
    )

    # 5. Diploma Typical Duration
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_MY_DIPLOMA_DURATION",
            domain="education",
            subject="diploma",
            constraint_type=TemporalConstraintType.DURATION_BOUND,
            scope=TemporalRuleScope.PATHWAY_SPECIFIC,
            scope_target="DIPLOMA",
            constraint_value=DurationBoundValue(
                min_years=2.0,
                max_years=3.0,
                min_months=24,
                max_months=36,
                typical_years=2.5,
            ),
            description="Diploma programmes typically span 2.0 to 3.0 years.",
            provenance_source="MALAYSIAN_MQA_FRAMEWORK",
            is_hard_rejection=False,
        )
    )

    # 6. Undergraduate Bachelor's Degree Typical Duration
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_MY_DEGREE_DURATION",
            domain="education",
            subject="undergraduate_degree",
            constraint_type=TemporalConstraintType.DURATION_BOUND,
            scope=TemporalRuleScope.GENERAL_ACADEMIC,
            scope_target="BACHELOR_DEGREE",
            constraint_value=DurationBoundValue(
                min_years=3.0,
                max_years=5.0,
                min_months=36,
                max_months=60,
                typical_years=4.0,
            ),
            description="Malaysian undergraduate bachelor's degree programmes typically span 3 to 4 years (up to 5 for engineering/medicine).",
            provenance_source="MALAYSIAN_MQA_FRAMEWORK",
            is_hard_rejection=False,
        )
    )

    # 7. USM Typical Undergraduate Intake Window (Advisory / Institutional Window)
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_USM_INTAKE_WINDOW",
            domain="education",
            subject="usm",
            constraint_type=TemporalConstraintType.TYPICAL_CALENDAR_WINDOW,
            scope=TemporalRuleScope.INSTITUTION_SPECIFIC,
            scope_target="world.usm.main_campus",
            constraint_value=CalendarWindowValue(
                intake_months=(10,),
                academic_year_start_month=10,
                academic_year_end_month=7,
                semester_count=2,
            ),
            description="Universiti Sains Malaysia typical annual main undergraduate intake occurs in October.",
            provenance_source="USM_ACADEMIC_CALENDAR_BASELINE",
            is_hard_rejection=False,
        )
    )

    # 8. Malaysian Public University Undergraduate Entry Age Window
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_MY_UNDERGRAD_ENTRY_AGE",
            domain="education",
            subject="undergraduate_entry",
            constraint_type=TemporalConstraintType.TYPICAL_AGE_WINDOW,
            scope=TemporalRuleScope.NATIONAL_EDUCATION_SYSTEM,
            scope_target="MALAYSIA",
            constraint_value=AgeWindowValue(typical_age=19, min_age=18, max_age=23),
            description="Typical university undergraduate entry age ranges from 19 to 21 (up to 23 with gap/diploma).",
            provenance_source="MALAYSIAN_MOHE_BASELINE",
            is_hard_rejection=False,
        )
    )

    # 9. Stage Precedence: Secondary Education -> Pre-University (STPM, Matrikulasi, Foundation)
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_PRECEDENCE_SECONDARY_TO_PRE_U",
            domain="education",
            subject="stage_precedence",
            constraint_type=TemporalConstraintType.STAGE_PRECEDENCE,
            scope=TemporalRuleScope.PATHWAY_SPECIFIC,
            scope_target="PRE_U_PATHWAYS",
            constraint_value=StagePrecedenceValue(
                required_preceding_stage=LifeStage.SECONDARY_EDUCATION,
                target_stage=LifeStage.PRE_UNIVERSITY,
                minimum_gap_months=0,
                maximum_gap_months=36,
                applicable_pathways=("STPM", "MATRIKULASI", "FOUNDATION"),
            ),
            description="Secondary education completion must precede entrance to Pre-University programmes (STPM, Matrikulasi, Foundation).",
            provenance_source="MALAYSIAN_MQA_FRAMEWORK",
            is_hard_rejection=True,
        )
    )

    # 10. Stage Precedence: Pre-University -> Undergraduate (Pre-U Pathways)
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD",
            domain="education",
            subject="stage_precedence",
            constraint_type=TemporalConstraintType.STAGE_PRECEDENCE,
            scope=TemporalRuleScope.PATHWAY_SPECIFIC,
            scope_target="PRE_U_PATHWAYS",
            constraint_value=StagePrecedenceValue(
                required_preceding_stage=LifeStage.PRE_UNIVERSITY,
                target_stage=LifeStage.UNDERGRADUATE,
                minimum_gap_months=0,
                maximum_gap_months=48,
                applicable_pathways=("STPM", "MATRIKULASI", "FOUNDATION"),
            ),
            description="Pre-University programme completion must precede entrance to Undergraduate Degree programmes for Pre-U pathways (STPM, Matrikulasi, Foundation).",
            provenance_source="MALAYSIAN_MQA_FRAMEWORK",
            is_hard_rejection=True,
        )
    )

    # 11. Stage Precedence: Secondary Education -> Diploma
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_PRECEDENCE_SECONDARY_TO_DIPLOMA",
            domain="education",
            subject="stage_precedence",
            constraint_type=TemporalConstraintType.STAGE_PRECEDENCE,
            scope=TemporalRuleScope.PATHWAY_SPECIFIC,
            scope_target="DIPLOMA",
            constraint_value=StagePrecedenceValue(
                required_preceding_stage=LifeStage.SECONDARY_EDUCATION,
                target_stage=LifeStage.DIPLOMA,
                minimum_gap_months=0,
                maximum_gap_months=36,
                applicable_pathways=("DIPLOMA",),
            ),
            description="Secondary education completion must precede entrance to Diploma programmes.",
            provenance_source="MALAYSIAN_MQA_FRAMEWORK",
            is_hard_rejection=True,
        )
    )

    # 12. Stage Precedence: Diploma -> Undergraduate
    TemporalRuleRegistry.register(
        TemporalRuleItem(
            rule_id="RULE_PRECEDENCE_DIPLOMA_TO_UNDERGRAD",
            domain="education",
            subject="stage_precedence",
            constraint_type=TemporalConstraintType.STAGE_PRECEDENCE,
            scope=TemporalRuleScope.PATHWAY_SPECIFIC,
            scope_target="DIPLOMA",
            constraint_value=StagePrecedenceValue(
                required_preceding_stage=LifeStage.DIPLOMA,
                target_stage=LifeStage.UNDERGRADUATE,
                minimum_gap_months=0,
                maximum_gap_months=60,
                applicable_pathways=("DIPLOMA",),
            ),
            description="Diploma completion must precede entrance to Undergraduate Degree programmes for Diploma holders (often with advanced standing).",
            provenance_source="MALAYSIAN_MQA_FRAMEWORK",
            is_hard_rejection=True,
        )
    )


# Execute declarative registration at module import
_seed_baseline_temporal_rules()
