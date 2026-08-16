"""One-time discovery: map each VayuSense city to up to 5 active OpenAQ v3
locations, recording sensor->parameter/unit so the live fetcher can decode
/latest responses without extra API calls. Writes ingest/live_locations.json.

Uses one /v3/locations call per city (well inside OpenAQ's 60/min, 2000/hour
rate limit -- see docs.openaq.org/using-the-api/rate-limits) and picks the
5 most RECENTLY reporting stations by datetimeLast, rather than the first 5
in response order. The original version took the first 5 unconditionally,
which for some cities picked stations that had been offline for years (e.g.
Bengaluru's original 5 all last reported in February 2018) while dozens of
genuinely live stations sat lower in the same response, unused."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
KEY = os.environ["OPENAQ_API_KEY"]
HEADERS = {"X-API-Key": KEY}
API = "https://api.openaq.org/v3"
PARAMS = {"pm25", "pm10", "no2", "o3", "so2", "co"}
CITY_QUERIES = {
    "Delhi":     {"coordinates": "28.6139,77.2090", "radius": 25000},
    "Mumbai":    {"coordinates": "19.0760,72.8777", "radius": 25000},
    "Kolkata":   {"coordinates": "22.5726,88.3639", "radius": 25000},
    "Chennai":   {"coordinates": "13.0827,80.2707", "radius": 25000},
    "Bengaluru": {"coordinates": "12.9716,77.5946", "radius": 25000},
    "Hyderabad": {"coordinates": "17.3850,78.4867", "radius": 25000},
    "Pune":      {"coordinates": "18.5204,73.8567", "radius": 25000},
    "Ahmedabad": {"coordinates": "23.0225,72.5714", "radius": 25000},
    "Lucknow":   {"coordinates": "26.8467,80.9462", "radius": 25000},
    "Patna":     {"coordinates": "25.5941,85.1376", "radius": 25000},
    "Jaipur":       {"coordinates": "26.9124,75.7873", "radius": 25000},
    "Surat":        {"coordinates": "21.1702,72.8311", "radius": 25000},
    "Kanpur":       {"coordinates": "26.4499,80.3319", "radius": 25000},
    "Nagpur":       {"coordinates": "21.1458,79.0882", "radius": 25000},
    "Indore":       {"coordinates": "22.7196,75.8577", "radius": 25000},
    "Bhopal":       {"coordinates": "23.2599,77.4126", "radius": 25000},
    "Visakhapatnam": {"coordinates": "17.6868,83.2185", "radius": 25000},
    "Vadodara":     {"coordinates": "22.3072,73.1812", "radius": 25000},
    "Coimbatore":   {"coordinates": "11.0168,76.9558", "radius": 25000},
    "Nashik":       {"coordinates": "19.9975,73.7898", "radius": 25000},
}

# One call per city keeps this at 20 requests total -- nowhere near the
# 60/minute limit -- but a small courtesy delay avoids bursting them all
# in under a second, per OpenAQ's "don't hammer the API" guidance.
REQUEST_DELAY_SECONDS = 1.0


def main() -> None:
    out: dict[str, list[dict]] = {}
    for city, q in CITY_QUERIES.items():
        r = requests.get(f"{API}/locations",
                         params={**q, "limit": 100}, headers=HEADERS, timeout=30)
        r.raise_for_status()
        candidates = []
        for loc in r.json().get("results", []):
            sensors = {}
            for s in loc.get("sensors", []):
                pname = (s.get("parameter") or {}).get("name")
                punits = (s.get("parameter") or {}).get("units", "")
                if pname in PARAMS:
                    sensors[str(s["id"])] = {"parameter": pname, "unit": punits}
            if not sensors:
                continue
            last = ((loc.get("datetimeLast") or {}).get("utc")) or ""
            candidates.append((last, loc["id"], loc.get("name"), sensors))

        # Freshest first, so a location that stopped reporting years ago never
        # displaces one that's actually live, even if it appeared earlier in
        # OpenAQ's response order.
        candidates.sort(key=lambda c: c[0], reverse=True)
        picked = candidates[:5]
        out[city] = [{"location_id": loc_id, "sensors": sensors}
                     for _, loc_id, _, sensors in picked]

        newest = picked[0][0] if picked else "none"
        print(f"{city}: {len(picked)} locations "
              f"(of {len(candidates)} candidates, newest reading {newest})")
        time.sleep(REQUEST_DELAY_SECONDS)

    (ROOT / "ingest" / "live_locations.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
