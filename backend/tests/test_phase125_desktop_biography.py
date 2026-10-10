"""test_phase125_desktop_biography.py — Dedicated Unit Tests for Phase 12.5 Desktop Biography Projection.

Governed by ADR-023 & Rule 19:
1. Constitutional Principle: "The desktop may display memory; it does not own memory."
2. Pure Read-Only Projection: Endpoint GET /character/longitudinal-memory serves reality state.
3. Zero Reverse Mutation: No desktop endpoint exists to arbitrarily mutate biography facts.
4. Causal & Relational Fidelity: Exposes Lock D UNKNOWN causal states and Rule 16 multi-axis dynamics.
5. Pure Static AST Audit: 0 DB, 0 LLM, 0 network, 0 mutation authority tokens.
"""

from __future__ import annotations

import ast
import pathlib
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.biography.biography_registry import (
    get_biography_service,
    get_shared_history_service,
    reset_registry_for_testing,
)


@pytest.fixture(autouse=True)
def clean_registry() -> None:
    reset_registry_for_testing()
    yield
    reset_registry_for_testing()


@pytest.mark.asyncio
async def test_get_longitudinal_memory_endpoint_contract() -> None:
    """Verifies that GET /character/longitudinal-memory returns valid dual-track projection."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/character/longitudinal-memory")
        assert resp.status_code == 200
        data = resp.json()

        # 1. Facts
        assert "facts" in data
        assert len(data["facts"]) >= 3
        fact_keys = [f["attribute_key"] for f in data["facts"]]
        assert "hometown_and_heritage" in fact_keys
        assert "academic_discipline" in fact_keys

        # 2. Life Events across eras
        assert "life_events" in data
        assert len(data["life_events"]) >= 2
        event_ids = [e["id"] for e in data["life_events"]]
        assert "evt-first-code" in event_ids
        assert "evt-tea-ritual" in event_ids

        # 3. Preferences with Lock D KNOWN vs UNKNOWN causal state
        assert "preferences" in data
        pref_map = {p["id"]: p for p in data["preferences"]}
        assert "pref-python-systems" in pref_map
        assert pref_map["pref-python-systems"]["causal_state"] == "KNOWN"
        assert pref_map["pref-python-systems"]["causal_relation_id"] == "rel-game-to-python"

        assert "pref-roasted-tea" in pref_map
        assert pref_map["pref-roasted-tea"]["causal_state"] == "UNKNOWN"
        assert pref_map["pref-roasted-tea"]["causal_relation_id"] is None

        # 4. Qualia Anchors
        assert "qualia" in data
        assert len(data["qualia"]) >= 2

        # 5. Contacts
        assert "contacts" in data
        assert any(c["id"] == "cnt-mr-lee" for c in data["contacts"])

        # 6. Shared History Episodes (Lock 4 & Lock F)
        assert "shared_episodes" in data
        assert len(data["shared_episodes"]) >= 2
        ep_sessions = [ep["session_anchor"] for ep in data["shared_episodes"]]
        assert "sess-001" in ep_sessions
        assert "sess-042" in ep_sessions

        # 7. Rule 16 Relational Dynamics
        assert "relational_dynamics" in data
        rel = data["relational_dynamics"]
        for dim in ["familiarity", "trust", "comfort", "respect", "affection", "attachment"]:
            assert dim in rel
            assert isinstance(rel[dim], float)


@pytest.mark.asyncio
async def test_zero_reverse_mutation_endpoints_exist() -> None:
    """Rule 19: Desktop UI has strictly zero endpoints to write or edit biography directly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Attempting POST/PUT/PATCH/DELETE to /character/longitudinal-memory is rejected
        post_resp = await client.post("/character/longitudinal-memory", json={"fact": "fake"})
        assert post_resp.status_code in (404, 405)

        patch_resp = await client.patch("/character/longitudinal-memory", json={"fact": "fake"})
        assert patch_resp.status_code in (404, 405)

        delete_resp = await client.delete("/character/longitudinal-memory")
        assert delete_resp.status_code in (404, 405)


def test_biography_registry_ast_purity() -> None:
    """Verifies that biography_registry.py has zero DB, LLM, or network dependencies."""
    tf = pathlib.Path("app/biography/biography_registry.py")
    assert tf.exists()
    source = tf.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(tf))

    forbidden_imports = [
        "sqlalchemy",
        "sqlite3",
        "database",
        "db",
        "llm",
        "google",
        "openai",
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
    ]
    forbidden_tokens = [
        "promotionauthorizationtoken",
        "set_fact",
        "execute_query",
        "session.commit",
        "db_session",
        "cursor.execute",
    ]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in forbidden_imports:
                    assert forbidden not in alias.name.lower()
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for forbidden in forbidden_imports:
                assert forbidden not in mod.lower()
        elif isinstance(node, ast.Name):
            for forbidden in forbidden_tokens:
                assert forbidden not in node.id.lower()
