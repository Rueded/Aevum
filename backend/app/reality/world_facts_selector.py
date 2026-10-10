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



def _is_cjk(s: str) -> bool:
    """Return True if string contains any CJK ideographs or kana."""
    return bool(re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", s))


def _is_alias_match(alias: str, input_lower: str, input_tokens: set[str]) -> bool:
    """Evaluate whether an alias legitimately matches the user input text.

    Contract (Decision A.1 — 7D.6 Pure Structural Boundary):
    1. ASCII / Latin aliases: must strictly match discrete word boundaries.
       Substrings within longer English words (e.g. 'kl' inside 'sparkles')
       are strictly rejected.
    2. CJK aliases >= 3 characters: verbatim substring match permitted.
       Does NOT guarantee zero false-positives across all complex compounds
       (known limitation).
    3. CJK aliases <= 2 characters (e.g. '理大', '昔涟'):
       Strict structural boundary required. At least one boundary (left or right)
       must touch a structural delimiter:
       - String/text start or end (start == 0 or end == len(text))
       - Whitespace, punctuation, or non-CJK character
       If both left and right characters are continuous CJK characters, the occurrence
       is conservatively rejected as an embedded sub-compound (zero heuristic dictionary,
       zero alias-specific exceptions).
    """
    if not alias:
        return False

    if not _is_cjk(alias):
        # ASCII / Latin alias: enforce word boundary
        if " " in alias:
            return bool(re.search(r"\b" + re.escape(alias) + r"\b", input_lower))
        return alias in input_tokens

    # CJK alias >= 3 characters: verbatim substring match
    if len(alias) >= 3:
        return alias in input_lower

    # CJK alias <= 2 characters: pure structural boundary contract
    cjk_particles = set("的得地里中上在是个有和与同并把被让呀啊呢吧")
    for m in re.finditer(re.escape(alias), input_lower):
        start, end = m.span()
        char_before = input_lower[start - 1] if start > 0 else ""
        char_after = input_lower[end] if end < len(input_lower) else ""

        has_left_boundary = (not char_before) or (not _is_cjk(char_before)) or (char_before in cjk_particles)
        has_right_boundary = (not char_after) or (not _is_cjk(char_after)) or (char_after in cjk_particles)

        if has_left_boundary or has_right_boundary:
            return True

    return False


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
        input_lower = user_input.lower()

        matched: list[tuple[str, Any]] = []

        registry = WorldKnowledgeRegistry._REGISTRY
        for key, item in registry.items():
            # Gate 1: kind must be eligible
            if item.kind not in _ELIGIBLE_KINDS:
                continue

            # Gate 2a: token-set intersection (segment keys or tokens)
            candidate_tokens = _item_tokens(key)
            token_match = bool(candidate_tokens.intersection(input_tokens))

            # Gate 2b: Guarded alias match (Decision A.1)
            alias_match = False
            if not token_match:
                aliases = _ENTITY_ALIASES.get(key, set())
                for alias in aliases:
                    if _is_alias_match(alias, input_lower, input_tokens):
                        alias_match = True
                        break

            if not token_match and not alias_match:
                continue

            matched.append((key, item.value))

        if not matched:
            return {}

        # Sort deterministically by key, then cap
        matched.sort(key=lambda kv: kv[0])
        selected = matched[:max_items]

        return dict(selected)
