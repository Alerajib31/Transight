---
name: transight-backend
description: Use when working in server/ or debugging Fusion Engine, ETA, BODS, GTFS, YOLO, or database behavior in Transight
---

# Transight Backend Skill

Use this skill for backend and data-pipeline work in Transight.

## Key Files

- `server/app.py`: Flask routes, Fusion Engine loop, ETA helpers, startup and shutdown behavior
- `server/models.py`: SQLAlchemy schema
- `server/bods_parser.py`: live vehicle parsing and route matching
- `server/gtfs_parser.py`: schedule helpers used at runtime
- `server/gtfs_loader.py`: GTFS import path
- `server/seed.py`: destructive DB reset and seed

## Commands

```bash
cd server
python app.py
python bods_parser.py
python gtfs_loader.py ../itm_south_west_gtfs.zip
python test_api.py
python test_status.py
python test_route2.py
```

## Gotchas

- `seed.py` drops and recreates tables; do not run it casually.
- `app.py` does not auto-load `.env`; export variables in the shell first.
- The Fusion Engine is a background daemon thread, so API behavior and write-path behavior can diverge.
- Keep fallback behavior intact when API keys are missing or live feeds are stale.
- Route and stop logic is heavily centralized in `server/app.py`; avoid broad unrelated edits there.

## Verification

- For API shape changes, hit the smallest affected endpoint or run a focused `python test_*.py` helper.
- For live-data logic, check both the live path and the fallback path.
- For ETA changes, verify downstream fields like predicted arrivals and delay text still line up.
