"""One-time discovery: map each VayuSense city to up to 5 active OpenAQ v3
locations, recording sensor->parameter/unit so the live fetcher can decode
/latest responses without extra API calls. Writes ingest/live_locations.json."""
from __future__ import annotations

import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
KEY = open("/tmp/openaq_key.txt").read().strip()
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
}


def main() -> None:
    out: dict[str, list[dict]] = {}
    for city, q in CITY_QUERIES.items():
        r = requests.get(f"{API}/locations",
                         params={**q, "limit": 100}, headers=HEADERS, timeout=30)
        r.raise_for_status()
        locs = []
        for loc in r.json().get("results", []):
            sensors = {}
            for s in loc.get("sensors", []):
                pname = (s.get("parameter") or {}).get("name")
                punits = (s.get("parameter") or {}).get("units", "")
                if pname in PARAMS:
                    sensors[str(s["id"])] = {"parameter": pname, "unit": punits}
            if sensors:
                locs.append({"location_id": loc["id"], "sensors": sensors})
            if len(locs) >= 5:
                break
        out[city] = locs
        print(f"{city}: {len(locs)} locations, "
              f"{sum(len(l['sensors']) for l in locs)} sensors")
    (ROOT / "ingest" / "live_locations.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
