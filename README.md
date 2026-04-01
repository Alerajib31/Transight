# Transight AI — Phase 2 MVP

> Real-Time Digital Twin for Bristol Bus Services.

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

### 1. Database

```bash
# Create the database (if not using dev.nix)
createdb transight_db
```

### 2. Backend

```bash
cd server
pip install -r requirements.txt
python seed.py          # Seeds 2 routes
python app.py           # Starts Flask on :5000 + Fusion Engine
```

### 3. Frontend

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
| `DATABASE_URL`   | `postgresql://postgres:postgres@localhost:5432/transight_db` | PostgreSQL connection      |
| `BODS_API_KEY`   | *(empty — uses dummy GPS)*                           | Bus Open Data Service key  |
| `TOMTOM_API_KEY` | *(empty — returns 0 delay)*                          | TomTom Traffic API key     |
| `VIDEO_PATH`     | `server/bus_queue.mp4`                               | Simulated camera feed      |
| `FUSION_INTERVAL`| `10`                                                 | Seconds between cycles     |

---

## API Reference

| Endpoint               | Method | Description                          |
|------------------------|--------|--------------------------------------|
| `/api/routes`          | GET    | All configured routes (for dropdown) |
| `/api/status/<route_id>` | GET  | Latest fused status for a route      |

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

## Phase 3 Roadmap

- [ ] XGBoost ETA prediction model (replaces math formula)
- [ ] Historical trend charts
- [ ] Multi-stop route visualisation
- [ ] WebSocket live push
