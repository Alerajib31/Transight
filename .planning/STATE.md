---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-04-02T20:40:54.080Z"
progress:
  total_phases: 2
  completed_phases: 0
  total_plans: 4
  completed_plans: 2
  percent: 50
---

# Project State: Transight AI — Multi-Route Expansion

**Last updated:** 2026-04-02
**Session:** Roadmap creation

---

## Project Reference

**Core value:** Accurate, real-time bus arrival predictions with delay indicators at every stop — proving the system scales beyond a single route.

**Current focus:** Phase 01 — Backend Foundation

---

## Current Position

Phase: 01 (Backend Foundation) — EXECUTING
Plan: 3 of 4
| Field | Value |
|-------|-------|
| Phase | 1 — Backend Foundation |
| Plan | None (planning not yet started) |
| Status | Not started |
| Milestone | A1 Airport Flyer + Multi-Route MVP |

**Progress:**

[█████░░░░░] 50%
Phase 1 [          ] 0%   Backend Foundation
Phase 2 [          ] 0%   Multi-Route Frontend

```

**Overall: 0/2 phases complete**

---

## Roadmap Summary

| Phase | Goal | Requirements | Status |
|-------|------|--------------|--------|
| 1 | A1 data flows through Fusion Engine with no silent corruption | DATA-01–04, LIVE-01–02 | Not started |
| 2 | User can switch routes, see stop popups, use on mobile + desktop | LIVE-03, UI-01–06 | Not started |

---

## Accumulated Context

### Key Decisions Recorded

- Phases derived from 13 v1 requirements; coarse granularity produces 2 phases naturally
- Phase 1 is entirely backend: all 5 silent-failure pitfalls must be closed before A1 rows enter the DB
- Phase 2 frontend work can be partially built in parallel with Phase 1 but cannot be validated for A1 until Phase 1 completes
- XGBoost gated off for A1 in Phase 1 (formula fallback); A1 model trained as a parallel track in Phase 2
- Stop popup implemented client-side from cached `routePredictions.stops[]` — no new API endpoint needed

### Critical Pitfalls to Close in Phase 1

1. BODS per-route HTTP request multiplication — refactor to bulk fetch + local fan-out
2. `MAJOR_STOPS` hardcoded to Route 72 coordinates — make `is_near_major_stop()` route-aware
3. GTFS `route_short_name` collision for "A1" — add `agency_id` filter to GTFS parser
4. XGBoost model trained on Route 72 only — gate off for A1 until A1 model exists
5. `gtfs_loader.py` destructive delete — add `--route` scoped delete argument

### Research Flags (Empirical Verification Required Before Coding)

- A1 BODS `LineRef` and `operator_ref` — must run raw BODS dump to confirm (assumption: `FBRI`/`A1`)
- A1 GTFS `route_short_name` and `agency_id` — must inspect `itm_south_west_gtfs.zip` before seeding
- `is_near_major_stop()` full internals — read `app.py` lines 800–900 before designing refactor
- `routePredictions.stops[].stop_id` type consistency — confirm string vs integer before building stop popup lookup

### Todos

- [ ] Start Phase 1 planning: `/gsd:plan-phase 1`
- [ ] Run empirical BODS discovery before any Fusion Engine code changes
- [ ] Run GTFS file inspection before any loader changes

### Blockers

None at roadmap stage. Empirical verification steps are ordered tasks within Phase 1 planning.

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Requirements mapped | 13/13 |
| Phases defined | 2 |
| Plans complete | 0 |
| Phases complete | 0 |

---
| Phase 01 P02 | 8 | 2 tasks | 2 files |
| Phase 01 P01 | 15 | 2 tasks | 2 files |

## Session Continuity

**To resume after a break:**

1. Read `.planning/STATE.md` (this file) for current position
2. Read `.planning/ROADMAP.md` for phase goals and success criteria
3. Read `.planning/REQUIREMENTS.md` for requirement details
4. Check which phase plan is active under `.planning/plans/`
5. Run `/gsd:plan-phase 1` to begin Phase 1 planning

**Files most relevant to current work:**

- `server/app.py` — Fusion Engine (lines 1235–1450), MAJOR_STOPS (lines 75–88), operator allowlist (lines 65–66)
- `server/bods_parser.py` — BODS fetch functions
- `server/gtfs_parser.py` — GTFS route lookup and trip candidates
- `server/gtfs_loader.py` — destructive delete pattern (lines 24–27)

---

*State initialized: 2026-04-02 during roadmap creation*
