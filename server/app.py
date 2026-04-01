"""
Transight — Flask Backend & Fusion Engine
Phase 2 MVP: Real-Time Digital Twin for Bristol Bus Services.

The Fusion Engine runs as a background daemon thread.  Every 10 seconds it:
  1. Queries ALL routes from the DB   (scalability — no hard-coded routes)
  2. Fetches live GPS from BODS        (Bus Open Data Service - SIRI-VM XML)
  3. Fetches live traffic from TomTom
  4. Runs YOLOv8 on the simulated camera feed (bus_queue.mp4)
  5. Computes ETA using real bus position + traffic + crowd
  6. Persists a BusLog row
"""

import os
import time
import math
import threading
import logging
import atexit
import signal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import cv2
import joblib
from ultralytics import YOLO
from flask import Flask, jsonify
from flask_cors import CORS

from models import db, Route, BusLog
from bods_parser import fetch_bods_vehicles
from gtfs_parser import (
    build_gtfs_datetime,
    get_cached_gtfs_data,
    select_live_route_trip,
    select_next_route_trip,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:R%40jibale3138@localhost:5432/transight_db",
)
BODS_API_KEY = os.getenv("BODS_API_KEY")
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")  # Traffic Flow API
TOMTOM_ROUTING_KEY = os.getenv("TOMTOM_ROUTING_KEY")  # Routing API
VIDEO_PATH = os.getenv("VIDEO_PATH", os.path.join(os.path.dirname(__file__), "..", "bus_queue.mp4"))
MODEL_PATH = os.path.join(os.path.dirname(__file__), "yolov8n.pt")
ETA_MODEL_PATH = os.path.join(os.path.dirname(__file__), "xgboost_eta_model.joblib")
GTFS_ZIP_PATH = os.path.join(os.path.dirname(__file__), "..", "itm_south_west_gtfs.zip")
FUSION_INTERVAL = int(os.getenv("FUSION_INTERVAL", "10"))  # seconds
LIVE_DATA_MAX_AGE_SECONDS = int(os.getenv("LIVE_DATA_MAX_AGE_SECONDS", "180"))
ROUTE_PROXIMITY_THRESHOLD_KM = float(os.getenv("ROUTE_PROXIMITY_THRESHOLD_KM", "2.0"))
UK_TZ = ZoneInfo("Europe/London")

_operator_allowlist = [op.strip() for op in os.getenv("BODS_OPERATOR_ALLOWLIST", "FBRI,FBRA").split(",") if op.strip()]
if len(_operator_allowlist) >= 2:
    BODS_OPERATOR_ALLOWLIST = tuple(dict.fromkeys(_operator_allowlist))[:2]
else:
    BODS_OPERATOR_ALLOWLIST = ("FBRI", "FBRA")

# Bristol operator code (First Bristol = FBRI)
BODS_OPERATOR = BODS_OPERATOR_ALLOWLIST[0]

# Major stops where crowd detection is applied (others assume 0 crowd)
# Format: (stop_name, lat, lng)
MAJOR_STOPS_OUTBOUND = [
    ("Temple Meads Stn", 51.44898, -2.58262),
    ("The Centre", 51.45386, -2.59758),
    ("College Green", 51.45301, -2.60086),
    ("Memorial Stadium", 51.49052, -2.58315),  # Approximate
    ("Frenchay Campus", 51.50019, -2.54622),
]

MAJOR_STOPS_INBOUND = [
    ("Frenchay Campus", 51.50019, -2.54622),
    ("Memorial Stadium", 51.49052, -2.58315),
    ("College Green", 51.45301, -2.60086),
    ("Temple Meads Stn", 51.44898, -2.58262),
]

# Distance threshold to consider bus "at" a major stop (in km)
CROWD_DETECTION_RADIUS_KM = 0.3  # 300 meters

# Store recent crowd counts for smoothing (prevents fluctuation)
_crowd_history = {}
MAX_CROWD_HISTORY = 3  # Average last 3 readings
_latest_bus_metadata = {}
_eta_model = None


def parse_gtfs_time(value):
    """Parse a GTFS time string such as HH:MM or HH:MM:SS."""
    if not value:
        return None

    parts = str(value).split(":")
    if len(parts) < 2:
        return None

    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        return hour, minute, second
    except ValueError:
        return None


def format_gtfs_time(value):
    """Render a GTFS time string as HH:MM for the UI."""
    parsed = parse_gtfs_time(value)
    if not parsed:
        return None

    hour, minute, _ = parsed
    return f"{hour:02d}:{minute:02d}"


def build_scheduled_datetime(reference_time, value):
    """Build a datetime for a GTFS scheduled time relative to reference_time."""
    parsed = parse_gtfs_time(value)
    if not parsed:
        return None

    hour, minute, second = parsed
    scheduled = reference_time.replace(hour=0, minute=0, second=0, microsecond=0)
    scheduled += timedelta(hours=hour, minutes=minute, seconds=second)
    return scheduled


def parse_iso_datetime(value):
    """Parse an ISO datetime string from BODS into a datetime."""
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def is_recent_live_timestamp(timestamp, max_age_seconds=LIVE_DATA_MAX_AGE_SECONDS):
    """Return True when a timestamp is recent enough to count as live."""
    if not timestamp:
        return False

    now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
    age_seconds = (now - timestamp).total_seconds()
    return 0 <= age_seconds <= max_age_seconds


def route_distance_km(route_path, lat, lng):
    """Return the minimum distance from a bus position to the stored route path."""
    if not route_path:
        return float("inf")

    return min(
        haversine(lat, lng, point[0], point[1])
        for point in route_path
        if isinstance(point, (list, tuple)) and len(point) >= 2
    )


def is_vehicle_live_for_route(vehicle_data, route):
    """Filter out stale or off-route BODS vehicles."""
    recorded_at = parse_iso_datetime(vehicle_data.get("recorded_at"))
    if not is_recent_live_timestamp(recorded_at):
        return False

    if route is None or not route.route_path:
        return True

    distance_km = route_distance_km(route.route_path, vehicle_data["lat"], vehicle_data["lng"])
    return distance_km <= ROUTE_PROXIMITY_THRESHOLD_KM


def resolve_vehicle_operator(vehicle_data):
    """Resolve a vehicle's operator from BODS data or the vehicle ID prefix."""
    operator = (vehicle_data.get("operator") or "").strip()
    if operator:
        return operator

    vehicle_id = (vehicle_data.get("vehicle_id") or "").strip()
    if "-" in vehicle_id:
        return vehicle_id.split("-", 1)[0].strip() or "unknown"

    return "unknown"


def get_current_stop_context(route_stops, current_lat, current_lng):
    """Return the closest stop and sequence for the current bus position."""
    min_dist = float("inf")
    current_stop_seq = 0
    current_stop = None

    for rs in route_stops:
        dist = haversine(current_lat, current_lng, rs.stop.lat, rs.stop.lng)
        if dist < min_dist:
            min_dist = dist
            current_stop_seq = rs.sequence
            current_stop = rs

    return current_stop_seq, current_stop, min_dist


def load_eta_model():
    """Load the trained XGBoost ETA model once per process."""
    global _eta_model

    if _eta_model is not None:
        return _eta_model

    if not os.path.exists(ETA_MODEL_PATH):
        logger.warning(f"[XGBoost] Model not found at {ETA_MODEL_PATH}; using formula fallback")
        _eta_model = False
        return None

    try:
        _eta_model = joblib.load(ETA_MODEL_PATH)
        logger.info(f"[XGBoost] Loaded ETA model from {ETA_MODEL_PATH}")
        return _eta_model
    except Exception as exc:
        logger.error(f"[XGBoost] Failed to load ETA model: {exc}")
        _eta_model = False
        return None


def build_eta_features(route, passenger_count, traffic_delay_seconds, current_stop_seq, remaining_stops, current_time):
    """Create the exact live feature vector used by XGBoost."""
    total_stops = route.total_stops or 0
    progress_ratio = 0.0
    if total_stops > 1:
        progress_ratio = current_stop_seq / float(total_stops - 1)

    return {
        "passenger_count": passenger_count or 0,
        "traffic_delay": traffic_delay_seconds or 0.0,
        "hour": current_time.hour if current_time else 12,
        "day_of_week": current_time.weekday() if current_time else 0,
        "current_stop_sequence": current_stop_seq or 0,
        "remaining_stops": remaining_stops or 0,
        "total_stops": total_stops,
        "progress_ratio": progress_ratio,
    }


def predict_eta_xgboost(route, passenger_count, traffic_delay_seconds, current_stop_seq, remaining_stops, current_time):
    """Predict ETA using the trained model when available."""
    model = load_eta_model()
    if model is None or model is False:
        return None

    features = build_eta_features(
        route,
        passenger_count,
        traffic_delay_seconds,
        current_stop_seq,
        remaining_stops,
        current_time,
    )

    try:
        ordered = [[
            features["passenger_count"],
            features["traffic_delay"],
            features["hour"],
            features["day_of_week"],
            features["current_stop_sequence"],
            features["remaining_stops"],
            features["total_stops"],
            features["progress_ratio"],
        ]]
        prediction = model.predict(ordered)[0]
        return round(float(prediction), 1)
    except Exception as exc:
        logger.error(f"[XGBoost] Prediction failed: {exc}")
        return None


def calculate_route_delay(route, current_stop_seq, eta_min):
    """Estimate route delay versus timetable using route progress."""
    if route is None or eta_min is None:
        return 0.0

    total_stops = route.total_stops or 0
    if total_stops <= 1 or not route.typical_duration_min:
        return round(max(0.0, float(eta_min)), 1)

    progress_ratio = min(max(current_stop_seq / float(total_stops - 1), 0.0), 1.0)
    expected_remaining_min = route.typical_duration_min * (1 - progress_ratio)
    delay_min = max(0.0, float(eta_min) - expected_remaining_min)
    return round(delay_min, 1)


def to_uk_datetime(value=None):
    """Convert a datetime into Europe/London local time."""
    if value is None:
        return datetime.now(UK_TZ)
    if value.tzinfo:
        return value.astimezone(UK_TZ)
    return value.replace(tzinfo=UK_TZ)


def get_gtfs_schedule_trip(route, current_time=None, current_stop_seq=None, mode="next"):
    """Return the GTFS trip that should drive the current timetable display."""
    if not os.path.exists(GTFS_ZIP_PATH):
        logger.warning(f"[GTFS] Zip not found at {GTFS_ZIP_PATH}; using DB fallback")
        return None

    gtfs_data = get_cached_gtfs_data(GTFS_ZIP_PATH)
    if not gtfs_data:
        logger.warning("[GTFS] Failed to load cached GTFS data; using DB fallback")
        return None

    local_time = to_uk_datetime(current_time)

    try:
        if mode == "live" and current_stop_seq is not None:
            return select_live_route_trip(
                gtfs_data,
                route.route_name,
                route.direction,
                local_time,
                current_stop_seq,
                origin_name=route.origin_name,
                destination_name=route.destination_name,
            )

        return select_next_route_trip(
            gtfs_data,
            route.route_name,
            route.direction,
            local_time,
            origin_name=route.origin_name,
            destination_name=route.destination_name,
        )
    except Exception as exc:
        logger.error(f"[GTFS] Trip selection failed: {exc}")
        return None


def build_schedule_only_response(route_id, route, current_time=None):
    """Build a schedule-only stop list when no live bus is available."""
    from models import RouteStop

    selected_trip = get_gtfs_schedule_trip(route, current_time=current_time, mode="next")
    stops_data = []
    service_time = None

    if selected_trip:
        service_time = format_gtfs_time(selected_trip.get("service_time"))
        for stop in selected_trip["stops"]:
            stops_data.append({
                "stop_sequence": stop["sequence"],
                "stop_name": stop["stop_name"],
                "stop_id": stop["stop_id"],
                "scheduled_arrival": format_gtfs_time(stop["arrival_time"]),
                "predicted_arrival": None,
                "delay_minutes": None,
                "delay_text": "No live bus scheduled",
                "status": "scheduled",
            })
    else:
        route_stops = (RouteStop.query
                       .filter_by(route_id=route_id)
                       .order_by(RouteStop.sequence)
                       .all())

        for rs in route_stops:
            stops_data.append({
                "stop_sequence": rs.sequence,
                "stop_name": rs.stop.stop_name,
                "stop_id": rs.stop.stop_id,
                "scheduled_arrival": format_gtfs_time(rs.scheduled_arrival),
                "predicted_arrival": None,
                "delay_minutes": None,
                "delay_text": "No live bus scheduled",
                "status": "scheduled",
            })
        if route_stops:
            service_time = format_gtfs_time(route_stops[0].scheduled_arrival)

    return {
        "route": route.to_dict(),
        "service_time": service_time,
        "current_delay": None,
        "bus_available": False,
        "message": "No live bus currently available on this route",
        "is_live": False,
        "stops": stops_data,
    }


def get_smoothed_crowd_count(vehicle_id, current_count):
    """
    Get smoothed crowd count by averaging recent readings.
    Prevents ETA fluctuation from frame-to-frame YOLO variations.
    """
    global _crowd_history
    
    if vehicle_id not in _crowd_history:
        _crowd_history[vehicle_id] = []
    
    # Add current count to history
    _crowd_history[vehicle_id].append(current_count)
    
    # Keep only recent readings
    if len(_crowd_history[vehicle_id]) > MAX_CROWD_HISTORY:
        _crowd_history[vehicle_id].pop(0)
    
    # Calculate average
    avg_count = sum(_crowd_history[vehicle_id]) / len(_crowd_history[vehicle_id])
    
    return round(avg_count)


def is_near_major_stop(bus_lat, bus_lng, direction):
    """
    Check if bus is near a major stop where crowd detection should be applied.
    
    Returns: (is_near_major_stop, nearest_stop_name)
    """
    major_stops = MAJOR_STOPS_OUTBOUND if direction == 'outbound' else MAJOR_STOPS_INBOUND
    
    min_dist = float('inf')
    nearest_stop = None
    
    for stop_name, stop_lat, stop_lng in major_stops:
        dist = haversine(bus_lat, bus_lng, stop_lat, stop_lng)
        if dist < min_dist:
            min_dist = dist
            nearest_stop = stop_name
    
    is_near = min_dist <= CROWD_DETECTION_RADIUS_KM
    return is_near, nearest_stop, min_dist

# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
CORS(app)
db.init_app(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("transight")


# =========================================================================
# Helper — Haversine Distance (km)
# =========================================================================
def haversine(lat1, lon1, lat2, lon2):
    """Return the great-circle distance in km between two GPS points."""
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# =========================================================================
# OSRM Routing API — Accurate Road Distance (Free, No API Key)
# =========================================================================
def get_route_distance_osrm(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    Get actual road distance using OSRM (Open Source Routing Machine).
    Free public API, no key required.

    Returns: (distance_km, travel_time_seconds, route_summary)
    """
    try:
        # OSRM public demo server
        url = f"http://router.project-osrm.org/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"

        params = {
            'overview': 'false',  # Don't need full geometry
            'steps': 'false',     # Don't need turn-by-turn
        }

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get('code') == 'Ok' and 'routes' in data and len(data['routes']) > 0:
            route = data['routes'][0]

            distance_km = route['distance'] / 1000.0  # meters to km
            travel_time_sec = route['duration']  # seconds

            logger.info(f"[OSRM Routing] Route: {distance_km:.2f}km, "
                       f"Time: {travel_time_sec}s ({travel_time_sec/60:.1f}min)")

            return distance_km, travel_time_sec, {
                'distance_km': distance_km,
                'travel_time_sec': travel_time_sec,
                'traffic_delay_sec': 0,  # OSRM doesn't include traffic
            }
        else:
            logger.warning(f"[OSRM Routing] No routes found - falling back to haversine")
            return haversine(origin_lat, origin_lng, dest_lat, dest_lng), None, None

    except Exception as exc:
        logger.error(f"[OSRM Routing] Error: {exc}")
        return haversine(origin_lat, origin_lng, dest_lat, dest_lng), None, None


# =========================================================================
# TomTom Routing API — Accurate Road Distance (Requires Routing API Key)
# =========================================================================
def get_route_distance_tomtom(origin_lat, origin_lng, dest_lat, dest_lng):
    """
    Get actual road distance using TomTom Routing API (with live traffic).

    Returns: (distance_km, travel_time_seconds, route_summary)
    """
    if not TOMTOM_ROUTING_KEY:
        logger.warning("[TomTom Routing] No routing API key - falling back to OSRM")
        return get_route_distance_osrm(origin_lat, origin_lng, dest_lat, dest_lng)

    try:
        url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin_lat},{origin_lng}:{dest_lat},{dest_lng}/json"

        params = {
            'key': TOMTOM_ROUTING_KEY,  # Use routing API key
            'traffic': 'true',  # Include live traffic in calculation
            'routeType': 'fastest',  # Fastest route
            # Note: travelMode 'bus' may require specific API subscription
        }

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if 'routes' in data and len(data['routes']) > 0:
            route = data['routes'][0]
            summary = route['summary']

            distance_km = summary['lengthInMeters'] / 1000.0
            travel_time_sec = summary['travelTimeInSeconds']
            traffic_delay_sec = summary.get('trafficDelayInSeconds', 0)

            logger.info(f"[TomTom Routing] Route: {distance_km:.2f}km, "
                       f"Time: {travel_time_sec}s ({travel_time_sec/60:.1f}min), "
                       f"Traffic delay: {traffic_delay_sec}s")

            return distance_km, travel_time_sec, {
                'distance_km': distance_km,
                'travel_time_sec': travel_time_sec,
                'traffic_delay_sec': traffic_delay_sec,
                'route_points': route.get('legs', [{}])[0].get('points', [])
            }
        else:
            logger.warning("[TomTom Routing] No routes found - falling back to haversine")
            return haversine(origin_lat, origin_lng, dest_lat, dest_lng), None, None

    except Exception as exc:
        logger.error(f"[TomTom Routing] Error: {exc}")
        return haversine(origin_lat, origin_lng, dest_lat, dest_lng), None, None


# =========================================================================
# BODS Real-Time Bus Fetcher
# =========================================================================
def fetch_all_buses_for_route(route):
    """
    Fetch ALL buses for a given route from BODS.
    
    Returns: List of vehicle data dicts, or empty list if no buses
    """
    route_name = route.route_name
    direction = route.direction

    if not BODS_API_KEY:
        logger.warning("[BODS] API key not set — no live bus data available")
        return []

    try:
        # Fetch vehicles for this route and filter to the configured operators locally.
        vehicles = fetch_bods_vehicles(
            api_key=BODS_API_KEY,
            line_ref=route_name,
        )
        
        if not vehicles:
            logger.warning(f"[BODS] No vehicles found for route {route_name}")
            return []
        
        logger.info(f"[BODS] Found {len(vehicles)} vehicle(s) for route {route_name}")
        logger.info(f"[BODS] Operator allowlist: {', '.join(BODS_OPERATOR_ALLOWLIST)}")

        allowed_operators = set(BODS_OPERATOR_ALLOWLIST)
        vehicles = [
            v for v in vehicles
            if resolve_vehicle_operator(v) in allowed_operators
        ]

        if not vehicles:
            logger.warning(f"[BODS] No vehicles matched operators {', '.join(BODS_OPERATOR_ALLOWLIST)}")
            return []

        vehicles = [
            v for v in vehicles
            if is_vehicle_live_for_route(v, route)
        ]

        if not vehicles:
            logger.warning(f"[BODS] No recent Bristol-route vehicles found for route {route_name}")
            return []

        # Filter by direction
        direction_lower = direction.lower()
        matching_vehicles = []
        
        for v in vehicles:
            vehicle_direction = (v.get('direction') or '').lower()
            destination = (v.get('destination') or '').lower()
            
            # Check direction match - either by direction field or destination
            if (direction_lower in vehicle_direction or 
                vehicle_direction == direction_lower or
                direction_lower in destination):
                matching_vehicles.append(v)
        
        # If no direction match, use all vehicles
        if not matching_vehicles:
            matching_vehicles = vehicles
            logger.warning(f"[BODS] No direction match for {direction}, using all {len(vehicles)} vehicles")
        
        logger.info(f"[BODS] Returning {len(matching_vehicles)} matching vehicle(s)")
        for v in matching_vehicles:
            logger.info(f"  - Vehicle {v.get('vehicle_id')}: ({v['lat']:.5f}, {v['lng']:.5f}) to {v.get('destination')}")
        
        return matching_vehicles
        
    except Exception as exc:
        logger.error(f"[BODS] Fetch error: {exc}")
        return []


# =========================================================================
# TomTom Traffic API
# =========================================================================
def fetch_traffic_delay(lat: float, lng: float):
    """
    Query TomTom Traffic Flow API for current delay at a point.
    Returns delay in seconds, or 0.0 on failure.
    """
    if not TOMTOM_API_KEY:
        return 0.0

    try:
        url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        params = {
            "point": f"{lat},{lng}",
            "unit": "KMPH",
            "key": TOMTOM_API_KEY
        }
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if "flowSegmentData" not in data:
            return 0.0
            
        flow = data["flowSegmentData"]
        free_flow_speed = flow.get("freeFlowSpeed", 0)
        current_speed = flow.get("currentSpeed", free_flow_speed)
        confidence = flow.get("confidence", 0)
        
        # Calculate delay only with reasonable confidence
        if free_flow_speed > 0 and current_speed > 0 and confidence >= 0.5:
            if current_speed < free_flow_speed:
                # Delay per km: time difference
                delay_hours = (1.0 / current_speed) - (1.0 / free_flow_speed)
                delay_seconds = max(0, delay_hours * 3600)
                
                logger.info(f"[TomTom] Speed: {current_speed:.1f}/{free_flow_speed:.1f} km/h, "
                           f"Delay: {delay_seconds:.1f}s")
                return delay_seconds
        
        return 0.0
        
    except Exception as exc:
        logger.error(f"[TomTom] Error: {exc}")
        return 0.0


# =========================================================================
# YOLOv8 Passenger Counter
# =========================================================================
_yolo_model = None
_video_capture = None
_frame_number = 0


def get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        logger.info(f"[YOLO] Loading model from {MODEL_PATH}...")
        _yolo_model = YOLO(MODEL_PATH)
        logger.info("[YOLO] Model loaded")
    return _yolo_model


def count_passengers(video_path: str) -> int:
    """
    Run YOLOv8 on one frame of the simulated camera feed.
    Video is processed frame-by-frame automatically - no manual play needed.
    """
    global _video_capture, _frame_number
    
    if not os.path.exists(video_path):
        logger.warning(f"[YOLO] Video not found: {video_path}")
        return 0

    # Initialize video capture if needed
    if _video_capture is None:
        _video_capture = cv2.VideoCapture(video_path)
        _frame_number = 0
        logger.info(f"[YOLO] Opened video: {video_path}")
    
    # Read next frame
    ret, frame = _video_capture.read()
    _frame_number += 1
    
    # Loop video when it ends
    if not ret or frame is None:
        _video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = _video_capture.read()
        _frame_number = 1
        logger.info("[YOLO] Video looped")

        # If loop also fails, video is corrupted
        if not ret or frame is None:
            logger.error("[YOLO] Video loop failed - file may be corrupted")
            return 0

    # Run YOLO detection
    model = get_yolo_model()
    results = model(frame, verbose=False)
    
    # Count persons (class 0)
    count = 0
    for r in results:
        for box in r.boxes:
            if int(box.cls[0]) == 0:
                count += 1
    
    logger.info(f"[YOLO] Frame {_frame_number}: {count} person(s)")
    return count


def cleanup_video_resources():
    """Release video capture resources on shutdown."""
    global _video_capture
    if _video_capture is not None:
        _video_capture.release()
        logger.info("[YOLO] Video resources released")
        _video_capture = None


# =========================================================================
# ETA Calculation
# =========================================================================
def calculate_eta(distance_km, traffic_delay_seconds, passenger_count, bus_speed=None):
    """
    Calculate ETA using:
    - Real bus speed from BODS if available, otherwise 18 km/h average
    - Distance to destination
    - Traffic delay from TomTom
    - Passenger boarding delay (4s per person)
    """
    # Use real bus speed if available, otherwise urban average
    avg_speed = bus_speed if bus_speed and bus_speed > 5 else 18  # km/h
    
    # Base travel time
    base_time_min = (distance_km / avg_speed) * 60
    
    # Traffic delay
    traffic_min = traffic_delay_seconds / 60
    
    # Passenger boarding delay (10 seconds per person - increased for more impact)
    crowd_min = (passenger_count * 10) / 60
    
    # Total ETA
    eta_min = base_time_min + traffic_min + crowd_min
    
    return round(eta_min, 1)


def calculate_eta_with_routing(base_time_min, passenger_count,
                               stop_delay_min=0, traffic_already_included=False,
                               typical_duration_min=None, total_stops=None, remaining_stops=None,
                               distance_km=None, current_stop_sequence=None):
    """
    Calculate ETA using TomTom routing data with bus-specific adjustments.
    Buses are slower than cars and have significant dwell times at stops.

    Args:
        base_time_min: Base travel time from TomTom (car time, includes traffic)
        passenger_count: Number of passengers boarding
        stop_delay_min: Additional delay for intermediate stops
        traffic_already_included: If True, don't add separate traffic delay
        typical_duration_min: Typical journey duration from timetable (e.g., 56 min)
        total_stops: Total number of stops on the route
        remaining_stops: Number of stops remaining to destination
        distance_km: Distance in km for bus speed factor calculation
        current_stop_sequence: Current position in route

    Returns:
        ETA in minutes
    """
    # Bus speed factor: Buses typically travel at 65-75% of car speed in urban areas
    # due to bus lanes, traffic, and slower acceleration/deceleration
    BUS_SPEED_FACTOR = 1.4  # Multiply car time by this factor
    
    # Adjust base time for bus speed (TomTom gives car time)
    adjusted_base_time = base_time_min * BUS_SPEED_FACTOR
    
    # Passenger boarding delay (15 seconds per person - more realistic)
    crowd_min = (passenger_count * 15) / 60
    
    # Stop dwell time: 1.5 minutes per stop on average
    # This accounts for boarding, alighting, and traffic light cycles
    if remaining_stops and remaining_stops > 0:
        stop_delay_min = remaining_stops * 1.5  # 1.5 min per stop
    
    # Total ETA
    eta_min = adjusted_base_time + crowd_min + stop_delay_min
    
    # If we have typical duration data, use it to sanity-check and adjust ETA
    if typical_duration_min and total_stops and remaining_stops is not None and remaining_stops > 0:
        # Calculate progress: what fraction of the journey is remaining?
        stops_completed = total_stops - remaining_stops
        progress_ratio = stops_completed / total_stops if total_stops > 0 else 0
        
        # Expected remaining time based on typical duration
        expected_remaining_min = typical_duration_min * (1 - progress_ratio)
        
        # Use timetable-based expectation heavily (80%) as it's more accurate for buses
        # Real-time data (20%) is used as adjustment
        blended_eta = (eta_min * 0.2) + (expected_remaining_min * 0.8)
        
        # Sanity check: ETA shouldn't exceed 2x typical duration or be negative
        max_eta = typical_duration_min * 1.8  # Allow 80% delay
        min_eta = expected_remaining_min * 0.7  # At least 70% of expected time
        
        final_eta = max(min_eta, min(blended_eta, max_eta))
        
        logger.info(f"[ETA] Car time: {base_time_min:.1f}min, Bus adj: {adjusted_base_time:.1f}min, "
                   f"Stops: {stop_delay_min:.1f}min ({remaining_stops} stops), "
                   f"Crowd: {crowd_min:.1f}min, Timetable: {expected_remaining_min:.1f}min, "
                   f"Final: {final_eta:.1f}min")
        
        return round(final_eta, 1)
    
    logger.info(f"[ETA] Car time: {base_time_min:.1f}min, Bus adj: {adjusted_base_time:.1f}min, "
               f"Stops: {stop_delay_min:.1f}min, Crowd: {crowd_min:.1f}min, "
               f"Total: {eta_min:.1f}min")

    return round(eta_min, 1)


def count_remaining_stops(route_id, current_lat, current_lng):
    """
    Count how many bus stops remain between current position and destination.
    Also returns the closest stop sequence.

    Returns: (remaining_stops_count, estimated_stop_delay_minutes, current_stop_seq)
    """
    from models import RouteStop
    
    # Handle None values (no live bus position)
    if current_lat is None or current_lng is None:
        return 0, 0.0, 0

    # Get all stops for this route, ordered by sequence
    route_stops = (RouteStop.query
                   .filter_by(route_id=route_id)
                   .order_by(RouteStop.sequence)
                   .all())

    if not route_stops:
        logger.info(f"[Stops] No GTFS stops loaded for route {route_id}")
        return 0, 0.0, 0

    current_stop_seq, _, _ = get_current_stop_context(route_stops, current_lat, current_lng)

    # Count stops after current position
    remaining = sum(1 for rs in route_stops if rs.sequence > current_stop_seq)

    # Estimate delay: 1.5 minutes per stop (accounts for dwell time, traffic lights, boarding)
    stop_delay_min = remaining * 1.5

    logger.info(f"[Stops] At sequence {current_stop_seq}, "
               f"{remaining} stops remaining, "
               f"+{stop_delay_min:.1f}min delay")

    return remaining, stop_delay_min, current_stop_seq


def get_current_service_time(route_id, current_lat, current_lng, current_time=None):
    """
    Determine which scheduled service the bus is currently running.
    Based on current position and time, find the closest scheduled departure.
    
    Returns: (service_time_str, delay_minutes, current_stop_scheduled_time)
    """
    from models import RouteStop
    
    if current_time is None:
        current_time = datetime.now(UK_TZ)

    local_time = to_uk_datetime(current_time)
    route = Route.query.get(route_id)
    
    # Get all stops for this route
    route_stops = (RouteStop.query
                   .filter_by(route_id=route_id)
                   .order_by(RouteStop.sequence)
                   .all())
    
    if not route_stops or not route_stops[0].scheduled_arrival:
        return None, 0, None
    
    current_stop_seq, current_stop, _ = get_current_stop_context(route_stops, current_lat, current_lng)
    current_stop_scheduled = current_stop.scheduled_arrival if current_stop else None

    if route:
        selected_trip = get_gtfs_schedule_trip(
            route,
            current_time=local_time,
            current_stop_seq=current_stop_seq,
            mode="live",
        )
        if selected_trip:
            service_time_str = format_gtfs_time(selected_trip.get("service_time"))
            trip_stops = selected_trip.get("stops", [])
            if 0 <= current_stop_seq < len(trip_stops):
                current_stop_scheduled = trip_stops[current_stop_seq]["arrival_time"]
                scheduled_dt = build_gtfs_datetime(
                    selected_trip["service_date"],
                    current_stop_scheduled,
                )
                if scheduled_dt is not None:
                    scheduled_dt = scheduled_dt.replace(tzinfo=UK_TZ)
                    delay_min = max(0.0, (local_time - scheduled_dt).total_seconds() / 60.0)
                    return service_time_str, round(delay_min, 1), current_stop_scheduled
            return service_time_str, 0, current_stop_scheduled

    first_stop_time = route_stops[0].scheduled_arrival
    if not first_stop_time:
        return None, 0, None

    parsed_first = parse_gtfs_time(first_stop_time)
    if not parsed_first:
        return None, 0, None
    sched_hour, sched_min, _ = parsed_first
    service_time_str = f"{sched_hour:02d}:{sched_min:02d}"

    if current_stop_scheduled:
        try:
            scheduled_dt = build_scheduled_datetime(local_time, current_stop_scheduled)
            if scheduled_dt is None:
                return service_time_str, 0, current_stop_scheduled

            delay_min = max(0.0, (local_time - scheduled_dt).total_seconds() / 60.0)
            return service_time_str, round(delay_min, 1), current_stop_scheduled
        except Exception:
            pass

    return service_time_str, 0, current_stop_scheduled


def calculate_stop_predictions(route_id, current_lat, current_lng, current_eta_min, current_time=None):
    """
    Calculate predicted arrival times and delays for all remaining stops.
    
    Returns list of dicts with stop info, scheduled time, predicted time, and delay.
    """
    from models import Route, RouteStop
    
    # Handle None values (no live bus position)
    if current_lat is None or current_lng is None or current_eta_min is None:
        return []
    
    if current_time is None:
        current_time = datetime.now(UK_TZ)

    local_time = to_uk_datetime(current_time)
    
    # Get all stops for this route
    route_stops = (RouteStop.query
                   .filter_by(route_id=route_id)
                   .order_by(RouteStop.sequence)
                   .all())
    
    if not route_stops:
        return []

    current_stop_seq, current_stop, _ = get_current_stop_context(route_stops, current_lat, current_lng)
    route = Route.query.get(route_id)
    route_delay_min = calculate_route_delay(route, current_stop_seq, current_eta_min)
    selected_trip = None
    schedule_by_sequence = {}
    if route:
        selected_trip = get_gtfs_schedule_trip(
            route,
            current_time=local_time,
            current_stop_seq=current_stop_seq,
            mode="live",
        )
        if selected_trip:
            schedule_by_sequence = {
                stop["sequence"]: stop["arrival_time"]
                for stop in selected_trip["stops"]
            }

    # Use the matched GTFS trip as the delay baseline when available.
    _, current_delay_min, _ = get_current_service_time(
        route_id, current_lat, current_lng, local_time
    )
    applied_delay_min = current_delay_min if current_delay_min is not None else route_delay_min
    
    predictions = []
    
    # Calculate remaining stops
    remaining_stops = [rs for rs in route_stops if rs.sequence >= current_stop_seq]

    if not remaining_stops:
        return predictions

    for rs in remaining_stops:
        scheduled = schedule_by_sequence.get(rs.sequence, rs.scheduled_arrival)
        predicted_time = local_time + timedelta(minutes=current_eta_min)
        predicted_time_str = predicted_time.strftime("%H:%M")

        # Calculate delay at this stop
        delay_min = int(round(applied_delay_min))
        delay_text = "No schedule"

        if scheduled:
            try:
                if selected_trip:
                    sched_datetime = build_gtfs_datetime(selected_trip["service_date"], scheduled)
                    if sched_datetime is not None:
                        sched_datetime = sched_datetime.replace(tzinfo=UK_TZ)
                else:
                    sched_datetime = build_scheduled_datetime(local_time, scheduled)
                if sched_datetime is not None:
                    predicted_time = sched_datetime + timedelta(minutes=applied_delay_min)
                    predicted_time_str = predicted_time.strftime("%H:%M")
                else:
                    predicted_time = local_time + timedelta(minutes=current_eta_min)
                    predicted_time_str = predicted_time.strftime("%H:%M")

                if delay_min <= 0:
                    delay_text = "On time"
                elif delay_min == 1:
                    delay_text = "Delayed 1 min"
                else:
                    delay_text = f"Delayed {delay_min} min"
            except Exception:
                pass
        else:
            predicted_time = local_time + timedelta(minutes=current_eta_min)
            predicted_time_str = predicted_time.strftime("%H:%M")

        # Determine status
        if rs.sequence < current_stop_seq:
            status = "departed"
        elif rs.sequence == current_stop_seq:
            status = "current"
        else:
            status = "upcoming"
        
        predictions.append({
            "stop_sequence": rs.sequence,
            "stop_name": rs.stop.stop_name,
            "stop_id": rs.stop.stop_id,
            "lat": rs.stop.lat,
            "lng": rs.stop.lng,
            "scheduled_arrival": format_gtfs_time(scheduled),
            "predicted_arrival": predicted_time_str,
            "delay_minutes": delay_min,
            "delay_text": delay_text,
            "status": status,
        })
    
    return predictions


# =========================================================================
# Fusion Engine — Background Worker
# =========================================================================
def fusion_engine():
    """
    Core loop that fuses GPS, traffic, and crowd data for ALL buses on every route.
    Runs in a daemon thread.
    """
    with app.app_context():
        # Wait a moment for app to fully start
        time.sleep(2)
        
        while True:
            try:
                routes = Route.query.all()
                if not routes:
                    logger.info("[Fusion] No routes configured")
                    time.sleep(FUSION_INTERVAL)
                    continue

                for route in routes:
                    logger.info(f"\n[Fusion] === Route {route.route_name} ({route.direction}) ===")

                    # Step 1 — Fetch ALL buses for this route
                    vehicles = fetch_all_buses_for_route(route)
                    
                    if not vehicles:
                        logger.warning(f"[Fusion] No live buses available for route {route.route_name}")
                        # Store a log entry indicating no bus is available
                        log = BusLog(
                            route_id=route.id,
                            vehicle_id=None,
                            bus_lat=None,
                            bus_lng=None,
                            passenger_count=0,
                            traffic_delay=0,
                            predicted_eta=None,
                            scheduled_service_time=None,
                            delay_minutes=None,
                        )
                        db.session.add(log)
                        db.session.commit()
                        continue
                    
                    logger.info(f"[Fusion] Processing {len(vehicles)} bus(es) for route {route.route_name}")
                    
                    # Process EACH bus individually
                    for vehicle_data in vehicles:
                        vehicle_id = vehicle_data.get('vehicle_id', 'unknown')
                        operator = resolve_vehicle_operator(vehicle_data)
                        bus_lat = vehicle_data['lat']
                        bus_lng = vehicle_data['lng']

                        _latest_bus_metadata[vehicle_id] = {
                            "operator": operator,
                            "route_id": route.id,
                            "timestamp": datetime.now(),
                        }
                        
                        logger.info(f"\n[Fusion] -- Processing Bus {vehicle_id} --")
                        logger.info(f"  Position: ({bus_lat:.5f}, {bus_lng:.5f})")
                        logger.info(f"  Destination: {vehicle_data.get('destination')}")
                        logger.info(f"  Operator: {operator}")

                        # Step 2 — Traffic from TomTom
                        traffic_delay = fetch_traffic_delay(bus_lat, bus_lng)

                        # Step 3 — Crowd from YOLO (ONLY at major stops)
                        is_near_major, nearest_stop_name, distance_to_stop = is_near_major_stop(
                            bus_lat, bus_lng, route.direction
                        )
                        
                        if is_near_major:
                            # Run YOLO only when near major stops
                            raw_count = count_passengers(VIDEO_PATH)
                            # Smooth the count to prevent fluctuation
                            passenger_count = get_smoothed_crowd_count(vehicle_id, raw_count)
                            logger.info(f"[Crowd] Bus {vehicle_id} near {nearest_stop_name} "
                                       f"({distance_to_stop:.2f}km) - Raw: {raw_count}, Smoothed: {passenger_count} passengers")
                        else:
                            # Use 0 crowd when not at major stops
                            # Reset history when leaving major stop area
                            if vehicle_id in _crowd_history:
                                del _crowd_history[vehicle_id]
                            passenger_count = 0
                            logger.info(f"[Crowd] Bus {vehicle_id} not near major stop "
                                       f"(closest: {nearest_stop_name} at {distance_to_stop:.2f}km) - Assuming 0 passengers")

                        # Step 4 — Get Route Distance from TomTom
                        distance_km, travel_time_sec, route_summary = get_route_distance_tomtom(
                            bus_lat, bus_lng,
                            route.dest_lat, route.dest_lng
                        )

                        traffic_delay = route_summary.get('traffic_delay_sec', 0) if route_summary else 0

                        # Step 5 — Count remaining bus stops
                        remaining_stops, stop_delay_min, current_stop_seq = count_remaining_stops(
                            route.id, bus_lat, bus_lng
                        )
                        
                        # Step 5b — Determine current service label
                        service_time, schedule_delay_min, _ = get_current_service_time(
                            route.id, bus_lat, bus_lng
                        )

                        # Step 6 — Calculate ETA with all factors
                        traffic_delay_seconds = traffic_delay or 0
                        eta = predict_eta_xgboost(
                            route=route,
                            passenger_count=passenger_count,
                            traffic_delay_seconds=traffic_delay_seconds,
                            current_stop_seq=current_stop_seq,
                            remaining_stops=remaining_stops,
                            current_time=datetime.now(),
                        )

                        if eta is None:
                            if travel_time_sec:
                                base_time_min = travel_time_sec / 60.0
                                eta = calculate_eta_with_routing(
                                    base_time_min, passenger_count,
                                    stop_delay_min=stop_delay_min,
                                    traffic_already_included=True,
                                    typical_duration_min=route.typical_duration_min,
                                    total_stops=route.total_stops,
                                    remaining_stops=remaining_stops,
                                    distance_km=distance_km,
                                    current_stop_sequence=current_stop_seq
                                )
                            else:
                                logger.warning(f"[Fusion] TomTom routing failed for bus {vehicle_id}")
                                eta = calculate_eta(
                                    haversine(bus_lat, bus_lng, route.dest_lat, route.dest_lng),
                                    traffic_delay_seconds,
                                    passenger_count,
                                )

                        delay_minutes = schedule_delay_min
                        if delay_minutes is None:
                            delay_minutes = calculate_route_delay(route, current_stop_seq, eta)

                        # Step 7 — Persist to database
                        log = BusLog(
                            route_id=route.id,
                            vehicle_id=vehicle_id,
                            bus_lat=bus_lat,
                            bus_lng=bus_lng,
                            passenger_count=passenger_count,
                            traffic_delay=traffic_delay,
                            predicted_eta=eta,
                            scheduled_service_time=service_time,
                            delay_minutes=delay_minutes,
                        )
                        db.session.add(log)
                        db.session.commit()

                        delay_str = f"{delay_minutes:.0f}min late" if delay_minutes and delay_minutes > 0 else "on time"
                        logger.info(f"[Fusion] Bus {vehicle_id}: ETA={eta}min | {delay_str}")
                    logger.info(
                        f"[Fusion] Result: ETA={eta}min | Dist={distance_km:.2f}km | "
                        f"Crowd={passenger_count} | Traffic={traffic_delay:.0f}s | "
                        f"Service={service_time} | {delay_str}"
                    )

            except Exception as exc:
                logger.error(f"[Fusion] Engine error: {exc}")
                db.session.rollback()

            time.sleep(FUSION_INTERVAL)


# =========================================================================
# API Endpoints
# =========================================================================
@app.route("/", methods=["GET"])
def root():
    """Simple health/info endpoint for direct browser access."""
    return jsonify({
        "service": "Transight backend",
        "status": "ok",
        "message": "Backend is running. Use the /api/* endpoints for data.",
        "endpoints": [
            "/api/routes",
            "/api/routes/<route_id>/stops",
            "/api/routes/<route_id>/predictions",
            "/api/status/<route_id>",
        ],
    })


@app.route("/api/routes", methods=["GET"])
def get_routes():
    """Return all configured routes."""
    routes = Route.query.all()
    return jsonify([r.to_dict() for r in routes])


@app.route("/api/routes/<int:route_id>/stops", methods=["GET"])
def get_route_stops(route_id):
    """Return all stops for a specific route in order."""
    from models import RouteStop
    
    route = Route.query.get(route_id)
    if not route:
        return jsonify({"error": "Route not found"}), 404
    
    route_stops = (RouteStop.query
                   .filter_by(route_id=route_id)
                   .order_by(RouteStop.sequence)
                   .all())
    
    return jsonify({
        "route": route.to_dict(),
        "stops": [rs.to_dict() for rs in route_stops]
    })


@app.route("/api/routes/<int:route_id>/predictions", methods=["GET"])
def get_route_predictions(route_id):
    """
    Return stop-by-stop predictions with scheduled times and delays.
    Similar to the transit app showing 'Delayed X min' at each stop.
    """
    route = Route.query.get(route_id)
    if not route:
        return jsonify({"error": "Route not found"}), 404
    
    # Get latest status
    log = (
        BusLog.query
        .filter_by(route_id=route_id)
        .order_by(BusLog.timestamp.desc())
        .first()
    )

    if (
        not log
        or log.bus_lat is None
        or log.bus_lng is None
        or not is_recent_live_timestamp(log.timestamp)
    ):
        return jsonify(build_schedule_only_response(route_id, route, current_time=datetime.now(UK_TZ)))
    
    # Calculate stop-by-step predictions
    current_eta = log.predicted_eta
    remaining_stops, _, current_stop_seq = count_remaining_stops(route_id, log.bus_lat, log.bus_lng)
    if current_eta is None and log.bus_lat is not None and log.bus_lng is not None:
        current_eta = predict_eta_xgboost(
            route=route,
            passenger_count=log.passenger_count or 0,
            traffic_delay_seconds=log.traffic_delay or 0,
            current_stop_seq=current_stop_seq,
            remaining_stops=remaining_stops,
            current_time=log.timestamp or datetime.now(),
        )
        if current_eta is None:
            current_eta = calculate_eta(
                haversine(log.bus_lat, log.bus_lng, route.dest_lat, route.dest_lng),
                log.traffic_delay or 0,
                log.passenger_count or 0,
            )

    stop_predictions = calculate_stop_predictions(
        route_id, log.bus_lat, log.bus_lng, current_eta, log.timestamp
    )

    service_time = log.scheduled_service_time
    current_delay = log.delay_minutes
    if log.bus_lat is not None and log.bus_lng is not None:
        service_time_live, current_delay_live, _ = get_current_service_time(
            route_id,
            log.bus_lat,
            log.bus_lng,
            log.timestamp or datetime.now(UK_TZ),
        )
        if service_time_live:
            service_time = service_time_live
        if current_delay_live is not None:
            current_delay = current_delay_live

    if current_delay is None:
        current_delay = calculate_route_delay(route, current_stop_seq, current_eta)
    
    return jsonify({
        "route": route.to_dict(),
        "service_time": service_time,
        "current_delay": current_delay,
        "bus_available": True,
        "is_live": True,
        "bus_position": {
            "lat": log.bus_lat,
            "lng": log.bus_lng,
            "last_updated": log.timestamp.isoformat() if log.timestamp else None
        },
        "stops": stop_predictions
    })


@app.route("/api/status/<int:route_id>", methods=["GET"])
def get_status(route_id):
    """Return ALL buses for the route with their positions and ETAs."""
    route = Route.query.get(route_id)
    if not route:
        return jsonify({"error": "Route not found"}), 404
    
    # Get the most recent timestamp for this route
    latest_log = (
        BusLog.query
        .filter_by(route_id=route_id)
        .order_by(BusLog.timestamp.desc())
        .first()
    )
    
    if latest_log is None:
        return jsonify({"error": "No data yet for this route"}), 404

    if not is_recent_live_timestamp(latest_log.timestamp):
        return jsonify({
            "route": route.to_dict(),
            "bus_available": False,
            "is_live": False,
            "message": "No live bus currently available on this route",
            "buses": [],
            "timestamp": latest_log.timestamp.isoformat() if latest_log.timestamp else None,
        }), 200

    recent_cutoff = datetime.now(latest_log.timestamp.tzinfo) - timedelta(minutes=2)
    
    recent_logs = (
        BusLog.query
        .filter_by(route_id=route_id)
        .filter(BusLog.timestamp >= recent_cutoff)
        .filter(BusLog.bus_lat.isnot(None))
        .filter(BusLog.bus_lng.isnot(None))
        .order_by(BusLog.timestamp.desc())
        .all()
    )
    
    # Group by vehicle_id to get unique buses
    buses = {}
    for log in recent_logs:
        vid = log.vehicle_id or 'unknown'
        if vid not in buses:
            buses[vid] = log
    
    # Build bus list
    bus_list = []
    for vehicle_id, log in buses.items():
        # Calculate remaining stops
        remaining_stops, _, current_stop_seq = count_remaining_stops(route_id, log.bus_lat, log.bus_lng)
        delay_minutes = log.delay_minutes
        if delay_minutes is None:
            delay_minutes = calculate_route_delay(route, current_stop_seq, log.predicted_eta)
        
        # Calculate predictions
        stop_predictions = calculate_stop_predictions(
            route_id, log.bus_lat, log.bus_lng, log.predicted_eta, log.timestamp
        )

        operator = _latest_bus_metadata.get(vehicle_id, {}).get("operator")
        if not operator and vehicle_id and "-" in vehicle_id:
            operator = vehicle_id.split("-", 1)[0]

        bus_list.append({
            "vehicle_id": vehicle_id,
            "operator": operator or "unknown",
            "position": {
                "lat": log.bus_lat,
                "lng": log.bus_lng,
            },
            "eta": log.predicted_eta,
            "passenger_count": log.passenger_count,
            "traffic_delay": log.traffic_delay,
            "scheduled_service_time": log.scheduled_service_time,
            "delay_minutes": delay_minutes,
            "remaining_stops": remaining_stops,
            "current_stop_sequence": current_stop_seq,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "stop_predictions": stop_predictions,
        })

    bus_list.sort(key=lambda bus: (
        bus["eta"] is None,
        bus["eta"] if bus["eta"] is not None else float("inf"),
        bus.get("vehicle_id") or "",
    ))
    
    if not bus_list:
        return jsonify({
            "route": route.to_dict(),
            "bus_available": False,
            "is_live": False,
            "message": "No bus currently available on this route",
            "buses": [],
            "timestamp": latest_log.timestamp.isoformat() if latest_log.timestamp else None,
        }), 200

    return jsonify({
        "route": route.to_dict(),
        "bus_available": True,
        "is_live": True,
        "bus_count": len(bus_list),
        "buses": bus_list,
        "timestamp": latest_log.timestamp.isoformat() if latest_log.timestamp else None,
    })


# =========================================================================
# Entry Point
# =========================================================================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        logger.info("[Startup] Database ready")
        load_eta_model()
        if os.path.exists(GTFS_ZIP_PATH):
            logger.info(f"[Startup] Warming GTFS cache from {GTFS_ZIP_PATH}")
            get_cached_gtfs_data(GTFS_ZIP_PATH)
            logger.info("[Startup] GTFS cache ready")

    # Register cleanup handlers
    atexit.register(cleanup_video_resources)

    def signal_handler(signum, frame):
        logger.info(f"[Shutdown] Received signal {signum}")
        cleanup_video_resources()
        exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start Fusion Engine
    worker = threading.Thread(target=fusion_engine, daemon=True)
    worker.start()
    logger.info("[Startup] Fusion Engine started")

    app.run(host="0.0.0.0", port=5000, debug=False)
