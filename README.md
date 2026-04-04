# Transight AI - Phase 2 MVP

Real-time bus tracking and ETA prediction for Bristol bus services.

## Prerequisites

- Python `3.11+`
- Node.js `20.19+`
- PostgreSQL `15+`
- `ffmpeg`

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

Copy `.env.example` to `.env`, then update at least `DATABASE_URL` for your local PostgreSQL instance.

The backend auto-loads the repo-root `.env` file. Process environment variables still override it if needed.

Important variables:

- `DATABASE_URL`
- `BODS_API_KEY`
- `TOMTOM_API_KEY`
- `TOMTOM_ROUTING_KEY`
- `VIDEO_PATH`
- `FUSION_INTERVAL`

If BODS or TomTom API keys are missing, the backend still starts and falls back where possible.

### 2. Install backend dependencies

```bash
cd server
py -3 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

On macOS/Linux, activate the virtual environment with:

```bash
source venv/bin/activate
```

### 3. Install frontend dependencies

```bash
cd client
npm install
```

### 4. Create the database

```bash
cd server
py -3 setup_db.py
```

### 5. Seed routes

```bash
cd server
py -3 seed.py
py -3 seed_a1.py --confirm
```

`seed.py` recreates the tables, so run it before `seed_a1.py --confirm`.

### 6. Optional but recommended: load GTFS data

```bash
cd server
py -3 gtfs_loader.py ../itm_south_west_gtfs.zip
```

Loading GTFS data is recommended if you want full stop-by-stop schedule data and populated A1 route geometry.

### 7. Start the backend

```bash
cd server
venv\Scripts\activate
py -3 app.py
```

### 8. Start the frontend

```bash
cd client
npm run dev
```

Open `http://localhost:3000`.

## Included And Optional Assets

Included in the repo:

- `server/yolov8n.pt`
- `server/xgboost_eta_model_72.joblib`
- `server/xgboost_eta_model_a1.joblib`

Not committed to GitHub by default:

- `.env`
- `bus_queue.mp4`
- `itm_south_west_gtfs.zip`

If `bus_queue.mp4` is missing, the app still starts and crowd counting falls back to `0`.

If `itm_south_west_gtfs.zip` is missing, the app still starts and skips GTFS cache warm-up, but stop-level timetable data will be limited.

## Optional Model Training

Pre-trained route-specific ETA models are already included in the repository, so training is not required for first run.

Only retrain after you have collected enough real `BusLog` history. The training script requires at least `50` usable real rows per route before augmentation.

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

## Development Helpers

Windows one-command start:

```powershell
.\start-dev.ps1
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
- For Vite 7, use Node.js `20.19+` to avoid version warnings during `npm run dev`.

## Remaining Roadmap

- Historical trend charts
- Multi-stop route visualization polish
- WebSocket live push
- Further route expansion beyond `72` and `A1`
