# Technology Stack

**Analysis Date:** 2026-04-02

## Languages

**Primary:**
- Python 3.x - Backend API, Fusion Engine, data pipelines, machine learning
- JavaScript (ES6+) - React frontend with JSX

**Secondary:**
- SQL - PostgreSQL database queries

## Runtime

**Environment:**
- Node.js (version not pinned) - JavaScript runtime for frontend tooling
- Python 3.x - Flask server and background processes

**Package Manager:**
- npm - JavaScript dependencies (frontend)
- pip - Python dependencies (backend)
- Lockfile: `client/package-lock.json` (present), `server/requirements.txt` (pinned)

## Frameworks

**Core:**
- Flask 3.0.0 - Web framework for REST API and server initialization at `server/app.py`
- React 19.2.0 - Frontend UI framework with hooks
- SQLAlchemy 2.0.23 - ORM for database models at `server/models.py`

**Frontend Tooling:**
- Vite 7.3.1 - Build tool and dev server configured at `client/vite.config.js`
- Tailwind CSS 4.1.18 - Utility-first CSS framework via `@tailwindcss/vite` plugin

**Geospatial & Mapping:**
- Leaflet 1.9.4 - Interactive map library
- react-leaflet 5.0.0 - React bindings for Leaflet

**Build/Dev:**
- @vitejs/plugin-react 5.1.1 - React Fast Refresh for HMR
- ESLint 9.39.1 - Code linting
- @eslint/js 9.39.1 - Core ESLint rules
- eslint-plugin-react-hooks 7.0.1 - React hooks lint rules
- eslint-plugin-react-refresh 0.4.24 - Fast Refresh rules

## Key Dependencies

**Critical:**
- Flask-SQLAlchemy 3.1.1 - Database ORM integration
- psycopg2-binary 2.9.9 - PostgreSQL adapter for Python
- Flask-CORS 4.0.0 - CORS support for cross-origin API requests
- requests 2.31.0 - HTTP client for external API calls (BODS, TomTom, OSRM)

**Machine Learning:**
- ultralytics 8.1.0 - YOLOv8 object detection for passenger counting from video
- opencv-python-headless 4.9.0.80 - Computer vision (video frame processing)
- xgboost 3.1.3 - Gradient boosting for ETA prediction model
- scikit-learn 1.8.0 - Machine learning utilities
- joblib - Model serialization for xgboost_eta_model.joblib

**Frontend:**
- globals 16.5.0 - Global variable definitions for ESLint
- @types/react 19.2.7 - TypeScript type definitions for React
- @types/react-dom 19.2.3 - TypeScript type definitions for ReactDOM

## Configuration

**Environment:**
- Configuration via `.env` file loaded at startup by `server/env_utils.py`
- Variables can be sourced manually in shell before running `python app.py`
- .env.example provided at project root showing required keys

**Environment Variables:**
- `DATABASE_URL` - PostgreSQL connection string (default: `postgresql://postgres:R%40jibale3138@localhost:5432/transight_db`)
- `BODS_API_KEY` - Bus Open Data Service API key for live vehicle data
- `TOMTOM_API_KEY` - TomTom Traffic Flow API key for congestion data
- `TOMTOM_ROUTING_KEY` - TomTom Routing API key for accurate distance/time calculations
- `VIDEO_PATH` - Path to bus queue video file for YOLOv8 passenger detection (default: `bus_queue.mp4`)
- `FUSION_INTERVAL` - Fusion Engine cycle frequency in seconds (default: 10)
- `LIVE_DATA_MAX_AGE_SECONDS` - Maximum age of live data before fallback (default: 180)
- `ROUTE_PROXIMITY_THRESHOLD_KM` - Vehicle-to-route matching distance (default: 2.0)
- `BODS_OPERATOR_ALLOWLIST` - Comma-separated operator codes to monitor (default: FBRI,FBRA)

**Build Config:**
- `client/vite.config.js` - Vite dev server on port 3000 with `/api` proxy to `http://localhost:5000`
- `client/eslint.config.js` - ESLint flat config with React, React Hooks, and React Refresh rules
- `client/src/index.css` - Tailwind v4 theme tokens and custom styling

## Database

**PostgreSQL:**
- Version: Specified via `DATABASE_URL` connection string
- Host: localhost (development), 5432 (default port)
- Database: `transight_db`
- Client: psycopg2-binary 2.9.9
- Setup: `server/setup_db.py` creates database if missing

**Schema:**
- `routes` table - Route configuration and metadata (`server/models.py::Route`)
- `bus_logs` table - Historical fusion engine cycle records (`server/models.py::BusLog`)
- `stops` table - GTFS stop data (`server/models.py::Stop`)
- `route_stops` table - Stop sequence on each route (`server/models.py::RouteStop`)

## Data Files

**GTFS (General Transit Feed Specification):**
- Location: `../itm_south_west_gtfs.zip` (relative to `server/`)
- Purpose: Schedule data for Bristol bus routes
- Loaded via: `server/gtfs_loader.py`
- Parsed by: `server/gtfs_parser.py`

**Machine Learning Models:**
- YOLOv8 nano: `server/yolov8n.pt` - Person detection for passenger counting
- XGBoost: `server/xgboost_eta_model.joblib` - ETA prediction model trained via `server/train_xgboost.py`

**Video Input:**
- Simulated camera feed: `bus_queue.mp4` (configurable via `VIDEO_PATH`)
- Processed by YOLOv8 for passenger detection every Fusion Engine cycle

## API Endpoints

**Frontend to Backend:**
- Dev: Vite proxy at `/api` → `http://localhost:5000` (configured in `client/vite.config.js`)
- Production: Backend Flask app serves API at base URL
- Endpoints defined in `server/app.py`:
  - `GET /api/routes` - All monitored routes
  - `GET /api/routes/<route_id>/stops` - Stops on a route
  - `GET /api/routes/<route_id>/predictions` - Live prediction data
  - `GET /api/routes/<route_id>/history` - Historical logs
  - `GET /api/status/<route_id>` - Current route status

## Platform Requirements

**Development:**
- Python 3.x with pip
- Node.js with npm
- PostgreSQL 12+
- ffmpeg (for video processing with OpenCV)
- GPU optional (for faster YOLOv8 inference)

**Production:**
- Flask server running on port 5000 (configurable)
- PostgreSQL database accessible
- Machine learning models loaded in memory
- Video file for YOLO processing (can be disabled)
- External API keys for BODS and TomTom

---

*Stack analysis: 2026-04-02*
