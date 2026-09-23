"""Inference Budget Controller and Provenance DAG Validator (Phase 7D.1).

Enforces hard multi-tier candidate generation and persistence budgets:
1. max_generated_hypotheses_per_turn = 4
2. max_direct_hypotheses_per_observation = 2
3. max_new_candidate_slots_per_turn = 2
4. max_inference_depth = 2
5. max_active_candidates_per_slot = 3

Enforces the strict lifecycle tri-state:
    Generated != Persisted != Promotable

Enforces Provenance DAG integrity:
    No circular inference loops (A -> B -> A)
    No candidate self-reinforcement (Candidate A -> Derived B -> Evidence for A)
"""

from collections import defaultdict
import enum
import logging
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    InferenceEdgeType,
    RealityTaxonomy,
)

logger = logging.getLogger(__name__)


class BudgetRejectionReason(str, enum.Enum):
    """Categorical reasons for hypothesis budget rejection or quarantine."""

    TURN_GENERATION_LIMIT_EXCEEDED = "TURN_GENERATION_LIMIT_EXCEEDED"
    OBSERVATION_FANOUT_LIMIT_EXCEEDED = "OBSERVATION_FANOUT_LIMIT_EXCEEDED"
    NEW_SLOTS_PER_TURN_EXCEEDED = "NEW_SLOTS_PER_TURN_EXCEEDED"
    INFERENCE_DEPTH_EXCEEDED = "INFERENCE_DEPTH_EXCEEDED"
    PROVENANCE_CYCLE_DETECTED = "PROVENANCE_CYCLE_DETECTED"
    USER_LOCKED_CANONICAL_FACT = "USER_LOCKED_CANONICAL_FACT"
    SPECULATIVE_ASSOCIATION = "SPECULATIVE_ASSOCIATION"
    DUAL_REALITY_TAXONOMY_VIOLATION = "DUAL_REALITY_TAXONOMY_VIOLATION"


class BudgetFilterResult(BaseModel):
    """Outcome of evaluating proposed hypotheses against turn budgets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    admitted: tuple[CandidateHypothesis, ...] = Field(default_factory=tuple)
    rejected: tuple[tuple[str, str], ...] = Field(
        default_factory=tuple,
        description="Tuple of (candidate_id, rejection_reason).",
    )
    quarantined: tuple[CandidateHypothesis, ...] = Field(default_factory=tuple)


class ProvenanceDAGValidator:
    """Validates that candidate derivation paths form a valid Directed Acyclic Graph (DAG)."""

    @classmethod
    def derive_lineage_depth(
        cls,
        candidate: CandidateHypothesis,
        ancestor_depth_map: Optional[dict[str, int]] = None,
    ) -> int:
        """Derive true inference depth from ancestor lineage rather than blindly trusting caller scalar input."""
        parent_ids = candidate.provenance.parent_candidate_ids
        if not parent_ids:
            return max(candidate.inference_depth, candidate.provenance.inference_depth)
        depth_map = ancestor_depth_map or {}
        max_parent_depth = max((depth_map.get(pid, 1) for pid in parent_ids), default=0)
        derived = max_parent_depth + 1
        return max(candidate.inference_depth, candidate.provenance.inference_depth, derived)

    @classmethod
    def validate_dag(
        cls,
        candidate: CandidateHypothesis,
        ancestor_graph: Optional[dict[str, list[str]]] = None,
    ) -> tuple[bool, Optional[str]]:
        """Verify candidate does not participate in a direct cycle or circular derivation loop.

        Args:
            candidate: The CandidateHypothesis to check.
            ancestor_graph: Mapping from candidate_id -> list of parent_candidate_ids.

        Returns:
            (is_valid, error_reason)
        """
        cand_id = candidate.candidate_id
        parent_ids = candidate.provenance.parent_candidate_ids

        # Check 1: Direct self-loop (A -> A)
        if cand_id in parent_ids:
            return False, f"Circular provenance detected: candidate {cand_id} lists itself as parent."

        # Check 2: Cycle detection in ancestor graph
        graph = dict(ancestor_graph or {})
        graph[cand_id] = list(parent_ids)

        visited: set[str] = set()
        rec_stack: set[str] = set()

        def _has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if _has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        if _has_cycle(cand_id):
            return False, f"Circular provenance loop detected involving candidate {cand_id}."

        # Check 3: Candidate self-reinforcement
        # A candidate cannot have an evidence family whose source is itself or derived from itself
        origin = candidate.provenance.origin_id
        if origin == cand_id:
            return False, f"Candidate self-reinforcement: candidate {cand_id} is its own origin stimulus."

        return True, None


class InferenceBudgetController:
    """Enforces multi-tier candidate budgets, lifecycle tri-state, and DAG validation."""

    MAX_GENERATED_HYPOTHESES_PER_TURN: int = 4
    MAX_DIRECT_HYPOTHESES_PER_OBSERVATION: int = 2
    MAX_NEW_CANDIDATE_SLOTS_PER_TURN: int = 2
    MAX_INFERENCE_DEPTH: int = 2
    MAX_ACTIVE_CANDIDATES_PER_SLOT: int = 3

    def __init__(
        self,
        max_generated_hypotheses_per_turn: int = MAX_GENERATED_HYPOTHESES_PER_TURN,
        max_direct_hypotheses_per_observation: int = MAX_DIRECT_HYPOTHESES_PER_OBSERVATION,
        max_new_candidate_slots_per_turn: int = MAX_NEW_CANDIDATE_SLOTS_PER_TURN,
        max_inference_depth: int = MAX_INFERENCE_DEPTH,
        max_active_candidates_per_slot: int = MAX_ACTIVE_CANDIDATES_PER_SLOT,
    ) -> None:
        self.max_generated = max_generated_hypotheses_per_turn
        self.max_direct_per_obs = max_direct_hypotheses_per_observation
        self.max_new_slots = max_new_candidate_slots_per_turn
        self.max_depth = max_inference_depth
        self.max_active_per_slot = max_active_candidates_per_slot

    def evaluate_turn_hypotheses(
        self,
        proposed_hypotheses: list[CandidateHypothesis],
        existing_canonical_slots: Optional[set[str]] = None,
        existing_active_slots: Optional[set[str]] = None,
        locked_slots: Optional[set[str]] = None,
        ancestor_graph: Optional[dict[str, list[str]]] = None,
        ancestor_depth_map: Optional[dict[str, int]] = None,
    ) -> BudgetFilterResult:
        """Evaluate a batch of ephemeral hypotheses proposed during a single turn.

        Enforces:
        1. Observation fan-out cap: max 2 direct hypotheses per origin observation.
        2. Turn generation cap: max 4 hypotheses admitted per turn.
        3. Turn new slots cap: max 2 newly introduced candidate slots per turn.
        4. Depth limit: depth > 2 quarantined / rejected.
        5. Edge type: SPECULATIVE_ASSOCIATION quarantined.
        6. DAG validation: cycles quarantined / rejected.
        7. User lock immunity: slots in locked_slots cannot be overridden.
        """
        canonical_slots = set(existing_canonical_slots or set())
        active_slots = set(existing_active_slots or set())
        user_locked = set(locked_slots or set())

        admitted: list[CandidateHypothesis] = []
        rejected: list[tuple[str, str]] = []
        quarantined: list[CandidateHypothesis] = []

        new_slots_introduced: set[str] = set()
        obs_hypotheses_count: dict[str, int] = defaultdict(int)

        # Sort proposed hypotheses by composite plausibility descending (prioritize strongest)
        sorted_hypotheses = sorted(
            proposed_hypotheses,
            key=lambda h: h.plausibility.composite_plausibility_score,
            reverse=True,
        )

        for hyp in sorted_hypotheses:
            # 1. Check User Lock Immunity
            if hyp.slot_name in user_locked:
                q_hyp = hyp.model_copy(
                    update={
                        "is_quarantined": True,
                        "quarantine_reason": f"Slot '{hyp.slot_name}' is locked by USER_LOCKED in canonical reality (GC-062).",
                    }
                )
                quarantined.append(q_hyp)
                rejected.append((hyp.candidate_id, BudgetRejectionReason.USER_LOCKED_CANONICAL_FACT.value))
                continue

            # 2. Check Dual Reality Taxonomy Boundaries
            if hyp.reality_taxonomy == RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT and hyp.slot_name.startswith("world."):
                q_hyp = hyp.model_copy(
                    update={
                        "is_quarantined": True,
                        "quarantine_reason": "SIMULATED_BIOGRAPHY_FACT cannot mutate objective world facts ('world.*').",
                    }
                )
                quarantined.append(q_hyp)
                rejected.append((hyp.candidate_id, BudgetRejectionReason.DUAL_REALITY_TAXONOMY_VIOLATION.value))
                continue

            if hyp.reality_taxonomy == RealityTaxonomy.OBJECTIVE_WORLD_FACT and not (
                hyp.slot_name.startswith("world.") or hyp.slot_name.startswith("knowledge.")
            ):
                q_hyp = hyp.model_copy(
                    update={
                        "is_quarantined": True,
                        "quarantine_reason": "OBJECTIVE_WORLD_FACT cannot mutate personal character biography slots.",
                    }
                )
                quarantined.append(q_hyp)
                rejected.append((hyp.candidate_id, BudgetRejectionReason.DUAL_REALITY_TAXONOMY_VIOLATION.value))
                continue

            # 3. Check Provenance DAG Cycle Detection
            is_dag_valid, dag_error = ProvenanceDAGValidator.validate_dag(hyp, ancestor_graph)
            if not is_dag_valid:
                q_hyp = hyp.model_copy(
                    update={
                        "is_quarantined": True,
                        "quarantine_reason": dag_error or "Circular provenance DAG cycle detected.",
                    }
                )
                quarantined.append(q_hyp)
                rejected.append((hyp.candidate_id, BudgetRejectionReason.PROVENANCE_CYCLE_DETECTED.value))
                continue

            # 4. Check Inference Depth Limit (derived from lineage rather than blindly trusting caller input)
            effective_depth = ProvenanceDAGValidator.derive_lineage_depth(hyp, ancestor_depth_map)
            if effective_depth > self.max_depth:
                q_hyp = hyp.model_copy(
                    update={
                        "inference_depth": effective_depth,
                        "is_quarantined": True,
                        "quarantine_reason": f"Lineage inference depth {effective_depth} exceeds max_inference_depth ({self.max_depth}).",
                    }
                )
                quarantined.append(q_hyp)
                rejected.append((hyp.candidate_id, BudgetRejectionReason.INFERENCE_DEPTH_EXCEEDED.value))
                continue

            # 4. Check Speculative Edge Type (Mandatory Quarantine)
            if hyp.inference_edge_type == InferenceEdgeType.SPECULATIVE_ASSOCIATION:
                q_hyp = hyp.model_copy(
                    update={
                        "is_quarantined": True,
                        "quarantine_reason": "SPECULATIVE_ASSOCIATION requires mandatory quarantine (Anti-Snowballing Boundary).",
                    }
                )
                quarantined.append(q_hyp)
                rejected.append((hyp.candidate_id, BudgetRejectionReason.SPECULATIVE_ASSOCIATION.value))
                continue

            # 5. Check Observation Direct Hypotheses Fan-Out (max 2)
            origin = hyp.provenance.origin_id
            if obs_hypotheses_count[origin] >= self.max_direct_per_obs:
                rejected.append((
                    hyp.candidate_id,
                    f"{BudgetRejectionReason.OBSERVATION_FANOUT_LIMIT_EXCEEDED.value}: max {self.max_direct_per_obs} direct hypotheses per observation.",
                ))
                continue

            # 6. Check Turn Generation Hard Ceiling (max 4)
            if len(admitted) >= self.max_generated:
                rejected.append((
                    hyp.candidate_id,
                    f"{BudgetRejectionReason.TURN_GENERATION_LIMIT_EXCEEDED.value}: max {self.max_generated} hypotheses per turn.",
                ))
                continue

            # 7. Check New Candidate Slots Cap (max 2 new slots per turn)
            is_new_slot = (hyp.slot_name not in canonical_slots) and (hyp.slot_name not in active_slots)
            if is_new_slot:
                if hyp.slot_name not in new_slots_introduced:
                    if len(new_slots_introduced) >= self.max_new_slots:
                        rejected.append((
                            hyp.candidate_id,
                            f"{BudgetRejectionReason.NEW_SLOTS_PER_TURN_EXCEEDED.value}: max {self.max_new_slots} new candidate slots per turn.",
                        ))
                        continue
                    new_slots_introduced.add(hyp.slot_name)

            # All budget checks passed: admit candidate
            obs_hypotheses_count[origin] += 1
            admitted.append(hyp)

        return BudgetFilterResult(
            admitted=tuple(admitted),
            rejected=tuple(rejected),
            quarantined=tuple(quarantined),
        )
