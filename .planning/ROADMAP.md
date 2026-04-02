# Roadmap: Transight AI — Multi-Route Expansion

**Milestone:** A1 Airport Flyer + Multi-Route MVP
**Generated:** 2026-04-02
**Granularity:** Coarse (2 phases)
**Coverage:** 13/13 v1 requirements mapped

---

## Phases

- [ ] **Phase 1: Backend Foundation** - Close all silent-failure pitfalls, load A1 data, and make the Fusion Engine route-aware before any A1 rows enter the system
- [ ] **Phase 2: Multi-Route Frontend** - Deliver the visible multi-route experience: route selector, stop popups, responsive layouts, delay indicators, and per-route ETA quality

---

## Phase Details

### Phase 1: Backend Foundation
**Goal**: A1 Airport Flyer data flows correctly through the Fusion Engine with no silent corruption — verified by accumulating BusLog rows for A1 while Route 72 remains unaffected
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, LIVE-01, LIVE-02
**Success Criteria** (what must be TRUE):
  1. Calling `/api/routes` returns both Route 72 and A1 (outbound + inbound) as distinct route entries
  2. A1 BusLog rows accumulate in the database during a live Fusion Engine cycle without disrupting existing Route 72 BusLog rows
  3. Running the GTFS loader with a route argument for A1 does not delete or alter Route 72 stop associations
  4. The BODS fetcher issues one bulk request per cycle (not one per route direction) and correctly fans out A1 and Route 72 vehicles in-process
  5. `is_near_major_stop()` returns meaningful results for A1 stop coordinates (not hardcoded Route 72 values)
**Plans**: 4 plans

Plans:
- [ ] 01-01-PLAN.md — Bulk BODS fetch, operator allowlist cap removal, route-prefixed logs
- [ ] 01-02-PLAN.md — GTFS agency_id filter + gtfs_loader scoped --route delete
- [ ] 01-03-PLAN.md — is_near_major_stop() route-aware refactor + XGBoost gate for A1
- [ ] 01-04-PLAN.md — A1 empirical discovery, route seeding, GTFS stop load, end-to-end validation

### Phase 2: Multi-Route Frontend
**Goal**: A user can switch between Route 72 and A1, see live buses and stop-level arrival times on the map, and use the app comfortably on both mobile and desktop
**Depends on**: Phase 1
**Requirements**: LIVE-03, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06
**Success Criteria** (what must be TRUE):
  1. A user can open a dropdown, select A1 (or Route 72), and the map flies to that route's area with correctly colored bus markers
  2. A user tapping any stop marker on the map sees a popup with the next predicted arrival time and a delay badge (on time / late / early)
  3. On a mobile device, the map fills the screen and a bottom sheet slides up to show route info and stop details without obscuring the map
  4. On a desktop browser, the map and info panel sit side by side without overlap or layout breakage
  5. Every active stop across both routes shows a computed delay indicator based on predicted vs scheduled arrival
**Plans**: TBD
**UI hint**: yes

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Backend Foundation | 0/4 | Not started | - |
| 2. Multi-Route Frontend | 0/? | Not started | - |

---

## Coverage Map

| Requirement | Phase |
|-------------|-------|
| DATA-01 | Phase 1 |
| DATA-02 | Phase 1 |
| DATA-03 | Phase 1 |
| DATA-04 | Phase 1 |
| LIVE-01 | Phase 1 |
| LIVE-02 | Phase 1 |
| LIVE-03 | Phase 2 |
| UI-01 | Phase 2 |
| UI-02 | Phase 2 |
| UI-03 | Phase 2 |
| UI-04 | Phase 2 |
| UI-05 | Phase 2 |
| UI-06 | Phase 2 |

**Total mapped: 13/13**

---

*Roadmap created: 2026-04-02*
*Phase 1 planned: 2026-04-02 — 4 plans in 2 waves*
