# Transight AI

## What This Is

A real-time Bristol bus prediction platform that shows live bus positions, arrival times, and delay status for Bristol bus routes. Currently tracks Route 72 (Temple Meads to UWE Frenchay). Expanding to multi-route support starting with the A1 Airport Flyer (Bristol city centre to Bristol Airport).

## Core Value

Accurate, real-time bus arrival predictions with delay indicators at every stop — proving the system scales beyond a single route.

## Requirements

### Validated

- ✓ Route 72 live bus tracking via BODS — existing
- ✓ Fusion Engine background thread (BODS + TomTom + YOLOv8 + GTFS) — existing
- ✓ ETA predictions with XGBoost model — existing
- ✓ Leaflet map with live bus markers — existing
- ✓ Route/stop data model (Route, Stop, RouteStop, BusLog) — existing
- ✓ TomTom traffic integration with OSRM/haversine fallback — existing
- ✓ GTFS timetable loading and schedule matching — existing
- ✓ 10-second polling for real-time updates — existing
- ✓ Dashboard cards with route metrics — existing
- ✓ Historical trends view — existing

### Active

- [ ] A1 Airport Flyer route with both directions (Bristol → Airport, Airport → Bristol)
- [ ] A1 stop data (GTFS extraction + manual supplement if needed)
- [ ] Full live tracking for A1 (BODS feed, TomTom, Fusion Engine predictions)
- [ ] Bus arrival times and delay indicators at each stop for all routes
- [ ] Stop popup on map tap showing next arrivals and delay status
- [ ] Route selector dropdown to switch between Route 72 and A1
- [ ] Modern, polished UI — evolve current Transight theme
- [ ] Mobile-first responsive design — full-screen map with bottom sheet for route info
- [ ] Desktop responsive layout — side-by-side map and info panels
- [ ] Multi-route Fusion Engine — process all active routes, not just one

### Out of Scope

- Multiple upcoming bus arrivals per stop — single next-bus focus for now
- Full stop detail page with history/trends — popup is sufficient for v1
- Dark/light theme toggle — keep current theme, just polish it
- Additional routes beyond 72 and A1 — prove multi-route first
- Native mobile app — web-first, responsive design covers mobile
- User accounts or authentication — public dashboard

## Context

- Existing codebase is a working Route 72 MVP with all data pipelines operational
- BODS API provides live SIRI-VM data for Bristol bus operators (First Bristol = FBRI)
- GTFS data from `itm_south_west_gtfs.zip` — A1 may be extractable from same file
- A1 Airport Flyer stops include: Public Transport Interchange (Bay 4), Airport Tavern, Fox and Goose, Hobbs Lane, and others
- Database schema already supports multiple routes via Route/Stop/RouteStop models
- `server/app.py` is the monolith (~1500+ lines) containing Flask routes, Fusion Engine, and ETA logic
- Frontend is a single `App.jsx` component with polling, map, and dashboard cards

## Constraints

- **Tech stack**: Flask + React + PostgreSQL — no framework changes
- **Data sources**: BODS, TomTom, GTFS — same integrations as Route 72
- **Tailwind**: v4 with `index.css` theme tokens — no `tailwind.config.js`
- **Seed safety**: `seed.py` drops all tables — never run without explicit approval
- **API keys**: Graceful fallback when BODS/TomTom keys unavailable

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| A1 stop data from GTFS first, manual supplement if needed | Same pipeline as Route 72, consistent approach | — Pending |
| Route selector dropdown (not tabs or multi-route map) | Simpler UI, one route context at a time | — Pending |
| Polish existing theme rather than redesign | Faster, preserves working styles, focuses effort on functionality | — Pending |
| Map-first mobile layout with bottom sheet | Standard transit app pattern, maximises map visibility | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-02 after initialization*
