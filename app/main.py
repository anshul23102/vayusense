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
    session_id: str | None = None


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


@app.get("/api/forecast")
def forecast(city: str = "Delhi", parameter: str = "pm25", days: int = 3):
    return json.loads(data_tools.get_forecast(city, parameter, days))


@app.get("/api/benchmark")
def benchmark():
    f = ROOT / "benchmark" / "benchmark_results.json"
    if f.exists():
        return json.loads(f.read_text())
    return JSONResponse({"error": "benchmark not yet generated"}, status_code=404)


@app.post("/api/ask")
async def ask(body: AskBody):
    question = body.question.strip()
    if not question:
        return JSONResponse({"error": "Please type a question first."}, status_code=400)
    if len(question) > 500:
        return JSONResponse({"error": "That question is too long. Try something shorter."}, status_code=400)

    try:
        session_id = body.session_id or str(uuid.uuid4())
        session = await runner.session_service.get_session(
            app_name="vayusense", user_id="web", session_id=session_id
        )
        if session is None:
            session = await runner.session_service.create_session(
                app_name="vayusense", user_id="web", session_id=session_id
            )
        content = types.Content(role="user", parts=[types.Part.from_text(text=question)])
        answer, analysis = "", ""
        async for event in runner.run_async(
            user_id="web", session_id=session.id, new_message=content
        ):
            if event.content and event.content.parts and event.content.parts[0].text:
                if event.author == "data_analyst":
                    analysis = event.content.parts[0].text
                else:
                    answer = event.content.parts[0].text
        if not (answer or analysis):
            return JSONResponse(
                {"error": "The agent didn't return an answer. Please try rephrasing your question."},
                status_code=502,
            )
        return {"answer": answer or analysis, "analysis": analysis, "session_id": session.id}
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            friendly = "VayuSense is getting a lot of questions right now (API rate limit). Please wait a few seconds and try again."
        else:
            friendly = "Something went wrong answering that question. Please try again in a moment."
        return JSONResponse({"error": friendly}, status_code=503)
