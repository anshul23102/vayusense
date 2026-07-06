"""Generate the process-flow and architecture diagrams for the pitch deck."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.path import Path

NAVY = "#1E2761"
BLUE = "#3B6FE0"
VIOLET = "#7A5FD6"
GREEN = "#4C9A2A"
GREY = "#5B6478"
LIGHT = "#EEF2FB"
WHITE = "#FFFFFF"


def box(ax, x, y, w, h, text, fc, tc=WHITE, fs=13, weight="bold", sub=None, subfs=10.5):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                        linewidth=0, facecolor=fc, zorder=2)
    ax.add_patch(b)
    if sub:
        ax.text(x + w / 2, y + h * 0.62, text, ha="center", va="center", color=tc,
                fontsize=fs, fontweight=weight, family="DejaVu Sans", zorder=3)
        ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", color=tc,
                fontsize=subfs, family="DejaVu Sans", alpha=.92, zorder=3)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=tc,
                fontsize=fs, fontweight=weight, family="DejaVu Sans", zorder=3)


def arrow(ax, x1, y1, x2, y2, color=GREY, style="-|>", lw=2.2, connectionstyle="arc3,rad=0"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=16,
                         color=color, linewidth=lw, zorder=1, connectionstyle=connectionstyle)
    ax.add_patch(a)


# ============================================================
# DIAGRAM 1 — Process flow / use-case (horizontal)
# ============================================================
fig, ax = plt.subplots(figsize=(11.6, 4.6), dpi=200)
ax.set_xlim(0, 11.6); ax.set_ylim(0, 4.6); ax.axis("off")

box(ax, 0.3, 1.6, 2.1, 1.4, "Parent · School\nClinic · Official", GREY, fs=12.5, weight="bold")
box(ax, 2.9, 1.6, 2.1, 1.4, "Asks a real\ndecision", BLUE, fs=12.5,
    sub='"Is it safe for practice\noutdoors this week?"', subfs=9.5)
box(ax, 5.5, 2.5, 2.6, 1.1, "Data Analyst Agent", NAVY, sub="pulls GPU-processed facts", subfs=9.5)
box(ax, 5.5, 0.7, 2.6, 1.1, "Health Advisor Agent", VIOLET, sub="Gemini · WHO-aware verdict", subfs=9.5)
box(ax, 8.6, 1.6, 2.7, 1.4, "Decision-ready answer", GREEN,
    sub="Safety score · Human impact\n(cigarettes/day, life-yrs)", subfs=9)

arrow(ax, 2.4, 2.3, 2.9, 2.3)
arrow(ax, 5.0, 2.3, 5.6, 3.0, connectionstyle="arc3,rad=-.25")
arrow(ax, 8.1, 3.0, 8.6, 2.5, connectionstyle="arc3,rad=-.25")
arrow(ax, 8.1, 1.25, 8.6, 1.9, connectionstyle="arc3,rad=.25")
arrow(ax, 6.8, 2.5, 6.8, 1.8, color=NAVY, style="-|>")
ax.text(6.85, 2.05, "facts", fontsize=8.5, color=NAVY, style="italic")

ax.text(5.8, 4.25, "VayuSense: Sequential Multi-Agent Pipeline (Google ADK + Gemini)",
        fontsize=13.5, fontweight="bold", color=NAVY, ha="center")

plt.tight_layout(pad=0.3)
plt.savefig("docs/deck/diagram_flow.png", facecolor="white", bbox_inches="tight")
plt.close()

# ============================================================
# DIAGRAM 2 — Architecture (layered, vertical)
# ============================================================
fig, ax = plt.subplots(figsize=(11.6, 6.1), dpi=200)
ax.set_xlim(0, 11.6); ax.set_ylim(0, 6.1); ax.axis("off")

layers = [
    (4.95, "Data source", "OpenAQ global archive (AWS Open Data): 5.9M+ real sensor readings, 4 cities, 6 pollutants", GREY),
    (3.85, "Acceleration layer", "NVIDIA RAPIDS cuDF on T4 GPU: clean → aggregate → 7-day trend → anomaly detection  (37.5× faster than pandas: 9.34s → 0.25s)", GREEN),
    (2.75, "Intelligence layer", "Google ADK Sequential Agents + Gemini: Data Analyst → Health Advisor  (grounded, tool-using, no hallucinated stats)", NAVY),
    (1.65, "Application layer", "FastAPI dashboard on Cloud Run / Render: safety score, human-impact metrics, live trends, agent chat", BLUE),
    (0.55, "Users", "Parents · Schools · Clinics · City & ward officials: a straight, decision-ready answer, not a spreadsheet", VIOLET),
]
for y, title, sub, color in layers:
    box(ax, 0.6, y, 10.4, 0.95, title, color, sub=sub, fs=13, subfs=10, weight="bold")

for i in range(len(layers) - 1):
    y_top = layers[i][0]
    y_bot = layers[i + 1][0] + 0.95
    arrow(ax, 5.8, y_top, 5.8, y_bot, color=NAVY, lw=2.4)

ax.text(5.8, 5.98, "VayuSense: End-to-End Architecture", fontsize=15, fontweight="bold", color=NAVY, ha="center")

plt.tight_layout(pad=0.3)
plt.savefig("docs/deck/diagram_arch.png", facecolor="white", bbox_inches="tight")
plt.close()
print("Saved diagram_flow.png and diagram_arch.png")
