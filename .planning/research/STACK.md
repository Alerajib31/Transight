# Technology Stack

**Project:** Transight AI — Multi-Route Expansion (Route 72 + A1 Airport Flyer)
**Researched:** 2026-04-02
**Scope:** Stack additions and patterns for scaling from single-route to multi-route. Does NOT re-document the existing stack (see `.planning/codebase/STACK.md`).

---

## What Already Works — Do Not Change

The existing stack (Flask 3, React 19, SQLAlchemy 2, PostgreSQL, Leaflet 1.9.4, react-leaflet 5, Tailwind v4) is already appropriate and operational. The data model already supports multiple routes via `Route`/`RouteStop`/`Stop` tables. The Fusion Engine already loops over `Route.query.all()`. The BODS parser already accepts `line_ref` and `operator_ref` parameters.

None of these need replacing or augmenting with new dependencies. The architecture only needs configuration changes, data loading, and frontend layout work.

---

## GTFS Multi-Route Extraction

### Approach: Use the existing `gtfs_parser.py` unchanged — confidence HIGH

**What exists:** `gtfs_parser.py` already extracts routes by `route_short_name` via the `routes_by_short_name` dict. `get_stops_for_route(gtfs_data, route_short_name, direction)` takes any short name — it is not hardcoded to "72". `gtfs_loader.py` already iterates `Route.query.all()` and calls `get_stops_for_route` for each.

**What this means for A1:** No new library is needed. The pattern is:

1. Look up A1 in `itm_south_west_gtfs.zip` using the existing `routes_by_short_name` dict. The route short name may be `"A1"`, `"A1X"`, or an agency-specific variant — this must be verified by inspecting the GTFS file.
2. Insert two `Route` rows into the database (outbound: city → airport; inbound: airport → city) with the correct `route_name` matching the GTFS short name.
3. Run `python server/gtfs_loader.py ../itm_south_west_gtfs.zip` — it will pick up the new routes automatically.

**Library verdict:** No new library. `zipfile` + `csv.DictReader` (already used) is sufficient and zero-dependency.

**Why not `gtfs-kit` or `gtfs_functions`:** These add pandas as a transitive dependency (>50 MB), require a separate install step, and provide features (shape geometry, feed validation, GTFS-RT) that this project does not use. The custom parser already handles calendar exceptions and `>24h` GTFS time rollovers correctly.

**Risk to flag:** A1 Airport Flyer may use a non-obvious `route_short_name` in the South West GTFS feed (e.g., some operators use `"A1 AIRPORT"` or a numeric agency ID). The GTFS file must be inspected before seeding. Use:

```python
import zipfile, csv, io
with zipfile.ZipFile("itm_south_west_gtfs.zip") as zf:
    with zf.open("routes.txt") as f:
        for row in csv.DictReader(io.TextIOWrapper(f)):
            if "a1" in row["route_short_name"].lower() or "airport" in row["route_long_name"].lower():
                print(row)
```

Run this before any seeding to confirm the exact `route_short_name`. **Confidence: HIGH** (GTFS spec is stable; the parser handles all standard fields correctly).

---

## BODS Multi-Route Filtering

### Approach: Call `fetch_bods_vehicles` once per route with per-route `line_ref` — confidence HIGH

**What exists:** `fetch_bods_vehicles(api_key, line_ref, operator_ref, bounding_box)` in `bods_parser.py` already supports per-call `line_ref`. The Fusion Engine already calls `fetch_all_buses_for_route(route)` which passes `route.route_name` as the `line_ref`. Adding A1 requires inserting a `Route` row with `route_name="A1"` (or whatever the BODS `LineRef` value is for the A1).

**What this means for A1:**
- BODS `LineRef` for the A1 Airport Flyer is likely `"A1"` under operator First Bristol (`FBRI`). The existing `BODS_OPERATOR_ALLOWLIST` already includes `FBRI`.
- The Fusion Engine will automatically process A1 vehicles in its next cycle once the route row exists.
- No API changes. No new HTTP client. No new library.

**One genuine gap — the `MAJOR_STOPS` lists are hardcoded to Route 72 stops:**

```python
# server/app.py lines 75–88
MAJOR_STOPS_OUTBOUND = [
    ("Temple Meads Stn", 51.44898, -2.58262),
    ...
    ("Frenchay Campus", 51.50019, -2.54622),
]
```

`is_near_major_stop()` uses these lists regardless of which route the bus is on. For A1, this means YOLO crowd detection will fire when an A1 bus passes near Temple Meads (which it does — the city terminus is the Public Transport Interchange, close to Temple Meads) but will not fire near the Airport.

**Fix pattern** (no new library, targeted refactor):
- Move `MAJOR_STOPS_OUTBOUND/INBOUND` from module-level constants into a dict keyed by route name, or derive them from `RouteStop` records at runtime.
- Pass `route.route_name` into `is_near_major_stop()` to select the right stop list.

**BODS `lineRef` vs GTFS `route_short_name` mismatch risk:** These values are sourced from different systems. Route 72's BODS `LineRef` matches its GTFS `route_short_name` exactly. For A1 this is likely true but should be verified by running a BODS query with no `lineRef` filter and inspecting the XML `LineRef` field for Airport Flyer vehicles. **Confidence: MEDIUM** (pattern is correct; the specific A1 `LineRef` string must be confirmed empirically).

---

## Mobile-First Responsive UI with Leaflet

### Approach: CSS Grid layout switch + CSS-only bottom sheet — no new libraries — confidence HIGH

**What exists:** The current layout uses `grid grid-cols-1 lg:grid-cols-3` in `App.jsx`. On mobile this stacks columns vertically, placing the info panel above the map. The map has no explicit height on mobile, which causes it to render with zero or near-zero height unless given an explicit `vh`-based height.

**Target layout (from PROJECT.md requirements):**
- Mobile: full-screen map with bottom sheet for route info
- Desktop: side-by-side map and info panels

**Implementation pattern — no new library needed:**

The standard 2025 transit app mobile layout (used by Citymapper, Google Maps, and UK-specific apps like Transport for London) is:

```
Mobile (< lg breakpoint):
  ┌─────────────────────┐
  │   Map (100dvh)      │
  │                     │
  │                     │
  └─────────────────────┘
  ┌─────────────────────┐  ← bottom sheet, translates up over map
  │ Route info / stops  │
  └─────────────────────┘

Desktop (>= lg breakpoint):
  ┌──────────┬──────────────────┐
  │ Left     │   Map            │
  │ panel    │   (full height)  │
  └──────────┴──────────────────┘
```

**CSS approach using Tailwind v4 tokens already in `index.css`:**

The bottom sheet is a fixed-position div that slides up via `transform: translateY(...)`. No external library is needed — the Headless UI or Radix bottom-sheet libraries add 20-80 KB and are designed for complex modal behavior, not a simple slide-up panel. The project's constraint (Tailwind v4, no new config files) makes a CSS-only implementation cleaner.

```jsx
// Pseudocode pattern — exact implementation in App.jsx
<div className="fixed inset-0 lg:relative lg:inset-auto">
  {/* Map fills all available space */}
  <MapContainer style={{ height: "100dvh" }} ... />
</div>

<div className={`
  fixed bottom-0 left-0 right-0 z-[400]
  bg-bg-card border-t border-border rounded-t-2xl
  transition-transform duration-300
  lg:static lg:transform-none lg:rounded-none lg:border-0
  ${sheetOpen ? "translate-y-0" : "translate-y-[calc(100%-4rem)]"}
`}>
  {/* Sheet handle */}
  <div className="flex justify-center pt-3 pb-2 cursor-pointer"
       onClick={() => setSheetOpen(o => !o)}>
    <div className="w-8 h-1 rounded-full bg-border" />
  </div>
  {/* Route info content */}
  ...
</div>
```

`100dvh` (dynamic viewport height) is the correct unit for mobile — it accounts for browser chrome collapsing on scroll, which `100vh` does not. It is supported in all modern mobile browsers (Safari 15.4+, Chrome 108+, Firefox 101+). **Confidence: HIGH.**

**Leaflet-specific mobile consideration:** Leaflet's default touch handling works correctly on mobile without plugins. The `MapContainer`'s `scrollWheelZoom` should be set to `false` on mobile to prevent scroll capture hijacking the page. The existing `stopIcon` dot markers (10×10px) are too small for finger taps; the stop tap target needs to be at least 44×44px per WCAG 2.5.5. This means either increasing the `iconSize` or using a larger transparent hit area in the `DivIcon` HTML.

**Route selector on mobile:** The existing `<select>` dropdown works on mobile. The label is already hidden on small screens (`hidden sm:inline`). No change needed here.

**What NOT to use:**
- `react-spring` or `framer-motion` for bottom sheet animation — animation complexity is not justified. CSS `transition-transform` is sufficient and has zero bundle cost.
- `@radix-ui/react-dialog` or `vaul` (drawer library) — these are designed for full dialog semantics. The route info panel is persistent context, not a dialog.
- Leaflet plugins (`leaflet.markercluster`, `leaflet-routing-machine`) — not needed for two routes and small stop counts.

---

## Supporting Libraries — No New Additions Recommended

| Category | Decision | Rationale |
|----------|----------|-----------|
| GTFS parsing | No new library | Existing pure-Python parser handles all required GTFS fields |
| BODS fetching | No new library | `requests` + `xml.etree.ElementTree` already sufficient |
| Bottom sheet / mobile UI | No new library | CSS-only via Tailwind v4 classes; avoids bundle bloat |
| Route color coding | No new library | CSS custom properties already in `index.css`; add `--color-route-72` and `--color-route-a1` |
| Map layer management | No new library | `react-leaflet` `LayersControl` is available in v5 if needed; defer unless routes need toggle |

---

## Configuration Additions (Environment Variables)

The current `BODS_OPERATOR_ALLOWLIST` already covers `FBRI,FBRA` which operates both Route 72 and the A1 Airport Flyer. No new environment variables are required.

One optional addition for clarity:

```bash
# .env.example addition
GTFS_ROUTE_NAMES=72,A1   # comma-separated list of GTFS route_short_name values to load
```

This is not strictly necessary — routes are driven by DB rows, not env config — but makes the seeding intent explicit.

---

## Stack Delta Summary

| Area | Current | Change | Confidence |
|------|---------|--------|------------|
| GTFS extraction | `gtfs_parser.py` + stdlib | No library change; verify A1 `route_short_name` in GTFS file | HIGH |
| BODS filtering | Per-route `line_ref` in `fetch_bods_vehicles` | No library change; extend `MAJOR_STOPS` dict for A1 | MEDIUM |
| Mobile layout | `grid grid-cols-1 lg:grid-cols-3` | CSS-only bottom sheet via Tailwind v4; `100dvh` map height | HIGH |
| Leaflet touch | Existing Leaflet 1.9.4 | Increase stop icon tap targets to 44px; set `scrollWheelZoom={false}` on mobile | HIGH |
| Route coloring | Single blue accent | Add per-route color tokens in `index.css` CSS variables | HIGH |

**No new npm packages. No new pip packages. No schema migrations.** The expansion is configuration + data + layout work against the existing stack.

---

## Sources

- Codebase analysis: `server/bods_parser.py`, `server/gtfs_parser.py`, `server/app.py` (Fusion Engine loop lines 1235–1401), `server/models.py`, `client/src/App.jsx`, `client/src/index.css`
- GTFS specification (General Transit Feed Specification, stable spec): https://gtfs.org/documentation/schedule/reference/
- BODS API (Bus Open Data Service SIRI-VM): https://developers.data.bus.dft.gov.uk/
- Tailwind CSS v4 (CSS-first configuration): https://tailwindcss.com/docs/v4-beta
- `100dvh` mobile viewport unit: MDN Web Docs, `dvh` CSS unit (supported Safari 15.4+, Chrome 108+)
- WCAG 2.5.5 Target Size: minimum 44×44px for touch targets

*Confidence ratings: HIGH = directly verified from codebase or stable specs. MEDIUM = correct pattern confirmed, specific value (A1 LineRef/GTFS name) requires empirical verification.*
