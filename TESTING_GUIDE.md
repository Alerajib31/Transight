# TESTING & VALIDATION GUIDE

## ✅ Pre-Deployment Testing Checklist

### 1. Backend API Testing

#### Start Backend
```bash
cd C:\Transight
uvicorn main:app --reload
```

#### Test Health Endpoint
```bash
curl http://localhost:8000/health

# Expected Response:
# {
#   "status": "healthy",
#   "timestamp": "2026-01-30T10:30:00",
#   "model_loaded": true,
#   "stops_configured": 3,
#   "routes_configured": 2
# }
```

#### Test Stops Endpoint
```bash
curl http://localhost:8000/stops

# Should return all configured stops
```

#### Test Prediction Endpoint
```bash
curl http://localhost:8000/predict/STOP_001

# Expected when data available:
# {
#   "stop_id": "STOP_001",
#   "stop_name": "Temple Meads Station",
#   "crowd_count": 8,
#   "traffic_delay": 5.2,
#   "dwell_delay": 0.4,
#   "total_time_min": 5,
#   "confidence": 0.87
# }
```

#### Test Nearby Stops
```bash
curl "http://localhost:8000/nearby-stops?latitude=51.45&longitude=-2.58&radius=2.0"

# Should return stops within 2km radius sorted by distance
```

#### Test Live Buses (requires BODS API)
```bash
curl http://localhost:8000/live-buses

# Expected: Array of bus locations with routes
```

---

### 2. CV Counter Testing

#### Test Single Video
```bash
python cv_counter.py --stop-id STOP_001 --video 1.mp4

# Should show:
# ✅ Loading AI Model...
# ✅ Opening video: C:\Transight\videos\1.mp4
# ✅ Monitoring Bus Stop: STOP_001
# ✅ Starting Detection. Press 'q' to quit.
# ✅ Video window with person count overlay
# ✅ Every 5 seconds: "✓ Sent to backend: Stop STOP_001 | Count: X"
```

#### Expected Output Format
```
Loading AI Model...
📹 Opening video: C:\Transight\videos\1.mp4
🚏 Monitoring Bus Stop: STOP_001
Starting Detection. Press 'q' to quit.
✓ Sent to backend: Stop STOP_001 | Count: 3
✓ Sent to backend: Stop STOP_001 | Count: 5
✓ Sent to backend: Stop STOP_001 | Count: 4
```

#### Verify Database Update
```bash
# In PostgreSQL client:
SELECT * FROM prediction_history 
WHERE bus_stop_id = 'STOP_001'
ORDER BY timestamp DESC LIMIT 5;

# Should see new rows every 5 seconds
```

#### Test Multi-Camera
```bash
python run_all_cameras.py

# Should launch 2 video windows simultaneously
# Terminal output shows both STOP_001 and STOP_002 updates
```

---

### 3. Frontend Testing

#### Start Frontend Dev Server
```bash
cd C:\Transight\transight-frontend
npm run dev

# Output:
# VITE v... ready in X ms
# ➜ Local: http://localhost:5173/
```

#### Test Page Load
- Navigate to `http://localhost:5173`
- Should see:
  - ✅ Transight AI header
  - ✅ Map displays (Leaflet)
  - ✅ User location marker (blue)
  - ✅ Bus stop markers (red)
  - ✅ Prediction card (right sidebar or bottom sheet)

#### Test Stop Selection
- Click dropdown "Bus Stop"
- Should show: Temple Meads, Cabot Circus, St Nicholas Market
- Select different stop
- Map should update
- Prediction should refresh
- Should see "✅ Refreshing" spinner

#### Test Location Services
- Browser asks for geolocation permission
- If denied: uses default (51.4496, -2.5811)
- If allowed: shows actual location
- "Nearby Stops" section shows stops within 2km

#### Test Auto-Refresh
- Click refresh icon in header
- Spinner appears for 1-2 seconds
- Data updates
- Auto-refresh should run every 10 seconds

#### Test Responsive Design
- Resize window to mobile (375px)
- Should show:
  - Map full width
  - Bottom drawer with prediction
- Resize to tablet (768px)
- Should show:
  - Sidebar (45% width)
  - Map (55% width)
- Resize to desktop (1920px)
- Should show:
  - Sidebar (420px fixed)
  - Map (remaining width)

---

### 4. Data Fusion Testing

#### Verify Multiple Data Sources
```bash
# In terminal during CV Counter + Backend running:
# You should see:
# 1. CV Counter: "✓ Sent to backend" messages
# 2. Frontend shows: Traffic status (Moderate, Free Flow, etc.)
# 3. Frontend shows: ETA calculation
# 4. Database: New rows with confidence scores
```

#### Test Confidence Scoring
```bash
# Low crowd (< 5 people):
GET /predict/STOP_001
# confidence should be ~0.95 (high)

# High crowd (> 30 people):
GET /predict/STOP_001
# confidence should be ~0.80-0.90
```

#### Test Dwell Time Calculation
```python
# 0 people: dwell_delay = 0.5 min
# 10 people: dwell_delay = 1.0 min
# 20 people: dwell_delay = 1.5 min
# 50 people: dwell_delay = 3.0 min

# Verify: dwell_delay in prediction response matches: 0.5 + (0.05 * crowd_count)
```

---

### 5. Model Validation

#### Check XGBoost Model
```bash
import xgboost as xgb
import pandas as pd

bst = xgb.Booster()
bst.load_model("bus_prediction_model.json")

# Test prediction
features = pd.DataFrame([[8, 25, 10]], columns=['crowd_count', 'traffic_speed', 'scheduled_interval'])
dmatrix = xgb.DMatrix(features)
prediction = float(bst.predict(dmatrix)[0])

print(f"Prediction: {prediction} minutes")
# Should be between 0-30 minutes
```

#### Validate Features
```bash
# Check that model receives correct features:
curl -X POST http://localhost:8000/update-sensor-data \
  -H "Content-Type: application/json" \
  -d '{"stop_id": "STOP_001", "crowd_count": 8}'

# Should return: "new_prediction": <integer between 1-30>
```

---

## 🧪 PERFORMANCE TESTING

### Load Test API
```bash
# Using Apache Bench (ab)
ab -n 1000 -c 10 http://localhost:8000/predict/STOP_001

# Expected results:
# - Response time: <100ms per request
# - Failed requests: 0
# - Throughput: >100 req/sec
```

### Database Performance
```sql
-- Check slow queries
EXPLAIN ANALYZE
SELECT * FROM prediction_history 
WHERE bus_stop_id = 'STOP_001' 
ORDER BY timestamp DESC LIMIT 1;

-- Should use index, <10ms
```

### Memory Usage
```bash
# Monitor with: Task Manager > Performance tab
# Expected at full load:
# - Python backend: 150-250MB
# - React dev server: 100-150MB
# - Total: <500MB
```

---

## 📊 INTEGRATION TESTING

### Test Full Pipeline

#### Step 1: Start Services
```bash
# Terminal 1: Backend
uvicorn main:app --reload

# Terminal 2: CV Counter
python cv_counter.py --stop-id STOP_001 --video 1.mp4

# Terminal 3: Frontend
cd transight-frontend && npm run dev
```

#### Step 2: Verify Data Flow
1. CV Counter detects people in video
2. Sends to backend: {"stop_id": "STOP_001", "crowd_count": 8}
3. Backend fetches traffic from TomTom
4. Backend runs XGBoost prediction
5. Backend saves to database
6. Frontend queries prediction
7. Frontend displays ETA

#### Step 3: Check Each Component
```bash
# CV Counter terminal:
✓ Sent to backend: Stop STOP_001 | Count: 8

# Backend logs:
POST /update-sensor-data - 200 OK

# Database:
SELECT COUNT(*) FROM prediction_history;
-- Should increment every 5 seconds

# Frontend:
- Displays "8 minutes" ✓
- Shows "Moderate" traffic ✓
- Shows "0.4 min" dwell delay ✓
- Shows "87%" confidence ✓
```

---

## ⚠️ ERROR SCENARIOS

### Scenario 1: Backend Not Running
**Error:** "✗ Backend connection failed: Connection refused"
**Solution:** 
```bash
uvicorn main:app --reload
```

### Scenario 2: Video File Not Found
**Error:** "FileNotFoundError: Video '1.mp4' not found"
**Solution:**
```bash
# Check file exists:
ls C:\Transight\videos\1.mp4

# If missing, copy video:
cp your_video.mp4 C:\Transight\videos\1.mp4
```

### Scenario 3: Model Not Loaded
**Error:** "⚠️ WARNING: AI Model not found"
**Solution:**
```bash
python train_model.py
# This retrains and saves bus_prediction_model.json
```

### Scenario 4: Database Connection Failed
**Error:** "psycopg2.Error: Connection refused"
**Solution:**
```bash
# Check PostgreSQL running:
pg_isready -h localhost -p 5432

# If not running:
# Windows: Services → PostgreSQL → Start
# Linux: sudo systemctl start postgresql
```

### Scenario 5: API Key Invalid
**Error:** "BODS API returned 401" or "TomTom API Error"
**Solution:**
- Check API keys in main.py:
  - BODS_API_KEY
  - TOMTOM_API_KEY
- Verify keys are valid and not expired

### Scenario 6: Lag in Video Detection
**Error:** Video plays slowly, detection is sluggish
**Solution:**
```python
# Increase frame skip in cv_counter.py
FRAME_SKIP = 3  # was 2
# This reduces processing to every 3rd frame
```

---

## ✅ VALIDATION CHECKLIST

### Backend
- [ ] API starts without errors
- [ ] Health endpoint returns 200
- [ ] Stops endpoint returns 3 stops
- [ ] Prediction endpoint works
- [ ] Database connects successfully
- [ ] XGBoost model loads
- [ ] API response time < 500ms

### CV Counter
- [ ] Video file loads
- [ ] YOLO detects people
- [ ] Sends data to backend
- [ ] Updates database every 5 sec
- [ ] ROI filtering works (no driver counted)
- [ ] Frame skipping reduces lag
- [ ] Multi-camera works simultaneously

### Frontend
- [ ] Page loads at localhost:5173
- [ ] Map displays correctly
- [ ] Prediction card shows data
- [ ] Stop dropdown works
- [ ] Location services work
- [ ] Auto-refresh works
- [ ] Responsive on all screen sizes

### Data Fusion
- [ ] CV data arrives at backend
- [ ] Traffic data fetched correctly
- [ ] Dwell time calculated properly
- [ ] Confidence score displayed
- [ ] Database has complete records
- [ ] Predictions are reasonable (1-30 min)

### Performance
- [ ] API response time < 500ms
- [ ] Database queries < 50ms
- [ ] CV detection 5-10 FPS
- [ ] Memory usage < 500MB
- [ ] No memory leaks after 1 hour
- [ ] Handles 100+ concurrent users

---

## 📈 SUCCESS METRICS

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| API Availability | 99.9% | TBD | ⏳ |
| Prediction Accuracy | >85% | TBD | ⏳ |
| Response Time | <500ms | TBD | ⏳ |
| MTBF (Mean Time Between Failures) | >24h | TBD | ⏳ |
| Data Freshness | <5 sec | TBD | ⏳ |
| User Satisfaction | >4/5 | TBD | ⏳ |

---

## 🔄 CONTINUOUS TESTING

### Daily Checks
- [ ] All APIs responding
- [ ] Database not full
- [ ] No error logs
- [ ] Model accuracy > 85%

### Weekly Checks
- [ ] Load test (1000 concurrent users)
- [ ] Rerun full pipeline test
- [ ] Check API key expiry
- [ ] Review prediction accuracy

### Monthly Checks
- [ ] Retrain model with new data
- [ ] Security audit
- [ ] Database optimization
- [ ] Performance benchmarking

---

**Testing Phase: READY ✅**

All components implemented and ready for validation.
