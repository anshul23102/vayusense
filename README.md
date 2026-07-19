# VayuSense: AI Decision Intelligence for the Air We Breathe

**Live demo:** https://vayusense-663068003180.us-central1.run.app
**Challenge:** AI for Better Living and Smarter Communities (Gen AI Academy APAC 2026, Cohort 2 Hackathon)
**Team:** BloodWyrm (solo), Anshul Jain, IIIT Delhi

---

## The problem

Delhi NCR breathes some of the most dangerous air of any capital region on Earth. Parents, schools, clinics, and city officials all make daily decisions that depend on air quality: should sports practice happen outdoors today, should a clinic stock up on nebulizers this week, which ward needs a public advisory. The raw data to answer these questions already exists, in government and public sensor networks, but it is fragmented across stations, buried in raw CSVs, and unreadable to anyone who is not a data analyst.

VayuSense closes that gap. It takes millions of raw sensor readings, processes them at GPU speed, and turns them into a direct, human answer to the question "is it safe right now."

## What it does

**A live dashboard** shows, for each supported city, an Air Safety Score out of 100, a plain language verdict (safe, caution, hazardous), the latest reading for every tracked pollutant compared against WHO 24 hour guidelines, a 90 day pollution trend chart with a 7 day rolling average, the city's worst pollution hotspots by monitoring station, and a Human Impact panel that converts raw PM2.5 numbers into two visceral, non technical metrics: cigarette equivalent daily exposure and an estimated life expectancy impact.

**An "Ask VayuSense" chat** lets anyone type a plain language question, such as "is it safe for my kid's school to hold sports practice outdoors this week," and receive a grounded, data backed recommendation in seconds. This is powered by a two stage multi agent pipeline built on Google's Agent Development Kit (ADK) and Gemini, described below.

**A GPU benchmark** proves the core engineering claim of the project: that GPU accelerated data processing (NVIDIA cuDF and RAPIDS) makes this kind of real time, city scale analysis practical in a way that CPU bound pandas processing does not.

## Why acceleration matters here

The original GPU benchmark ran on 5,922,378 individual sensor readings pulled from the OpenAQ public archive (hosted on AWS Open Data), spanning multiple years, four Indian cities, and six pollutants (PM2.5, PM10, NO2, SO2, O3, CO). That fixed benchmark result is the honest, reproducible proof of the speedup and is not regenerated as the app grows. The live dataset has since expanded well beyond that proof of concept: it now spans ten Indian cities (Delhi, Mumbai, Kolkata, Chennai, Bengaluru, Hyderabad, Pune, Ahmedabad, Lucknow, and Patna), all six pollutants, and close to 13 million combined raw sensor readings across both ingestion runs. Turning that raw firehose into a usable daily snapshot requires cleaning, resampling to daily means per city and pollutant, computing 7 day rolling trends, and flagging anomaly days.

Run on pandas (CPU), that pipeline takes **9.34 seconds**. Run on NVIDIA cuDF and RAPIDS on a T4 GPU (Google Colab), the identical pipeline takes **0.249 seconds**, a **37.5x speedup**. The benchmark notebook and its raw output are in `benchmark/vayusense_gpu_benchmark.ipynb`, with the recorded result in `benchmark/benchmark_results.json` and displayed live at `/api/benchmark` on the deployed app.

This is not a cosmetic optimization. A pipeline that takes 9 seconds instead of a quarter second is the difference between a nightly batch report and a dashboard that can refresh on demand, per city, per pollutant, whenever a parent or official actually needs an answer. Faster processing directly enables the "decision intelligence" framing of this project: fresher data means better, more timely decisions.

## Architecture

```
                    OpenAQ public archive (AWS S3)
                    millions of raw sensor readings
                                |
                                v
          NVIDIA layer: cuDF / RAPIDS on T4 GPU (Google Colab)
          clean -> resample to daily -> 7 day rolling trend -> anomaly flag
          (benchmarked at 37.5x faster than pandas on CPU)
                                |
                                v
              Processed parquet datasets (data/processed/)
              daily_city.parquet, station_league.parquet
                                |
                                v
        Google Cloud layer: ADK multi agent pipeline (Gemini 2.5 Flash)
        data_analyst_agent  ->  health_advisor_agent
        (facts and figures)     (plain language, safety first guidance)
                                |
                                v
            FastAPI web application (app/main.py)
            dashboard UI + REST API + "Ask VayuSense" chat endpoint
                                |
                                v
              Deployed container (Docker, Cloud Run / Render)
```

## Multi agent design (Google ADK + Gemini)

VayuSense uses a **sequential two agent pipeline**, defined in `agents/agent.py`, that mirrors an analyst then advisor workflow:

1. **`data_analyst_agent`** receives the user's question and is instructed to gather facts before saying anything. It has access to five tools (`agents/tools.py`): `get_city_snapshot`, `get_trend`, `get_worst_stations`, `get_human_impact`, and `list_cities`. It writes a compact, numbers first analysis: current pollutant levels versus WHO 24 hour guidelines, expressed as a multiple (for example, "6.2 times the WHO limit"), the 7 day trend direction, any anomaly days, relevant pollution hotspots, and human impact metrics when relevant. This agent is explicitly instructed not to give advice, only facts.
2. **`health_advisor_agent`** receives the analyst's factual report through ADK's session state (`output_key="analysis"`) and turns it into practical, decision ready guidance: a one line verdict, two to four concrete recommendations (timing, N95 masks, indoor alternatives, extra caution for children, the elderly, and those with respiratory or heart conditions), and a brief reference back to the underlying numbers. It is instructed to stay grounded in the analyst's facts and never invent data.

This separation of concerns, facts first and then advice, keeps the system's recommendations auditable and reduces the risk of a language model inventing numbers.

The chat also carries conversational memory: each browser session keeps a stable `session_id` that both agents share across turns through ADK's session service, and the data analyst is explicitly instructed to resolve follow-up questions (`"what about Mumbai?"`, `"and tomorrow?"`) against the most recently discussed city, pollutant, or timeframe rather than asking the user to repeat context. A "New chat" control in the UI lets a user deliberately start a fresh session.

## Human impact methodology

Raw AQI and PM2.5 numbers do not mean much to a non expert. `get_human_impact` (in `agents/tools.py`) converts a city's annual average PM2.5 concentration into two more visceral, decision relevant metrics:

- **Cigarette equivalent exposure**: using the Berkeley Earth methodology, where sustained exposure to 22 micrograms per cubic meter of PM2.5 over 24 hours is treated as roughly equivalent to smoking one cigarette.
- **Estimated life expectancy impact**: using an AQLI style coefficient of approximately 0.98 years of life expectancy lost per additional 10 micrograms per cubic meter of PM2.5 sustained above the WHO annual guideline of 5 micrograms per cubic meter.

Both metrics are clearly labeled in the API response as illustrative, decision support estimates, not medical or actuarial diagnoses.

## Technology stack

**Google Cloud**
- Gemini 2.5 Flash as the underlying language model for both agents
- Google Agent Development Kit (ADK) for the sequential multi agent orchestration and session state management
- Container deployment path compatible with Cloud Run (Dockerfile in `deploy/`)

**NVIDIA**
- cuDF and RAPIDS for GPU accelerated dataframe processing (clean, resample, rolling trend, anomaly detection)
- NVIDIA T4 GPU (via Google Colab) as the benchmark and processing hardware

**Application layer**
- FastAPI for the backend API and server rendered dashboard
- Jinja2 templated HTML, vanilla JavaScript, and Plotly style charts on the frontend, no heavy frontend framework
- pandas and PyArrow for local data access in the served application
- Pydantic for request validation
- Docker for containerized deployment, deployed publicly on Google Cloud Run (Vertex AI mode for Gemini access, backed by real Cloud Billing quota)

**Data source**
- OpenAQ, a global, public, open air quality data archive, accessed via its AWS Open Data S3 bucket

## Repository layout

```
ingest/           OpenAQ archive discovery and bulk download scripts
benchmark/        cuDF vs pandas GPU benchmark notebook, results, and plot
agents/           ADK agent definitions (analyst, advisor) and their data tools
app/              FastAPI application: routes, templates, static assets
data/             Raw and GPU processed datasets (parquet)
deploy/           Dockerfile and deployment configuration
docs/             Pitch deck, architecture diagrams, and submission assets
render.yaml       One click Render deployment blueprint (alternate deployment path)
```

## API reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Public landing page |
| `/dashboard` | GET | Main interactive dashboard |
| `/api/cities` | GET | List of cities available in the dataset |
| `/api/snapshot?city=` | GET | Latest pollutant levels, trend, and WHO comparison for a city |
| `/api/trend?city=&parameter=&days=` | GET | Time series of daily and 7 day rolling values for one pollutant |
| `/api/stations?city=` | GET | Worst pollution hotspots by monitoring station |
| `/api/impact?city=` | GET | Cigarette equivalent and life expectancy impact estimates |
| `/api/benchmark` | GET | Recorded GPU vs CPU benchmark results |
| `/api/ask` | POST | Natural language question, answered by the ADK agent pipeline |

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create a .env file with:
#   GOOGLE_GENAI_USE_VERTEXAI=FALSE
#   GOOGLE_API_KEY=your_gemini_api_key
#   MODEL=gemini-2.5-flash

uvicorn app.main:app --reload --port 8090
```

Then open `http://localhost:8090` for the landing page or `http://localhost:8090/dashboard` for the dashboard.

## Deployment

VayuSense ships as a single Docker container (`deploy/Dockerfile`) and is deployed publicly on Google Cloud Run, using Vertex AI mode for Gemini access so the agent pipeline draws on real Cloud Billing quota instead of a rate limited API key. The same image also deploys cleanly to Render via the included `render.yaml` blueprint as an alternate path. The GPU benchmark itself is run separately, offline, on a Colab T4 instance, since the production web application serves already processed data and does not require live GPU access at request time.

## Credits

Built solo for the Gen AI Academy APAC Cohort 2 Hackathon by **Anshul Jain** (Team BloodWyrm), IIIT Delhi. Air quality data courtesy of the [OpenAQ](https://openaq.org) project.
