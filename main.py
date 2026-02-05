from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import psycopg2
import requests
import xgboost as xgb
import pandas as pd
import time
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt

# --- CONFIGURATION ---
app = FastAPI(
    title="Transight Transit API",
    description="Real-time bus tracking with Modular ID System",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Database Configuration
DB_PARAMS = {
    "host": "localhost", "database": "transight_db", "user": "postgres", "password": "R@jibale3138"
}

# API Keys (PRESERVED - DO NOT DELETE)
BODS_API_KEY = "2bc39438a3eeec844704f182bab7892fea39b8bd"
TOMTOM_API_KEY = "IgrkN0Ci9H94UGQWLoBSpzSFEycU8Xiy"  # Replace with actual TomTom API key

# Target Routes Filter
TARGET_ROUTES = ["72", "76"]

# ==========================================
# MODULAR STOP DIRECTORY (The "Registry")
# ==========================================
# Easy to add new stops - just add a new entry here
STOP_DIRECTORY = {
    "BST-001": {
        "name": "Temple Meads",
        "lat": 51.4496,
        "lng": -2.5811,
        "atco_code": "01000053220"
    },
    "BST-002": {
        "name": "Cabot Circus",
        "lat": 51.4545,
        "lng": -2.5879,
        "atco_code": "01000588088"
    },
    "BST-003": {
        "name": "Clifton Down",
        "lat": 51.4645,
        "lng": -2.6098,
        "atco_code": "01000058001"
    },
    # Future stops can be added here easily following the same pattern
}

# Cache
STOPS_CACHE = {"data": None, "timestamp": 0}
STOPS_CACHE_EXPIRY = 600  # 10 minutes
BUSES_CACHE = {"buses": {}, "timestamp": 0}
BUS_HISTORY = {}

# Load AI model
model_path = "bus_prediction_model.json"
bst = None
if os.path.exists(model_path):
    bst = xgb.Booster()
    bst.load_model(model_path)
    print(f"✅ ML Model loaded: {model_path}")

# --- HELPER FUNCTIONS ---

def haversine(lon1, lat1, lon2, lat2):
    """Calculate distance in km between two coordinates."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c


def get_tomtom_traffic(lat: float, lng: float):
    """
    Fetch real-time traffic data from TomTom API.
    Returns traffic delay in minutes and current speed.
    """
    try:
        # TomTom Flow Segment Data API
        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        params = {
            "key": TOMTOM_API_KEY,
            "point": f"{lat},{lng}"
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            flow = data.get("flowSegmentData", {})
            
            current_speed = flow.get("currentSpeed", 0)
            free_flow_speed = flow.get("freeFlowSpeed", 0)
            
            # Calculate delay: if current_speed is significantly lower than free_flow_speed
            if free_flow_speed > 0 and current_speed > 0:
                speed_ratio = current_speed / free_flow_speed
                if speed_ratio < 0.5:
                    # Heavy traffic - estimate 10-20 min delay
                    delay_min = round((1 - speed_ratio) * 20, 1)
                elif speed_ratio < 0.8:
                    # Moderate traffic - estimate 5-10 min delay
                    delay_min = round((1 - speed_ratio) * 15, 1)
                else:
                    # Light traffic
                    delay_min = 0
            else:
                delay_min = 0
                
            return {
                "traffic_delay_min": delay_min,
                "current_speed_kph": current_speed,
                "free_flow_speed_kph": free_flow_speed,
                "congestion_level": flow.get("confidence", 0),
                "status": "success"
            }
        else:
            print(f"TomTom API error: {response.status_code}")
            return {
                "traffic_delay_min": 0,
                "current_speed_kph": 0,
                "free_flow_speed_kph": 0,
                "congestion_level": 0,
                "status": f"api_error_{response.status_code}"
            }
    except Exception as e:
        print(f"TomTom fetch error: {e}")
        return {
            "traffic_delay_min": 0,
            "current_speed_kph": 0,
            "free_flow_speed_kph": 0,
            "congestion_level": 0,
            "status": "error"
        }


def predict_arrival_delay(traffic_delay: float, crowd_count: int, is_raining: bool = False):
    """
    Use XGBoost model to predict arrival delay.
    Features: traffic_delay, crowd_count, is_raining
    """
    if bst is None:
        # Fallback calculation if model not available
        crowd_delay = (crowd_count * 4) / 60  # 4 seconds per person
        rain_delay = 2 if is_raining else 0
        return traffic_delay + crowd_delay + rain_delay
    
    try:
        # Prepare features for model
        features = pd.DataFrame([{
            "traffic_delay": traffic_delay,
            "crowd_count": crowd_count,
            "is_raining": int(is_raining)
        }])
        
        dmatrix = xgb.DMatrix(features)
        prediction = bst.predict(dmatrix)[0]
        return round(float(prediction), 2)
    except Exception as e:
        print(f"Prediction error: {e}")
        # Fallback
        crowd_delay = (crowd_count * 4) / 60
        return traffic_delay + crowd_delay


def save_prediction_to_db(stop_id: str, stop_name: str, crowd_count: int, 
                          traffic_delay: float, predicted_delay: float, 
                          lat: float, lng: float):
    """Save prediction record to database."""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO prediction_history 
            (bus_stop_id, crowd_count, traffic_delay, total_prediction, 
             bus_lat, bus_lon, traffic_status, confidence, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            stop_id, crowd_count, traffic_delay, predicted_delay,
            lat, lng, 
            "Live TomTom", 
            0.85,
            datetime.now()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Database error: {e}")
        return False


# --- BODS BUS API ---

def parse_siri_xml(xml_text):
    """Parse SIRI-VM XML from BODS API."""
    buses = []
    try:
        root = ET.fromstring(xml_text)
        ns = {'siri': 'http://www.siri.org.uk/siri'}
        
        for vehicle in root.findall('.//siri:VehicleActivity', ns):
            try:
                journey = vehicle.find('.//siri:MonitoredVehicleJourney', ns)
                if journey is None:
                    continue
                
                # Get route number
                route_elem = journey.find('siri:PublishedLineName', ns)
                if route_elem is None:
                    route_elem = journey.find('siri:LineRef', ns)
                route = route_elem.text if route_elem is not None else "Unknown"
                
                # FILTER: Only keep target routes (72 & 76)
                if route not in TARGET_ROUTES:
                    continue
                
                location = journey.find('.//siri:VehicleLocation', ns)
                if location is None:
                    continue
                
                lat_elem = location.find('siri:Latitude', ns)
                lon_elem = location.find('siri:Longitude', ns)
                if lat_elem is None or lon_elem is None:
                    continue
                
                lat = float(lat_elem.text)
                lon = float(lon_elem.text)
                
                bus_id_elem = journey.find('siri:VehicleRef', ns)
                bus_id = bus_id_elem.text if bus_id_elem is not None else "Unknown"
                
                operator_elem = journey.find('siri:OperatorRef', ns)
                operator = operator_elem.text if operator_elem is not None else "Unknown"
                
                bearing_elem = journey.find('siri:Bearing', ns)
                bearing = float(bearing_elem.text) if bearing_elem is not None else 0
                
                speed_elem = journey.find('siri:Speed', ns)
                speed = float(speed_elem.text) if speed_elem is not None else 0
                
                dest_elem = journey.find('siri:DestinationName', ns)
                destination = dest_elem.text if dest_elem is not None else "Unknown"
                
                origin_elem = journey.find('siri:OriginName', ns)
                origin = origin_elem.text if origin_elem is not None else "Unknown"
                
                delay_elem = journey.find('siri:Delay', ns)
                delay = delay_elem.text if delay_elem is not None else "PT0S"
                delay_min = 0
                try:
                    import re
                    minutes = re.search(r'(\d+)M', delay)
                    if minutes:
                        delay_min = int(minutes.group(1))
                except:
                    delay_min = 0
                
                monitored_call = journey.find('.//siri:MonitoredCall', ns)
                next_stop = "Unknown"
                next_stop_ref = ""
                expected_arrival = ""
                
                if monitored_call is not None:
                    stop_name_elem = monitored_call.find('siri:StopPointName', ns)
                    if stop_name_elem is not None:
                        next_stop = stop_name_elem.text
                    
                    stop_ref_elem = monitored_call.find('siri:StopPointRef', ns)
                    if stop_ref_elem is not None:
                        next_stop_ref = stop_ref_elem.text
                    
                    arrival_elem = monitored_call.find('siri:ExpectedArrivalTime', ns)
                    if arrival_elem is not None:
                        expected_arrival = arrival_elem.text
                
                buses.append({
                    "bus_id": bus_id,
                    "route": route,
                    "operator": operator,
                    "latitude": lat,
                    "longitude": lon,
                    "bearing": bearing,
                    "speed": speed,
                    "delay_minutes": delay_min,
                    "destination": destination,
                    "origin": origin,
                    "next_stop": next_stop,
                    "next_stop_ref": next_stop_ref,
                    "expected_arrival": expected_arrival,
                })
            except:
                continue
    except Exception as e:
        print(f"XML parse error: {e}")
    
    return buses


def fetch_live_buses(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    """Fetch live bus positions from BODS API (filtered to routes 72 & 76)."""
    global BUSES_CACHE, BUS_HISTORY
    
    try:
        url = "https://data.bus-data.dft.gov.uk/api/v1/datafeed/"
        params = {
            "api_key": BODS_API_KEY,
            "boundingBox": f"{min_lon},{min_lat},{max_lon},{max_lat}"
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            buses_list = parse_siri_xml(response.text)
            
            current_time = time.time()
            bus_dict = {}
            
            for bus in buses_list:
                bus_id = bus["bus_id"]
                
                if bus_id not in BUS_HISTORY:
                    BUS_HISTORY[bus_id] = []
                
                BUS_HISTORY[bus_id].append({
                    "lat": bus["latitude"],
                    "lon": bus["longitude"],
                    "timestamp": current_time
                })
                
                if len(BUS_HISTORY[bus_id]) > 20:
                    BUS_HISTORY[bus_id] = BUS_HISTORY[bus_id][-20:]
                
                bus["trail"] = BUS_HISTORY[bus_id]
                bus["last_updated"] = current_time
                bus_dict[bus_id] = bus
            
            BUSES_CACHE["buses"] = bus_dict
            BUSES_CACHE["timestamp"] = current_time
            return bus_dict
        else:
            return BUSES_CACHE.get("buses", {})
    except Exception as e:
        print(f"BODS fetch error: {e}")
        return BUSES_CACHE.get("buses", {})


def get_buses_for_stop(stop_id: str, lat: float, lon: float):
    """Get buses approaching a specific stop with real-time positions and trail."""
    # Lookup stop in directory
    stop_info = None
    for sid, info in STOP_DIRECTORY.items():
        if sid == stop_id or info.get("atco_code") == stop_id:
            stop_info = info
            stop_info["sensor_id"] = sid
            break
    
    if not stop_info:
        return None
    
    # Fetch all buses in Bristol area
    all_buses = fetch_live_buses(-2.7, 51.4, -2.5, 51.6)
    
    # Find buses heading to or near this stop
    stop_buses = []
    for bus_id, bus in all_buses.items():
        next_stop_ref = bus.get("next_stop_ref", "")
        
        # Check if heading to this stop
        is_heading_to_stop = next_stop_ref == stop_info.get("atco_code", "")
        
        # Check distance to this stop
        dist_to_stop = haversine(stop_info["lng"], stop_info["lat"], bus["longitude"], bus["latitude"])
        is_near_stop = dist_to_stop < 2.5  # Within 2.5km
        
        if is_heading_to_stop or is_near_stop:
            bus_copy = dict(bus)
            bus_copy["distance_to_stop"] = round(dist_to_stop, 2)
            bus_copy["distance_to_user"] = round(haversine(lon, lat, bus["longitude"], bus["latitude"]), 2)
            
            # Include trail if available
            if bus_id in BUS_HISTORY and len(BUS_HISTORY[bus_id]) > 1:
                bus_copy["trail"] = BUS_HISTORY[bus_id][-20:]
            else:
                bus_copy["trail"] = []
            
            stop_buses.append(bus_copy)
    
    # Sort by distance
    stop_buses.sort(key=lambda x: x["distance_to_stop"])
    
    return {
        "stop": stop_info,
        "buses": stop_buses,
        "count": len(stop_buses)
    }


# --- REQUEST/RESPONSE MODELS ---

class SensorData(BaseModel):
    stop_id: str
    crowd_count: int


# --- API ENDPOINTS ---

@app.post("/update-sensor-data")
def update_sensor_data(data: SensorData):
    """
    Receive crowd count from CV sensor.
    Validates stop_id against STOP_DIRECTORY, fetches traffic from TomTom,
    calculates prediction, and saves to database.
    """
    stop_id = data.stop_id
    crowd_count = data.crowd_count
    
    # Validation: Check if stop_id exists in STOP_DIRECTORY
    if stop_id not in STOP_DIRECTORY:
        raise HTTPException(
            status_code=404, 
            detail=f"Stop ID '{stop_id}' not found in registry. Available: {list(STOP_DIRECTORY.keys())}"
        )
    
    stop_info = STOP_DIRECTORY[stop_id]
    lat = stop_info["lat"]
    lng = stop_info["lng"]
    stop_name = stop_info["name"]
    
    # Traffic Lookup: Use lat/lng from directory to ask TomTom
    traffic_data = get_tomtom_traffic(lat, lng)
    traffic_delay = traffic_data["traffic_delay_min"]
    
    # Prediction: Calculate delay based on Crowd + Traffic
    predicted_delay = predict_arrival_delay(traffic_delay, crowd_count, is_raining=False)
    
    # Storage: Save to Database
    db_saved = save_prediction_to_db(
        stop_id=stop_id,
        stop_name=stop_name,
        crowd_count=crowd_count,
        traffic_delay=traffic_delay,
        predicted_delay=predicted_delay,
        lat=lat,
        lng=lng
    )
    
    return {
        "status": "success",
        "stop_id": stop_id,
        "stop_name": stop_name,
        "crowd_count": crowd_count,
        "traffic_delay_min": traffic_delay,
        "predicted_delay_min": predicted_delay,
        "traffic_data": traffic_data,
        "db_saved": db_saved,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/stops")
def get_all_stops():
    """Get all stops from the Modular Stop Directory."""
    return {
        "stops": STOP_DIRECTORY,
        "count": len(STOP_DIRECTORY),
        "target_routes": TARGET_ROUTES
    }


@app.get("/stop/{stop_id}/buses")
def get_stop_buses(
    stop_id: str,
    lat: float = Query(...),
    lon: float = Query(...)
):
    """Get buses for a specific stop with real-time locations."""
    result = get_buses_for_stop(stop_id, lat, lon)
    
    if not result:
        raise HTTPException(status_code=404, detail="Stop not found in directory")
    
    return result


@app.get("/all-buses")
def get_all_buses(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(15.0)
):
    """Get all buses (Routes 72 & 76 only) in Bristol area."""
    lat_offset = radius / 111.0
    lon_offset = radius / (111.0 * cos(radians(lat)))
    
    buses = fetch_live_buses(lon - lon_offset, lat - lat_offset, lon + lon_offset, lat + lat_offset)
    
    result = []
    for bus in buses.values():
        bus_copy = dict(bus)
        dist = haversine(lon, lat, bus["longitude"], bus["latitude"])
        bus_copy["distance_km"] = round(dist, 2)
        result.append(bus_copy)
    
    return {
        "buses": result, 
        "count": len(result),
        "filtered_routes": TARGET_ROUTES
    }


@app.get("/directory")
def get_stop_directory():
    """Get the full STOP_DIRECTORY registry."""
    return {
        "directory": STOP_DIRECTORY,
        "total_stops": len(STOP_DIRECTORY),
        "note": "Add new stops to STOP_DIRECTORY in main.py"
    }


@app.get("/health")
def health_check():
    """System health check."""
    return {
        "status": "healthy",
        "version": "4.0.0",
        "modular_id_system": "active",
        "registered_stops": len(STOP_DIRECTORY),
        "target_routes": TARGET_ROUTES,
        "buses_tracked": len(BUSES_CACHE.get("buses", {})),
        "ml_model_loaded": bst is not None
    }


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Transight API v4.0 - Modular ID System")
    print(f"📍 Registered Stops: {list(STOP_DIRECTORY.keys())}")
    print(f"🚌 Target Routes: {TARGET_ROUTES}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
