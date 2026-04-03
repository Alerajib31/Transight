# Phase 2: Multi-Route Frontend - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the visible multi-route experience: route selector dropdown, stop popups with arrival/delay info, responsive layouts (mobile bottom sheet + desktop side panel), delay indicators, and per-route ETA quality. The backend is ready — 4 routes in DB, stops loaded, Fusion Engine route-aware.

</domain>

<decisions>
## Implementation Decisions

### Route Selector & Navigation
- Route selector is a dropdown in the header (already exists at line 429-439 of App.jsx)
- Dropdown already shows all routes from /api/routes — works with 4 routes out of the box
- Map should flyTo the selected route's area when switching routes (UI-05)
- Route path polyline and origin/destination markers already update on route change

### Stop Popup Design
- Tapping a stop marker shows a popup with next arrival time and delay status (UI-02)
- Stop popups already exist (App.jsx lines 666-708) with arrival, status, service, delay
- Enhance with a clear delay badge: green "On Time", amber "X min late", blue "X min early"
- Single next-bus focus (not multiple upcoming — out of scope per PROJECT.md)

### Delay Indicators
- Per-stop delay indicator computed from predicted vs scheduled arrival (LIVE-03)
- Display as colored badge: On Time (green), Late (red/amber), Early (blue)
- Use existing routePredictions.stops[].delay_text and predicted_arrival fields
- Backend already computes delay — frontend needs to present it more visually

### Mobile Layout
- Mobile-first: full-screen map with bottom sheet for route info and stop details (UI-03)
- Bottom sheet slides up from bottom, shows route card + stop list + bus details
- Map takes 100vh on mobile, info panel overlays as draggable sheet
- Breakpoint: below lg (1024px) = mobile layout, above = desktop

### Desktop Layout
- Desktop: map and info panel side-by-side (UI-04) — already the pattern at lg: breakpoint
- Current layout is close: 1-col cards + 2-col map at lg:grid-cols-3
- Refine spacing and ensure no overlap or layout breakage at all widths

### UI Polish
- Evolve current Transight theme — improve typography, spacing, card design (UI-06)
- Keep existing color tokens (accent blue, success green, danger red, warning amber)
- Improve card hierarchy and visual weight
- Keep Inter font, adjust weights and sizes for better readability
- No dark/light theme toggle redesign — just polish what exists

### Claude's Discretion
- Exact bottom sheet implementation approach (CSS-only vs lightweight library)
- Card layout reorganization for mobile vs desktop
- Animation and transition details
- Stop list ordering and grouping in bottom sheet
- Map zoom level per route

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `App.jsx` (729 lines) — route selector, map, bus markers, stop popups, dashboard cards all exist
- `HistoricalTrends.jsx` — SVG trend charts component (keep as-is)
- `index.css` — complete Tailwind v4 theme with dark/light mode tokens
- Leaflet icon helpers: `createBusIcon()`, `originIcon`, `destIcon`, `stopIcon`
- Bus helpers: `getBusKey()`, `getBusLabel()`, `getBusMarkerColors()`
- Fetch hooks: `fetchStatus`, `fetchStops`, `fetchHistory`, `fetchPredictions` with 10s polling

### Established Patterns
- Single App.jsx component with all state and rendering (monolith pattern)
- Tailwind utility classes inline in JSX
- Theme via `[data-theme]` CSS custom properties
- react-leaflet for map with DivIcon markers
- 10-second polling cadence for status + predictions
- `lg:grid-cols-3` breakpoint for desktop layout

### Integration Points
- `/api/routes` → route list (already fetched on mount)
- `/api/status/{id}` → bus positions + ETA (polled every 10s)
- `/api/routes/{id}/stops` → stop list (fetched on route change)
- `/api/routes/{id}/predictions` → per-stop arrival/delay (polled every 10s)
- `/api/routes/{id}/history` → historical data (polled every 30s)
- `useMap()` hook from react-leaflet for flyTo on route change

</code_context>

<specifics>
## Specific Ideas

- User specifically requested "awesome modern UI impressive, highly responsive"
- User said "map-first" for mobile layout
- User said "popup with arrivals" for stop interaction
- User said "delay indicator" (on time / late / early) at each stop
- User said "keep current + polish" for UI style — evolution not redesign
- Stop names user mentioned for A1: Public Transport Interchange (Bay 4), Airport Tavern, Fox and Goose, Hobbs Lane

</specifics>

<deferred>
## Deferred Ideas

- Multiple upcoming bus arrivals per stop (v2 — UX-03)
- Full stop detail page with history/trends (v2 — UX-04)
- Animated bus markers with direction indicators (v2 — UX-01)
- PWA manifest for installable mobile experience (v2 — UX-02)

</deferred>
