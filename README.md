# Transight - Intelligent Transit Prediction System

## What This System Does

**Transight** is a real-time bus arrival prediction system for Route 72 in Bristol, UK (Temple Meads to UWE Frenchay). It combines live bus GPS tracking, traffic data, and computer vision to provide accurate arrival time estimates.

### Key Features

**1. Real-Time Bus Tracking**
- Shows live bus locations on a map
- Updates every 10 seconds from BODS (Bus Open Data Service)
- Displays bus speed, direction, and destination

**2. Traffic-Aware Predictions**
- Uses TomTom Traffic API for real-time road conditions
- Calculates traffic delays based on current vs. free-flow speed
- Adjusts ETAs during congestion

**3. Crowd Detection (Computer Vision)**
- YOLOv8 AI model counts people at bus stops
- Accounts for boarding time (4 seconds per person)
- Updates predictions based on queue size

**4. Machine Learning Predictions**
- XGBoost model trained on historical data
- Inputs: traffic delay + crowd count + weather
- Output: predicted arrival delay

**5. Interactive Web Interface**
- Leaflet map showing Route 72 line and stops
- Tap any stop to see approaching buses
- Live ETA breakdown (travel time + traffic + crowd)

---

## How It Works (Simple)

```
User taps "Temple Meads" stop
        |
        v
System fetches:
  - Bus location (BODS API)
  - Traffic speed (TomTom API)
  - Crowd count (Database/Camera)
        |
        v
ML Model calculates:
  ETA = Travel Time + Traffic + Crowd
        |
        v
User sees: "Bus 72 arriving in 9 minutes"
```

---

## Tech Stack

### Backend

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | FastAPI (Python) | REST API server |
| ML Model | XGBoost | Arrival delay prediction |
| Database | PostgreSQL | Store crowd data & predictions |
| Bus Data | BODS API | Real-time bus GPS locations |
| Traffic | TomTom Traffic API | Road speed & congestion |
| Computer Vision | YOLOv8 (Ultralytics) | People counting at stops |

### Frontend

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | React 19 | UI components |
| Build Tool | Vite 7 | Development & bundling |
| UI Library | Material-UI (MUI) v6 | Buttons, cards, icons |
| Maps | Leaflet + React-Leaflet | Interactive map display |
| HTTP Client | Axios | API requests |

### DevOps & Tools

| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.12 | Backend development |
| Language | JavaScript/JSX | Frontend development |
| Package Manager | npm | Frontend dependencies |
| API Testing | Swagger UI (FastAPI) | API documentation |

---

## System Architecture

```
+------------------+     HTTP      +------------------------+
|    FRONTEND      | <----------> |       BACKEND          |
|    (React)       |              |      (FastAPI)         |
|                  |              |                        |
|  +------------+  |              |  +------------------+  |
|  |  Leaflet   |  |              |  |   BODS API       |  |
|  |    Map     |  |              |  |   (Bus GPS)      |  |
|  +------------+  |              |  +------------------+  |
|                  |              |                        |
|  +------------+  |              |  +------------------+  |
|  |   MUI      |  |              |  |  TomTom API      |  |
|  | Components |  |              |  |  (Traffic)       |  |
|  +------------+  |              |  +------------------+  |
|                  |              |                        |
|  +------------+  |              |  +------------------+  |
|  |   Axios    |  |              |  |  YOLO / CV       |  |
|  |  API Calls |  |              |  |  (Crowd)         |  |
|  +------------+  |              |  +------------------+  |
+------------------+              |                        |
                                  |  +------------------+  |
                                  |  |  XGBoost ML      |  |
                                  |  |  (Predict)       |  |
                                  |  +------------------+  |
                                  |                        |
                                  |  +------------------+  |
                                  |  |  PostgreSQL      |  |
                                  |  |  (Database)      |  |
                                  |  +------------------+  |
                                  +------------------------+
```

---

## API Endpoints

### Bus Data
| Endpoint | Method | Description |
|----------|--------|-------------|
| /stop/{stop_id}/buses | GET | Get buses near a specific stop with ETAs |
| /route/72/buses | GET | Get all Route 72 buses |
| /route/72/geometry | GET | Get Route 72 path coordinates |

### Sensor Data
| Endpoint | Method | Description |
|----------|--------|-------------|
| /update-sensor-data | POST | Receive crowd count from CV sensor |

### System
| Endpoint | Method | Description |
|----------|--------|-------------|
| /stops | GET | List all Route 72 stops |
| /health | GET | System status check |

---

## File Structure

```
transight/
|-- main.py                      # FastAPI backend
|-- cv_counter.py               # YOLO computer vision
|-- train_model.py              # XGBoost training script
|-- bus_prediction_model.json   # Trained ML model
|-- historical_bus_data.csv     # Training dataset
|-- yolov8n.pt                  # YOLOv8 weights
|-- README.md                   # This file
|
|-- transight-frontend/         # React frontend
|   |-- src/
|   |   |-- App.jsx            # Main React component
|   |   |-- main.jsx           # React entry point
|   |   |-- index.css          # Global styles
|   |-- package.json           # Node dependencies
|   |-- vite.config.js         # Vite configuration
|
|-- videos/                     # CV input videos
    |-- crowd_quiet.mp4
    |-- crowd_busy.mp4
```

---

## Data Flow Examples

### Without CV Counter (No Camera)
```
User -> Tap Stop -> Backend -> BODS API (bus location)
                              -> TomTom API (traffic)
                              -> Database (crowd = 0)
         |
    ETA = Travel Time + Traffic Delay
```

### With CV Counter (Camera Running)
```
CV Counter -> Detects 8 people -> POST to /update-sensor-data
                                        |
User -> Tap Stop -> Backend -> BODS API (bus location)
                              -> TomTom API (traffic)
                              -> Database (crowd = 8)
         |
    ETA = Travel Time + Traffic Delay + Crowd Delay
```

---

## Key Algorithms

### Traffic Delay Calculation
```python
speed_ratio = current_speed / free_flow_speed

if speed_ratio < 0.3:
    delay = (1 - speed_ratio) * 25  # Severe congestion
elif speed_ratio < 0.6:
    delay = (1 - speed_ratio) * 20  # Heavy traffic
elif speed_ratio < 0.85:
    delay = (1 - speed_ratio) * 15  # Moderate traffic
else:
    delay = 0  # Free flow
```

### ETA Calculation
```python
travel_time = (distance_km / bus_speed_kmh) * 60
crowd_delay = (crowd_count * 4) / 60  # 4 seconds per person

predicted_delay = ML_predict(traffic_delay, crowd_count, weather)

ETA = travel_time + predicted_delay
```

---

## External APIs

### 1. BODS (Bus Open Data Service)
- **Provider:** UK Department for Transport
- **Data:** Real-time bus GPS locations
- **Update:** Every 10 seconds
- **Format:** SIRI-VM XML
- **Cost:** Free

### 2. TomTom Traffic API
- **Provider:** TomTom
- **Data:** Road speed, congestion, traffic delays
- **Endpoint:** Flow Segment Data API
- **Cost:** Free tier (2,500 requests/day)

---

## Machine Learning Model

### Features
| Feature | Description | Source |
|---------|-------------|--------|
| traffic_delay | Minutes of traffic delay | TomTom API |
| crowd_count | People waiting at stop | YOLO/CV |
| is_raining | Weather condition | Optional |

### Target
- **actual_arrival_time:** Minutes bus is delayed

### Model Type
- **XGBoost Regressor**
- Trained on synthetic data
- Saved as `bus_prediction_model.json`

---

## How to Run

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL (optional, works without)

### 1. Backend
```bash
# Install dependencies
pip install fastapi uvicorn psycopg2 requests xgboost pandas ultralytics opencv-python

# Run server
python main.py
```

### 2. Computer Vision (Optional)
```bash
# Terminal 2
python cv_counter.py

# Press '1' for quiet scene
# Press '2' for busy scene
```

### 3. Frontend
```bash
# Terminal 3
cd transight-frontend
npm install
npm run dev

# Open http://localhost:5173
```

---

## System Status

| Component | Status | Notes |
|-----------|--------|-------|
| BODS API | Working | Live bus tracking |
| TomTom API | Working | Real traffic data |
| YOLO/CV | Working | People counting |
| XGBoost ML | Working | Delay prediction |
| Frontend | Working | Interactive map |

---

## Example Output

When user taps "Temple Meads":

```
Temple Meads Station
Route 72 Stop #1

LIVE DATA:
Traffic: 17 km/h (+4 min delay)
Crowd: 8 waiting (Live from camera)
Predicted Delay: 5.3 min

BUS APPROACHING:
Route 72 to UWE Frenchay
Distance: 1.5 km
Speed: 20 km/h
ETA: 9 minutes
```

---

## Credits

- **Bus Data:** Bus Open Data Service (BODS)
- **Traffic Data:** TomTom Developer
- **Computer Vision:** Ultralytics YOLOv8
- **Maps:** OpenStreetMap + Leaflet

---

## License

This is a student/academic project for demonstration purposes.
