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
TOMTOM_API_KEY = "a1jG3Ptx5icrrFGYVRBWQo4o0t2XurwP"  # Get your free API key from https://developer.tomtom.com/
# TomTom API Key Note: The system works without a TomTom key using fallback traffic estimation

# Target Routes Filter - FOCUS ONLY ON ROUTE 72
TARGET_ROUTES = ["72"]

# ==========================================
# ROUTE 72 GEOMETRY (Actual bus route path)
# ==========================================
# Coordinates along Route 72: Temple Meads → UWE Frenchay
# This defines the actual path the bus takes
ROUTE_72_GEOMETRY = [
    # Temple Meads area
    {"lat": 51.4496, "lng": -2.5811, "name": "Temple Meads Station"},
    {"lat": 51.4510, "lng": -2.5820, "name": "Temple Gate"},
    # City Centre
    {"lat": 51.4528, "lng": -2.5975, "name": "The Centre"},
    {"lat": 51.4545, "lng": -2.5879, "name": "Cabot Circus"},
    # Stokes Croft / Gloucester Road
    {"lat": 51.4600, "lng": -2.5880, "name": "Stokes Croft"},
    {"lat": 51.4640, "lng": -2.5900, "name": "Gloucester Road"},
    # Horfield
    {"lat": 51.4750, "lng": -2.5850, "name": "Horfield"},
    # Southmead
    {"lat": 51.4900, "lng": -2.5950, "name": "Southmead Hospital"},
    # UWE Frenchay
    {"lat": 51.5005, "lng": -2.5490, "name": "UWE Frenchay Campus"},
]

# ==========================================
# MODULAR STOP DIRECTORY (Route 72 Stops Only)
# ==========================================
# Only stops that are actually ON Route 72
STOP_DIRECTORY = {
    "BST-001": {
        "name": "Temple Meads Station",
        "lat": 51.4496,
        "lng": -2.5811,
        "atco_code": "01000053220",
        "route": "72",
        "order": 1  # First stop on route
    },
    "BST-004": {
        "name": "The Centre",
        "lat": 51.4528,
        "lng": -2.5975,
        "atco_code": "01000002301",
        "route": "72",
        "order": 2
    },
    "BST-002": {
        "name": "Cabot Circus",
        "lat": 51.4545,
        "lng": -2.5879,
        "atco_code": "01000588088",
        "route": "72",
        "order": 3
    },
    "BST-005": {
        "name": "Stokes Croft",
        "lat": 51.4600,
        "lng": -2.5880,
        "atco_code": "01000030101",
        "route": "72",
        "order": 4
    },
    "BST-006": {
        "name": "Gloucester Road",
        "lat": 51.4640,
        "lng": -2.5900,
        "atco_code": "01000046701",
        "route": "72",
        "order": 5
    },
    "BST-007": {
        "name": "Horfield",
        "lat": 51.4750,
        "lng": -2.5850,
        "atco_code": "01000048901",
        "route": "72",
        "order": 6
    },
    "BST-008": {
        "name": "Southmead Hospital",
        "lat": 51.4900,
        "lng": -2.5950,
        "atco_code": "01000055001",
        "route": "72",
        "order": 7
    },
    "BST-003": {
        "name": "UWE Frenchay Campus",
        "lat": 51.5005,
        "lng": -2.5490,
        "atco_code": "01000057001",
        "route": "72",
        "order": 8  # Last stop on route
    },
    # Future Route 72 stops can be added here
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
    print(f"[OK] ML Model loaded: {model_path}")

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
    
    NOTE: Get a free API key from https://developer.tomtom.com/
    """
    # Check if API key looks valid (TomTom keys are typically longer)
    if not TOMTOM_API_KEY or len(TOMTOM_API_KEY) < 20:
        print("⚠️  TomTom API key not configured. Using fallback traffic estimation.")
        return {
            "traffic_delay_min": 0,
            "current_speed_kph": 40,
            "free_flow_speed_kph": 40,
            "congestion_level": 0,
            "status": "no_api_key"
        }
    
    try:
        # TomTom Flow Segment Data API
        # Using relative0 endpoint which works with just coordinates
        url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"
        params = {
            "key": TOMTOM_API_KEY,
            "point": f"{lat},{lng}",
            "unit": "KMPH"
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for API error in response
            if "error" in data:
                print(f"TomTom API returned error: {data.get('error', 'Unknown')}")
                return {
                    "traffic_delay_min": 0,
                    "current_speed_kph": 40,
                    "free_flow_speed_kph": 40,
                    "congestion_level": 0,
                    "status": "api_error_response"
                }
            
            flow = data.get("flowSegmentData", {})
            
            current_speed = flow.get("currentSpeed", 0)
            free_flow_speed = flow.get("freeFlowSpeed", 0)
            confidence = flow.get("confidence", 0)
            
            # Calculate delay based on speed ratio
            delay_min = 0
            if free_flow_speed > 0 and current_speed > 0:
                speed_ratio = current_speed / free_flow_speed
                if speed_ratio < 0.3:
                    # Severe congestion
                    delay_min = round((1 - speed_ratio) * 25, 1)
                elif speed_ratio < 0.6:
                    # Heavy traffic
                    delay_min = round((1 - speed_ratio) * 20, 1)
                elif speed_ratio < 0.85:
                    # Moderate traffic
                    delay_min = round((1 - speed_ratio) * 15, 1)
                # Light traffic = no delay
            
            print(f"🚦 TomTom Traffic at ({lat:.4f}, {lng:.4f}): {current_speed}/{free_flow_speed} km/h, delay: {delay_min}min")
                
            return {
                "traffic_delay_min": delay_min,
                "current_speed_kph": current_speed,
                "free_flow_speed_kph": free_flow_speed,
                "congestion_level": confidence,
                "status": "success"
            }
        elif response.status_code == 403:
            print(f"🚫 TomTom API access denied (403). Check your API key at https://developer.tomtom.com/")
            return {
                "traffic_delay_min": 0,
                "current_speed_kph": 0,
                "free_flow_speed_kph": 0,
                "congestion_level": 0,
                "status": "invalid_api_key"
            }
        else:
            print(f"⚠️  TomTom API error: {response.status_code} - {response.text[:100]}")
            return {
                "traffic_delay_min": 0,
                "current_speed_kph": 0,
                "free_flow_speed_kph": 0,
                "congestion_level": 0,
                "status": f"api_error_{response.status_code}"
            }
    except requests.exceptions.Timeout:
        print("⏱️  TomTom API timeout")
        return {
            "traffic_delay_min": 0,
            "current_speed_kph": 0,
            "free_flow_speed_kph": 0,
            "congestion_level": 0,
            "status": "timeout"
        }
    except Exception as e:
        print(f"❌ TomTom fetch error: {e}")
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
            "Live Traffic", 
            0.85,
            datetime.now()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Database error (save): {e}")
        return False


def get_latest_stop_data(stop_id: str):
    """
    Get latest crowd count and prediction for a stop from database.
    Returns crowd_count, traffic_delay, predicted_delay or defaults if no data.
    """
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT crowd_count, traffic_delay, total_prediction, timestamp
            FROM prediction_history
            WHERE bus_stop_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (stop_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            crowd_count, traffic_delay, predicted_delay, timestamp = result
            # Check if data is recent (within last 5 minutes)
            is_recent = timestamp and (datetime.now() - timestamp).total_seconds() < 300
            return {
                "crowd_count": crowd_count,
                "traffic_delay": float(traffic_delay) if traffic_delay else 0,
                "predicted_delay": float(predicted_delay) if predicted_delay else 0,
                "timestamp": timestamp.isoformat() if timestamp else None,
                "is_live": is_recent,
                "source": "sensor" if is_recent else "historical"
            }
    except Exception as e:
        print(f"Database error (read): {e}")
    
    # Return defaults if no data or error
    return {
        "crowd_count": 0,
        "traffic_delay": 0,
        "predicted_delay": 0,
        "timestamp": None,
        "is_live": False,
        "source": "default"
    }


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
                
                # FILTER: Only keep target routes (72 & 76 and variants)
                # Check if route starts with any of our target routes
                is_target_route = any(route.startswith(tr) for tr in TARGET_ROUTES)
                if not is_target_route:
                    continue  # Silently skip non-target routes
                
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
                
                bus_data = {
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
                }
                buses.append(bus_data)
                print(f"  [BODS] Route {route} bus {bus_id} to {destination} at ({lat:.4f}, {lon:.4f})")
            except Exception as e:
                print(f"  [BODS] Parse error for vehicle: {e}")
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
        
        print(f"🚌 Fetching BODS data for bbox: {min_lon},{min_lat},{max_lon},{max_lat}")
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            buses_list = parse_siri_xml(response.text)
            print(f"📊 Total buses from BODS: {len(buses_list)} (filtered to routes {TARGET_ROUTES})")
            
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


def get_buses_for_stop(stop_id: str, user_lat: float, user_lon: float):
    """Get buses approaching a specific stop with real-time positions, trail, and predictions."""
    # Lookup stop in directory
    stop_info = None
    sensor_id = None
    for sid, info in STOP_DIRECTORY.items():
        if sid == stop_id or info.get("atco_code") == stop_id:
            stop_info = dict(info)
            sensor_id = sid
            break
    
    if not stop_info:
        print(f"⚠️  Stop {stop_id} not found in directory")
        return None
    
    stop_info["sensor_id"] = sensor_id
    print(f"🔍 Looking for buses near: {stop_info['name']} ({stop_id})")
    
    # Get latest crowd data and predictions for this stop
    stop_data = get_latest_stop_data(sensor_id or stop_id)
    print(f"📊 Stop data: crowd={stop_data['crowd_count']}, predicted_delay={stop_data['predicted_delay']:.1f}min")
    
    # Fetch all buses in Greater Bristol area
    all_buses = fetch_live_buses(-2.75, 51.38, -2.45, 51.55)
    print(f"🔍 Total buses in area: {len(all_buses)}")
    
    # Find buses heading to or near this stop
    stop_buses = []
    for bus_id, bus in all_buses.items():
        next_stop_ref = bus.get("next_stop_ref", "")
        bus_route = bus.get("route", "Unknown")
        
        # Only show Route 72 buses
        if bus_route != "72" and not bus_route.startswith("72-"):
            continue
        
        # Check if heading to this stop
        is_heading_to_stop = next_stop_ref == stop_info.get("atco_code", "")
        
        # Check distance to this stop
        dist_to_stop = haversine(stop_info["lng"], stop_info["lat"], bus["longitude"], bus["latitude"])
        is_near_stop = dist_to_stop < 3.0  # Within 3km
        
        if is_heading_to_stop or is_near_stop:
            print(f"  🚌 Bus {bus_id} (Route {bus_route}) near stop: {dist_to_stop:.2f}km")
            bus_copy = dict(bus)
            bus_copy["distance_to_stop"] = round(dist_to_stop, 2)
            bus_copy["distance_to_user"] = round(haversine(user_lon, user_lat, bus["longitude"], bus["latitude"]), 2)
            
            # Calculate ETA based on distance and average speed (assume 20 km/h in city)
            avg_speed_kmh = max(bus.get("speed", 20), 15)  # Min 15 km/h
            eta_minutes = (dist_to_stop / avg_speed_kmh) * 60 + stop_data['predicted_delay']
            bus_copy["eta_minutes"] = round(eta_minutes, 1)
            
            # Include trail if available
            if bus_id in BUS_HISTORY and len(BUS_HISTORY[bus_id]) > 1:
                bus_copy["trail"] = BUS_HISTORY[bus_id][-20:]
            else:
                bus_copy["trail"] = []
            
            stop_buses.append(bus_copy)
    
    # Sort by ETA
    stop_buses.sort(key=lambda x: x["eta_minutes"])
    
    print(f"✅ Returning {len(stop_buses)} buses for stop {stop_id}")
    
    return {
        "stop": stop_info,
        "buses": stop_buses,
        "stop_data": stop_data,
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
def get_all_stops(
    lat: float = Query(None),
    lon: float = Query(None),
    radius: float = Query(50.0)
):
    """Get all stops from the Modular Stop Directory."""
    # Convert STOP_DIRECTORY object to array format for frontend compatibility
    stops_array = []
    for stop_id, info in STOP_DIRECTORY.items():
        stop_data = {
            "atco_code": info.get("atco_code", stop_id),
            "common_name": info.get("name", "Unknown"),
            "locality": "Bristol",
            "indicator": stop_id,
            "latitude": info.get("lat"),
            "longitude": info.get("lng"),
            "sensor_id": stop_id
        }
        
        # Calculate distance if user location provided
        if lat and lon:
            try:
                dist = haversine(lon, lat, info.get("lng"), info.get("lat"))
                stop_data["distance_km"] = round(dist, 2)
            except:
                pass
        
        stops_array.append(stop_data)
    
    # Filter by radius if location provided
    if lat and lon:
        stops_array = [s for s in stops_array if s.get("distance_km", 999) <= radius]
        stops_array.sort(key=lambda x: x.get("distance_km", 999))
    
    return {
        "stops": stops_array,
        "count": len(stops_array),
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


@app.get("/route/72/geometry")
def get_route_72_geometry():
    """Get the Route 72 geometry (path from Temple Meads to UWE Frenchay)."""
    return {
        "route": "72",
        "name": "Temple Meads to UWE Frenchay",
        "direction": "Northbound",
        "geometry": ROUTE_72_GEOMETRY,
        "stops": [
            {
                "id": stop_id,
                "name": info["name"],
                "lat": info["lat"],
                "lng": info["lng"],
                "order": info.get("order", 99)
            }
            for stop_id, info in STOP_DIRECTORY.items()
            if info.get("route") == "72"
        ],
        "total_points": len(ROUTE_72_GEOMETRY)
    }


@app.get("/route/72/buses")
def get_route_72_buses():
    """
    Get all Route 72 buses with real-time positions.
    Returns buses with their progress along the route.
    """
    # Fetch buses in the Route 72 corridor
    all_buses = fetch_live_buses(-2.75, 51.38, -2.45, 51.55)
    
    # Filter to only Route 72
    route_72_buses = []
    for bus_id, bus in all_buses.items():
        route = bus.get("route", "")
        # Exact match or starts with 72 (but not 720, 721, etc)
        if route == "72" or route.startswith("72-") or route == "72A":
            bus_copy = dict(bus)
            
            # Find nearest point on route geometry
            nearest_idx = 0
            min_dist = float('inf')
            for i, point in enumerate(ROUTE_72_GEOMETRY):
                dist = haversine(
                    bus["longitude"], bus["latitude"],
                    point["lng"], point["lat"]
                )
                if dist < min_dist:
                    min_dist = dist
                    nearest_idx = i
            
            bus_copy["route_progress"] = {
                "nearest_point_index": nearest_idx,
                "nearest_stop": ROUTE_72_GEOMETRY[nearest_idx]["name"],
                "distance_from_route_km": round(min_dist, 2),
                "is_on_route": min_dist < 0.5  # Within 500m of route
            }
            
            # Include trail
            if bus_id in BUS_HISTORY and len(BUS_HISTORY[bus_id]) > 1:
                bus_copy["trail"] = BUS_HISTORY[bus_id][-20:]
            else:
                bus_copy["trail"] = []
            
            route_72_buses.append(bus_copy)
    
    # Sort by progress along route (from Temple Meads to Frenchay)
    route_72_buses.sort(key=lambda x: x["route_progress"]["nearest_point_index"])
    
    return {
        "route": "72",
        "buses": route_72_buses,
        "count": len(route_72_buses),
        "last_updated": BUSES_CACHE.get("timestamp")
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
