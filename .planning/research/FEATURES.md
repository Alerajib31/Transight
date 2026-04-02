# Feature Landscape

**Domain:** Multi-route real-time transit prediction (Bristol bus, web dashboard)
**Researched:** 2026-04-02
**Confidence note:** WebSearch and WebFetch were unavailable. Findings derive from training knowledge of established transit apps (Google Maps Transit, Citymapper, Transit App, Moovit, TfL Go, Traveline) and the existing Transight codebase. Confidence levels reflect that source limitation.

---

## Table Stakes

Features users expect when opening a multi-route transit tracker. Missing any of these makes the product feel broken or unfinished.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Route selector (switch between 72 and A1) | Users cannot use a multi-route app without knowing which route they are viewing | Low | Dropdown is decided. Keep it simple: show route number + short name. Active route clearly highlighted. |
| Live bus marker on map, updated in real time | Users expect to see the bus moving; a static dot is the minimum credible live tracker | Low | Already exists for Route 72. Extend to A1. Each route should have a distinct marker colour to avoid confusion when both are visible. |
| ETA at terminus / end-of-line | "When does it arrive?" is the primary question for any transit user | Low | Already exists. Per-route label on dashboard card. |
| Delay status indicator (on-time / delayed / early) | Users need a single glance answer: is this bus running late? | Low | Colour badge: green = on time (< 2 min late), amber = slight delay (2–5 min), red = delayed (> 5 min). Threshold values should be configurable constants. |
| Stop-level arrival times for the active route | Users waiting at a specific stop need to know when the bus reaches their stop, not just the terminus | Medium | The `/api/routes/<route_id>/predictions` endpoint already returns per-stop data. The frontend must surface it. A stop list panel or map popup is the minimum viable UI. |
| Stop popup on map tap | Standard transit map pattern; users tap a stop to see next arrival and delay | Medium | Already required in PROJECT.md. Should show: stop name, scheduled time, predicted time, delay badge. Single next arrival only (PROJECT.md scope). |
| Directional awareness for A1 | A1 runs Bristol → Airport and Airport → Bristol; these are different services and users must not confuse them | Medium | Route selector or sub-selector must expose direction. Route 72 is single-direction currently; A1 adds this complexity. |
| Schedule fallback when no live data | Users who open the app when BODS feed is stale must still see something useful | Low | Already implemented in backend. Frontend should clearly label schedule-only vs live data with a "Last updated X min ago" or "Schedule only" badge. |
| Mobile-usable layout | Bristol airport travellers will primarily be on phones | High | Full-screen map with bottom sheet is decided. The bottom sheet must be dismissible, draggable to half-height and full-height states. |
| Desktop layout with side panel | Users monitoring at a desk (operators, planners) expect a side-by-side view | Medium | Map left, info panel right. Panel shows route selector, dashboard cards, stop list. |

---

## Differentiators

Features that distinguish Transight from a generic GTFS viewer or a static timetable page. Not expected at first glance, but meaningfully improve the experience once discovered.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Predicted arrival vs scheduled arrival, side by side | Most transit apps show only one or the other. Showing both lets users judge reliability directly | Low | Backend already computes both. UI just needs two columns: "Scheduled 14:32 / Predicted 14:35 (+3 min)". |
| Confidence or data-freshness indicator on predictions | XGBoost predictions are better than schedule alone; signalling this builds trust | Low | A small "(Live prediction)" vs "(Schedule estimate)" label per stop. Flag when prediction is > 2 minutes stale. |
| Crowd / occupancy indicator at major stops | Unique differentiator; not available in standard GTFS viewers | High | Already computed via YOLOv8 but not surfaced in UI. Surface as a low/medium/high badge on the stop popup for stops within crowd-detection radius. Keep it subtle — not the main message. |
| Historical reliability summary on dashboard | "Route 72 is on average 3 min late on weekday mornings" builds user trust and helps trip planning | Medium | Historical data already stored in BusLog. A rolling 7-day on-time % card on the dashboard requires a new aggregation query but no new data collection. |
| Per-stop delay propagation (downstream stops get updated ETAs) | Most apps show a single bus ETA. Showing how a current delay ripples through every remaining stop is more informative | Medium | Backend already computes this in the predictions endpoint. The frontend must render it as a stop-by-stop list with delay colour coding. |
| Live data badge showing last-update timestamp | Users trust live apps more when they can see the data is fresh | Low | Small "Updated X seconds ago" label. Already have polling cadence; just expose it in the UI. |

---

## Anti-Features

Features to deliberately NOT build in this milestone. Each has a concrete reason and a preferred alternative.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Multiple upcoming arrivals per stop | Requires significant backend complexity (tracking multiple vehicles per route per stop), adds visual clutter, and is out of PROJECT.md scope | Single next-bus focus. State clearly "Next bus" in the UI. Add a "and X more today" count only if trivially derived from existing schedule data. |
| Full stop detail page with history / trends | A dedicated page per stop implies navigation, deep-linking, and back-button UX — significant frontend rework for marginal user value at MVP scale | Stop popup is sufficient. If users request drill-down, add it in a future milestone. |
| Dark / light theme toggle | Tailwind v4 `index.css` tokens make this doable but it is styling work, not product work | Polish the existing light theme. Ship dark mode as a standalone future task. |
| Routes beyond 72 and A1 | Adding more routes before the multi-route architecture is validated risks shipping broken data or UI for routes with edge-case GTFS shapes | Prove the pattern with two routes. The database schema already supports N routes; adding route 3+ is configuration, not code. |
| Native mobile app | React PWA with responsive design covers mobile sufficiently for a transit dashboard. A native app requires an entirely different build/release pipeline | PWA / responsive web. Optionally add a `manifest.json` and service worker for offline basic caching if time permits — but that is a nice-to-have, not a requirement. |
| User accounts / favourites / notifications | Auth adds backend complexity, GDPR surface area, and email infrastructure. Not needed for a public monitoring dashboard | Keep endpoints public. If push notifications for a specific stop are wanted, that is a separate product feature with significant complexity. |
| Auto-routing / trip planner | "How do I get from X to Y?" is Google Maps territory. This app's value is deep prediction quality, not journey planning breadth | Focus on prediction accuracy for the routes you have, not breadth of routing. |
| Complex animated bus movement between polling cycles | Smooth animation between 10-second GPS pings requires dead-reckoning interpolation and adds rendering complexity | Simple marker jump on each poll update. Users accept this in transit apps. |

---

## Feature Dependencies

```
Route selector (dropdown) → Stop-level arrival list
  Reason: The stop list is meaningless without knowing which route is active.

Stop list (per route) → Stop popup on map tap
  Reason: The popup content (predicted time, delay) comes from the same predictions
  endpoint that feeds the stop list. Both must be wired before either is polished.

A1 route in database → A1 in Fusion Engine → A1 in API → A1 in route selector
  Reason: End-to-end dependency chain. UI work on A1 selection is wasted if the
  backend pipeline is not emitting BusLog rows for A1.

A1 directional support → A1 stop list accuracy
  Reason: Stops are direction-specific (outbound vs inbound sequence). If direction
  is not resolved, the stop list will show stops in wrong order or mix both directions.

Delay badge constants (thresholds) → Delay status indicator + Stop popup delay label
  Reason: Both UI elements share the same green/amber/red thresholds. Define once
  (backend config or frontend constants file), use everywhere.

Mobile bottom sheet → Stop popup on mobile
  Reason: On mobile the stop popup triggered by map tap should render in the bottom
  sheet, not as a floating Leaflet tooltip (too small on phones). Bottom sheet must
  exist before stop popup mobile UX is correct.
```

---

## MVP Recommendation

Prioritise in this order for the A1 milestone:

1. **A1 route in backend** (GTFS extraction, database seed, Fusion Engine cycle, API endpoints) — nothing else works without this.
2. **Route selector dropdown** (switch between 72 and A1 including direction) — core multi-route UX.
3. **Stop-level predictions panel** (list of stops with scheduled/predicted/delay for active route) — surfaces existing backend capability.
4. **Stop popup on map tap** (reuses predictions data, connects map to info panel) — mobile and desktop parity.
5. **Delay badge** (green/amber/red on dashboard card and stop popup) — single-glance status.
6. **Responsive layout** (mobile bottom sheet + desktop side panel) — makes the above features usable on phones.

Defer:
- Crowd occupancy badge: backend computes it but UI surfacing adds complexity; validate stop popup first.
- Historical reliability summary: new aggregation query; add only if backend work completes early.
- Live data freshness badge: low complexity, add as polish after core features are stable.

---

## Sources

- Training knowledge of Transit App, Citymapper, TfL Go, Google Maps Transit, Moovit — MEDIUM confidence (established patterns, well-documented in public UX writing, stable conventions unlikely to have changed materially)
- Existing Transight codebase (`server/app.py`, `server/models.py`, `client/src/App.jsx`) as observed in ARCHITECTURE.md — HIGH confidence
- PROJECT.md requirements and constraints — HIGH confidence
- WebSearch and WebFetch unavailable for this session; no external verification was possible
