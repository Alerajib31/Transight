from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import psycopg2
import requests
import xgboost as xgb
import pandas as pd
import time
import json
import os
from datetime import datetime, timedelta

# --- CONFIGURATION ---
app = FastAPI(
    title="Transight Transit API",
    description="Intelligent real-time transit prediction system",
    version="1.0.0"
)

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

# Cache for BODS data (refresh every 30 seconds)
BODS_CACHE = {"data": None, "timestamp": 0}
CACHE_EXPIRY = 30

# Bus Stop Database (Replace with actual DB queries)
BUS_STOPS = {
    "STOP_001": {"name": "Temple Meads Station", "lat": 51.4496, "lon": -2.5811, "routes": [72, 10, 15]},
    "STOP_002": {"name": "Cabot Circus", "lat": 51.4545, "lon": -2.5879, "routes": [72, 20]},
    "STOP_003": {"name": "St Nicholas Market", "lat": 51.4510, "lon": -2.5880, "routes": [10, 72]},
}

ROUTES = {
    "72": {"name": "Route 72: Temple Meads → Cabot Circus", "stops": ["STOP_001", "STOP_002", "STOP_003"]},
    "10": {"name": "Route 10: Bristol Airport", "stops": ["STOP_001", "STOP_003"]},
}

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

class BusLocation(BaseModel):
    bus_id: str
    route_id: str
    latitude: float
    longitude: float
    speed: float
    occupancy: int

class PredictionResponse(BaseModel):
    stop_id: str
    stop_name: str
    crowd_count: int
    traffic_delay: float
    dwell_delay: float
    total_time_min: int
    crowd_level: str
    traffic_status: str
    eta_time: str
    confidence: float

# --- 1. DATA FUSION ENGINE (BODS + Traffic + CV) ---
def fetch_bods_data():
    """
    Fetch live bus data from BODS API
    Returns cached data if fresh, otherwise fetches new data
    """
    global BODS_CACHE
    
    # Return cached data if fresh
    if BODS_CACHE["data"] and (time.time() - BODS_CACHE["timestamp"]) < CACHE_EXPIRY:
        return BODS_CACHE["data"]
    
    try:
        # BODS API endpoint for live vehicle positions
        url = "https://api.bushesdata.org.uk/api/v1/datafeed"
        headers = {"X-API-Key": BODS_API_KEY}
        params = {"operatorRef": "all"}
        
        response = requests.get(url, headers=headers, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            BODS_CACHE["data"] = data
            BODS_CACHE["timestamp"] = time.time()
            return data
    except Exception as e:
        print(f"⚠️ BODS API Error: {e}")
    
    return BODS_CACHE.get("data", [])  # Return cached if API fails


def get_traffic_data(lat: float, lon: float) -> dict:
    """
    Fetch real-time traffic data from TomTom API
    Returns speed and traffic status
    """
    base_url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
    params = {"key": TOMTOM_API_KEY, "point": f"{lat},{lon}"}
    
    try:
        resp = requests.get(base_url, params=params, timeout=2)
        if resp.status_code == 200:
            flow = resp.json().get('flowSegmentData', {})
            speed = flow.get('currentSpeed', 0)
            
            # Classify traffic status
            if speed > 50:
                status = "Free Flow"
            elif speed > 30:
                status = "Moderate"
            else:
                status = "Congested"
            
            return {"speed": speed, "status": status}
    except Exception as e:
        print(f"⚠️ TomTom API Error: {e}")
    
    return {"speed": 0, "status": "Unknown"}


def calculate_dwell_time(crowd_count: int) -> float:
    """
    Estimate passenger boarding time based on crowd
    Formula: base_time + (per_person_time * crowd_count)
    """
    base_time = 0.5  # 30 seconds base boarding time
    per_person_time = 0.05  # 3 seconds per person
    dwell_time = base_time + (per_person_time * crowd_count)
    return dwell_time / 60  # Convert to minutes


def get_confidence_score(crowd_count: int, traffic_status: str) -> float:
    """
    Calculate confidence in prediction based on data quality
    """
    confidence = 0.85  # Base confidence
    
    # Adjust based on crowd size
    if 0 < crowd_count < 50:
        confidence += 0.10
    elif crowd_count > 50:
        confidence -= 0.05
    
    # Adjust based on traffic
    if traffic_status == "Free Flow":
        confidence += 0.05
    elif traffic_status == "Congested":
        confidence -= 0.10
    
    return min(0.99, max(0.5, confidence))


# --- 2. SENSOR UPDATE ENDPOINT (Called by CV Counter) ---
@app.post("/update-sensor-data")
def update_sensor(data: SensorData):
    """
    DATA FUSION ENGINE:
    1. Receives Crowd Count (CV Vision)
    2. Fetches Traffic Speed (TomTom)
    3. Fetches Bus Location (BODS)
    4. Predicts Delay (XGBoost)
    5. Saves to DB
    """
    try:
        # A. GET STOP LOCATION
        stop_info = BUS_STOPS.get(data.stop_id, {})
        lat, lon = stop_info.get("lat", 51.4496), stop_info.get("lon", -2.5811)
        
        # B. GET REAL TRAFFIC
        traffic_data = get_traffic_data(lat, lon)
        traffic_speed = traffic_data.get('speed', 30)
        traffic_status = traffic_data.get('status', 'Unknown')
        
        # C. PREPARE AI INPUT
        features = pd.DataFrame(
            [[data.crowd_count, traffic_speed, 10]],
            columns=['crowd_count', 'traffic_speed', 'scheduled_interval']
        )
        
        # D. RUN PREDICTION
        predicted_delay = 0
        if bst:
            dmatrix = xgb.DMatrix(features)
            predicted_delay = float(bst.predict(dmatrix)[0])
        
        # E. CALCULATE DWELL TIME
        dwell_delay = calculate_dwell_time(data.crowd_count)
        total_prediction = max(0, int(predicted_delay + dwell_delay))
        
        # F. CALCULATE CONFIDENCE
        confidence = get_confidence_score(data.crowd_count, traffic_status)
        
        # G. SAVE TO DATABASE
        try:
            conn = psycopg2.connect(**DB_PARAMS)
            cur = conn.cursor()
            
            query = """
                INSERT INTO prediction_history 
                (bus_stop_id, crowd_count, traffic_delay, dwell_delay, total_prediction, 
                 bus_lat, bus_lon, traffic_status, confidence, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            cur.execute(query, (
                data.stop_id,
                data.crowd_count,
                predicted_delay,
                dwell_delay,
                total_prediction,
                lat, lon,
                traffic_status,
                confidence
            ))
            
            conn.commit()
            cur.close()
            conn.close()
        except psycopg2.Error as e:
            print(f"⚠️ Database Error: {e}")
        
        return {
            "status": "Fusion Complete",
            "new_prediction": total_prediction,
            "confidence": round(confidence, 2),
            "traffic_status": traffic_status
        }

    except Exception as e:
        print(f"❌ Fusion Error: {e}")
        return {"error": str(e)}

# --- 3. PREDICTION ENDPOINTS (For Frontend) ---

@app.get("/predict/{stop_id}", response_model=Optional[PredictionResponse])
def get_prediction(stop_id: str):
    """Get latest prediction for a bus stop"""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("""
            SELECT traffic_delay, dwell_delay, total_prediction, crowd_count, traffic_status, confidence
            FROM prediction_history WHERE bus_stop_id = %s 
            ORDER BY timestamp DESC LIMIT 1
        """, (stop_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            eta_time = (datetime.now() + timedelta(minutes=int(row[2]))).strftime("%H:%M")
            crowd_level = "High" if row[3] > 10 else "Low"
            
            return PredictionResponse(
                stop_id=stop_id,
                stop_name=BUS_STOPS.get(stop_id, {}).get("name", "Unknown Stop"),
                crowd_count=row[3],
                traffic_delay=round(row[0], 2),
                dwell_delay=round(row[1], 2),
                total_time_min=int(row[2]),
                crowd_level=crowd_level,
                traffic_status=row[4] or "Unknown",
                eta_time=eta_time,
                confidence=round(row[5], 2) if row[5] else 0.85
            )
        return None
    except Exception as e:
        print(f"Error fetching prediction: {e}")
        return None


@app.get("/stops")
def get_all_stops():
    """Get all bus stops with their information"""
    return {
        "stops": [
            {
                "stop_id": stop_id,
                "name": info["name"],
                "latitude": info["lat"],
                "longitude": info["lon"],
                "routes": info["routes"]
            }
            for stop_id, info in BUS_STOPS.items()
        ]
    }


@app.get("/stops/{stop_id}")
def get_stop_detail(stop_id: str):
    """Get detailed information about a specific stop"""
    if stop_id not in BUS_STOPS:
        raise HTTPException(status_code=404, detail="Stop not found")
    
    stop_info = BUS_STOPS[stop_id]
    return {
        "stop_id": stop_id,
        "name": stop_info["name"],
        "latitude": stop_info["lat"],
        "longitude": stop_info["lon"],
        "routes": stop_info["routes"],
        "prediction": get_prediction(stop_id)
    }


@app.get("/routes")
def get_all_routes():
    """Get all transit routes"""
    return {
        "routes": [
            {
                "route_id": route_id,
                "name": info["name"],
                "stops": info["stops"]
            }
            for route_id, info in ROUTES.items()
        ]
    }


@app.get("/routes/{route_id}")
def get_route_detail(route_id: str):
    """Get detailed information about a specific route"""
    if route_id not in ROUTES:
        raise HTTPException(status_code=404, detail="Route not found")
    
    route_info = ROUTES[route_id]
    stops_data = []
    
    for stop_id in route_info["stops"]:
        stop_info = BUS_STOPS.get(stop_id, {})
        prediction = get_prediction(stop_id)
        stops_data.append({
            "stop_id": stop_id,
            "name": stop_info.get("name"),
            "latitude": stop_info.get("lat"),
            "longitude": stop_info.get("lon"),
            "prediction": prediction
        })
    
    return {
        "route_id": route_id,
        "name": route_info["name"],
        "stops": stops_data
    }


@app.get("/live-buses")
def get_live_buses():
    """Get live bus locations and status"""
    try:
        bods_data = fetch_bods_data()
        buses = []
        
        if bods_data and isinstance(bods_data, list):
            for vehicle in bods_data[:10]:  # Limit to 10 buses for demo
                try:
                    buses.append({
                        "bus_id": vehicle.get("vehicle", {}).get("id", "Unknown"),
                        "route": vehicle.get("monitoredVehicleJourney", {}).get("lineRef", "Unknown"),
                        "latitude": vehicle.get("monitoredVehicleJourney", {}).get("vehicleLocation", {}).get("latitude", 0),
                        "longitude": vehicle.get("monitoredVehicleJourney", {}).get("vehicleLocation", {}).get("longitude", 0),
                        "occupancy": vehicle.get("monitoredVehicleJourney", {}).get("occupancy", "Unknown"),
                        "delay": vehicle.get("monitoredVehicleJourney", {}).get("delay", "PT0S"),
                        "speed": vehicle.get("monitoredVehicleJourney", {}).get("speed", 0)
                    })
                except Exception as e:
                    print(f"Error parsing BODS vehicle: {e}")
        
        return {
            "buses": buses,
            "timestamp": datetime.now().isoformat(),
            "data_source": "BODS API"
        }
    except Exception as e:
        print(f"Error fetching live buses: {e}")
        return {"buses": [], "timestamp": datetime.now().isoformat(), "error": str(e)}


@app.get("/live-buses/{route_id}")
def get_live_buses_by_route(route_id: str):
    """Get live buses for a specific route"""
    all_buses = get_live_buses()
    filtered_buses = [bus for bus in all_buses.get("buses", []) if route_id in str(bus.get("route", ""))]
    
    return {
        "route_id": route_id,
        "buses": filtered_buses,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/nearby-stops")
def get_nearby_stops(latitude: float, longitude: float, radius: float = 1.0):
    """
    Get bus stops within a specified radius (km) of user location
    """
    from math import radians, cos, sin, asin, sqrt
    
    def haversine(lon1, lat1, lon2, lat2):
        """Calculate distance between two points on earth (in km)"""
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r
    
    nearby = []
    for stop_id, stop_info in BUS_STOPS.items():
        dist = haversine(longitude, latitude, stop_info["lon"], stop_info["lat"])
        if dist <= radius:
            prediction = get_prediction(stop_id)
            nearby.append({
                "stop_id": stop_id,
                "name": stop_info["name"],
                "distance_km": round(dist, 2),
                "latitude": stop_info["lat"],
                "longitude": stop_info["lon"],
                "routes": stop_info["routes"],
                "prediction": prediction
            })
    
    nearby.sort(key=lambda x: x["distance_km"])
    return {"nearby_stops": nearby, "user_location": {"latitude": latitude, "longitude": longitude}}


@app.get("/analytics/{stop_id}")
def get_analytics(stop_id: str, hours: int = 24):
    """Get historical analytics for a stop"""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        
        query = f"""
            SELECT 
                AVG(crowd_count) as avg_crowd,
                MAX(crowd_count) as max_crowd,
                AVG(traffic_delay) as avg_traffic,
                AVG(dwell_delay) as avg_dwell,
                AVG(total_prediction) as avg_eta,
                COUNT(*) as records
            FROM prediction_history 
            WHERE bus_stop_id = %s 
            AND timestamp > NOW() - INTERVAL '{hours} hours'
        """
        cur.execute(query, (stop_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return {
                "stop_id": stop_id,
                "period_hours": hours,
                "average_crowd": round(row[0], 1) if row[0] else 0,
                "max_crowd": int(row[1]) if row[1] else 0,
                "average_traffic_delay": round(row[2], 2) if row[2] else 0,
                "average_dwell_delay": round(row[3], 2) if row[3] else 0,
                "average_eta": round(row[4], 2) if row[4] else 0,
                "total_records": row[5]
            }
        return {"error": "No data available"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
def health_check():
    """API health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model_loaded": bst is not None,
        "stops_configured": len(BUS_STOPS),
        "routes_configured": len(ROUTES)
    }