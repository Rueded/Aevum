"""Unit tests for World Knowledge Registry (Phase 7B.3.3).

Verifies declarative knowledge registration, static facts, plausibility rules,
and pop-culture entity relations (GC-021, GC-022, GC-026).
"""

from app.reality.world_knowledge import (
    KnowledgeKind,
    WorldKnowledgeItem,
    WorldKnowledgeRegistry,
)


def test_registry_contains_malaysian_campuses() -> None:
    usm_main = WorldKnowledgeRegistry.get("world.usm.main_campus")
    assert usm_main is not None
    assert usm_main.kind == KnowledgeKind.STATIC_FACT
    assert "Penang" in usm_main.fact_value

    usm_eng = WorldKnowledgeRegistry.get("world.usm.engineering_campus")
    assert usm_eng is not None
    assert "Nibong Tebal" in usm_eng.fact_value

    um_main = WorldKnowledgeRegistry.get("world.um.main_campus")
    assert um_main is not None
    assert "Kuala Lumpur" in um_main.fact_value


def test_registry_contains_physics_laws() -> None:
    sun_rises = WorldKnowledgeRegistry.get("world.astronomy.sun_rises")
    assert sun_rises is not None
    assert sun_rises.kind == KnowledgeKind.STATIC_FACT
    assert sun_rises.fact_value == "East"


def test_registry_contains_educational_plausibility_rules() -> None:
    stpm = WorldKnowledgeRegistry.get("education.malaysia.stpm_duration")
    assert stpm is not None
    assert stpm.kind == KnowledgeKind.PLAUSIBILITY_RULE
    assert "1.5" in str(stpm.fact_value)

    entry_age = WorldKnowledgeRegistry.get("education.malaysia.typical_undergrad_entry_age")
    assert entry_age is not None
    assert entry_age.kind == KnowledgeKind.PLAUSIBILITY_RULE
    assert entry_age.fact_value == (19, 21)


def test_registry_contains_game_lore_relations() -> None:
    xianlian = WorldKnowledgeRegistry.get("lore.game.xianlian")
    assert xianlian is not None
    assert xianlian.kind == KnowledgeKind.ENTITY_RELATION
    assert xianlian.fact_value == "Honkai_Star_Rail"


def test_custom_registration_and_query() -> None:
    WorldKnowledgeRegistry.register(
        WorldKnowledgeItem(
            key="test.custom.key",
            kind=KnowledgeKind.STATIC_FACT,
            fact_value="CustomValue",
            domain_category="test",
            description="A test fact",
        )
    )
    item = WorldKnowledgeRegistry.get("test.custom.key")
    assert item is not None
    assert item.fact_value == "CustomValue"
