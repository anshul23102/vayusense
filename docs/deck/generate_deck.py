"""Fill the official hackathon PPT template with VayuSense content.

Formatting rules:
- Font forced to "Google Sans" everywhere (the template's own header font) so it
  renders consistently regardless of the source shape's original run font.
- Rich bold/italic emphasis per line, not flat paragraphs.
- No em dashes, no double hyphens: colons, semicolons and periods only.
"""
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor

SRC = "docs/deck/template.pptx"
OUT = "docs/deck/VayuSense_Submission_Deck.pptx"

FONT = "Google Sans"
DARK = RGBColor(0x22, 0x22, 0x22)


def shapes_by_id(slide):
    return {sh.shape_id: sh for sh in slide.shapes}


def set_plain(shape, text, size=14, bold=False):
    """Single-run replace, forcing Google Sans."""
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = DARK


def set_rich(shape, paragraphs, size=13, space_after=8, line_size=None):
    """paragraphs: list of paragraph-specs. Each spec is a list of
    (text, bold, italic) tuples rendered as consecutive runs in one paragraph."""
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    for i, spec in enumerate(paragraphs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(space_after)
        for text, bold, italic in spec:
            run = p.add_run()
            run.text = text
            run.font.name = FONT
            run.font.size = Pt(line_size or size)
            run.font.bold = bold
            run.font.italic = italic
            run.font.color.rgb = DARK


def force_font(shape, size=None):
    """Force every existing run in a shape to Google Sans (keep bold/italic as-is)."""
    for p in shape.text_frame.paragraphs:
        for r in p.runs:
            r.font.name = FONT
            if size:
                r.font.size = Pt(size)


prs = Presentation(SRC)
slides = list(prs.slides)

B = True   # bold
I = True   # italic
_ = False

# ---------------- Slide 1: Participant details ----------------
s = shapes_by_id(slides[0])
tf = s[55].text_frame
for p in tf.paragraphs:
    full = "".join(r.text for r in p.runs)
    if full.strip().startswith("Participant Name"):
        for r in p.runs:
            r.text = ""
            r.font.name = FONT
        p.runs[0].text = "Participant Name: Anshul Jain (Team BloodWyrm, Solo)"
    elif full.strip().startswith("Problem Statement"):
        for r in p.runs:
            r.text = ""
            r.font.name = FONT
        p.runs[0].text = ("Problem Statement: AI for Better Living and Smarter Communities. "
                           "Create a data intelligence tool people would actually use, and show "
                           "how acceleration helps them make a faster or better decision.")

# ---------------- Slide 2: Brief about the idea ----------------
s = shapes_by_id(slides[1])
set_rich(s[62], [
    [("VayuSense", B, _), (" is an AI ", _, _), ("Decision Intelligence Platform", B, _),
     (" that turns millions of raw air quality sensor readings across Indian and APAC cities "
      "into one honest, decision-ready answer, for parents, schools, clinics, and city officials.", _, _)],
    [("It pairs ", _, _), ("NVIDIA RAPIDS", B, _), (" accelerated data processing (", _, _),
     ("37.5× faster", B, I), (" than pandas over ", _, _), ("5.9M+ real OpenAQ sensor readings", B, _),
     (") with a ", _, _), ("Google ADK", B, _), (" multi-agent pipeline (", _, _),
     ("Data Analyst → Health Advisor", I, _), (", powered by ", _, _), ("Gemini", B, _),
     (") to go beyond a raw AQI number: surfacing a ", _, _), ("Safety Score", B, _),
     (" and a ", _, _), ("Human Impact", B, _),
     (" metric (cigarette-equivalent exposure, illustrative life-expectancy impact) that most "
      "air quality tools never show.", _, _)],
    [("Built solo, fully deployed, and designed to scale", B, I),
     (" from a hackathon prototype into a real public-health decision tool for any city.", _, _)],
], size=14, space_after=14)

# ---------------- Slide 3: Approach / impact / architecture ----------------
s = shapes_by_id(slides[2])
force_font(s[70], size=11)
for p in s[70].text_frame.paragraphs:
    p.space_after = Pt(4)
s[68].height = Emu(1500000)
s[68].top = Emu(3550000)
set_rich(s[68], [
    [("Approach: ", B, _), ("Ingested ", _, _), ("5.9M+ real OpenAQ sensor readings", B, _),
     ("; built a GPU-accelerated (", _, _), ("NVIDIA cuDF/RAPIDS", B, _),
     (") pipeline for cleaning, trend and anomaly analysis; layered a ", _, _),
     ("Google ADK Sequential multi-agent system", B, _), (" (Data Analyst → Health Advisor) on ", _, _),
     ("Gemini", B, _), (" to reason over the results; shipped as a publicly deployed FastAPI app.", _, _)],
    [("Real-world impact: ", B, _), ("Delhi-NCR breathes the world's most hazardous urban air. ", _, _),
     ("VayuSense", I, _), (" turns that into a same-day decision for schools (sports practice), "
      "clinics (staffing), and city wards (advisories); not just another chart nobody reads.", _, _)],
    [("Architecture: ", B, _), ("OpenAQ archive → NVIDIA RAPIDS cuDF (GPU) → Google ADK/Gemini "
      "agents → FastAPI dashboard → end users. Converting raw sensor data into a ", _, _),
     ("Safety Score", B, _), (", a ", _, _), ("Human Impact", B, _),
     (" estimate, and a plain-language, decision-ready recommendation.", _, _)],
], size=10.5, space_after=8)

# ---------------- Slide 4: Opportunities / USP ----------------
s = shapes_by_id(slides[3])
set_rich(s[77], [
    [("Proven acceleration, not a claim. ", B, _),
     ("An honest, reproducible ", _, _), ("37.5× cuDF-vs-pandas benchmark", B, I),
     (" over 5.9M+ real rows; most entries will show a number with no receipts.", _, _)],
    [("Human stakes, not just AQI. ", B, _),
     ("Cigarette-equivalent exposure and an illustrative life-expectancy impact, grounded in "
      "published air quality epidemiology (Berkeley Earth, AQLI-style); a stat most air quality "
      "tools never surface.", _, _)],
    [("A true multi-agent pipeline, not a prompt wrapper. ", B, _),
     ("Google ADK Sequential agents: the ", _, _), ("Data Analyst", I, _),
     (" gathers facts with real tools; the ", _, _), ("Health Advisor", I, _),
     (" reasons over them.", _, _)],
    [("Answers the brief end to end. ", B, _),
     ("A real ingest, clean, model, visualize pipeline; 2+ Google Cloud layer items; 2+ NVIDIA "
      "layer items; a genuinely useful output.", _, _)],
    [("Built to scale beyond the hackathon. ", B, _),
     ("The same architecture works for any city or pollutant dataset; just repoint the ingestion.", _, _)],
], size=12.5, space_after=7)

# ---------------- Slide 5: Features ----------------
s = shapes_by_id(slides[4])
set_rich(s[84], [
    [("Live multi-city dashboard", B, _), (" (Delhi, Mumbai, Kolkata, Chennai) with 90-day trend "
      "and 7-day rolling average per pollutant", _, _)],
    [("Safety Score", B, _), (" (0 to 100) with a plain-language verdict for each city", _, _)],
    [("Human Impact panel: ", B, _), ("cigarette-equivalent exposure and estimated "
      "life-expectancy impact", _, _)],
    [("Pollution hotspot ranking", B, _), (" of the worst-performing stations per city", _, _)],
    [("“Ask VayuSense”", B, I), (" natural-language chat, a ", _, _),
     ("Google ADK multi-agent pipeline", B, _), (" (Data Analyst → Health Advisor) on Gemini", _, _)],
    [("GPU-accelerated backend analytics", B, _), (" (NVIDIA RAPIDS cuDF) with a live benchmark panel", _, _)],
    [("Fully deployed, publicly accessible web app", B, _),
     (" with WHO-guideline comparisons across 6 pollutants", _, _)],
], size=13, space_after=10)

# ---------------- Slide 6: Process flow diagram ----------------
s = shapes_by_id(slides[5])
set_plain(s[91], " ", size=1)
slides[5].shapes.add_picture("docs/deck/diagram_flow.png", Emu(463125), Emu(1180000), width=Emu(8270400))

# ---------------- Slide 7: Wireframe / landing page ----------------
s = shapes_by_id(slides[6])
set_plain(s[98], " ", size=1)
slides[6].shapes.add_picture("docs/deck/screenshots/landing.png", Emu(1100000), Emu(1180000), height=Emu(3850000))

# ---------------- Slide 10: Snapshots of the running prototype ----------------
s = shapes_by_id(slides[9])
set_plain(s[120], " ", size=1)
slides[9].shapes.add_picture("docs/deck/screenshots/dashboard_top.png", Emu(463125), Emu(1180000), width=Emu(4000000))
slides[9].shapes.add_picture("docs/deck/screenshots/dashboard_trend.png", Emu(4600000), Emu(1180000), width=Emu(4000000))

# ---------------- Slide 8: Architecture diagram ----------------
s = shapes_by_id(slides[7])
set_plain(s[105], " ", size=1)
slides[7].shapes.add_picture("docs/deck/diagram_arch.png", Emu(600000), Emu(1180000), width=Emu(7944000))

# ---------------- Slide 9: Tech stack ----------------
s = shapes_by_id(slides[8])
force_font(s[111])
set_rich(s[112], [
    [("Google stack: ", B, _), ("Google ADK", B, _), (" (Agent Development Kit) for Sequential "
      "multi-agent orchestration; ", _, _), ("Gemini 2.5 Flash", B, _),
     (" for both agents' reasoning; a BigQuery-ready data pipeline; a containerized FastAPI app "
      "built for Cloud Run deployment.", _, _)],
    [("NVIDIA stack: ", B, _), ("NVIDIA RAPIDS cuDF", B, _),
     (" for the GPU-accelerated clean, aggregate, trend, anomaly pipeline; ", _, _),
     ("NVIDIA T4 GPU", B, _), (" (Google Colab) as the benchmark and production-scale processing target.", _, _)],
    [("Why this stack: ", B, _),
     ("millions of sensor rows need cuDF-class speed to stay decision-fresh; grounded, "
      "tool-calling ADK agents avoid hallucinated health claims that a single freeform prompt "
      "risks; a lightweight containerized FastAPI service scales horizontally and deploys "
      "anywhere (Cloud Run, Render, or on-prem) with no code changes.", _, _)],
], size=12.5, space_after=10)

prs.save(OUT)
print("Saved", OUT)
