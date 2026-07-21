import pytest

from agents.health_guidance import (
    CONDITIONS, CONDITION_LABELS, GUIDANCE, citation, get_guidance,
)

CATEGORY_KEYS = ["good", "moderate", "poor", "unhealthy", "severe", "hazardous"]


def test_all_conditions_have_labels():
    assert set(CONDITIONS) == set(CONDITION_LABELS)
    assert len(CONDITIONS) == 6


def test_every_cell_present_and_well_formed():
    for cond in CONDITIONS:
        assert set(GUIDANCE[cond]) == set(CATEGORY_KEYS)
        for cat in CATEGORY_KEYS:
            cell = GUIDANCE[cond][cat]
            assert isinstance(cell, dict)
            assert set(cell) == {"summary", "dos", "donts"}
            assert isinstance(cell["summary"], str) and len(cell["summary"]) > 10
            assert isinstance(cell["dos"], list) and len(cell["dos"]) >= 1
            assert isinstance(cell["donts"], list) and len(cell["donts"]) >= 1
            assert all(isinstance(x, str) and x for x in cell["dos"])
            assert all(isinstance(x, str) and x for x in cell["donts"])


def test_no_duplicate_summary_within_a_condition():
    for cond in CONDITIONS:
        summaries = [GUIDANCE[cond][cat]["summary"] for cat in CATEGORY_KEYS]
        assert len(summaries) == len(set(summaries)), f"duplicate summary in {cond}"


def test_get_guidance_returns_cell():
    assert get_guidance("asthma", "hazardous") == GUIDANCE["asthma"]["hazardous"]


def test_get_guidance_raises_on_unknown_inputs():
    with pytest.raises(KeyError):
        get_guidance("unknown_condition", "good")
    with pytest.raises(KeyError):
        get_guidance("general", "unknown_category")


def test_citation_nonempty():
    assert len(citation()) > 20
