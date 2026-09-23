"""Structural and semantic regression checks for the Phase 7B.0 Aevum Golden Suite.

The suite evaluates behavioral decisions, epistemic trust, reality consistency,
and longitudinal stability across 30 benchmark cases, 3 cross-case chains, and
long-horizon benchmarks.
"""

import json
from collections import Counter
from pathlib import Path
import re
import pytest

CORPUS_PATH = Path(__file__).parent / "fixtures" / "golden_conversations.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "version",
    "metadata",
    "cases",
    "cross_case_chains",
    "long_horizon_benchmarks",
}

REQUIRED_CASE_FIELDS = {
    "id",
    "suite",
    "title",
    "preconditions",
    "turns",
    "behavioral_contract",
    "response_contract",
    "state_transition",
    "assertions",
    "tolerance",
    "rationale",
}

VALID_SUITES = {
    "social_behavior",
    "emergent_reality",
    "reality_integrity",
    "belief_trust",
    "user_controlled_reality",
}

VALID_ASSERTION_LAYERS = {
    "deterministic",
    "semantic",
    "longitudinal",
    "integration",
}

ID_REGEX = re.compile(r"^GC-(00[1-9]|0[1-2][0-9]|030)$")


def _load_raw_data() -> dict[str, object]:
    assert CORPUS_PATH.exists(), f"Corpus fixture missing at {CORPUS_PATH}"
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _load_cases() -> list[dict[str, object]]:
    data = _load_raw_data()
    return data["cases"]


def test_top_level_corpus_structure() -> None:
    """The corpus must declare version 7B.0, metadata, cases, chains, and long-horizon benchmarks."""
    data = _load_raw_data()
    assert REQUIRED_TOP_LEVEL_KEYS <= set(data.keys())
    assert data["version"] == "7B.0"
    assert data["metadata"]["total_cases"] == 30
    assert set(data["metadata"]["suites"]) == VALID_SUITES


def test_golden_suite_has_exactly_thirty_atomic_cases() -> None:
    """The first frozen benchmark baseline contains exactly 30 atomic cases numbered GC-001 to GC-030."""
    cases = _load_cases()
    assert len(cases) == 30

    ids = [case["id"] for case in cases]
    assert len(set(ids)) == 30, "All case IDs must be unique"

    for case_id in ids:
        assert ID_REGEX.match(case_id), f"Case ID '{case_id}' violates strict regex ^GC-(00[1-9]|0[1-2][0-9]|030)$"

    expected_ids = [f"GC-{i:03d}" for i in range(1, 31)]
    assert ids == expected_ids, "Cases must be sorted sequentially from GC-001 to GC-030"


def test_suite_distribution() -> None:
    """The 30 cases must be distributed across the 5 specialized cognitive domains."""
    cases = _load_cases()
    counts = Counter(case["suite"] for case in cases)

    assert counts["social_behavior"] == 12, "Suite A must contain exactly 12 cases"
    assert counts["emergent_reality"] == 6, "Suite B must contain exactly 6 cases"
    assert counts["reality_integrity"] == 6, "Suite C must contain exactly 6 cases"
    assert counts["belief_trust"] == 4, "Suite D must contain exactly 4 cases"
    assert counts["user_controlled_reality"] == 2, "Suite E must contain exactly 2 cases"


def test_case_contract_and_first_class_assertions() -> None:
    """Every case must define behavioral contract, state transition, and layered assertions without keyword matching."""
    cases = _load_cases()

    for case in cases:
        case_id = case["id"]
        assert REQUIRED_CASE_FIELDS <= set(case.keys()), f"{case_id} missing required fields"

        # Preconditions
        assert isinstance(case["preconditions"], dict) and case["preconditions"], f"{case_id} preconditions empty"

        # Turns
        turns = case["turns"]
        assert isinstance(turns, list) and len(turns) >= 1, f"{case_id} must have at least 1 turn"
        assert all("user" in turn and turn["user"].strip() for turn in turns), f"{case_id} turn missing user text"

        # Behavioral contract
        b_contract = case["behavioral_contract"]
        assert isinstance(b_contract, dict), f"{case_id} behavioral_contract must be dict"
        assert "must" in b_contract and isinstance(b_contract["must"], list) and len(b_contract["must"]) >= 1
        assert "must_not" in b_contract and isinstance(b_contract["must_not"], list) and len(b_contract["must_not"]) >= 1

        # Response contract
        r_contract = case["response_contract"]
        assert isinstance(r_contract, dict), f"{case_id} response_contract must be dict"
        assert "required_directions" in r_contract and len(r_contract["required_directions"]) >= 1
        assert "forbidden_directions" in r_contract and len(r_contract["forbidden_directions"]) >= 1

        # State transition as first-class citizen
        st = case["state_transition"]
        assert isinstance(st, dict), f"{case_id} state_transition must be dict"

        # Assertions
        assertions = case["assertions"]
        assert isinstance(assertions, list) and len(assertions) >= 1, f"{case_id} must have >= 1 assertion"
        for assertion in assertions:
            assert "layer" in assertion and assertion["layer"] in VALID_ASSERTION_LAYERS, (
                f"{case_id} assertion layer invalid: {assertion.get('layer')}"
            )
            assert "target" in assertion, f"{case_id} assertion missing target"
            assert "condition" in assertion, f"{case_id} assertion missing condition"

        # Tolerance & Rationale
        assert isinstance(case["tolerance"], dict), f"{case_id} tolerance must be dict"
        assert isinstance(case["rationale"], str) and case["rationale"].strip(), f"{case_id} rationale missing"

        # No rigid keyword / script assertions
        assert "expected_response" not in case, f"{case_id} must not prescribe exact response"
        assert "exact_response" not in case, f"{case_id} must not prescribe exact response"


def test_cross_case_chains_are_complete_and_referenced() -> None:
    """The corpus must specify the 3 cross-case chains, all referencing valid case IDs."""
    data = _load_raw_data()
    chains = data["cross_case_chains"]
    assert len(chains) == 3, "Must define exactly 3 cross-case chains"

    all_case_ids = {c["id"] for c in data["cases"]}
    expected_chain_ids = {"CHAIN-01", "CHAIN-02", "CHAIN-03"}
    actual_chain_ids = {chain["chain_id"] for chain in chains}
    assert actual_chain_ids == expected_chain_ids

    for chain in chains:
        assert "title" in chain and chain["title"].strip()
        assert "steps" in chain and len(chain["steps"]) >= 3
        assert "verification_goal" in chain and chain["verification_goal"].strip()
        for step_id in chain["steps"]:
            assert step_id in all_case_ids, f"Chain step {step_id} does not exist in cases"


def test_long_horizon_benchmarks_are_defined() -> None:
    """The corpus must specify 50, 100, and 200 turns long-horizon invariants."""
    data = _load_raw_data()
    benchmarks = data["long_horizon_benchmarks"]
    levels = {b["level"] for b in benchmarks}
    assert levels == {"50_turns", "100_turns", "200_turns"}
    for b in benchmarks:
        assert "invariant" in b and b["invariant"].strip()
