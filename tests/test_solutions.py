import pytest

from agents.solutions import SOLUTION_LABELS, SOLUTIONS, STATUS_TABLE, citation, get_solutions

CATEGORY_KEYS = ["good", "moderate", "poor", "unhealthy", "severe", "hazardous"]
ALLOWED_STATUSES = {"Not needed", "Optional", "Recommended", "Advised", "Must"}


def test_all_solutions_have_labels():
    assert set(SOLUTIONS) == set(SOLUTION_LABELS)
    assert len(SOLUTIONS) == 4


def test_every_cell_present_and_well_formed():
    for s in SOLUTIONS:
        assert set(STATUS_TABLE[s]) == set(CATEGORY_KEYS)
        for cat in CATEGORY_KEYS:
            cell = STATUS_TABLE[s][cat]
            assert cell["status"] in ALLOWED_STATUSES
            assert isinstance(cell["tip"], str) and len(cell["tip"]) > 5


def test_get_solutions_returns_four_in_stable_order():
    out = get_solutions("hazardous")
    assert len(out) == 4
    assert [o["type"] for o in out] == SOLUTIONS
    assert all(o["status"] == "Must" for o in out)


def test_get_solutions_good_category_mostly_not_needed():
    out = get_solutions("good")
    assert all(o["status"] == "Not needed" for o in out)


def test_get_solutions_raises_on_unknown_category():
    with pytest.raises(KeyError):
        get_solutions("unknown_category")


def test_citation_nonempty():
    assert len(citation()) > 20
