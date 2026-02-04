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
    version="3.1.0"
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

DB_PARAMS = {
    "host": "localhost", "database": "transight_db", "user": "postgres", "password": "R@jibale3138"
}

BODS_API_KEY = "2bc39438a3eeec844704f182bab7892fea39b8bd"

# Cache
STOPS_CACHE = {"data": None, "timestamp": 0}
STOPS_CACHE_EXPIRY = 600  # 10 minutes
BUSES_CACHE = {"buses": {}, "timestamp": 0}
BUS_HISTORY = {}
CACHE_EXPIRY = 10

# Comprehensive UK bus stops database (major cities)
DEFAULT_UK_STOPS = [
    # Bristol
    {"atco_code": "01000053220", "common_name": "Temple Meads Station", "locality": "Bristol", "indicator": "T4", "latitude": 51.4496, "longitude": -2.5811},
    {"atco_code": "01000588088", "common_name": "Cabot Circus", "locality": "Bristol", "indicator": "S1", "latitude": 51.4545, "longitude": -2.5879},
    {"atco_code": "01000001008", "common_name": "St Nicholas Market", "locality": "Bristol", "indicator": "A1", "latitude": 51.4510, "longitude": -2.5880},
    {"atco_code": "01000053304", "common_name": "Broadmead", "locality": "Bristol", "indicator": "C1", "latitude": 51.4580, "longitude": -2.5905},
    {"atco_code": "01000058001", "common_name": "Clifton Down", "locality": "Bristol", "indicator": "CD1", "latitude": 51.4645, "longitude": -2.6098},
    {"atco_code": "01000054001", "common_name": "Bedminster Parade", "locality": "Bristol", "indicator": "B1", "latitude": 51.4420, "longitude": -2.5945},
    {"atco_code": "01000055001", "common_name": "Southmead Hospital", "locality": "Bristol", "indicator": "H1", "latitude": 51.4950, "longitude": -2.5950},
    {"atco_code": "01000057001", "common_name": "UWE Frenchay", "locality": "Bristol", "indicator": "U1", "latitude": 51.5005, "longitude": -2.5490},
    {"atco_code": "01000056001", "common_name": "Bristol Parkway", "locality": "Stoke Gifford", "indicator": "P1", "latitude": 51.5135, "longitude": -2.5420},
    
    # London (sample)
    {"atco_code": "490000252S", "common_name": "Victoria Station", "locality": "London", "indicator": "S", "latitude": 51.4952, "longitude": -0.1439},
    {"atco_code": "490000235Z", "common_name": "Waterloo Station", "locality": "London", "indicator": "Z", "latitude": 51.5036, "longitude": -0.1123},
    {"atco_code": "490001081N", "common_name": "Oxford Circus", "locality": "London", "indicator": "N", "latitude": 51.5150, "longitude": -0.1415},
    {"atco_code": "490007732W", "common_name": "King's Cross Station", "locality": "London", "indicator": "W", "latitude": 51.5309, "longitude": -0.1230},
    {"atco_code": "490001298G", "common_name": "Liverpool Street", "locality": "London", "indicator": "G", "latitude": 51.5188, "longitude": -0.0814},
    
    # Manchester
    {"atco_code": "180000231", "common_name": "Piccadilly Gardens", "locality": "Manchester", "indicator": "Stop A", "latitude": 53.4803, "longitude": -2.2367},
    {"atco_code": "180000173", "common_name": "Piccadilly Station", "locality": "Manchester", "indicator": "Stop A", "latitude": 53.4773, "longitude": -2.2301},
    {"atco_code": "180000065", "common_name": "Victoria Station", "locality": "Manchester", "indicator": "Stop A", "latitude": 53.4875, "longitude": -2.2422},
    {"atco_code": "180000233", "common_name": "Deansgate", "locality": "Manchester", "indicator": "Stop A", "latitude": 53.4742, "longitude": -2.2497},
    
    # Birmingham
    {"atco_code": "43000203201", "common_name": "Bull Street", "locality": "Birmingham", "indicator": "BS1", "latitude": 52.4814, "longitude": -1.8964},
    {"atco_code": "43000204001", "common_name": "New Street Station", "locality": "Birmingham", "indicator": "NS1", "latitude": 52.4778, "longitude": -1.8990},
    {"atco_code": "43000206001", "common_name": "Grand Central", "locality": "Birmingham", "indicator": "GC1", "latitude": 52.4792, "longitude": -1.8994},
    {"atco_code": "43000280101", "common_name": "Snow Hill Station", "locality": "Birmingham", "indicator": "SH1", "latitude": 52.4833, "longitude": -1.8858},
    
    # Liverpool
    {"atco_code": "2400102901", "common_name": "Liverpool ONE", "locality": "Liverpool", "indicator": "L1", "latitude": 53.4041, "longitude": -2.9836},
    {"atco_code": "2400101010", "common_name": "Queen Square", "locality": "Liverpool", "indicator": "QS1", "latitude": 53.4073, "longitude": -2.9825},
    {"atco_code": "2400211081", "common_name": "Lime Street Station", "locality": "Liverpool", "indicator": "LS1", "latitude": 53.4085, "longitude": -2.9773},
    {"atco_code": "2400157801", "common_name": "Paradise Street", "locality": "Liverpool", "indicator": "PS1", "latitude": 53.4039, "longitude": -2.9875},
    
    # Leeds
    {"atco_code": "450010141", "common_name": "Leeds Station", "locality": "Leeds", "indicator": "A1", "latitude": 53.7958, "longitude": -1.5480},
    {"atco_code": "450020080", "common_name": "Corn Exchange", "locality": "Leeds", "indicator": "A1", "latitude": 53.7972, "longitude": -1.5350},
    {"atco_code": "450010054", "common_name": "Vicar Lane", "locality": "Leeds", "indicator": "A1", "latitude": 53.7989, "longitude": -1.5389},
    {"atco_code": "450010060", "common_name": "Boar Lane", "locality": "Leeds", "indicator": "A1", "latitude": 53.7961, "longitude": -1.5436},
    
    # Glasgow
    {"atco_code": "640001451", "common_name": "Buchanan Bus Station", "locality": "Glasgow", "indicator": "Stance 1", "latitude": 55.8642, "longitude": -4.2518},
    {"atco_code": "640002051", "common_name": "Central Station", "locality": "Glasgow", "indicator": "A1", "latitude": 55.8596, "longitude": -4.2581},
    {"atco_code": "640000221", "common_name": "Argyle Street", "locality": "Glasgow", "indicator": "A1", "latitude": 55.8580, "longitude": -4.2520},
    {"atco_code": "640001761", "common_name": "Buchanan Street", "locality": "Glasgow", "indicator": "S", "latitude": 55.8632, "longitude": -4.2530},
    
    # Edinburgh
    {"atco_code": "6200200010", "common_name": "Princes Street", "locality": "Edinburgh", "indicator": "A", "latitude": 55.9524, "longitude": -3.1933},
    {"atco_code": "6200201010", "common_name": "Waverley Bridge", "locality": "Edinburgh", "indicator": "A", "latitude": 55.9513, "longitude": -3.1905},
    {"atco_code": "6200248010", "common_name": "St Andrew Square", "locality": "Edinburgh", "indicator": "A", "latitude": 55.9541, "longitude": -3.1933},
    {"atco_code": "6200206010", "common_name": "Lothian Road", "locality": "Edinburgh", "indicator": "A", "latitude": 55.9474, "longitude": -3.2065},
    
    # Cardiff
    {"atco_code": "570001113456", "common_name": "Central Station", "locality": "Cardiff", "indicator": "CN", "latitude": 51.4763, "longitude": -3.1789},
    {"atco_code": "570001113481", "common_name": "Queen Street Station", "locality": "Cardiff", "indicator": "QS", "latitude": 51.4816, "longitude": -3.1705},
    {"atco_code": "570001113462", "common_name": "St Mary Street", "locality": "Cardiff", "indicator": "SM", "latitude": 51.4805, "longitude": -3.1767},
    {"atco_code": "570001113471", "common_name": "Duke Street", "locality": "Cardiff", "indicator": "KD", "latitude": 51.4831, "longitude": -3.1718},
    
    # Bath
    {"atco_code": "019035903546", "common_name": "Dorchester Street", "locality": "Bath", "indicator": "A", "latitude": 51.3817, "longitude": -2.3571},
    {"atco_code": "019035904161", "common_name": "Manvers Street", "locality": "Bath", "indicator": "B", "latitude": 51.3819, "longitude": -2.3561},
]

# Load AI model
model_path = "bus_prediction_model.json"
bst = None
if os.path.exists(model_path):
    bst = xgb.Booster()
    bst.load_model(model_path)

# --- HELPER FUNCTIONS ---
def haversine(lon1, lat1, lon2, lat2):
    """Calculate distance (km)"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c

def fetch_all_stops():
    """Get all stops - uses default database since BODS stops API is unreliable"""
    return DEFAULT_UK_STOPS

def get_stops_near_location(lat: float, lon: float, radius: float = 5.0) -> List[dict]:
    """Get stops within radius - default 5km to ensure we find stops"""
    all_stops = fetch_all_stops()
    
    nearby = []
    for stop in all_stops:
        try:
            s_lat = stop.get("latitude", 0)
            s_lon = stop.get("longitude", 0)
            if s_lat == 0 or s_lon == 0:
                continue
            
            dist = haversine(lon, lat, s_lon, s_lat)
            if dist <= radius:
                stop_copy = dict(stop)
                stop_copy["distance_km"] = round(dist, 2)
                nearby.append(stop_copy)
        except:
            continue
    
    nearby.sort(key=lambda x: x.get("distance_km", 999))
    
    # If no stops found in radius, return nearest 5 stops regardless of distance
    if not nearby and radius < 50:
        for stop in all_stops:
            try:
                s_lat = stop.get("latitude", 0)
                s_lon = stop.get("longitude", 0)
                if s_lat == 0 or s_lon == 0:
                    continue
                dist = haversine(lon, lat, s_lon, s_lat)
                stop_copy = dict(stop)
                stop_copy["distance_km"] = round(dist, 2)
                nearby.append(stop_copy)
            except:
                continue
        nearby.sort(key=lambda x: x.get("distance_km", 999))
        nearby = nearby[:5]  # Return 5 nearest
    
    return nearby

# --- BODS BUS API ---

def parse_siri_xml(xml_text):
    """Parse SIRI-VM XML"""
    buses = []
    try:
        root = ET.fromstring(xml_text)
        ns = {'siri': 'http://www.siri.org.uk/siri'}
        
        for vehicle in root.findall('.//siri:VehicleActivity', ns):
            try:
                journey = vehicle.find('.//siri:MonitoredVehicleJourney', ns)
                if journey is None:
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
    """Fetch live buses from BODS"""
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

def get_buses_for_user(lat: float, lon: float, radius: float = 1.5):
    """Get buses near user's stops (by proximity or next_stop_ref)"""
    # Get nearby stops
    nearby_stops = get_stops_near_location(lat, lon, radius)
    
    if not nearby_stops:
        return {"stops": [], "buses": []}
    
    stop_ids = {s["atco_code"] for s in nearby_stops if s.get("atco_code")}
    
    # Fetch buses in larger area
    lat_offset = 0.15
    lon_offset = 0.2
    all_buses = fetch_live_buses(lon - lon_offset, lat - lat_offset, lon + lon_offset, lat + lat_offset)
    
    # Find buses that are:
    # 1. Heading to one of user's stops (next_stop_ref matches)
    # 2. OR physically close to one of user's stops (within 800m)
    relevant_buses = []
    for bus in all_buses.values():
        bus_lat = bus["latitude"]
        bus_lon = bus["longitude"]
        next_stop_ref = bus.get("next_stop_ref", "")
        
        # Check if heading to one of user's stops
        is_heading_to_stop = next_stop_ref in stop_ids
        
        # Check if close to any of user's stops
        is_near_stop = False
        nearest_stop = None
        nearest_dist = float('inf')
        
        for stop in nearby_stops:
            dist_to_stop = haversine(stop["longitude"], stop["latitude"], bus_lon, bus_lat)
            if dist_to_stop < nearest_dist:
                nearest_dist = dist_to_stop
                nearest_stop = stop
            if dist_to_stop < 0.8:  # Within 800m of a stop
                is_near_stop = True
        
        if is_heading_to_stop or is_near_stop:
            bus_copy = dict(bus)
            dist_to_user = haversine(lon, lat, bus_lon, bus_lat)
            bus_copy["distance_to_user"] = round(dist_to_user, 2)
            bus_copy["nearest_stop"] = nearest_stop["common_name"] if nearest_stop else "Unknown"
            bus_copy["nearest_stop_dist"] = round(nearest_dist, 2)
            relevant_buses.append(bus_copy)
    
    # Sort by distance to user
    relevant_buses.sort(key=lambda x: x["distance_to_user"])
    
    # Add bus count to stops
    for stop in nearby_stops:
        count = sum(1 for b in relevant_buses 
                   if b.get("next_stop_ref") == stop["atco_code"] 
                   or (b.get("nearest_stop") == stop["common_name"] and b.get("nearest_stop_dist", 999) < 0.5))
        stop["buses_approaching"] = count
    
    return {"stops": nearby_stops, "buses": relevant_buses}

# --- API ENDPOINTS ---

@app.get("/my-buses")
def get_my_buses(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(1.5)
):
    """Main endpoint - get buses approaching stops near user"""
    result = get_buses_for_user(lat, lon, radius)
    return {
        "stops": result["stops"],
        "buses": result["buses"],
        "total_buses": len(result["buses"]),
        "total_stops": len(result["stops"]),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/nearby-stops")
def get_nearby_stops(
    latitude: float = Query(...),
    longitude: float = Query(...),
    radius: float = Query(5.0)
):
    """Get stops near location - returns nearest stops if none in radius"""
    stops = get_stops_near_location(latitude, longitude, radius)
    
    # If no stops found, return 10 nearest regardless of distance
    if not stops:
        all_stops = fetch_all_stops()
        for stop in all_stops:
            try:
                dist = haversine(longitude, latitude, stop["longitude"], stop["latitude"])
                stop_copy = dict(stop)
                stop_copy["distance_km"] = round(dist, 2)
                stops.append(stop_copy)
            except:
                continue
        stops.sort(key=lambda x: x["distance_km"])
        stops = stops[:10]
    
    return {"stops": stops, "count": len(stops), "user_location": {"lat": latitude, "lon": longitude}}

@app.get("/search-stops")
def search_stops(
    q: str = Query(...),
    lat: float = Query(None),
    lon: float = Query(None)
):
    """Search stops"""
    all_stops = fetch_all_stops()
    query = q.lower()
    
    results = []
    for stop in all_stops:
        name = (stop.get("common_name") or "").lower()
        locality = (stop.get("locality") or "").lower()
        
        if query in name or query in locality:
            stop_data = dict(stop)
            if lat and lon:
                try:
                    dist = haversine(lon, lat, stop["longitude"], stop["latitude"])
                    stop_data["distance_km"] = round(dist, 2)
                except:
                    pass
            results.append(stop_data)
    
    if lat and lon:
        results.sort(key=lambda x: x.get("distance_km", 999))
    
    return {"results": results[:30], "count": len(results)}

@app.get("/all-buses-in-area")
def get_all_buses(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(5.0)
):
    """Get all buses in area (for map)"""
    lat_offset = radius / 111.0
    lon_offset = radius / (111.0 * cos(radians(lat)))
    
    buses = fetch_live_buses(lon - lon_offset, lat - lat_offset, lon + lon_offset, lat + lat_offset)
    
    result = []
    for bus in buses.values():
        bus_copy = dict(bus)
        dist = haversine(lon, lat, bus["longitude"], bus["latitude"])
        bus_copy["distance_km"] = round(dist, 2)
        result.append(bus_copy)
    
    return {"buses": result, "count": len(result)}

@app.get("/bus/{bus_id}")
def get_bus(bus_id: str):
    """Get bus details"""
    bus = BUSES_CACHE.get("buses", {}).get(bus_id)
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
    return bus

@app.get("/stop/{stop_id}/buses")
def get_buses_for_stop(
    stop_id: str,
    lat: float = Query(...),
    lon: float = Query(...)
):
    """Get buses approaching a specific stop"""
    # Find the stop
    all_stops = fetch_all_stops()
    stop = None
    for s in all_stops:
        if s.get("atco_code") == stop_id:
            stop = s
            break
    
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
    
    # Fetch buses in area
    lat_offset = 0.2
    lon_offset = 0.25
    all_buses = fetch_live_buses(lon - lon_offset, lat - lat_offset, lon + lon_offset, lat + lat_offset)
    
    # Filter buses for this stop
    stop_buses = []
    for bus in all_buses.values():
        next_stop_ref = bus.get("next_stop_ref", "")
        is_heading_to_stop = next_stop_ref == stop_id
        
        # Check distance to this stop
        dist_to_stop = haversine(stop["longitude"], stop["latitude"], bus["longitude"], bus["latitude"])
        is_near_stop = dist_to_stop < 1.5  # Within 1.5km
        
        if is_heading_to_stop or is_near_stop:
            bus_copy = dict(bus)
            bus_copy["distance_to_stop"] = round(dist_to_stop, 2)
            bus_copy["distance_to_user"] = round(haversine(lon, lat, bus["longitude"], bus["latitude"]), 2)
            stop_buses.append(bus_copy)
    
    # Sort by distance to user
    stop_buses.sort(key=lambda x: x["distance_to_user"])
    
    return {
        "stop": stop,
        "buses": stop_buses,
        "count": len(stop_buses)
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "stops_available": len(DEFAULT_UK_STOPS),
        "buses_tracked": len(BUSES_CACHE.get("buses", {})),
        "version": "3.1.0"
    }

if __name__ == "__main__":
    import uvicorn
    print("Transight API v3.1 - Starting...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
