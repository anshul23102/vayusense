"""VayuSense web app — FastAPI dashboard + ADK agent chat."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from agents.agent import root_agent
from agents import tools as data_tools

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="VayuSense")
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")

runner = InMemoryRunner(agent=root_agent, app_name="vayusense")


class AskBody(BaseModel):
    question: str


@app.get("/", response_class=HTMLResponse)
def landing():
    return (ROOT / "app" / "templates" / "landing.html").read_text()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return (ROOT / "app" / "templates" / "index.html").read_text()


@app.get("/api/cities")
def cities():
    return json.loads(data_tools.list_cities())


@app.get("/api/snapshot")
def snapshot(city: str = "Delhi"):
    return json.loads(data_tools.get_city_snapshot(city))


@app.get("/api/trend")
def trend(city: str = "Delhi", parameter: str = "pm25", days: int = 60):
    return json.loads(data_tools.get_trend(city, parameter, days))


@app.get("/api/stations")
def stations(city: str = "Delhi"):
    return json.loads(data_tools.get_worst_stations(city))


@app.get("/api/impact")
def impact(city: str = "Delhi"):
    return json.loads(data_tools.get_human_impact(city))


@app.get("/api/benchmark")
def benchmark():
    f = ROOT / "benchmark" / "benchmark_results.json"
    if f.exists():
        return json.loads(f.read_text())
    return JSONResponse({"error": "benchmark not yet generated"}, status_code=404)


@app.post("/api/ask")
async def ask(body: AskBody):
    session = await runner.session_service.create_session(
        app_name="vayusense", user_id="web", session_id=str(uuid.uuid4())
    )
    content = types.Content(role="user", parts=[types.Part.from_text(text=body.question)])
    answer, analysis = "", ""
    async for event in runner.run_async(
        user_id="web", session_id=session.id, new_message=content
    ):
        if event.content and event.content.parts and event.content.parts[0].text:
            if event.author == "data_analyst":
                analysis = event.content.parts[0].text
            else:
                answer = event.content.parts[0].text
    return {"answer": answer or analysis, "analysis": analysis}
