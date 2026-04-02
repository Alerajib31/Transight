# Domain Pitfalls: Multi-Route Transit Prediction Scaling

**Domain:** Real-time bus prediction — scaling from 1 route to N routes
**Researched:** 2026-04-02
**Source basis:** Direct codebase analysis (`server/app.py`, `server/bods_parser.py`,
`server/gtfs_parser.py`, `server/seed.py`, `client/src/App.jsx`) + known patterns
in transit data engineering. WebSearch unavailable; all findings grounded in
current codebase evidence or well-established SIRI-VM / GTFS design constraints.
**Confidence:** HIGH for pitfalls grounded in observed code. MEDIUM for BODS
rate-limiting and A1 GTFS coverage claims (no live API verification possible).

---

## Critical Pitfalls

Mistakes that require significant rework or cause silent wrong predictions.

---

### Pitfall 1: BODS Issues One HTTP Request Per Route Per Fusion Cycle

**What goes wrong:**
`fetch_all_buses_for_route()` calls `fetch_bods_vehicles(line_ref=route_name)` once
per route per Fusion cycle. With Route 72 alone that is 6 requests per minute (one
outbound + one inbound, every 10 s). Adding A1 (two directions) doubles it to 12
requests per minute. BODS SIRI-VM is a public API without published rate limits;
First Bus operators share feed bandwidth across all data consumers. Under sustained
high frequency the API returns empty XML before it returns an error, silently
starving the second route of data.

**Why it happens:**
The current architecture was designed for a single route. `fetch_bods_vehicles` with
a `lineRef` filter returns only that route's vehicles, which looks efficient but means
a separate round-trip for every (route, direction) pair.

**Evidence in codebase:**
- `server/app.py` line 702: `fetch_bods_vehicles(api_key=BODS_API_KEY, line_ref=route_name)` — one call per route loop iteration
- `server/app.py` line 1252: outer `for route in routes:` iterates every 10 s
- `server/bods_parser.py` line 155: test harness also calls with `line_ref='72'` (hardcoded, will not cover A1)

**Consequences:**
Route 72 starves A1, or A1 starves Route 72, with no error surfaced. The
`logger.warning("No vehicles found")` path is hit but operator logs are hard to
distinguish for different routes when interleaved.

**Prevention:**
Fetch all First Bristol vehicles once per cycle (no `lineRef` filter, just
`operator_ref=FBRI`) and fan the response out to each route in-process. This is
O(1) BODS calls per cycle regardless of route count. The existing
`is_vehicle_live_for_route()` filter is already written to do this assignment
locally — it just needs to be called after a single bulk fetch rather than inside
each per-route fetch.

**Warning signs:**
- A1 predictions remain schedule-only while Route 72 is live
- BODS call count in logs doubles as routes are added
- Periodic bursts of "No vehicles found" for one route but not the other

**Phase that must address this:** Phase 1 / Fusion Engine multi-route work, before A1
data pipeline goes live. Do not land A1 in the DB until the bulk-fetch pattern is in
place.

---

### Pitfall 2: MAJOR_STOPS Hardcoded to Route 72 Coordinates — Crowd Detection Breaks for A1

**What goes wrong:**
`MAJOR_STOPS_OUTBOUND` and `MAJOR_STOPS_INBOUND` (lines 75–88 of `app.py`) are
hardcoded to Route 72 stop coordinates (Temple Meads, College Green, Frenchay
Campus, etc.). `is_near_major_stop()` uses these for all routes by checking
`direction == 'outbound'`. When an A1 bus at Bristol Airport triggers
`is_near_major_stop()`, the function compares it to Route 72 coordinates 12 km
away, returns `is_near = False` for every stop, and suppresses crowd detection
entirely. The system silently assigns zero crowd to every A1 position.

**Why it happens:**
The module-level constants predate the data model's route-aware design. When
`is_near_major_stop()` was written, `direction` was a sufficient discriminant
because there was only one route.

**Evidence in codebase:**
- `server/app.py` lines 75–88: Temple Meads (51.449, -2.583), Frenchay Campus
  (51.500, -2.546) — all Route 72 stops
- `server/app.py` line 522: `major_stops = MAJOR_STOPS_OUTBOUND if direction == 'outbound' else MAJOR_STOPS_INBOUND` — no route discriminant
- `server/app.py` line 1301: called as `is_near_major_stop(bus_lat, bus_lng, route.direction)` — passes direction only, not route

**Consequences:**
Crowd detection is permanently inactive for A1, degrading passenger count accuracy.
Worse, if a Route 72 bus and an A1 bus share the same `direction` value, an A1 bus
near Temple Meads (e.g., if the A1 passes through Bristol centre) gets Route 72 crowd
logic applied, corrupting counts.

**Prevention:**
Change `is_near_major_stop(lat, lng, direction)` to `is_near_major_stop(lat, lng, route)`.
Move stop coordinates into a per-route data structure (dict keyed by route name, or
loaded from `RouteStop` table), so A1 major stops are looked up separately.

**Warning signs:**
- All A1 buses show `passenger_count: 0` in logs regardless of YOLO output
- "near major stop" log messages never appear for A1 route
- Route 72 crowd detection continues working, masking the silent A1 failure

**Phase that must address this:** Phase 1 (Fusion Engine), alongside MAJOR_STOPS
extraction. Easy to miss because it does not produce an error — only a silent zero.

---

### Pitfall 3: GTFS route_short_name Collision — "A1" May Not Be the Unique Key

**What goes wrong:**
`get_trip_candidates()` looks up routes by `route_short_name` (line 276:
`routes_by_short_name.get(route_name)`). The `itm_south_west_gtfs.zip` covers the
entire South West region, not just Bristol. The short name "A1" is used by multiple
operators and services in that region (e.g., Weston-super-Mare, Bath, Somerset
routes may have their own A1 variants). If two GTFS routes share the short name "A1",
`matching_routes` returns both, and trip candidates from the wrong service enter
the schedule-matching algorithm. This produces schedule times that are geographically
wrong (a stop sequence from Somerset being applied to an Airport Flyer bus near
Filton).

**Why it happens:**
Route 72 is a Bristol-specific number with minimal collision risk in the South West
GTFS feed. A1 is a common designation across operators. The current disambiguation
relies entirely on `origin_name` / `destination_name` fuzzy matching
(`names_match()`), which is a substring check with no geographic validation.

**Evidence in codebase:**
- `server/gtfs_parser.py` lines 276–280: no agency_id or operator filter in
  `matching_routes`
- `server/gtfs_parser.py` lines 303–309: fallback to `fallback_payloads` if no
  origin/destination name match — meaning even wrong-operator trips are returned
  when name matching fails
- `server/extract_bristol_route72.py` line 25: Route 72 extraction filters by
  `route_short_name == '72'` without agency filter — same latent bug, lower
  collision risk

**Consequences:**
Schedule-only predictions show incorrect stop sequence. XGBoost ETA is trained on
Route 72 features; wrong stop sequences produce nonsense inputs. Trip plausibility
check (`is_position_plausible_for_timetable`) rejects valid A1 buses as implausible
because they are being compared to a Somerset schedule.

**Prevention:**
Verify using `extract_bristol_route72.py`-style investigation before assuming
GTFS is collision-free. During GTFS loader step, filter by agency_id (First Bristol
= FBRI equivalent in GTFS; agency name will be "First Bristol" or similar). Pass
`agency_id` as a filter parameter to `get_trip_candidates()` alongside
`route_short_name`. Log how many distinct agencies produce trips for "A1" so
the collision count is visible before any route goes live.

**Warning signs:**
- A1 trip candidates include stops outside Bristol (e.g., stops in Somerset)
- `is_position_plausible_for_timetable` logs "Rejecting implausible live bus" on
  every A1 cycle
- Schedule times in API response are hours off from actual Airport Flyer timetable

**Phase that must address this:** Phase 1 (GTFS extraction for A1), before
`gtfs_loader.py` is run for A1. Cheap to fix when discovered early; expensive if
discovered after XGBoost retraining.

---

### Pitfall 4: BODS_OPERATOR_ALLOWLIST Capped at 2 Operators — Brittle for A1

**What goes wrong:**
Line 65–66 of `app.py` hard-caps the operator allowlist at 2 entries:
`tuple(dict.fromkeys(_operator_allowlist))[:2]`. The A1 Airport Flyer is operated
by First Bristol (FBRI), the same operator as Route 72, so the immediate A1
expansion is safe. However, if A1 is actually operated by a different entity
(e.g., National Express or a Bristol Airport shuttle operator using a different
BODS operator code), it would be silently filtered out at the operator filter step
(line 714–718 of `app.py`) with no error — just "No vehicles matched operators".

**Why it happens:**
The 2-operator cap is an undocumented design decision (flagged in CONCERNS.md line
121) with no rationale. The BODS operator code for A1 was assumed to be FBRI/FBRA
without verification against the BODS feed.

**Evidence in codebase:**
- `server/app.py` line 66: `[:2]` truncation
- `server/app.py` line 70: comment says "First Bristol = FBRI" — no mention of A1
- `CONCERNS.md` line 121: notes the 2-operator limit is "not documented"

**Consequences:**
A1 returns zero vehicles from BODS not because there are no buses, but because the
operator code filter drops them. The fallback schedule-only path activates
permanently with no diagnostic that the operator code is wrong.

**Prevention:**
Before implementation, query BODS with no `lineRef` and no `operatorRef`, filter
results to buses with `destination` matching "Airport" to find the actual operator
code used for A1 vehicles. Document the operator code explicitly. Remove the `:2`
cap and replace with a per-route operator config.

**Warning signs:**
- A1 buses appear in a raw BODS dump but not in filtered app output
- Logs show "No vehicles matched operators FBRI, FBRA" for A1 route
- A1 consistently falls to schedule-only with no live data despite BODS API working

**Phase that must address this:** Phase 1 discovery/data audit, before any A1
Fusion Engine work begins.

---

### Pitfall 5: XGBoost Model Trained on Route 72 Features — Applied to A1 Without Retraining

**What goes wrong:**
`xgboost_eta_model.joblib` was trained on Route 72 data (total_stops, route
geometry, haversine distances to a Temple Meads → Frenchay route). Applying this
model to A1 (different total_stops, different geometry, different stop spacing,
motorway section on A38 with different speed profiles) produces ETAs that are
statistically extrapolating far outside the training distribution.

**Why it happens:**
The ETA fallback chain (`resolve_live_eta()`) silently uses the loaded model for
any route without checking `route_id` against the model's training provenance.
There is no model metadata recording which routes it was trained on.

**Evidence in codebase:**
- `server/app.py` line 55: `ETA_MODEL_PATH` points to a single `.joblib` file —
  no per-route model files
- `CONCERNS.md` lines 79–82: "Users don't know if ETA is model-based,
  traffic-aware, or just straight-line distance. Model training effort might be
  wasted if always falling back."
- `server/train_xgboost.py` exists — training script is route-specific, not
  parameterised by route

**Consequences:**
A1 ETA shown to users is confidently wrong rather than falling back to a schedule
baseline. The XGBoost model may produce negative ETAs or wildly inflated values for
the Airport Flyer because motorway segments have no analogue in Route 72 training
data.

**Prevention:**
For the A1 milestone, do not enable XGBoost for A1. Log clearly in
`resolve_live_eta()` which model path is used and for which route. Treat A1 as
"formula/schedule-only ETA" initially and generate A1 synthetic training data
(`generate_synthetic_data.py`) before retraining a new model file (or a
multi-route model with a route feature column). Name model files per-route:
`xgboost_eta_model_route72.joblib`, `xgboost_eta_model_a1.joblib`.

**Warning signs:**
- A1 ETAs are negative or exceed 120 minutes
- A1 ETAs do not change meaningfully as the bus progresses along the route
- No A1-specific training data in `generate_synthetic_data.py` output

**Phase that must address this:** Phase 2 (ETA quality for A1). Phase 1 should
explicitly gate XGBoost off for A1 routes until retraining completes.

---

## Moderate Pitfalls

---

### Pitfall 6: Fusion Engine Logs Are Interleaved — Multi-Route Debugging Becomes Unreadable

**What goes wrong:**
The Fusion Engine loops over all routes in sequence. Each route logs with `[Fusion]`
prefix but no route identifier in every line (only in the header line "=== Route 72
(outbound) ==="). With two routes and two directions each (four Fusion sub-cycles
per 10 s tick), log lines from different routes are interleaved. A BODS fetch
warning for A1 appears between two Route 72 processing lines.

**Evidence in codebase:**
- `server/app.py` line 1253: `logger.info(f"\n[Fusion] === Route {route.route_name}...")` — separator, but individual steps on lines 1291–1294 use no route ID
- `CONCERNS.md` lines 220–224: explicitly flags this: "Multi-route logs are interleaved."

**Prevention:**
Add `route_id` and `route_name` as a prefix to every log line inside the per-route
Fusion sub-cycle. Python `logging.LoggerAdapter` with `{"route": route.route_name}`
is the lowest-friction fix without restructuring. This is a prerequisite for
diagnosing any of the other pitfalls above.

**Warning signs:**
- Cannot determine from logs which route a BODS warning belongs to
- A1 and Route 72 "Processing Bus" lines appear mixed in single log tail output

**Phase that must address this:** Phase 1 (Fusion Engine), first task, before any
A1 data flows through the system.

---

### Pitfall 7: `gtfs_loader.py` Deletes All Stops and RouteStops Before Reloading

**What goes wrong:**
Lines 24–27 of `gtfs_loader.py`:
```python
RouteStop.query.delete()
Stop.query.delete()
db.session.commit()
```
This is a destructive truncate of all stops for all routes before reloading from
GTFS. If `gtfs_loader.py` is rerun to add A1 stops, all Route 72 RouteStop
associations are dropped first. If the GTFS lookup for Route 72 then fails (e.g.,
the zip was updated and the trip selection finds no candidates), Route 72 loses its
stops permanently until the loader runs again successfully.

**Why it happens:**
Designed as a one-time seed tool for Route 72. The delete-all pattern avoids
duplicate stop inserts but is unsafe in a multi-route context.

**Evidence in codebase:**
- `server/gtfs_loader.py` lines 24–27: unconditional delete before insert
- `server/seed.py` line 36: `db.drop_all()` — even more destructive, same pattern

**Prevention:**
Refactor `gtfs_loader.py` to accept a `--route` argument and delete/reload only
the stops for that route. Use `RouteStop.query.filter_by(route_id=X).delete()` and
upsert stops rather than truncating global tables. Add a dry-run mode that prints
what would be loaded without writing.

**Warning signs:**
- After running `gtfs_loader.py` for A1, Route 72 stops count goes to 0
- `/api/routes/<route_id>/stops` returns empty for Route 72 after A1 onboarding
- `calculate_stop_predictions()` returns empty arrays for Route 72 post-loader run

**Phase that must address this:** Phase 1 (data seeding for A1), before the first
`gtfs_loader.py` run targeting A1.

---

### Pitfall 8: Direction Matching by String Substring Fails for A1's Destination Names

**What goes wrong:**
`fetch_all_buses_for_route()` filters vehicles by direction using:
```python
if (direction_lower in vehicle_direction or
    direction_lower in destination):
    matching_vehicles.append(v)
```
Route 72 uses "outbound" / "inbound" as direction values and the BODS feed
returns `DirectionRef` values that include those substrings. A1 uses
"outbound" (Bristol → Airport) and "inbound" (Airport → Bristol), but BODS
`DestinationName` for A1 outbound buses is "Bristol Airport" — which does not
contain "outbound". If `DirectionRef` is absent or inconsistent in the A1 feed,
all A1 buses fall through the direction filter into the fallback "use all vehicles"
path (line 748), assigning the same bus to both outbound and inbound routes.

**Evidence in codebase:**
- `server/app.py` lines 742–749: fallback on direction mismatch silently uses all
  vehicles rather than returning empty
- Route 72 direction values verified against Bristol BODS data; A1 direction
  values unverified

**Prevention:**
Verify actual BODS `DirectionRef` values for A1 vehicles before implementing
direction assignment. Add a configurable per-route direction map (e.g.,
`{"outbound": ["outbound", "airport"], "inbound": ["inbound", "bristol"]}`).
Log clearly when the fallback path is taken and which vehicles were affected.

**Warning signs:**
- Same vehicle_id appears in both outbound and inbound route logs
- A1 inbound and outbound routes always show the same bus position
- BODS direction filter fallback warning triggers on every A1 cycle

**Phase that must address this:** Phase 1 (BODS integration for A1), during
live data testing.

---

### Pitfall 9: `_latest_bus_metadata` Global Dict Grows Unbounded with Multiple Routes

**What goes wrong:**
`_latest_bus_metadata` is a global dict keyed by `vehicle_id` that stores operator
and route_id for each seen vehicle. With one route, the dict contains at most a
handful of entries. With multiple routes and multiple operators, every vehicle ever
seen accumulates an entry that is never evicted (no TTL, no max-size). Over days of
operation, the dict can contain thousands of stale vehicle IDs consuming memory and
slowing lookups.

**Evidence in codebase:**
- `server/app.py` lines 93–96: `_latest_bus_metadata = {}` — no eviction logic
- `server/app.py` line 1285: always writes, never deletes
- `CONCERNS.md` lines 38–40: flags the thread-safety race condition but not the
  unbounded growth

**Prevention:**
Use a bounded LRU cache (Python `functools.lru_cache` or `cachetools.TTLCache`
with a 30-minute TTL) instead of a plain dict. Alternatively, clear entries older
than `LIVE_DATA_MAX_AGE_SECONDS * 3` at the end of each Fusion cycle.

**Warning signs:**
- `len(_latest_bus_metadata)` grows in logs over hours without shrinking
- Memory usage trends upward over multi-day deployments
- Stale vehicle_ids from days ago appear in route metadata lookups

**Phase that must address this:** Phase 1 (Fusion Engine cleanup), low urgency for
2-route MVP but cheap to fix while touching the global state code.

---

### Pitfall 10: Frontend `selectedRouteId` Defaults to First Route — Map Viewport Does Not Move

**What goes wrong:**
When the route selector changes from Route 72 to A1, the Leaflet map stays
centered on Bristol city centre (where Route 72 runs). The A1 route goes south
to Bristol Airport. The initial map center and zoom level are hardcoded to the
Route 72 corridor. A user selecting A1 sees an empty map with the route polyline
partially off-screen until they manually pan.

**Evidence in codebase:**
- `client/src/App.jsx` line 177: `setSelectedRouteId(data[0].id)` — auto-selects
  first route
- No `flyTo` or `setView` call on route selection change in App.jsx (confirmed
  by absence of `flyTo` / `setView` in grep results)
- Leaflet `MapContainer` initial center is set once and not programmatically
  updated on route switch

**Prevention:**
On route selection change, call `map.flyTo([route.origin_lat, route.origin_lng], zoom)`
using the React-Leaflet `useMap()` hook or an imperative map ref. Derive zoom from
the route's bounding box (origin + destination coordinates already in the Route
model). A1 spans ~13 km; zoom 12 fits both endpoints.

**Warning signs:**
- Switching to A1 in the selector shows no buses or polyline on the visible map
- Users report needing to zoom out to find A1 buses
- Route 72 still visible in background when A1 is selected

**Phase that must address this:** Phase 2 (Frontend route selector), as part of
the route switch UX.

---

## Minor Pitfalls

---

### Pitfall 11: `bods_parser.py` Test Harness Hardcodes `line_ref='72'`

**What goes wrong:**
The `if __name__ == "__main__":` block in `bods_parser.py` (line 155) calls
`fetch_bods_vehicles(BODS_API_KEY, line_ref='72')`. Running `python bods_parser.py`
to test A1 connectivity requires modifying the file, which is easy to accidentally
commit with the wrong value.

**Prevention:**
Replace with `sys.argv[1]` or an environment variable:
`line_ref = os.getenv("TEST_LINE_REF", "72")`. Takes 5 minutes to fix and prevents
incorrect test assumptions about BODS connectivity for A1.

**Phase that must address this:** Phase 1 (early A1 data validation), before first
BODS live test for A1.

---

### Pitfall 12: `seed.py` Title Block Claims "Populates Route 72" — No A1 Path Exists

**What goes wrong:**
`seed.py` loads `bristol_route72_real.json` exclusively. There is no equivalent
`bristol_a1_real.json` or parametric seed path. If the A1 seed is added to `seed.py`
as a second block and `seed.py` is accidentally run, `db.drop_all()` destroys
both routes. The more common failure is that no A1 seed path exists and the route
is inserted through a different mechanism (ad-hoc script, manual SQL), creating
an inconsistent state that is hard to reproduce.

**Prevention:**
Create a `seed_a1.py` (or extend `seed.py` with a `--routes` argument) that
explicitly does NOT call `db.drop_all()` and instead uses upsert semantics. Keep the
destructive `seed.py` for full-reset scenarios only. Require explicit flag
(`--destroy`) to trigger drop_all.

**Phase that must address this:** Phase 1 (database seeding for A1), before first
A1 route creation.

---

### Pitfall 13: Stop Popup Requires Stop-Level ETA Data That Does Not Exist Yet

**What goes wrong:**
The PROJECT.md requirement "Stop popup on map tap showing next arrivals and delay
status" implies per-stop ETA data available in the frontend. The current
`/api/routes/<route_id>/predictions` endpoint returns stop-level predictions
including `predicted_arrival` and `delay_minutes` per stop. However, the frontend
does not currently render stop popups — only the bus marker popup exists. Building
the popup requires stop markers to be interactive Leaflet elements rather than the
current non-interactive `stopIcon` markers.

**Prevention:**
This is a feature gap, not a bug — but it is easy to build the wrong thing.
The stop predictions data shape is already correct on the backend. The frontend
work is to convert `stopIcon` markers to `<Marker>` components with `<Popup>`
children that read from `routePredictions.stops`. Do not add a new API endpoint;
the data is already returned by `/predictions`.

**Phase that must address this:** Phase 2 (Frontend), stop popup feature.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| A1 GTFS extraction | GTFS route_short_name collision (Pitfall 3) | Filter by agency_id, log candidate count before committing |
| A1 BODS live data | Operator code unknown for A1 (Pitfall 4) | Raw BODS dump first to find actual operator code |
| BODS polling scale | Per-route request multiplication (Pitfall 1) | Bulk fetch + local fan-out before adding A1 routes to DB |
| Fusion Engine multi-route | Route 72 MAJOR_STOPS applied to A1 (Pitfall 2) | Make `is_near_major_stop` route-aware before A1 goes live |
| ETA for A1 | XGBoost trained on Route 72 data only (Pitfall 5) | Gate XGBoost off for A1; use formula fallback; log ETA method |
| GTFS loader rerun | Destructive stop deletion (Pitfall 7) | Add --route filter to gtfs_loader.py before rerunning |
| A1 direction matching | Destination-based direction heuristic fails (Pitfall 8) | Verify actual BODS DirectionRef values for A1 before coding |
| Frontend route switch | Map viewport stays on Route 72 (Pitfall 10) | Add flyTo on route change, derive bounds from route model |
| Debugging multi-route | Interleaved Fusion logs (Pitfall 6) | Add route_name prefix to all per-cycle log lines first |

---

## Sources

All findings grounded in direct code analysis of:
- `C:/Users/rajib/Downloads/Transight2/server/app.py` (lines cited above)
- `C:/Users/rajib/Downloads/Transight2/server/bods_parser.py`
- `C:/Users/rajib/Downloads/Transight2/server/gtfs_parser.py`
- `C:/Users/rajib/Downloads/Transight2/server/seed.py`
- `C:/Users/rajib/Downloads/Transight2/server/gtfs_loader.py`
- `C:/Users/rajib/Downloads/Transight2/client/src/App.jsx`
- `.planning/codebase/CONCERNS.md` (existing concern audit, dated 2025-02-15)
- `.planning/PROJECT.md` (active requirements)

BODS SIRI-VM rate limit behavior: MEDIUM confidence (known public API behavior,
not verified against current BODS documentation due to WebSearch unavailability).
All other pitfalls: HIGH confidence (directly observable in code).
