from app.main import solutions_api


def test_solutions_api_shape():
    out = solutions_api(category="hazardous")
    assert out["category"] == "hazardous"
    assert len(out["solutions"]) == 4
    assert all(s["status"] == "Must" for s in out["solutions"])
    assert len(out["citation"]) > 20


def test_solutions_api_unknown_category():
    from starlette.responses import JSONResponse
    out = solutions_api(category="not_a_real_category")
    assert isinstance(out, JSONResponse)
    assert out.status_code == 404
