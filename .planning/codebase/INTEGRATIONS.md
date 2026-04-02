# External Integrations

**Analysis Date:** 2026-04-02

## APIs & External Services

**Bus Open Data Service (BODS):**
- SIRI-VM (SIRI Vehicle Monitoring) XML feed for live bus positions
- What it's used for: Real-time vehicle GPS, speed, bearing, destination, vehicle reference
- SDK/Client: HTTP request via `requests` library
- Auth: API key via `BODS_API_KEY` environment variable
- Endpoint: `https://data.bus-data.dft.gov.uk/api/v1/datafeed` (inferred from bods_parser.py)
- Parser: `server/bods_parser.py::parse_siri_vm()` - Extracts vehicle data from XML
- Fetch function: `server/bods_parser.py::fetch_bods_vehicles()` - Queries with line reference and operator filters
- Operator filtering: `BODS_OPERATOR_ALLOWLIST` (default: FBRI, FBRA for First Bristol)
- Fallback: Returns empty list on connection error; Fusion Engine continues with fallback prediction

**TomTom Traffic Flow API:**
- What it's used for: Current traffic speed and delay estimation at a point location
- SDK/Client: HTTP request via `requests` library
- Auth: API key via `TOMTOM_API_KEY` environment variable
- Endpoint: `https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json`
- Fetch function: `server/app.py::fetch_traffic_delay()` (lines 766-824)
- Parameters: Point (lat, lng), unit (KMPH), key
- Returns: Current speed vs free-flow speed; calculates delay in seconds per km
- Error handling: Disables on 401/403 auth errors with graceful fallback to zero delay
- Timeout: 10 seconds

**TomTom Routing API:**
- What it's used for: Accurate road distance and travel time with live traffic consideration
- SDK/Client: HTTP request via `requests` library
- Auth: API key via `TOMTOM_ROUTING_KEY` environment variable (separate key from Traffic API)
- Endpoint: `https://api.tomtom.com/routing/1/calculateRoute/`
- Fetch function: `server/app.py::get_route_distance_tomtom()` (lines 615-672)
- Parameters: Origin (lat, lng), destination (lat, lng), key, traffic=true, routeType=fastest
- Returns: Distance (meters), travel time (seconds), traffic delay (seconds)
- Fallback: Falls back to OSRM (free API) if no routing key provided or on error
- Timeout: 10 seconds

**Open Source Routing Machine (OSRM):**
- What it's used for: Free fallback for road distance and travel time (no live traffic)
- SDK/Client: HTTP request via `requests` library
- Auth: No API key required (public API)
- Endpoint: `http://router.project-osrm.org/route/v1/driving/`
- Fetch function: `server/app.py::get_route_distance_osrm()` (lines 569-609)
- Parameters: Start (lng, lat), end (lng, lat), overview=false, steps=false
- Returns: Distance (meters), duration (seconds)
- Usage: Primary fallback when TomTom routing key unavailable or times out
- Timeout: 10 seconds

## Data Storage

**Databases:**
- PostgreSQL 12+ at `localhost:5432` (configurable via `DATABASE_URL`)
- Connection: psycopg2-binary 2.9.9
- Client: SQLAlchemy 2.0.23 ORM
- Credentials: Embedded in `DATABASE_URL` (user/password in connection string)

**Tables:**
- `routes` - Route configuration (stops, endpoints, GTFS trip reference)
- `bus_logs` - Historical Fusion Engine cycle data (GPS, crowd, traffic, ETA per second)
- `stops` - GTFS stop master data (from itm_south_west_gtfs.zip)
- `route_stops` - Route-stop sequence and timings

**File Storage:**
- Local filesystem only
- GTFS zip: `../itm_south_west_gtfs.zip` (relative to `server/app.py`)
- YOLO model: `server/yolov8n.pt`
- XGBoost model: `server/xgboost_eta_model.joblib`
- Video feed: Configurable path (default: `bus_queue.mp4`)

**Caching:**
- In-memory GTFS cache: `server/gtfs_parser.py::@lru_cache`
- Passenger count smoothing: Rolling window stored in `_crowd_history` dict
- Latest bus metadata: Cached in `_latest_bus_metadata` global

## Authentication & Identity

**Auth Provider:**
- Custom: API keys and no formal identity management
- Implementation: Environment variable-based API keys for external services
  - BODS_API_KEY: For BODS API
  - TOMTOM_API_KEY: For TomTom Traffic
  - TOMTOM_ROUTING_KEY: For TomTom Routing
- Database: PostgreSQL password in connection string (default embedded in code)
- Frontend: No authentication (public dashboard, no user accounts)

## Monitoring & Observability

**Error Tracking:**
- None configured (no Sentry, Rollbar, etc.)
- Local logging via Python `logging` module in `server/app.py` and all parsers

**Logs:**
- Approach: Standard Python logging with logger named "transight"
- Output: Console (stdout/stderr)
- Levels: INFO, WARNING, ERROR
- Key log sources:
  - `[BODS]` - Vehicle fetch and parsing
  - `[TomTom]` - Traffic and routing API calls
  - `[OSRM]` - Fallback routing
  - `[YOLO]` - Model loading and passenger detection
  - `[GTFS]` - Schedule parsing
  - `[Fusion Engine]` - Main cycle loop
- Service state tracking: `_tomtom_service_state` dict stores disabled/auth_logged flags for graceful degradation

## CI/CD & Deployment

**Hosting:**
- Not configured (local/manual deployment assumed)
- Backend: Flask app listening on port 5000 (can be changed)
- Frontend: Vite dev server on port 3000 (dev) or static build output

**CI Pipeline:**
- None detected

**Build Output:**
- Frontend: `client/dist/` (built via `npm run build`)
- Backend: Python modules in place, no compilation step

## Environment Configuration

**Required env vars:**
- `DATABASE_URL` - PostgreSQL connection (default provided in code)
- `BODS_API_KEY` - Blank by default, required for live bus data
- `TOMTOM_API_KEY` - Blank by default, optional (traffic will be disabled if missing)
- `TOMTOM_ROUTING_KEY` - Blank by default, optional (falls back to OSRM)

**Optional env vars:**
- `VIDEO_PATH` - Path to video file (default: bus_queue.mp4)
- `FUSION_INTERVAL` - Cycle interval in seconds (default: 10)
- `LIVE_DATA_MAX_AGE_SECONDS` - Max age before fallback (default: 180)
- `ROUTE_PROXIMITY_THRESHOLD_KM` - Vehicle-route match distance (default: 2.0)
- `BODS_OPERATOR_ALLOWLIST` - Operator codes (default: FBRI,FBRA)
- `LIVE_TRIP_MAX_EARLY_MINUTES` - Schedule tolerance (default: 5)
- `LIVE_TRIP_MAX_LATE_MINUTES` - Schedule tolerance (default: 25)

**Secrets location:**
- `.env` file at project root or `server/` directory
- Loaded via `server/env_utils.py::load_project_env_files()`
- Also supports shell environment variables (override .env)
- Example: `.env.example` at project root shows format

**Loading mechanism:**
- On Flask startup: `server/env_utils.py::load_project_env_files()` called at top of `server/app.py`
- Looks for `.env` in `server/` directory first, then project root
- Does not override existing environment variables

## Webhooks & Callbacks

**Incoming:**
- None configured

**Outgoing:**
- None configured
- All integrations are pull-based (polling BODS, TomTom, OSRM)

## Fusion Engine Data Flow

**Polling Cycle** (every `FUSION_INTERVAL` seconds, default 10s):

1. **BODS Vehicle Fetch** - `fetch_bods_vehicles(BODS_API_KEY, line_ref=route_name, operator_ref=BODS_OPERATOR)`
   - Returns current GPS positions and metadata for matching buses
   - Fallback: Empty list if API unavailable

2. **TomTom Traffic Query** - `fetch_traffic_delay(bus_lat, bus_lng)`
   - Queries current traffic speed at bus location
   - Returns delay in seconds; falls back to 0.0 if unavailable

3. **TomTom or OSRM Routing** - `get_route_distance_tomtom()` or `get_route_distance_osrm()`
   - Gets road distance and travel time to destination
   - TomTom preferred if key provided and working; OSRM fallback

4. **YOLOv8 Passenger Detection** - `count_passengers(VIDEO_PATH)`
   - Runs inference on next frame of video
   - Returns detected person count
   - Fallback: 0 if video missing or corrupted

5. **XGBoost ETA Prediction** - `predict_eta_xgboost()`
   - Uses distance, traffic, crowd, and other features to predict ETA
   - Model: `server/xgboost_eta_model.joblib` (trained via `server/train_xgboost.py`)

6. **Persist BusLog** - `server/models.py::BusLog`
   - Stores: Vehicle ID, GPS, passenger count, traffic delay, predicted ETA, schedule info
   - Row per cycle per active route

## Rate Limits & Quotas

**BODS API:**
- Limit: Not documented in codebase
- Query frequency: Every 10 seconds per route

**TomTom APIs:**
- Limit: Not documented in codebase
- Query frequency: Every 10 seconds per vehicle for traffic; per route calculation for distance

**OSRM:**
- Public API with unknown limits
- Used as fallback when TomTom unavailable

## Data Retention

**Bus Logs:**
- No retention policy defined
- Historical data accumulates in `bus_logs` table indefinitely

**GTFS Data:**
- Cached in memory from zip file at startup
- Can be reloaded via `server/gtfs_loader.py`

---

*Integration audit: 2026-04-02*
