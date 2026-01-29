# --- CONFIGURATION ---
TOMTOM_API_KEY = "IgrkN0Ci9H94UGQWLoBSpzSFEycU8Xiy"
BODS_API_KEY = "2bc39438a3eeec844704f182bab7892fea39b8bd"
USE_REAL_APIS = True

ROUTE_72_PATH = [
    (51.4496, -2.5811), # Temple Meads
    (51.4532, -2.5815),
    (51.4560, -2.5820), # Old Market
    (51.4586, -2.5843), # Cabot Circus
    (51.4650, -2.5880),
    (51.5000, -2.5480)  # UWE
]

# --- IMPORTS ---
import requests
import xml.etree.ElementTree as ET
import time
import random

# --- FUNCTIONS ---

def _get_simulated_location():
    """Helper function to simulate movement if API fails"""
    now = int(time.time())
    index = (now // 15) % len(ROUTE_72_PATH)
    return ROUTE_72_PATH[index] + ("Simulated Location",)

def get_traffic_delay(origin_lat, origin_lon, dest_lat, dest_lon):
    """Gets REAL traffic from TomTom API"""
    base_url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"
    
    params = {
        "key": TOMTOM_API_KEY,
        "traffic": "true",
        "travelMode": "car"
    }

    try:
        print(f"   🚗 Calling TomTom API...")
        response = requests.get(base_url, params=params, timeout=8)
        
        if response.status_code == 200:
            data = response.json()
            travel_time_seconds = data['routes'][0]['summary']['travelTimeInSeconds']
            traffic_minutes = round(travel_time_seconds / 60, 1)
            print(f"   ✅ TomTom traffic delay: {traffic_minutes} minutes")
            return traffic_minutes
        else:
            print(f"   ⚠️ TomTom returned status {response.status_code}. Using default.")
            return 10.0
        
    except Exception as e:
        print(f"   ⚠️ TomTom API Error: {e}. Using default (10 min).")
        return 10.0

def get_live_bus_location(bus_line_id="72"):
    """
    Gets REAL location from Bristol Open Data Service (BODS).
    Uses SIRI-VM (XML) which provides live bus locations (functionally equivalent to GTFS-Realtime for locations).

    Refined logic:
    1. Uses a Bounding Box for Bristol area (-2.7,51.4,-2.5,51.55) to catch all relevant operators (e.g. FBRI).
    2. Filters for the specific bus line ID.
    """
    # Bristol Bounding Box: minLon, minLat, maxLon, maxLat
    bbox = "-2.7,51.4,-2.5,51.55"
    url = f"https://data.bus-data.dft.gov.uk/api/v1/datafeed?boundingBox={bbox}&api_key={BODS_API_KEY}"

    try:
        print(f"   📡 Calling BODS API for Bus {bus_line_id} (using Bounding Box)...")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            ns = {'siri': 'http://www.siri.org.uk/siri'}
            
            activities = root.findall(".//siri:VehicleActivity", ns)
            print(f"   ✅ Found {len(activities)} buses in Bristol area")
            
            for activity in activities:
                line_ref = activity.find(".//siri:LineRef", ns)
                
                if line_ref is not None and line_ref.text == bus_line_id:
                    latitude = activity.find(".//siri:Latitude", ns)
                    longitude = activity.find(".//siri:Longitude", ns)
                    operator_ref = activity.find(".//siri:OperatorRef", ns)
                    op_code = operator_ref.text if operator_ref is not None else "Unknown"
                    
                    if latitude is not None and longitude is not None:
                        lat = float(latitude.text)
                        lon = float(longitude.text)
                        print(f"   ✅ REAL BUS LOCATION: Bus {bus_line_id} (Op: {op_code}) at ({lat:.4f}, {lon:.4f})")
                        return (lat, lon, f"En Route ({op_code})")
            
            print(f"   ⚠️ Bus {bus_line_id} not found in live feed. Using fallback.")
            return _get_simulated_location()

    except Exception as e:
        print(f"   ⚠️ BODS API Error: {e}. Using fallback.")
        return _get_simulated_location()

# END OF FILE - NO FUNCTION CALLS BELOW THIS LINE