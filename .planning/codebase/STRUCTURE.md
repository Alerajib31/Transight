# Codebase Structure

**Analysis Date:** 2026-04-02

## Directory Layout

```
Transight2/
├── server/                  # Python Flask backend
│   ├── app.py               # Flask API, Fusion Engine, main entry point
│   ├── models.py            # SQLAlchemy models (Route, BusLog, Stop, RouteStop)
│   ├── bods_parser.py       # SIRI-VM XML parsing for BODS live vehicle data
│   ├── gtfs_parser.py       # GTFS zip file parsing for schedules and stops
│   ├── env_utils.py         # Environment config loading
│   ├── requirements.txt      # Python dependencies
│   ├── setup_db.py          # Database initialization script
│   ├── seed.py              # Destructive DB reset (DO NOT RUN without approval)
│   ├── train_xgboost.py     # ETA model training
│   ├── generate_synthetic_data.py  # Test data generation
│   ├── test_*.py            # Verification scripts
│   └── runs/                # YOLOv8 inference output (generated)
├── client/                  # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx          # Main component (route selector, map, dashboard)
│   │   ├── HistoricalTrends.jsx  # SVG trend charts component
│   │   ├── main.jsx         # React entry point
│   │   ├── index.css        # Tailwind v4 theme tokens and custom styles
│   │   └── assets/          # Static images
│   ├── package.json         # npm dependencies, scripts
│   ├── vite.config.js       # Vite + Tailwind + React plugin config
│   ├── eslint.config.js     # ESLint rules
│   ├── dist/                # Built static assets (npm run build)
│   └── node_modules/        # npm packages
├── .planning/
│   └── codebase/            # GSD documentation (generated)
├── docs/                    # Research and design docs
├── .claude/
│   ├── rules/               # File-specific Claude rules
│   │   ├── python-backend.md
│   │   ├── react-frontend.md
│   │   └── workflow.md
│   └── skills/              # Claude agent skill definitions
├── .env.example             # Template for required env vars
├── .env                     # Actual env vars (NOT COMMITTED)
├── CLAUDE.md                # Project memory for Claude Code
├── README.md                # Getting started guide
└── bus_queue.mp4            # Video feed for YOLOv8 crowd detection
```

## Directory Purposes

**server/**
- Purpose: Flask REST API, real-time data fusion, scheduling, and persistence
- Contains: API routes, database models, external service parsers, ML inference, background worker
- Key files: `app.py` (everything), `models.py` (schema), `bods_parser.py` (BODS XML), `gtfs_parser.py` (schedules)

**client/src/**
- Purpose: React UI for route selection, map visualization, live metrics
- Contains: Main App component, trend charts, Leaflet map integration, Tailwind styling
- Key files: `App.jsx` (polling, state, map), `HistoricalTrends.jsx` (SVG charts), `index.css` (theme)

**.planning/codebase/**
- Purpose: GSD documentation for automated code generation
- Contains: ARCHITECTURE.md, STRUCTURE.md, and other analysis documents
- Used by: `/gsd:plan-phase` and `/gsd:execute-phase` commands

**docs/**
- Purpose: Design documentation and research
- Contains: Architecture diagrams, data flow specs, integration notes

**.claude/**
- Purpose: Claude-specific rules and skill definitions
- Contains: File-scoped constraints, custom agent prompts, skill configurations

## Key File Locations

**Entry Points:**

- `server/app.py` (line 1732): Backend web server and Fusion Engine startup
- `client/src/main.jsx`: React root mount point
- `client/vite.config.js`: Frontend build and dev server configuration

**Configuration:**

- `server/app.py` (line 41-108): Flask app configuration, constants, environment variables
- `server/env_utils.py`: Centralized env loading and database URL parsing
- `client/vite.config.js`: Vite plugins, dev server proxy to backend
- `client/src/index.css`: Tailwind v4 theme tokens (light/dark mode)

**Core Logic:**

- `server/app.py` (line 1235): Fusion Engine background loop
- `server/app.py` (line 687): BODS vehicle fetching and filtering
- `server/app.py` (line 615): TomTom routing API integration
- `server/app.py` (line 318): XGBoost ETA prediction
- `server/app.py` (line 1496): Stop prediction endpoint
- `client/src/App.jsx` (line 124): Main dashboard component with state management

**Database & Models:**

- `server/models.py` (line 12): `Route` model - route configuration
- `server/models.py` (line 57): `BusLog` model - historical records
- `server/models.py` (line 96): `Stop` model - GTFS stops
- `server/models.py` (line 116): `RouteStop` model - route-stop association

**Data Parsing:**

- `server/bods_parser.py` (line 17): SIRI-VM XML parsing from BODS
- `server/gtfs_parser.py` (line 19): GTFS zip parsing, trip/stop matching

**Testing & Verification:**

- `server/test_api.py`: API endpoint verification
- `server/test_status.py`: Status endpoint checks
- `server/test_route2.py`: Route-specific tests
- `server/setup_db.py`: Schema initialization

## Naming Conventions

**Files:**

- Python modules: `snake_case.py` (e.g., `bods_parser.py`, `gtfs_parser.py`)
- React components: `PascalCase.jsx` (e.g., `App.jsx`, `HistoricalTrends.jsx`)
- Config files: Standard names (`vite.config.js`, `eslint.config.js`, `package.json`)
- Scripts: Descriptive action + noun (e.g., `setup_db.py`, `train_xgboost.py`, `generate_synthetic_data.py`)
- Test files: `test_<noun>.py` (e.g., `test_api.py`, `test_status.py`)

**Directories:**

- Server modules: Single level (`server/`) with all Python files flat
- Frontend source: Grouped by type (`client/src/` contains components, styles, assets)
- Tools/config: Dot-directories for IDE config (`.vscode/`, `.claude/`, `.planning/`)

**Python Functions:**

- Data parsers: `parse_*` (e.g., `parse_siri_vm()`, `parse_gtfs_zip()`)
- Getters: `get_*` (e.g., `get_route_distance_tomtom()`, `get_smoothed_crowd_count()`)
- Builders: `build_*` (e.g., `build_eta_features()`, `build_scheduled_datetime()`)
- Checkers: `is_*` (e.g., `is_vehicle_live_for_route()`, `is_recent_live_timestamp()`)
- Calculators: `calculate_*` (e.g., `calculate_eta()`, `calculate_route_delay()`)
- Formatters: `format_*` (e.g., `format_gtfs_time()`)

**JavaScript/React:**

- State setters: camelCase with `set` prefix (e.g., `setRoutes`, `setSelectedRouteId`)
- Callbacks: `handle*` or `fetch*` (e.g., `fetchStatus`, `handleThemeToggle`)
- Helpers: lowercase (e.g., `getBusMarkerColors()`, `getBusKey()`)
- Constants: UPPERCASE (e.g., `API_BASE`, `POLL_INTERVAL`)

## Where to Add New Code

**New Feature:**
- Primary code: Add to `server/app.py` for API logic or `client/src/App.jsx` for UI
- Tests: Create `server/test_<feature>.py`
- Models: Extend `server/models.py` if new data type needed
- Parser: Create `server/<service>_parser.py` if new external API

**New Component/Module:**
- Implementation: React components in `client/src/<ComponentName>.jsx`
- Python modules: Avoid creating new files; add functions to existing parsers or app.py
- Styling: Use Tailwind classes in JSX; add custom CSS to `client/src/index.css` only for theme vars

**Utilities:**
- Shared Python functions: Add to appropriate parser module or create helper functions in `app.py`
- Shared JavaScript helpers: Add to `client/src/App.jsx` above component definition (lines 28-119)
- Shared constants: Define at module top (Python: line 41-108 in app.py; JavaScript: line 89-91 in App.jsx)

## Special Directories

**server/runs/**
- Purpose: YOLOv8 inference output directories
- Generated: Yes (by ultralytics library during crowd detection)
- Committed: No (ignored in `.gitignore`)

**client/dist/**
- Purpose: Built static assets
- Generated: Yes (by `npm run build`)
- Committed: No (ignored in `.gitignore`)

**client/node_modules/**
- Purpose: npm dependencies
- Generated: Yes (by `npm install`)
- Committed: No (ignored in `.gitignore`)

**.planning/codebase/**
- Purpose: GSD codebase analysis documents
- Generated: Yes (by `/gsd:map-codebase` command)
- Committed: Yes (required by GSD workflow)

**.env and .env.example**
- `.env`: Actual environment variables (credentials, API keys)
- Committed: No (`.env` ignored; `.env.example` shows required keys)
- `.env.example`: Template for required env vars

## Database Schema Files

**Initialization:**
- File: `server/setup_db.py`
- Purpose: Create PostgreSQL database and initialize tables
- Usage: Run once before first app start

**Destructive Reset:**
- File: `server/seed.py`
- Purpose: Drop and recreate all tables, load seed data
- WARNING: Never run without explicit user approval; loses all historical data

**Models Definition:**
- File: `server/models.py`
- Contains: SQLAlchemy model definitions (Route, BusLog, Stop, RouteStop)
- Changes: Update here to modify schema

## Frontend Asset Organization

**Static Images:**
- Location: `client/src/assets/`
- Current: React logo (unused in current design)

**Styling:**
- Theme: `client/src/index.css` (Tailwind v4 theme tokens)
- Component styles: Inline Tailwind classes in JSX (App.jsx, HistoricalTrends.jsx)
- No `tailwind.config.js`: Theme defined directly in CSS `@theme` block

**Icons & Markers:**
- Leaflet icons: Hardcoded as DivIcons in `client/src/App.jsx` (lines 52-87)
- Bus marker: Dynamic SVG with gradient based on delay (line 36-50)

---

*Structure analysis: 2026-04-02*
