# Architecture Patterns: Multi-Route Transit Prediction

**Domain:** Real-time multi-route bus tracking and arrival prediction
**Researched:** 2026-04-02
**Confidence:** HIGH (grounded in existing codebase; patterns derived from well-established
transit app and background-worker architecture; WebSearch unavailable so no external
community sources cited — recommendations flagged accordingly)

---

## Recommended Architecture

Keep the monolith. Do not split into microservices. The Flask + daemon-thread + PostgreSQL
pattern already scales to N routes because the Fusion Engine already iterates
`Route.query.all()` (line 1246 in app.py). The right pattern is to extend what exists,
not restructure.

### High-Level Picture

```
Browser (React)
  |
  |  10s poll: /api/status/<route_id>
  |  10s poll: /api/routes/<route_id>/predictions
  |  on-demand: /api/routes/<route_id>/stops
  |  tap on stop marker → /api/routes/<route_id>/stops/<stop_id>/next-arrival  [NEW]
  v
Flask API  (server/app.py)
  |
  |  reads latest BusLog per route
  |  reads RouteStop + Stop for geometry
  v
PostgreSQL  (Route, Stop, RouteStop, BusLog)
  ^
  |  writes BusLog every 10s per vehicle
Fusion Engine  (daemon thread in app.py)
  |
  |-- BODS (live GPS, per route_name)
  |-- TomTom (traffic delay, per vehicle position)
  |-- GTFS cache (schedule, per route gtfs_trip_id)
  |-- XGBoost (ETA, per vehicle)
  |-- YOLOv8 (crowd, near major stops only)
```

---

## Component Boundaries

| Component | Responsibility | Communicates With | Lives In |
|-----------|---------------|-------------------|----------|
| Fusion Engine | Poll all routes every 10s; write BusLog | BODS, TomTom, GTFS cache, XGBoost, YOLO, PostgreSQL | `server/app.py` lines 1235–1450 |
| Flask API | Serve JSON to frontend; assemble predictions from DB | PostgreSQL, GTFS cache | `server/app.py` lines 1450–1732 |
| Route Config | Define all active routes; Fusion Engine iterates this | PostgreSQL (routes table) | `server/models.py` Route model |
| BusLog Store | Time-series of every fusion cycle per vehicle | Written by Fusion Engine, read by API | `server/models.py` BusLog model |
| Stop Store | GTFS geometry and schedule for each stop | Written by GTFS loader, read by predictions endpoint | `server/models.py` Stop + RouteStop |
| React Shell | Layout, route selector, polling orchestration | Flask API | `client/src/App.jsx` |
| Map Layer | Leaflet map, bus markers, stop markers, route polyline | React state (buses, stops, selectedStop) | `client/src/App.jsx` map section |
| Bottom Sheet / Side Panel | Route info, stop arrival times, delay indicators | React state (routePredictions, selectedStop) | `client/src/App.jsx` — currently dashboard cards; evolves to sheet |
| Stop Popup | Next arrival time + delay for a tapped stop | `/api/routes/<route_id>/stops/<stop_id>/next-arrival` | New endpoint + Leaflet Popup or custom overlay |

**Key constraint:** The React app is a single component today. Extracting the map layer,
bottom sheet, and stop popup into their own files (e.g., `MapLayer.jsx`,
`BottomSheet.jsx`) is a maintainability improvement but is not required for correctness.
Do it if the component exceeds ~600 lines after adding new features; defer otherwise.

---

## Data Flow

### Multi-Route Fusion Cycle (Every 10 Seconds)

```
Fusion Engine wakes
  └─ Route.query.all()  →  [Route 72 outbound, Route 72 inbound, A1 outbound, A1 inbound]
       for each route:
         └─ fetch_all_buses_for_route(route)
              └─ BODS API call (filtered by route.route_name)
         for each vehicle:
           ├─ TomTom traffic delay
           ├─ YOLO crowd (if near major stop)
           ├─ XGBoost ETA
           └─ INSERT BusLog(route_id=route.id, vehicle_id=..., ...)
```

The loop is already N-route-aware. Adding A1 = inserting two Route rows (one per
direction). No code change to the loop itself is needed.

**Single concern to resolve:** `is_near_major_stop()` uses a hardcoded list of major stop
names tied to Route 72's direction string. This must be made route-aware (accept a
`Route` object or a list of major stop lat/lngs from the DB) before A1 can use crowd
detection correctly. This is a moderate refactor within app.py.

### Frontend Polling Flow (Selected Route Context)

```
User selects route from dropdown
  └─ setSelectedRouteId(id)
       ├─ fetchStatus()    →  GET /api/status/<id>       (10s interval)
       ├─ fetchPredictions() → GET /api/routes/<id>/predictions  (10s interval)
       ├─ fetchStops()     →  GET /api/routes/<id>/stops (once per route change)
       └─ fetchHistory()   →  GET /api/routes/<id>/history (30s interval)
```

This pattern is already correct for multi-route. Changing `selectedRouteId` naturally
switches all polls. No architecture change needed — only the route selector UI needs
updating to list all configured routes.

### Stop Popup Data Flow (New — Does Not Exist Yet)

```
User taps stop marker on map
  └─ setSelectedStop(stop)            [React state]
       └─ fetch /api/routes/<routeId>/stops/<stopId>/next-arrival
            └─ backend: find latest BusLog for routeId
                        calculate_stop_predictions() already does this
                        return the stop's predicted + scheduled arrival time
  → Render Popup (Leaflet) or BottomSheet panel with stop name + arrival
```

**Recommended approach:** Reuse the existing `calculate_stop_predictions()` output
already returned by `/api/routes/<route_id>/predictions`. The frontend already receives
the full `routePredictions.stops[]` array every 10 seconds. A stop popup can be built
purely client-side by looking up the tapped stop's `stop_id` in the cached
`routePredictions.stops` array — no new backend endpoint needed for MVP.

A dedicated `/api/routes/<route_id>/stops/<stop_id>/next-arrival` endpoint is useful
later for direct linking and native app integration, but is not the unblocking step.

---

## Patterns to Follow

### Pattern 1: Route Rows as Configuration, Not Code

**What:** Each route (including directions) is a database row in the `routes` table.
Adding a route = inserting rows. The Fusion Engine and API are already route-agnostic.

**When:** Every time a new route or direction is added.

**How:**
```python
# seed or migration script — no app.py change needed
Route(
    route_name="A1",
    direction="outbound",
    origin_name="Bristol City Centre",
    origin_lat=51.4488,
    origin_lng=-2.5951,
    destination_name="Bristol Airport",
    dest_lat=51.3827,
    dest_lng=-2.7191,
    gtfs_trip_id="...",     # extracted from GTFS
    typical_duration_min=40.0,
    total_stops=...,
)
```

**Confidence:** HIGH — this is exactly how the existing code is structured
(models.py line 16 docstring: "Adding a new row here automatically includes it in the
Fusion Engine loop").

### Pattern 2: Scoped BusLog Queries

**What:** Every BusLog row carries `route_id`. All status, prediction, and history
queries filter on `route_id`. This is the primary isolation boundary between routes.

**When:** Any query that reads live or historical bus data.

**Example (existing — do not change):**
```python
log = BusLog.query.filter_by(route_id=route_id).order_by(BusLog.timestamp.desc()).first()
```

### Pattern 3: Client-Side Stop Lookup from Cached Predictions

**What:** The frontend already receives `routePredictions.stops[]` every 10 seconds.
Stop arrival data for a tapped stop should be derived from this cached array rather than
a separate per-stop fetch.

**When:** Stop popup rendering on marker click.

**Example:**
```javascript
// On stop marker click:
const stopPrediction = routePredictions.stops.find(
  s => s.stop_id === clickedStop.stop_id
);
// stopPrediction.predicted_arrival and stopPrediction.delay_minutes are already there
```

**Confidence:** HIGH — the predictions endpoint already returns per-stop times
(app.py line 1527–1559).

### Pattern 4: Mobile Bottom Sheet via CSS Position Fixed

**What:** A slide-up panel anchored to the viewport bottom. Full-screen map behind it,
panel overlaps bottom ~40% of screen on mobile. On desktop, the same content renders in
a right-side panel.

**When:** Mobile layout for route summary, stop predictions, and active bus status.

**Example structure (Tailwind v4):**
```jsx
{/* Bottom sheet — mobile only */}
<div className="fixed bottom-0 left-0 right-0 z-[1000]
                bg-surface rounded-t-2xl shadow-xl
                max-h-[45vh] overflow-y-auto
                md:hidden">
  {/* drag handle */}
  <div className="w-10 h-1 bg-muted mx-auto mt-3 rounded-full" />
  {/* content: route name, buses, stop predictions */}
</div>

{/* Side panel — desktop only */}
<div className="hidden md:flex md:flex-col md:w-80
                bg-surface border-l border-border
                overflow-y-auto">
  {/* same content */}
</div>
```

**Tailwind v4 note:** These use CSS variable tokens (`bg-surface`, `border-border`) as
defined in `client/src/index.css`. Do not introduce `tailwind.config.js`.

**Confidence:** MEDIUM — pattern is standard across transit apps (TfL, Citymapper,
Google Maps); implementation specifics for this codebase inferred from existing
Tailwind v4 token usage.

### Pattern 5: Leaflet Stop Marker with Inline Popup (No New Endpoint)

**What:** Stop markers use Leaflet's `<Popup>` component. Content is populated from
React state (`routePredictions.stops`) at click time, not from a fetch.

**When:** Stop marker tap on map.

**Example:**
```jsx
{stops.map((stop) => {
  const pred = routePredictions.stops.find(s => s.stop_id === stop.stop_id);
  return (
    <Marker key={stop.stop_id} position={[stop.lat, stop.lng]} icon={stopIcon}>
      <Popup>
        <strong>{stop.stop_name}</strong>
        {pred ? (
          <>
            <div>Next: {pred.predicted_arrival}</div>
            <div style={{ color: pred.delay_minutes > 2 ? 'red' : 'green' }}>
              {pred.delay_minutes > 0 ? `+${pred.delay_minutes} min late` : 'On time'}
            </div>
          </>
        ) : (
          <div>Schedule only</div>
        )}
      </Popup>
    </Marker>
  );
})}
```

**Confidence:** HIGH — react-leaflet `<Popup>` is already used in the existing codebase
(App.jsx line 11 import; bus markers already use Popup).

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Per-Route Daemon Threads

**What:** Spawning a separate background thread per route as you add routes.

**Why bad:** The existing single-thread loop already processes all routes sequentially.
Two routes with 10s cycle time = ~1-2 seconds per route, well within budget.
Separate threads add shared-state complexity (locking `_crowd_history`,
`_latest_bus_metadata`, GTFS cache) with no benefit at this scale.

**Instead:** Keep the single Fusion Engine thread. If cycle time grows beyond 30 seconds
as you add more routes, move to a per-route lock-free approach (separate process per
route with a shared DB) — but that is not a concern for 2–3 routes.

### Anti-Pattern 2: Separate `/api/stop/<stop_id>` Status Endpoint at MVP

**What:** Building a dedicated stop-status endpoint that re-runs prediction logic just
for one stop.

**Why bad:** The `/api/routes/<route_id>/predictions` response already contains all
stops with predicted times. Duplicating the prediction logic in a new endpoint creates
two sources of truth and double the DB reads.

**Instead:** Serve stop popups from the predictions cache already in React state.
Add the dedicated endpoint only when a second consumer (e.g., a public stop page)
needs it.

### Anti-Pattern 3: Hardcoding A1 Route Logic in app.py

**What:** Adding `if route.route_name == "A1": ...` branches inside the Fusion Engine.

**Why bad:** Breaks the route-agnostic design. The engine should use only fields
available on the `Route` model (lat/lng, direction, gtfs_trip_id, total_stops).
Any A1-specific tuning belongs in the database row, not as code branches.

**Instead:** If A1 needs different BODS operator filters or proximity thresholds,
add those as nullable columns on the `Route` model and fall back to defaults when null.

### Anti-Pattern 4: Splitting App.jsx Before It Breaks

**What:** Pre-emptively splitting the single-component frontend into many files before
the new features are working.

**Why bad:** React component extraction is a refactor, not a feature. Doing it
speculatively adds risk (re-wiring state, prop drilling) without user-visible value.

**Instead:** Build the bottom sheet and stop popup as JSX blocks inside `App.jsx` first.
Extract to separate `.jsx` files only when the file becomes hard to navigate (practical
threshold: 700+ lines or two distinct interaction patterns that need their own state).

---

## Scalability Considerations

| Concern | 2 routes (now) | 5 routes | 10+ routes |
|---------|---------------|----------|------------|
| Fusion cycle time | ~2–4s per cycle, single thread is fine | ~5–10s, still fine | May approach 10s interval; consider parallelising route loops with `concurrent.futures.ThreadPoolExecutor` |
| BusLog table size | ~8,640 rows/day (2 routes × 2 buses × 10s) | ~21,600 rows/day | Add `route_id` index if not present; partition by month |
| GTFS cache memory | Negligible for 2 routes | Negligible | Cache per route_name key, evict infrequently used |
| Frontend poll load | 4 concurrent fetches per route change, fine | Fine | Fine — polling is per selected route, not all routes |
| Major-stop crowd detection | Hardcoded to Route 72 stops | Must be DB-driven | Route model needs `major_stops` JSON column or separate table |

---

## Build Order (Phase Dependency Graph)

The following ordering is derived from data dependencies:

```
1. A1 Route Data (DB rows + GTFS stops)
   — Required before: Fusion Engine can track A1
   — Required before: Frontend can display A1 stops on map

2. Fusion Engine: Route-Aware Major Stop Detection
   — Required before: A1 crowd detection works correctly
   — Unblocks: A1 Fusion Engine predictions being accurate
   — Scope: Refactor is_near_major_stop() to accept route context

3. A1 Live Tracking (Fusion Engine running for A1)
   — Required before: BusLogs accumulate for A1
   — Required before: Stop predictions are live (not schedule-only) for A1

4. Route Selector UI + Multi-Route Frontend State
   — Required before: Users can switch to A1
   — Depends on: /api/routes returning A1 rows (satisfied in step 1)

5. Stop Popup on Map
   — Depends on: stops[] loaded per route (already working)
   — Depends on: routePredictions.stops[] populated (working for Route 72,
     working for A1 after step 3)
   — No backend dependency — can be built in parallel with steps 2–3

6. Mobile Bottom Sheet Layout
   — No backend dependency — pure CSS/JSX restructure
   — Can be built in parallel with steps 1–5
   — Should be done after stop popup so content is settled

7. Desktop Side Panel Layout
   — Same as bottom sheet — no backend dependency
   — Build after bottom sheet (share content, split by breakpoint)
```

**Critical path:**
A1 Route Data → A1 Fusion Engine tracking → A1 Predictions API working

Stop popup and layout work (steps 5–7) are independent of the critical path and can
proceed in parallel with backend work.

---

## Existing Strengths (Do Not Break)

1. **Route.query.all() loop** — the Fusion Engine is already N-route. Preserve this.
2. **Graceful fallback chain** — no-key, stale-data, and OSRM fallbacks. All must be
   preserved when touching the Fusion Engine.
3. **BusLog as insert-only log** — immutable history. Never update rows in place.
4. **`_t` cache-busting on all poll fetches** — prevents stale browser caching.
   Preserve on any new fetch calls.
5. **`routePredictions.stops[]` cached in React state every 10s** — this is the
   low-latency path to stop arrival data without extra fetches.

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Fusion Engine scaling | HIGH | Directly observed in app.py lines 1244–1252 — loop already iterates all routes |
| Route-as-DB-config pattern | HIGH | Documented in models.py docstring; verified in codebase |
| Stop popup from cached predictions | HIGH | predictions endpoint already returns per-stop data (app.py 1527–1559) |
| Bottom sheet CSS pattern | MEDIUM | Standard transit app pattern; Tailwind v4 implementation inferred from existing token usage |
| Build order dependencies | HIGH | Derived from data flow — A1 BusLogs cannot exist until Route rows and Fusion tracking exist |
| Major stop refactor scope | MEDIUM | is_near_major_stop() behaviour inferred from app.py line 1300–1302; full function not read |

---

## Gaps to Address in Phase Planning

- **is_near_major_stop() internals** — read lines 800–900 of app.py before designing
  the route-aware refactor. Confidence in scope estimate is MEDIUM.
- **BODS filtering for A1** — the A1 Airport Flyer operator may differ from FBRI
  (First Bristol). Verify which operator code BODS uses for A1 before writing the
  Route row. This is a data question, not an architecture question.
- **GTFS trip selection for A1** — `Route.gtfs_trip_id` is a single trip ID. A1 runs
  frequently; the correct trip to anchor to needs validation against the GTFS file.
- **`routePredictions.stops[].stop_id` type consistency** — confirm the predictions
  endpoint returns `stop_id` as the GTFS string ID (not the internal integer PK) so
  it matches the `stops[]` array used for map markers. If there is a mismatch, the
  client-side stop popup lookup will silently fail.

---

*Architecture analysis: 2026-04-02*
*Primary sources: server/app.py, server/models.py, client/src/App.jsx,
.planning/codebase/ARCHITECTURE.md*
