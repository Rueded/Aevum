"""World Facts Selector for Phase 7D.5 — Context-Aware Lexical Relevance Selection.

Selects objective world facts from WorldKnowledgeRegistry that are lexically relevant
to the current conversation turn.

Hard Invariants (7D.5 Architecture Gate):
1. Normalize both user_input and registry item fields before matching.
2. Only STATIC_FACT and ENTITY_RELATION items are eligible. PLAUSIBILITY_RULE
   and TEMPORAL_RULE are NEVER included in world_facts for prompt context.
3. Selection is based on lexical/entity/key overlap only — no embeddings, no
   vector search, no semantic model.
4. No match → returns {} (empty dict). Never falls back to registry order.
5. An item is included only if it has a lexical match in user_input.
6. Cap: at most MAX_CONTEXT_WORLD_ITEMS items returned.
7. Deterministic ordering: matched items sorted by key (alphabetical) for
   identical input and registry state.
"""

import re
from typing import Any

from app.reality.world_knowledge import KnowledgeKind, WorldKnowledgeRegistry

# Maximum number of world facts to include in a single turn's context.
# Mirrors RealityContextBuilder.MAX_CONTEXT_WORLD_ITEMS (frozen 7D.4).
MAX_CONTEXT_WORLD_ITEMS: int = 4

# ---------------------------------------------------------------------------
# Static alias map.
# Purpose: allow matching of registry items via common synonyms or translations.
# This is an AUXILIARY matching mechanism only — the authoritative fact value
# always comes from the registry, never from this alias map.
# ---------------------------------------------------------------------------
_ENTITY_ALIASES: dict[str, set[str]] = {
    "world.usm.main_campus": {
        "usm",
        "universiti sains malaysia",
        "槟城大学",
        "理大",
    },
    "world.usm.engineering_campus": {
        "usm",
        "nibong tebal",
        "理大工程",
    },
    "world.usm.health_campus": {
        "usm",
        "kubang kerian",
        "理大医",
    },
    "world.usm.kl_centre": {
        "usm",
        "kuala lumpur",
        "kl",
        "吉隆坡",
        "理大kl",
    },
    "world.um.main_campus": {
        "universiti malaya",
        "um",
        "kuala lumpur",
        "kl",
        "马大",
        "吉隆坡",
    },
    "world.astronomy.sun_rises": {
        "sun",
        "太阳",
        "日出",
        "sunrise",
        "rises",
    },
    "world.astronomy.sun_sets": {
        "sun",
        "太阳",
        "日落",
        "sunset",
        "sets",
    },
    "lore.game.xianlian": {
        "昔涟",
        "xianlian",
        "honkai",
        "star rail",
        "崩坏",
        "hsr",
    },
    "lore.game.xianlian.game": {
        "昔涟",
        "xianlian",
        "honkai",
        "star rail",
        "崩坏",
        "hsr",
    },
}

# Kinds eligible for inclusion in world_facts prompt context.
_ELIGIBLE_KINDS: frozenset[KnowledgeKind] = frozenset({
    KnowledgeKind.STATIC_FACT,
    KnowledgeKind.ENTITY_RELATION,
})


def _normalize(text: str) -> set[str]:
    """Lowercase and tokenize text into a set of non-empty tokens.

    Splits on any non-alphanumeric-or-CJK character so that both
    Latin and Chinese/Japanese/Korean tokens are preserved.
    """
    text = text.lower()
    # Split on sequences of characters that are not alphanumeric and not CJK
    tokens = re.split(r"[^\w\u4e00-\u9fff\u3040-\u30ff]+", text)
    return {t for t in tokens if t}


def _item_tokens(key: str) -> set[str]:
    """Return the full set of match tokens for a registry item key.

    Combines:
    - Key segments (split on '.')
    - Any aliases registered in _ENTITY_ALIASES for this key
    """
    segments = set(key.lower().split("."))
    aliases = _ENTITY_ALIASES.get(key, set())
    # Flatten alias phrases into individual tokens as well
    alias_tokens: set[str] = set()
    for alias in aliases:
        alias_tokens.update(_normalize(alias))
    return segments | alias_tokens


class WorldFactsSelector:
    """Context-aware lexical world fact selector for 7D.5 orchestration.

    Selects objective world facts from WorldKnowledgeRegistry whose content
    is lexically relevant to the current user turn.

    This is intentionally a LEXICAL selector, not a semantic retrieval system.
    It will be replaced or extended in a future phase if semantic retrieval
    is required — changes to this class do not affect any other component.
    """

    @classmethod
    def select_for_turn(
        cls,
        user_input: str,
        max_items: int = MAX_CONTEXT_WORLD_ITEMS,
    ) -> dict[str, Any]:
        """Return a dict of contextually relevant world facts for this turn.

        Args:
            user_input: Raw user message text for the current turn.
            max_items: Maximum number of facts to include (default 4).

        Returns:
            dict mapping fact key → fact value for matched registry items,
            sorted by key (alphabetical) for determinism.
            Returns {} if no eligible items match.

        Invariants (never violated):
        - Only STATIC_FACT and ENTITY_RELATION items are returned.
        - Items are only included when they have lexical overlap with user_input.
        - Never falls back to registry insertion order.
        - Output is deterministic for identical input + registry state.
        """
        if not user_input or not user_input.strip():
            return {}

        input_tokens = _normalize(user_input)
        input_lower = user_input.lower()  # used for CJK alias substring check

        matched: list[tuple[str, Any]] = []

        registry = WorldKnowledgeRegistry._REGISTRY
        for key, item in registry.items():
            # Gate 1: kind must be eligible
            if item.kind not in _ELIGIBLE_KINDS:
                continue

            # Gate 2a: token-set intersection (works for Latin/single-char tokens)
            candidate_tokens = _item_tokens(key)
            token_match = bool(candidate_tokens.intersection(input_tokens))

            # Gate 2b: CJK alias substring check
            # Required because CJK word-boundary tokenization keeps adjacent characters
            # as one long token (e.g., "昔涟这个游戏" → one token), so multi-char
            # CJK aliases cannot be matched via token intersection alone.
            cjk_alias_match = False
            if not token_match:
                aliases = _ENTITY_ALIASES.get(key, set())
                for alias in aliases:
                    # Check if the alias phrase appears verbatim in the lowercased input
                    if alias and alias in input_lower:
                        cjk_alias_match = True
                        break

            if not token_match and not cjk_alias_match:
                continue

            matched.append((key, item.value))

        if not matched:
            return {}

        # Sort deterministically by key, then cap
        matched.sort(key=lambda kv: kv[0])
        selected = matched[:max_items]

        return dict(selected)
