---
phase: 01-backend-foundation
plan: "01"
subsystem: backend
tags: [bods, fusion-engine, multi-route, logging]
dependency_graph:
  requires: []
  provides: [bulk-bods-fetch, operator-allowlist-fix, route-tagged-logs, parameterised-test-harness]
  affects: [fusion-engine, bods-fetching, server/app.py, server/bods_parser.py]
tech_stack:
  added: []
  patterns: [cycle-id-cache, bulk-fetch-fanout, legacy-fallback-parameter]
key_files:
  created: []
  modified:
    - server/app.py
    - server/bods_parser.py
decisions:
  - "Bulk BODS fetch caches by cycle_id int to allow safe reuse across all routes in same cycle"
  - "Legacy single-fetch path preserved via all_vehicles=None default for backwards compatibility"
  - "operator allowlist simplified to single-line tuple comprehension — no cap"
metrics:
  duration_minutes: 15
  completed_date: "2026-04-02"
  tasks_completed: 2
  files_modified: 2
---

# Phase 01 Plan 01: Bulk BODS Fetch + Allowlist Cap Removal Summary

Single-fetch-per-cycle BODS refactor with cycle-id cache, removal of undocumented operator allowlist `:2` cap, route-name-prefixed Fusion Engine logs, and parameterised test harness via `TEST_LINE_REF`.

## Objective Achieved

Without this plan, adding A1 would have doubled BODS HTTP requests to 12/min, and the `:2` cap would silently drop any operator not in the first two slots. Both issues are now closed.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Bulk BODS fetch function, allowlist cap removal, route-prefixed logs | 2bef6a74 | server/app.py |
| 2 | Parameterise bods_parser.py test harness | 507d2f11 | server/bods_parser.py |

## Changes Made

### server/app.py

**Edit A — Operator allowlist cap removed**

The old 5-line block with `[:2]` truncation replaced by a single expression:
```python
BODS_OPERATOR_ALLOWLIST = tuple(dict.fromkeys(_operator_allowlist)) if _operator_allowlist else ("FBRI", "FBRA")
```
All configured operators are now included, no silent truncation.

**Edit B — `fetch_bods_vehicles_bulk()` added**

New function with `_bods_bulk_cache` dict and `_bods_cycle_counter` int. Fetches all BODS vehicles once per cycle (no `line_ref` filter), caches the result keyed by `cycle_id`. Subsequent calls within the same cycle return the cached list immediately.

**Edit C — `fetch_all_buses_for_route()` updated**

Signature changed to `fetch_all_buses_for_route(route, all_vehicles: list | None = None)`. When `all_vehicles` is supplied, filters the pre-fetched list by `line` field equality. When `None` (default), falls back to the original individual BODS call. All downstream operator filtering, proximity filtering, and direction filtering is preserved unchanged.

**Edit D — `fusion_engine()` wired to bulk fetch**

Before the `for route in routes:` loop, increments `_bods_cycle_counter` and calls `fetch_bods_vehicles_bulk(_bods_cycle_counter)`. Passes the result as `all_vehicles=all_vehicles` to `fetch_all_buses_for_route()`. Per-vehicle log lines now use `tag = f"[Fusion:{route.route_name}:{route.direction[:3]}]"` for unambiguous route identification.

### server/bods_parser.py

**Test harness parameterised**

Replaced hardcoded `line_ref='72'` with `os.getenv("TEST_LINE_REF", "72")`. Running `TEST_LINE_REF=A1 python bods_parser.py` now tests the A1 route without any code change.

## Verification Results

```
PASS: all checks passed  (app.py)
PASS: all checks passed  (bods_parser.py)
grep -c '[:2]' server/app.py  → 0
grep -c 'fetch_bods_vehicles_bulk' server/app.py  → 2 (definition + call)
grep -c 'TEST_LINE_REF' server/bods_parser.py  → 1
ast.parse(app.py)  → OK
ast.parse(bods_parser.py)  → OK
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All data paths are fully wired. The bulk fetch returns real BODS data (or empty list if no API key, preserving the existing graceful fallback).

## Self-Check: PASSED

Files created/modified:
- FOUND: server/app.py (contains `fetch_bods_vehicles_bulk`, `_bods_cycle_counter`, `all_vehicles`, `Fusion:{route.route_name}`)
- FOUND: server/bods_parser.py (contains `TEST_LINE_REF`)

Commits verified:
- FOUND: 2bef6a74 — feat(01-01): bulk BODS fetch, allowlist cap removal, route-prefixed logs
- FOUND: 507d2f11 — feat(01-01): parameterise bods_parser.py test harness with TEST_LINE_REF
