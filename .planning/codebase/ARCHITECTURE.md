# Architecture

**Analysis Date:** 2026-04-02

## Pattern Overview

**Overall:** Monolithic client-server with background worker pattern

**Key Characteristics:**
- Flask REST API backend serving React frontend
- Daemon thread (Fusion Engine) for continuous data collection and processing
- Database-driven route configuration enables scalability to new bus routes
- Layered data pipeline: BODS (live GPS) → TomTom (traffic) → YOLOv8 (crowd) → ETA prediction → persistence
- Graceful fallback chain when optional integrations unavailable (TomTom → OSRM → Haversine)

## Layers

**Presentation (Client):**
- Purpose: Route selection dashboard, map visualization, real-time metrics
- Location: `client/src/`
- Contains: React components (App.jsx, HistoricalTrends.jsx), Leaflet map integration, Tailwind v4 styling
- Depends on: `/api` endpoints from Flask backend (10s polling)
- Used by: End users tracking Bristol bus routes

**API (Backend):**
- Purpose: REST endpoints for route data, live bus status, historical data, stop predictions
- Location: `server/app.py` (Flask routes starting at line 1450)
- Contains: Route data (`/api/routes`), status (`/api/status/<route_id>`), predictions (`/api/routes/<route_id>/predictions`), history (`/api/routes/<route_id>/history`), stops (`/api/routes/<route_id>/stops`)
- Depends on: Database models, Fusion Engine outputs, GTFS cache
- Used by: React frontend, verification scripts

**Data Fusion (Background Worker):**
- Purpose: Continuously fuse live GPS, traffic, crowd, and timetable data every 10 seconds
- Location: `server/app.py` (Fusion Engine function at line 1235)
- Contains: BODS vehicle fetching, TomTom traffic lookup, YOLO crowd detection, ETA calculation, persistence
- Depends on: BODS API, TomTom Routing API, YOLOv8 model, GTFS schedule, database
- Used by: Database (writes BusLog rows), API responses

**Models & Database:**
- Purpose: Store and query route configuration and historical bus logs
- Location: `server/models.py`
- Contains: `Route` (configuration), `BusLog` (history), `Stop` (GTFS), `RouteStop` (association)
- Depends on: SQLAlchemy, PostgreSQL
- Used by: All Flask endpoints, Fusion Engine

**Data Parsers & Integrations:**
- Purpose: Parse external data sources into normalized formats
- Location: `server/bods_parser.py` (SIRI-VM XML), `server/gtfs_parser.py` (GTFS zip files)
- Contains: XML parsing, CSV reading, GTFS trip selection, live/scheduled trip matching
- Depends on: Requests library, zipfile, CSV readers
- Used by: Fusion Engine, schedule builders

**ML & Routing:**
- Purpose: Predict ETA using trained XGBoost model, calculate distances with fallback chain
- Location: `server/app.py` (XGBoost functions at line 277, routing at line 530)
- Contains: ETA feature engineering, model loading, haversine fallback, OSRM routing, TomTom routing
- Depends on: joblib, requests, trained `xgboost_eta_model.joblib`
- Used by: Fusion Engine (every cycle), schedule delay calculation

**Video/Crowd Detection:**
- Purpose: Detect passenger count at major stops from video feed
- Location: `server/app.py` (crowd functions at line 760)
- Contains: YOLOv8 inference on `bus_queue.mp4`, crowd smoothing, major stop detection
- Depends on: OpenCV, ultralytics YOLO, haversine distance calculations
- Used by: Fusion Engine (only when near major stops)

## Data Flow

**Live Bus Update Cycle (Every 10 seconds):**

1. Fusion Engine wakes up (line 1244)
2. Fetch ALL routes from database (line 1246)
3. For each route:
   a. Fetch all BODS vehicles for that route (line 1256)
   b. Filter by operator allowlist (line 714)
   c. Filter by live timestamp and proximity (line 724-726)
   d. Filter by direction (line 734-748)
4. For each vehicle on the route:
   a. Get traffic delay from TomTom (line 1297)
   b. Check if near major stop; if yes, run YOLO (line 1300-1318)
   c. Get route distance and travel time from TomTom (line 1321-1326)
   d. Count remaining stops and current stop sequence (line 1329-1330)
   e. Get scheduled service time for ETA baseline (line 1334-1335)
   f. Predict ETA using XGBoost or formula fallback (line 1340-1368)
   g. Calculate schedule delay vs timetable (line 1370-1372)
   h. Write BusLog row to database (line 1375-1386)
5. Persist all logs in single transaction

**Client Request Flow:**

1. Frontend polls `/api/status/<route_id>` every 10s (line 187 App.jsx)
2. Backend finds most recent BusLog for route (line 1623-1627)
3. Returns latest bus position(s), ETA(s), stop predictions
4. Client renders map markers, updates dashboard cards

**Stop Prediction Flow:**

1. Client requests `/api/routes/<route_id>/predictions` (line 1496)
2. Backend loads latest BusLog for route (line 1507-1511)
3. If live data is stale or implausible, return schedule-only response (line 1514-1521)
4. Count remaining stops and current stop context (line 1524)
5. Resolve current ETA (live model or formula) (line 1525)
6. Calculate per-stop arrival times accounting for delays (line 1527-1529)
7. Return array of stops with scheduled, predicted, and delay times (line 1559)

**State Management:**

- Route configuration: Static in `Route` table, loaded once per Fusion Engine cycle
- Live bus position/ETA: Latest BusLog entry per route
- Historical data: All BusLog entries, queried with time window filter (default 6 hours)
- Crowd history: In-memory `_crowd_history` dict, averaged over 3 readings to smooth YOLO noise
- GTFS schedule: Cached in memory via `get_cached_gtfs_data()` (line 409)
- ETA model: Loaded once on startup, memoized in `_eta_model` global (line 277)

## Key Abstractions

**Route:**
- Purpose: Define a bus route (e.g., "Route 72 Outbound Temple Meads→Frenchay")
- Examples: `server/models.py` line 12, Flask query at `server/app.py` line 1246
- Pattern: SQLAlchemy model with `to_dict()` serializer; scalable by adding rows to DB

**BusLog:**
- Purpose: Time-series record of each Fusion Engine cycle per vehicle
- Examples: `server/models.py` line 57, written at `server/app.py` line 1375
- Pattern: Immutable insert-only log; queried by `route_id` + time window for history

**Vehicle Data:**
- Purpose: BODS-parsed vehicle dict with position, destination, operator, direction
- Examples: Returned from `fetch_bods_vehicles()` at `server/bods_parser.py` line 17
- Pattern: Validated through `is_vehicle_live_for_route()` and operator filtering

**Trip (GTFS):**
- Purpose: Represents a single scheduled service from origin to destination
- Examples: Dict from `select_live_route_trip()` at `server/gtfs_parser.py` line 19
- Pattern: Matched to live bus position using stop proximity and timetable constraints

**Stop:**
- Purpose: Physical bus stop with lat/lng from GTFS
- Examples: `server/models.py` line 96, used in predictions at `server/app.py` line 1217
- Pattern: Many-to-many with routes via `RouteStop` (sequence order)

## Entry Points

**Backend Web Server:**
- Location: `server/app.py` line 1732 (main block)
- Triggers: `python app.py`
- Responsibilities: Initialize Flask app, create database tables, load ETA model, start Fusion Engine thread, listen on port 5000

**Fusion Engine Background Thread:**
- Location: `server/app.py` line 1235 (function definition); started at line 1754
- Triggers: Spawned at app startup as daemon thread
- Responsibilities: Poll all routes every 10s, fetch BODS vehicles, compute ETA, write logs

**Frontend:**
- Location: `client/src/main.jsx` (entry point)
- Triggers: `npm run dev` (Vite dev server on :3000) or `npm run build` (static bundle)
- Responsibilities: Render route selector, fetch `/api` data, display map and dashboard

**Setup & Initialization:**
- Location: `server/setup_db.py`
- Triggers: `python setup_db.py` (before first run)
- Responsibilities: Create PostgreSQL database, initialize schema

## Error Handling

**Strategy:** Graceful degradation with fallback chains; log all errors but never crash Fusion Engine

**Patterns:**

- **TomTom API failures:** Disable service on auth error (401/403), log once, fall back to OSRM (line 666-678)
- **XGBoost model missing:** Use formula-based ETA instead (line 284-286, 319-322)
- **GTFS file missing:** Use DB-only stops if zip unavailable (line 405-407, 444-445)
- **BODS API key missing:** Return empty vehicle list, skip route (line 696-698)
- **YOLOv8 inference failure:** Caught in `count_passengers()`, return 0 crowd
- **Stale live data:** Detected by `is_recent_live_timestamp()`, route falls back to schedule-only (line 1514-1521)
- **Invalid vehicle position:** Filter by `is_vehicle_live_for_route()`, reject off-route vehicles (line 724-726)

## Cross-Cutting Concerns

**Logging:** 
- Framework: Python `logging` module
- Output: Console (via Flask dev server or systemd journal in production)
- Pattern: All major operations log with prefix tags: `[BODS]`, `[TomTom Routing]`, `[Fusion]`, `[Crowd]`, `[GTFS]`, `[XGBoost]`

**Validation:**
- Route proximity: Haversine distance vs `ROUTE_PROXIMITY_THRESHOLD_KM` (2.0 km default)
- Schedule plausibility: Bus position vs scheduled stop within `LIVE_TRIP_MAX_EARLY_MINUTES` (5) and `LIVE_TRIP_MAX_LATE_MINUTES` (25)
- Crowd detection: Only applied within `CROWD_DETECTION_RADIUS_KM` (0.3 km) of major stops
- ETA bounds: Clamped to non-negative minutes

**Authentication:**
- API: No auth required (public endpoints)
- External services: API keys in environment variables (`BODS_API_KEY`, `TOMTOM_API_KEY`, `TOMTOM_ROUTING_KEY`)
- Database: Connection string from `DATABASE_URL` env var or hardcoded default

---

*Architecture analysis: 2026-04-02*
