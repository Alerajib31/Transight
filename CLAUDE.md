# CLAUDE.md

Project memory for Claude Code in this repository.

## Project Snapshot

Transight AI is a Phase 2 MVP for Bristol bus prediction across Route 72 and the A1 Airport Flyer. The live app is:

- `client/`: React 19 + Vite 7 + Tailwind v4 + Leaflet
- `server/`: Flask API + Fusion Engine background thread + SQLAlchemy
- PostgreSQL for route, stop, and bus-log data
- Live inputs from BODS, TomTom, and YOLOv8, with optional GTFS timetable enrichment
- Route-specific XGBoost ETA models for `72` and `A1`, with formula fallback retained for resilience

The current shippable architecture is the existing Flask + React + PostgreSQL stack. Larger platform changes are deferred.

## Start Here

Backend:

```bash
cd server
pip install -r requirements.txt
python setup_db.py
python app.py
```

Frontend:

```bash
cd client
npm install
npm run dev
```

Optional data/model steps:

```bash
cd server
python gtfs_loader.py ../itm_south_west_gtfs.zip
python generate_synthetic_data.py --route 72
python train_xgboost.py --route 72
python train_xgboost.py --route A1
```

## High-Signal Files

- `server/app.py`: Flask entry point, Fusion Engine, ETA helpers, API routes
- `server/models.py`: `Route`, `BusLog`, `Stop`, `RouteStop`
- `server/bods_parser.py`: live bus parsing and vehicle matching
- `server/gtfs_parser.py`: schedule helpers used by the live pipeline
- `server/seed.py`: destructive reset and reseed script
- `client/src/App.jsx`: route selector, polling, Leaflet map, dashboard cards
- `client/src/index.css`: Tailwind v4 theme tokens and custom styling

## Working Rules

- Prefer the smallest targeted change and verify it before moving on.
- Do not run `python seed.py` or `python server/seed.py` unless the user explicitly approves a destructive reset.
- `server/app.py` auto-loads the repo-root `.env`; shell variables still override it when needed.
- Keep graceful fallbacks intact when API keys or live feeds are unavailable.
- Preserve Tailwind v4 patterns in the frontend; there is no `tailwind.config.js`.
- Use the repo-specific rules in `.claude/rules/` for file-targeted constraints.

## Verification Expectations

- Frontend change: `cd client && npm run build` and `npm run lint`
- Backend/API change: run the smallest relevant `python test_*.py` script or a targeted Flask/client smoke test
- Data-pipeline change: verify both the live-data path and the fallback/no-key path
- Route or ETA changes: confirm `/api/status/<route_id>` and `/api/routes/<route_id>/predictions` still behave sensibly

## Useful Claude Commands

- `/seed-check`: inspect DB state without reseeding
- `/route-audit`: inspect a route end-to-end from config to status endpoint
- `/fusion-debug`: investigate a Fusion Engine, ETA, or live-data issue
- `/ship-readiness`: review diffs and run the right verification steps before shipping

## Useful Claude Agents

- `transight-backend-agent`: Flask, BODS, GTFS, ETA, and database work
- `transight-frontend-agent`: React, Tailwind, and Leaflet work
- `transight-verifier-agent`: targeted verification and ship checks

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Transight AI**

A real-time Bristol bus prediction platform that shows live bus positions, arrival times, and delay status for Bristol bus routes. It currently tracks Route 72 and the A1 Airport Flyer in both directions.

**Core Value:** Accurate, real-time bus arrival predictions with delay indicators at every stop — proving the system scales beyond a single route.

### Constraints

- **Tech stack**: Flask + React + PostgreSQL — no framework changes
- **Data sources**: BODS, TomTom, GTFS — shared across Route 72 and A1
- **Tailwind**: v4 with `index.css` theme tokens — no `tailwind.config.js`
- **Seed safety**: `seed.py` drops all tables — never run without explicit approval
- **API keys**: Graceful fallback when BODS/TomTom keys unavailable
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.x - Backend API, Fusion Engine, data pipelines, machine learning
- JavaScript (ES6+) - React frontend with JSX
- SQL - PostgreSQL database queries
## Runtime
- Node.js (version not pinned) - JavaScript runtime for frontend tooling
- Python 3.x - Flask server and background processes
- npm - JavaScript dependencies (frontend)
- pip - Python dependencies (backend)
- Lockfile: `client/package-lock.json` (present), `server/requirements.txt` (pinned)
## Frameworks
- Flask 3.0.0 - Web framework for REST API and server initialization at `server/app.py`
- React 19.2.0 - Frontend UI framework with hooks
- SQLAlchemy 2.0.23 - ORM for database models at `server/models.py`
- Vite 7.3.1 - Build tool and dev server configured at `client/vite.config.js`
- Tailwind CSS 4.1.18 - Utility-first CSS framework via `@tailwindcss/vite` plugin
- Leaflet 1.9.4 - Interactive map library
- react-leaflet 5.0.0 - React bindings for Leaflet
- @vitejs/plugin-react 5.1.1 - React Fast Refresh for HMR
- ESLint 9.39.1 - Code linting
- @eslint/js 9.39.1 - Core ESLint rules
- eslint-plugin-react-hooks 7.0.1 - React hooks lint rules
- eslint-plugin-react-refresh 0.4.24 - Fast Refresh rules
## Key Dependencies
- Flask-SQLAlchemy 3.1.1 - Database ORM integration
- psycopg2-binary 2.9.9 - PostgreSQL adapter for Python
- Flask-CORS 4.0.0 - CORS support for cross-origin API requests
- requests 2.31.0 - HTTP client for external API calls (BODS, TomTom, OSRM)
- ultralytics 8.1.0 - YOLOv8 object detection for passenger counting from video
- opencv-python-headless 4.9.0.80 - Computer vision (video frame processing)
- xgboost 3.1.3 - Gradient boosting for ETA prediction model
- scikit-learn 1.8.0 - Machine learning utilities
- joblib - Model serialization for route-specific ETA model artifacts
- globals 16.5.0 - Global variable definitions for ESLint
- @types/react 19.2.7 - TypeScript type definitions for React
- @types/react-dom 19.2.3 - TypeScript type definitions for ReactDOM
## Configuration
- Configuration via `.env` file loaded at startup by `server/env_utils.py`
- Variables can be sourced manually in shell before running `python app.py`
- .env.example provided at project root showing required keys
- `DATABASE_URL` - PostgreSQL connection string (default: `postgresql://postgres:R%40jibale3138@localhost:5432/transight_db`)
- `BODS_API_KEY` - Bus Open Data Service API key for live vehicle data
- `TOMTOM_API_KEY` - TomTom Traffic Flow API key for congestion data
- `TOMTOM_ROUTING_KEY` - TomTom Routing API key for accurate distance/time calculations
- `VIDEO_PATH` - Path to bus queue video file for YOLOv8 passenger detection (default: `bus_queue.mp4`)
- `FUSION_INTERVAL` - Fusion Engine cycle frequency in seconds (default: 10)
- `LIVE_DATA_MAX_AGE_SECONDS` - Maximum age of live data before fallback (default: 180)
- `ROUTE_PROXIMITY_THRESHOLD_KM` - Vehicle-to-route matching distance (default: 2.0)
- `BODS_OPERATOR_ALLOWLIST` - Comma-separated operator codes to monitor (default: FBRI,FBRA)
- `client/vite.config.js` - Vite dev server on port 3000 with `/api` proxy to `http://localhost:5000`
- `client/eslint.config.js` - ESLint flat config with React, React Hooks, and React Refresh rules
- `client/src/index.css` - Tailwind v4 theme tokens and custom styling
## Database
- Version: Specified via `DATABASE_URL` connection string
- Host: localhost (development), 5432 (default port)
- Database: `transight_db`
- Client: psycopg2-binary 2.9.9
- Setup: `server/setup_db.py` creates database if missing
- `routes` table - Route configuration and metadata (`server/models.py::Route`)
- `bus_logs` table - Historical fusion engine cycle records (`server/models.py::BusLog`)
- `stops` table - GTFS stop data (`server/models.py::Stop`)
- `route_stops` table - Stop sequence on each route (`server/models.py::RouteStop`)
## Data Files
- Location: `../itm_south_west_gtfs.zip` (relative to `server/`)
- Purpose: Schedule data for Bristol bus routes
- Loaded via: `server/gtfs_loader.py`
- Parsed by: `server/gtfs_parser.py`
- YOLOv8 nano: `server/yolov8n.pt` - Person detection for passenger counting
- XGBoost:
  - `server/xgboost_eta_model_72.joblib`
  - `server/xgboost_eta_model_a1.joblib`
  - `server/xgboost_eta_metrics_72.json`
  - `server/xgboost_eta_metrics_a1.json`
  - `server/xgboost_eta_model.joblib` and `server/xgboost_eta_metrics.json` remain as the legacy Route 72 compatibility artifacts
- Simulated camera feed: `bus_queue.mp4` (configurable via `VIDEO_PATH`)
- Processed by YOLOv8 for passenger detection every Fusion Engine cycle
## API Endpoints
- Dev: Vite proxy at `/api` → `http://localhost:5000` (configured in `client/vite.config.js`)
- Production: Backend Flask app serves API at base URL
- Endpoints defined in `server/app.py`:
## Platform Requirements
- Python 3.x with pip
- Node.js with npm
- PostgreSQL 12+
- ffmpeg (for video processing with OpenCV)
- GPU optional (for faster YOLOv8 inference)
- Flask server running on port 5000 (configurable)
- PostgreSQL database accessible
- Machine learning models loaded in memory
- Video file for YOLO processing (can be disabled)
- External API keys for BODS and TomTom
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Backend: `snake_case.py` (e.g., `bods_parser.py`, `gtfs_parser.py`, `env_utils.py`)
- Frontend: `PascalCase.jsx` for components (e.g., `App.jsx`, `HistoricalTrends.jsx`), `lowercase.js` for utilities
- Test files: `test_*.py` for Python (e.g., `test_api.py`, `test_status.py`, `test_route2.py`)
- Python: `snake_case` for all functions (e.g., `parse_gtfs_time()`, `fetch_bods_vehicles()`, `is_vehicle_live_for_route()`)
- JavaScript: `camelCase` for functions and `useCallbacks`, `PascalCase` for React components
- Exception: Helper functions prefixed with underscore if internal only (e.g., `_strip_optional_quotes()`)
- Python: `snake_case` constants in UPPERCASE at module level (e.g., `MAJOR_STOPS_OUTBOUND`, `FUSION_INTERVAL`, `MAX_CROWD_HISTORY`)
- JavaScript: `camelCase` for state and regular variables (e.g., `selectedRouteId`, `activeBus`, `routePredictions`); `UPPER_CASE` for module constants (e.g., `API_BASE = "/api"`, `POLL_INTERVAL = 10_000`)
- Python: `PascalCase` for classes (e.g., `Route`, `BusLog`, `Stop`, `RouteStop`)
- JavaScript: Generic object shape patterns use `camelCase` keys (see Data Flow section)
## Code Style
- No auto-formatter in use; code written by hand following conventions below
- Indentation: Python (4 spaces), JavaScript (2 spaces)
- Line length: Implicit soft limit around 100 characters, no hard enforcer
- Frontend: ESLint with config in `client/eslint.config.js`
- Backend: No linter configured; code review relies on type hints and manual inspection
- Python: Type hints present in some functions (e.g., `def get_database_admin_config() -> dict[str, object]:`), gradually applied to new/edited signatures
- JavaScript: No TypeScript; React components use JSDoc blocks for clarity (see Comments section)
## Import Organization
- None configured; all imports are relative or absolute module names
## Error Handling
- Try-except blocks around API calls and file I/O
- Errors logged via `logger.error()` before returning graceful fallbacks
- HTTP errors caught as `requests.exceptions.HTTPError` then `Exception` (broad catch)
- Database errors rolled back with `db.session.rollback()` in Fusion Engine catch block
- `.catch()` handlers on all fetch calls
- Error state stored in state variable (e.g., `const [error, setError] = useState(null)`)
- Failed requests silently set empty data with `.catch(() => { setStops([]) })`
- No error boundary component; errors logged to error state UI display
- Live APIs have graceful no-data fallbacks (e.g., no BODS key → empty buses, no TomTom → haversine distance fallback)
- File loads use `os.path.exists()` checks before loading (e.g., YOLOv8 model, ETA model)
- Missing environment variables fall back to hardcoded defaults (e.g., `BODS_OPERATOR_ALLOWLIST` defaults to `("FBRI", "FBRA")`)
## Logging
- Logger initialized as: `logger = logging.getLogger("transight")`
- Log levels used: `info()` for flow steps, `warning()` for non-fatal issues, `error()` for failures
- Messages prefixed with component tag in brackets (e.g., `[BODS]`, `[TomTom]`, `[Fusion]`, `[GTFS]`, `[XGBoost]`, `[Crowd]`)
- Detailed context logged: vehicle IDs, coordinates, metric values, service times
- No logging in production code; React state drives visibility
- Error messages stored in `error` state and displayed conditionally
- Historical trends component calculates and formats values without logging intermediate steps
## Comments
- Complex algorithms: ETA calculation with multiple factors, haversine distance, stop sequence matching
- Non-obvious business logic: GTFS timetable matching, vehicle operator resolution
- Data transformation: SIRI-VM XML parsing, coordinate munging
- External API contracts: TomTom routing params, BODS polling intervals
- Avoid: Commenting obvious code (e.g., `x = 1  # Set x to 1`)
- Python docstrings present on modules and public classes (e.g., `class Route(db.Model): """Stores the configuration..."""`)
- Function docstrings for complex helpers (e.g., `def is_vehicle_live_for_route(): """Filter out stale or off-route BODS vehicles."""`)
- JavaScript uses leading comment blocks for component descriptions
## Function Design
- Python: Most functions 20-60 lines; helpers cluster around 10-20 lines
- JavaScript: React components often 300-400 lines (includes JSX render); hooks extracted separately
- Python: Functions accept 4-8 parameters; many use optional keyword arguments for config
- JavaScript: Components receive props object; callbacks accept single event or data parameter
- Python: Explicit None for fallbacks, tuples for multi-return values (e.g., `(remaining_stops, stop_delay_min, current_stop_seq)`)
- JavaScript: State setters return void; fetch handlers return nothing, mutations via setState
- API routes: Always return `jsonify()` with dict structure (never raw JSON strings)
## Module Design
- Classes always exported: `Route`, `BusLog`, `Stop`, `RouteStop`, `db` (from `models.py`)
- Helper functions exported: `parse_gtfs_time()`, `format_gtfs_time()`, `fetch_bods_vehicles()` (public API for tests/reuse)
- Private functions prefixed with underscore if intended for internal use only
- Default export: Main component (`export default function App()`, `export default function HistoricalTrends()`)
- Utility functions at module level used internally only (not exported)
- Constants defined at top: `METRICS`, `API_BASE`, `POLL_INTERVAL`
- Not used; imports are direct (e.g., `from models import Route, BusLog`)
## Flask API Response Format
## Tailwind CSS v4 Conventions
- No `tailwind.config.js`; all config in `client/src/index.css` using `@theme` and `@layer` directives
- Custom properties for theme colors: `--color-bg-primary`, `--color-text-primary`, `--color-accent`, etc.
- Light/dark mode controlled via `[data-theme="light"]` and `[data-theme="dark"]` selectors
- Component styling via utility classes inline in JSX or CSS modules (none used currently)
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Flask REST API backend serving React frontend
- Daemon thread (Fusion Engine) for continuous data collection and processing
- Database-driven route configuration enables scalability to new bus routes
- Layered data pipeline: BODS (live GPS) → TomTom (traffic) → YOLOv8 (crowd) → ETA prediction → persistence
- Graceful fallback chain when optional integrations unavailable (TomTom → OSRM → Haversine)
## Layers
- Purpose: Route selection dashboard, map visualization, real-time metrics
- Location: `client/src/`
- Contains: React components (App.jsx, HistoricalTrends.jsx), Leaflet map integration, Tailwind v4 styling
- Depends on: `/api` endpoints from Flask backend (10s polling)
- Used by: End users tracking Bristol bus routes
- Purpose: REST endpoints for route data, live bus status, historical data, stop predictions
- Location: `server/app.py` (Flask routes starting at line 1450)
- Contains: Route data (`/api/routes`), status (`/api/status/<route_id>`), predictions (`/api/routes/<route_id>/predictions`), history (`/api/routes/<route_id>/history`), stops (`/api/routes/<route_id>/stops`)
- Depends on: Database models, Fusion Engine outputs, GTFS cache
- Used by: React frontend, verification scripts
- Purpose: Continuously fuse live GPS, traffic, crowd, and timetable data every 10 seconds
- Location: `server/app.py` (Fusion Engine function at line 1235)
- Contains: BODS vehicle fetching, TomTom traffic lookup, YOLO crowd detection, ETA calculation, persistence
- Depends on: BODS API, TomTom Routing API, YOLOv8 model, GTFS schedule, database
- Used by: Database (writes BusLog rows), API responses
- Purpose: Store and query route configuration and historical bus logs
- Location: `server/models.py`
- Contains: `Route` (configuration), `BusLog` (history), `Stop` (GTFS), `RouteStop` (association)
- Depends on: SQLAlchemy, PostgreSQL
- Used by: All Flask endpoints, Fusion Engine
- Purpose: Parse external data sources into normalized formats
- Location: `server/bods_parser.py` (SIRI-VM XML), `server/gtfs_parser.py` (GTFS zip files)
- Contains: XML parsing, CSV reading, GTFS trip selection, live/scheduled trip matching
- Depends on: Requests library, zipfile, CSV readers
- Used by: Fusion Engine, schedule builders
- Purpose: Predict ETA using route-specific trained XGBoost models, calculate distances with fallback chain
- Location: `server/app.py` (XGBoost functions at line 277, routing at line 530)
- Contains: ETA feature engineering, model loading, haversine fallback, OSRM routing, TomTom routing
- Depends on: joblib, requests, trained `xgboost_eta_model_<route>.joblib` artifacts
- Used by: Fusion Engine (every cycle), schedule delay calculation
- Purpose: Detect passenger count at major stops from video feed
- Location: `server/app.py` (crowd functions at line 760)
- Contains: YOLOv8 inference on `bus_queue.mp4`, crowd smoothing, major stop detection
- Depends on: OpenCV, ultralytics YOLO, haversine distance calculations
- Used by: Fusion Engine (only when near major stops)
## Data Flow
- Route configuration: Static in `Route` table, loaded once per Fusion Engine cycle
- Live bus position/ETA: Latest BusLog entry per route
- Historical data: All BusLog entries, queried with time window filter (default 6 hours)
- Crowd history: In-memory `_crowd_history` dict, averaged over 3 readings to smooth YOLO noise
- GTFS schedule: Cached in memory via `get_cached_gtfs_data()` (line 409)
- ETA models: Loaded per route and memoized in the `_eta_models` registry
## Key Abstractions
- Purpose: Define a bus route (e.g., "Route 72 Outbound Temple Meads→Frenchay")
- Examples: `server/models.py` line 12, Flask query at `server/app.py` line 1246
- Pattern: SQLAlchemy model with `to_dict()` serializer; scalable by adding rows to DB
- Purpose: Time-series record of each Fusion Engine cycle per vehicle
- Examples: `server/models.py` line 57, written at `server/app.py` line 1375
- Pattern: Immutable insert-only log; queried by `route_id` + time window for history
- Purpose: BODS-parsed vehicle dict with position, destination, operator, direction
- Examples: Returned from `fetch_bods_vehicles()` at `server/bods_parser.py` line 17
- Pattern: Validated through `is_vehicle_live_for_route()` and operator filtering
- Purpose: Represents a single scheduled service from origin to destination
- Examples: Dict from `select_live_route_trip()` at `server/gtfs_parser.py` line 19
- Pattern: Matched to live bus position using stop proximity and timetable constraints
- Purpose: Physical bus stop with lat/lng from GTFS
- Examples: `server/models.py` line 96, used in predictions at `server/app.py` line 1217
- Pattern: Many-to-many with routes via `RouteStop` (sequence order)
## Entry Points
- Location: `server/app.py` line 1732 (main block)
- Triggers: `python app.py`
- Responsibilities: Initialize Flask app, create database tables, preload route-specific ETA models, start Fusion Engine thread, listen on port 5000
- Location: `server/app.py` line 1235 (function definition); started at line 1754
- Triggers: Spawned at app startup as daemon thread
- Responsibilities: Poll all routes every 10s, fetch BODS vehicles, compute ETA, write logs
- Location: `client/src/main.jsx` (entry point)
- Triggers: `npm run dev` (Vite dev server on :3000) or `npm run build` (static bundle)
- Responsibilities: Render route selector, fetch `/api` data, display map and dashboard
- Location: `server/setup_db.py`
- Triggers: `python setup_db.py` (before first run)
- Responsibilities: Create PostgreSQL database, initialize schema
## Error Handling
- **TomTom API failures:** Disable service on auth error (401/403), log once, fall back to OSRM (line 666-678)
- **XGBoost model missing for a route:** Use formula-based ETA for that route only
- **GTFS file missing:** Use DB-only stops if zip unavailable (line 405-407, 444-445)
- **BODS API key missing:** Return empty vehicle list, skip route (line 696-698)
- **YOLOv8 inference failure:** Caught in `count_passengers()`, return 0 crowd
- **Stale live data:** Detected by `is_recent_live_timestamp()`, route falls back to schedule-only (line 1514-1521)
- **Invalid vehicle position:** Filter by `is_vehicle_live_for_route()`, reject off-route vehicles (line 724-726)
## Cross-Cutting Concerns
- Framework: Python `logging` module
- Output: Console (via Flask dev server or systemd journal in production)
- Pattern: All major operations log with prefix tags: `[BODS]`, `[TomTom Routing]`, `[Fusion]`, `[Crowd]`, `[GTFS]`, `[XGBoost]`
- Route proximity: Haversine distance vs `ROUTE_PROXIMITY_THRESHOLD_KM` (2.0 km default)
- Schedule plausibility: Bus position vs scheduled stop within `LIVE_TRIP_MAX_EARLY_MINUTES` (5) and `LIVE_TRIP_MAX_LATE_MINUTES` (25)
- Crowd detection: Only applied within `CROWD_DETECTION_RADIUS_KM` (0.3 km) of major stops
- ETA bounds: Clamped to non-negative minutes
- API: No auth required (public endpoints)
- External services: API keys in environment variables (`BODS_API_KEY`, `TOMTOM_API_KEY`, `TOMTOM_ROUTING_KEY`)
- Database: Connection string from `DATABASE_URL` env var or hardcoded default
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
