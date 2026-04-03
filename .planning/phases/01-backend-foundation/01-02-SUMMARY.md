---
phase: "01"
plan: "02"
subsystem: backend
tags: [gtfs, multi-route, agency-filter, loader]
dependency_graph:
  requires: []
  provides: [agency_id filter in get_trip_candidates, scoped GTFS loader with --route and --dry-run]
  affects: [server/gtfs_parser.py, server/gtfs_loader.py]
tech_stack:
  added: [argparse]
  patterns: [optional kwargs for backward-compatible filter, scoped SQLAlchemy delete with filter_by]
key_files:
  modified:
    - server/gtfs_parser.py
    - server/gtfs_loader.py
decisions:
  - "agency_id filter is optional (default None) — existing callers unaffected"
  - "Scoped delete uses filter_by(route_id=route.id) — Route 72 records untouched during A1 reload"
  - "Full reload (no --route) still wipes Stop table; scoped reload upserts stops per-route"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-02"
  tasks_completed: 2
  files_modified: 2
---

# Phase 01 Plan 02: GTFS Agency Filter and Scoped Loader Summary

**One-liner:** Added `agency_id` filter to `get_trip_candidates()` and refactored `gtfs_loader.py` with `--route` scoped delete and `--dry-run` preview mode to prevent A1/Route 72 data collisions.

## What Was Built

### Task 1: agency_id filter in get_trip_candidates() (commit: 1c13dc43)

Added optional `agency_id=None` keyword argument to `get_trip_candidates()` in `server/gtfs_parser.py`. When supplied, the function filters `matching_routes` to only entries whose `agency_id` field matches before extracting `route_ids`. Logs the before/after count at INFO level and emits a WARNING + returns `[]` if no routes survive the filter. All existing callers are unaffected because the default is `None`.

### Task 2: --route scoped delete and --dry-run in gtfs_loader.py (commit: b060b8fc)

Rewrote `server/gtfs_loader.py` to replace the unconditional `RouteStop.query.delete()` with a per-route scoped delete using `RouteStop.query.filter_by(route_id=route.id).delete()`. Added `argparse` CLI with:
- `--route ROUTE_NAME` — scopes load/delete to a single named route (e.g. `A1`), leaving Route 72 RouteStop rows completely untouched
- `--dry-run` — prints planned actions (row counts) without any `db.session.commit()`

Full reload (no `--route`) still wipes the Stop table safely before reinserting all stops. Scoped reload upserts stops per-route only. Exits with error if `--route` target not found in DB.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Verification

- `python -c "import ast; ast.parse(open('server/gtfs_parser.py').read()); print('OK')"` — PASS
- `python -c "import ast; ast.parse(open('server/gtfs_loader.py').read()); print('OK')"` — PASS
- `python server/gtfs_loader.py --help` — lists `--route` and `--dry-run`; exits 0
- `grep 'RouteStop.query.delete()' server/gtfs_loader.py` — 0 matches (unconditional delete removed)
- `grep 'agency_id' server/gtfs_parser.py` — 6 matches (parameter, filter, log, warning)

## Self-Check: PASSED

- server/gtfs_parser.py — modified and committed at 1c13dc43
- server/gtfs_loader.py — modified and committed at b060b8fc
- Both files parse cleanly via ast.parse
