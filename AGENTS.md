# Transight - Intelligent Transit Prediction System

## Project Overview

Transight is an AI-powered real-time bus arrival prediction system for Bristol, UK. It combines computer vision, live transit data from the Bus Open Data Service (BODS) API, and machine learning to provide accurate bus arrival predictions. The system features an interactive React-based map interface showing real-time bus locations with GPS trails.

### Key Features
- **Computer Vision Crowd Detection**: Uses YOLOv8 to count people waiting at bus stops via video analysis
- **Real-Time Bus Tracking**: Fetches live vehicle positions from BODS API with GPS trail visualization
- **Comprehensive Bristol Coverage**: Hardcoded database of 77 bus stops across Bristol City Region
- **Interactive Map Interface**: Leaflet-based map with user location, stop markers, and animated bus positions
- **ML Prediction Model**: XGBoost model trained on synthetic data to predict arrival times based on traffic, crowds, and weather

## Technology Stack

### Backend (Python)
| Component | Technology |
|-----------|------------|
| Web Framework | FastAPI 3.2.0 |
| ML/DL | XGBoost, Ultralytics YOLOv8 |
| Computer Vision | OpenCV (cv2) |
| Data Processing | pandas, numpy |
| External APIs | requests (BODS API) |

### Frontend (JavaScript/React)
| Component | Technology |
|-----------|------------|
| Framework | React 19.2.0 |
| Build Tool | Vite 7.2.4 |
| UI Components | Material-UI (MUI) v6/v7 |
| Maps | Leaflet 1.9.4 + React-Leaflet 5.0.0 |
| HTTP Client | axios 1.13.2 |

## Project Structure

```
c:\Transight/
├── main.py                      # FastAPI backend - BODS API integration, stop database
├── cv_counter.py                # YOLOv8 crowd detection for bus stops
├── run_all_cameras.py           # Multi-camera launcher (subprocess orchestrator)
├── train_model.py               # XGBoost model training script
├── generate_data.py             # Synthetic training data generator
├── camera_config.json           # CV system configuration
├── bus_prediction_model.json    # Trained XGBoost model
├── historical_bus_data.csv      # Synthetic training dataset (2000 samples)
├── yolov8n.pt                   # YOLOv8 Nano model weights
├── package.json                 # Root Node.js dependencies
├── videos/                      # Video files for CV processing
│   ├── 1.mp4
│   └── 2.mp4
├── runs/                        # YOLO training runs (auto-generated)
└── transight-frontend/          # React frontend application
    ├── package.json             # Frontend dependencies
    ├── vite.config.js           # Vite build configuration
    ├── eslint.config.js         # ESLint configuration
    ├── index.html               # HTML entry point
    └── src/
        ├── App.jsx              # Main React component (614 lines)
        ├── main.jsx             # React entry point
        ├── index.css            # Global styles
        └── App.css              # Component styles
```

## Module Descriptions

### Backend Modules (`*.py`)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI application with REST endpoints. Contains BRISTOL_STOPS database (77 stops), BODS API integration with SIRI-XML parsing, bus location caching, and haversine distance calculations. |
| `cv_counter.py` | YOLOv8-based person detection for bus stops. Processes video files, filters detections by ROI (excludes right 40% of frame), sends crowd counts to backend every 5 seconds. |
| `run_all_cameras.py` | Orchestrates multiple CV counter instances using subprocess. Configured for STOP_001/STOP_002 with videos 1.mp4/2.mp4. |
| `train_model.py` | Trains XGBoost regressor on historical_bus_data.csv. Features: traffic_delay, crowd_count, is_raining. Target: actual_arrival_time. |
| `generate_data.py` | Generates 2000 synthetic samples using formula: actual_arrival = traffic + (crowd * 4s / 60) + rain_penalty(2min) + noise. |

### Frontend Modules (`transight-frontend/src/`)

| File | Purpose |
|------|---------|
| `App.jsx` | Main UI component with three view modes: 'stops' (map with all stops), 'bus-list' (bottom sheet with approaching buses), 'bus-detail' (live bus tracking with GPS trail). Implements draggable bottom sheet, search, and real-time updates every 10 seconds. |
| `main.jsx` | React 19 bootstrap with createRoot. |
| `index.css` | Global styles with CSS variables, dark/light mode support, full-height layout. |

## Configuration Files

### `camera_config.json`
```json
{
  "system": {
    "backend_url": "http://localhost:8000",
    "update_interval_seconds": 5,
    "frame_skip": 2,
    "display_width": 800
  },
  "bus_stops": [],
  "notes": "Bus stops are now loaded dynamically from BODS API"
}
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with stops count and tracked buses |
| `/stops` | GET | List all 77 Bristol stops (optionally filter by lat/lon/radius) |
| `/nearby-stops` | GET | Find stops near coordinates (default 10km radius) |
| `/stop/{stop_id}/buses` | GET | Get buses approaching a specific stop with real-time positions and trail |
| `/search-stops` | GET | Search stops by name/locality (returns max 20 results) |
| `/all-buses` | GET | Get all buses in Bristol area with distance calculations |

## Build and Run Commands

### Prerequisites
- Python 3.8+
- Node.js 18+
- Video files in `/videos/` directory (for CV module)

### Backend Setup
```bash
# Install Python dependencies (no requirements.txt - install manually)
pip install fastapi uvicorn psycopg2 requests xgboost pandas ultralytics opencv-python scikit-learn

# Generate training data (optional)
python generate_data.py

# Train model (optional)
python train_model.py

# Start backend server
python main.py
# OR with uvicorn directly:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup
```bash
cd transight-frontend

# Install dependencies
npm install

# Development server (Vite dev server with HMR)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Lint
npm run lint
```

### Computer Vision (CV Counter)
```bash
# Single camera/stop
python cv_counter.py --stop-id 01000053220 --video 1.mp4

# Multiple cameras
python run_all_cameras.py
```

## Data Flow

1. **CV Counter** detects people → Sends `crowd_count` to `/update-sensor-data` every 5 seconds
2. **Backend** fetches live bus data from BODS API (cached 30s) via SIRI-XML parsing
3. **Backend** maintains 77 Bristol stops in memory (BRISTOL_STOPS list)
4. **Frontend** polls `/stop/{stop_id}/buses` every 10 seconds for real-time updates
5. **Frontend** displays bus locations with GPS trail (last 20 positions) on Leaflet map

## Code Conventions

### Naming Conventions
- **Python**: `snake_case` for functions/variables, `PascalCase` for classes
- **JavaScript**: `camelCase` for variables/functions, `PascalCase` for components
- **Stop IDs**: ATCO format (e.g., "01000053220" for Temple Meads Station)
- **Route IDs**: Numeric strings (e.g., "72", "10")

### Code Style
- **Python**: Comments use emoji indicators for status: ✅ ✓ ⚠️ ❌ 🟢 🔴
- **JavaScript/React**: Uses ESLint with React hooks and refresh plugins
- **Type Hints**: Used in Python where applicable

### Key Implementation Details

1. **Bristol Stops Database**: Hardcoded list of 77 stops with atco_code, common_name, locality, indicator, latitude, longitude. Covers City Centre, East Bristol, North Bristol, Clifton/Hotwells, South Bristol.

2. **Bus Trail Visualization**: Backend maintains BUS_HISTORY dictionary with last 20 GPS positions per bus. Frontend renders as thick blue Polyline on Leaflet map.

3. **ROI Filtering**: cv_counter.py excludes detections in right 40% of frame (x > 0.6 * width) to avoid counting people on the bus.

4. **Distance Calculation**: Haversine formula for accurate km distances between GPS coordinates.

## Testing Strategy

Currently, the project has **no automated tests**. Testing is done manually:

1. **Backend Testing**: Use `/docs` endpoint (Swagger UI) for API testing at `http://localhost:8000/docs`
2. **Frontend Testing**: Manual browser testing, responsive design verification
3. **CV Testing**: Run with sample videos, verify detection accuracy with visual overlay

### Mock Data
- Frontend includes fallback user location (51.4545, -2.5879) if geolocation denied
- `generate_data.py` creates synthetic training data with realistic distributions

## Security Considerations

⚠️ **WARNING**: Hardcoded credentials in `main.py`:
```python
DB_PARAMS = {
    "host": "localhost", "database": "transight_db", 
    "user": "postgres", "password": "R@jibale3138"
}
BODS_API_KEY = "2bc39438a3eeec844704f182bab7892fea39b8bd"
```

These should be moved to environment variables for production:
```bash
# Database
DB_HOST=localhost
DB_NAME=transight_db
DB_USER=postgres
DB_PASSWORD=your_password

# API Keys
BODS_API_KEY=your_key
```

## External Dependencies

### APIs
- **BODS API**: Bus Open Data Service (UK) - Live vehicle positions via SIRI-VM XML format
- **OpenStreetMap**: Map tiles for frontend

### ML Models
- **YOLOv8 Nano**: Pre-trained on COCO dataset for person detection (class 0)
- **XGBoost**: Trained on synthetic data for arrival prediction

## Troubleshooting

| Issue | Solution |
|-------|----------|
| CV Counter lag | Adjust `FRAME_SKIP` in config (higher = less lag, default: 2) |
| Backend connection failed | Verify backend running on port 8000, check CORS settings |
| Video not found | Place videos in `/videos/` directory or specify full path |
| Geolocation denied | Frontend falls back to Bristol city centre coordinates |
| BODS API fails | Check API key; backend uses cached data as fallback |
| Build errors | Ensure Node.js 18+ and Python 3.8+ installed |

## Version History

- **v3.2.0** (Current): Comprehensive Bristol stops database (77 stops), real-time bus tracking with GPS trails, draggable bottom sheet UI
- Previous versions included TomTom Traffic API integration (removed in current version)
