# Coding Conventions

**Analysis Date:** 2026-04-02

## Naming Patterns

**Files:**
- Backend: `snake_case.py` (e.g., `bods_parser.py`, `gtfs_parser.py`, `env_utils.py`)
- Frontend: `PascalCase.jsx` for components (e.g., `App.jsx`, `HistoricalTrends.jsx`), `lowercase.js` for utilities
- Test files: `test_*.py` for Python (e.g., `test_api.py`, `test_status.py`, `test_route2.py`)

**Functions:**
- Python: `snake_case` for all functions (e.g., `parse_gtfs_time()`, `fetch_bods_vehicles()`, `is_vehicle_live_for_route()`)
- JavaScript: `camelCase` for functions and `useCallbacks`, `PascalCase` for React components
- Exception: Helper functions prefixed with underscore if internal only (e.g., `_strip_optional_quotes()`)

**Variables:**
- Python: `snake_case` constants in UPPERCASE at module level (e.g., `MAJOR_STOPS_OUTBOUND`, `FUSION_INTERVAL`, `MAX_CROWD_HISTORY`)
- JavaScript: `camelCase` for state and regular variables (e.g., `selectedRouteId`, `activeBus`, `routePredictions`); `UPPER_CASE` for module constants (e.g., `API_BASE = "/api"`, `POLL_INTERVAL = 10_000`)

**Types/Classes:**
- Python: `PascalCase` for classes (e.g., `Route`, `BusLog`, `Stop`, `RouteStop`)
- JavaScript: Generic object shape patterns use `camelCase` keys (see Data Flow section)

## Code Style

**Formatting:**
- No auto-formatter in use; code written by hand following conventions below
- Indentation: Python (4 spaces), JavaScript (2 spaces)
- Line length: Implicit soft limit around 100 characters, no hard enforcer

**Linting:**
- Frontend: ESLint with config in `client/eslint.config.js`
  - Rules: `@eslint/js` recommended + `react-hooks` + `react-refresh`
  - Exception: Unused variables with UPPERCASE names ignored (`varsIgnorePattern: '^[A-Z_]'`)
  - Run: `npm run lint` from `client/`
- Backend: No linter configured; code review relies on type hints and manual inspection

**Type Hints:**
- Python: Type hints present in some functions (e.g., `def get_database_admin_config() -> dict[str, object]:`), gradually applied to new/edited signatures
- JavaScript: No TypeScript; React components use JSDoc blocks for clarity (see Comments section)

## Import Organization

**Python order:**
1. Standard library (`import os`, `from datetime import`, `from zoneinfo import`)
2. Third-party packages (`import requests`, `from flask import`)
3. Local modules (`from env_utils import`, `from models import`)

Example from `server/app.py`:
```python
import os
import time
import math
import threading
import logging
import atexit
import signal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import cv2
import joblib
from ultralytics import YOLO
from flask import Flask, jsonify, request
from flask_cors import CORS

from env_utils import DEFAULT_DATABASE_URL, load_project_env_files, resolve_project_path
from models import db, Route, BusLog
from bods_parser import fetch_bods_vehicles
```

**JavaScript order:**
1. React/library imports
2. Local component imports
3. Asset imports (CSS, images)

Example from `client/src/App.jsx`:
```javascript
import { useState, useEffect, useCallback } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import HistoricalTrends from "./HistoricalTrends.jsx";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
```

**Path aliases:**
- None configured; all imports are relative or absolute module names

## Error Handling

**Python patterns:**
- Try-except blocks around API calls and file I/O
- Errors logged via `logger.error()` before returning graceful fallbacks
- HTTP errors caught as `requests.exceptions.HTTPError` then `Exception` (broad catch)
- Database errors rolled back with `db.session.rollback()` in Fusion Engine catch block

Example from `server/app.py`:
```python
try:
    # API call
    resp = requests.post(url, params=params)
    resp.raise_for_status()
    # ... process response
except requests.exceptions.HTTPError as exc:
    logger.error(f"[TomTom Routing] Error: {exc}")
    # Return None or fallback value
except Exception as exc:
    logger.error(f"[TomTom Routing] Error: {exc}")
```

**JavaScript patterns:**
- `.catch()` handlers on all fetch calls
- Error state stored in state variable (e.g., `const [error, setError] = useState(null)`)
- Failed requests silently set empty data with `.catch(() => { setStops([]) })`
- No error boundary component; errors logged to error state UI display

Example from `client/src/App.jsx`:
```javascript
fetch(`${API_BASE}/status/${selectedRouteId}?_t=${Date.now()}`)
  .then((r) => {
    if (!r.ok) throw new Error("No data yet");
    return r.json();
  })
  .then((data) => {
    // ... process data
    setError(null);
  })
  .catch((e) => {
    setBuses([]);
    setError(e.message);
  });
```

**Fallback patterns:**
- Live APIs have graceful no-data fallbacks (e.g., no BODS key → empty buses, no TomTom → haversine distance fallback)
- File loads use `os.path.exists()` checks before loading (e.g., YOLOv8 model, ETA model)
- Missing environment variables fall back to hardcoded defaults (e.g., `BODS_OPERATOR_ALLOWLIST` defaults to `("FBRI", "FBRA")`)

## Logging

**Framework:** Python `logging` module; JavaScript console (via `console.log` in JSDoc examples, not in production code)

**Python patterns:**
- Logger initialized as: `logger = logging.getLogger("transight")`
- Log levels used: `info()` for flow steps, `warning()` for non-fatal issues, `error()` for failures
- Messages prefixed with component tag in brackets (e.g., `[BODS]`, `[TomTom]`, `[Fusion]`, `[GTFS]`, `[XGBoost]`, `[Crowd]`)
- Detailed context logged: vehicle IDs, coordinates, metric values, service times

Example from `server/app.py`:
```python
logger.info(f"[Fusion] Bus {vehicle_id}: ETA={eta}min | {delay_str}")
logger.warning(
    f"[GTFS] Rejecting implausible live bus for route {route.route_name} "
    f"({route.direction}) at stop seq {current_stop_seq}: "
    f"schedule delta {delta_minutes:.1f} min"
)
logger.error(f"[Fusion] Engine error: {exc}")
```

**JavaScript patterns:**
- No logging in production code; React state drives visibility
- Error messages stored in `error` state and displayed conditionally
- Historical trends component calculates and formats values without logging intermediate steps

## Comments

**When to comment:**
- Complex algorithms: ETA calculation with multiple factors, haversine distance, stop sequence matching
- Non-obvious business logic: GTFS timetable matching, vehicle operator resolution
- Data transformation: SIRI-VM XML parsing, coordinate munging
- External API contracts: TomTom routing params, BODS polling intervals
- Avoid: Commenting obvious code (e.g., `x = 1  # Set x to 1`)

**JSDoc/TSDoc:**
- Python docstrings present on modules and public classes (e.g., `class Route(db.Model): """Stores the configuration..."""`)
- Function docstrings for complex helpers (e.g., `def is_vehicle_live_for_route(): """Filter out stale or off-route BODS vehicles."""`)
- JavaScript uses leading comment blocks for component descriptions

Example from `server/app.py`:
```python
def route_distance_km(route_path, lat, lng):
    """Return the minimum distance from a bus position to the stored route path."""
    if not route_path:
        return float("inf")
    ...
```

Example from `client/src/App.jsx`:
```javascript
/* ── Fix Leaflet's default icon paths (Vite bundling workaround) ────── */
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
```

## Function Design

**Size:**
- Python: Most functions 20-60 lines; helpers cluster around 10-20 lines
- JavaScript: React components often 300-400 lines (includes JSX render); hooks extracted separately

**Parameters:**
- Python: Functions accept 4-8 parameters; many use optional keyword arguments for config
- JavaScript: Components receive props object; callbacks accept single event or data parameter

**Return values:**
- Python: Explicit None for fallbacks, tuples for multi-return values (e.g., `(remaining_stops, stop_delay_min, current_stop_seq)`)
- JavaScript: State setters return void; fetch handlers return nothing, mutations via setState
- API routes: Always return `jsonify()` with dict structure (never raw JSON strings)

Example from `server/app.py`:
```python
def count_remaining_stops(route_id, current_lat, current_lng):
    """Return (remaining_stops, stop_delay_min, current_stop_seq)."""
    # ... logic
    return remaining_stops, stop_delay_min, current_stop_seq
```

Example from `client/src/App.jsx`:
```javascript
const fetchStatus = useCallback(() => {
    if (!selectedRouteId) return;
    fetch(`${API_BASE}/status/${selectedRouteId}?_t=${Date.now()}`)
      .then((r) => {
        if (!r.ok) throw new Error("No data yet");
        return r.json();
      })
      .then((data) => {
        setBuses(nextBuses);
        setError(null);
      })
      .catch((e) => {
        setBuses([]);
        setError(e.message);
      });
  }, [selectedRouteId]);
```

## Module Design

**Python exports:**
- Classes always exported: `Route`, `BusLog`, `Stop`, `RouteStop`, `db` (from `models.py`)
- Helper functions exported: `parse_gtfs_time()`, `format_gtfs_time()`, `fetch_bods_vehicles()` (public API for tests/reuse)
- Private functions prefixed with underscore if intended for internal use only

**JavaScript exports:**
- Default export: Main component (`export default function App()`, `export default function HistoricalTrends()`)
- Utility functions at module level used internally only (not exported)
- Constants defined at top: `METRICS`, `API_BASE`, `POLL_INTERVAL`

**Barrel files:**
- Not used; imports are direct (e.g., `from models import Route, BusLog`)

## Flask API Response Format

All Flask routes return `jsonify()` with consistent structures:

**Success responses:**
```python
return jsonify({
    "key": "value",
    "nested": { "data": "here" }
})
```

**Error responses:**
```python
return jsonify({"error": "Description"}), 404
```

**Example from `server/app.py`:**
```python
@app.route("/api/status/<int:route_id>", methods=["GET"])
def get_status(route_id):
    # ... logic
    return jsonify({
        "bus_available": bool,
        "bus_count": int,
        "buses": [...],
        "route": {...}
    })
```

## Tailwind CSS v4 Conventions

- No `tailwind.config.js`; all config in `client/src/index.css` using `@theme` and `@layer` directives
- Custom properties for theme colors: `--color-bg-primary`, `--color-text-primary`, `--color-accent`, etc.
- Light/dark mode controlled via `[data-theme="light"]` and `[data-theme="dark"]` selectors
- Component styling via utility classes inline in JSX or CSS modules (none used currently)

Example from `client/src/index.css`:
```css
@theme {
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --color-bg-primary: #0b0f19;
  --color-accent: #3b82f6;
}

[data-theme="light"] {
  --color-bg-primary: #f8fafc;
  --color-text-primary: #1e293b;
}
```

---

*Convention analysis: 2026-04-02*
