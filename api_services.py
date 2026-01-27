import requests
import random
import xml.etree.ElementTree as ET
import time

# --- CONFIGURATION ---

# 1. TRAFFIC DATA (TomTom) - YOUR KEY IS PRESERVED HERE
TOMTOM_API_KEY = "IgrkN0Ci9H94UGQWLoBSpzSFEycU8Xiy"

# 2. BUS DATA (Bristol Open Data)
# ⚠️ PASTE YOUR NEW BODS KEY HERE ⚠️
BODS_API_KEY = "2bc39438a3eeec844704f182bab7892fea39b8bd"

# Set to True to use real APIs. 
# If False, it uses simulation for both (Safe for Viva demo).
USE_REAL_APIS = True

# --- FALLBACK DATA (For Safety) ---
# If the Bus API fails, we simulate the bus moving along this real path
ROUTE_72_PATH = [
    (51.4496, -2.5811), # Temple Meads
    (51.4532, -2.5815),
    (51.4560, -2.5820), # Old Market
    (51.4586, -2.5843), # Cabot Circus
    (51.4650, -2.5880),
    (51.5000, -2.5480)  # UWE
]

def get_traffic_delay(origin_lat, origin_lon, dest_lat, dest_lon):
    """
    Asks TomTom: 'How long to drive this segment in CURRENT traffic?'
    Returns: Minutes (float)
    """
    if not USE_REAL_APIS:
        return round(random.uniform(5.0, 15.0), 1)

    base_url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"
    
    params = {
        "key": TOMTOM_API_KEY,
        "traffic": "true",
        "travelMode": "car"
    }

    try:
        response = requests.get(base_url, params=params, timeout=5)
        data = response.json()
        travel_time_seconds = data['routes'][0]['summary']['travelTimeInSeconds']
        return round(travel_time_seconds / 60, 1)
        
    except Exception as e:
        print(f"⚠️ TomTom API Error: {e}")
        return 10.0 # Default safety value

def get_live_bus_location(bus_line_id="72"):
    """
    Attempts to get REAL location from Bristol API (BODS).
    If that fails, falls back to the Simulated Route 72 path.
    """
    if not USE_REAL_APIS or BODS_API_KEY == "2bc39438a3eeec844704f182bab7892fea39b8bd":
        return _get_simulated_location()

    # The Official Bristol Feed URL (SIRI-VM)
    url = f"https://data.bus-data.dft.gov.uk/api/v1/datafeed?operatorRef=FBAL&api_key={BODS_API_KEY}"

    try:
        response = requests.get(url, timeout=8)
        
        if response.status_code == 200:
            # Parse the XML
            root = ET.fromstring(response.content)
            ns = {'siri': 'http://www.siri.org.uk/siri'}
            
            # Find all buses
            activities = root.findall(".//siri:VehicleActivity", ns)
            
            for activity in activities:
                line_ref = activity.find(".//siri:LineRef", ns)
                
                # Check if this is Bus 72
                if line_ref is not None and line_ref.text == bus_line_id:
                    loc = activity.find(".//siri:VehicleLocation", ns)
                    lat = float(loc.find("siri:Latitude", ns).text)
                    lon = float(loc.find("siri:Longitude", ns).text)
                    print(f"   📡 FOUND LIVE BUS 72: {lat}, {lon}")
                    return (lat, lon)
        
        print("   ⚠️ Bus 72 not found in live feed. Switching to simulation.")
        return _get_simulated_location()

    except Exception as e:
        print(f"   ⚠️ Bus API Error: {e}. Switching to simulation.")
        return _get_simulated_location()

def _get_simulated_location():
    """Helper function to simulate movement if API fails"""
    now = int(time.time())
    # Move to next stop every 15 seconds
    index = (now // 15) % len(ROUTE_72_PATH)
    return ROUTE_72_PATH[index]