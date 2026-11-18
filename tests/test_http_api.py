"""Real HTTP-level tests (routing, status codes, headers, rate limits) through
FastAPI's TestClient. The Gemini runner and the vision call are replaced with
fakes, so nothing here needs the network or spends a billed call."""
import json
from collections import defaultdict, deque
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    # No live OpenAQ calls, and fresh rate-limit buckets for every test.
    monkeypatch.setattr(main.live, "get_live_city", lambda city: None)
    monkeypatch.setattr(main.live, "peek_live_city", lambda city: None)
    monkeypatch.setattr(main, "_ask_hits", defaultdict(deque))
    monkeypatch.setattr(main, "_vision_hits", defaultdict(deque))


# ---- fake ADK runner -------------------------------------------------------

class _Event:
    def __init__(self, author, text=None, calls=(), partial=False):
        self.author = author
        self.partial = partial
        self._calls = calls
        self.content = (SimpleNamespace(parts=[SimpleNamespace(text=text)])
                        if text is not None else None)

    def get_function_calls(self):
        return [SimpleNamespace(name=n, args=a) for n, a in self._calls]


def _fake_runner(monkeypatch, events=None, boom=None):
    async def run_async(**kwargs):
        if boom:
            raise boom
        for e in events or []:
            yield e
    monkeypatch.setattr(main.runner, "run_async", run_async)


# ---- error contract --------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/api/snapshot?city=Atlantis",
    "/api/trend?city=Atlantis&parameter=pm25",
    "/api/trend?city=Delhi&parameter=zzz",
    "/api/stations?city=Atlantis",
    "/api/impact?city=Atlantis",
    "/api/yoy?city=Atlantis",
    "/api/forecast?city=Atlantis&parameter=pm25",
    "/api/forecast_bench?city=Atlantis&parameter=pm25",
    "/api/calendar?city=Atlantis",
    "/api/monthly?city=Atlantis",
    "/api/aqi?city=Atlantis",
    "/api/advisory?city=Atlantis",
    "/api/export?city=Atlantis",
])
def test_unknown_things_are_404_not_200(path):
    r = client.get(path)
    assert r.status_code == 404
    assert "error" in r.json()


@pytest.mark.parametrize("path", [
    "/api/snapshot?city=Delhi",
    "/api/trend?city=Delhi&parameter=pm25",
    "/api/stations?city=Delhi",
    "/api/impact?city=Delhi",
    "/api/yoy?city=Delhi",
    "/api/forecast?city=Delhi&parameter=pm25",
    "/api/forecast_bench?city=Delhi&parameter=pm25",
    "/api/calendar?city=Delhi&year=2026",
    "/api/monthly?city=Delhi",
    "/api/aqi?city=Delhi",
    "/api/advisory?city=Delhi",
    "/api/alerts",
    "/api/benchmark",
    "/api/health_guidance",
])
def test_valid_requests_are_200(path):
    r = client.get(path)
    assert r.status_code == 200, r.text[:200]
    assert "error" not in r.json()


def test_non_numeric_query_param_is_422():
    assert client.get("/api/trend?city=Delhi&parameter=pm25&days=abc").status_code == 422


def test_out_of_range_numbers_are_clamped_not_crashing():
    assert client.get("/api/trend?city=Delhi&parameter=pm25&days=-5").status_code == 200
    assert len(client.get("/api/trend?city=Delhi&parameter=pm25&days=-5").json()["series"]) == 1
    big = client.get("/api/trend?city=Delhi&parameter=pm25&days=999999999").json()
    assert len(big["series"]) <= 3650
    fc = client.get("/api/forecast?city=Delhi&parameter=pm25&days=100").json()
    assert len(fc["forecast"]) <= 7


def test_unknown_solutions_category_404():
    assert client.get("/api/solutions?category=nope").status_code == 404


# ---- export ----------------------------------------------------------------

def test_export_csv_and_json():
    csv_r = client.get("/api/export?city=Delhi&format=csv")
    assert csv_r.status_code == 200
    assert csv_r.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv_r.headers["content-disposition"]
    assert csv_r.text.splitlines()[0].startswith("date,parameter,daily_mean")
    js = client.get("/api/export?city=Delhi&format=json").json()
    assert js["rows"] == len(js["data"]) > 0


def test_export_rejects_unknown_format():
    r = client.get("/api/export?city=Delhi&format=xml")
    assert r.status_code == 400
    assert "csv or json" in r.json()["error"]


# ---- pages, headers, hardening ----------------------------------------------

def test_security_headers_on_every_response():
    for path in ["/", "/dashboard", "/api/cities", "/city/delhi", "/nope"]:
        h = client.get(path).headers
        assert "default-src 'self'" in h["content-security-policy"]
        assert "frame-ancestors 'none'" in h["content-security-policy"]
        assert "object-src 'none'" in h["content-security-policy"]
        assert h["x-content-type-options"] == "nosniff"
        assert h["x-frame-options"] == "DENY"
        assert "max-age=31536000" in h["strict-transport-security"]
        assert "camera=()" in h["permissions-policy"]


def test_api_docs_are_not_exposed():
    for path in ["/docs", "/redoc", "/openapi.json"]:
        assert client.get(path).status_code == 404


def test_city_page_is_slug_whitelisted():
    ok = client.get("/city/delhi")
    assert ok.status_code == 200
    assert "let CITY='Delhi';" in ok.text
    assert "<title>VayuSense: Delhi Air Quality</title>" in ok.text
    assert client.get("/city/DELHI").status_code == 200
    for evil in ["%3Cscript%3Ealert(1)%3C%2Fscript%3E", "..%2F..%2Fetc%2Fpasswd", "x'%3Balert(1)%3B'"]:
        r = client.get(f"/city/{evil}")
        assert r.status_code == 404
        assert "<script>" not in r.text


def test_static_path_traversal_blocked():
    assert client.get("/static/../app/main.py").status_code == 404
    assert client.get("/static/%2e%2e/app/main.py").status_code == 404


def test_html_is_revalidated_and_static_is_cacheable():
    assert "no-cache" in client.get("/").headers["cache-control"]
    assert "must-revalidate" in client.get("/static/benchmark.png").headers["cache-control"]


def test_share_card_is_a_png():
    r = client.get("/city/delhi/card.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


# ---- advisory ---------------------------------------------------------------

def test_advisory_batch_covers_every_city():
    cities = client.get("/api/cities").json()
    r = client.get("/api/advisory/all").json()
    assert r["count"] == len(cities) == 36
    assert {a["city"] for a in r["advisories"]} == set(cities)
    assert all(a["text"].strip() for a in r["advisories"])


def test_single_advisory_has_the_expected_shape():
    a = client.get("/api/advisory?city=Delhi").json()
    assert {"city", "aqi", "category", "dominant_pollutant", "text"} <= set(a)
    assert a["text"].startswith("DELHI AIR QUALITY ADVISORY")


# ---- /api/ask ---------------------------------------------------------------

def test_ask_validation(monkeypatch):
    _fake_runner(monkeypatch, [])
    assert client.post("/api/ask", json={"question": "   "}).status_code == 400
    assert client.post("/api/ask", json={"question": "x" * 501}).status_code == 400
    assert client.post("/api/ask", json={}).status_code == 422


def test_ask_returns_answer_trace_and_session(monkeypatch):
    _fake_runner(monkeypatch, [
        _Event("data_analyst", calls=[("get_city_snapshot", {"city": "Delhi"})]),
        _Event("data_analyst", text="PM2.5 is 6x the WHO limit."),
        _Event("health_advisor", text="Avoid outdoor sports today."),
    ])
    r = client.post("/api/ask", json={"question": "Is it safe to run in Delhi?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "Avoid outdoor sports today."
    assert body["analysis"] == "PM2.5 is 6x the WHO limit."
    assert body["trace"] == [{"agent": "data_analyst", "tool": "get_city_snapshot", "args": {"city": "Delhi"}}]
    assert body["session_id"]


def test_ask_reuses_the_session_id(monkeypatch):
    _fake_runner(monkeypatch, [_Event("health_advisor", text="ok")])
    first = client.post("/api/ask", json={"question": "hi"}).json()["session_id"]
    second = client.post("/api/ask", json={"question": "and tomorrow?", "session_id": first}).json()
    assert second["session_id"] == first


def test_ask_with_no_answer_is_502(monkeypatch):
    _fake_runner(monkeypatch, [_Event("data_analyst", calls=[("list_cities", {})])])
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 502


def test_ask_hides_internal_errors_behind_a_friendly_message(monkeypatch):
    _fake_runner(monkeypatch, boom=RuntimeError("secret internal detail /srv/app.py"))
    r = client.post("/api/ask", json={"question": "hi"})
    assert r.status_code == 503
    assert "secret internal detail" not in r.text
    _fake_runner(monkeypatch, boom=RuntimeError("429 RESOURCE_EXHAUSTED quota"))
    assert "rate limit" in client.post("/api/ask", json={"question": "hi"}).json()["error"]


def test_ask_is_rate_limited_per_client(monkeypatch):
    _fake_runner(monkeypatch, [_Event("health_advisor", text="ok")])
    codes = [client.post("/api/ask", json={"question": "hi"}).status_code
             for _ in range(main.ASK_RATE_LIMIT + 2)]
    assert codes[:main.ASK_RATE_LIMIT] == [200] * main.ASK_RATE_LIMIT
    assert codes[main.ASK_RATE_LIMIT:] == [429, 429]
    # a different client (different X-Forwarded-For) has its own budget
    other = client.post("/api/ask", json={"question": "hi"}, headers={"x-forwarded-for": "9.9.9.9"})
    assert other.status_code == 200


def test_rate_limit_window_expires(monkeypatch):
    hits = defaultdict(deque)
    t = {"now": 1000.0}
    monkeypatch.setattr(main.time, "time", lambda: t["now"])
    assert [main._rate_limited("c", hits, 2, 60) for _ in range(3)] == [False, False, True]
    t["now"] += 61
    assert main._rate_limited("c", hits, 2, 60) is False


def test_client_id_uses_the_address_the_trusted_proxy_appended():
    req = SimpleNamespace(headers={"x-forwarded-for": "6.6.6.6, 1.2.3.4"}, client=SimpleNamespace(host="proxy"))
    assert main._client_id(req) == "1.2.3.4"          # right-most, not the client-supplied left value
    req = SimpleNamespace(headers={"x-forwarded-for": "1.2.3.4"}, client=SimpleNamespace(host="proxy"))
    assert main._client_id(req) == "1.2.3.4"
    req = SimpleNamespace(headers={}, client=SimpleNamespace(host="5.6.7.8"))
    assert main._client_id(req) == "5.6.7.8"


def test_a_spoofed_forwarded_for_header_cannot_dodge_the_rate_limit(monkeypatch):
    _fake_runner(monkeypatch, [_Event("health_advisor", text="ok")])
    codes = [client.post("/api/ask", json={"question": "hi"},
                         headers={"x-forwarded-for": f"10.0.0.{i}, 203.0.113.9"}).status_code
             for i in range(main.ASK_RATE_LIMIT + 2)]
    # every request claims a different left-most address; the proxy-appended one is constant
    assert codes[-1] == 429 and codes.count(200) == main.ASK_RATE_LIMIT


# ---- /api/ask/stream --------------------------------------------------------

def _sse(resp):
    return [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]


def test_stream_emits_session_tools_deltas_done_and_dedupes_tool_calls(monkeypatch):
    call = ("get_forecast", {"city": "Delhi", "parameter": "pm25"})
    _fake_runner(monkeypatch, [
        _Event("data_analyst", calls=[call]),
        _Event("data_analyst", calls=[call]),          # ADK re-emits the same call
        _Event("data_analyst", text="internal analysis"),
        _Event("health_advisor", text="Likely ", partial=True),
        _Event("health_advisor", text="Likely to worsen.", partial=False),
    ])
    r = client.post("/api/ask/stream", json={"question": "tomorrow?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    frames = _sse(r)
    assert [f["type"] for f in frames] == ["session", "tool", "delta", "delta", "done"]
    assert frames[1]["tool"] == "get_forecast"
    assert all("internal analysis" not in json.dumps(f) for f in frames)   # analyst text never streamed
    assert frames[-2] == {"type": "delta", "text": "Likely to worsen.", "partial": False}


def test_stream_reports_an_error_frame_instead_of_dropping_the_connection(monkeypatch):
    _fake_runner(monkeypatch, boom=RuntimeError("kaboom"))
    frames = _sse(client.post("/api/ask/stream", json={"question": "hi"}))
    assert frames[-1]["type"] == "error"
    assert "kaboom" not in json.dumps(frames)


def test_stream_validates_like_ask(monkeypatch):
    assert client.post("/api/ask/stream", json={"question": ""}).status_code == 400


# ---- /api/vision-check -------------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _upload(data=PNG, mime="image/png", city="Delhi"):
    return client.post(f"/api/vision-check?city={city}", files={"file": ("sky.png", data, mime)})


def test_vision_success_passes_city_and_measured_aqi_to_the_model(monkeypatch):
    seen = {}

    def fake(image_bytes, mime, city, aqi, category):
        seen.update(mime=mime, city=city, aqi=aqi, category=category, n=len(image_bytes))
        return "Looks hazy."
    monkeypatch.setattr(main, "assess_sky_photo", fake)
    r = _upload()
    assert r.status_code == 200
    assert r.json()["assessment"] == "Looks hazy."
    assert seen["city"] == "Delhi" and seen["mime"] == "image/png" and seen["n"] == len(PNG)
    assert seen["aqi"] == r.json()["aqi"]


def test_vision_rejects_wrong_type_oversize_and_unknown_city(monkeypatch):
    monkeypatch.setattr(main, "assess_sky_photo", lambda *a: "never called")
    assert _upload(mime="application/pdf").status_code == 400
    assert _upload(data=b"x" * (main.MAX_IMAGE_BYTES + 1)).status_code == 400
    assert _upload(city="Atlantis").status_code == 404


def test_vision_failure_is_503_and_does_not_leak(monkeypatch):
    def boom(*a):
        raise RuntimeError("api key AIza-secret")
    monkeypatch.setattr(main, "assess_sky_photo", boom)
    r = _upload()
    assert r.status_code == 503
    assert "AIza-secret" not in r.text


def test_vision_is_rate_limited_on_its_own_bucket(monkeypatch):
    monkeypatch.setattr(main, "assess_sky_photo", lambda *a: "ok")
    codes = [_upload().status_code for _ in range(main.VISION_RATE_LIMIT + 1)]
    assert codes[-1] == 429
    assert codes[:main.VISION_RATE_LIMIT] == [200] * main.VISION_RATE_LIMIT
    # exhausting vision does not touch the ask budget
    _fake_runner(monkeypatch, [_Event("health_advisor", text="ok")])
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 200


# ---- CSP must allow every origin the page actually loads at runtime ------------

def _csp_allows(csp_directive: str, url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).hostname
    for src in csp_directive.split()[1:]:
        if src.startswith("https://"):
            pat = src[len("https://"):]
            if pat.startswith("*."):
                if host.endswith(pat[1:]):
                    return True
            elif host == pat:
                return True
    return False


def test_any_tile_host_a_template_names_is_allowed_by_the_csp():
    import re
    from pathlib import Path
    img_src = next(d for d in main._CSP.split("; ") if d.startswith("img-src"))
    for tpl in (Path(main.ROOT) / "app" / "templates").glob("*.html"):
        for url in re.findall(r"L\.tileLayer\('([^']+)'", tpl.read_text()):
            assert _csp_allows(img_src, url.replace("{s}", "a")), f"{tpl.name}: CSP blocks {url}"


def test_dashboard_map_has_no_third_party_basemap():
    # Regression: the Carto tile endpoint now serves an "API KEY REQUIRED"
    # placeholder, so the map is drawn from the vendored state outlines instead.
    from pathlib import Path
    html = (Path(main.ROOT) / "app" / "templates" / "summary.html").read_text()
    assert "cartocdn" not in html and "tileLayer(" not in html
    assert "cartocdn" not in main._CSP
    assert (Path(main.ROOT) / "app" / "static" / "vendor" / "geo" / "india-states.geojson").exists()
