# Project Research Summary

**Project:** Transight AI — Multi-Route Expansion (Route 72 + A1 Airport Flyer)
**Domain:** Real-time multi-route bus tracking and arrival prediction
**Researched:** 2026-04-02
**Confidence:** HIGH (grounded primarily in direct codebase analysis)

## Executive Summary

Transight AI is a real-time bus prediction dashboard built on Flask 3, React 19, PostgreSQL, and Leaflet. The existing architecture is already N-route-capable at the database and Fusion Engine level — `Route.query.all()` drives the backend loop, `BusLog` rows carry `route_id`, and the GTFS parser accepts any `route_short_name`. Expanding from Route 72 to include the A1 Airport Flyer is a configuration, data-loading, and targeted-refactor problem, not a rewrite or platform migration. No new libraries are required on either the frontend or backend. The critical path is: verify A1 identifiers in BODS and GTFS, insert two Route rows (outbound + inbound), refactor a handful of hardcoded Route 72 assumptions in `app.py`, load GTFS stops for A1, then expose multi-route state in the React frontend.

The recommended approach is to work in two sequential phases. Phase 1 closes all backend gaps that would silently corrupt A1 data before any A1 route rows are inserted — specifically: BODS bulk-fetch refactor, GTFS agency-id filtering, MAJOR_STOPS route-awareness, and safe GTFS loader semantics. Phase 2 adds the frontend work (mobile bottom sheet, desktop side panel, stop popups, route-switching UX) and A1 ETA quality (synthetic training data and per-route XGBoost model). A deferred polish phase handles crowd occupancy surfacing, historical reliability summaries, and PWA manifest.

The dominant risk is silent data corruption: five of the thirteen identified pitfalls produce incorrect predictions or empty data with no visible error. The BODS per-route request multiplication, the hardcoded MAJOR_STOPS list, the GTFS route_short_name collision risk, the operator allowlist cap, and the Route 72-only XGBoost model all fail quietly. Each must be addressed before A1 data flows through the system, not after. Verification should be empirical first — inspect the actual BODS feed and GTFS file to confirm A1 identifiers — before writing any Fusion Engine code.

---

## Key Findings

### Recommended Stack

The existing stack (Flask 3, React 19, SQLAlchemy 2, PostgreSQL, Leaflet 1.9.4, react-leaflet 5, Tailwind v4) requires no additions. All required capabilities are already present. The GTFS parser, BODS fetcher, Fusion Engine loop, and API prediction endpoint are already multi-route in structure; they only need targeted fixes to remove Route 72-specific hardcoding.

**Core technologies (existing — do not change):**
- Flask 3 + SQLAlchemy 2: API and data pipeline — already route-agnostic via `Route.query.all()`
- PostgreSQL: Route/Stop/RouteStop/BusLog schema — already supports N routes
- `gtfs_parser.py` (stdlib only): GTFS extraction — already parameterised by `route_short_name`
- `bods_parser.py` (requests + ElementTree): BODS live data — already accepts per-call `line_ref`
- React 19 + Tailwind v4: Frontend — CSS-only bottom sheet via `100dvh` + `translate-transform`
- Leaflet 1.9.4 + react-leaflet 5: Map layer — existing `<Popup>` component sufficient for stop popups

**Stack-level actions required (no new dependencies):**
- Add per-route color CSS variables (`--color-route-72`, `--color-route-a1`) in `index.css`
- Increase stop icon tap targets to 44px minimum for mobile WCAG compliance
- Set `scrollWheelZoom={false}` on mobile to prevent scroll capture by the map
- Optional `GTFS_ROUTE_NAMES=72,A1` env var for seeding clarity (not strictly necessary)

### Expected Features

**Must have (table stakes) — MVP scope:**
- Route selector dropdown (switch between 72 and A1 including direction)
- Live bus marker per route with distinct color coding
- ETA at terminus per route on dashboard card
- Delay status badge (green/amber/red) on dashboard and stop popup
- Stop-level arrival time panel (scheduled vs predicted, delay propagation)
- Stop popup on map tap (populates from cached `routePredictions.stops[]`, no new endpoint)
- Directional awareness for A1 (outbound Bristol→Airport / inbound Airport→Bristol)
- Schedule fallback label when BODS data is stale or unavailable
- Mobile layout: full-screen map with bottom sheet
- Desktop layout: side-by-side map and info panel

**Should have (differentiators) — add after core is stable:**
- Predicted vs scheduled arrival side by side in stop list
- Live data freshness badge ("Updated X seconds ago")
- Crowd / occupancy indicator at major stops (backend computes it; UI needs surfacing)
- Historical reliability summary (rolling 7-day on-time % from existing BusLog data)

**Defer to v2+:**
- Multiple upcoming arrivals per stop (requires multi-vehicle tracking complexity)
- Dark/light theme toggle
- Routes beyond 72 and A1 (prove pattern with two routes first)
- Native mobile app / full PWA with push notifications
- Trip planner / auto-routing

### Architecture Approach

Keep the monolith. The Flask + daemon-thread + PostgreSQL pattern scales to N routes without restructuring. The Fusion Engine single-thread loop already iterates all routes; two routes add ~1-2 seconds to cycle time, well within the 10-second budget. The `App.jsx` single-component frontend should remain unified until it exceeds ~700 lines after new features are added, at which point `MapLayer.jsx` and `BottomSheet.jsx` extraction is warranted.

**Major components and their roles:**
1. **Fusion Engine** (`app.py` lines 1235–1450) — polls BODS, TomTom, XGBoost, YOLO every 10s for all routes; writes BusLog rows; must become route-aware for `is_near_major_stop()`
2. **Flask API** (`app.py` lines 1450–1732) — serves status, predictions, stops, history endpoints; already route-scoped by `route_id`
3. **Route Config** (PostgreSQL `routes` table) — database rows as configuration; adding a route = inserting rows, no code change to the loop
4. **React Shell** (`App.jsx`) — polling orchestration keyed to `selectedRouteId`; route switch naturally redirects all polls
5. **Map Layer** (Leaflet in `App.jsx`) — bus markers, stop markers (must become interactive `<Marker>` with `<Popup>`), route polyline
6. **Bottom Sheet / Side Panel** (new JSX in `App.jsx`) — mobile bottom sheet (`fixed bottom-0`, `translate-transform`); desktop side panel (`hidden md:flex`)

**Key pattern — stop popup from cached state, not new endpoint:**
The `/api/routes/<route_id>/predictions` response already contains `stops[]` with `predicted_arrival` and `delay_minutes` per stop. Stop popups should look up tapped stop in `routePredictions.stops` client-side. A dedicated per-stop endpoint is not needed for MVP.

### Critical Pitfalls

1. **BODS per-route HTTP request multiplication** — with 4 route directions (72 outbound, 72 inbound, A1 outbound, A1 inbound) the current one-call-per-route pattern issues 24 BODS requests/minute. Fetch all First Bristol vehicles once per cycle (no `lineRef` filter, `operator_ref=FBRI` only) and fan out to routes in-process. Must be done before A1 rows are inserted.

2. **MAJOR_STOPS hardcoded to Route 72 coordinates** — `is_near_major_stop()` uses module-level constants tied to Route 72 stops regardless of which route is being processed. A1 buses will always return `is_near=False`, silently zeroing out crowd detection. Fix: pass `route` object into `is_near_major_stop()` and load stop coordinates from per-route data structure.

3. **GTFS route_short_name collision for "A1"** — the South West GTFS feed covers the entire region; "A1" may match multiple operators. The current parser has no agency_id filter. Fix: filter by `agency_id` (First Bristol) when extracting A1 trips; log candidate count before committing any data.

4. **XGBoost model trained on Route 72 only** — applying the Route 72 ETA model to A1 (motorway segment, different stop spacing, different total_stops) produces confidently wrong ETAs. Fix: gate XGBoost off for A1 in Phase 1; generate A1 synthetic training data and produce `xgboost_eta_model_a1.joblib` in Phase 2 before enabling.

5. **`gtfs_loader.py` deletes all stops before reloading** — rerunning the loader to add A1 stops drops all Route 72 RouteStop associations first. If the A1 GTFS lookup fails mid-run, Route 72 loses its stops permanently. Fix: add `--route` argument to loader; use `RouteStop.query.filter_by(route_id=X).delete()` scoped deletion.

---

## Implications for Roadmap

Based on the combined research, a three-phase structure is recommended. The first phase is entirely backend and data integrity work. The second phase delivers visible frontend features. The third phase is optional polish.

### Phase 1: Backend Foundation and Data Pipeline

**Rationale:** Every other feature depends on correct A1 data flowing through the system. Five pitfalls (BODS rate, MAJOR_STOPS, GTFS collision, operator allowlist, destructive loader) silently corrupt data with no visible error. These must be fixed before any A1 route row is inserted. Discovery steps (BODS raw dump, GTFS file inspection) must precede implementation steps.

**Delivers:**
- A1 Route rows in database (outbound + inbound) with verified GTFS trip IDs and BODS identifiers
- Fusion Engine processing A1 buses with correct crowd detection and route-aware logic
- GTFS loader safe for multi-route operation (scoped delete, dry-run mode)
- Per-route XGBoost gating (A1 uses formula fallback, Route 72 continues with model)
- Structured logging with `route_name` prefix on all Fusion sub-cycle log lines

**Features addressed:** A1 in API endpoints, directional awareness, schedule fallback for A1

**Pitfalls avoided:** Pitfalls 1, 2, 3, 4, 5, 6, 7, 8

**Ordered tasks within phase:**
1. Empirical discovery: BODS raw dump to find A1 operator code and DirectionRef values
2. Empirical discovery: GTFS file inspection to find A1 `route_short_name` and agency_id
3. Logging: add route_name prefix to Fusion Engine log lines (prerequisite for debugging)
4. BODS: refactor to bulk fetch + local fan-out; remove `:2` operator allowlist cap
5. GTFS parser: add agency_id filter to `get_trip_candidates()`
6. GTFS loader: add `--route` scoped delete, dry-run mode
7. Fusion Engine: refactor `is_near_major_stop()` to accept route context
8. Route rows: insert A1 outbound and inbound with verified identifiers
9. GTFS load: run loader for A1; verify stop count and sequence
10. Validation: confirm A1 BusLog rows accumulate; confirm Route 72 data unaffected
11. `bods_parser.py` test harness: parameterise `line_ref` from env/argv (minor, Pitfall 11)
12. `seed.py`: add `--route` argument and `--destroy` gate; create `seed_a1.py` (Pitfall 12)
13. `_latest_bus_metadata`: add TTL eviction (Pitfall 9, low urgency but cheap while touching code)

### Phase 2: Frontend Multi-Route Experience

**Rationale:** Frontend work is largely independent of backend Phase 1 but cannot be validated for A1 until Phase 1 completes. The route selector, map viewport fix, and bottom sheet can be built in parallel with Phase 1 backend work. Stop popup depends on Phase 1 completing so `routePredictions.stops[]` is populated for A1.

**Delivers:**
- Route selector with all configured routes (dropdown lists Route 72 and A1 with direction)
- Map viewport flies to route bounds on route switch (Pitfall 10 fix)
- Stop markers converted to interactive `<Marker>` + `<Popup>` using cached predictions data
- Delay badge (green/amber/red) on dashboard card and stop popup
- Mobile bottom sheet layout (`fixed bottom-0`, CSS-only slide-up, no new library)
- Desktop side panel layout (`hidden md:flex md:w-80`)
- Per-route color tokens in `index.css` (`--color-route-72`, `--color-route-a1`)
- Stop icon tap targets increased to 44px minimum (WCAG 2.5.5)

**Features addressed:** Route selector, live bus markers with color coding, stop popup, delay badge, responsive layout, A1 directional selector

**Pitfalls avoided:** Pitfall 10 (map viewport), Pitfall 13 (stop popup implementation)

**Ordered tasks within phase:**
1. Route selector: fetch all routes from API, display with direction; style active route
2. Map viewport: `flyTo` on route change using route origin/destination bounds from Route model
3. Per-route color tokens and marker styling
4. Mobile bottom sheet: full-screen map, CSS slide-up panel with drag handle
5. Desktop side panel: breakpoint split, same content as bottom sheet
6. Stop markers: convert to interactive `<Marker>` + `<Popup>` with predictions lookup
7. Delay badge: define threshold constants (< 2 min = green, 2–5 = amber, > 5 = red); apply to dashboard and stop popup
8. Predicted vs scheduled side-by-side in stop list panel
9. Live data freshness label ("Updated X sec ago")

**Note on A1 ETA quality:** Generate A1 synthetic training data (`generate_synthetic_data.py`) and train `xgboost_eta_model_a1.joblib`. Enable XGBoost for A1 only after model validation. This can be done concurrently with frontend work as a parallel backend task within Phase 2.

### Phase 3: Polish and Differentiators (Deferred)

**Rationale:** These features improve quality and trust signals but do not unblock the core multi-route experience. Address only after Phase 1 and Phase 2 are stable and verified.

**Delivers:**
- Crowd occupancy badge on stop popup (YOLOv8 data already computed; UI surfacing only)
- Historical reliability summary card (rolling 7-day on-time % aggregation from BusLog)
- `manifest.json` for basic PWA install prompt (optional, low complexity)
- Additional route onboarding (route 3+ is pure configuration once the pattern is proven)

**Features addressed:** Crowd indicator, historical reliability, live data badge (if not added in Phase 2)

### Phase Ordering Rationale

- Phase 1 must precede Phase 2 validation because A1 stop predictions cannot be tested until A1 BusLog rows exist.
- Pitfalls 1–5 are all Phase 1 concerns; none can be deferred without risking silent wrong data reaching users.
- Frontend layout work (bottom sheet, desktop panel) is path-independent and can begin in parallel with Phase 1 backend tasks — but should not be considered complete until stop popup is tested against live A1 data.
- XGBoost for A1 is the one genuinely new ML task; it belongs in Phase 2 as a background track, not Phase 1, because it requires accumulated A1 BusLog data to generate meaningful synthetic training inputs.

### Research Flags

Phases likely needing deeper research or empirical verification during planning:

- **Phase 1 (BODS A1 identifiers):** The A1 operator code and BODS `LineRef` value must be verified against the live BODS API before any code is written. This is a data question, not a code question — run a raw BODS dump first.
- **Phase 1 (GTFS A1 short name):** The A1 `route_short_name` in `itm_south_west_gtfs.zip` must be confirmed by inspection before seeding. "A1", "A1X", or an agency-specific variant are all possible.
- **Phase 1 (`is_near_major_stop()` full internals):** ARCHITECTURE.md flags that lines 800–900 of `app.py` need reading before designing the route-aware refactor. The full function scope was not verified during research.
- **Phase 2 (A1 XGBoost training):** `train_xgboost.py` and `generate_synthetic_data.py` are route-specific and not parameterised. The effort to extend them for A1 is not fully estimated.

Phases with standard, well-documented patterns (can proceed without research phase):

- **Phase 2 (mobile bottom sheet):** CSS-only `translate-transform` pattern is standard and well-established. Implementation is direct.
- **Phase 2 (stop popup):** `react-leaflet` `<Popup>` is already used in the codebase for bus markers. Extension to stop markers follows the same pattern.
- **Phase 3 (additional routes):** Once the pattern is validated with A1, adding route 3+ is purely configuration (insert Route rows, run GTFS loader).

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All findings grounded in direct codebase analysis; no new libraries required — verified by reading existing parsers and engine code |
| Features | MEDIUM-HIGH | Table stakes derived from established transit app conventions (Citymapper, TfL Go, Google Maps Transit); codebase backend capabilities confirmed HIGH; WebSearch unavailable so external UX sources not verified |
| Architecture | HIGH | Patterns derived from observed code structure; `Route.query.all()` loop, `BusLog.route_id` isolation, and predictions endpoint per-stop data all directly confirmed |
| Pitfalls | HIGH | 12 of 13 pitfalls grounded in specific line-number evidence from codebase; BODS rate-limiting behaviour is MEDIUM (no live API verification possible) |

**Overall confidence:** HIGH — research is primarily codebase-grounded, not speculative. The main uncertainty is external data: A1's specific BODS `LineRef`, `operator_ref`, and GTFS `route_short_name` values are unknown until the live feed and GTFS file are inspected.

### Gaps to Address

- **A1 BODS `LineRef` and `operator_ref`:** Must be verified empirically before Phase 1 coding begins. Assumption is `FBRI`/`A1` but not confirmed. Run a raw BODS query with no filters and search for Airport Flyer vehicles by destination name.
- **A1 GTFS `route_short_name` and `agency_id`:** Must be confirmed by running the inspection snippet from STACK.md against `itm_south_west_gtfs.zip` before `gtfs_loader.py` is extended.
- **`is_near_major_stop()` full function body:** Lines 800–900 of `app.py` were not fully read during research. Read before designing the route-aware refactor to confirm the signature and any internal state dependencies.
- **`routePredictions.stops[].stop_id` type consistency:** Confirm the predictions endpoint returns `stop_id` as the GTFS string ID (not the internal integer PK) before building the client-side stop popup lookup. A type mismatch will cause silent popup failures.
- **`train_xgboost.py` parameterisation effort:** The A1 XGBoost track in Phase 2 requires understanding whether `train_xgboost.py` and `generate_synthetic_data.py` can be called with a route argument or require a more significant refactor.

---

## Sources

### Primary (HIGH confidence — direct codebase analysis)
- `server/app.py` (Fusion Engine lines 1235–1450, API lines 1450–1732, MAJOR_STOPS lines 75–88, operator allowlist lines 65–66)
- `server/models.py` (Route, BusLog, Stop, RouteStop schema)
- `server/bods_parser.py` (fetch functions, test harness)
- `server/gtfs_parser.py` (route lookup, trip candidates, agency filtering absence)
- `server/gtfs_loader.py` (destructive delete pattern lines 24–27)
- `server/seed.py` (drop_all pattern)
- `client/src/App.jsx` (polling, route selector, map markers, Leaflet integration)
- `client/src/index.css` (Tailwind v4 token structure)
- `.planning/codebase/CONCERNS.md` (existing concern audit)
- `.planning/PROJECT.md` (active requirements and scope)

### Secondary (MEDIUM confidence — established specs and conventions)
- GTFS specification (stable spec): https://gtfs.org/documentation/schedule/reference/
- BODS SIRI-VM API: https://developers.data.bus.dft.gov.uk/
- Tailwind CSS v4 (CSS-first configuration): https://tailwindcss.com/docs/v4-beta
- `100dvh` CSS unit: MDN Web Docs (Safari 15.4+, Chrome 108+, Firefox 101+)
- WCAG 2.5.5 Target Size: 44x44px minimum for touch targets
- Transit app UX conventions: Citymapper, TfL Go, Google Maps Transit, Transit App, Moovit (training knowledge — WebSearch unavailable for live verification)

---
*Research completed: 2026-04-02*
*Ready for roadmap: yes*
