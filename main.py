from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import time
import requests
import xml.etree.ElementTree as ET  # <--- Built-in Python Library (No Install Needed)

# --- 1. SETUP & CONFIG ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Config
DB_PARAMS = {
    "host": "localhost",
    "database": "transight_db",
    "user": "postgres",
    "password": "R@jibale3138"
}

# UK Bus Open Data Service API Key
BODS_API_KEY = "bc39438a3eeec844704f182bab7892fea39b8bd" # <--- PASTE KEY HERE

# --- 2. THE REAL-TIME DATA FETCHING FUNCTION ---
def get_real_bristol_buses():
    """
    Fetches LIVE bus data from UK Gov API in JSON format.
    """
    # Bristol Bounding Box
    bbox = "-2.7,51.4,-2.5,51.5"
    url = f"https://data.bus-data.dft.gov.uk/api/v1/datafeed?boundingBox={bbox}&api_key={BODS_API_KEY}"
    
    try:
        # FORCE JSON RESPONSE
        response = requests.get(url, headers={'Accept': 'application/json'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Debug: Print the first bit of data to see if it worked
            print("✅ Raw Data Received (First 100 chars):", str(data)[:100])
            
            # Navigate the JSON structure (Siri -> ServiceDelivery -> VehicleMonitoringDelivery)
            try:
                delivery = data.get('Siri', {}).get('ServiceDelivery', {}).get('VehicleMonitoringDelivery', [])
                
                # The API usually returns a list for VehicleMonitoringDelivery, pick the first one
                if isinstance(delivery, list) and len(delivery) > 0:
                    activity = delivery[0].get('VehicleActivity', [])
                else:
                    # Sometimes it's a direct dictionary
                    activity = delivery.get('VehicleActivity', [])
                
                live_buses = []
                
                for bus in activity:
                    journey = bus.get('MonitoredVehicleJourney', {})
                    line = journey.get('PublishedLineName', 'Unknown')
                    operator = journey.get('OperatorRef', 'Unknown')
                    
                    # Coordinates
                    location = journey.get('VehicleLocation', {})
                    lat = location.get('Latitude')
                    lng = location.get('Longitude')
                    
                    # Identifiers
                    vehicle_ref = journey.get('VehicleRef', 'Unknown')
                    
                    if lat and lng:
                        live_buses.append({
                            "id": vehicle_ref,
                            "line": line,
                            "lat": float(lat),
                            "lng": float(lng),
                            "operator": operator
                        })
                
                print(f"🚌 Found {len(live_buses)} active buses.")
                return live_buses

            except Exception as e:
                print(f"JSON Parsing Error: {e}")
                return []
        else:
            print(f"API Error: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Connection Error: {e}")
        return []

# --- 3. API ENDPOINTS ---

@app.get("/")
def read_root():
    return {"status": "Transight Real-Time System Online 🟢"}

@app.get("/live-locations")
def live_locations():
    """
    STRICTLY REAL DATA.
    If no buses are found, returns 0. No simulation.
    """
    real_data = get_real_bristol_buses()
    
    return {
        "status": "success", 
        "source": "REAL_LIVE_BODS_API",
        "count": len(real_data),
        "buses": real_data
    }

@app.get("/bus-location/{bus_line}")
def get_bus_location(bus_line: str):
    """
    Finds a specific bus line in the real-time feed.
    """
    all_buses = get_real_bristol_buses()
    
    # Filter for the specific bus line (e.g., "72")
    target_bus = next((b for b in all_buses if b['line'] == bus_line), None)
    
    if target_bus:
        return {
            "bus_line": bus_line,
            "latitude": target_bus['lat'],
            "longitude": target_bus['lng'],
            "source": "REAL_GPS",
            "timestamp": time.time()
        }
    else:
        # STRICTLY NO SIMULATION
        return {
            "error": "Bus not currently active in live feed", 
            "bus_line": bus_line
        }

@app.get("/predict/{stop_id}")
def get_prediction(stop_id: str):
    # This remains the same (Database Logic)
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        
        query = """
            SELECT traffic_delay, dwell_delay, total_prediction, crowd_count, bus_lat, bus_lon 
            FROM prediction_history 
            WHERE bus_stop_id = %s 
            ORDER BY timestamp DESC 
            LIMIT 1
        """
        cur.execute(query, (stop_id,))
        row = cur.fetchone()
        
        cur.close()
        conn.close()

        if row:
            return {
                "stop_id": stop_id,
                "bus_line": "72",
                "traffic_delay": row[0],
                "dwell_delay": row[1],
                "traffic_status": "Heavy" if row[0] > 15 else "Moderate" if row[0] > 5 else "Light",
                "total_time_min": row[2],
                "crowd_count": row[3],
                "crowd_level": "High" if row[3] > 10 else "Low",
                "bus_lat": row[4],
                "bus_lon": row[5]
            }
        else:
            return {"error": "No data found for this stop yet."}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Database Error")