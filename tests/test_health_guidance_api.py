from agents.health_guidance import CONDITIONS
from app.main import health_guidance_api


def test_health_guidance_api_shape():
    out = health_guidance_api()
    assert out["conditions"] == CONDITIONS
    assert set(out["labels"]) == set(CONDITIONS)
    assert set(out["guidance"]) == set(CONDITIONS)
    for cond in CONDITIONS:
        assert set(out["guidance"][cond]) == {"good", "moderate", "poor", "unhealthy", "severe", "hazardous"}
        for cat, cell in out["guidance"][cond].items():
            assert set(cell) == {"summary", "dos", "donts"}
            assert cell["dos"] and cell["donts"]
    assert len(out["citation"]) > 20
