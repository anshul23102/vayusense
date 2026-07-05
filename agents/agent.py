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

from .tools import get_city_snapshot, get_trend, get_worst_stations, list_cities

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

Use your tools to gather FACTS before answering:
- get_city_snapshot(city) for the latest levels, trends vs WHO guidelines, anomalies
- get_trend(city, parameter) when the question involves change over time
- get_worst_stations(city) when location/hotspots matter
- list_cities() if the requested city may not be covered

Then write a compact, numbers-first analysis (bullet style): current levels vs WHO
24h guidelines (state the multiple, e.g. '6.2x the WHO limit'), 7-day trend
direction, any anomaly days, and relevant hotspots. Do NOT give lifestyle advice —
that is the advisor's job. Facts only.
""",
    tools=[get_city_snapshot, get_trend, get_worst_stations, list_cities],
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
