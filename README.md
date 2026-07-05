# VayuSense — AI Decision Intelligence for the Air We Breathe

**Challenge:** AI for Better Living and Smarter Communities (Gen AI Academy APAC 2026 — Cohort 2 Hackathon)

Delhi-NCR breathes the most dangerous air of any capital region on Earth. Parents, schools, clinics, and city officials make daily decisions — *Should sports practice happen outdoors? Should the clinic stock up on nebulizers this week? Which ward needs an advisory today?* — with data that is fragmented, slow, and unreadable to non-experts.

**VayuSense** turns millions of raw air-sensor readings into decisions:

- **Real data, real scale** — multi-year, multi-station readings from the [OpenAQ](https://openaq.org) global archive (AWS Open Data), for Delhi-NCR and major APAC cities.
- **⚡ GPU-accelerated analytics (NVIDIA cuDF/RAPIDS)** — the full clean→resample→rolling-trend→anomaly pipeline runs **~20× faster on GPU than pandas**, proven with a reproducible benchmark. Faster pipeline → fresher insight → better decisions.
- **🤖 Multi-agent intelligence (Google ADK + Gemini)** — a sequential agent pipeline (Data Analyst → Health Advisor) that answers plain-language questions with grounded, WHO-guideline-aware recommendations.
- **🌐 A tool people actually use** — a clean web dashboard: city trends, next-day outlook, health guidance, and an "Ask VayuSense" agent chat. Deployed publicly.

## Architecture

```
OpenAQ archive (S3, public)          NVIDIA layer                    Google Cloud layer
   millions of rows      ─────▶  cuDF / RAPIDS on GPU  ─────▶  processed parquet
                                  (benchmark vs pandas)              │
                                                                     ▼
                                                     ADK multi-agent (Gemini)
                                                     data_analyst → health_advisor
                                                                     │
                                                                     ▼
                                                        FastAPI dashboard (Cloud Run)
```

## Repo layout

- `ingest/` — OpenAQ archive discovery + bulk download
- `benchmark/` — the cuDF vs pandas GPU benchmark notebook (run on Colab T4) + results
- `agents/` — ADK agent definitions (analyst, advisor, pipeline)
- `app/` — FastAPI web app (dashboard + agent chat)
- `deploy/` — Dockerfile + Cloud Run deploy notes
- `docs/` — deck, demo script, architecture

## Quickstart

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Built solo by **Anshul Jain** (Team BloodWyrm), IIIT Delhi.
