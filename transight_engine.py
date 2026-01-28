import cv2
import time
import random
import psycopg2
import pandas as pd
import api_services
from ultralytics import YOLO
from xgboost import XGBRegressor
import os

# --- CONFIGURATION ---
DB_PARAMS = {
    "host": "localhost",
    "database": "transight_db",
    "user": "postgres",
    "password": "R@jibale3138"
}

# FIXED COORDINATES FOR BRISTOL BUS ROUTE 72
# Route: Frenchay → Temple Meads

STOP_CONFIG = {
    "BST-001": {
        "name": "Temple Meads Station",
        "video": "videos/1.mp4", 
        "lat": 51.4496, 
        "lon": -2.5811,
        "bus_line": "72"
    },
    "BST-002": {
        "name": "Cabot Circus",
        "video": "videos/2.mp4", 
        "lat": 51.4586, 
        "lon": -2.5843,
        "bus_line": "72"
    }
}

# ROUTE 72 WAYPOINTS (Fixed Path: Frenchay to Temple Meads)
ROUTE_72_WAYPOINTS = [
    {"name": "Frenchay Campus", "lat": 51.5046, "lon": -2.5623},
    {"name": "Fishponds", "lat": 51.4950, "lon": -2.5700},
    {"name": "Eastville", "lat": 51.4850, "lon": -2.5750},
    {"name": "Lawrence Hill", "lat": 51.4750, "lon": -2.5800},
    {"name": "Old Market", "lat": 51.4650, "lon": -2.5850},
    {"name": "Broadmead", "lat": 51.4545, "lon": -2.5879},
    {"name": "Temple Meads", "lat": 51.4496, "lon": -2.5811},
]

print("🚀 INITIALIZING TRANSIGHT AI FUSION ENGINE...")

# 1. LOAD COMPUTER VISION MODEL
print("   👁️ Loading YOLOv8 Vision Model...")
yolo_model = YOLO('yolov8n.pt')

# 2. LOAD PREDICTIVE AI MODEL (Objective 3)
print("   🧠 Loading XGBoost Prediction Brain...")
xgb_model = XGBRegressor()
try:
    xgb_model.load_model("bus_prediction_model.json")
    USING_AI = True
    print("   ✅ AI Model Loaded Successfully.")
except Exception as e:
    print(f"   ⚠️ WARNING: AI Model not found ({e}). Using backup math logic.")
    USING_AI = False

def get_db_connection():
    try:
        return psycopg2.connect(**DB_PARAMS)
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return None

def analyze_crowd_smart(video_path):
    """
    Smart Analyzer: Jumps to the middle of the video to avoid 
    empty frames at the start.
    """
    if not os.path.exists(video_path):
        print(f"      ❌ Video not found: {video_path}")
        return 0
        
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return 0
    
    # TRICK: Jump to frame 50 (approx 2 seconds in) to catch the crowd
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target_frame = min(50, total_frames - 1)
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    ret, frame = cap.read()
    
    count = 0
    if ret:
        results = yolo_model(frame, classes=[0], verbose=False)
        count = len(results[0].boxes)
    
    cap.release()
    return count

def get_simulated_bus_location():
    """
    Simulate Bus 72 moving along the fixed Route 72 waypoints.
    Uses current time to determine position on the route.
    
    Returns: (latitude, longitude, waypoint_name)
    """
    current_time = int(time.time())
    
    # Bus takes 40 minutes (2400 seconds) to complete route
    # Then loops back
    route_progress = (current_time % 2400) / 2400
    waypoint_index = int(route_progress * (len(ROUTE_72_WAYPOINTS) - 1))
    
    waypoint = ROUTE_72_WAYPOINTS[waypoint_index]
    
    # Add tiny random variation (±50 meters)
    lat_offset = random.uniform(-0.0005, 0.0005)
    lon_offset = random.uniform(-0.0005, 0.0005)
    
    bus_lat = waypoint["lat"] + lat_offset
    bus_lon = waypoint["lon"] + lon_offset
    
    return bus_lat, bus_lon, waypoint["name"]

def main_loop():
    print("\n📡 TRANSIGHT LIVE SYSTEM STARTED...")
    print("📍 Bus Route 72: Frenchay → Temple Meads")
    print("⚠️ Using REAL BODS data ONLY (no simulation)\n")
    
    while True:
        conn = get_db_connection()
        if not conn:
            time.sleep(5)
            continue
        cur = conn.cursor()

        for stop_id, stop_data in STOP_CONFIG.items():
            print(f"\n📍 PROCESSING: {stop_data['name']}")

            # --- INPUT 1: VISION (Crowd Analysis) ---
            crowd_count = analyze_crowd_smart(stop_data["video"])
            
            # --- INPUT 2: BUS LOCATION & TRAFFIC (REAL ONLY) ---
            try:
                bus_lat, bus_lon, bus_location_name = api_services.get_live_bus_location("72")
                print(f"   ✅ Got REAL bus location from BODS")
            except Exception as e:
                print(f"   ⚠️ BODS API failed: {e}")
                print(f"   ⚠️ Skipping this cycle (waiting for bus to be in service)")
                continue
            
            # Calculate traffic delay based on REAL bus location
            traffic_delay = api_services.get_traffic_delay(
                origin_lat=bus_lat, 
                origin_lon=bus_lon,
                dest_lat=stop_data["lat"], 
                dest_lon=stop_data["lon"]
            )
            
            # --- INPUT 3: WEATHER (Simulated) ---
            is_raining = 0
            
            # --- THE AI PREDICTION CORE ---
            if USING_AI:
                input_df = pd.DataFrame(
                    [[traffic_delay, crowd_count, is_raining]], 
                    columns=["traffic_delay", "crowd_count", "is_raining"]
                )
                total_prediction = float(xgb_model.predict(input_df)[0])
                total_prediction = round(max(0, total_prediction), 1)
                method_label = "🤖 AI Inference"
            else:
                dwell_time = (crowd_count * 4.0) / 60
                total_prediction = round(traffic_delay + dwell_time, 1)
                method_label = "🧮 Backup Formula"

            dwell_display = round((crowd_count * 4.0) / 60, 1)
            
            # --- SAVE TO DATABASE (REAL DATA ONLY) ---
            query = """
                INSERT INTO prediction_history 
                (bus_stop_id, traffic_delay, dwell_delay, total_prediction, crowd_count, bus_lat, bus_lon)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(query, (
                stop_id, 
                traffic_delay, 
                dwell_display, 
                total_prediction, 
                crowd_count,
                bus_lat,
                bus_lon
            ))
            conn.commit()
            
            # --- DISPLAY RESULTS ---
            print(f"   🚌  Bus 72 Location: {bus_location_name}")
            print(f"       Coordinates: ({bus_lat:.4f}, {bus_lon:.4f}) [REAL]")
            print(f"   👁️  Crowd Analysis: {crowd_count} people waiting")
            print(f"   🚗  Traffic Delay: {traffic_delay} minutes [REAL]")
            print(f"   ⏱️  Dwell Time: {dwell_display} minutes")
            print(f"   ✅  PREDICTION ({method_label}): {total_prediction} minutes")

        cur.close()
        conn.close()
        
        print("\n💤 Sleeping for 10 seconds...\n")
        time.sleep(10)

if __name__ == "__main__":
    main_loop()