from fastapi import FastAPI, HTTPException, Query
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
from math import radians, cos, sin, asin, sqrt

# --- CONFIGURATION ---
app = FastAPI(
    title="Transight Transit API",
    description="Real-time bus tracking and arrival prediction system",
    version="2.1.0"
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

# Cache settings
BODS_CACHE = {"buses": None, "buses_timestamp": 0, "stops": None, "stops_timestamp": 0}
CACHE_EXPIRY = 30
STOPS_CACHE_EXPIRY = 600  # 10 minutes for stops

# Bristol area default stops (real stops from BODS dataset)
DEFAULT_STOPS = [
    {"atco_code": "01000053220", "common_name": "Temple Meads Station", "locality": "Bristol", "indicator": "T4", "latitude": 51.4496, "longitude": -2.5811},
    {"atco_code": "01000053221", "common_name": "Temple Meads Station", "locality": "Bristol", "indicator": "T5", "latitude": 51.4498, "longitude": -2.5815},
    {"atco_code": "01000588088", "common_name": "Cabot Circus", "locality": "Bristol", "indicator": "S1", "latitude": 51.4545, "longitude": -2.5879},
    {"atco_code": "01000588089", "common_name": "Cabot Circus", "locality": "Bristol", "indicator": "S2", "latitude": 51.4547, "longitude": -2.5882},
    {"atco_code": "01000001008", "common_name": "St Nicholas Market", "locality": "Bristol", "indicator": "A1", "latitude": 51.4510, "longitude": -2.5880},
    {"atco_code": "01000001009", "common_name": "St Nicholas Market", "locality": "Bristol", "indicator": "A2", "latitude": 51.4512, "longitude": -2.5885},
    {"atco_code": "01000053304", "common_name": "Broadmead", "locality": "Bristol", "indicator": "C1", "latitude": 51.4580, "longitude": -2.5905},
    {"atco_code": "01000053305", "common_name": "Broadmead", "locality": "Bristol", "indicator": "C2", "latitude": 51.4582, "longitude": -2.5908},
    {"atco_code": "01000058001", "common_name": "Clifton Down", "locality": "Bristol", "indicator": "CD1", "latitude": 51.4645, "longitude": -2.6098},
    {"atco_code": "01000058002", "common_name": "Clifton Down", "locality": "Bristol", "indicator": "CD2", "latitude": 51.4647, "longitude": -2.6102},
    {"atco_code": "01000054001", "common_name": "Bedminster Parade", "locality": "Bristol", "indicator": "B1", "latitude": 51.4420, "longitude": -2.5945},
    {"atco_code": "01000054002", "common_name": "Bedminster Parade", "locality": "Bristol", "indicator": "B2", "latitude": 51.4422, "longitude": -2.5948},
    {"atco_code": "01000055001", "common_name": "Southmead Hospital", "locality": "Bristol", "indicator": "H1", "latitude": 51.4950, "longitude": -2.5950},
    {"atco_code": "01000055002", "common_name": "Southmead Hospital", "locality": "Bristol", "indicator": "H2", "latitude": 51.4952, "longitude": -2.5955},
    {"atco_code": "01000056001", "common_name": "Bristol Parkway", "locality": "Stoke Gifford", "indicator": "P1", "latitude": 51.5135, "longitude": -2.5420},
    {"atco_code": "01000056002", "common_name": "Bristol Parkway", "locality": "Stoke Gifford", "indicator": "P2", "latitude": 51.5137, "longitude": -2.5425},
    {"atco_code": "01000057001", "common_name": "UWE Frenchay", "locality": "Bristol", "indicator": "U1", "latitude": 51.5005, "longitude": -2.5490},
    {"atco_code": "01000057002", "common_name": "UWE Frenchay", "locality": "Bristol", "indicator": "U2", "latitude": 51.5007, "longitude": -2.5495},
]

# --- LOAD AI MODEL ---
model_path = "bus_prediction_model.json"
bst = None

if os.path.exists(model_path):
    print("Loading XGBoost Brain...")
    bst = xgb.Booster()
    bst.load_model(model_path)
else:
    print("WARNING: AI Model not found. Please run train_model.py")

# --- DATA MODELS ---
class SensorData(BaseModel):
    stop_id: str
    crowd_count: int

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

# --- HELPER FUNCTIONS ---
def haversine(lon1, lat1, lon2, lat2):
    """Calculate distance between two points on earth (in km)"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r

# --- 1. BODS API INTEGRATION ---

def fetch_bods_stops(lat: float = None, lon: float = None, radius: float = 1.0) -> List[dict]:
    """
    Fetch bus stops - uses real BODS data or falls back to default Bristol stops
    """
    global BODS_CACHE
    
    # Use cached stops if available
    if BODS_CACHE["stops"] is None or (time.time() - BODS_CACHE["stops_timestamp"]) > STOPS_CACHE_EXPIRY:
        try:
            # Try BODS API first
            url = "https://data.bus-data.dft.gov.uk/api/v1/stops/"
            headers = {"X-API-Key": BODS_API_KEY}
            params = {"limit": 1000}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                stops = data.get("results", [])
                if stops:
                    BODS_CACHE["stops"] = stops
                    BODS_CACHE["stops_timestamp"] = time.time()
                    print(f"Loaded {len(stops)} stops from BODS API")
                else:
                    raise Exception("Empty response from BODS")
            else:
                raise Exception(f"BODS API error: {response.status_code}")
        except Exception as e:
            print(f"BODS Stops API failed: {e}, using default stops")
            BODS_CACHE["stops"] = DEFAULT_STOPS
            BODS_CACHE["stops_timestamp"] = time.time()
    
    stops = BODS_CACHE.get("stops", DEFAULT_STOPS)
    
    # Filter by location if provided
    if lat and lon and stops:
        filtered_stops = []
        for stop in stops:
            try:
                stop_lat = float(stop.get("latitude", 0))
                stop_lon = float(stop.get("longitude", 0))
                if stop_lat == 0 or stop_lon == 0:
                    continue
                dist = haversine(lon, lat, stop_lon, stop_lat)
                if dist <= radius:
                    stop_copy = dict(stop)
                    stop_copy["distance_km"] = round(dist, 2)
                    filtered_stops.append(stop_copy)
            except:
                continue
        # Sort by distance
        filtered_stops.sort(key=lambda x: x.get("distance_km", 999))
        return filtered_stops
    
    return stops


def fetch_bods_live_buses(lat: float = None, lon: float = None, radius: float = 5.0) -> List[dict]:
    """
    Fetch live bus positions from BODS Vehicle Locations API
    Falls back to mock data if API fails
    """
    global BODS_CACHE
    
    # Return cached data if fresh
    if BODS_CACHE["buses"] and (time.time() - BODS_CACHE["buses_timestamp"]) < CACHE_EXPIRY:
        buses = BODS_CACHE["buses"]
        # Filter by location if needed
        if lat and lon:
            filtered = []
            for bus in buses:
                try:
                    bus_lat = float(bus.get("latitude", 0))
                    bus_lon = float(bus.get("longitude", 0))
                    dist = haversine(lon, lat, bus_lon, bus_lat)
                    if dist <= radius:
                        bus_copy = dict(bus)
                        bus_copy["distance_km"] = round(dist, 2)
                        filtered.append(bus_copy)
                except:
                    continue
            return filtered
        return buses
    
    buses = []
    try:
        # BODS Vehicle Locations API
        url = "https://data.bus-data.dft.gov.uk/api/v1/datafeed"
        headers = {"X-API-Key": BODS_API_KEY}
        params = {}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse SIRI-VM format
            service_delivery = data.get("Siri", {}).get("ServiceDelivery", {})
            vehicle_activity = service_delivery.get("VehicleMonitoringDelivery", {}).get("VehicleActivity", [])
            
            for entity in vehicle_activity:
                try:
                    journey = entity.get("MonitoredVehicleJourney", {})
                    location = journey.get("VehicleLocation", {})
                    
                    bus_lat = float(location.get("Latitude", 0))
                    bus_lon = float(location.get("Longitude", 0))
                    
                    # Parse delay
                    delay = journey.get("Delay", "PT0S")
                    delay_min = 0
                    if "PT" in delay:
                        delay_str = delay.replace("PT", "").replace("M", "")
                        try:
                            if "M" in delay:
                                parts = delay.replace("PT", "").split("M")
                                delay_min = int(parts[0]) if parts[0].isdigit() else 0
                        except:
                            delay_min = 0
                    
                    bus = {
                        "bus_id": journey.get("VehicleRef", "Unknown"),
                        "route": journey.get("PublishedLineName", journey.get("LineRef", "Unknown")),
                        "route_id": journey.get("LineRef", "Unknown"),
                        "operator": journey.get("OperatorRef", "Unknown"),
                        "latitude": bus_lat,
                        "longitude": bus_lon,
                        "speed": journey.get("Speed", 0) or 0,
                        "bearing": journey.get("Bearing", 0),
                        "occupancy": journey.get("Occupancy", "Unknown"),
                        "delay_minutes": delay_min,
                        "destination": journey.get("DestinationName", "Unknown"),
                        "origin": journey.get("OriginName", "Unknown"),
                        "next_stop": journey.get("MonitoredCall", {}).get("StopPointName", "Unknown"),
                        "next_stop_ref": journey.get("MonitoredCall", {}).get("StopPointRef", ""),
                        "expected_arrival": journey.get("MonitoredCall", {}).get("ExpectedArrivalTime", ""),
                    }
                    buses.append(bus)
                except Exception as e:
                    continue
            
            BODS_CACHE["buses"] = buses
            BODS_CACHE["buses_timestamp"] = time.time()
            print(f"Loaded {len(buses)} live buses from BODS")
        else:
            print(f"BODS API Error: {response.status_code}")
            raise Exception(f"BODS API returned {response.status_code}")
    except Exception as e:
        print(f"BODS Live Buses Error: {e}, using mock data")
        # Generate realistic mock buses around Bristol
        import random
        base_lat, base_lon = 51.4545, -2.5879  # Bristol center
        routes = ["72", "10", "15", "49", "X39", "70", "73", "76", "m1", "m2", "m3"]
        operators = ["First", "Stagecoach", "Arriva"]
        
        for i in range(15):
            # Random position within 5km of Bristol center
            lat_offset = (random.random() - 0.5) * 0.1
            lon_offset = (random.random() - 0.5) * 0.15
            bus_lat = base_lat + lat_offset
            bus_lon = base_lon + lon_offset
            
            # Filter by user location if provided
            if lat and lon:
                dist = haversine(lon, lat, bus_lon, bus_lat)
                if dist > radius:
                    continue
            
            route = random.choice(routes)
            destinations = {
                "72": "Temple Meads", "10": "City Centre", "15": "Southmead",
                "49": "Cribbs Causeway", "X39": "Bath", "70": "Clifton",
                "73": "Cribbs Causeway", "76": "Henbury", "m1": "Cribbs",
                "m2": "City Centre", "m3": "Emersons Green"
            }
            
            buses.append({
                "bus_id": f"BUS{1000 + i}",
                "route": route,
                "route_id": route,
                "operator": random.choice(operators),
                "latitude": bus_lat,
                "longitude": bus_lon,
                "speed": random.randint(10, 40),
                "bearing": random.randint(0, 359),
                "occupancy": random.choice(["seatsAvailable", "full", "unknown"]),
                "delay_minutes": random.choice([0, 0, 0, 1, 2, 3, 5]),
                "destination": destinations.get(route, "City Centre"),
                "origin": "Unknown",
                "next_stop": "Unknown",
                "next_stop_ref": "",
                "expected_arrival": (datetime.now() + timedelta(minutes=random.randint(2, 15))).isoformat(),
                "is_mock": True
            })
    
    return buses


def get_traffic_data(lat: float, lon: float) -> dict:
    """Fetch real-time traffic data from TomTom API"""
    base_url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
    params = {"key": TOMTOM_API_KEY, "point": f"{lat},{lon}"}
    
    try:
        resp = requests.get(base_url, params=params, timeout=2)
        if resp.status_code == 200:
            flow = resp.json().get('flowSegmentData', {})
            speed = flow.get('currentSpeed', 0)
            
            if speed > 50:
                status = "Free Flow"
            elif speed > 30:
                status = "Moderate"
            else:
                status = "Congested"
            
            return {"speed": speed, "status": status}
    except Exception as e:
        print(f"TomTom API Error: {e}")
    
    return {"speed": 0, "status": "Unknown"}


def calculate_dwell_time(crowd_count: int) -> float:
    """Estimate passenger boarding time based on crowd"""
    base_time = 0.5
    per_person_time = 0.05
    dwell_time = base_time + (per_person_time * crowd_count)
    return dwell_time / 60


def get_confidence_score(crowd_count: int, traffic_status: str) -> float:
    """Calculate confidence in prediction based on data quality"""
    confidence = 0.85
    
    if 0 < crowd_count < 50:
        confidence += 0.10
    elif crowd_count > 50:
        confidence -= 0.05
    
    if traffic_status == "Free Flow":
        confidence += 0.05
    elif traffic_status == "Congested":
        confidence -= 0.10
    
    return min(0.99, max(0.5, confidence))


# --- 2. API ENDPOINTS ---

@app.post("/update-sensor-data")
def update_sensor(data: SensorData):
    """Receive crowd count from CV system and predict arrival"""
    try:
        # Get stop location
        stops = fetch_bods_stops()
        stop_info = None
        for stop in stops:
            if stop.get("atco_code") == data.stop_id or str(stop.get("id")) == data.stop_id:
                stop_info = stop
                break
        
        if not stop_info:
            lat, lon = 51.4496, -2.5811
            stop_name = "Unknown Stop"
        else:
            lat = float(stop_info.get("latitude", 51.4496))
            lon = float(stop_info.get("longitude", -2.5811))
            stop_name = stop_info.get("common_name", "Unknown Stop")
        
        # Get traffic data
        traffic_data = get_traffic_data(lat, lon)
        traffic_speed = traffic_data.get('speed', 30)
        traffic_status = traffic_data.get('status', 'Unknown')
        
        # Run AI prediction
        features = pd.DataFrame(
            [[data.crowd_count, traffic_speed, 10]],
            columns=['crowd_count', 'traffic_speed', 'scheduled_interval']
        )
        
        predicted_delay = 0
        if bst:
            dmatrix = xgb.DMatrix(features)
            predicted_delay = float(bst.predict(dmatrix)[0])
        
        dwell_delay = calculate_dwell_time(data.crowd_count)
        total_prediction = max(0, int(predicted_delay + dwell_delay))
        confidence = get_confidence_score(data.crowd_count, traffic_status)
        
        # Save to database
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
                data.stop_id, data.crowd_count, predicted_delay,
                dwell_delay, total_prediction, lat, lon, traffic_status, confidence
            ))
            
            conn.commit()
            cur.close()
            conn.close()
        except psycopg2.Error as e:
            print(f"Database Error: {e}")
        
        return {
            "status": "Fusion Complete",
            "stop_name": stop_name,
            "new_prediction": total_prediction,
            "confidence": round(confidence, 2),
            "traffic_status": traffic_status
        }
    
    except Exception as e:
        print(f"Fusion Error: {e}")
        return {"error": str(e)}


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

        # Get stop name
        stops = fetch_bods_stops()
        stop_name = "Unknown Stop"
        for stop in stops:
            if stop.get("atco_code") == stop_id or str(stop.get("id")) == stop_id:
                stop_name = stop.get("common_name", "Unknown Stop")
                break

        if row:
            eta_time = (datetime.now() + timedelta(minutes=int(row[2]))).strftime("%H:%M")
            crowd_level = "High" if row[3] > 10 else "Low"
            
            return PredictionResponse(
                stop_id=stop_id,
                stop_name=stop_name,
                crowd_count=row[3],
                traffic_delay=round(row[0], 2),
                dwell_delay=round(row[1], 2),
                total_time_min=int(row[2]),
                crowd_level=crowd_level,
                traffic_status=row[4] or "Unknown",
                eta_time=eta_time,
                confidence=round(row[5], 2) if row[5] else 0.85
            )
        
        # Return default
        return PredictionResponse(
            stop_id=stop_id,
            stop_name=stop_name,
            crowd_count=0,
            traffic_delay=0,
            dwell_delay=0,
            total_time_min=5,
            crowd_level="Low",
            traffic_status="Free Flow",
            eta_time=(datetime.now() + timedelta(minutes=5)).strftime("%H:%M"),
            confidence=0.75
        )
    except Exception as e:
        print(f"Error fetching prediction: {e}")
        return None


@app.get("/stops")
def get_all_stops(
    lat: float = Query(None, description="User latitude"),
    lon: float = Query(None, description="User longitude"),
    radius: float = Query(2.0, description="Search radius in km")
):
    """Get bus stops - optionally filtered by location"""
    stops = fetch_bods_stops(lat, lon, radius)
    
    formatted_stops = []
    for stop in stops:
        formatted_stops.append({
            "stop_id": stop.get("atco_code") or str(stop.get("id", "")),
            "name": stop.get("common_name", "Unknown"),
            "latitude": float(stop.get("latitude", 0)),
            "longitude": float(stop.get("longitude", 0)),
            "locality": stop.get("locality", ""),
            "indicator": stop.get("indicator", ""),
            "routes": [],
            "distance_km": stop.get("distance_km")
        })
    
    return {"stops": formatted_stops, "count": len(formatted_stops)}


@app.get("/stops/{stop_id}")
def get_stop_detail(stop_id: str):
    """Get detailed information about a specific stop"""
    # Find stop
    stops = fetch_bods_stops()
    stop_info = None
    for stop in stops:
        if stop.get("atco_code") == stop_id or str(stop.get("id")) == stop_id:
            stop_info = stop
            break
    
    if not stop_info:
        raise HTTPException(status_code=404, detail="Stop not found")
    
    # Get live buses for this stop
    live_buses = fetch_bods_live_buses()
    upcoming_buses = []
    
    for bus in live_buses:
        if bus.get("next_stop_ref") == stop_id:
            upcoming_buses.append(bus)
    
    # Sort by expected arrival
    upcoming_buses.sort(key=lambda x: x.get("expected_arrival", ""))
    
    return {
        "stop_id": stop_id,
        "name": stop_info.get("common_name", "Unknown"),
        "latitude": float(stop_info.get("latitude", 0)),
        "longitude": float(stop_info.get("longitude", 0)),
        "locality": stop_info.get("locality", ""),
        "indicator": stop_info.get("indicator", ""),
        "upcoming_buses": upcoming_buses[:5],
        "prediction": get_prediction(stop_id)
    }


@app.get("/live-buses")
def get_live_buses(
    lat: float = Query(None, description="User latitude"),
    lon: float = Query(None, description="User longitude"),
    radius: float = Query(5.0, description="Search radius in km")
):
    """Get live bus locations and status"""
    buses = fetch_bods_live_buses(lat, lon, radius)
    
    return {
        "buses": buses,
        "count": len(buses),
        "timestamp": datetime.now().isoformat(),
        "data_source": "BODS API" if not any(b.get("is_mock") for b in buses) else "Mock Data (BODS unavailable)"
    }


@app.get("/live-buses/route/{route_id}")
def get_live_buses_by_route(route_id: str):
    """Get live buses for a specific route"""
    all_buses = fetch_bods_live_buses()
    filtered_buses = [bus for bus in all_buses if route_id.upper() in str(bus.get("route", "")).upper()]
    
    return {
        "route_id": route_id,
        "buses": filtered_buses,
        "count": len(filtered_buses),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/nearby-stops")
def get_nearby_stops(
    latitude: float = Query(..., description="User latitude"),
    longitude: float = Query(..., description="User longitude"),
    radius: float = Query(1.0, description="Search radius in km")
):
    """Get bus stops within a specified radius of user location"""
    stops = fetch_bods_stops(latitude, longitude, radius)
    
    nearby = []
    for stop in stops:
        stop_id = stop.get("atco_code") or str(stop.get("id", ""))
        nearby.append({
            "stop_id": stop_id,
            "name": stop.get("common_name", "Unknown"),
            "distance_km": stop.get("distance_km", 0),
            "latitude": float(stop.get("latitude", 0)),
            "longitude": float(stop.get("longitude", 0)),
            "locality": stop.get("locality", ""),
            "indicator": stop.get("indicator", ""),
            "routes": []
        })
    
    return {
        "nearby_stops": nearby,
        "count": len(nearby),
        "user_location": {"latitude": latitude, "longitude": longitude},
        "radius_km": radius
    }


@app.get("/routes/nearby")
def get_routes_nearby(
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    radius: float = Query(2.0, description="Search radius in km")
):
    """Get all routes operating near user location"""
    live_buses = fetch_bods_live_buses(lat, lon, radius)
    
    # Build route info
    routes = {}
    for bus in live_buses:
        route = bus.get("route", "Unknown")
        if route not in routes:
            routes[route] = {
                "route_id": route,
                "name": f"Route {route}",
                "destination": bus.get("destination", "Unknown"),
                "operator": bus.get("operator", "Unknown"),
                "active_buses": 0,
                "buses": []
            }
        routes[route]["active_buses"] += 1
        routes[route]["buses"].append(bus)
    
    return {
        "routes": list(routes.values()),
        "count": len(routes),
        "user_location": {"latitude": lat, "longitude": lon}
    }


@app.get("/search")
def search_stops(
    q: str = Query(..., description="Search query"),
    lat: float = Query(None, description="User latitude for distance sorting"),
    lon: float = Query(None, description="User longitude for distance sorting")
):
    """Search for bus stops by name"""
    all_stops = fetch_bods_stops()
    query = q.lower()
    
    results = []
    for stop in all_stops:
        name = stop.get("common_name", "").lower()
        locality = stop.get("locality", "").lower()
        
        if query in name or query in locality:
            stop_data = {
                "stop_id": stop.get("atco_code") or str(stop.get("id", "")),
                "name": stop.get("common_name", "Unknown"),
                "locality": stop.get("locality", ""),
                "latitude": float(stop.get("latitude", 0)),
                "longitude": float(stop.get("longitude", 0)),
            }
            
            if lat and lon:
                try:
                    dist = haversine(lon, lat, float(stop.get("longitude", 0)), float(stop.get("latitude", 0)))
                    stop_data["distance_km"] = round(dist, 2)
                except:
                    pass
            
            results.append(stop_data)
    
    if lat and lon:
        results.sort(key=lambda x: x.get("distance_km", 999))
    
    return {"results": results[:20], "query": q, "count": len(results)}


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
        "version": "2.1.0"
    }


if __name__ == "__main__":
    import uvicorn
    print("Transight API Server Starting...")
    print("Endpoints:")
    print("   - GET  /stops?lat=51.45&lon=-2.58&radius=2")
    print("   - GET  /nearby-stops?latitude=51.45&longitude=-2.58")
    print("   - GET  /live-buses?lat=51.45&lon=-2.58")
    print("   - GET  /search?q=bristol")
    print("   - GET  /predict/{stop_id}")
    print("   - GET  /health")
    uvicorn.run(app, host="0.0.0.0", port=8000)
