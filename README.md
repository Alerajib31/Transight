# Transight AI — Phase 2 MVP

> Real-Time Digital Twin for Bristol Bus Services.

## Current Release

This repository is frozen at the Route 72 MVP handoff state. The current Flask + React + PostgreSQL stack is the shippable version in this branch. Future architecture work stays in `NEXT_STEPS.md`.

```
Transight2/
├── dev.nix                 # Nix environment (PostgreSQL, Python, Node, ffmpeg)
├── server/
│   ├── requirements.txt    # Python dependencies
│   ├── models.py           # SQLAlchemy models (Route, BusLog)
│   ├── app.py              # Flask API + Fusion Engine
│   ├── seed.py             # Database seeder (2 × Route 72)
│   └── bus_queue.mp4       # ← Place your video file here
└── client/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx         # Dashboard + Map
        └── index.css       # Tailwind v4 + dark theme
```

---

## Prerequisites

| Tool       | Version |
|------------|---------|
| Python     | 3.11+   |
| Node.js    | 20+     |
| PostgreSQL | 15+     |
| ffmpeg     | any     |

---

## Quick Start

### 1. Environment

Set the runtime variables in your shell before starting Flask. `app.py` reads environment variables directly and does not auto-load `.env`.

```powershell
$env:DATABASE_URL="postgresql://postgres:R%40jibale3138@localhost:5432/transight_db"
$env:BODS_API_KEY="your_bods_api_key_here"
$env:TOMTOM_API_KEY="your_tomtom_traffic_key_here"
$env:TOMTOM_ROUTING_KEY="your_tomtom_routing_key_here"
$env:VIDEO_PATH="server/bus_queue.mp4"
$env:FUSION_INTERVAL="10"
```

If you prefer using `.env`, source those values into the shell first or copy them into your terminal session. The backend only sees variables exported into the process environment.

### 2. Database

```bash
# Create the database if it does not already exist
cd server
python setup_db.py
```

### 3. Backend

```bash
cd server
pip install -r requirements.txt
python seed.py          # Seeds 2 routes
python app.py           # Starts Flask on :5000 + Fusion Engine
```

### 4. Frontend

```bash
cd client
npm install
npm run dev             # Starts Vite on :3000
```

Open **http://localhost:3000** in your browser.

---

## Environment Variables

| Variable         | Default                                              | Purpose                    |
|------------------|------------------------------------------------------|----------------------------|
| `DATABASE_URL`   | `postgresql://postgres:R%40jibale3138@localhost:5432/transight_db` | PostgreSQL connection      |
| `BODS_API_KEY`   | required for live GPS, optional for schedule-only fallback | Bus Open Data Service key  |
| `TOMTOM_API_KEY` | required for live traffic, optional for schedule-only fallback | TomTom Traffic API key     |
| `TOMTOM_ROUTING_KEY` | required for routing ETA estimates, optional for schedule-only fallback | TomTom Routing API key |
| `VIDEO_PATH`     | `server/bus_queue.mp4`                               | Simulated camera feed      |
| `FUSION_INTERVAL`| `10`                                                 | Seconds between cycles     |

---

## API Reference

| Endpoint               | Method | Description                          |
|------------------------|--------|--------------------------------------|
| `/api/routes`          | GET    | All configured routes (for dropdown) |
| `/api/routes/<route_id>/stops` | GET | Ordered stops for a route |
| `/api/routes/<route_id>/predictions` | GET | Stop-by-stop timetable or live predictions |
| `/api/status/<route_id>` | GET  | Latest fused status for a route      |

---

## Notes

- The backend does not auto-load `.env` in this repo. Export shell variables before running `python app.py`.
- If the live API keys are missing, the app still starts and falls back to schedule-only behavior where possible.

---

## Architecture

```
┌──────────────┐  HTTP/JSON  ┌──────────────┐  SQL  ┌──────────────┐
│  React App   │◄──────────►│  Flask API   │◄─────►│  PostgreSQL  │
│  (Port 3000) │             │  (Port 5000) │       │  (Port 5432) │
└──────────────┘             └──────┬───────┘       └──────────────┘
                                    │
                        ┌───────────┴───────────┐
                        │   Fusion Engine       │
                        │   (Background Thread) │
                        ├───────────────────────┤
                        │ ► BODS GPS Fetch      │
                        │ ► TomTom Traffic      │
                        │ ► YOLOv8 Crowd Count  │
                        │ ► ETA Calculation     │
                        └───────────────────────┘
```

---

## Later Roadmap

- [ ] XGBoost ETA prediction model (replaces math formula)
- [ ] Historical trend charts
- [ ] Multi-stop route visualisation
- [ ] WebSocket live push
