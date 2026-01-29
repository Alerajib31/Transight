from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
import requests
import xgboost as xgb
import pandas as pd
import time
import json
import os

# --- CONFIGURATION ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Database Credentials
DB_PARAMS = {
    "host": "localhost", "database": "transight_db", "user": "postgres", "password": "R@jibale3138"
}

# API Keys
BODS_API_KEY = "2bc39438a3eeec844704f182bab7892fea39b8bd"
TOMTOM_API_KEY = "IgrkN0Ci9H94UGQWLoBSpzSFEycU8Xiy"

# --- LOAD AI MODEL ---
model_path = "bus_prediction_model.json"
bst = None

if os.path.exists(model_path):
    print("🧠 Loading XGBoost Brain...")
    bst = xgb.Booster()
    bst.load_model(model_path)
else:
    print("⚠️ WARNING: AI Model not found. Please run train_model.py")

# --- DATA MODELS ---
class SensorData(BaseModel):
    stop_id: str
    crowd_count: int

# --- 1. SENSOR UPDATE ENDPOINT (Called by CV Counter) ---
@app.post("/update-sensor-data")
def update_sensor(data: SensorData):
    """
    DATA FUSION ENGINE:
    1. Receives Crowd Count (Vision)
    2. Fetches Traffic Speed (TomTom)
    3. Predicts Delay (XGBoost)
    4. Saves to DB
    """
    try:
        # A. GET REAL TRAFFIC (Fixed Lat/Lon for this Stop ID for demo)
        # In full version, fetch lat/lon from DB based on stop_id
        lat, lon = 51.4496, -2.5811 
        traffic_data = get_real_traffic(lat, lon)
        traffic_speed = traffic_data.get('speed', 30) # Default 30km/h
        
        # B. PREPARE AI INPUT
        # Model expects: [crowd_count, traffic_speed, scheduled_interval]
        features = pd.DataFrame([[data.crowd_count, traffic_speed, 10]], 
                                columns=['crowd_count', 'traffic_speed', 'scheduled_interval'])
        
        # C. RUN PREDICTION
        predicted_delay = 0
        if bst:
            dmatrix = xgb.DMatrix(features)
            predicted_delay = float(bst.predict(dmatrix)[0])
        
        # D. SAVE TO DATABASE
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        
        # Calculate Dwell Delay (Simple logic: 3s per person)
        dwell_delay = data.crowd_count * (3.0 / 60.0) 
        total_prediction = max(0, int(predicted_delay + dwell_delay))

        # Insert/Update logic
        query = """
            INSERT INTO prediction_history 
            (bus_stop_id, crowd_count, traffic_delay, dwell_delay, total_prediction, bus_lat, bus_lon, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """
        cur.execute(query, (
            data.stop_id, 
            data.crowd_count, 
            predicted_delay, 
            dwell_delay, 
            total_prediction,
            lat, lon
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "Fusion Complete", "new_prediction": total_prediction}

    except Exception as e:
        print(f"❌ Fusion Error: {e}")
        return {"error": str(e)}

# --- 2. REAL TRAFFIC (Helper) ---
def get_real_traffic(lat, lon):
    base_url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
    params = {"key": TOMTOM_API_KEY, "point": f"{lat},{lon}"}
    try:
        resp = requests.get(base_url, params=params, timeout=2)
        if resp.status_code == 200:
            flow = resp.json().get('flowSegmentData', {})
            return {"speed": flow.get('currentSpeed', 0)}
    except:
        pass
    return {"speed": 0}

# --- 3. FRONTEND ENDPOINTS ---
@app.get("/predict/{stop_id}")
def get_prediction(stop_id: str):
    # READS from DB (same as before)
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("""
            SELECT traffic_delay, dwell_delay, total_prediction, crowd_count 
            FROM prediction_history WHERE bus_stop_id = %s 
            ORDER BY timestamp DESC LIMIT 1
        """, (stop_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            return {
                "stop_id": stop_id,
                "traffic_delay": row[0],
                "dwell_delay": row[1],
                "total_time_min": row[2],
                "crowd_count": row[3],
                "crowd_level": "High" if row[3] > 10 else "Low"
            }
        return {"error": "No data"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/live-locations")
def live_locations():
    # Insert your BODS Logic from previous answer here
    # (Kept short for clarity, but use the BODS function provided previously)
    return {"status": "active", "buses": []} # Placeholder