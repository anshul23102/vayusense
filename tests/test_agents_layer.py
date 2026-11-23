"""Agent layer: ADK wiring, RAG retrieval, the vision call and the advisory
generator. Gemini is never called; embeddings and the genai client are faked."""
import json
import zlib
from types import SimpleNamespace

import numpy as np
import pytest

from agents import advisory, agent, rag, tools, vision


# ---- ADK wiring --------------------------------------------------------------

def test_pipeline_is_two_stage_analyst_then_advisor():
    assert [a.name for a in agent.root_agent.sub_agents] == ["data_analyst", "health_advisor"]


def test_analyst_has_exactly_the_data_tools_and_hands_off_via_state():
    analyst = agent.data_analyst_agent
    assert {t.__name__ for t in analyst.tools} == {
        "get_city_snapshot", "get_trend", "get_worst_stations", "get_human_impact",
        "get_forecast", "get_year_over_year", "list_cities", "get_active_alerts_tool"}
    assert analyst.output_key == "analysis"
    assert "Do NOT give lifestyle advice" in analyst.instruction


def test_advisor_reads_the_analysis_and_only_has_retrieval():
    advisor = agent.health_advisor_agent
    assert "{analysis}" in advisor.instruction
    assert [t.__name__ for t in advisor.tools] == ["retrieve_guidelines"]
    assert "Using ONLY these facts" in advisor.instruction


def test_agent_text_matches_the_five_method_bench():
    # Regression: the prompt and tool docs used to say "four" methods and call
    # the archive "GPU-processed" after both stopped being true.
    assert "five" in agent.data_analyst_agent.instruction
    assert "Transformer" in tools.get_forecast.__doc__
    assert "GPU-processed" not in agent.data_analyst_agent.description


def test_model_comes_from_the_environment_with_a_sane_default():
    assert agent.MODEL


# ---- RAG ----------------------------------------------------------------------

def _hash_embed(texts, task_type):
    """Deterministic bag-of-words vectors, so similarity ranking is testable."""
    out = np.zeros((len(texts), 256))
    for i, t in enumerate(texts):
        for w in "".join(c.lower() if c.isalnum() else " " for c in t).split():
            out[i, zlib.crc32(w.encode()) % 256] += 1
    return out


@pytest.fixture
def fake_embeddings(monkeypatch):
    monkeypatch.setattr(rag, "_embed", _hash_embed)
    rag._corpus_embeddings.cache_clear()
    yield
    rag._corpus_embeddings.cache_clear()


def test_a_query_identical_to_a_passage_retrieves_that_passage_first(fake_embeddings):
    for entry in rag.CORPUS:
        top = rag.retrieve_guidelines(entry["text"], top_k=1)
        assert entry["text"] in top and entry["source"] in top


def test_results_are_ordered_by_descending_similarity(fake_embeddings):
    query = "WHO ozone guideline 100 8-hour"
    lines = rag.retrieve_guidelines(query, top_k=5).splitlines()
    q = _hash_embed([query], "q")[0]
    sims = []
    for line in lines:
        text = next(c["text"] for c in rag.CORPUS if c["text"] in line)
        v = _hash_embed([text], "d")[0]
        sims.append(float(v @ q / (np.linalg.norm(v) * np.linalg.norm(q))))
    assert sims == sorted(sims, reverse=True)
    assert len(lines) == 5


def test_retrieval_respects_top_k(fake_embeddings):
    assert len(rag.retrieve_guidelines("ozone", top_k=1).splitlines()) == 1


def test_corpus_is_well_formed():
    ids = [c["id"] for c in rag.CORPUS]
    assert len(ids) == len(set(ids))
    assert all(c["source"] and c["text"] for c in rag.CORPUS)


def test_corpus_figures_agree_with_the_constants_the_app_uses():
    # The WHO 24-hour passage and the tool constants must not drift apart.
    who24 = next(c["text"] for c in rag.CORPUS if c["id"] == "who_24h")
    for key, value in tools.WHO_24H.items():
        if key != "co":
            assert str(int(value)) in who24
    # 8x and 4x claims in the CPCB passage follow from 40/5 and 60/15
    assert 40 / 5 == 8 and 60 / 15 == 4


# ---- vision --------------------------------------------------------------------

def test_vision_prompt_carries_city_aqi_and_the_not_a_measurement_caveat(monkeypatch):
    captured = {}

    class FakeModels:
        def generate_content(self, model, contents):
            captured["model"], captured["contents"] = model, contents
            return SimpleNamespace(text="Hazy skyline.")

    monkeypatch.setattr(vision, "_client", lambda: SimpleNamespace(models=FakeModels()))
    out = vision.assess_sky_photo(b"\x89PNG0", "image/png", "Delhi", 187, "Poor")
    assert out == "Hazy skyline."
    assert captured["model"] == vision.MODEL
    prompt = captured["contents"][1]
    assert "Delhi" in prompt and "187" in prompt and "Poor" in prompt
    assert "not a measurement" in prompt


def test_vision_limits_and_types():
    assert vision.MAX_IMAGE_BYTES == 8 * 1024 * 1024
    assert {"image/jpeg", "image/png", "image/webp"} <= vision.ALLOWED_MIME_TYPES
    assert "application/pdf" not in vision.ALLOWED_MIME_TYPES


# ---- advisory ------------------------------------------------------------------

def _stub(monkeypatch, aqi, dominant="pm25", cigs=4.0, forecast=None):
    monkeypatch.setattr(advisory, "get_city_snapshot", lambda c: json.dumps(
        {"city": c, "aqi": aqi, "aqi_dominant": dominant}))
    monkeypatch.setattr(advisory, "get_human_impact", lambda c: json.dumps(
        {"cigarettes_per_day_equivalent": cigs}))
    monkeypatch.setattr(advisory, "get_forecast", lambda c, p, days=3: json.dumps(
        forecast or {"error": "none"}))


def test_bad_air_adds_sensitive_group_guidance(monkeypatch):
    _stub(monkeypatch, aqi=260)                     # severe
    a = advisory.generate_advisory("Delhi")
    assert a["category_key"] == "severe"
    assert "Sensitive groups needing additional precautions" in a["text"]
    assert a["cigarette_equivalent"] == 4.0


def test_good_air_does_not_alarm(monkeypatch):
    _stub(monkeypatch, aqi=40)
    a = advisory.generate_advisory("Delhi")
    assert a["category_key"] == "good"
    assert "Sensitive groups needing additional precautions" not in a["text"]


def test_advisory_always_states_its_basis(monkeypatch):
    _stub(monkeypatch, aqi=120)
    text = advisory.generate_advisory("Delhi")["text"]
    assert "EPA-method AQI from real archived sensor data" in text


@pytest.mark.parametrize("values,phrase", [
    ([100, 130], "likely to worsen"),
    ([100, 70], "likely to improve"),
    ([100, 104], "expected to hold roughly steady"),
])
def test_forecast_outlook_direction_and_hedging(monkeypatch, values, phrase):
    fc = {"method_label": "Naive persistence", "backtest_mae": 9.5,
          "forecast": [{"value": v} for v in values]}
    _stub(monkeypatch, aqi=120, forecast=fc)
    outlook = advisory._forecast_outlook("Delhi", "pm25")
    assert phrase in outlook
    assert "projected by Naive persistence" in outlook and "9.5" in outlook


def test_outlook_admits_when_there_is_no_backtest(monkeypatch):
    fc = {"method_label": "Damped trend", "backtest_mae": None, "forecast": [{"value": 5}, {"value": 5}]}
    _stub(monkeypatch, aqi=60, forecast=fc)
    assert "no held-out backtest available" in advisory._forecast_outlook("Delhi", "pm25")


def test_outlook_is_none_when_forecast_unavailable(monkeypatch):
    _stub(monkeypatch, aqi=60)
    assert advisory._forecast_outlook("Delhi", "pm25") is None


def test_unknown_city_returns_an_error_not_an_exception():
    assert "error" in advisory.generate_advisory("Atlantis")


# ---- agent tools: guards against model-chosen arguments -------------------------

def test_tool_arguments_chosen_by_the_model_are_clamped():
    assert len(json.loads(tools.get_trend("Delhi", "pm25", days=-5))["series"]) == 1
    assert len(json.loads(tools.get_worst_stations("Delhi", top_n=-1))) == 1
    assert len(json.loads(tools.get_forecast("Delhi", "pm25", days=99))["forecast"]) <= 7


def test_forecast_tool_separates_unknown_city_from_short_history():
    assert json.loads(tools.get_forecast("Atlantis", "pm25"))["error"].startswith("no ")


# ---- data freshness: the agents must not call old archive data "today" ---------

def test_snapshot_reports_how_old_its_data_is():
    snap = json.loads(tools.get_city_snapshot("Delhi"))
    as_of = max(p["latest_date"] for p in snap["pollutants"].values())
    assert snap["data_as_of"] == as_of
    assert isinstance(snap["data_age_days"], int) and snap["data_age_days"] >= 0
    assert snap["data_is_stale"] == (snap["data_age_days"] > tools.STALE_AFTER_DAYS)


def test_analyst_is_told_to_state_the_data_date_and_not_to_say_today():
    text = agent.data_analyst_agent.instruction
    assert "data_as_of" in text and "data_is_stale" in text
    assert "never present it as a live measurement" in text
    assert "data as of" in agent.health_advisor_agent.instruction.lower() or "as of" in agent.health_advisor_agent.instruction


def _stub_snapshot(monkeypatch, **extra):
    snap = {"aqi": 150, "aqi_dominant": "pm25", **extra}
    monkeypatch.setattr(advisory, "get_city_snapshot", lambda c: json.dumps(snap))
    monkeypatch.setattr(advisory, "get_human_impact", lambda c: json.dumps({"cigarettes_per_day_equivalent": 3}))
    monkeypatch.setattr(advisory, "get_forecast", lambda c, p, days=3: json.dumps({"error": "none"}))


def test_stale_advisory_says_it_is_not_a_live_measurement(monkeypatch):
    _stub_snapshot(monkeypatch, data_as_of="2026-08-19", data_age_days=91, data_is_stale=True)
    a = advisory.generate_advisory("Delhi")
    assert "Data as of 2026-08-19 (91 days old" in a["text"]
    assert "not a live measurement" in a["text"]
    assert a["data_as_of"] == "2026-08-19" and a["data_is_stale"] is True


def test_fresh_advisory_does_not_cry_stale(monkeypatch):
    _stub_snapshot(monkeypatch, data_as_of="2026-11-17", data_age_days=1, data_is_stale=False)
    a = advisory.generate_advisory("Delhi")
    assert "Data as of 2026-11-17." in a["text"]
    assert "not a live measurement" not in a["text"]


# ---- what is served must be what the scoreboard says it is ---------------------

def _bench_and_stored():
    import pandas as pd
    bench = json.loads((tools.Path(tools.__file__).resolve().parent.parent / "benchmark" / "forecast_bench.json").read_text())
    fc = pd.read_parquet(tools.DATA_DIR / "forecasts.parquet")
    return bench, fc


def test_every_series_is_served_by_its_best_method_that_has_stored_forecasts():
    bench, fc = _bench_and_stored()
    assert len(bench["series"]) == 216
    for s in bench["series"]:
        stored = set(fc[(fc["city"] == s["city"]) & (fc["parameter"] == s["parameter"])]["method"])
        out = json.loads(tools.get_forecast(s["city"], s["parameter"], 3))
        assert "error" not in out, (s["city"], s["parameter"])
        assert out["method"] in stored
        best_stored = min((m for m in s["mae"] if m in stored), key=lambda m: s["mae"][m])
        assert out["method"] == best_stored
        assert out["backtest_mae"] == s["mae"][best_stored]
        assert not out.get("fallback")
        assert out["scoreboard_winner"] == s["winner"]


def test_a_method_without_stored_forecasts_is_skipped_when_choosing_what_to_serve():
    import pandas as pd
    stored = pd.DataFrame({"method": ["naive", "gbt"]})
    mae = {"arima_plus": 0.1, "naive": 3.0, "gbt": 2.0, "transformer": 1.0}   # best two are not stored
    assert tools._served_method(stored, mae) == "gbt"
    assert tools._served_method(pd.DataFrame({"method": []}), mae) is None


def test_bench_endpoint_reports_the_served_method():
    bench, fc = _bench_and_stored()
    s = bench["series"][0]
    out = json.loads(tools.get_forecast_bench(s["city"], s["parameter"]))
    stored = set(fc[(fc["city"] == s["city"]) & (fc["parameter"] == s["parameter"])]["method"])
    assert out["series"]["served"] in stored and out["series"]["served"] in out["series"]["mae"]


# ---- "tomorrow" must mean tomorrow, not "the day after the data ends" ------------

def _data_end():
    return json.loads(tools._get_forecast_unanchored("Delhi", "pm25", 7))["last_date"]


def _fc(monkeypatch, days_after_data, days=3):
    """Pretend today is N days after the data's last day, so the tests do not depend on when the archive ends."""
    import datetime as dt
    today = dt.date.fromisoformat(_data_end()) + dt.timedelta(days=days_after_data)
    monkeypatch.setattr(tools, "_today", lambda: today)
    return json.loads(tools.get_forecast("Delhi", "pm25", days)), today


def test_forecast_from_old_data_is_flagged_and_cannot_answer_tomorrow(monkeypatch):
    out, today = _fc(monkeypatch, 30)
    assert out["forecast_is_stale"] is True
    assert all(r["days_from_today"] < 0 for r in out["forecast"])
    assert "NOT a forecast for tomorrow" in out["forecast_note"]
    assert out["today"] == str(today)


def test_days_counts_from_today_so_one_means_tomorrow(monkeypatch):
    import datetime as dt
    for lag in (1, 3, 5):
        out, today = _fc(monkeypatch, lag, days=1)
        assert out["forecast_is_stale"] is False
        assert [r["days_from_today"] for r in out["forecast"]] == [1]
        assert out["forecast"][0]["date"] == str(today + dt.timedelta(days=1))


def test_fresh_data_has_no_warning(monkeypatch):
    out, _ = _fc(monkeypatch, 1, days=3)
    assert out["forecast_note"] is None
    assert [r["days_from_today"] for r in out["forecast"]] == [1, 2, 3]


def test_a_few_days_old_data_still_forecasts_but_says_it_is_less_certain(monkeypatch):
    out, _ = _fc(monkeypatch, 4, days=2)
    assert out["forecast_is_stale"] is False
    assert "less certain" in out["forecast_note"]


def test_the_chart_keeps_rows_that_continue_from_the_last_data_point(monkeypatch):
    import datetime as dt
    end = dt.date.fromisoformat(_data_end())
    monkeypatch.setattr(tools, "_today", lambda: end + dt.timedelta(days=4))
    chart = json.loads(tools.get_forecast_for_chart("Delhi", "pm25", 3))
    assert chart["forecast"][0]["date"] == str(end + dt.timedelta(days=1))
    assert chart["forecast_is_stale"] is False        # judged on all 7 stored rows, not the 3 drawn


def test_today_follows_indian_time_not_utc(monkeypatch):
    import datetime as dt
    real = dt.datetime

    class Fake(real):
        @classmethod
        def now(cls, tz=None):
            utc = real(2026, 11, 22, 19, 31, tzinfo=dt.timezone.utc)    # 1:01 AM on 23 Nov in India
            return utc.astimezone(tz) if tz else utc

    monkeypatch.setattr(tools, "datetime", Fake)
    assert tools._today() == dt.date(2026, 11, 23)


def test_agents_are_told_how_to_handle_tomorrow():
    a = agent.data_analyst_agent.instruction
    assert "days_from_today" in a and "forecast_is_stale" in a and "'tomorrow'" in a
    assert "Never turn a projected date" in agent.health_advisor_agent.instruction


def test_stale_forecast_gives_no_upcoming_outlook(monkeypatch):
    fc = {"method_label": "Naive", "backtest_mae": 1.0, "forecast_is_stale": True,
          "forecast": [{"value": 5}, {"value": 9}]}
    monkeypatch.setattr(advisory, "get_forecast", lambda c, p, days=3: json.dumps(fc))
    assert advisory._forecast_outlook("Delhi", "pm25") is None
