"""Trajectory Plurality & Timeline State Engine (Phase 8B.4).

Architectural Principles & Constitutional Invariants (Phase 8B.4):
1. Invariant G (Trajectory Plurality & Temporal Ambiguity Preservation): When multiple
   temporal trajectories satisfy constraints, Phase 8B preserves the compatible set
   (bounded by MAX_COMPATIBLE_TRAJECTORIES = 3) rather than arbitrarily choosing one.
   If compatible trajectories exceed this bound, the engine flags
   is_ambiguity_unresolved = True with selected_canonical_trajectory = None.
2. Invariant C (Projection is Never Canonical Reality): Future projected nodes
   carry EpistemicGrounding.PROJECTED and Canonicality.NON_CANONICAL. They can never
   enter canonical reality or mutate CharacterCore.
3. Invariant E (Bounded Propagation & Cardinality): Bounded propagation depth
   (MAX_TEMPORAL_PROPAGATION_HOPS = 2). Cardinality bounded by MAX_PROJECTED_NODES = 4.
   Projected nodes cannot recursively serve as origins for further projection.
4. LOCK-8B3-01 (VIOLATED != IMPOSSIBLE): Only an applicable hard rule violation
   (is_hard_rejection=True and status=VIOLATED) eliminates a candidate trajectory
   as HARD_INCOMPATIBLE. Advisory rule violations mark ADVISORY_ANOMALY but remain
   in the compatible set.
5. LOCK-8B3-02 (UNDETERMINED != Failure): Incomplete or UNKNOWN evidence must not
   be converted into a chosen trajectory or fabricated temporal fact.
6. LOCK-8B3-03 (Precision Ceiling): Temporal evaluation and trajectory generation
   precision must not exceed evidence precision. No synthetic exact dates or durations.
7. LOCK-8B3-04 (No Fact Fabrication): Constraint evaluation and trajectory generation
   never reconstruct missing personal temporal facts merely to satisfy a rule.
8. Zero Mutation Authority: TCG and trajectory generation are ephemeral in-memory
   reasoning structures. Zero canonical fact mutation, zero tokens, zero DB, zero network, zero LLM.
"""

from __future__ import annotations

from datetime import date
import enum
from typing import Any, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.reality.temporal_models import (
    MAX_COMPATIBLE_TRAJECTORIES,
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
    TemporalRuleItem,
    TemporalRuleRegistry,
)
from app.reality.temporal_graph import (
    ConstraintEvaluationResult,
    ConstraintStatus,
    STAGE_PROGRESSION_RANK,
    TemporalConstraintEvaluator,
    TemporalConstraintGraph,
    TemporalEdge,
    TemporalNode,
    TemporalRelationType,
)


# =============================================================================
# Categorical Enums & Domain Models
# =============================================================================

class TrajectoryStatus(str, enum.Enum):
    """Categorical compatibility status of a candidate life trajectory."""

    COMPATIBLE = "COMPATIBLE"                  # Satisfies all applicable rules without hard or advisory conflicts
    ADVISORY_ANOMALY = "ADVISORY_ANOMALY"      # Satisfies hard constraints, but has advisory rule mismatch (e.g. non-standard intake)
    HARD_INCOMPATIBLE = "HARD_INCOMPATIBLE"    # Violates an applicable hard constraint (scoped to pathway/institution)


class LifeTrajectory(BaseModel):
    """Immutable sequence of chronologically ordered temporal nodes forming a coherent life pathway.

    Constitutional Constraints:
    - Immutable (frozen=True, extra="forbid").
    - Maximum projected nodes <= MAX_PROJECTED_NODES (4).
    - Future nodes must carry EpistemicGrounding.PROJECTED and Canonicality.NON_CANONICAL.
    - Zero pseudo-probability or arbitrary confidence scores.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    trajectory_id: str = Field(..., description="Deterministic trajectory identifier (e.g. 'traj_stpm_degree')")
    pathway: Optional[str] = Field(default=None, description="Educational pathway (e.g. 'STPM', 'DIPLOMA')")
    nodes: tuple[TemporalNode, ...] = Field(..., description="Ordered sequence of temporal nodes")
    status: TrajectoryStatus = Field(default=TrajectoryStatus.COMPATIBLE, description="Compatibility classification")
    evaluation_findings: tuple[ConstraintEvaluationResult, ...] = Field(
        default_factory=tuple,
        description="Structured evaluation results from TCG constraint evaluation",
    )
    description: str = Field(default="", description="Human-readable summary of this trajectory pathway")

    @model_validator(mode="after")
    def validate_trajectory_invariants(self) -> LifeTrajectory:
        """Enforce cardinality and projection invariants on the trajectory."""
        projected_count = sum(
            1 for n in self.nodes
            if n.epistemic_grounding == EpistemicGrounding.PROJECTED
        )
        if projected_count > MAX_PROJECTED_NODES:
            raise ValueError(
                f"Trajectory '{self.trajectory_id}' exceeds MAX_PROJECTED_NODES: "
                f"{projected_count} > {MAX_PROJECTED_NODES}."
            )
        return self

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def projected_node_count(self) -> int:
        return sum(
            1 for n in self.nodes
            if n.epistemic_grounding == EpistemicGrounding.PROJECTED
        )

    def get_node(self, node_id: str) -> Optional[TemporalNode]:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None


class TrajectoryPluralityResult(BaseModel):
    """Structured result representing the set of evaluated life trajectories for a turn.

    Hard Architectural Invariant (Invariant G & LOCK-8B3-02):
    - When multiple trajectories are compatible, Phase 8B preserves the compatible set
      (up to MAX_COMPATIBLE_TRAJECTORIES = 3).
    - If compatible trajectories exceed 3, or if the pathway is unknown with multiple
      viable alternatives, is_ambiguity_unresolved is True.
    - When ambiguity is unresolved, selected_canonical_trajectory is strictly None.
      The engine NEVER arbitrarily picks one trajectory over others.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    compatible_trajectories: tuple[LifeTrajectory, ...] = Field(
        default_factory=tuple,
        description="Enumerated compatible trajectories if cardinality bound is not exceeded",
    )
    compatible_pathways: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Set of compatible pathway identifiers (preserved even when cardinality bound exceeded)",
    )
    incompatible_trajectories: tuple[LifeTrajectory, ...] = Field(
        default_factory=tuple,
        description="Trajectories rejected due to applicable hard rule violations",
    )
    total_compatible_count: int = Field(
        ...,
        description="Total number of compatible trajectories discovered",
    )
    is_ambiguity_unresolved: bool = Field(
        default=False,
        description="True if multiple trajectories remain viable or compatible count exceeded bound",
    )
    trajectory_bound_exceeded: bool = Field(
        default=False,
        description="True if compatible trajectories exceeded MAX_COMPATIBLE_TRAJECTORIES (bounded ambiguity)",
    )
    selected_canonical_trajectory: Optional[LifeTrajectory] = Field(
        default=None,
        description="Designated trajectory if and only if exactly 1 trajectory is uniquely evidenced and authoritative",
    )


# =============================================================================
# Canonical Higher Education Pathway Specifications
# =============================================================================

CANONICAL_HIGHER_ED_PATHWAYS: tuple[str, ...] = (
    "STPM",
    "MATRIKULASI",
    "FOUNDATION",
    "DIPLOMA",
)
"""The four canonical Malaysian higher education entry pathways."""


# =============================================================================
# Deterministic Trajectory Plurality & Timeline State Engine
# =============================================================================

class TimelineTrajectoryEngine:
    """Ephemeral, deterministic trajectory plurality engine.

    Constitutional Responsibilities:
    - Given known baseline evidence (e.g. birth, secondary school, degree intake),
      generates candidate trajectory structures.
    - Evaluates each candidate trajectory using TemporalConstraintEvaluator.
    - Strictly filters out HARD_INCOMPATIBLE candidates (LOCK-8B3-01).
    - Preserves trajectory plurality without arbitrary selection (Invariant G & LOCK-8B3-02).
    - Bounded to MAX_COMPATIBLE_TRAJECTORIES = 3.
    """

    @classmethod
    def generate_trajectories(
        cls,
        base_nodes: Sequence[TemporalNode],
        known_pathway: Optional[str] = None,
        pathway_grounding: Optional[EpistemicGrounding] = None,
        target_institution_ref: Optional[str] = None,
        project_degree_graduation: bool = True,
    ) -> TrajectoryPluralityResult:
        """Construct, evaluate, and filter candidate life trajectories deterministically.

        Semantics:
        - If known_pathway is provided (explicitly evidenced): evaluates candidates
          only for that designated pathway.
        - If known_pathway is None (UNKNOWN): generates candidates across all canonical
          higher education pathways (STPM, Matrikulasi, Foundation, Diploma) and
          preserves ambiguity without picking one.
        - pathway_grounding: EpistemicGrounding of the known_pathway. A canonical trajectory
          is selected IFF the pathway is uniquely supported by authoritative personal evidence
          (USER_CONFIRMED or OBSERVED). Derived temporal compatibility alone is NEVER canonical.
        """
        # Determine candidate pathways to evaluate
        if known_pathway:
            norm_p = known_pathway.strip().upper()
            candidate_pathways = (norm_p,)
        else:
            candidate_pathways = CANONICAL_HIGHER_ED_PATHWAYS

        candidate_trajectories: list[LifeTrajectory] = []

        # Find key anchor nodes from base_nodes
        birth_node = next((n for n in base_nodes if "birth" in n.node_id.lower()), None)
        sec_node = next((n for n in base_nodes if n.stage == LifeStage.SECONDARY_EDUCATION), None)
        ug_node = next((n for n in base_nodes if n.stage == LifeStage.UNDERGRADUATE), None)

        for p_name in candidate_pathways:
            traj = cls._build_candidate_trajectory_for_pathway(
                base_nodes=base_nodes,
                pathway=p_name,
                birth_node=birth_node,
                sec_node=sec_node,
                ug_node=ug_node,
                target_institution_ref=target_institution_ref,
                project_degree_graduation=project_degree_graduation,
            )
            candidate_trajectories.append(traj)

        # Evaluate and categorize each trajectory
        compatible: list[LifeTrajectory] = []
        incompatible: list[LifeTrajectory] = []

        for traj in candidate_trajectories:
            evaluated_traj = cls._evaluate_trajectory(traj)
            if evaluated_traj.status == TrajectoryStatus.HARD_INCOMPATIBLE:
                incompatible.append(evaluated_traj)
            else:
                compatible.append(evaluated_traj)

        # Sort compatible trajectories deterministically by trajectory_id
        sorted_compatible = sorted(compatible, key=lambda t: t.trajectory_id)
        total_compatible = len(sorted_compatible)
        all_compatible_pathways = tuple(sorted({t.pathway for t in sorted_compatible}))

        # Enforce MAX_COMPATIBLE_TRAJECTORIES = 3 bound (Lock 1 & Invariant G)
        # CRITICAL: If compatible trajectories exceed bound, DO NOT silently truncate (keep 3, drop 4th).
        # Discarding compatible alternatives arbitrarily violates trajectory plurality.
        # Instead, enter non-enumerated bounded ambiguity representation.
        is_ambiguous = total_compatible > 1
        bound_exceeded = total_compatible > MAX_COMPATIBLE_TRAJECTORIES

        if bound_exceeded:
            # Bounded ambiguity: Do not arbitrarily pick 3 out of 4.
            # Retain empty enumerated tuple to prevent disguising 4 as 3, but preserve all compatible pathways.
            enumerated_compatible: tuple[LifeTrajectory, ...] = ()
        else:
            enumerated_compatible = tuple(sorted_compatible)

        # Determine if a canonical trajectory can be uniquely designated (Lock 2)
        # Grounding check: Temporal compatibility alone is NEVER authoritative evidence.
        # selected_canonical_trajectory requires authoritative evidence (USER_CONFIRMED or OBSERVED).
        # Derived/Projected temporal compatibility alone CANNOT select a canonical trajectory!
        resolved_pathway_grounding = pathway_grounding
        if resolved_pathway_grounding is None and known_pathway is not None:
            # Check if any base node provided this pathway authoritatively
            matching_base = next(
                (n for n in base_nodes if n.pathway == known_pathway),
                None,
            )
            if matching_base is not None:
                resolved_pathway_grounding = matching_base.epistemic_grounding
            elif any(n.epistemic_grounding in (EpistemicGrounding.USER_CONFIRMED, EpistemicGrounding.OBSERVED) for n in base_nodes):
                resolved_pathway_grounding = EpistemicGrounding.USER_CONFIRMED

        is_authoritative = resolved_pathway_grounding in (
            EpistemicGrounding.USER_CONFIRMED,
            EpistemicGrounding.OBSERVED,
        )

        selected_canonical: Optional[LifeTrajectory] = None
        if total_compatible == 1 and is_authoritative and not is_ambiguous:
            selected_canonical = sorted_compatible[0]

        return TrajectoryPluralityResult(
            compatible_trajectories=enumerated_compatible,
            compatible_pathways=all_compatible_pathways,
            incompatible_trajectories=tuple(sorted(incompatible, key=lambda t: t.trajectory_id)),
            total_compatible_count=total_compatible,
            is_ambiguity_unresolved=is_ambiguous,
            trajectory_bound_exceeded=bound_exceeded,
            selected_canonical_trajectory=selected_canonical,
        )

    @classmethod
    def _build_candidate_trajectory_for_pathway(
        cls,
        base_nodes: Sequence[TemporalNode],
        pathway: str,
        birth_node: Optional[TemporalNode],
        sec_node: Optional[TemporalNode],
        ug_node: Optional[TemporalNode],
        target_institution_ref: Optional[str],
        project_degree_graduation: bool,
    ) -> LifeTrajectory:
        """Synthesize candidate temporal nodes for a specific pathway."""
        nodes: list[TemporalNode] = []

        # 1. Include base anchor nodes (preserving original grounding/canonicality)
        for bn in base_nodes:
            # If base node is undergraduate, specialize its pathway
            if bn.stage == LifeStage.UNDERGRADUATE:
                specialized_ug = TemporalNode(
                    node_id=bn.node_id,
                    label=bn.label,
                    stage=bn.stage,
                    interval=bn.interval,
                    temporal_horizon=bn.temporal_horizon,
                    epistemic_grounding=bn.epistemic_grounding,
                    canonicality=bn.canonicality,
                    institution_ref=target_institution_ref or bn.institution_ref,
                    pathway=pathway,
                    origin_fact_key=bn.origin_fact_key,
                    propagation_depth=bn.propagation_depth,
                    constraint_chain=bn.constraint_chain,
                )
                nodes.append(specialized_ug)
            else:
                nodes.append(bn)

        # 2. Add intermediate pre-university / diploma stage if not already in base_nodes
        has_intermediate = any(
            n.stage in (LifeStage.PRE_UNIVERSITY, LifeStage.DIPLOMA)
            for n in nodes
        )

        if not has_intermediate and ug_node is not None:
            # Reconstruct intermediate node (LOCK-8B3-03: Do not fabricate synthetic exact dates)
            # Reconstructed intermediate stage has EpistemicGrounding.DERIVED and Canonicality.NON_CANONICAL
            ug_start = ug_node.interval.earliest_start
            ug_year = ug_start.year if ug_start else None

            if pathway == "DIPLOMA":
                inter_stage = LifeStage.DIPLOMA
                inter_label = "Diploma Studies"
                rule_id = "RULE_PRECEDENCE_DIPLOMA_TO_UNDERGRAD"
                # Duration approx 2.5 - 3 years before UG
                inter_interval = (
                    TemporalInterval.create_date_range(
                        start=date(ug_year - 3, 7, 1),
                        end=date(ug_year, 6, 30),
                    )
                    if ug_year else TemporalInterval.create_unknown()
                )
            elif pathway == "STPM":
                inter_stage = LifeStage.PRE_UNIVERSITY
                inter_label = "STPM (Form 6) Studies"
                rule_id = "RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD"
                # Duration approx 1.5 - 2 years before UG
                inter_interval = (
                    TemporalInterval.create_date_range(
                        start=date(ug_year - 2, 7, 1),
                        end=date(ug_year, 3, 31),
                    )
                    if ug_year else TemporalInterval.create_unknown()
                )
            elif pathway == "MATRIKULASI":
                inter_stage = LifeStage.PRE_UNIVERSITY
                inter_label = "Matrikulasi Studies"
                rule_id = "RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD"
                inter_interval = (
                    TemporalInterval.create_date_range(
                        start=date(ug_year - 1, 6, 1),
                        end=date(ug_year, 5, 31),
                    )
                    if ug_year else TemporalInterval.create_unknown()
                )
            else:  # FOUNDATION
                inter_stage = LifeStage.PRE_UNIVERSITY
                inter_label = "University Foundation Studies"
                rule_id = "RULE_PRECEDENCE_PRE_U_TO_UNDERGRAD"
                inter_interval = (
                    TemporalInterval.create_date_range(
                        start=date(ug_year - 1, 7, 1),
                        end=date(ug_year, 6, 30),
                    )
                    if ug_year else TemporalInterval.create_unknown()
                )

            inter_node = TemporalNode(
                node_id=f"node_{pathway.lower()}_stage",
                label=inter_label,
                stage=inter_stage,
                interval=inter_interval,
                temporal_horizon=TemporalHorizon.PAST,
                epistemic_grounding=EpistemicGrounding.DERIVED,
                canonicality=Canonicality.NON_CANONICAL,
                pathway=pathway,
                origin_node_id=ug_node.node_id,
                propagation_depth=min(ug_node.propagation_depth + 1, MAX_TEMPORAL_PROPAGATION_HOPS),
                constraint_chain=(rule_id,),
            )
            nodes.append(inter_node)

        # 3. Project degree graduation node if requested and ug_node exists
        if project_degree_graduation and ug_node is not None:
            ug_start = ug_node.interval.earliest_start
            ug_year = ug_start.year if ug_start else None

            # Degree duration typically 3-4 years (Diploma holders often 3 years with credit transfer)
            degree_duration = 3 if pathway == "DIPLOMA" else 4
            grad_year = ug_year + degree_duration if ug_year else None

            grad_interval = (
                TemporalInterval.create_approximate_year(year=grad_year)
                if grad_year else TemporalInterval.create_unknown()
            )

            # Invariant C: Projected node must be PROJECTED and NON_CANONICAL
            grad_node = TemporalNode(
                node_id=f"node_projected_grad_{pathway.lower()}",
                label=f"Projected Undergraduate Graduation ({pathway})",
                stage=LifeStage.UNDERGRADUATE,
                interval=grad_interval,
                temporal_horizon=TemporalHorizon.FUTURE,
                epistemic_grounding=EpistemicGrounding.PROJECTED,
                canonicality=Canonicality.NON_CANONICAL,
                pathway=pathway,
                origin_node_id=ug_node.node_id,
                propagation_depth=min(ug_node.propagation_depth + 1, MAX_TEMPORAL_PROPAGATION_HOPS),
                constraint_chain=("RULE_MY_DEGREE_DURATION",),
            )
            nodes.append(grad_node)

        # Sort nodes deterministically: Chronologically by earliest_start, then by node_id
        sorted_nodes = tuple(
            sorted(
                nodes,
                key=lambda n: (
                    n.interval.earliest_start or date.min,
                    n.node_id,
                ),
            )
        )

        return LifeTrajectory(
            trajectory_id=f"traj_{pathway.lower()}_undergrad",
            pathway=pathway,
            nodes=sorted_nodes,
            status=TrajectoryStatus.COMPATIBLE,
            description=f"Undergraduate educational trajectory via {pathway} pathway.",
        )

    @classmethod
    def _evaluate_trajectory(cls, trajectory: LifeTrajectory) -> LifeTrajectory:
        """Build an ephemeral TCG for the trajectory and evaluate all constraints."""
        # 1. Build ephemeral graph
        graph = TemporalConstraintGraph(nodes=trajectory.nodes)

        # 2. Add stage progression constraint edges based on STAGE_PROGRESSION_RANK
        nodes_list = trajectory.nodes
        for i in range(len(nodes_list)):
            for j in range(len(nodes_list)):
                if i != j:
                    n1 = nodes_list[i]
                    n2 = nodes_list[j]
                    if n1.stage and n2.stage:
                        rank1 = STAGE_PROGRESSION_RANK.get(n1.stage, 0)
                        rank2 = STAGE_PROGRESSION_RANK.get(n2.stage, 0)
                        if rank1 < rank2:
                            edge_id = f"edge_stage_prog_{n1.node_id}_to_{n2.node_id}"
                            if not graph.get_edge(edge_id):
                                graph.add_edge(
                                    TemporalEdge(
                                        edge_id=edge_id,
                                        source_node_id=n1.node_id,
                                        target_node_id=n2.node_id,
                                        relation=TemporalRelationType.BEFORE,
                                        description=f"Developmental stage '{n1.stage.value}' must precede '{n2.stage.value}'.",
                                    )
                                )

        # Also add sequential ordering edges for adjacent stages if rank is non-decreasing
        for i in range(len(nodes_list) - 1):
            n1 = nodes_list[i]
            n2 = nodes_list[i + 1]
            edge_id = f"edge_{n1.node_id}_to_{n2.node_id}"
            if not graph.get_edge(edge_id):
                rank1 = STAGE_PROGRESSION_RANK.get(n1.stage, 0) if n1.stage else 0
                rank2 = STAGE_PROGRESSION_RANK.get(n2.stage, 0) if n2.stage else 0
                if rank1 <= rank2:
                    graph.add_edge(
                        TemporalEdge(
                            edge_id=edge_id,
                            source_node_id=n1.node_id,
                            target_node_id=n2.node_id,
                            relation=TemporalRelationType.BEFORE,
                        )
                    )

        # 3. Evaluate full graph
        findings = TemporalConstraintEvaluator.evaluate_all(graph)

        # 4. Check for hard rejections vs advisory anomalies (LOCK-8B3-01)
        has_hard_violation = any(
            f.status == ConstraintStatus.VIOLATED and f.is_hard_rejection
            for f in findings
        )
        has_advisory_violation = any(
            f.status == ConstraintStatus.VIOLATED and not f.is_hard_rejection
            for f in findings
        )

        if has_hard_violation:
            status = TrajectoryStatus.HARD_INCOMPATIBLE
        elif has_advisory_violation:
            status = TrajectoryStatus.ADVISORY_ANOMALY
        else:
            status = TrajectoryStatus.COMPATIBLE

        return LifeTrajectory(
            trajectory_id=trajectory.trajectory_id,
            pathway=trajectory.pathway,
            nodes=trajectory.nodes,
            status=status,
            evaluation_findings=findings,
            description=trajectory.description,
        )
