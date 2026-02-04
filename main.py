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
    description="Real-time bus tracking system - Final Year Project",
    version="3.2.0"
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

# ==========================================
# COMPREHENSIVE BRISTOL BUS STOPS DATABASE
# ==========================================
# Based on Bristol's major bus corridors and key areas
BRISTOL_STOPS = [
    # City Centre - Core area
    {"atco_code": "01000588088", "common_name": "Cabot Circus", "locality": "Bristol City Centre", "indicator": "Stop A", "latitude": 51.4545, "longitude": -2.5879},
    {"atco_code": "01000588089", "common_name": "Cabot Circus", "locality": "Bristol City Centre", "indicator": "Stop B", "latitude": 51.4547, "longitude": -2.5882},
    {"atco_code": "01000001008", "common_name": "St Nicholas Market", "locality": "Bristol City Centre", "indicator": "Stop A", "latitude": 51.4510, "longitude": -2.5880},
    {"atco_code": "01000001009", "common_name": "St Nicholas Market", "locality": "Bristol City Centre", "indicator": "Stop B", "latitude": 51.4512, "longitude": -2.5885},
    {"atco_code": "01000053304", "common_name": "Broadmead", "locality": "Bristol", "indicator": "H4", "latitude": 51.4580, "longitude": -2.5905},
    {"atco_code": "01000053305", "common_name": "Broadmead", "locality": "Bristol", "indicator": "H5", "latitude": 51.4582, "longitude": -2.5908},
    {"atco_code": "01000053220", "common_name": "Temple Meads Station", "locality": "Bristol", "indicator": "T4", "latitude": 51.4496, "longitude": -2.5811},
    {"atco_code": "01000053221", "common_name": "Temple Meads Station", "locality": "Bristol", "indicator": "T5", "latitude": 51.4498, "longitude": -2.5815},
    {"atco_code": "01000054001", "common_name": "Bedminster Parade", "locality": "Bristol", "indicator": "BE", "latitude": 51.4420, "longitude": -2.5945},
    {"atco_code": "01000054002", "common_name": "Bedminster Parade", "locality": "Bristol", "indicator": "BF", "latitude": 51.4422, "longitude": -2.5948},
    {"atco_code": "01000058001", "common_name": "Clifton Down", "locality": "Bristol", "indicator": "CD1", "latitude": 51.4645, "longitude": -2.6098},
    {"atco_code": "01000058002", "common_name": "Clifton Down", "locality": "Bristol", "indicator": "CD2", "latitude": 51.4647, "longitude": -2.6102},
    {"atco_code": "01000055001", "common_name": "Southmead Hospital", "locality": "Bristol", "indicator": "SM1", "latitude": 51.4950, "longitude": -2.5950},
    {"atco_code": "01000055002", "common_name": "Southmead Hospital", "locality": "Bristol", "indicator": "SM2", "latitude": 51.4952, "longitude": -2.5955},
    {"atco_code": "01000056001", "common_name": "Bristol Parkway Station", "locality": "Stoke Gifford", "indicator": "P1", "latitude": 51.5135, "longitude": -2.5420},
    {"atco_code": "01000056002", "common_name": "Bristol Parkway Station", "locality": "Stoke Gifford", "indicator": "P2", "latitude": 51.5137, "longitude": -2.5425},
    {"atco_code": "01000057001", "common_name": "UWE Frenchay", "locality": "Bristol", "indicator": "U1", "latitude": 51.5005, "longitude": -2.5490},
    {"atco_code": "01000057002", "common_name": "UWE Frenchay", "locality": "Bristol", "indicator": "U2", "latitude": 51.5007, "longitude": -2.5495},
    
    # Additional City Centre stops
    {"atco_code": "01000002301", "common_name": "The Centre", "locality": "Bristol", "indicator": "C1", "latitude": 51.4528, "longitude": -2.5975},
    {"atco_code": "01000002302", "common_name": "The Centre", "locality": "Bristol", "indicator": "C2", "latitude": 51.4530, "longitude": -2.5978},
    {"atco_code": "01000004501", "common_name": "College Green", "locality": "Bristol", "indicator": "CG1", "latitude": 51.4520, "longitude": -2.6015},
    {"atco_code": "01000004502", "common_name": "College Green", "locality": "Bristol", "indicator": "CG2", "latitude": 51.4522, "longitude": -2.6018},
    {"atco_code": "01000006701", "common_name": "Park Street", "locality": "Bristol", "indicator": "PS1", "latitude": 51.4545, "longitude": -2.6025},
    {"atco_code": "01000006702", "common_name": "Park Street", "locality": "Bristol", "indicator": "PS2", "latitude": 51.4547, "longitude": -2.6028},
    {"atco_code": "01000008901", "common_name": "Broad Quay", "locality": "Bristol", "indicator": "BQ1", "latitude": 51.4515, "longitude": -2.5950},
    {"atco_code": "01000008902", "common_name": "Broad Quay", "locality": "Bristol", "indicator": "BQ2", "latitude": 51.4517, "longitude": -2.5953},
    {"atco_code": "01000010101", "common_name": "Old Market", "locality": "Bristol", "indicator": "OM1", "latitude": 51.4555, "longitude": -2.5830},
    {"atco_code": "01000010102", "common_name": "Old Market", "locality": "Bristol", "indicator": "OM2", "latitude": 51.4557, "longitude": -2.5833},
    {"atco_code": "01000011201", "common_name": "Rupert Street", "locality": "Bristol", "indicator": "RS1", "latitude": 51.4560, "longitude": -2.5920},
    {"atco_code": "01000011202", "common_name": "Rupert Street", "locality": "Bristol", "indicator": "RS2", "latitude": 51.4562, "longitude": -2.5923},
    {"atco_code": "01000013401", "common_name": "Baldwin Street", "locality": "Bristol", "indicator": "BS1", "latitude": 51.4535, "longitude": -2.5930},
    {"atco_code": "01000013402", "common_name": "Baldwin Street", "locality": "Bristol", "indicator": "BS2", "latitude": 51.4537, "longitude": -2.5933},
    {"atco_code": "01000015601", "common_name": "Victoria Street", "locality": "Bristol", "indicator": "VS1", "latitude": 51.4520, "longitude": -2.5800},
    {"atco_code": "01000015602", "common_name": "Victoria Street", "locality": "Bristol", "indicator": "VS2", "latitude": 51.4522, "longitude": -2.5803},
    {"atco_code": "01000017801", "common_name": "Temple Way", "locality": "Bristol", "indicator": "TW1", "latitude": 51.4480, "longitude": -2.5820},
    {"atco_code": "01000017802", "common_name": "Temple Way", "locality": "Bristol", "indicator": "TW2", "latitude": 51.4482, "longitude": -2.5823},
    
    # Redcliffe / South Bristol
    {"atco_code": "01000018901", "common_name": "Redcliffe Bridge", "locality": "Bristol", "indicator": "RB1", "latitude": 51.4495, "longitude": -2.5870},
    {"atco_code": "01000018902", "common_name": "Redcliffe Bridge", "locality": "Bristol", "indicator": "RB2", "latitude": 51.4497, "longitude": -2.5873},
    {"atco_code": "01000020101", "common_name": "Coronation Road", "locality": "Bristol", "indicator": "CR1", "latitude": 51.4435, "longitude": -2.6000},
    {"atco_code": "01000020102", "common_name": "Coronation Road", "locality": "Bristol", "indicator": "CR2", "latitude": 51.4437, "longitude": -2.6003},
    {"atco_code": "01000022301", "common_name": "Bedminster Down", "locality": "Bristol", "indicator": "BD1", "latitude": 51.4380, "longitude": -2.6050},
    {"atco_code": "01000022302", "common_name": "Bedminster Down", "locality": "Bristol", "indicator": "BD2", "latitude": 51.4382, "longitude": -2.6053},
    {"atco_code": "01000024501", "common_name": "Hartcliffe", "locality": "Bristol", "indicator": "HC1", "latitude": 51.4300, "longitude": -2.6100},
    {"atco_code": "01000024502", "common_name": "Hartcliffe", "locality": "Bristol", "indicator": "HC2", "latitude": 51.4302, "longitude": -2.6103},
    {"atco_code": "01000026701", "common_name": "Withywood", "locality": "Bristol", "indicator": "WW1", "latitude": 51.4250, "longitude": -2.6150},
    {"atco_code": "01000026702", "common_name": "Withywood", "locality": "Bristol", "indicator": "WW2", "latitude": 51.4252, "longitude": -2.6153},
    {"atco_code": "01000028901", "common_name": "Bishopsworth", "locality": "Bristol", "indicator": "BW1", "latitude": 51.4180, "longitude": -2.6200},
    {"atco_code": "01000028902", "common_name": "Bishopsworth", "locality": "Bristol", "indicator": "BW2", "latitude": 51.4182, "longitude": -2.6203},
    
    # East Bristol
    {"atco_code": "01000030101", "common_name": "Lawrence Hill", "locality": "Bristol", "indicator": "LH1", "latitude": 51.4600, "longitude": -2.5750},
    {"atco_code": "01000030102", "common_name": "Lawrence Hill", "locality": "Bristol", "indicator": "LH2", "latitude": 51.4602, "longitude": -2.5753},
    {"atco_code": "01000032301", "common_name": "Easton", "locality": "Bristol", "indicator": "EA1", "latitude": 51.4620, "longitude": -2.5700},
    {"atco_code": "01000032302", "common_name": "Easton", "locality": "Bristol", "indicator": "EA2", "latitude": 51.4622, "longitude": -2.5703},
    {"atco_code": "01000034501", "common_name": "Stapleton Road", "locality": "Bristol", "indicator": "SR1", "latitude": 51.4650, "longitude": -2.5650},
    {"atco_code": "01000034502", "common_name": "Stapleton Road", "locality": "Bristol", "indicator": "SR2", "latitude": 51.4652, "longitude": -2.5653},
    {"atco_code": "01000036701", "common_name": "Fishponds", "locality": "Bristol", "indicator": "FP1", "latitude": 51.4800, "longitude": -2.5350},
    {"atco_code": "01000036702", "common_name": "Fishponds", "locality": "Bristol", "indicator": "FP2", "latitude": 51.4802, "longitude": -2.5353},
    {"atco_code": "01000038901", "common_name": "Staple Hill", "locality": "Bristol", "indicator": "SH1", "latitude": 51.4850, "longitude": -2.5250},
    {"atco_code": "01000038902", "common_name": "Staple Hill", "locality": "Bristol", "indicator": "SH2", "latitude": 51.4852, "longitude": -2.5253},
    {"atco_code": "01000040101", "common_name": "Kingswood", "locality": "Bristol", "indicator": "KW1", "latitude": 51.4900, "longitude": -2.5150},
    {"atco_code": "01000040102", "common_name": "Kingswood", "locality": "Bristol", "indicator": "KW2", "latitude": 51.4902, "longitude": -2.5153},
    {"atco_code": "01000042301", "common_name": "Hanham", "locality": "Bristol", "indicator": "HM1", "latitude": 51.4450, "longitude": -2.5100},
    {"atco_code": "01000042302", "common_name": "Hanham", "locality": "Bristol", "indicator": "HM2", "latitude": 51.4452, "longitude": -2.5103},
    {"atco_code": "01000044501", "common_name": "Longwell Green", "locality": "Bristol", "indicator": "LG1", "latitude": 51.4500, "longitude": -2.5000},
    {"atco_code": "01000044502", "common_name": "Longwell Green", "locality": "Bristol", "indicator": "LG2", "latitude": 51.4502, "longitude": -2.5003},
    
    # North Bristol
    {"atco_code": "01000046701", "common_name": "Horfield", "locality": "Bristol", "indicator": "HF1", "latitude": 51.4900, "longitude": -2.5800},
    {"atco_code": "01000046702", "common_name": "Horfield", "locality": "Bristol", "indicator": "HF2", "latitude": 51.4902, "longitude": -2.5803},
    {"atco_code": "01000048901", "common_name": "Filton", "locality": "Bristol", "indicator": "FI1", "latitude": 51.5000, "longitude": -2.5700},
    {"atco_code": "01000048902", "common_name": "Filton", "locality": "Bristol", "indicator": "FI2", "latitude": 51.5002, "longitude": -2.5703},
    {"atco_code": "01000050101", "common_name": "Patchway", "locality": "Bristol", "indicator": "PA1", "latitude": 51.5250, "longitude": -2.5600},
    {"atco_code": "01000050102", "common_name": "Patchway", "locality": "Bristol", "indicator": "PA2", "latitude": 51.5252, "longitude": -2.5603},
    {"atco_code": "01000052301", "common_name": "Cribbs Causeway", "locality": "Bristol", "indicator": "CC1", "latitude": 51.5250, "longitude": -2.6100},
    {"atco_code": "01000052302", "common_name": "Cribbs Causeway", "locality": "Bristol", "indicator": "CC2", "latitude": 51.5252, "longitude": -2.6103},
    {"atco_code": "01000054501", "common_name": "Henbury", "locality": "Bristol", "indicator": "HE1", "latitude": 51.5100, "longitude": -2.6200},
    {"atco_code": "01000054502", "common_name": "Henbury", "locality": "Bristol", "indicator": "HE2", "latitude": 51.5102, "longitude": -2.6203},
    {"atco_code": "01000056701", "common_name": "Westbury-on-Trym", "locality": "Bristol", "indicator": "WT1", "latitude": 51.4950, "longitude": -2.6250},
    {"atco_code": "01000056702", "common_name": "Westbury-on-Trym", "locality": "Bristol", "indicator": "WT2", "latitude": 51.4952, "longitude": -2.6253},
    {"atco_code": "01000058901", "common_name": "Henleaze", "locality": "Bristol", "indicator": "HZ1", "latitude": 51.4900, "longitude": -2.6150},
    {"atco_code": "01000058902", "common_name": "Henleaze", "locality": "Bristol", "indicator": "HZ2", "latitude": 51.4902, "longitude": -2.6153},
    
    # Clifton / Hotwells
    {"atco_code": "01000060101", "common_name": "Clifton Village", "locality": "Bristol", "indicator": "CV1", "latitude": 51.4550, "longitude": -2.6200},
    {"atco_code": "01000060102", "common_name": "Clifton Village", "locality": "Bristol", "indicator": "CV2", "latitude": 51.4552, "longitude": -2.6203},
    {"atco_code": "01000062301", "common_name": "Clifton Suspension Bridge", "locality": "Bristol", "indicator": "SB1", "latitude": 51.4540, "longitude": -2.6280},
    {"atco_code": "01000062302", "common_name": "Clifton Suspension Bridge", "locality": "Bristol", "indicator": "SB2", "latitude": 51.4542, "longitude": -2.6283},
    {"atco_code": "01000064501", "common_name": "Hotwells", "locality": "Bristol", "indicator": "HW1", "latitude": 51.4500, "longitude": -2.6150},
    {"atco_code": "01000064502", "common_name": "Hotwells", "locality": "Bristol", "indicator": "HW2", "latitude": 51.4502, "longitude": -2.6153},
    {"atco_code": "01000066701", "common_name": "Cumberland Basin", "locality": "Bristol", "indicator": "CB1", "latitude": 51.4450, "longitude": -2.6180},
    {"atco_code": "01000066702", "common_name": "Cumberland Basin", "locality": "Bristol", "indicator": "CB2", "latitude": 51.4452, "longitude": -2.6183},
    
    # Key residential areas
    {"atco_code": "01000068901", "common_name": "Knowle", "locality": "Bristol", "indicator": "KN1", "latitude": 51.4350, "longitude": -2.5900},
    {"atco_code": "01000068902", "common_name": "Knowle", "locality": "Bristol", "indicator": "KN2", "latitude": 51.4352, "longitude": -2.5903},
    {"atco_code": "01000070101", "common_name": "Brislington", "locality": "Bristol", "indicator": "BR1", "latitude": 51.4400, "longitude": -2.5450},
    {"atco_code": "01000070102", "common_name": "Brislington", "locality": "Bristol", "indicator": "BR2", "latitude": 51.4402, "longitude": -2.5453},
    {"atco_code": "01000072301", "common_name": "Whitchurch", "locality": "Bristol", "indicator": "WC1", "latitude": 51.4200, "longitude": -2.5700},
    {"atco_code": "01000072302", "common_name": "Whitchurch", "locality": "Bristol", "indicator": "WC2", "latitude": 51.4202, "longitude": -2.5703},
    {"atco_code": "01000074501", "common_name": "Hengrove", "locality": "Bristol", "indicator": "HG1", "latitude": 51.4150, "longitude": -2.5850},
    {"atco_code": "01000074502", "common_name": "Hengrove", "locality": "Bristol", "indicator": "HG2", "latitude": 51.4152, "longitude": -2.5853},
    {"atco_code": "01000076701", "common_name": "Stockwood", "locality": "Bristol", "indicator": "SK1", "latitude": 51.4100, "longitude": -2.5350},
    {"atco_code": "01000076702", "common_name": "Stockwood", "locality": "Bristol", "indicator": "SK2", "latitude": 51.4102, "longitude": -2.5353},
    {"atco_code": "01000078901", "common_name": "Keynsham", "locality": "Bristol", "indicator": "KY1", "latitude": 51.4150, "longitude": -2.4950},
    {"atco_code": "01000078902", "common_name": "Keynsham", "locality": "Bristol", "indicator": "KY2", "latitude": 51.4152, "longitude": -2.4953},
]

# Load AI model
model_path = "bus_prediction_model.json"
bst = None
if os.path.exists(model_path):
    bst = xgb.Booster()
    bst.load_model(model_path)

# --- HELPER FUNCTIONS ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c

def get_all_bristol_stops():
    """Return all Bristol stops"""
    return BRISTOL_STOPS

def get_stops_near_location(lat: float, lon: float, radius: float = 10.0) -> List[dict]:
    """Get stops within radius - returns ALL if radius is large enough"""
    all_stops = get_all_bristol_stops()
    
    nearby = []
    for stop in all_stops:
        try:
            dist = haversine(lon, lat, stop["longitude"], stop["latitude"])
            if dist <= radius:
                stop_copy = dict(stop)
                stop_copy["distance_km"] = round(dist, 2)
                nearby.append(stop_copy)
        except:
            continue
    
    nearby.sort(key=lambda x: x.get("distance_km", 999))
    return nearby

# --- BODS BUS API ---

def parse_siri_xml(xml_text):
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
    """Get buses approaching a specific stop with real-time positions"""
    # Find the stop
    all_stops = get_all_bristol_stops()
    stop = None
    for s in all_stops:
        if s.get("atco_code") == stop_id:
            stop = s
            break
    
    if not stop:
        return None
    
    # Fetch all buses in Bristol area
    all_buses = fetch_live_buses(-2.7, 51.4, -2.5, 51.6)
    
    # Find buses heading to or near this stop
    stop_buses = []
    for bus in all_buses.values():
        next_stop_ref = bus.get("next_stop_ref", "")
        
        # Check if heading to this stop
        is_heading_to_stop = next_stop_ref == stop_id
        
        # Check distance to this stop
        dist_to_stop = haversine(stop["longitude"], stop["latitude"], bus["longitude"], bus["latitude"])
        is_near_stop = dist_to_stop < 2.0  # Within 2km
        
        if is_heading_to_stop or is_near_stop:
            bus_copy = dict(bus)
            bus_copy["distance_to_stop"] = round(dist_to_stop, 2)
            bus_copy["distance_to_user"] = round(haversine(lon, lat, bus["longitude"], bus["latitude"]), 2)
            stop_buses.append(bus_copy)
    
    # Sort by ETA (estimated based on distance)
    stop_buses.sort(key=lambda x: x["distance_to_stop"])
    
    return {
        "stop": stop,
        "buses": stop_buses,
        "count": len(stop_buses)
    }

# --- API ENDPOINTS ---

@app.get("/stops")
def get_all_stops(
    lat: float = Query(None),
    lon: float = Query(None),
    radius: float = Query(50.0)  # Large radius to get all Bristol stops
):
    """Get all Bristol stops - returns 50 stops for comprehensive coverage"""
    if lat and lon:
        stops = get_stops_near_location(lat, lon, radius)
    else:
        stops = get_all_bristol_stops()
    
    return {
        "stops": stops,
        "count": len(stops),
        "total_available": len(BRISTOL_STOPS),
        "coverage": "Bristol City Region"
    }

@app.get("/nearby-stops")
def get_nearby_stops(
    latitude: float = Query(...),
    longitude: float = Query(...),
    radius: float = Query(10.0)  # 10km radius
):
    """Get nearby stops - for map display"""
    stops = get_stops_near_location(latitude, longitude, radius)
    return {
        "stops": stops,
        "count": len(stops),
        "user_location": {"lat": latitude, "lon": longitude},
        "radius_km": radius
    }

@app.get("/stop/{stop_id}/buses")
def get_stop_buses(
    stop_id: str,
    lat: float = Query(...),
    lon: float = Query(...)
):
    """Get buses for a specific stop with real-time locations"""
    result = get_buses_for_stop(stop_id, lat, lon)
    
    if not result:
        raise HTTPException(status_code=404, detail="Stop not found")
    
    return result

@app.get("/search-stops")
def search_stops(
    q: str = Query(...),
    lat: float = Query(None),
    lon: float = Query(None)
):
    """Search stops"""
    all_stops = get_all_bristol_stops()
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
    
    return {"results": results[:20], "count": len(results)}

@app.get("/all-buses")
def get_all_buses(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(15.0)
):
    """Get all buses in Bristol area"""
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

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "stops_count": len(BRISTOL_STOPS),
        "buses_tracked": len(BUSES_CACHE.get("buses", {})),
        "version": "3.2.0"
    }

if __name__ == "__main__":
    import uvicorn
    print(f"Transight API v3.2 - {len(BRISTOL_STOPS)} Bristol stops loaded")
    uvicorn.run(app, host="0.0.0.0", port=8000)
