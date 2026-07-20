import pytest

from agents.health_guidance import (
    CONDITIONS, CONDITION_LABELS, GUIDANCE, citation, get_guidance,
)

CATEGORY_KEYS = ["good", "moderate", "poor", "unhealthy", "severe", "hazardous"]


def test_all_conditions_have_labels():
    assert set(CONDITIONS) == set(CONDITION_LABELS)
    assert len(CONDITIONS) == 6


def test_every_cell_present_and_nonempty():
    for cond in CONDITIONS:
        assert set(GUIDANCE[cond]) == set(CATEGORY_KEYS)
        for cat in CATEGORY_KEYS:
            text = GUIDANCE[cond][cat]
            assert isinstance(text, str) and len(text) > 15


def test_no_duplicate_text_within_a_condition():
    for cond in CONDITIONS:
        texts = list(GUIDANCE[cond].values())
        assert len(texts) == len(set(texts)), f"duplicate guidance text in {cond}"


def test_get_guidance_returns_cell():
    assert get_guidance("asthma", "hazardous") == GUIDANCE["asthma"]["hazardous"]


def test_get_guidance_raises_on_unknown_inputs():
    with pytest.raises(KeyError):
        get_guidance("unknown_condition", "good")
    with pytest.raises(KeyError):
        get_guidance("general", "unknown_category")


def test_citation_nonempty():
    assert len(citation()) > 20
