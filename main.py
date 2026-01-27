from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import pandas as pd
import time

import api_services

app = FastAPI()

# Allow React to talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB Config (Same as your engine)
DB_PARAMS = {
    "host": "localhost",
    "database": "transight_db",
    "user": "postgres",
    "password": "R@jibale3138"
}

@app.get("/")
def read_root():
    return {"status": "Transight API is Online 🟢"}

@app.get("/predict/{stop_id}")
def get_prediction(stop_id: str):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        
        # Get the LATEST prediction for this specific stop
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

@app.get("/bus-location/{bus_line}")
def get_bus_location(bus_line: str):
    """Get current bus location"""
    try:
        lat, lon = api_services.get_live_bus_location(bus_line)
        return {
            "bus_line": bus_line,
            "latitude": lat,
            "longitude": lon,
            "timestamp": time.time()
        }
    except Exception as e:
        return {"error": str(e)}