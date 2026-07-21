"""US EPA AQI computation (pure functions, no I/O).

Breakpoints: EPA tables, PM2.5 per the May-2024 update. Archive-derived AQI is
computed from daily means, not EPA's 1h/8h windows — callers must label it
"EPA-method AQI from daily averages"."""
from __future__ import annotations

import math

# (concentration_low, concentration_high) per band, in EPA units:
# pm25/pm10 ug/m3, o3/so2/no2 ppb, co ppm.
BREAKPOINTS: dict[str, list[tuple[float, float]]] = {
    "pm25": [(0.0, 9.0), (9.1, 35.4), (35.5, 55.4), (55.5, 125.4), (125.5, 225.4), (225.5, 325.4)],
    "pm10": [(0, 54), (55, 154), (155, 254), (255, 354), (355, 424), (425, 604)],
    "o3":   [(0, 54), (55, 70), (71, 85), (86, 105), (106, 200), (201, 604)],
    "co":   [(0.0, 4.4), (4.5, 9.4), (9.5, 12.4), (12.5, 15.4), (15.5, 30.4), (30.5, 50.4)],
    "so2":  [(0, 35), (36, 75), (76, 185), (186, 304), (305, 604), (605, 1004)],
    "no2":  [(0, 53), (54, 100), (101, 360), (361, 649), (650, 1249), (1250, 2049)],
}
AQI_BANDS = [(0, 50), (51, 100), (101, 150), (151, 200), (201, 300), (301, 500)]
CATEGORIES = [
    {"key": "good", "label": "Good", "color": "#3dfc9e"},
    {"key": "moderate", "label": "Moderate", "color": "#ffc247"},
    {"key": "poor", "label": "Poor", "color": "#ff9640"},
    {"key": "unhealthy", "label": "Unhealthy", "color": "#ff5c85"},
    {"key": "severe", "label": "Severe", "color": "#ef4fc0"},
    {"key": "hazardous", "label": "Hazardous", "color": "#c93a5a"},
]
_MW = {"no2": 46.006, "so2": 64.066, "o3": 48.0, "co": 28.01}
# EPA truncation: decimals kept per parameter (in EPA units)
_TRUNC = {"pm25": 1, "pm10": 0, "o3": 0, "so2": 0, "no2": 0, "co": 1}
# How the processed archive stores each parameter
ARCHIVE_UNITS = {"pm25": "ugm3", "pm10": "ugm3", "no2": "ugm3",
                 "o3": "ugm3", "so2": "ugm3", "co": "mgm3"}

_UNIT_ALIASES = {"µg/m³": "ugm3", "ug/m3": "ugm3", "mg/m³": "mgm3", "mg/m3": "mgm3",
                 "ppb": "ppb", "ppm": "ppm", "ugm3": "ugm3", "mgm3": "mgm3"}


def to_epa_unit(parameter: str, value: float, unit: str = "ugm3") -> float | None:
    """Convert a concentration to the EPA unit for its parameter (25 C, 1 atm)."""
    unit = _UNIT_ALIASES.get(unit)
    if unit is None or parameter not in BREAKPOINTS:
        return None
    if parameter in ("pm25", "pm10"):
        return float(value)  # ug/m3 across all our sources
    if unit == "ppb":
        ppb = float(value)
    elif unit == "ppm":
        ppb = float(value) * 1000.0
    elif unit == "ugm3":
        ppb = float(value) * 24.45 / _MW[parameter]
    else:  # mgm3
        ppb = float(value) * 1000.0 * 24.45 / _MW[parameter]
    return ppb / 1000.0 if parameter == "co" else ppb


def _truncate(parameter: str, value: float) -> float:
    q = 10 ** _TRUNC[parameter]
    return math.floor(value * q) / q


def pollutant_aqi(parameter: str, value: float, unit: str = "ugm3") -> int | None:
    if value is None or value < 0:
        return None
    conc = to_epa_unit(parameter, value, unit)
    if conc is None:
        return None
    conc = _truncate(parameter, conc)
    table = BREAKPOINTS[parameter]
    for (c_lo, c_hi), (i_lo, i_hi) in zip(table, AQI_BANDS):
        if c_lo <= conc <= c_hi:
            return round((i_hi - i_lo) / (c_hi - c_lo) * (conc - c_lo) + i_lo)
    return 500  # above the top breakpoint


def overall_aqi(concs: dict[str, float], units: dict[str, str]) -> tuple[int, str, dict[str, int]]:
    subs: dict[str, int] = {}
    for p, v in concs.items():
        a = pollutant_aqi(p, v, units.get(p, "ugm3"))
        if a is not None:
            subs[p] = a
    if not subs:
        raise ValueError("no computable pollutants")
    dominant = max(subs, key=subs.get)
    return subs[dominant], dominant, subs


def category(aqi: int) -> dict:
    for (lo, hi), cat in zip(AQI_BANDS, CATEGORIES):
        if lo <= aqi <= hi:
            return dict(cat)
    return dict(CATEGORIES[-1])
