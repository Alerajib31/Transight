# Codebase Concerns

**Analysis Date:** 2025-02-15

## Monolithic Application Files

**Backend Fusion Engine Consolidation:**
- Issue: `server/app.py` is 1759 lines containing Flask routes, Fusion Engine loop, ETA calculation, YOLO integration, TomTom/BODS/GTFS parsers, and database initialization all in one file.
- Files: `server/app.py`
- Impact: Makes testing individual components difficult, increases cognitive load, creates circular dependency risks as more features are added.
- Fix approach: Extract layers into separate modules: `server/services/fusion_engine.py`, `server/services/eta_calculator.py`, `server/services/traffic.py`, `server/services/crowd_detection.py`, `server/api/routes.py` (blueprint). Keep app.py as orchestrator only.

**Frontend App Component Complexity:**
- Issue: `client/src/App.jsx` manages routing, polling logic, map state, bus selection, and history fetching in a single component (400+ lines).
- Files: `client/src/App.jsx`
- Impact: Side effects are tightly coupled, refactoring polling intervals or fetch logic is risky, prop drilling becomes complex with more features.
- Fix approach: Extract custom hooks (`useBusPolling`, `useRouteSelection`, `useHistoryFetch`) and separate map concerns into `<BusMap>` and dashboard into `<DashboardPanel>`.

## Missing Test Coverage

**No Automated Test Suite:**
- Issue: Repository has test scripts (`server/test_api.py`, `server/test_route2.py`, `server/test_status.py`) but no unit/integration test framework configured. Tests are manual scripts, not executable via test runner.
- Files: `server/test_*.py` (manual only)
- Impact: Changes to ETA calculation, vehicle filtering, or GTFS trip selection can silently break without detection. Regression risk increases as complexity grows.
- Priority: High
- Fix approach: Migrate to pytest with fixtures for database, mock BODS/TomTom responses. Create test modules for: `test_eta_calculation.py`, `test_vehicle_filtering.py`, `test_fusion_engine_cycle.py`, `test_stop_predictions.py`.

**Crowd Detection Logic Untested:**
- Issue: `is_near_major_stop()` and crowd smoothing in `get_smoothed_crowd_count()` have complex heuristics (0.3 km radius, 3-frame average) but no test coverage.
- Files: `server/app.py` (lines 516-534, 492-513)
- Impact: YOLO integration bugs or edge cases (rapid direction changes, missed frames) remain undetected until user-facing.
- Fix approach: Add tests covering: boundary conditions (exactly at radius), empty frame sequences, vehicle ID persistence across frames.

## Global State and Thread Safety Issues

**Unprotected Global Dictionaries:**
- Issue: `_crowd_history`, `_latest_bus_metadata`, `_tomtom_service_state` are module-level dictionaries mutated by Fusion Engine thread without locks.
- Files: `server/app.py` (lines 93-106)
- Impact: Race condition risk when frontend makes concurrent requests while Fusion Engine updates state. Inconsistent reads on `_tomtom_service_state["disabled"]` and `_crowd_history[vehicle_id]`.
- Fix approach: Wrap shared state in threading.Lock or use queue.Queue. Move state into a thread-safe service class (e.g., `BusMetadataService()`).

**Video Capture Stateful Singleton:**
- Issue: `_video_capture` and `_frame_number` are global, managed by `count_passengers()`, risking frame skips or frame desync if called from multiple threads concurrently.
- Files: `server/app.py` (lines 830-890)
- Impact: YOLO crowd counts become unpredictable during high-frequency polling. Frame loop reset on EOF may cause missed detections.
- Fix approach: Encapsulate in a `YOLOVideoProcessor` class with instance lock and explicit frame state management.

## Database Transaction Issues

**Implicit Single-Use Transactions in Fusion Engine:**
- Issue: Fusion Engine commits after each bus log (line 1387: `db.session.commit()`) but does not isolate route fetches. If a route is deleted mid-loop, subsequent buses reference a stale route object.
- Files: `server/app.py` (line 1246-1387)
- Impact: Inconsistent state between two buses on same route if route is updated during processing. No rollback strategy for partial batch failures.
- Fix approach: Wrap entire route processing in a transaction with atomic multi-bus commits per route. Use SQLAlchemy `session.begin_nested()` for savepoints.

**Bare `db.session.rollback()` on Error:**
- Issue: Line 1399 rolls back on fusion engine error but doesn't log which route/bus failed, making debugging difficult.
- Files: `server/app.py` (line 1399)
- Impact: Silent data loss or inconsistent database state. No alert on repeated failures.
- Fix approach: Log route/vehicle context before rollback. Implement exponential backoff for repeated errors.

## API Validation and Input Handling

**Insufficient Query Parameter Validation:**
- Issue: `/api/routes/<route_id>/history` accepts unbounded `hours` (clamped to max 48) and `limit` (clamped to max 240), but no validation on `vehicle_id`. Could theoretically query for any vehicle_id string.
- Files: `server/app.py` (lines 1563-1612)
- Impact: No SQL injection risk (SQLAlchemy parameterized), but allows querying non-existent vehicle IDs, wasting database resources. No rate limiting.
- Fix approach: Whitelist vehicle_ids against actual buses on route before query. Add request rate limiting (Flask-Limiter).

**No 404 Distinction Between Non-Existent Route and No Live Data:**
- Issue: `/api/status/<route_id>` returns 404 with message "No data yet" when route exists but has no logs, conflating "route not found" with "no live data".
- Files: `server/app.py` (lines 1615-1726)
- Impact: Frontend cannot distinguish between configuration error (missing route) and transient issue (waiting for first Fusion cycle). Confusing UX.
- Fix approach: Return 200 with `"data_available": false` for no logs. Return 404 only for missing route_id.

## Error Handling Gaps

**Silent Fallback Chain in ETA Calculation:**
- Issue: `resolve_live_eta()` falls back from XGBoost → TomTom formula → haversine distance with no logging of which path was taken.
- Files: `server/app.py` (lines 350-375)
- Impact: Users don't know if ETA is model-based, traffic-aware, or just straight-line distance. Model training effort might be wasted if always falling back.
- Fix approach: Log which ETA method was used at each step with confidence score (e.g., "ETA 12.5m [XGBoost confidence: 0.8]").

**Bare `except Exception` Clauses:**
- Issue: Multiple broad exception handlers (e.g., line 1108, 1202, 1397) catch all errors without distinguishing transient vs. permanent failures.
- Files: `server/app.py` (multiple locations)
- Impact: Network timeouts treated same as parsing errors. No retry logic for transient faults. Obscures true bugs under generic logging.
- Fix approach: Catch specific exceptions (`requests.Timeout`, `ValueError`, `KeyError`) with appropriate retry/fallback strategies.

**GTFS Trip Selection Failure Silent:**
- Issue: `get_gtfs_schedule_trip()` returns None on any error (line 437) with generic error log. No distinction between "GTFS zip not found" vs. "trip matching algorithm failed".
- Files: `server/app.py` (lines 402-437)
- Impact: Frontend receives schedule-only response without visibility into why live trip selection failed. Could mask GTFS data corruption.
- Fix approach: Return error object with reason: `{"trip": null, "error": "gtfs_zip_not_found", "timestamp": ...}`.

## Missing Input Sanitization

**Frontend Bus Position Handling:**
- Issue: `client/src/App.jsx` doesn't validate API response structure before accessing nested properties like `bus.position.lat` (line 379).
- Files: `client/src/App.jsx` (lines 191-220, 375-383)
- Impact: Malformed API response or missing fields cause component crash with no fallback. No error boundary.
- Fix approach: Add response schema validation (Zod or similar). Provide safe getters with defaults: `getOrDefault(bus, "position.lat", null)`.

## Hardcoded Constants and Configuration

**Major Stops as Hardcoded Tuples:**
- Issue: `MAJOR_STOPS_OUTBOUND` and `MAJOR_STOPS_INBOUND` (lines 74-87) are hardcoded Bristol coordinates.
- Files: `server/app.py` (lines 74-87)
- Impact: Cannot support other cities or route changes without code edit. No database table for stops, no configuration management.
- Fix approach: Move to database: `MajorStop` table linked to routes. Load at startup from config or database.

**Crowd Detection Radius as Magic Number:**
- Issue: `CROWD_DETECTION_RADIUS_KM = 0.3` (line 90) is not justified or tunable without code change.
- Files: `server/app.py` (line 90)
- Impact: If 300m is too small/large for some stops, requires code deployment. No A/B testing path.
- Fix approach: Move to `config.py` or environment variable `CROWD_DETECTION_RADIUS_KM`. Document rationale.

**Operator Allowlist Split Logic Fragile:**
- Issue: Lines 63-67 parse and deduplicate operator codes with complex list comprehension and set/dict conversion.
- Files: `server/app.py` (lines 63-67)
- Impact: If `BODS_OPERATOR_ALLOWLIST` env var is malformed (extra spaces, empty), behavior is undefined. Limited to 2 operators by design but not documented.
- Fix approach: Add validation function: `parse_operator_allowlist(env_str) → List[str]` with tests. Document 2-operator limit.

## Security and Data Privacy

**No API Authentication:**
- Issue: All endpoints (`/api/routes`, `/api/status/<route_id>`, `/api/routes/<route_id>/history`) are publicly readable without credentials.
- Files: `server/app.py` (routes: lines 1469-1726)
- Impact: Anyone can scrape real-time bus positions, passenger counts, and historical data. No rate limiting. Potential for DoS.
- Fix approach: Add JWT authentication middleware (Flask-JWT-Extended) with refresh tokens. Implement per-endpoint rate limiting.

**Debug Mode Disabled But Check Absence:**
- Issue: Line 1758 has `debug=False` hardcoded, but no environment variable override for local development.
- Files: `server/app.py` (line 1758)
- Impact: Cannot enable Flask debugger for development without code edit. Relies on log output for troubleshooting.
- Fix approach: Use `debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true'`.

**Vehicle ID Exposed in API Responses:**
- Issue: Vehicle IDs from BODS (e.g., `FBRI-12345`) are logged and returned in API responses without redaction.
- Files: `server/app.py` (lines 292, 1286, 1690, 1754)
- Impact: Real vehicle identifiers could enable tracking of specific buses, raising privacy concerns for commercial operations.
- Fix approach: Implement vehicle ID hashing or redaction layer. Return opaque bus_key instead of raw BODS vehicle_id in public API.

## Data Quality and Validation

**No Validation on Route Path JSON:**
- Issue: `Route.route_path` is stored as JSON (line 29 in models.py) but no validation that it contains valid lat/lng pairs.
- Files: `server/models.py` (line 29)
- Impact: Invalid route paths cause haversine calculation failures (line 175-179) with cryptic errors. Silent NaN or inf distances.
- Fix approach: Add SQLAlchemy validator that parses and checks array structure. Return validation error on seed.

**Null Handling Inconsistency in Stop Predictions:**
- Issue: `calculate_stop_predictions()` doesn't handle case where `route_stops` is empty (returns empty list) vs. missing GTFS data (still tries to iterate).
- Files: `server/app.py` (lines 1114-1229)
- Impact: If route has no stops in database, predictions endpoint silently returns empty array. No indication of configuration error.
- Fix approach: Return error response: `{"error": "route_has_no_stops"}` when route_stops is empty on first-run.

**Traffic Delay Unreliable from TomTom:**
- Issue: `fetch_traffic_delay()` calculates delay per-km but uses instantaneous speed, not congestion trend or historical data.
- Files: `server/app.py` (lines 766-824)
- Impact: A single slow segment reports massive delay; stops with consistent congestion underestimate ETA. No confidence intervals.
- Fix approach: Request TomTom HistoricalTraffic API for realistic corridor delay. Add confidence score to response.

## Missing Graceful Degradation

**YOLO Model Not Found Causes Silent Zero Crowd:**
- Issue: If `xgboost_eta_model.joblib` doesn't exist, ETA calculation silently falls back to formula without warning in logs.
- Files: `server/app.py` (lines 276-295)
- Impact: ETA quality silently degrades. Users/ops don't know model is missing.
- Fix approach: Log warning at startup: "[Startup] XGBoost ETA model missing; using formula fallback. ETA accuracy will be reduced."

**GTFS Zip Load Cached But Stale:**
- Issue: `@lru_cache` on `_cached_gtfs` uses file mtime as key (line 129-131), but if GTFS is updated during process lifetime, cache is not invalidated.
- Files: `server/gtfs_parser.py` (lines 129-141)
- Impact: Service runs on outdated GTFS schedule for hours until restart. No hot-reload mechanism.
- Fix approach: Add explicit cache invalidation endpoint `/admin/refresh-gtfs`. Log file mtime on load.

## Performance and Scalability Issues

**Haversine Calculation in Tight Loop:**
- Issue: `route_distance_km()` calculates distance to all route points in a list comprehension for every vehicle (line 175-179).
- Files: `server/app.py` (lines 170-179)
- Impact: O(n) for each bus, O(n*m) total per Fusion cycle (n=buses, m=route_path_points). 100 buses × 100 route points = 10k calculations per cycle.
- Fix approach: Pre-compute or cache route geometry as spatial index. Use PostGIS if using PostgreSQL.

**Full Route Query Every Fusion Cycle:**
- Issue: `fusion_engine()` queries `Route.query.all()` every 10 seconds (line 1246), loading all routes from database.
- Files: `server/app.py` (lines 1244-1250)
- Impact: With 100+ routes, becomes N+1 problem when accessing `route.route_stops` on line 208. Unnecessary database pressure.
- Fix approach: Implement in-memory route cache with update hook on Route change. Query only once on startup.

**Video Frame Loop Without Buffering:**
- Issue: `count_passengers()` reads one frame per call, discarding frames between calls (line 862).
- Files: `server/app.py` (lines 844-889)
- Impact: If Fusion cycle runs every 10s but video is 30fps, frames 1-299 are discarded per cycle. Inefficient use of expensive video data.
- Fix approach: Implement sliding window frame buffer with one YOLO inference per N frames, averaging crowd counts.

## Dependency and Version Management

**Pinned Versions Without Upper Bounds:**
- Issue: `requirements.txt` pins exact versions (e.g., `flask==3.0.0`) but no upper bounds (`flask>=3.0.0,<4.0.0`).
- Files: `server/requirements.txt`
- Impact: Major version updates are blocked (good for stability) but no path for security patches within same major version. Becomes unmaintainable over time.
- Fix approach: Switch to `==3.0.*` for safe range, or use `poetry` with lock file.

**YOLOv8 Model Auto-Download:**
- Issue: First call to `get_yolo_model()` auto-downloads model from Ultralytics Hub if not cached (line 839). No control over model source.
- Files: `server/app.py` (lines 835-841)
- Impact: Deployment may fail silently if internet is unavailable. Model version/source is non-deterministic.
- Fix approach: Require model to be pre-downloaded and mounted. Fail fast with clear error message if not found.

## Missing Observability

**No Health Check Endpoint:**
- Issue: No dedicated health/readiness endpoint for Kubernetes or load balancers to check service status.
- Files: `server/app.py` (root endpoint at line 1452 is info-only, not health)
- Impact: Deployment automation cannot detect if Fusion Engine is stuck or database is down. Cannot distinguish "running" from "ready to serve".
- Fix approach: Add `/health` endpoint returning `{"status": "healthy", "fusion_engine": true, "database": true}` with probes.

**Limited Fusion Engine Logging Context:**
- Issue: Fusion Engine logs individual steps but doesn't correlate with route ID or cycle number, making log parsing difficult.
- Files: `server/app.py` (lines 1235-1401)
- Impact: Multi-route logs are interleaved. Cannot easily trace one complete cycle for a route. No structured logging (JSON).
- Fix approach: Use Python `structlog` library. Log `{"route_id": 1, "cycle": 42, "event": "fetched_vehicles", "count": 3}`.

## Frontend State Management Issues

**No Error Boundary:**
- Issue: `client/src/App.jsx` has no error boundary component. Component crash from malformed API data is unrecoverable.
- Files: `client/src/App.jsx`
- Impact: User sees blank screen on API schema mismatch. No fallback or recovery UX.
- Fix approach: Wrap main routes in `<ErrorBoundary>` that catches and displays error message with "Reload" button.

**Polling Intervals Hardcoded:**
- Issue: `POLL_INTERVAL = 10_000` (line 89) and `HISTORY_POLL_INTERVAL = 30_000` (line 90) are hardcoded.
- Files: `client/src/App.jsx` (lines 89-90)
- Impact: Cannot adjust polling from admin panel or config. High polling creates unnecessary API load.
- Fix approach: Fetch poll intervals from `/api/config` endpoint or make configurable via localStorage.

**localStorage Silent Failures:**
- Issue: Theme storage in `saveTheme()` (line 111-118) has try/catch that silently ignores storage failures.
- Files: `client/src/App.jsx` (lines 102-118)
- Impact: Private browsing mode silently fails to persist theme. No indication to user that preference won't be remembered.
- Fix approach: Log to console or show subtle toast notification on storage failure.

## Known Limitations and Trade-offs

**No Support for Multiple Buses Per Direction:**
- Issue: Code assumes one bus per route/direction for display (e.g., `activeBus` in frontend, latest BusLog per route_id in status endpoint).
- Files: `server/app.py` (line 1661-1664), `client/src/App.jsx` (line 346)
- Impact: When multiple buses are on same route (fetch returns array), frontend displays only first. Backend status endpoint dedupes to one bus per vehicle_id, but doesn't prioritize by ETA or position.
- Workaround: `/api/status/<route_id>` returns all buses in array, frontend should iterate but doesn't.
- Fix approach: Update frontend to render bus carousel or list. Update `/api/status` to return ordered array instead of single "status" object.

**GTFS Trip Selection Too Conservative:**
- Issue: `select_live_route_trip()` filters by schedule bounds (5 min early, 25 min late per lines 59-60), may reject valid in-service trips that are delayed more than 25 minutes.
- Files: `server/app.py` (lines 59-60, 236), `server/gtfs_parser.py` (trip selection logic)
- Impact: Major delays (>25 min) cause system to fall back to schedule-only predictions, losing real-time accuracy when it matters most.
- Fix approach: Use adaptive threshold based on historical delays for the route. Make configurable per route.

---

*Concerns audit: 2025-02-15*
