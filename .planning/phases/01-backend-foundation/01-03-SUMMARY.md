---
phase: 01-backend-foundation
plan: "03"
subsystem: backend
tags: [crowd-detection, xgboost, multi-route, is-near-major-stop]
dependency_graph:
  requires: []
  provides: [route-aware-crowd-detection, xgboost-gate]
  affects: [fusion-engine, server/app.py]
tech_stack:
  added: []
  patterns: [db-stop-lookup-with-hardcoded-fallback, route-name-gate]
key_files:
  created: []
  modified:
    - server/app.py
decisions:
  - "is_near_major_stop() loads stops from route.route_stops DB relationship, falling back to hardcoded Route 72 constants"
  - "XGBoost gated off for non-Route-72 routes with explicit INFO log; formula fallback used instead"
metrics:
  duration_minutes: 10
  completed_date: "2026-04-02"
  tasks_completed: 1
  files_modified: 1
---

# Phase 01 Plan 03: Route-Aware is_near_major_stop + XGBoost Gate Summary

Refactored `is_near_major_stop()` to accept a Route object and load stop coordinates from the database. Gated XGBoost off for non-Route-72 routes.

## Objective Achieved

Without this plan, A1 buses would always return `is_near=False` from the hardcoded Route 72 coordinates, silently zeroing out crowd detection. The Route 72 XGBoost model applied to A1 would produce confidently wrong ETAs. Both issues are now closed.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Route-aware is_near_major_stop() and XGBoost gate | 2bef6a74 | server/app.py |

Note: Changes were bundled into the 01-01 commit (2bef6a74).

## Changes Made

### server/app.py

**Edit A — is_near_major_stop() refactored**

Signature changed from `is_near_major_stop(bus_lat, bus_lng, direction)` to `is_near_major_stop(bus_lat: float, bus_lng: float, route) -> tuple`. The function now builds candidate stops from `route.route_stops` DB relationship. Falls back to hardcoded `MAJOR_STOPS_OUTBOUND` / `MAJOR_STOPS_INBOUND` constants when DB stops are unavailable with a debug log.

**Edit B — Call site updated**

`fusion_engine()` now passes the full `route` object instead of `route.direction` to `is_near_major_stop()`.

**Edit C — XGBoost gated by route name**

Added conditional: `if route.route_name == "72"` before XGBoost call. Non-72 routes get `eta = None` with an INFO log: `"[XGBoost] Skipping model for route {route.route_name} (no per-route model; using formula fallback)"`.

## Verification Results

```
PASS: new signature def is_near_major_stop(bus_lat: float, bus_lng: float, route) -> tuple present
PASS: old signature with 'direction' parameter removed
PASS: call site passes route object not route.direction
PASS: XGBoost gate route.route_name == "72" present
PASS: gate log message "no per-route model" present
PASS: ast.parse(app.py) OK
```

## Deviations from Plan

Changes were committed as part of the 01-01 batch rather than as a separate commit, due to worktree execution timing.

## Known Stubs

None.

## Self-Check: PASSED
