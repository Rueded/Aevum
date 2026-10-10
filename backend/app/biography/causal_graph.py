"""causal_graph.py — Phase 12.2 Causal Explanation Graph Engine.

Governed by ADR-023:
1. Lock A (Causal DAG Scope): Constrains the Canonical Causal Explanation Graph
   to be an acyclic DAG. Does not force general life event or relationship graphs into a DAG.
2. Lock B (Cycle Detection): Full multi-hop cycle detection (A -> B -> C -> A)
   raising CausalCycleDetectedError upon any attempt to create a cycle.
3. Lock C (No Causal Invention): Pure graph derivation engine with zero canonical
   biography mutation authority (0 set_fact, 0 PromotionAuthorizationToken).
4. Lock D (UNKNOWN remains UNKNOWN): If causal_state == UNKNOWN, strictly returns
   ungrounded path with UNKNOWN state, refusing to fabricate or hypothesize causes.
"""

from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.biography.biography_models import (
    BiographicalDomain,
    BiographicalFact,
    CanonicalStatus,
    CausalKnowledgeState,
    CausalRelation,
    CausalRelationType,
    LifeEra,
    LifeEventRecord,
    PersonalPreference,
    RecallLevel,
)


class CausalCycleDetectedError(ValueError):
    """Raised when an added causal relation would introduce a directed cycle in causal explanations."""
    pass


class CausalNodeNotFoundError(KeyError):
    """Raised when attempting to link a relation referencing an unregistered node."""
    pass


class CausalNodeType(str, Enum):
    """Ontological node types participating in causal explanations."""
    EVENT = "EVENT"
    FACT = "FACT"
    PREFERENCE = "PREFERENCE"


class CausalNode(BaseModel):
    """Immutable node representation in the causal explanation graph."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str
    node_type: CausalNodeType
    label: str
    domain: BiographicalDomain
    era: Optional[LifeEra] = None
    canonical_status: CanonicalStatus = CanonicalStatus.CANONICAL
    recall_level: RecallLevel = RecallLevel.VIVID


class CausalExplanationStep(BaseModel):
    """A single atomic causal derivation step in an explanation path."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    target_id: str
    relation_type: CausalRelationType
    narrative_summary: str


class CausalExplanationPath(BaseModel):
    """Complete causal derivation path explaining why a preference, habit, or event exists."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_id: str
    causal_state: CausalKnowledgeState
    is_grounded: bool
    steps: list[CausalExplanationStep] = Field(default_factory=list)
    root_cause_ids: list[str] = Field(default_factory=list)
    terminal_reason: str = "EXPLAINED"


class CausalExplanationGraph:
    """Canonical Causal Explanation Graph Engine.
    
    Enforces strict acyclicity within the causal explanation derivation scope (Lock A, Lock B).
    Possesses zero canonical mutation authority (Lock C).
    Preserves UNKNOWN semantic state unconditionally (Lock D).
    """

    def __init__(self) -> None:
        self._nodes: dict[str, CausalNode] = {}
        self._outgoing: dict[str, list[CausalRelation]] = {}
        self._incoming: dict[str, list[CausalRelation]] = {}
        self._relations: dict[str, CausalRelation] = {}

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def relation_count(self) -> int:
        return len(self._relations)

    def add_node(self, node: CausalNode) -> None:
        """Registers a node in the causal explanation graph."""
        self._nodes[node.node_id] = node
        if node.node_id not in self._outgoing:
            self._outgoing[node.node_id] = []
        if node.node_id not in self._incoming:
            self._incoming[node.node_id] = []

    def add_node_from_event(self, event: LifeEventRecord) -> None:
        """Adapts a LifeEventRecord into a CausalNode."""
        node = CausalNode(
            node_id=event.event_id,
            node_type=CausalNodeType.EVENT,
            label=event.headline,
            domain=event.domain,
            era=event.era,
            canonical_status=event.canonical_status,
            recall_level=event.recall_level,
        )
        self.add_node(node)

    def add_node_from_fact(self, fact: BiographicalFact) -> None:
        """Adapts a BiographicalFact into a CausalNode."""
        node = CausalNode(
            node_id=fact.fact_id,
            node_type=CausalNodeType.FACT,
            label=f"{fact.attribute_key}: {fact.attribute_value}",
            domain=fact.domain,
            era=fact.era,
            canonical_status=fact.canonical_status,
            recall_level=fact.recall_level,
        )
        self.add_node(node)

    def add_node_from_preference(self, preference: PersonalPreference) -> None:
        """Adapts a PersonalPreference into a CausalNode."""
        node = CausalNode(
            node_id=preference.preference_id,
            node_type=CausalNodeType.PREFERENCE,
            label=f"{preference.category}: {preference.object_name} ({preference.affinity.value})",
            domain=BiographicalDomain.PASSION_AND_DISCIPLINE
            if preference.category in {"computing", "programming", "academic"}
            else BiographicalDomain.LIFESTYLE_AND_RHYTHM,
            era=preference.era_acquired,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.VIVID,
        )
        self.add_node(node)

    def get_node(self, node_id: str) -> Optional[CausalNode]:
        """Retrieves a node by its ID."""
        return self._nodes.get(node_id)

    def get_relation(self, relation_id: str) -> Optional[CausalRelation]:
        """Retrieves a relation by its ID."""
        return self._relations.get(relation_id)

    def add_relation(self, relation: CausalRelation) -> None:
        """Adds a causal derivation relation with strict DAG cycle detection (Lock A, Lock B)."""
        # 1. Self-loop verification (already on DTO, double-checked for runtime safety)
        if relation.source_id == relation.target_id:
            raise CausalCycleDetectedError(
                f"Self-referential causal relation forbidden: {relation.source_id} -> {relation.target_id}"
            )

        # 2. Node registration verification
        if relation.source_id not in self._nodes:
            raise CausalNodeNotFoundError(
                f"Source node '{relation.source_id}' is not registered in the causal explanation graph"
            )
        if relation.target_id not in self._nodes:
            raise CausalNodeNotFoundError(
                f"Target node '{relation.target_id}' is not registered in the causal explanation graph"
            )

        # 3. Directed cycle detection (Lock B: A -> B -> C -> A)
        # If there is already a path from target_id to source_id, adding source_id -> target_id creates a cycle!
        if self._has_path(start_id=relation.target_id, target_id=relation.source_id):
            raise CausalCycleDetectedError(
                f"Causal cycle detected: adding relation '{relation.relation_id}' ({relation.source_id} -> "
                f"{relation.target_id}) would create a directed causal cycle in the explanation graph"
            )

        # 4. Store relation
        self._relations[relation.relation_id] = relation
        self._outgoing[relation.source_id].append(relation)
        self._incoming[relation.target_id].append(relation)

    def _has_path(self, start_id: str, target_id: str) -> bool:
        """Determines if a directed path exists from start_id to target_id using BFS."""
        if start_id == target_id:
            return True

        visited: set[str] = {start_id}
        queue: deque[str] = deque([start_id])

        while queue:
            current = queue.popleft()
            for rel in self._outgoing.get(current, []):
                next_node = rel.target_id
                if next_node == target_id:
                    return True
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append(next_node)

        return False

    def get_causal_chain(self, target_id: str) -> list[CausalExplanationStep]:
        """Backward traversal: returns all causal derivation steps leading up to target_id.
        
        Ordered topologically from root causes to the target.
        """
        if target_id not in self._nodes:
            return []

        # Collect all reachable ancestors via backward BFS
        ancestor_relations: list[CausalRelation] = []
        visited_nodes: set[str] = {target_id}
        queue: deque[str] = deque([target_id])

        while queue:
            current = queue.popleft()
            for rel in self._incoming.get(current, []):
                ancestor_relations.append(rel)
                if rel.source_id not in visited_nodes:
                    visited_nodes.add(rel.source_id)
                    queue.append(rel.source_id)

        if not ancestor_relations:
            return []

        # Subgraph topological sort of collected relations
        subgraph_node_ids = visited_nodes
        topo_order = self._topological_sort_subgraph(subgraph_node_ids)
        node_order_index = {node_id: idx for idx, node_id in enumerate(topo_order)}

        # Sort relations by source node's topological rank
        ancestor_relations.sort(key=lambda r: node_order_index.get(r.source_id, 0))

        return [
            CausalExplanationStep(
                source_id=rel.source_id,
                target_id=rel.target_id,
                relation_type=rel.relation_type,
                narrative_summary=rel.narrative_summary,
            )
            for rel in ancestor_relations
        ]

    def get_downstream_effects(self, source_id: str) -> list[CausalExplanationStep]:
        """Forward traversal: returns all downstream causal consequences stemming from source_id."""
        if source_id not in self._nodes:
            return []

        consequence_relations: list[CausalRelation] = []
        visited_nodes: set[str] = {source_id}
        queue: deque[str] = deque([source_id])

        while queue:
            current = queue.popleft()
            for rel in self._outgoing.get(current, []):
                consequence_relations.append(rel)
                if rel.target_id not in visited_nodes:
                    visited_nodes.add(rel.target_id)
                    queue.append(rel.target_id)

        if not consequence_relations:
            return []

        subgraph_node_ids = visited_nodes
        topo_order = self._topological_sort_subgraph(subgraph_node_ids)
        node_order_index = {node_id: idx for idx, node_id in enumerate(topo_order)}

        consequence_relations.sort(key=lambda r: node_order_index.get(r.source_id, 0))

        return [
            CausalExplanationStep(
                source_id=rel.source_id,
                target_id=rel.target_id,
                relation_type=rel.relation_type,
                narrative_summary=rel.narrative_summary,
            )
            for rel in consequence_relations
        ]

    def get_root_causes(self, target_id: str) -> list[str]:
        """Finds root cause node IDs (in-degree == 0 in the causal explanation subgraph)."""
        if target_id not in self._nodes:
            return []

        # Find all ancestors
        ancestor_nodes: set[str] = set()
        queue: deque[str] = deque([target_id])

        while queue:
            current = queue.popleft()
            incoming_edges = self._incoming.get(current, [])
            for rel in incoming_edges:
                if rel.source_id not in ancestor_nodes:
                    ancestor_nodes.add(rel.source_id)
                    queue.append(rel.source_id)

        if not ancestor_nodes:
            # Target itself has no causal antecedents
            return [target_id]

        # Root causes in the ancestor set have no incoming relations in the whole graph
        root_causes = [
            node_id for node_id in ancestor_nodes
            if len(self._incoming.get(node_id, [])) == 0
        ]
        return sorted(root_causes)

    def topological_sort(self) -> list[str]:
        """Returns all nodes in topological derivation order using Kahn's algorithm."""
        in_degree: dict[str, int] = {node_id: len(self._incoming.get(node_id, [])) for node_id in self._nodes}
        queue: deque[str] = deque([node_id for node_id, deg in in_degree.items() if deg == 0])
        sorted_order: list[str] = []

        while queue:
            node_id = queue.popleft()
            sorted_order.append(node_id)
            for rel in self._outgoing.get(node_id, []):
                next_id = rel.target_id
                in_degree[next_id] -= 1
                if in_degree[next_id] == 0:
                    queue.append(next_id)

        if len(sorted_order) != len(self._nodes):
            # This should be mathematically impossible if add_relation prevents cycles
            raise CausalCycleDetectedError("Cycle detected during full topological sort")

        return sorted_order

    def _topological_sort_subgraph(self, node_ids: set[str]) -> list[str]:
        """Topological sort restricted to a subset of node IDs."""
        in_degree: dict[str, int] = {}
        for nid in node_ids:
            # Only count incoming edges that originate within the subgraph
            in_edges = [rel for rel in self._incoming.get(nid, []) if rel.source_id in node_ids]
            in_degree[nid] = len(in_edges)

        queue: deque[str] = deque([nid for nid, deg in in_degree.items() if deg == 0])
        sorted_order: list[str] = []

        while queue:
            nid = queue.popleft()
            sorted_order.append(nid)
            for rel in self._outgoing.get(nid, []):
                if rel.target_id in node_ids:
                    in_degree[rel.target_id] -= 1
                    if in_degree[rel.target_id] == 0:
                        queue.append(rel.target_id)

        return sorted_order

    def explain_preference(self, preference: PersonalPreference) -> CausalExplanationPath:
        """Explains why a PersonalPreference exists, adhering strictly to Lock D.
        
        If causal_state == UNKNOWN, strictly returns UNKNOWN without hallucinating causes.
        """
        # Lock D: UNKNOWN remains UNKNOWN
        if preference.causal_state == CausalKnowledgeState.UNKNOWN:
            return CausalExplanationPath(
                target_id=preference.preference_id,
                causal_state=CausalKnowledgeState.UNKNOWN,
                is_grounded=False,
                steps=[],
                root_cause_ids=[],
                terminal_reason="UNKNOWN",
            )

        # KNOWN state: check if node is registered
        if preference.preference_id not in self._nodes:
            # Fallback: check if the causal_relation_id exists in our relations
            if preference.causal_relation_id and preference.causal_relation_id in self._relations:
                rel = self._relations[preference.causal_relation_id]
                steps = [
                    CausalExplanationStep(
                        source_id=rel.source_id,
                        target_id=rel.target_id,
                        relation_type=rel.relation_type,
                        narrative_summary=rel.narrative_summary,
                    )
                ]
                root_causes = self.get_root_causes(rel.source_id)
                return CausalExplanationPath(
                    target_id=preference.preference_id,
                    causal_state=CausalKnowledgeState.KNOWN,
                    is_grounded=True,
                    steps=steps,
                    root_cause_ids=root_causes if root_causes else [rel.source_id],
                    terminal_reason="EXPLAINED",
                )
            return CausalExplanationPath(
                target_id=preference.preference_id,
                causal_state=CausalKnowledgeState.KNOWN,
                is_grounded=False,
                steps=[],
                root_cause_ids=[],
                terminal_reason="UNREGISTERED_PREFERENCE",
            )

        # Full backward traversal from registered preference node
        steps = self.get_causal_chain(preference.preference_id)
        root_causes = self.get_root_causes(preference.preference_id)

        return CausalExplanationPath(
            target_id=preference.preference_id,
            causal_state=CausalKnowledgeState.KNOWN,
            is_grounded=len(steps) > 0,
            steps=steps,
            root_cause_ids=root_causes,
            terminal_reason="EXPLAINED" if len(steps) > 0 else "UNGROUNDED_ROOT",
        )
