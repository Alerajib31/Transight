---
phase: 01-backend-foundation
plan: "04"
subsystem: backend
tags: [a1-route, seeding, gtfs-stops, discovery, multi-route]
dependency_graph:
  requires: [bulk-bods-fetch, gtfs-agency-filter, route-aware-crowd-detection, xgboost-gate]
  provides: [a1-route-rows, a1-gtfs-stops, a1-route-path]
  affects: [routes-table, route-stops-table, stops-table, api-routes-endpoint]
tech_stack:
  added: []
  patterns: [upsert-seeding, empirical-discovery, scoped-gtfs-load]
key_files:
  created:
    - server/discover_a1.py
    - server/seed_a1.py
  modified: []
decisions:
  - "A1 GTFS agency_id confirmed as OP736 (single agency, no collision)"
  - "A1 operator code assumed FBRI (BODS API returned 403 during discovery; will confirm when key is refreshed)"
  - "A1 route_path populated from GTFS stop coordinates after loading"
  - "A1 typical_duration_min set to 40 outbound / 45 inbound based on research"
metrics:
  duration_minutes: 10
  completed_date: "2026-04-03"
  tasks_completed: 3
  files_modified: 3
---

# Phase 01 Plan 04: A1 Discovery, Seeding, and GTFS Stop Load Summary

Created empirical discovery tool, safe A1 route seeder, loaded GTFS stops, and verified end-to-end data integrity.

## Objective Achieved

A1 Airport Flyer is now fully represented in the database with both route directions and all GTFS stops loaded. The `/api/routes` endpoint returns 4 routes. Route 72 data is completely unaffected.

## Tasks Completed

| Task | Name | Status | Files |
|------|------|--------|-------|
| 1 | Create discover_a1.py | Complete | server/discover_a1.py |
| 2 | Create seed_a1.py and insert A1 routes | Complete | server/seed_a1.py |
| 3 | Human verification checkpoint | Complete (see below) | — |

## Verification Results

```
GTFS Discovery:
  route_id='32450'  agency_id='OP736'  — single agency, no collision
  
BODS Discovery:
  BODS API returned 403 — key expired or rate-limited
  Operator code assumed FBRI (First Bristol — known A1 operator)

Seed (dry run):
  Route 72 rows present: 2 (not affected)
  INSERT A1 outbound: Bristol City Centre → Bristol Airport
  INSERT A1 inbound: Bristol Airport → Bristol City Centre

Seed (confirmed):
  A1 rows in database: 2

GTFS Loader (--route A1):
  A1 outbound: 22 stops linked
  A1 inbound: 23 stops linked

Route 72 integrity:
  72 outbound: 32 stops (unchanged)
  72 inbound: 29 stops (unchanged)

API verification:
  GET /api/routes → 4 routes (72 out, 72 in, A1 out, A1 in)

BusLog accumulation:
  DEFERRED — requires working BODS API key (403 during this session)
```

## Deviations from Plan

- BODS API key returned 403, preventing live vehicle discovery. Used known FBRI operator code.
- A1 BusLog accumulation cannot be verified until BODS key is refreshed.
- A1 `total_stops` and `route_path` updated post-GTFS-load (extra step not in original plan).

## Known Stubs

- BODS live verification deferred — A1 vehicle tracking will activate automatically once BODS API key works.
- A1 XGBoost model not trained (expected — gated off in plan 01-03, formula fallback used).

## Self-Check: PASSED (with BODS caveat)
