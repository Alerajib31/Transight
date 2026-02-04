# Transight - Intelligent Transit Prediction System

## Project Overview

Transight is an AI-powered real-time bus arrival prediction system that combines computer vision, traffic data fusion, and machine learning to provide accurate transit predictions. The system uses YOLOv8 for crowd detection at bus stops, integrates with external traffic and transit APIs (BODS, TomTom), and employs an XGBoost model to predict bus arrival times.

### Key Features
- **Computer Vision Crowd Detection**: Uses YOLOv8 to count people waiting at bus stops
- **Multi-Source Data Fusion**: Combines CV data with traffic conditions and live bus locations
- **AI Prediction**: XGBoost model predicts arrival times based on crowd count, traffic, and weather
- **Interactive Dashboard**: React-based frontend with real-time maps and predictions
- **RESTful API**: FastAPI backend with endpoints for predictions, stops, routes, and live bus data

## Technology Stack

### Backend (Python)
| Component | Technology |
|-----------|------------|
| Web Framework | FastAPI |
| ML/DL | XGBoost, Ultralytics YOLOv8 |
| Database | PostgreSQL (psycopg2) |
| Data Processing | pandas, numpy |
| External APIs | requests (BODS API, TomTom Traffic API) |
| Computer Vision | OpenCV (cv2) |

### Frontend (JavaScript/React)
| Component | Technology |
|-----------|------------|
| Framework | React 19 |
| Build Tool | Vite 7 |
| UI Components | Material-UI (MUI) v6 |
| Maps | Leaflet + React-Leaflet |
| HTTP Client | axios |
| Icons | @mui/icons-material |

## Project Structure

```
c:\Transight/
├── main.py                  # FastAPI backend server - main entry point
├── cv_counter.py            # Computer vision module (YOLOv8 crowd detection)
├── run_all_cameras.py       # Multi-camera launcher for multiple bus stops
├── train_model.py           # XGBoost model training script
├── generate_data.py         # Synthetic training data generator
├── camera_config.json       # Camera and bus stop configuration
├── bus_prediction_model.json # Trained XGBoost model (binary)
├── historical_bus_data.csv  # Training dataset
├── yolov8n.pt              # YOLOv8 Nano model weights
├── package.json            # Root Node.js dependencies (frontend shared)
├── videos/                 # Video files for CV processing
│   ├── 1.mp4              # Stop 001 video
│   └── 2.mp4              # Stop 002 video
├── runs/                   # YOLO training runs (auto-generated)
└── transight-frontend/     # React frontend application
    ├── package.json        # Frontend dependencies
    ├── vite.config.js      # Vite build configuration
    ├── index.html          # HTML entry point
    └── src/
        ├── App.jsx         # Main React component
        ├── main.jsx        # React entry point
        ├── App.css         # Component styles
        └── index.css       # Global styles
```

## Module Descriptions

### 1. Backend Modules (`*.py`)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI application with REST endpoints for predictions, stops, routes, live buses, and analytics. Contains data fusion logic. |
| `cv_counter.py` | YOLOv8-based people detection for bus stops. Sends crowd counts to backend. Supports video files, USB cameras, and RTSP streams. |
| `run_all_cameras.py` | Orchestrates multiple CV counter instances for different bus stops using subprocess. |
| `train_model.py` | Trains XGBoost regression model on historical data to predict arrival times. |
| `generate_data.py` | Generates synthetic training data simulating traffic, crowds, and weather conditions. |

### 2. Frontend Modules (`transight-frontend/src/`)

| File | Purpose |
|------|---------|
| `App.jsx` | Main UI component with map visualization, prediction cards, stop selector, and live bus tracking. Responsive design for mobile/desktop. |
| `main.jsx` | React application bootstrap |

## Configuration Files

### `camera_config.json`
Defines system settings and bus stop configurations:
```json
{
  "system": {
    "backend_url": "http://localhost:8000",
    "update_interval_seconds": 5,
    "frame_skip": 2,
    "display_width": 800
  },
  "bus_stops": [
    {
      "stop_id": "STOP_001",
      "name": "Downtown Station",
      "route_ids": [10, 15, 22],
      "latitude": 51.4496,
      "longitude": -2.5811,
      "camera": {
        "type": "video",      // Options: "video", "usb", "rtsp"
        "source": "1.mp4",    // Video file, camera index, or RTSP URL
        "roi_boundary": 0.6   // Region of interest (exclude bus area)
      }
    }
  ]
}
```

### Database Schema (PostgreSQL)
Table: `prediction_history`
- `bus_stop_id` (TEXT): Stop identifier
- `crowd_count` (INTEGER): People detected
- `traffic_delay` (FLOAT): Traffic delay in minutes
- `dwell_delay` (FLOAT): Boarding time estimate
- `total_prediction` (FLOAT): Final arrival prediction
- `bus_lat`, `bus_lon` (FLOAT): Bus location
- `traffic_status` (TEXT): Free Flow / Moderate / Congested
- `confidence` (FLOAT): Prediction confidence 0-1
- `timestamp` (TIMESTAMP): Record time

## Build and Run Commands

### Prerequisites
- Python 3.8+
- Node.js 18+
- PostgreSQL database
- API Keys: BODS_API_KEY, TomTom_API_KEY (hardcoded in main.py)

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

# Development server
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
python cv_counter.py --stop-id STOP_001 --video 1.mp4

# Multiple cameras
python run_all_cameras.py
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check and system status |
| `/stops` | GET | List all bus stops |
| `/stops/{stop_id}` | GET | Get specific stop details |
| `/routes` | GET | List all routes |
| `/routes/{route_id}` | GET | Get route with stop predictions |
| `/predict/{stop_id}` | GET | Get arrival prediction for stop |
| `/live-buses` | GET | Get live bus locations from BODS |
| `/live-buses/{route_id}` | GET | Get buses for specific route |
| `/nearby-stops` | GET | Find stops near coordinates |
| `/analytics/{stop_id}` | GET | Historical analytics |
| `/update-sensor-data` | POST | Receive CV crowd count data |

## Development Conventions

### Code Style
- **Python**: Follow PEP 8, use type hints where applicable
- **JavaScript/React**: Uses ESLint with React hooks and refresh plugins
- **Comments**: Use emoji indicators for status: ✅ ✓ ⚠️ ❌ 🟢 🔴

### Naming Conventions
- Python: `snake_case` for functions/variables, `PascalCase` for classes
- JavaScript: `camelCase` for variables/functions, `PascalCase` for components
- Bus Stop IDs: `STOP_XXX` format
- Route IDs: Numeric strings (e.g., "72", "10")

### Data Flow
1. CV Counter detects people → Sends `crowd_count` to `/update-sensor-data`
2. Backend fetches traffic data from TomTom API
3. Backend fetches live bus data from BODS API (cached 30s)
4. XGBoost model predicts delay based on crowd + traffic
5. Frontend polls `/predict/{stop_id}` every 10 seconds
6. Frontend displays prediction with map visualization

## Testing Strategy

Currently, the project has **no automated tests**. Testing is done manually:

1. **Backend Testing**: Use `/docs` endpoint (Swagger UI) for API testing
2. **Frontend Testing**: Manual browser testing, responsive design verification
3. **CV Testing**: Run with sample videos, verify detection accuracy

### Mock Data
- Frontend includes mock bus data for when BODS API fails
- `generate_data.py` creates synthetic training data

## Deployment Considerations

### Security Notes (Hardcoded Credentials)
⚠️ **WARNING**: The following sensitive data is hardcoded in `main.py`:
- Database credentials: `DB_PARAMS` (host: localhost, db: transight_db, user: postgres)
- API Keys: `BODS_API_KEY`, `TOMTOM_API_KEY`
- These should be moved to environment variables for production

### Environment Variables (Recommended)
```bash
# Database
DB_HOST=localhost
DB_NAME=transight_db
DB_USER=postgres
DB_PASSWORD=your_password

# API Keys
BODS_API_KEY=your_key
TOMTOM_API_KEY=your_key

# Backend
BACKEND_URL=http://localhost:8000
```

### Production Build
```bash
# Frontend
cd transight-frontend
npm run build
# Output: transight-frontend/dist/

# Backend (use production server)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## External Dependencies

### APIs
- **BODS API**: Bus Open Data Service (UK) - Live vehicle positions
- **TomTom Traffic API**: Real-time traffic flow data
- **OpenStreetMap**: Map tiles for frontend

### ML Model
- **YOLOv8 Nano**: Pre-trained on COCO dataset for person detection
- **XGBoost**: Trained on synthetic data for arrival prediction

## Troubleshooting

| Issue | Solution |
|-------|----------|
| CV Counter lag | Adjust `FRAME_SKIP` in config (higher = less lag) |
| Backend connection failed | Verify backend running on port 8000, check CORS |
| Database errors | Ensure PostgreSQL running, credentials correct |
| BODS API fails | Check API key, uses cached data as fallback |
| Video not found | Place videos in `/videos/` directory or specify full path |
| Geolocation denied | Frontend shows error, does not fall back to default |
