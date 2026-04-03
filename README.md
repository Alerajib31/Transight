# Transight AI - Phase 2 MVP

Real-time bus tracking and ETA prediction for Bristol bus services.

## Current Scope

The current MVP tracks:

- Route `72` outbound and inbound
- Route `A1` outbound and inbound

The stack is:

- `client/`: React 19 + Vite 7 + Tailwind v4 + Leaflet
- `server/`: Flask API + Fusion Engine background thread + SQLAlchemy
- PostgreSQL for routes, stops, and historical `BusLog` data
- Live inputs from BODS, TomTom, GTFS, and YOLOv8

ETA prediction now uses route-specific XGBoost models as the primary path for both `72` and `A1`, with formula-based ETA kept as a resilience fallback if a model is missing or prediction fails.

## Quick Start

### 1. Configure environment

The backend auto-loads the repo-root `.env` file. Process environment variables still override it if needed.

Important variables:

- `DATABASE_URL`
- `BODS_API_KEY`
- `TOMTOM_API_KEY`
- `TOMTOM_ROUTING_KEY`
- `VIDEO_PATH`
- `FUSION_INTERVAL`

### 2. Create the database

```bash
cd server
py -3 setup_db.py
```

### 3. Seed routes

```bash
cd server
py -3 seed.py
py -3 seed_a1.py
```

### 4. Optional: load GTFS data

```bash
cd server
py -3 gtfs_loader.py ../itm_south_west_gtfs.zip
```

### 5. Train ETA models

```bash
cd server
py -3 train_xgboost.py --route 72
py -3 train_xgboost.py --route A1
```

This produces:

- `server/xgboost_eta_model_72.joblib`
- `server/xgboost_eta_model_a1.joblib`
- `server/xgboost_eta_metrics_72.json`
- `server/xgboost_eta_metrics_a1.json`

For Route `72`, training also refreshes the legacy compatibility artifact:

- `server/xgboost_eta_model.joblib`
- `server/xgboost_eta_metrics.json`

### 6. Start the backend

```bash
cd server
py -3 app.py
```

### 7. Start the frontend

```bash
cd client
npm install
npm run dev
```

Open `http://localhost:3000`.

## Development Helpers

Windows one-command start:

```powershell
.\start-dev.ps1
```

Windows local Node shell:

```powershell
. .\use-local-node.ps1
```

## API Summary

| Endpoint | Method | Description |
|---|---|---|
| `/api/routes` | `GET` | List configured routes |
| `/api/routes/<route_id>/stops` | `GET` | Ordered stops for a route |
| `/api/routes/<route_id>/predictions` | `GET` | Stop-by-stop timetable or live predictions |
| `/api/routes/<route_id>/history` | `GET` | Recent BusLog history for charts/debugging |
| `/api/status/<route_id>` | `GET` | Current live bus status for a route |

Live ETA responses now include an `eta_method` field so you can verify whether the current ETA came from:

- `xgboost`
- `formula_fallback`
- `schedule_only`

## Model Training Notes

- Real training rows are filtered by `Route.route_name`, so `72` and `A1` each get their own model.
- Synthetic augmentation is now generated in memory and does not delete or overwrite `BusLog`.
- Training fails clearly if there are not enough real `BusLog` rows for the requested route before augmentation.

## Notes

- If BODS or TomTom keys are unavailable, the app still starts and falls back where possible.
- The backend batches BODS requests by allowed operators instead of using the unrestricted national feed.
- On Windows, prefer `py -3` if `python` is not on `PATH`.

## Remaining Roadmap

- Historical trend charts
- Multi-stop route visualization polish
- WebSocket live push
- Further route expansion beyond `72` and `A1`
