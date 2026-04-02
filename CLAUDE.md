# CLAUDE.md

Project memory for Claude Code in this repository.

## Project Snapshot

Transight AI is a Route 72 MVP for Bristol bus prediction. The live app is:

- `client/`: React 19 + Vite 7 + Tailwind v4 + Leaflet
- `server/`: Flask API + Fusion Engine background thread + SQLAlchemy
- PostgreSQL for route, stop, and bus-log data
- Live inputs from BODS, TomTom, and YOLOv8, with optional GTFS timetable enrichment

The current shippable architecture is the existing Flask + React + PostgreSQL stack. Larger platform changes are deferred.

## Start Here

Backend:

```bash
cd server
pip install -r requirements.txt
python setup_db.py
python app.py
```

Frontend:

```bash
cd client
npm install
npm run dev
```

Optional data/model steps:

```bash
cd server
python gtfs_loader.py ../itm_south_west_gtfs.zip
python generate_synthetic_data.py
python train_xgboost.py
```

## High-Signal Files

- `server/app.py`: Flask entry point, Fusion Engine, ETA helpers, API routes
- `server/models.py`: `Route`, `BusLog`, `Stop`, `RouteStop`
- `server/bods_parser.py`: live bus parsing and vehicle matching
- `server/gtfs_parser.py`: schedule helpers used by the live pipeline
- `server/seed.py`: destructive reset and reseed script
- `client/src/App.jsx`: route selector, polling, Leaflet map, dashboard cards
- `client/src/index.css`: Tailwind v4 theme tokens and custom styling

## Working Rules

- Prefer the smallest targeted change and verify it before moving on.
- Do not run `python seed.py` or `python server/seed.py` unless the user explicitly approves a destructive reset.
- `server/app.py` does not auto-load `.env`; export variables in the shell when needed.
- Keep graceful fallbacks intact when API keys or live feeds are unavailable.
- Preserve Tailwind v4 patterns in the frontend; there is no `tailwind.config.js`.
- Use the repo-specific rules in `.claude/rules/` for file-targeted constraints.

## Verification Expectations

- Frontend change: `cd client && npm run build` and `npm run lint`
- Backend/API change: run the smallest relevant `python test_*.py` script or a targeted Flask/client smoke test
- Data-pipeline change: verify both the live-data path and the fallback/no-key path
- Route or ETA changes: confirm `/api/status/<route_id>` and `/api/routes/<route_id>/predictions` still behave sensibly

## Useful Claude Commands

- `/seed-check`: inspect DB state without reseeding
- `/route-audit`: inspect a route end-to-end from config to status endpoint
- `/fusion-debug`: investigate a Fusion Engine, ETA, or live-data issue
- `/ship-readiness`: review diffs and run the right verification steps before shipping

## Useful Claude Agents

- `transight-backend-agent`: Flask, BODS, GTFS, ETA, and database work
- `transight-frontend-agent`: React, Tailwind, and Leaflet work
- `transight-verifier-agent`: targeted verification and ship checks
