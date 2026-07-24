# Global wind + AQI map

## Problem

The wind + AQI map on `/dashboard` (`app/templates/summary.html`) is hardcoded to India: the wind grid (`app/wind.py`) queries a fixed India bounding box, the AQI heatmap/markers are built from VayuSense's own 20-city ranking data, and the only boundary overlay is an India states geojson. The map should work anywhere in the world, using real live data, not a fixed list of cities.

## Data sources

**Wind** (`app/wind.py`): Open-Meteo's forecast API is already global (`api.open-meteo.com/v1/forecast`, no key). The current implementation hardcodes India's bbox and a 22x17 grid tuned to stay under Open-Meteo's URL length limit. This becomes viewport-driven: the endpoint takes bbox params from the frontend and computes a grid resolution that fits the same URL-length budget for whatever bbox it's given (denser for a small/zoomed-in bbox, coarser for a large/zoomed-out one).

**AQI markers/heatmap**: new module `app/wind_aqi_stations.py` (or extend `app/live.py`) calls OpenAQ v3's real endpoints, verified directly against the live API:
- `GET /v3/locations?bbox=...` -- confirmed to genuinely filter by bounding box.
- `GET /v3/locations/{id}/latest` -- per-location latest sensor readings.
- Note: `GET /v3/parameters/{id}/latest` does **not** respect `bbox` (verified -- returns unfiltered global results regardless of the bbox param), so a single bulk call cannot replace the two-step fetch.

Flow: locations-in-bbox -> take up to ~40 nearest to bbox center that have a pm25 sensor -> fetch each location's latest reading with bounded concurrency (e.g. 8 at a time) -> build heatmap points + markers from real values only. TTL-cached (10-15 min) keyed by a rounded bbox, so minor pans reuse cached results instead of re-querying.

## Backend

- `app/wind.py`: `get_wind_grid(bbox)` takes a bbox instead of a hardcoded constant; grid density formula keeps total query URL under the existing safe threshold.
- New `/api/wind-grid?bbox=lo1,la1,lo2,la2` (bbox replaces the old no-arg call).
- New `/api/aqi-stations?bbox=lo1,la1,lo2,la2` returning `[{name, city, country, lat, lon, aqi, category, pollutant, value, unit, updated_at, is_supported_city, supported_city_slug}]`. `is_supported_city` true only when the station's city matches one of the 20 VayuSense-supported cities (case-insensitive), used by the frontend to decide the popup's link.
- Both endpoints follow the codebase's existing discipline: never raise, return a cached/empty/error-shaped response on failure, short-timeout httpx clients.

## Frontend (`app/templates/summary.html`)

- Map init: center stays India (`[22.5, 80]`), but `minZoom` drops (e.g. 2) and initial `zoom` drops (e.g. 3) so the whole world is reachable by scrolling out from the India-centered default.
- Boundaries: replace `india-states.geojson` with a world ADM0 (country) + ADM1 (state/province) geojson from geoBoundaries (same source already credited on this page), simplified/generalized for file size. Single static file, loaded once on map init, same as today's pattern.
- On `moveend`/`zoomend` (debounced ~500ms), refetch both `/api/wind-grid` and `/api/aqi-stations` for the current bounds; replace the wind velocity layer and the heat layer + markers. Keep the previous layer visible until the new one is ready (no flash-to-empty).
- Marker popup content:
  - Station/city name, country, live pollutant reading + AQI category, "as of {relative time}".
  - If `is_supported_city`: existing "Open full city page ->" link, unchanged.
  - Else: "Ask VayuSense about {city} ->" link that scrolls to/opens the Ask panel with a preset question about that city (chat itself is unchanged -- it may not have deep data on far-away cities, but the link is honest about what it does).
- New always-visible legend control (bottom-left or top-right corner, matching the existing Leaflet control style) showing the AQI color ramp (Good/Moderate/Poor/Unhealthy/Severe/Hazardous with their colors), so the heatmap is self-explanatory without hovering. Existing leaflet-velocity wind-speed control stays as-is.
- Existing scroll-to-zoom-with-modifier-key interaction, zoom controls, and popups/tooltips behavior are unchanged.

## Resilience

- Any Open-Meteo or OpenAQ failure: keep whatever layer was last successfully rendered, show the existing small inline note pattern (`$('windMapNote').textContent = ...`) instead of clearing the map or erroring.
- No fabricated/placeholder data anywhere -- if a bbox genuinely has zero OpenAQ stations, show zero markers and say so in the note, rather than inventing points.

## Out of scope

- No changes to the Ask VayuSense agent pipeline itself (only a UI link into it).
- No changes to the 20-city archive/ingestion pipeline or per-city detail pages.
- No user-facing search/filter UI beyond pan/zoom (matches the reference sites cited: pan/zoom is the primary interaction).

## Testing

- Unit tests for `app/wind.py`'s bbox-aware grid sizing (URL length stays under budget across a range of bbox sizes).
- Unit tests for the new AQI-stations endpoint: bbox parsing, the "supported city" match, graceful empty/error responses, mocked OpenAQ responses (no live network calls in the test suite, matching the existing `tests/test_live.py` pattern).
