"""Server-rendered, shareable PNG "report card" for one city's current air
quality -- used both as a directly downloadable/shareable image and as the
Open Graph preview image for city pages, so pasting a VayuSense city link
into WhatsApp/Twitter/Slack shows a real, live-data card instead of a bare
link. Pure drawing logic only: takes plain data in, returns PNG bytes out,
no knowledge of the web app's routing or data-access layers."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).resolve().parent / "static" / "fonts"
W, H = 1200, 630

# Same tokens as DESIGN.md / the dashboard's own RAMP.
NIGHT_BG = (0x13, 0x1b, 0x30)
NIGHT_BG_DEEP = (0x16, 0x21, 0x3a)
INK = (0xf3, 0xf6, 0xfd)
MIST = (0xa9, 0xb4, 0xd0)
HAIRLINE = (0xff, 0xff, 0xff, 0x1c)
RAMP = {
    "good": (0x3d, 0xfc, 0x9e), "moderate": (0xff, 0xc2, 0x47),
    "poor": (0xff, 0x96, 0x40), "unhealthy": (0xff, 0x5c, 0x85),
    "severe": (0xef, 0x4f, 0xc0), "hazardous": (0xc9, 0x3a, 0x5a),
}
BANDS = [(0, 50, "good"), (51, 100, "moderate"), (101, 150, "poor"),
         (151, 200, "unhealthy"), (201, 300, "severe"), (301, 500, "hazardous")]

# Oxblood is correct for fills/outlines (WCAG non-text 3:1 threshold: 3.45:1
# against the night bg) but fails AA as small text (needs 4.5:1) -- this
# lightened variant is used only where the color is drawn as readable text.
TEXT_SAFE = {**RAMP, "hazardous": (0xd2, 0x5c, 0x76)}


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    name = {"regular": "Onest-Regular.ttf", "semibold": "Onest-SemiBold.ttf",
            "bold": "Onest-Bold.ttf"}[weight]
    return ImageFont.truetype(str(FONTS / name), size)


def _vertical_gradient(w: int, h: int, top: tuple, bottom: tuple) -> Image.Image:
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        px = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        grad.putpixel((0, y), px)
    return grad.resize((w, h))


def render_card(*, city: str, aqi: int, category_key: str, category_label: str,
                 dominant: str, source: str, updated: str,
                 cigarettes_per_day: float, years_lost: float) -> bytes:
    color = RAMP.get(category_key, RAMP["moderate"])
    img = _vertical_gradient(W, H, NIGHT_BG, NIGHT_BG_DEEP).convert("RGBA")

    # Soft radial glow behind the headline number, tinted by AQI category.
    glow = Image.new("RGBA", (900, 900), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([0, 0, 900, 900], fill=(*color, 40))
    glow = glow.filter(__import__("PIL.ImageFilter", fromlist=["GaussianBlur"]).GaussianBlur(120))
    img.alpha_composite(glow, (-120, -260))

    d = ImageDraw.Draw(img)

    # Brand row.
    try:
        logo = Image.open(Path(__file__).resolve().parent / "static" / "logo-mark.png").convert("RGBA")
        logo = logo.resize((52, 52))
        img.alpha_composite(logo, (64, 52))
    except Exception:
        pass
    d.text((128, 58), "VayuSense", font=_font("bold", 32), fill=INK)
    d.text((128, 98), "Know when the air is safe", font=_font("regular", 16), fill=MIST)

    # City + date label.
    d.text((64, 168), f"{city.upper()} · {updated[:10]}", font=_font("semibold", 20),
            fill=MIST)

    # Headline AQI number.
    d.text((60, 195), str(aqi), font=_font("bold", 220), fill=INK)
    num_w = d.textlength(str(aqi), font=_font("bold", 220))
    d.text((70 + num_w, 300), "AQI\n(US EPA)", font=_font("semibold", 22), fill=MIST, spacing=4)

    # Category pill: drawn on its own transparent layer so the tinted fill
    # actually alpha-blends onto the background instead of overwriting it
    # opaquely (ImageDraw writes raw RGBA, it does not blend in place).
    pill_y = 460
    lf = _font("bold", 26)
    tw = d.textlength(category_label, font=lf)
    pill_w, pill_h = int(tw) + 76, 56
    pill_layer = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill_layer)
    text_color = TEXT_SAFE.get(category_key, color)
    pd.rounded_rectangle([0, 0, pill_w - 1, pill_h - 1], radius=28,
                          fill=(*color, 40), outline=(*color, 255), width=2)
    pd.ellipse([24, 25, 34, 35], fill=(*color, 255))
    pd.text((46, 14), category_label, font=lf, fill=(*text_color, 255))
    img.alpha_composite(pill_layer, (64, pill_y))

    # AQI ramp mini-bar with a pointer at the current value.
    bar_x, bar_y, bar_w, bar_h = 64, 540, 1072, 14
    total_span = 500
    x = bar_x
    for lo, hi, key in BANDS:
        seg_w = (hi - lo + (1 if hi == 500 else 0)) / total_span * bar_w
        d.rectangle([x, bar_y, x + seg_w, bar_y + bar_h], fill=RAMP[key])
        x += seg_w
    ptr_x = bar_x + min(aqi, 500) / total_span * bar_w
    d.polygon([(ptr_x - 8, bar_y - 12), (ptr_x + 8, bar_y - 12), (ptr_x, bar_y - 1)], fill=INK)

    # Human impact stats, right-aligned block.
    stat_x = 800
    d.line([(stat_x - 40, 200), (stat_x - 40, 430)], fill=(255, 255, 255, 40), width=2)
    d.text((stat_x, 210), f"{cigarettes_per_day}", font=_font("bold", 46), fill=INK)
    d.text((stat_x, 262), "cigarettes/day equivalent", font=_font("regular", 18), fill=MIST)
    d.text((stat_x, 320), f"{years_lost}", font=_font("bold", 46), fill=INK)
    d.text((stat_x, 372), "years life expectancy impact", font=_font("regular", 18), fill=MIST)
    d.text((stat_x, 420), f"Driven by {dominant.upper()}", font=_font("semibold", 16), fill=MIST)

    # Footer.
    d.line([(64, 578), (1136, 578)], fill=(255, 255, 255, 30), width=1)
    src_label = "LIVE" if source == "live" else "ARCHIVE"
    d.text((64, 592), f"{src_label} · OpenAQ archive, GPU-processed · vayusense.app",
            font=_font("regular", 16), fill=MIST)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
