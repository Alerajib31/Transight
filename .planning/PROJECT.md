# Transight AI

## What This Is

A real-time Bristol bus prediction platform for Bristol bus routes. Route 72 is live today, and the current milestone expands the product into a polished multi-route experience with the A1 Airport Flyer.

## Core Value

Accurate, real-time bus arrival predictions with delay indicators at every stop, proving the system scales beyond a single route.

## Requirements

### Validated

- [x] Route 72 live bus tracking via BODS
- [x] Fusion Engine background thread combining BODS, TomTom, YOLOv8, and GTFS
- [x] ETA prediction pipeline with graceful XGBoost fallback when a route-specific model is unavailable
- [x] Leaflet map with live bus markers and route geometry
- [x] Route/stop data model (`Route`, `Stop`, `RouteStop`, `BusLog`)
- [x] GTFS timetable loading and schedule matching
- [x] 10-second polling for live frontend updates
- [x] Dashboard cards and historical trends view
- [x] Multi-route backend foundation for Route 72 plus A1 in both directions
- [x] A1 route seeding, GTFS stop loading, and route-aware Fusion Engine processing
- [x] Bulk BODS fan-out, scoped GTFS loading, and route-aware major-stop detection

### Active

- [ ] Bus arrival times and delay indicators at each stop for all active routes
- [ ] Stop popup on map tap with a clear next-arrival and delay badge
- [ ] Route switch fly-to behavior so the map re-centers on the selected route
- [ ] Mobile-first responsive layout with a full-screen map and bottom sheet
- [ ] Desktop side-by-side layout refinement for map plus info panels
- [ ] Polished route selector, card hierarchy, and typography
- [ ] Human verification of the complete multi-route frontend on mobile and desktop

### Out of Scope

- Multiple upcoming bus arrivals per stop - single next-bus focus for now
- Full stop detail page with history and trends - popup is sufficient for v1
- Dark/light theme toggle - keep the current theme and polish it
- Additional routes beyond 72 and A1 - prove the multi-route pattern first
- Native mobile app - web-first responsive design is enough for v1
- User accounts or authentication - public dashboard

## Context

- Phase 1 backend foundation completed on 2026-04-02
- Phase 2 frontend planning completed on 2026-04-03 with 3 executable plans
- A1 routes for both directions are in the database and GTFS stop associations are loaded
- `.planning/ROADMAP.md` maps 13/13 v1 requirements across 2 phases
- `server/app.py` remains the main backend monolith for API routes, Fusion Engine, and ETA logic
- `client/src/App.jsx` remains the main frontend shell for route selection, polling, map, and cards
- `client/src/index.css` holds the Tailwind v4 theme tokens and styling layer

## Constraints

- **Tech stack**: Flask + React + PostgreSQL - no framework changes
- **Data sources**: BODS, TomTom, GTFS - same integrations as Route 72
- **Tailwind**: v4 with `index.css` theme tokens - no `tailwind.config.js`
- **Seed safety**: `seed.py` drops all tables - never run without explicit approval
- **API keys**: Graceful fallback when BODS or TomTom keys are unavailable

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| A1 stop data from GTFS first, manual supplement only if required | Reuse the existing Route 72 pipeline and reduce data drift | Done in Phase 1 |
| Route selector dropdown instead of tabs or a simultaneous multi-route map | Keep one clear route context at a time | Confirmed for Phase 2 |
| Polish the current theme instead of redesigning from scratch | Faster path to a strong, shippable UI | Confirmed for Phase 2 |
| Map-first mobile layout with a bottom sheet | Best fit for transit use on phones | Confirmed for Phase 2 |
| Gate XGBoost for A1 until route-specific training exists | Avoid misleading ETAs from a Route 72-only model | Done in Phase 1; route-specific training deferred |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if it drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-03 after Phase 2 planning*
