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
    description="Real-time bus tracking and arrival prediction system",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Database Credentials
DB_PARAMS = {
    "host": "localhost", "database": "transight_db", "user": "postgres", "password": "R@jibale3138"
}

# API Keys - REPLACE WITH YOUR VALID BODS API KEY
BODS_API_KEY = "2bc39438a3eeec844704f182bab7892fea39b8bd"
TOMTOM_API_KEY = "IgrkN0Ci9H94UGQWLoBSpzSFEycU8Xiy"

# Cache and history
BODS_CACHE = {"buses": {}, "timestamp": 0}
BUS_HISTORY = {}
CACHE_EXPIRY = 10

# Default Bristol stops
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
]

# --- LOAD AI MODEL ---
model_path = "bus_prediction_model.json"
bst = None

if os.path.exists(model_path):
    print("Loading XGBoost Brain...")
    bst = xgb.Booster()
    bst.load_model(model_path)

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


# --- 1. BODS API - XML PARSING ---

def parse_siri_xml(xml_text):
    """Parse SIRI-VM XML response and extract bus data"""
    buses = []
    try:
        root = ET.fromstring(xml_text)
        
        # Define namespace
        ns = {'siri': 'http://www.siri.org.uk/siri'}
        
        # Find all VehicleActivity elements
        for vehicle in root.findall('.//siri:VehicleActivity', ns):
            try:
                journey = vehicle.find('.//siri:MonitoredVehicleJourney', ns)
                if journey is None:
                    continue
                
                # Extract vehicle location
                location = journey.find('.//siri:VehicleLocation', ns)
                if location is None:
                    continue
                
                lat_elem = location.find('siri:Latitude', ns)
                lon_elem = location.find('siri:Longitude', ns)
                
                if lat_elem is None or lon_elem is None:
                    continue
                
                lat = float(lat_elem.text)
                lon = float(lon_elem.text)
                
                # Extract other fields
                bus_id_elem = journey.find('siri:VehicleRef', ns)
                bus_id = bus_id_elem.text if bus_id_elem is not None else "Unknown"
                
                route_elem = journey.find('siri:PublishedLineName', ns)
                if route_elem is None:
                    route_elem = journey.find('siri:LineRef', ns)
                route = route_elem.text if route_elem is not None else "Unknown"
                
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
                
                direction_elem = journey.find('siri:DirectionRef', ns)
                direction = direction_elem.text if direction_elem is not None else "unknown"
                
                # Get delay
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
                
                # Get next stop info
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
                    "route_id": route,
                    "operator": operator,
                    "latitude": lat,
                    "longitude": lon,
                    "bearing": bearing,
                    "speed": speed,
                    "delay_minutes": delay_min,
                    "destination": destination,
                    "origin": origin,
                    "direction": direction,
                    "next_stop": next_stop,
                    "next_stop_ref": next_stop_ref,
                    "expected_arrival": expected_arrival,
                }
                
                buses.append(bus_data)
                
            except Exception as e:
                continue
                
    except Exception as e:
        print(f"XML parsing error: {e}")
    
    return buses


def fetch_bods_live_buses(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> Dict[str, dict]:
    """Fetch REAL bus positions from BODS using boundingBox"""
    global BODS_CACHE, BUS_HISTORY
    
    try:
        url = "https://data.bus-data.dft.gov.uk/api/v1/datafeed/"
        params = {
            "api_key": BODS_API_KEY,
            "boundingBox": f"{min_lon},{min_lat},{max_lon},{max_lat}"
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            # Parse XML response
            buses_list = parse_siri_xml(response.text)
            
            current_time = time.time()
            active_buses = {}
            
            for bus in buses_list:
                bus_id = bus["bus_id"]
                bus_lat = bus["latitude"]
                bus_lon = bus["longitude"]
                
                # Update history
                if bus_id not in BUS_HISTORY:
                    BUS_HISTORY[bus_id] = []
                
                BUS_HISTORY[bus_id].append({
                    "lat": bus_lat,
                    "lon": bus_lon,
                    "timestamp": current_time
                })
                
                # Keep last 20 positions
                if len(BUS_HISTORY[bus_id]) > 20:
                    BUS_HISTORY[bus_id] = BUS_HISTORY[bus_id][-20:]
                
                bus["trail"] = BUS_HISTORY[bus_id]
                bus["last_updated"] = current_time
                active_buses[bus_id] = bus
            
            # Clean old buses
            cutoff_time = current_time - 60
            BODS_CACHE["buses"] = {
                k: v for k, v in active_buses.items() 
                if v.get("last_updated", 0) > cutoff_time
            }
            BODS_CACHE["timestamp"] = current_time
            
            print(f"BODS: Found {len(active_buses)} real buses")
            return BODS_CACHE["buses"]
        else:
            print(f"BODS API Error: {response.status_code}")
            return BODS_CACHE.get("buses", {})
            
    except Exception as e:
        print(f"BODS Error: {e}")
        return BODS_CACHE.get("buses", {})


def get_buses_near_location(lat: float, lon: float, radius_km: float = 5.0) -> List[dict]:
    """Get buses within radius of location"""
    lat_offset = radius_km / 111.0
    lon_offset = radius_km / (111.0 * cos(radians(lat)))
    
    min_lat = lat - lat_offset
    max_lat = lat + lat_offset
    min_lon = lon - lon_offset
    max_lon = lon + lon_offset
    
    all_buses = fetch_bods_live_buses(min_lon, min_lat, max_lon, max_lat)
    
    nearby = []
    for bus_id, bus in all_buses.items():
        try:
            dist = haversine(lon, lat, bus["longitude"], bus["latitude"])
            if dist <= radius_km:
                bus_copy = dict(bus)
                bus_copy["distance_km"] = round(dist, 2)
                nearby.append(bus_copy)
        except:
            continue
    
    return nearby


def fetch_bods_stops(lat: float = None, lon: float = None, radius: float = 1.0) -> List[dict]:
    """Fetch bus stops"""
    stops = DEFAULT_STOPS
    
    if lat and lon:
        filtered = []
        for stop in stops:
            try:
                s_lat = float(stop.get("latitude", 0))
                s_lon = float(stop.get("longitude", 0))
                if s_lat == 0 or s_lon == 0:
                    continue
                dist = haversine(lon, lat, s_lon, s_lat)
                if dist <= radius:
                    stop_copy = dict(stop)
                    stop_copy["distance_km"] = round(dist, 2)
                    filtered.append(stop_copy)
            except:
                continue
        filtered.sort(key=lambda x: x.get("distance_km", 999))
        return filtered
    
    return stops


# --- 2. API ENDPOINTS ---

@app.get("/live-buses")
def get_live_buses(
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    radius: float = Query(5.0, description="Search radius in km")
):
    """Get REAL live bus locations"""
    buses = get_buses_near_location(lat, lon, radius)
    
    return {
        "buses": buses,
        "count": len(buses),
        "timestamp": datetime.now().isoformat(),
        "user_location": {"lat": lat, "lon": lon},
        "is_real_data": True
    }


@app.get("/bus-trail/{bus_id}")
def get_bus_trail(bus_id: str):
    """Get position history for a bus"""
    trail = BUS_HISTORY.get(bus_id, [])
    return {
        "bus_id": bus_id,
        "trail": trail,
        "count": len(trail)
    }


@app.get("/nearby-stops")
def get_nearby_stops(
    latitude: float = Query(..., description="User latitude"),
    longitude: float = Query(..., description="User longitude"),
    radius: float = Query(1.0, description="Search radius in km")
):
    """Get bus stops within radius"""
    stops = fetch_bods_stops(latitude, longitude, radius)
    
    nearby_buses = get_buses_near_location(latitude, longitude, radius + 2)
    
    stop_bus_count = {}
    for bus in nearby_buses:
        next_stop = bus.get("next_stop_ref", "")
        if next_stop:
            stop_bus_count[next_stop] = stop_bus_count.get(next_stop, 0) + 1
    
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
            "buses_approaching": stop_bus_count.get(stop_id, 0)
        })
    
    return {
        "nearby_stops": nearby,
        "count": len(nearby),
        "user_location": {"latitude": latitude, "longitude": longitude}
    }


@app.get("/stops")
def get_all_stops(
    lat: float = Query(None),
    lon: float = Query(None),
    radius: float = Query(2.0)
):
    """Get all bus stops"""
    stops = fetch_bods_stops(lat, lon, radius)
    
    formatted = []
    for stop in stops:
        formatted.append({
            "stop_id": stop.get("atco_code") or str(stop.get("id", "")),
            "name": stop.get("common_name", "Unknown"),
            "latitude": float(stop.get("latitude", 0)),
            "longitude": float(stop.get("longitude", 0)),
            "locality": stop.get("locality", ""),
            "indicator": stop.get("indicator", ""),
            "distance_km": stop.get("distance_km")
        })
    
    return {"stops": formatted, "count": len(formatted)}


@app.get("/stops/{stop_id}")
def get_stop_detail(stop_id: str):
    """Get stop details"""
    stops = fetch_bods_stops()
    stop_info = None
    for stop in stops:
        if stop.get("atco_code") == stop_id or str(stop.get("id")) == stop_id:
            stop_info = stop
            break
    
    if not stop_info:
        raise HTTPException(status_code=404, detail="Stop not found")
    
    lat = float(stop_info.get("latitude", 0))
    lon = float(stop_info.get("longitude", 0))
    nearby_buses = get_buses_near_location(lat, lon, 10)
    
    upcoming = [b for b in nearby_buses if b.get("next_stop_ref") == stop_id]
    upcoming.sort(key=lambda x: x.get("expected_arrival", ""))
    
    return {
        "stop_id": stop_id,
        "name": stop_info.get("common_name", "Unknown"),
        "latitude": lat,
        "longitude": lon,
        "locality": stop_info.get("locality", ""),
        "indicator": stop_info.get("indicator", ""),
        "upcoming_buses": upcoming[:5]
    }


@app.get("/search")
def search_stops(
    q: str = Query(...),
    lat: float = Query(None),
    lon: float = Query(None)
):
    """Search stops"""
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
    
    return {"results": results[:20], "count": len(results)}


@app.get("/live-buses/route/{route_id}")
def get_buses_by_route(route_id: str):
    """Get buses by route"""
    all_buses = BODS_CACHE.get("buses", {})
    filtered = [b for b in all_buses.values() if route_id.upper() in str(b.get("route", "")).upper()]
    
    return {
        "route_id": route_id,
        "buses": filtered,
        "count": len(filtered)
    }


@app.get("/routes/nearby")
def get_routes_nearby(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(3.0)
):
    """Get active routes"""
    buses = get_buses_near_location(lat, lon, radius)
    
    routes = {}
    for bus in buses:
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
        "count": len(routes)
    }


@app.post("/update-sensor-data")
def update_sensor(data: dict):
    """Receive crowd count"""
    return {"status": "OK"}


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "buses_tracked": len(BODS_CACHE.get("buses", {})),
        "version": "3.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    print("Transight API v3.0 - Real-time Bus Tracking")
    print("Parsing BODS SIRI-VM XML data")
    uvicorn.run(app, host="0.0.0.0", port=8000)
