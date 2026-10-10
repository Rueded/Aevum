"""Temporal Constraint Graph (TCG) & Constraint Evaluation (Phase 8B.3).

Architectural Principles & Constitutional Invariants (Phase 8B.3):
1. Invariant D (Reasoning Structure, Not a Fact Store): The TCG is an ephemeral
   in-memory graph representing temporal relationships and evaluating scoped rules.
   Zero direct database writes, zero ORM, zero mutation authority.
2. Invariant C (Projection is Never Canonical Reality): Future projected nodes
   carry EpistemicGrounding.PROJECTED and Canonicality.NON_CANONICAL. They can never
   enter canonical reality or mutate CharacterCore.
3. Invariant E (Bounded Propagation & Cardinality): Bounded propagation depth
   (MAX_TEMPORAL_PROPAGATION_HOPS = 2). Cardinality bounded by MAX_PROJECTED_NODES = 4.
   Projected nodes cannot recursively serve as origins for further projection.
4. Invariant F (World Temporal Rules != Personal Temporal Facts): World rules are
   evaluative constraints, never copied as personal core facts.
5. Tri-State Constraint Logic: All evaluations produce SATISFIED, VIOLATED, or
   UNDETERMINED. UNKNOWN temporal information yields UNDETERMINED, NEVER VIOLATED.
   (UNKNOWN != wildcard, UNKNOWN != false, UNKNOWN != impossible).
6. Scoped Hard Rejection: Hard rule rejection is strictly scoped to applicable
   pathway / institution. Violation != personal contradiction; TCG produces
   structured findings, never triggers biography repair or canonical mutation.
7. Zero Network / Zero LLM / Zero DB: Pure deterministic symbolic reasoning.
"""

from __future__ import annotations

from datetime import date
import enum
from typing import Any, Optional, Sequence, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.reality.temporal_models import (
    MAX_PROJECTED_NODES,
    MAX_TEMPORAL_PROPAGATION_HOPS,
    Canonicality,
    EpistemicGrounding,
    LifeStage,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
    validate_epistemic_canonicality_combination,
)
from app.reality.temporal_rules import (
    AgeWindowValue,
    CalendarWindowValue,
    DurationBoundValue,
    StagePrecedenceValue,
    TemporalConstraintType,
    TemporalRuleItem,
    TemporalRuleRegistry,
    TemporalRuleScope,
)


# =============================================================================
# Categorical Enums: Relations & Tri-State Evaluation Status
# =============================================================================

class TemporalRelationType(str, enum.Enum):
    """Deterministic temporal edge relations between graph nodes."""

    BEFORE = "BEFORE"                      # Source interval ends before Target starts
    AFTER = "AFTER"                        # Source interval starts after Target ends
    CONTAINS = "CONTAINS"                  # Source interval completely encapsulates Target
    OVERLAPS = "OVERLAPS"                  # Source and Target have non-empty intersection
    DURING = "DURING"                      # Source interval is strictly within Target
    PRECEDES_STAGE = "PRECEDES_STAGE"      # Developmental stage progression prerequisite
    CONSTRAINS_START = "CONSTRAINS_START"  # Source start boundary constrains Target start
    CONSTRAINS_END = "CONSTRAINS_END"      # Source end boundary constrains Target end


class ConstraintStatus(str, enum.Enum):
    """Tri-state constraint evaluation outcome (Crucial: Not binary boolean).

    - SATISFIED: Known temporal evidence unambiguously complies with the rule.
    - VIOLATED: Known temporal evidence directly contradicts the applicable rule.
    - UNDETERMINED: Temporal evidence is UNKNOWN or insufficient to confirm/deny.
    """

    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"
    UNDETERMINED = "UNDETERMINED"


# =============================================================================
# Domain Models: TemporalNode & TemporalEdge
# =============================================================================

class TemporalNode(BaseModel):
    """Immutable in-memory node representing a life state, milestone, or event in TCG.

    Constitutional Constraints:
    - Immutable (frozen=True, extra="forbid").
    - Propagation depth strictly <= MAX_TEMPORAL_PROPAGATION_HOPS (2).
    - Future projected nodes must carry PROJECTED / UNKNOWN and NON_CANONICAL.
    - Provenance: origin_fact_key, propagation_depth, constraint_chain preserved.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str = Field(..., description="Deterministic unique identifier for this node")
    label: str = Field(default="", description="Descriptive label (e.g. 'Degree Studies')")
    stage: Optional[LifeStage] = Field(default=None, description="Categorical developmental stage")
    interval: TemporalInterval = Field(
        default_factory=TemporalInterval.create_unknown,
        description="Temporal boundary interval",
    )
    temporal_horizon: TemporalHorizon = Field(
        default=TemporalHorizon.PRESENT,
        description="Temporal direction relative to current turn",
    )
    epistemic_grounding: EpistemicGrounding = Field(
        default=EpistemicGrounding.DERIVED,
        description="Evidence origin and grounding classification",
    )
    canonicality: Canonicality = Field(
        default=Canonicality.NON_CANONICAL,
        description="Canonical authority status (PROJECTED/DERIVED cannot be CANONICAL)",
    )
    institution_ref: Optional[str] = Field(default=None, description="Reference to WorldKnowledge institution")
    pathway: Optional[str] = Field(default=None, description="Educational pathway (e.g. 'STPM', 'DIPLOMA')")
    origin_fact_key: Optional[str] = Field(default=None, description="Canonical core fact triggering this node")
    origin_node_id: Optional[str] = Field(default=None, description="Parent node ID if derived/projected")
    propagation_depth: int = Field(
        default=0,
        ge=0,
        le=MAX_TEMPORAL_PROPAGATION_HOPS,
        description="Derivation hop depth from authoritative origin fact (max 2)",
    )
    constraint_chain: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Tuple of rule IDs applied to derive/project this node",
    )

    @model_validator(mode="after")
    def validate_node_invariants(self) -> TemporalNode:
        """Enforce constitutional epistemic and projection invariants."""
        # 1. Epistemic-Canonicality Combination Matrix
        validate_epistemic_canonicality_combination(self.epistemic_grounding, self.canonicality)

        # 2. Future nodes must carry PROJECTED or UNKNOWN grounding
        if self.temporal_horizon == TemporalHorizon.FUTURE:
            if self.epistemic_grounding not in (EpistemicGrounding.PROJECTED, EpistemicGrounding.UNKNOWN):
                raise ValueError(
                    f"Future nodes must have EpistemicGrounding.PROJECTED or UNKNOWN, "
                    f"got {self.epistemic_grounding.value}. Future cannot be observed or confirmed."
                )

        # 3. Projected nodes must be NON_CANONICAL
        if self.epistemic_grounding == EpistemicGrounding.PROJECTED:
            if self.canonicality != Canonicality.NON_CANONICAL:
                raise ValueError(
                    "Projected temporal nodes must strictly carry Canonicality.NON_CANONICAL."
                )

        return self


class TemporalEdge(BaseModel):
    """Immutable directed edge representing a temporal relationship or constraint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_id: str = Field(..., description="Deterministic unique identifier for this edge")
    source_node_id: str = Field(..., description="Origin node identifier")
    target_node_id: str = Field(..., description="Destination node identifier")
    relation: TemporalRelationType = Field(..., description="Categorical temporal relationship")
    rule_id: Optional[str] = Field(default=None, description="TemporalRuleItem ID establishing this constraint")
    description: str = Field(default="", description="Human-readable context of the relationship")


# =============================================================================
# Ephemeral Temporal Constraint Graph (TCG)
# =============================================================================

class TemporalConstraintGraph:
    """Ephemeral, deterministic Temporal Constraint Graph (TCG) for temporal reasoning.

    Constitutional Invariants:
    - Pure in-memory reasoning structure: zero database persistence, zero ORM.
    - Cardinality bounded by MAX_PROJECTED_NODES (4).
    - Recursive projection forbidden: Projected nodes cannot serve as inputs to
      generate further projected nodes.
    - Deterministic ordering: Nodes and edges always returned in sorted order.
    """

    def __init__(
        self,
        nodes: Optional[Sequence[TemporalNode]] = None,
        edges: Optional[Sequence[TemporalEdge]] = None,
    ) -> None:
        self._nodes: dict[str, TemporalNode] = {}
        self._edges: dict[str, TemporalEdge] = {}

        if nodes:
            for n in nodes:
                self.add_node(n)
        if edges:
            for e in edges:
                self.add_edge(e)

    # -------------------------------------------------------------------------
    # Node Management & Cardinality Bounds
    # -------------------------------------------------------------------------

    def add_node(self, node: TemporalNode) -> TemporalNode:
        """Add an immutable node to the graph while validating cardinality and recursion bounds."""
        # 1. Check if node is PROJECTED and enforces MAX_PROJECTED_NODES
        if node.epistemic_grounding == EpistemicGrounding.PROJECTED:
            current_projected = [
                n for nid, n in self._nodes.items()
                if n.epistemic_grounding == EpistemicGrounding.PROJECTED and nid != node.node_id
            ]
            if len(current_projected) >= MAX_PROJECTED_NODES:
                raise ValueError(
                    f"Cannot add projected node '{node.node_id}': MAX_PROJECTED_NODES "
                    f"bound ({MAX_PROJECTED_NODES}) reached. Ambiguity must be bounded."
                )

            # 2. Check recursive projection: Projected nodes cannot serve as origin for further projection
            if node.origin_node_id and node.origin_node_id in self._nodes:
                parent_node = self._nodes[node.origin_node_id]
                if parent_node.epistemic_grounding == EpistemicGrounding.PROJECTED:
                    raise ValueError(
                        f"Recursive projection forbidden: Projected node '{node.node_id}' cannot "
                        f"have projected node '{parent_node.node_id}' as its origin."
                    )

        self._nodes[node.node_id] = node
        return node

    def add_edge(self, edge: TemporalEdge) -> TemporalEdge:
        """Add an immutable directed edge between existing nodes."""
        if edge.source_node_id not in self._nodes:
            raise ValueError(f"Source node '{edge.source_node_id}' not found in graph.")
        if edge.target_node_id not in self._nodes:
            raise ValueError(f"Target node '{edge.target_node_id}' not found in graph.")

        self._edges[edge.edge_id] = edge
        return edge

    def get_node(self, node_id: str) -> Optional[TemporalNode]:
        """Look up a node by its deterministic identifier."""
        return self._nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[TemporalEdge]:
        """Look up an edge by its deterministic identifier."""
        return self._edges.get(edge_id)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def projected_node_count(self) -> int:
        return sum(
            1 for n in self._nodes.values()
            if n.epistemic_grounding == EpistemicGrounding.PROJECTED
        )

    def all_nodes(self) -> tuple[TemporalNode, ...]:
        """Return all nodes in deterministic sorted order by node_id."""
        return tuple(sorted(self._nodes.values(), key=lambda n: n.node_id))

    def all_edges(self) -> tuple[TemporalEdge, ...]:
        """Return all edges in deterministic sorted order by edge_id."""
        return tuple(sorted(self._edges.values(), key=lambda e: e.edge_id))


# =============================================================================
# Structured Evaluation Result
# =============================================================================

class ConstraintEvaluationResult(BaseModel):
    """Structured evaluation finding produced by evaluating a temporal constraint in TCG.

    Constitutional Invariant:
    - Non-authoritative finding: Produces an epistemic evaluation result without
      triggering database mutation, fact promotion, or biography repair.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(..., description="Unique rule or constraint identifier")
    status: ConstraintStatus = Field(..., description="SATISFIED, VIOLATED, or UNDETERMINED")
    target_node_ids: tuple[str, ...] = Field(..., description="Node identifiers involved in this evaluation")
    explanation: str = Field(default="", description="Deterministic explanation of evaluation rationale")
    is_hard_rejection: bool = Field(
        default=False,
        description="True if an applicable hard constraint was violated (scoped to pathway/institution)",
    )


STAGE_PROGRESSION_RANK: dict[LifeStage, int] = {
    LifeStage.PRIMARY_EDUCATION: 1,
    LifeStage.SECONDARY_EDUCATION: 2,
    LifeStage.PRE_UNIVERSITY: 3,
    LifeStage.DIPLOMA: 3,
    LifeStage.UNDERGRADUATE: 4,
    LifeStage.INTERNSHIP: 5,
    LifeStage.POSTGRADUATE: 6,
    LifeStage.EARLY_CAREER: 7,
    LifeStage.CAREER: 8,
    LifeStage.TRANSITIONAL: 9,
}


# =============================================================================
# Deterministic Constraint Evaluation Engine
# =============================================================================

class TemporalConstraintEvaluator:
    """Evaluates scoped temporal rules and graph relationships deterministically.

    Tri-State Semantics:
    - SATISFIED: Known facts confirm compliance.
    - VIOLATED: Known facts contradict applicable constraint.
    - UNDETERMINED: Incomplete/UNKNOWN facts prevent definitive evaluation.
      (Never convert UNKNOWN into VIOLATED or SATISFIED).
    """

    @classmethod
    def evaluate_edge_relation(
        cls,
        graph: TemporalConstraintGraph,
        edge: TemporalEdge,
    ) -> ConstraintEvaluationResult:
        """Evaluate the temporal ordering relationship expressed by an edge."""
        source = graph.get_node(edge.source_node_id)
        target = graph.get_node(edge.target_node_id)

        if not source or not target:
            return ConstraintEvaluationResult(
                rule_id=edge.edge_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(edge.source_node_id, edge.target_node_id),
                explanation="Missing source or target node in graph.",
            )

        src_int = source.interval
        tgt_int = target.interval

        # UNKNOWN Semantics: If either interval is unknown, ordering is UNDETERMINED
        if src_int.is_unknown() or tgt_int.is_unknown():
            return ConstraintEvaluationResult(
                rule_id=edge.edge_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(source.node_id, target.node_id),
                explanation="Interval boundaries unknown; temporal relation is undetermined.",
            )

        rel = edge.relation

        if rel in (TemporalRelationType.BEFORE, TemporalRelationType.PRECEDES_STAGE):
            # Source must end before (or at) Target start
            if src_int.latest_end is not None and tgt_int.earliest_start is not None:
                if src_int.latest_end <= tgt_int.earliest_start:
                    return ConstraintEvaluationResult(
                        rule_id=edge.edge_id,
                        status=ConstraintStatus.SATISFIED,
                        target_node_ids=(source.node_id, target.node_id),
                        explanation=f"Source ends by {src_int.latest_end} before Target starts at {tgt_int.earliest_start}.",
                    )
                if src_int.earliest_start is not None and tgt_int.latest_end is not None:
                    if src_int.earliest_start > tgt_int.latest_end:
                        return ConstraintEvaluationResult(
                            rule_id=edge.edge_id,
                            status=ConstraintStatus.VIOLATED,
                            target_node_ids=(source.node_id, target.node_id),
                            explanation=f"Source start ({src_int.earliest_start}) is after Target end ({tgt_int.latest_end}).",
                            is_hard_rejection=True,
                        )
            return ConstraintEvaluationResult(
                rule_id=edge.edge_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(source.node_id, target.node_id),
                explanation="Interval boundaries overlap or lack sufficient precision to confirm strict precedence.",
            )

        if rel == TemporalRelationType.AFTER:
            # Source must start after Target ends
            if src_int.earliest_start is not None and tgt_int.latest_end is not None:
                if src_int.earliest_start >= tgt_int.latest_end:
                    return ConstraintEvaluationResult(
                        rule_id=edge.edge_id,
                        status=ConstraintStatus.SATISFIED,
                        target_node_ids=(source.node_id, target.node_id),
                        explanation=f"Source starts at {src_int.earliest_start} after Target ends at {tgt_int.latest_end}.",
                    )
                if src_int.latest_end is not None and tgt_int.earliest_start is not None:
                    if src_int.latest_end < tgt_int.earliest_start:
                        return ConstraintEvaluationResult(
                            rule_id=edge.edge_id,
                            status=ConstraintStatus.VIOLATED,
                            target_node_ids=(source.node_id, target.node_id),
                            explanation=f"Source ends ({src_int.latest_end}) before Target starts ({tgt_int.earliest_start}).",
                            is_hard_rejection=True,
                        )
            return ConstraintEvaluationResult(
                rule_id=edge.edge_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(source.node_id, target.node_id),
                explanation="Interval boundaries lack precision to confirm AFTER relation.",
            )

        if rel == TemporalRelationType.CONTAINS:
            if (
                src_int.earliest_start is not None
                and src_int.latest_end is not None
                and tgt_int.earliest_start is not None
                and tgt_int.latest_end is not None
            ):
                if src_int.earliest_start <= tgt_int.earliest_start and src_int.latest_end >= tgt_int.latest_end:
                    return ConstraintEvaluationResult(
                        rule_id=edge.edge_id,
                        status=ConstraintStatus.SATISFIED,
                        target_node_ids=(source.node_id, target.node_id),
                        explanation="Source bounds fully contain Target bounds.",
                    )
                if src_int.latest_end < tgt_int.earliest_start or src_int.earliest_start > tgt_int.latest_end:
                    return ConstraintEvaluationResult(
                        rule_id=edge.edge_id,
                        status=ConstraintStatus.VIOLATED,
                        target_node_ids=(source.node_id, target.node_id),
                        explanation="Source and Target intervals are disjoint.",
                        is_hard_rejection=True,
                    )
            return ConstraintEvaluationResult(
                rule_id=edge.edge_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(source.node_id, target.node_id),
                explanation="Interval boundaries lack precision to confirm CONTAINS relation.",
            )

        if rel == TemporalRelationType.OVERLAPS:
            if src_int.overlaps(tgt_int):
                return ConstraintEvaluationResult(
                    rule_id=edge.edge_id,
                    status=ConstraintStatus.SATISFIED,
                    target_node_ids=(source.node_id, target.node_id),
                    explanation="Source and Target intervals unambiguously overlap.",
                )
            # If definitely disjoint
            if (
                src_int.latest_end is not None
                and tgt_int.earliest_start is not None
                and src_int.latest_end < tgt_int.earliest_start
            ) or (
                tgt_int.latest_end is not None
                and src_int.earliest_start is not None
                and tgt_int.latest_end < src_int.earliest_start
            ):
                return ConstraintEvaluationResult(
                    rule_id=edge.edge_id,
                    status=ConstraintStatus.VIOLATED,
                    target_node_ids=(source.node_id, target.node_id),
                    explanation="Source and Target intervals are strictly disjoint.",
                )
            return ConstraintEvaluationResult(
                rule_id=edge.edge_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(source.node_id, target.node_id),
                explanation="Overlap cannot be confirmed with available interval precision.",
            )

        return ConstraintEvaluationResult(
            rule_id=edge.edge_id,
            status=ConstraintStatus.UNDETERMINED,
            target_node_ids=(source.node_id, target.node_id),
            explanation=f"Relation '{rel.value}' evaluated as undetermined.",
        )

    @classmethod
    def evaluate_duration_bound(
        cls,
        node: TemporalNode,
        rule: TemporalRuleItem,
    ) -> ConstraintEvaluationResult:
        """Evaluate a DURATION_BOUND rule against a node."""
        if not isinstance(rule.constraint_value, DurationBoundValue):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(node.node_id,),
                explanation="Rule constraint payload is not DurationBoundValue.",
            )

        rule_stage_map: dict[str, LifeStage] = {
            "stpm": LifeStage.PRE_UNIVERSITY,
            "matrikulasi": LifeStage.PRE_UNIVERSITY,
            "foundation": LifeStage.PRE_UNIVERSITY,
            "diploma": LifeStage.DIPLOMA,
            "undergraduate_degree": LifeStage.UNDERGRADUATE,
        }
        expected_stage = rule_stage_map.get(rule.subject)
        if expected_stage is not None and node.stage != expected_stage:
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(node.node_id,),
                explanation=f"Rule '{rule.rule_id}' stage scope ({expected_stage.value}) does not match node stage '{node.stage}'.",
            )

        # Pathway Scope Check: If rule is pathway-scoped and node's pathway does not match
        if not rule.applies_to_pathway(node.pathway):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(node.node_id,),
                explanation=f"Rule '{rule.rule_id}' pathway scope does not apply to node pathway '{node.pathway}'.",
            )

        bounds = rule.constraint_value

        # Single-point / intake granularity check:
        # A node with MONTH or APPROXIMATE_YEAR granularity specifies a single point/milestone (intake or graduation),
        # not the completed multi-year duration of the whole stage.
        if (
            node.interval.granularity in (TemporalGranularity.MONTH, TemporalGranularity.APPROXIMATE_YEAR)
            and bounds.min_years is not None
            and bounds.min_years > 1.05
        ):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(node.node_id,),
                explanation="Node specifies single point/milestone; multi-year stage duration is undetermined.",
            )

        # UNKNOWN Semantics: If interval is unknown or has no start/end
        if (
            node.interval.is_unknown()
            or node.interval.earliest_start is None
            or node.interval.latest_end is None
        ):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(node.node_id,),
                explanation="Node duration is undetermined due to missing or unknown boundary dates.",
            )

        start = node.interval.earliest_start
        end = node.interval.latest_end

        if start > end:
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.VIOLATED,
                target_node_ids=(node.node_id,),
                explanation=f"Negative duration: start ({start}) is after end ({end}).",
                is_hard_rejection=True,
            )

        # Calculate calendar duration in years and months
        year_span = (end.year - start.year) + (end.month - start.month) / 12.0 + (end.day - start.day) / 365.0
        month_span = (end.year - start.year) * 12 + (end.month - start.month) + (end.day - start.day) / 30.0

        bounds = rule.constraint_value

        # Check bounds with standard 0.05 year tolerance to avoid day count calendar skew
        if bounds.min_years is not None and year_span < (bounds.min_years - 0.05):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.VIOLATED,
                target_node_ids=(node.node_id,),
                explanation=f"Duration {year_span:.2f} years is below minimum {bounds.min_years} years.",
                is_hard_rejection=rule.is_hard_rejection,
            )

        if bounds.max_years is not None and year_span > (bounds.max_years + 0.05):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.VIOLATED,
                target_node_ids=(node.node_id,),
                explanation=f"Duration {year_span:.2f} years exceeds maximum {bounds.max_years} years.",
                is_hard_rejection=rule.is_hard_rejection,
            )

        if bounds.min_months is not None and month_span < (bounds.min_months - 0.5):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.VIOLATED,
                target_node_ids=(node.node_id,),
                explanation=f"Duration {round(month_span)} months is below minimum {bounds.min_months} months.",
                is_hard_rejection=rule.is_hard_rejection,
            )

        if bounds.max_months is not None and month_span > (bounds.max_months + 0.5):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.VIOLATED,
                target_node_ids=(node.node_id,),
                explanation=f"Duration {round(month_span)} months exceeds maximum {bounds.max_months} months.",
                is_hard_rejection=rule.is_hard_rejection,
            )

        return ConstraintEvaluationResult(
            rule_id=rule.rule_id,
            status=ConstraintStatus.SATISFIED,
            target_node_ids=(node.node_id,),
            explanation=f"Duration {year_span:.2f} years satisfies bound constraints.",
        )

    @classmethod
    def evaluate_age_window(
        cls,
        birth_node: TemporalNode,
        target_node: TemporalNode,
        rule: TemporalRuleItem,
    ) -> ConstraintEvaluationResult:
        """Evaluate an age window constraint between a birth node and a milestone node."""
        if not isinstance(rule.constraint_value, AgeWindowValue):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(birth_node.node_id, target_node.node_id),
                explanation="Rule constraint payload is not AgeWindowValue.",
            )

        if birth_node.interval.is_unknown() or target_node.interval.is_unknown():
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(birth_node.node_id, target_node.node_id),
                explanation="Birth date or target milestone date is UNKNOWN.",
            )

        birth_date = birth_node.interval.earliest_start
        target_date = target_node.interval.earliest_start

        if not birth_date or not target_date:
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(birth_node.node_id, target_node.node_id),
                explanation="Missing specific start date for birth or milestone.",
            )

        # Compute age at milestone
        age = target_date.year - birth_date.year
        if (target_date.month, target_date.day) < (birth_date.month, birth_date.day):
            age -= 1

        bounds = rule.constraint_value

        if bounds.min_age is not None and age < bounds.min_age:
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.VIOLATED,
                target_node_ids=(birth_node.node_id, target_node.node_id),
                explanation=f"Age at milestone ({age}) is below minimum typical age ({bounds.min_age}).",
                is_hard_rejection=rule.is_hard_rejection,
            )

        if bounds.max_age is not None and age > bounds.max_age:
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.VIOLATED,
                target_node_ids=(birth_node.node_id, target_node.node_id),
                explanation=f"Age at milestone ({age}) exceeds maximum typical age ({bounds.max_age}).",
                is_hard_rejection=rule.is_hard_rejection,
            )

        return ConstraintEvaluationResult(
            rule_id=rule.rule_id,
            status=ConstraintStatus.SATISFIED,
            target_node_ids=(birth_node.node_id, target_node.node_id),
            explanation=f"Age at milestone ({age}) complies with typical age window.",
        )

    @classmethod
    def evaluate_stage_precedence(
        cls,
        graph: TemporalConstraintGraph,
        target_node: TemporalNode,
        rule: TemporalRuleItem,
    ) -> ConstraintEvaluationResult:
        """Evaluate a STAGE_PRECEDENCE rule against a target node and graph context.

        Hard Invariants (Lock 1 & Lock 5):
        - Scoped to applicable_pathways. Pre-U rule does NOT apply to Diploma pathway.
        - Diploma -> Undergraduate does NOT require Pre-U.
        - If prior history is unknown, yields UNDETERMINED (never false rejection).
        """
        if not isinstance(rule.constraint_value, StagePrecedenceValue):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(target_node.node_id,),
                explanation="Rule constraint payload is not StagePrecedenceValue.",
            )

        prec = rule.constraint_value

        # Check if target node matches target stage of this precedence rule
        if target_node.stage != prec.target_stage:
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(target_node.node_id,),
                explanation=f"Target node stage '{target_node.stage}' does not match rule target '{prec.target_stage}'.",
            )

        # Pathway Scope Check: If rule has pathway restrictions, verify applicability
        if not rule.applies_to_pathway(target_node.pathway):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(target_node.node_id,),
                explanation=(
                    f"Rule '{rule.rule_id}' applies to pathways {prec.applicable_pathways}, "
                    f"does not apply to node pathway '{target_node.pathway}'."
                ),
            )

        # Look for preceding nodes with required_preceding_stage in graph
        matching_preceding_nodes = [
            n for n in graph.all_nodes()
            if n.stage == prec.required_preceding_stage and n.node_id != target_node.node_id
        ]

        if not matching_preceding_nodes:
            target_rank = STAGE_PROGRESSION_RANK.get(target_node.stage, 0) if target_node.stage else 0
            prior_stage_nodes = [
                n for n in graph.all_nodes()
                if n.stage is not None
                and STAGE_PROGRESSION_RANK.get(n.stage, 0) < target_rank
                and n.node_id != target_node.node_id
            ]
            if not prior_stage_nodes:
                return ConstraintEvaluationResult(
                    rule_id=rule.rule_id,
                    status=ConstraintStatus.UNDETERMINED,
                    target_node_ids=(target_node.node_id,),
                    explanation=f"Prior educational history is UNKNOWN in graph; prerequisite '{prec.required_preceding_stage.value}' is undetermined.",
                )
            # Prior stages exist, but required stage is missing
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.VIOLATED,
                target_node_ids=(target_node.node_id,),
                explanation=f"Missing required preceding stage '{prec.required_preceding_stage.value}' for '{prec.target_stage.value}'.",
                is_hard_rejection=rule.is_hard_rejection,
            )

        # Verify that at least one matching node strictly precedes the target node
        for p_node in matching_preceding_nodes:
            if (
                p_node.interval.latest_end is not None
                and target_node.interval.earliest_start is not None
                and p_node.interval.latest_end <= target_node.interval.earliest_start
            ):
                return ConstraintEvaluationResult(
                    rule_id=rule.rule_id,
                    status=ConstraintStatus.SATISFIED,
                    target_node_ids=(p_node.node_id, target_node.node_id),
                    explanation=f"Preceding stage '{prec.required_preceding_stage.value}' completed prior to target stage.",
                )

        return ConstraintEvaluationResult(
            rule_id=rule.rule_id,
            status=ConstraintStatus.UNDETERMINED,
            target_node_ids=(matching_preceding_nodes[0].node_id, target_node.node_id),
            explanation="Preceding stage node exists but exact boundary precedence cannot be definitively verified.",
        )

    @classmethod
    def evaluate_calendar_window(
        cls,
        node: TemporalNode,
        rule: TemporalRuleItem,
    ) -> ConstraintEvaluationResult:
        """Evaluate an institution-scoped TYPICAL_CALENDAR_WINDOW rule against a node."""
        if not isinstance(rule.constraint_value, CalendarWindowValue):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(node.node_id,),
                explanation="Rule constraint payload is not CalendarWindowValue.",
            )

        # Institution Scope Check (Lock 6)
        if not rule.applies_to_institution(node.institution_ref):
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(node.node_id,),
                explanation=(
                    f"Institution rule '{rule.rule_id}' for '{rule.scope_target}' does not "
                    f"apply to node institution '{node.institution_ref}'."
                ),
            )

        # UNKNOWN Semantics: If start date is unknown
        if node.interval.is_unknown() or node.interval.earliest_start is None:
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.UNDETERMINED,
                target_node_ids=(node.node_id,),
                explanation="Intake timing is UNKNOWN; calendar window compatibility is undetermined.",
            )

        intake_month = node.interval.earliest_start.month
        cal = rule.constraint_value

        if intake_month in cal.intake_months:
            return ConstraintEvaluationResult(
                rule_id=rule.rule_id,
                status=ConstraintStatus.SATISFIED,
                target_node_ids=(node.node_id,),
                explanation=f"Intake month ({intake_month}) matches institutional calendar {cal.intake_months}.",
            )

        return ConstraintEvaluationResult(
            rule_id=rule.rule_id,
            status=ConstraintStatus.VIOLATED,
            target_node_ids=(node.node_id,),
            explanation=f"Intake month ({intake_month}) falls outside typical institutional intake {cal.intake_months}.",
            is_hard_rejection=rule.is_hard_rejection,
        )

    @classmethod
    def evaluate_all(
        cls,
        graph: TemporalConstraintGraph,
    ) -> tuple[ConstraintEvaluationResult, ...]:
        """Perform deterministic full-graph constraint evaluation against all registered temporal rules.

        Constitutional Invariant:
        - Pure evaluation returning immutable findings.
        - Zero personal mutations, zero biography repair, zero canonical promotion.
        """
        results: list[ConstraintEvaluationResult] = []

        # 1. Evaluate all explicit edges
        for edge in graph.all_edges():
            results.append(cls.evaluate_edge_relation(graph, edge))

        # 2. Evaluate applicable registered world temporal rules for each node
        for node in graph.all_nodes():
            # Query relevant rules by subject / scope
            rules = TemporalRuleRegistry.all_rules()
            for rule in rules:
                if rule.constraint_type == TemporalConstraintType.DURATION_BOUND:
                    if node.stage in (LifeStage.PRE_UNIVERSITY, LifeStage.DIPLOMA, LifeStage.UNDERGRADUATE):
                        rule_stage_map = {
                            "stpm": LifeStage.PRE_UNIVERSITY,
                            "matrikulasi": LifeStage.PRE_UNIVERSITY,
                            "foundation": LifeStage.PRE_UNIVERSITY,
                            "diploma": LifeStage.DIPLOMA,
                            "undergraduate_degree": LifeStage.UNDERGRADUATE,
                        }
                        expected_stage = rule_stage_map.get(rule.subject)
                        if expected_stage is not None and node.stage != expected_stage:
                            continue
                        if rule.applies_to_pathway(node.pathway):
                            results.append(cls.evaluate_duration_bound(node, rule))

                elif rule.constraint_type == TemporalConstraintType.STAGE_PRECEDENCE:
                    if isinstance(rule.constraint_value, StagePrecedenceValue):
                        if node.stage == rule.constraint_value.target_stage:
                            results.append(cls.evaluate_stage_precedence(graph, node, rule))

                elif rule.constraint_type == TemporalConstraintType.TYPICAL_CALENDAR_WINDOW:
                    if rule.scope == TemporalRuleScope.INSTITUTION_SPECIFIC:
                        if rule.applies_to_institution(node.institution_ref):
                            results.append(cls.evaluate_calendar_window(node, rule))

        # Sort results deterministically by rule_id and target_node_ids
        return tuple(sorted(results, key=lambda r: (r.rule_id, r.target_node_ids)))
