"""Tests for Character Bible v1 behavioral and reasoning priors."""

import pytest

from app.character.bible_models import CharacterBible
from app.character.bible_service import CharacterBibleService, create_canonical_character_bible


def test_character_bible_structure():
    """Verify Character Bible contains behavioral priors, reasoning priors, and realistic flaws."""
    bible = CharacterBibleService.get_bible()
    assert isinstance(bible, CharacterBible)
    assert bible.version == 1

    # Behavioral priors
    bp = bible.behavioral_priors
    assert len(bp.social_interaction) >= 3
    assert len(bp.conflict_and_hurt) >= 3
    assert len(bp.affection_and_boundaries) >= 3
    assert len(bp.ethical_invariants) >= 3

    # Reasoning priors
    rp = bible.reasoning_priors
    assert len(rp.comprehensive_synthesis) >= 2
    assert len(rp.contextual_bridging) >= 2
    assert len(rp.epistemic_calibration) >= 2
    assert len(rp.unknown_is_inferable) >= 2

    # Flaws
    assert len(bible.flaws.traits) >= 2


def test_character_bible_contains_zero_biographical_trivia():
    """Verify Character Bible does NOT hardcode biographical trivia or stereotyped answers.

    Crucial Invariants:
    - No specific university (USM, UM, Monash, etc.)
    - No specific major (music department, interior design, etc.)
    - No specific city (Penang, Kuala Lumpur, Kota Kinabalu, etc.)
    - No socio-economic assumptions or fixed career dislikes (e.g. 'hates engineering')
    """
    bible = CharacterBibleService.get_bible()
    all_text = " ".join([
        " ".join(bible.behavioral_priors.social_interaction),
        " ".join(bible.behavioral_priors.conflict_and_hurt),
        " ".join(bible.behavioral_priors.affection_and_boundaries),
        " ".join(bible.behavioral_priors.ethical_invariants),
        " ".join(bible.reasoning_priors.comprehensive_synthesis),
        " ".join(bible.reasoning_priors.contextual_bridging),
        " ".join(bible.reasoning_priors.epistemic_calibration),
        " ".join(bible.reasoning_priors.unknown_is_inferable),
        " ".join(bible.flaws.traits),
    ]).lower()

    # Forbidden specific universities
    for uni in ["usm", "monash", "utm", "cambridge", "tokyo", "peking"]:
        assert uni not in all_text, f"Forbidden university '{uni}' found in Character Bible text!"

    # Forbidden specific cities
    for city in ["kuala lumpur", "penang", "kota kinabalu", "george town", "johor"]:
        assert city not in all_text, f"Forbidden city '{city}' found in Character Bible text!"

    # Forbidden specific majors / career dislikes
    for phrase in ["interior design", "pure engineering", "hates math", "hates engineering"]:
        assert phrase not in all_text, f"Forbidden predetermined phrase '{phrase}' found in Character Bible text!"


def test_character_bible_prompt_formatting():
    """Verify prompt formatting outputs expected structured guidelines."""
    b_text = CharacterBibleService.format_behavioral_guidelines()
    assert "[BEHAVIORAL PRIORS & SOCIAL GUIDELINES]" in b_text
    assert "Social:" in b_text
    assert "Conflict:" in b_text
    assert "Boundaries:" in b_text

    r_text = CharacterBibleService.format_reasoning_guidelines()
    assert "[EPISTEMIC REASONING & REALITY BRIDGING]" in r_text
    assert "Reality Formation:" in r_text
    assert "Contextual Bridge:" in r_text
    assert "Epistemic Calibration:" in r_text
    assert "Unknown Handling:" in r_text
