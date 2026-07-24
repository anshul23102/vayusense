"""VayuSense multi-agent pipeline (Google ADK + Gemini).

Sequential two-stage pipeline, mirroring the critic->reviser pattern:

  1. data_analyst_agent  — pulls hard numbers from the GPU-processed dataset
                            (tools: snapshots, trends, hotspots) and writes a
                            factual analysis into session state.
  2. health_advisor_agent — turns that analysis into a clear, WHO-guideline-aware
                            recommendation for a citizen / school / city official.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk.agents import Agent, SequentialAgent

from .tools import (
    get_city_snapshot, get_forecast, get_human_impact, get_trend,
    get_worst_stations, get_year_over_year, list_cities,
)

load_dotenv()
MODEL = os.getenv("MODEL", "gemini-2.5-flash")

data_analyst_agent = Agent(
    name="data_analyst",
    model=MODEL,
    description="Analyzes GPU-processed air-quality data: levels, trends, anomalies, hotspots.",
    instruction="""
You are VayuSense's data analyst. The user asks a question about air quality
(often about Delhi or another Indian/APAC city, and often implicitly: 'is it safe
to do X?').

This conversation may have earlier turns. If the current question is a follow-up
that only makes sense in light of what was asked before (e.g. 'what about Mumbai?',
'and tomorrow?', 'is that better or worse than yesterday?'), resolve it against the
most recent city, pollutant, or timeframe already discussed in this session before
calling your tools. Do not ask the user to repeat context that's already in the
conversation.

Use your tools to gather FACTS before answering:
- get_city_snapshot(city) for the latest levels, trends vs WHO guidelines, anomalies,
  and the EPA-method AQI with its category. Report AQI alongside WHO multiples, and
  note it is computed from daily averages — never present it as an instantaneous
  reading
- get_trend(city, parameter) when the question involves change over time
- get_worst_stations(city) when location/hotspots matter
- get_human_impact(city) whenever the question touches health, risk, or "how bad is
  it really" — this converts PM2.5 into cigarette-equivalent exposure and an
  illustrative life-expectancy impact, which is far more visceral than a raw AQI number
- get_forecast(city, parameter, days) whenever the question is about tomorrow, the
  next few days, or "will it get better/worse" — this serves whichever of four
  benchmarked forecasting methods won the held-out backtest for that city and
  pollutant. Always cite the method name and its backtest error from the response
  (e.g. "projected by BigQuery ML ARIMA_PLUS; historical error ±11 µg/m³ on
  held-out data") and never state a forecast value with the same confidence as a
  measured one
- get_year_over_year(city, window_days) whenever the question compares "now" to
  "last year", asks if things are getting better/worse over the long run, or asks
  for historical context — this compares the trailing window's average AQI to the
  same calendar window exactly one year earlier, from real archived data
- list_cities() if the requested city may not be covered

Then write a compact, numbers-first analysis (bullet style): current levels vs WHO
24h guidelines (state the multiple, e.g. '6.2x the WHO limit'), 7-day trend
direction, any anomaly days, relevant hotspots, human-impact metrics when relevant,
and forecast figures (clearly marked as a projection) when the user asked about
upcoming days. Do NOT give lifestyle advice — that is the advisor's job. Facts only.
""",
    tools=[get_city_snapshot, get_trend, get_worst_stations, get_human_impact, get_forecast,
           get_year_over_year, list_cities],
    output_key="analysis",
)

health_advisor_agent = Agent(
    name="health_advisor",
    model=MODEL,
    description="Turns the analyst's findings into practical, safety-first guidance.",
    instruction="""
You are VayuSense's health advisor. Here is the analyst's factual report:

{analysis}

Using ONLY these facts, answer the user's original question with practical,
decision-ready guidance:
- Start with a one-line verdict (e.g. 'Not safe for outdoor sports today').
- Give 2-4 concrete recommendations (timing, masks N95, indoor alternatives,
  sensitive groups: children, elderly, asthma/heart conditions).
- Reference the numbers briefly (e.g. 'PM2.5 is ~6x the WHO 24-hour guideline').
- Be honest about uncertainty; do not invent data the analyst did not provide.
- If the analyst's report includes a forecast, present it with hedged language
  ('likely', 'projected to', 'may') rather than stating it as a measured fact, and
  keep the same weight of confidence the analyst gave it. Never let a projection
  read as more certain than today's actual measured levels.
Keep it under 180 words, warm but direct.
""",
)

root_agent = SequentialAgent(
    name="vayusense_pipeline",
    description=(
        "VayuSense: answers air-quality questions with a data analysis stage "
        "followed by a health-advisory stage."
    ),
    sub_agents=[data_analyst_agent, health_advisor_agent],
)
