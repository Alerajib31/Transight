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
import re
import threading
import logging
import atexit
import signal
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import requests
import cv2
import joblib
from ultralytics import YOLO
from flask import Flask, jsonify, request
from flask_cors import CORS

from env_utils import DEFAULT_DATABASE_URL, load_project_env_files, resolve_project_path
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
load_project_env_files()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    DEFAULT_DATABASE_URL,
)
BODS_API_KEY = os.getenv("BODS_API_KEY")
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")  # Traffic Flow API
TOMTOM_ROUTING_KEY = os.getenv("TOMTOM_ROUTING_KEY")  # Routing API
VIDEO_PATH = resolve_project_path(os.getenv("VIDEO_PATH"), "bus_queue.mp4")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "yolov8n.pt")
ETA_MODEL_PATH = os.path.join(os.path.dirname(__file__), "xgboost_eta_model.joblib")
GTFS_ZIP_PATH = os.path.join(os.path.dirname(__file__), "..", "itm_south_west_gtfs.zip")
FUSION_INTERVAL = int(os.getenv("FUSION_INTERVAL", "10"))  # seconds
LIVE_DATA_MAX_AGE_SECONDS = int(os.getenv("LIVE_DATA_MAX_AGE_SECONDS", "180"))
STATUS_BODS_CACHE_SECONDS = int(os.getenv("STATUS_BODS_CACHE_SECONDS", "15"))
STATUS_LOG_FALLBACK_GRACE_SECONDS = int(os.getenv("STATUS_LOG_FALLBACK_GRACE_SECONDS", "120"))
ROUTE_PROXIMITY_THRESHOLD_KM = float(os.getenv("ROUTE_PROXIMITY_THRESHOLD_KM", "2.0"))
LIVE_TRIP_MAX_EARLY_MINUTES = float(os.getenv("LIVE_TRIP_MAX_EARLY_MINUTES", "5"))
LIVE_TRIP_MAX_LATE_MINUTES = float(os.getenv("LIVE_TRIP_MAX_LATE_MINUTES", "25"))
ORIGIN_STAGING_RADIUS_KM = float(os.getenv("ORIGIN_STAGING_RADIUS_KM", "0.15"))
TERMINAL_ARRIVAL_RADIUS_KM = float(os.getenv("TERMINAL_ARRIVAL_RADIUS_KM", "0.15"))
ORIGIN_EARLY_DISPLAY_MINUTES = float(os.getenv("ORIGIN_EARLY_DISPLAY_MINUTES", "4"))
UK_TZ = ZoneInfo("Europe/London")

_operator_allowlist = [op.strip() for op in os.getenv("BODS_OPERATOR_ALLOWLIST", "FBRI,FBRA").split(",") if op.strip()]
BODS_OPERATOR_ALLOWLIST = tuple(dict.fromkeys(_operator_allowlist)) if _operator_allowlist else ("FBRI", "FBRA")

# Bristol operator code (First Bristol = FBRI)
BODS_OPERATOR = BODS_OPERATOR_ALLOWLIST[0]

ROUTE_DIRECTION_TERMINAL_ALIASES = {
    "a1": {
        "outbound": (
            "bristol airport",
            "public transport interchange",
        ),
        "inbound": (
            "bristol bus station",
            "bus station",
            "marlborough",
            "city centre",
        ),
    },
    "72": {
        "outbound": (
            "frenchay",
            "frenchay campus",
            "uwe frenchay",
        ),
        "inbound": (
            "temple meads",
            "temple meads stn",
            "temple meads station",
        ),
    },
}
GENERIC_DIRECTION_ALIASES = {
    "outbound": ("outbound",),
    "inbound": ("inbound",),
}

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

A1_MAJOR_STOPS_OUTBOUND = [
    ("Bus Station", 51.45909, -2.59294),
    ("The Centre", 51.45381, -2.59696),
    ("Queen Square", 51.45051, -2.59646),
    ("Temple Meads Stn", 51.44898, -2.58262),
    ("Bedminster Parade", 51.44431, -2.59315),
    ("Airport Tavern", 51.38727, -2.70061),
    ("Public Transport Interchange", 51.38743, -2.70987),
]

A1_MAJOR_STOPS_INBOUND = [
    ("Public Transport Interchange", 51.38743, -2.70987),
    ("Airport Tavern", 51.38838, -2.70006),
    ("Winford Arms", 51.41049, -2.64689),
    ("Temple Meads Stn", 51.44902, -2.58579),
    ("Queen Square", 51.45116, -2.59652),
    ("The Centre", 51.45409, -2.59694),
    ("Bus Station", 51.45909, -2.59294),
]

FALLBACK_MAJOR_STOPS_BY_ROUTE = {
    "72": {
        "outbound": MAJOR_STOPS_OUTBOUND,
        "inbound": MAJOR_STOPS_INBOUND,
    },
    "A1": {
        "outbound": A1_MAJOR_STOPS_OUTBOUND,
        "inbound": A1_MAJOR_STOPS_INBOUND,
    },
}

# Distance threshold to consider bus "at" a major stop (in km)
CROWD_DETECTION_RADIUS_KM = 0.3  # 300 meters

# Store recent crowd counts for smoothing (prevents fluctuation)
_crowd_history = {}
MAX_CROWD_HISTORY = 3  # Average last 3 readings

# Fraction of frame width (measured from the LEFT edge) that counts as the
# passenger waiting area. OFF BY DEFAULT (1.0 = no-op, whole frame width
# included): bus-aware exclusion (BUS_CONTAINMENT_MIN / BUS_INTERIOR_Y_FRACTION
# below) is the active mechanism for separating waiting passengers from
# people inside the bus. This fraction remains available as an optional
# manual tightening knob via the CROWD_ROI_X_FRACTION env var.
try:
    CROWD_ROI_X_FRACTION = float(os.getenv("CROWD_ROI_X_FRACTION", "1.0"))
except ValueError:
    CROWD_ROI_X_FRACTION = 1.0
CROWD_ROI_X_FRACTION = min(max(CROWD_ROI_X_FRACTION, 0.05), 1.0)  # clamp to (0.05, 1.0]

# Fraction of frame HEIGHT (measured from the TOP edge) that marks the
# ground line. OFF BY DEFAULT (0.0 = no-op, every detection passes the
# ground-line check): bus-aware exclusion (BUS_CONTAINMENT_MIN /
# BUS_INTERIOR_Y_FRACTION below) is the active mechanism for excluding
# people visible through the bus windows. This fraction remains available
# as an optional manual tightening knob via the CROWD_ROI_Y_MIN_FRACTION
# env var.
try:
    CROWD_ROI_Y_MIN_FRACTION = float(os.getenv("CROWD_ROI_Y_MIN_FRACTION", "0.0"))
except ValueError:
    CROWD_ROI_Y_MIN_FRACTION = 0.0
CROWD_ROI_Y_MIN_FRACTION = min(max(CROWD_ROI_Y_MIN_FRACTION, 0.0), 0.95)  # clamp to [0.0, 0.95]

# Fraction of a PERSON box area that must fall inside a detected bus box
# (class 5) for that person to be considered "inside the bus". Override via
# the BUS_CONTAINMENT_MIN env var.
try:
    BUS_CONTAINMENT_MIN = float(os.getenv("BUS_CONTAINMENT_MIN", "0.85"))
except ValueError:
    BUS_CONTAINMENT_MIN = 0.85
BUS_CONTAINMENT_MIN = min(max(BUS_CONTAINMENT_MIN, 0.0), 1.0)  # clamp to [0.0, 1.0]

# Fraction of bus box HEIGHT (measured from the TOP edge, bus_y1) that marks
# the bus interior line: interior_line = bus_y1 + fraction * bus_height. A
# contained person whose box bottom (y2) is ABOVE this line is behind the
# glass and excluded; a contained person whose box bottom is at/below this
# line is at the door/pavement and still counted. Override via the
# BUS_INTERIOR_Y_FRACTION env var.
try:
    BUS_INTERIOR_Y_FRACTION = float(os.getenv("BUS_INTERIOR_Y_FRACTION", "0.7"))
except ValueError:
    BUS_INTERIOR_Y_FRACTION = 0.7
BUS_INTERIOR_Y_FRACTION = min(max(BUS_INTERIOR_Y_FRACTION, 0.0), 1.0)  # clamp to [0.0, 1.0]

_latest_bus_metadata = {}
_eta_models: dict[str, object] = {}
_tomtom_service_state = {
    "traffic": {
        "disabled": False,
        "auth_logged": False,
    },
    "routing": {
        "disabled": False,
        "auth_logged": False,
    },
}


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
    hour %= 24
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
    if distance_km > ROUTE_PROXIMITY_THRESHOLD_KM:
        return False

    return is_position_plausible_for_timetable(
        route,
        vehicle_data["lat"],
        vehicle_data["lng"],
        recorded_at,
    )


def is_position_plausible_for_timetable(route, current_lat, current_lng, current_time):
    """Check whether a live position plausibly matches an in-service GTFS trip."""
    if route is None or current_lat is None or current_lng is None:
        return True

    route_stops = sorted(route.route_stops, key=lambda rs: rs.sequence)
    if not route_stops:
        return True

    local_time = to_uk_datetime(current_time)
    current_stop_seq, _, _ = get_current_stop_context(route_stops, current_lat, current_lng)
    selected_trip = get_gtfs_schedule_trip(
        route,
        current_time=local_time,
        current_stop_seq=current_stop_seq,
        mode="live",
    )
    if not selected_trip:
        return True

    trip_stops = selected_trip.get("stops", [])
    if current_stop_seq < 0 or current_stop_seq >= len(trip_stops):
        return True

    first_stop = trip_stops[0] if trip_stops else None
    if first_stop and current_stop_seq == first_stop["sequence"]:
        first_departure_dt = build_gtfs_datetime(
            selected_trip["service_date"],
            first_stop.get("departure_time") or first_stop["arrival_time"],
        )
        if first_departure_dt is not None:
            first_departure_dt = first_departure_dt.replace(tzinfo=UK_TZ)
            display_window_dt = first_departure_dt - timedelta(
                minutes=ORIGIN_EARLY_DISPLAY_MINUTES
            )
            origin_distance_km = haversine(
                current_lat,
                current_lng,
                first_stop["lat"],
                first_stop["lng"],
            )
            if (
                origin_distance_km <= ORIGIN_STAGING_RADIUS_KM
                and local_time < display_window_dt
            ):
                logger.warning(
                    f"[GTFS] Rejecting origin-staging bus for route {route.route_name} "
                    f"({route.direction}) before display window: "
                    f"{origin_distance_km:.2f}km from first stop, "
                    f"display from {display_window_dt.isoformat()}, "
                    f"departure at {first_departure_dt.isoformat()}"
                )
                return False

    scheduled_dt = build_gtfs_datetime(
        selected_trip["service_date"],
        trip_stops[current_stop_seq]["arrival_time"],
    )
    if scheduled_dt is None:
        return True

    scheduled_dt = scheduled_dt.replace(tzinfo=UK_TZ)
    delta_minutes = (local_time - scheduled_dt).total_seconds() / 60.0
    if delta_minutes < -LIVE_TRIP_MAX_EARLY_MINUTES or delta_minutes > LIVE_TRIP_MAX_LATE_MINUTES:
        logger.warning(
            f"[GTFS] Rejecting implausible live bus for route {route.route_name} "
            f"({route.direction}) at stop seq {current_stop_seq}: "
            f"schedule delta {delta_minutes:.1f} min"
        )
        return False

    return True


def resolve_vehicle_operator(vehicle_data):
    """Resolve a vehicle's operator from BODS data or the vehicle ID prefix."""
    operator = (vehicle_data.get("operator") or "").strip()
    if operator:
        return operator

    vehicle_id = (vehicle_data.get("vehicle_id") or "").strip()
    if "-" in vehicle_id:
        return vehicle_id.split("-", 1)[0].strip() or "unknown"

    return "unknown"


def normalize_bods_text(value):
    """Normalize BODS free-text fields for resilient alias matching."""
    if not value:
        return ""

    normalized = re.sub(r"[^a-z0-9]+", " ", str(value).lower())
    return re.sub(r"\s+", " ", normalized).strip()


def find_matching_alias(text, aliases):
    """Return the first alias that appears in text after normalization."""
    normalized_text = normalize_bods_text(text)
    for alias in sorted({normalize_bods_text(alias) for alias in aliases if alias}, key=len, reverse=True):
        if alias and alias in normalized_text:
            return alias
    return None


def get_route_terminal_aliases(route):
    """Return selected and opposite terminal aliases for a route direction."""
    route_name = (getattr(route, "route_name", "") or "").strip().lower()
    direction = (getattr(route, "direction", "") or "").strip().lower()
    opposite_direction = "inbound" if direction == "outbound" else "outbound"
    alias_config = ROUTE_DIRECTION_TERMINAL_ALIASES.get(route_name, {})

    selected_aliases = set(alias_config.get(direction, ()))
    opposite_aliases = set(alias_config.get(opposite_direction, ()))

    if getattr(route, "destination_name", None):
        selected_aliases.add(route.destination_name)
    if getattr(route, "origin_name", None):
        opposite_aliases.add(route.origin_name)

    return selected_aliases, opposite_aliases


def confirm_vehicle_direction(route, vehicle_data):
    """Return whether a vehicle is positively confirmed for the route direction."""
    route_direction = (getattr(route, "direction", "") or "").strip().lower()
    opposite_direction = "inbound" if route_direction == "outbound" else "outbound"
    destination_text = vehicle_data.get("destination")
    direction_text = vehicle_data.get("direction")
    selected_aliases, opposite_aliases = get_route_terminal_aliases(route)

    destination_match = find_matching_alias(destination_text, selected_aliases)
    if destination_match:
        return True, "destination_match", destination_match

    destination_conflict = find_matching_alias(destination_text, opposite_aliases)
    if destination_conflict:
        return False, "direction_conflict", destination_conflict

    direction_aliases = GENERIC_DIRECTION_ALIASES.get(route_direction, ())
    direction_match = find_matching_alias(direction_text, direction_aliases)
    if direction_match:
        return True, "direction_match", direction_match

    opposite_direction_aliases = GENERIC_DIRECTION_ALIASES.get(opposite_direction, ())
    direction_conflict = find_matching_alias(direction_text, opposite_direction_aliases)
    if direction_conflict:
        return False, "direction_conflict", direction_conflict

    return False, "direction_ambiguous", None


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


def get_eta_model_path(route_name: str) -> str:
    """Return the expected model path for a route, with Route 72 legacy fallback."""
    normalized = (route_name or "").strip().lower()
    route_model_path = os.path.join(
        os.path.dirname(__file__),
        f"xgboost_eta_model_{normalized}.joblib",
    )
    if os.path.exists(route_model_path):
        return route_model_path

    if normalized == "72":
        return ETA_MODEL_PATH

    return route_model_path


def load_eta_model(route_name: str):
    """Load the trained XGBoost ETA model for a route once per process."""
    cache_key = (route_name or "").strip().lower()
    if cache_key in _eta_models:
        return _eta_models[cache_key]

    model_path = get_eta_model_path(cache_key)
    if not os.path.exists(model_path):
        logger.warning(
            f"[XGBoost] Model not found for route {route_name} at {model_path}; "
            "using formula fallback"
        )
        _eta_models[cache_key] = False
        return None

    try:
        model = joblib.load(model_path)
        logger.info(f"[XGBoost] Loaded ETA model for route {route_name} from {model_path}")
        _eta_models[cache_key] = model
        return model
    except Exception as exc:
        logger.error(f"[XGBoost] Failed to load ETA model for route {route_name}: {exc}")
        _eta_models[cache_key] = False
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
    route_name = getattr(route, "route_name", "unknown")
    model = load_eta_model(route_name)
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
        logger.info(f"[XGBoost] Using model prediction for route {route_name}: {float(prediction):.1f} min")
        return round(float(prediction), 1)
    except Exception as exc:
        logger.error(f"[XGBoost] Prediction failed for route {route_name}: {exc}")
        return None


def find_trip_stop_by_sequence(trip_stops, stop_sequence):
    """Return the GTFS trip stop matching a route stop sequence."""
    if trip_stops is None or stop_sequence is None:
        return None

    return next(
        (stop for stop in trip_stops if stop.get("sequence") == stop_sequence),
        None,
    )


def estimate_schedule_eta_from_position(route, current_lat, current_lng, current_time=None, current_stop_seq=None):
    """Estimate remaining ETA from the matched GTFS trip and current lateness."""
    if route is None or current_lat is None or current_lng is None:
        return None

    route_stops = sorted(route.route_stops, key=lambda rs: rs.sequence)
    if not route_stops:
        return None

    local_time = to_uk_datetime(current_time)
    if current_stop_seq is None:
        current_stop_seq, _, _ = get_current_stop_context(route_stops, current_lat, current_lng)

    selected_trip = get_gtfs_schedule_trip(
        route,
        current_time=local_time,
        current_stop_seq=current_stop_seq,
        mode="live",
    )
    if not selected_trip:
        return None

    trip_stops = selected_trip.get("stops", [])
    if not trip_stops:
        return None

    current_trip_stop = find_trip_stop_by_sequence(trip_stops, current_stop_seq)
    if current_trip_stop is None and 0 <= current_stop_seq < len(trip_stops):
        current_trip_stop = trip_stops[current_stop_seq]
    if current_trip_stop is None:
        return None

    final_stop = trip_stops[-1]
    current_sched_dt = build_gtfs_datetime(
        selected_trip["service_date"],
        current_trip_stop["arrival_time"],
    )
    final_sched_dt = build_gtfs_datetime(
        selected_trip["service_date"],
        final_stop["arrival_time"],
    )
    if current_sched_dt is None or final_sched_dt is None:
        return None

    current_sched_dt = current_sched_dt.replace(tzinfo=UK_TZ)
    final_sched_dt = final_sched_dt.replace(tzinfo=UK_TZ)

    terminal_distance_km = haversine(
        current_lat,
        current_lng,
        final_stop["lat"],
        final_stop["lng"],
    )
    if terminal_distance_km <= TERMINAL_ARRIVAL_RADIUS_KM:
        delay_min = max(0.0, (local_time - final_sched_dt).total_seconds() / 60.0)
        return {
            "eta": 0.5,
            "delay_minutes": round(delay_min, 1),
            "service_time": format_gtfs_time(selected_trip.get("service_time")),
            "current_stop_sequence": final_stop["sequence"],
            "current_stop_scheduled": final_stop["arrival_time"],
            "final_stop_scheduled": final_stop["arrival_time"],
        }

    delay_min = max(0.0, (local_time - current_sched_dt).total_seconds() / 60.0)
    eta_min = max(0.5, ((final_sched_dt - local_time).total_seconds() / 60.0) + delay_min)

    return {
        "eta": round(eta_min, 1),
        "delay_minutes": round(delay_min, 1),
        "service_time": format_gtfs_time(selected_trip.get("service_time")),
        "current_stop_sequence": current_stop_seq,
        "current_stop_scheduled": current_trip_stop["arrival_time"],
        "final_stop_scheduled": trip_stops[-1]["arrival_time"],
    }


def apply_eta_guardrail(route, eta_min, eta_method, current_lat, current_lng,
                        remaining_stops=None, current_time=None, current_stop_seq=None):
    """Keep live ETA estimates anchored to the matched timetable when available."""
    if eta_min is None or current_lat is None or current_lng is None:
        return eta_min, eta_method

    schedule_eta = estimate_schedule_eta_from_position(
        route,
        current_lat,
        current_lng,
        current_time=current_time,
        current_stop_seq=current_stop_seq,
    )
    if not schedule_eta:
        return round(float(eta_min), 1), eta_method

    schedule_eta_min = schedule_eta["eta"]
    eta_value = round(float(eta_min), 1)
    tolerance_min = max(
        4.0,
        float(remaining_stops or 0) * 1.5,
        schedule_eta_min * 0.4,
    )
    max_eta = schedule_eta_min + tolerance_min
    min_eta = max(0.5, schedule_eta_min - max(3.0, schedule_eta_min * 0.65))

    if eta_value < min_eta or eta_value > max_eta:
        logger.warning(
            "[ETA] Guardrail applied for route %s (%s): %.1f via %s replaced with schedule %.1f "
            "(seq=%s remaining=%s service=%s current_sched=%s final_sched=%s)",
            route.route_name,
            route.direction,
            eta_value,
            eta_method,
            schedule_eta_min,
            schedule_eta["current_stop_sequence"],
            remaining_stops,
            schedule_eta["service_time"] or "unknown",
            schedule_eta["current_stop_scheduled"],
            schedule_eta["final_stop_scheduled"],
        )
        return schedule_eta_min, "schedule_guardrail"

    return eta_value, eta_method


def resolve_live_eta(route, log, current_stop_seq, remaining_stops):
    """Resolve the best ETA for a live bus using model first, then formula fallback."""
    if log.bus_lat is None or log.bus_lng is None:
        return log.predicted_eta, None

    current_eta = predict_eta_xgboost(
        route=route,
        passenger_count=log.passenger_count or 0,
        traffic_delay_seconds=log.traffic_delay or 0,
        current_stop_seq=current_stop_seq,
        remaining_stops=remaining_stops,
        current_time=log.timestamp or datetime.now(),
    )
    if current_eta is not None:
        return apply_eta_guardrail(
            route,
            current_eta,
            "xgboost",
            log.bus_lat,
            log.bus_lng,
            remaining_stops=remaining_stops,
            current_time=log.timestamp,
            current_stop_seq=current_stop_seq,
        )

    if log.predicted_eta is not None:
        return apply_eta_guardrail(
            route,
            log.predicted_eta,
            "formula_fallback",
            log.bus_lat,
            log.bus_lng,
            remaining_stops=remaining_stops,
            current_time=log.timestamp,
            current_stop_seq=current_stop_seq,
        )

    fallback_eta = calculate_eta(
        haversine(log.bus_lat, log.bus_lng, route.dest_lat, route.dest_lng),
        log.traffic_delay or 0,
        log.passenger_count or 0,
    )
    return apply_eta_guardrail(
        route,
        fallback_eta,
        "formula_fallback",
        log.bus_lat,
        log.bus_lng,
        remaining_stops=remaining_stops,
        current_time=log.timestamp,
        current_stop_seq=current_stop_seq,
    )


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
                origin_lat=route.origin_lat,
                origin_lng=route.origin_lng,
                destination_lat=route.dest_lat,
                destination_lng=route.dest_lng,
            )

        return select_next_route_trip(
            gtfs_data,
            route.route_name,
            route.direction,
            local_time,
            origin_name=route.origin_name,
            destination_name=route.destination_name,
            origin_lat=route.origin_lat,
            origin_lng=route.origin_lng,
            destination_lat=route.dest_lat,
            destination_lng=route.dest_lng,
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
        "eta_method": "schedule_only",
        "bus_available": False,
        "message": "No live bus currently available on this route",
        "is_live": False,
        "stops": stops_data,
    }


def resolve_route_stop_schedule(route_stop, schedule_by_stop_id=None, schedule_by_sequence=None):
    """Resolve the best scheduled time for a route stop from the matched trip first."""
    schedule_by_stop_id = schedule_by_stop_id or {}
    schedule_by_sequence = schedule_by_sequence or {}

    stop = getattr(route_stop, "stop", None)
    stop_id = getattr(stop, "stop_id", None)
    if stop_id and stop_id in schedule_by_stop_id:
        return schedule_by_stop_id[stop_id]

    return schedule_by_sequence.get(route_stop.sequence, route_stop.scheduled_arrival)


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


def is_near_major_stop(bus_lat: float, bus_lng: float, route) -> tuple:
    """
    Check if bus is near a major stop where crowd detection should be applied.
    Uses the route's actual stops from the database. Falls back to route-specific
    hardcoded constants if the route has no database stops loaded yet.

    Args:
        bus_lat: Current bus latitude.
        bus_lng: Current bus longitude.
        route:   SQLAlchemy Route object (has .route_name, .direction, .route_stops).

    Returns:
        Tuple of (is_near: bool, nearest_stop_name: str, distance_km: float)
    """
    # Build candidate major stop list from database RouteStop records for this route.
    # Use all stops in the route as candidates (crowd detection checks proximity anyway).
    candidate_stops = []
    try:
        for rs in route.route_stops:
            if rs.stop and rs.stop.lat is not None and rs.stop.lng is not None:
                candidate_stops.append((rs.stop.stop_name, rs.stop.lat, rs.stop.lng))
    except Exception:
        candidate_stops = []

    # Fall back to route-specific hardcoded constants when DB stops unavailable.
    if not candidate_stops:
        route_name = (getattr(route, 'route_name', '') or '').strip().upper()
        direction = (getattr(route, 'direction', 'outbound') or 'outbound').strip().lower()
        fallback_stops = FALLBACK_MAJOR_STOPS_BY_ROUTE.get(route_name, {})
        candidate_stops = fallback_stops.get(direction, [])

        if candidate_stops:
            logger.debug(
                f"[Crowd] is_near_major_stop: no DB stops for {route.route_name} "
                f"({route.direction}); using {route_name} hardcoded fallback"
            )
        else:
            logger.warning(
                f"[Crowd] is_near_major_stop: no DB stops and no hardcoded fallback "
                f"for {route.route_name} ({route.direction})"
            )
            return False, None, float('inf')

    min_dist = float('inf')
    nearest_stop = None

    for stop_name, stop_lat, stop_lng in candidate_stops:
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
    routing_state = _tomtom_service_state["routing"]

    if routing_state["disabled"]:
        return get_route_distance_osrm(origin_lat, origin_lng, dest_lat, dest_lng)

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
            logger.warning("[TomTom Routing] No routes found - falling back to OSRM")
            return get_route_distance_osrm(origin_lat, origin_lng, dest_lat, dest_lng)

    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (401, 403):
            routing_state["disabled"] = True
            if not routing_state["auth_logged"]:
                logger.warning(
                    f"[TomTom Routing] HTTP {status_code} from TomTom. "
                    "Disabling TomTom routing for this process and falling back to OSRM."
                )
                routing_state["auth_logged"] = True
        else:
            logger.error(f"[TomTom Routing] Error: {exc}")
        return get_route_distance_osrm(origin_lat, origin_lng, dest_lat, dest_lng)
    except Exception as exc:
        logger.error(f"[TomTom Routing] Error: {exc}")
        return get_route_distance_osrm(origin_lat, origin_lng, dest_lat, dest_lng)


# =========================================================================
# BODS Real-Time Bus Fetcher
# =========================================================================
def fetch_all_buses_for_route(route, all_vehicles: list | None = None):
    """
    Fetch ALL buses for a given route from BODS.

    When all_vehicles is provided (bulk-fetch path), filters the pre-fetched list
    by line_ref for this route instead of making a new BODS HTTP request.

    Returns: List of vehicle data dicts, or empty list if no buses
    """
    route_name = route.route_name
    direction = route.direction

    if all_vehicles is not None:
        # Bulk-fetch path: filter the pre-fetched list by line_ref for this route
        vehicles = [v for v in all_vehicles if (v.get("line") or "").strip() == route_name]
        if not vehicles:
            logger.info(f"[BODS] No vehicles for route {route_name} in bulk result")
            return []
        logger.info(f"[BODS] {len(vehicles)} vehicle(s) for {route_name} after line filter")
    else:
        # Legacy path: individual BODS call (used when all_vehicles not supplied)
        if not BODS_API_KEY:
            logger.warning("[BODS] API key not set — no live bus data available")
            return []
        try:
            vehicles = fetch_bods_vehicles(api_key=BODS_API_KEY, line_ref=route_name)
        except Exception as exc:
            logger.error(f"[BODS] Fetch error: {exc}")
            return []
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

    direction_confirmed = []
    for vehicle in vehicles:
        vehicle_id = vehicle.get("vehicle_id") or "unknown"
        is_match, reason, detail = confirm_vehicle_direction(route, vehicle)
        if is_match:
            logger.info(
                "[BODS] Direction accept for route %s (%s) vehicle %s via %s: detail=%s destination=%s direction=%s",
                route_name,
                direction,
                vehicle_id,
                reason,
                detail or "n/a",
                vehicle.get("destination"),
                vehicle.get("direction"),
            )
            direction_confirmed.append(vehicle)
        else:
            logger.info(
                "[BODS] Direction reject for route %s (%s) vehicle %s via %s: detail=%s destination=%s direction=%s",
                route_name,
                direction,
                vehicle_id,
                reason,
                detail or "n/a",
                vehicle.get("destination"),
                vehicle.get("direction"),
            )

    if not direction_confirmed:
        logger.warning(
            f"[BODS] No direction-confirmed vehicles found for route {route_name} ({direction})"
        )
        return []

    vehicles = [
        v for v in direction_confirmed
        if is_vehicle_live_for_route(v, route)
    ]

    if not vehicles:
        logger.warning(f"[BODS] No recent Bristol-route vehicles found for route {route_name}")
        return []

    logger.info(f"[BODS] Returning {len(vehicles)} matching vehicle(s)")
    for v in vehicles:
        logger.info(f"  - Vehicle {v.get('vehicle_id')}: ({v['lat']:.5f}, {v['lng']:.5f}) to {v.get('destination')}")

    return vehicles


# ---------------------------------------------------------------------------
# BODS Bulk Fetch Cache (one call per cycle, shared across all routes)
# ---------------------------------------------------------------------------
_bods_bulk_cache: dict = {"vehicles": None, "cycle_id": -1}
_bods_cycle_counter: int = 0
_status_bods_cache: dict = {"vehicles": None, "fetched_at": None}


def dedupe_bods_vehicles(vehicles: list[dict]) -> list[dict]:
    """Keep the newest unique vehicle record for each vehicle_id."""
    deduped = {}

    for vehicle in vehicles:
        vehicle_id = (vehicle.get("vehicle_id") or "").strip()
        key = vehicle_id or (
            (vehicle.get("operator") or "").strip(),
            (vehicle.get("line") or "").strip(),
            vehicle.get("lat"),
            vehicle.get("lng"),
            vehicle.get("recorded_at"),
        )
        deduped[key] = vehicle

    return list(deduped.values())


def fetch_bods_vehicles_uncached(log_context: str) -> list[dict]:
    """Fetch a fresh BODS vehicle snapshot without using the fusion cache."""
    if not BODS_API_KEY:
        logger.warning("[BODS] API key not set — no live bus data available")
        return []

    try:
        vehicles = []

        if BODS_OPERATOR_ALLOWLIST:
            logger.info(
                f"[BODS] {log_context}: batching by operator "
                f"({', '.join(BODS_OPERATOR_ALLOWLIST)})"
            )
            for operator_ref in BODS_OPERATOR_ALLOWLIST:
                operator_vehicles = fetch_bods_vehicles(
                    api_key=BODS_API_KEY,
                    operator_ref=operator_ref,
                )
                logger.info(
                    f"[BODS] {log_context}: operator {operator_ref} returned "
                    f"{len(operator_vehicles)} raw vehicles"
                )
                vehicles.extend(operator_vehicles)
        else:
            vehicles = fetch_bods_vehicles(api_key=BODS_API_KEY)
            logger.info(f"[BODS] {log_context}: {len(vehicles)} raw vehicles")

        vehicles = dedupe_bods_vehicles(vehicles)
        logger.info(f"[BODS] {log_context}: {len(vehicles)} deduped vehicles")
        return vehicles
    except Exception as exc:
        logger.error(f"[BODS] {log_context} error: {exc}")
        return []


def fetch_bods_vehicles_bulk(cycle_id: int) -> list:
    """
    Fetch vehicles once per cycle for the configured operator allowlist.
    Result is cached by cycle_id so each route in the same cycle reuses it.
    """
    global _bods_bulk_cache

    if _bods_bulk_cache["cycle_id"] == cycle_id and _bods_bulk_cache["vehicles"] is not None:
        logger.info(
            f"[BODS] Reusing bulk cache (cycle {cycle_id}): "
            f"{len(_bods_bulk_cache['vehicles'])} vehicles"
        )
        return _bods_bulk_cache["vehicles"]

    if not BODS_API_KEY:
        logger.warning("[BODS] API key not set — no live bus data available")
        _bods_bulk_cache = {"vehicles": [], "cycle_id": cycle_id}
        return []

    try:
        vehicles = []

        if BODS_OPERATOR_ALLOWLIST:
            logger.info(
                f"[BODS] Bulk fetch cycle {cycle_id}: batching by operator "
                f"({', '.join(BODS_OPERATOR_ALLOWLIST)})"
            )
            for operator_ref in BODS_OPERATOR_ALLOWLIST:
                operator_vehicles = fetch_bods_vehicles(
                    api_key=BODS_API_KEY,
                    operator_ref=operator_ref,
                )
                logger.info(
                    f"[BODS] Operator {operator_ref}: "
                    f"{len(operator_vehicles)} raw vehicles"
                )
                vehicles.extend(operator_vehicles)
        else:
            vehicles = fetch_bods_vehicles(api_key=BODS_API_KEY)
            logger.info(
                f"[BODS] Bulk fetch cycle {cycle_id}: "
                f"{len(vehicles)} raw vehicles"
            )

        vehicles = dedupe_bods_vehicles(vehicles)
        logger.info(
            f"[BODS] Bulk fetch cycle {cycle_id}: "
            f"{len(vehicles)} deduped vehicles"
        )
        _bods_bulk_cache = {"vehicles": vehicles, "cycle_id": cycle_id}
        return vehicles
    except Exception as exc:
        logger.error(f"[BODS] Bulk fetch error: {exc}")
        _bods_bulk_cache = {"vehicles": [], "cycle_id": cycle_id}
        return []


def fetch_bods_vehicles_status_snapshot() -> list[dict]:
    """Fetch or reuse a short-lived BODS snapshot for status requests."""
    global _status_bods_cache

    fetched_at = _status_bods_cache.get("fetched_at")
    now = datetime.now()
    if (
        _status_bods_cache["vehicles"] is not None
        and fetched_at is not None
        and (now - fetched_at).total_seconds() <= STATUS_BODS_CACHE_SECONDS
    ):
        logger.info(
            "[BODS] Reusing status snapshot: %s vehicles (%ss old)",
            len(_status_bods_cache["vehicles"]),
            round((now - fetched_at).total_seconds(), 1),
        )
        return _status_bods_cache["vehicles"]

    vehicles = fetch_bods_vehicles_uncached("Status snapshot")
    _status_bods_cache = {"vehicles": vehicles, "fetched_at": now}
    return vehicles


# =========================================================================
# TomTom Traffic API
# =========================================================================
def fetch_traffic_delay(lat: float, lng: float):
    """
    Query TomTom Traffic Flow API for current delay at a point.
    Returns delay in seconds, or 0.0 on failure.
    """
    traffic_state = _tomtom_service_state["traffic"]

    if not TOMTOM_API_KEY or traffic_state["disabled"]:
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
        
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (401, 403):
            traffic_state["disabled"] = True
            if not traffic_state["auth_logged"]:
                logger.warning(
                    f"[TomTom] HTTP {status_code} from TomTom traffic API. "
                    "Disabling traffic lookups for this process and using zero-delay fallback."
                )
                traffic_state["auth_logged"] = True
            return 0.0
        logger.error(f"[TomTom] Error: {exc}")
        return 0.0
    except Exception as exc:
        logger.error(f"[TomTom] Error: {exc}")
        return 0.0


def resolve_traffic_delay_seconds(point_delay_seconds, route_summary=None):
    """Resolve the traffic delay to persist without discarding non-zero flow data."""
    point_delay = max(0.0, float(point_delay_seconds or 0.0))
    route_delay = 0.0
    if route_summary:
        route_delay = max(0.0, float(route_summary.get("traffic_delay_sec") or 0.0))

    if point_delay > route_delay:
        logger.info(
            "[TomTom] Using point-flow traffic delay %.1fs over route delay %.1fs",
            point_delay,
            route_delay,
        )

    return round(max(point_delay, route_delay), 1)


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


def _center_in_left_roi(x1: float, x2: float, frame_width: int) -> bool:
    """Return True if a detection's horizontal center lies within the left
    region of the frame defined by CROWD_ROI_X_FRACTION. Fails open (counts
    the detection) when frame_width is unknown, so ROI logic never silently
    zeroes out a valid crowd reading."""
    if frame_width <= 0:
        return True
    center_x = (x1 + x2) / 2.0
    return center_x <= frame_width * CROWD_ROI_X_FRACTION


def _is_waiting_passenger(
    x1: float, y1: float, x2: float, y2: float,
    frame_width: int, frame_height: int,
) -> bool:
    """Return True if a person detection is a waiting passenger on the
    pavement: horizontal center within the left ROI (CROWD_ROI_X_FRACTION)
    AND bounding-box bottom (y2) at/below the ground line
    (CROWD_ROI_Y_MIN_FRACTION). Fails open per-dimension when frame_width
    or frame_height is unknown (<= 0), matching _center_in_left_roi, so
    the ROI logic never silently zeroes a valid crowd reading."""
    if not _center_in_left_roi(x1, x2, frame_width):
        return False
    if frame_height <= 0:
        return True
    return y2 >= frame_height * CROWD_ROI_Y_MIN_FRACTION


def _person_overlap_fraction(
    person: tuple[float, float, float, float],
    bus: tuple[float, float, float, float],
) -> float:
    """Return the fraction of the PERSON box area that overlaps the bus box.
    1.0 means the person box is fully contained inside the bus box; 0.0 means
    no overlap at all."""
    px1, py1, px2, py2 = person
    bx1, by1, bx2, by2 = bus
    intersect_w = max(0.0, min(px2, bx2) - max(px1, bx1))
    intersect_h = max(0.0, min(py2, by2) - max(py1, by1))
    person_area = max(1.0, (px2 - px1) * (py2 - py1))
    return (intersect_w * intersect_h) / person_area


def _is_inside_bus(
    person: tuple[float, float, float, float],
    buses: list[tuple[float, float, float, float]],
) -> bool:
    """Return True if a person detection is "inside the bus" (behind glass)
    and should be excluded from the count: the person box must be at least
    BUS_CONTAINMENT_MIN contained within a bus box AND its bottom (y2) must
    be ABOVE the bus interior line (bus_y1 + BUS_INTERIOR_Y_FRACTION *
    bus_height). Fails open (returns False) when buses is empty, so a
    missing bus detection never zeroes out the crowd count."""
    for bus in buses:
        if _person_overlap_fraction(person, bus) >= BUS_CONTAINMENT_MIN:
            bus_y1, bus_y2 = bus[1], bus[3]
            interior_line = bus_y1 + BUS_INTERIOR_Y_FRACTION * (bus_y2 - bus_y1)
            if person[3] < interior_line:
                return True
    return False


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

    # Count persons (class 0) as waiting passengers unless they are "inside
    # the bus": heavily contained within a detected bus box (class 5) AND
    # sitting above the bus interior line (behind the glass). See
    # BUS_CONTAINMENT_MIN and BUS_INTERIOR_Y_FRACTION. No bus detected means
    # nobody is excluded (fail open). CROWD_ROI_X_FRACTION /
    # CROWD_ROI_Y_MIN_FRACTION remain available as an optional manual
    # pre-filter but are no-ops by default.
    frame_width = frame.shape[1] if frame is not None else 0
    frame_height = frame.shape[0] if frame is not None else 0
    persons: list[tuple[float, float, float, float]] = []
    buses: list[tuple[float, float, float, float]] = []
    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            if cls == 0:
                persons.append(tuple(box.xyxy[0].tolist()))
            elif cls == 5:
                buses.append(tuple(box.xyxy[0].tolist()))

    count = 0
    excluded = 0
    for x1, y1, x2, y2 in persons:
        if not _is_waiting_passenger(x1, y1, x2, y2, frame_width, frame_height):
            continue
        if _is_inside_bus((x1, y1, x2, y2), buses):
            excluded += 1
            continue
        count += 1

    logger.info(
        f"[YOLO] Frame {_frame_number}: {count} waiting passenger(s), "
        f"{excluded} excluded as in-bus ({len(buses)} bus box(es) detected)"
    )
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
    route = db.session.get(Route, route_id)
    
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
            current_trip_stop = find_trip_stop_by_sequence(trip_stops, current_stop_seq)
            if current_trip_stop is None and 0 <= current_stop_seq < len(trip_stops):
                current_trip_stop = trip_stops[current_stop_seq]
            if current_trip_stop is not None:
                current_stop_scheduled = current_trip_stop["arrival_time"]
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
    route = db.session.get(Route, route_id)
    route_delay_min = calculate_route_delay(route, current_stop_seq, current_eta_min)
    selected_trip = None
    schedule_by_sequence = {}
    schedule_by_stop_id = {}
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
            schedule_by_stop_id = {
                stop["stop_id"]: stop["arrival_time"]
                for stop in selected_trip["stops"]
                if stop.get("stop_id")
            }

    # Use the matched GTFS trip as the delay baseline when available.
    _, current_delay_min, _ = get_current_service_time(
        route_id, current_lat, current_lng, local_time
    )
    applied_delay_min = current_delay_min if current_delay_min is not None else route_delay_min
    
    predictions = []
    
    for rs in route_stops:
        scheduled = resolve_route_stop_schedule(
            rs,
            schedule_by_stop_id=schedule_by_stop_id,
            schedule_by_sequence=schedule_by_sequence,
        )
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

                # Single BODS call for this entire cycle — fanned out per route below
                global _bods_cycle_counter
                _bods_cycle_counter += 1
                all_vehicles = fetch_bods_vehicles_bulk(_bods_cycle_counter)

                for route in routes:
                    logger.info(f"\n[Fusion] === Route {route.route_name} ({route.direction}) ===")

                    # Step 1 — Fetch ALL buses for this route
                    vehicles = fetch_all_buses_for_route(route, all_vehicles=all_vehicles)
                    
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

                        tag = f"[Fusion:{route.route_name}:{route.direction[:3]}]"
                        logger.info(f"\n{tag} -- Processing Bus {vehicle_id} --")
                        logger.info(f"{tag}   Position: ({bus_lat:.5f}, {bus_lng:.5f})")
                        logger.info(f"{tag}   Destination: {vehicle_data.get('destination')}")
                        logger.info(f"{tag}   Operator: {operator}")

                        # Step 2 — Traffic from TomTom
                        point_traffic_delay = fetch_traffic_delay(bus_lat, bus_lng)

                        # Step 3 — Crowd from YOLO (ONLY at major stops)
                        is_near_major, nearest_stop_name, distance_to_stop = is_near_major_stop(
                            bus_lat, bus_lng, route
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

                        traffic_delay = resolve_traffic_delay_seconds(
                            point_traffic_delay,
                            route_summary,
                        )

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
                        eta_method = "xgboost" if eta is not None else "formula_fallback"

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
                        logger.info(
                            "[Fusion] ETA resolved for route %s vehicle %s via %s: %.1f min",
                            route.route_name,
                            vehicle_id,
                            eta_method,
                            eta,
                        )
                        eta, eta_method = apply_eta_guardrail(
                            route,
                            eta,
                            eta_method,
                            bus_lat,
                            bus_lng,
                            remaining_stops=remaining_stops,
                            current_time=datetime.now(UK_TZ),
                            current_stop_seq=current_stop_seq,
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
                        logger.info(f"{tag} Bus {vehicle_id}: ETA={eta}min | {delay_str}")
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
# History Helpers
# =========================================================================
def parse_bounded_int(value, default, min_value, max_value):
    """Parse and clamp an integer query parameter."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    return max(min_value, min(parsed, max_value))


def build_history_point(log):
    """Serialize a BusLog row for frontend charts."""
    return {
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        "vehicle_id": log.vehicle_id,
        "eta": log.predicted_eta,
        "passenger_count": log.passenger_count,
        "traffic_delay": log.traffic_delay,
        "delay_minutes": log.delay_minutes,
        "scheduled_service_time": log.scheduled_service_time,
    }


def summarize_history_metric(points, key):
    """Return summary statistics for a numeric history series."""
    values = [point[key] for point in points if isinstance(point.get(key), (int, float))]
    if not values:
        return {
            "latest": None,
            "min": None,
            "max": None,
            "average": None,
        }

    return {
        "latest": values[-1],
        "min": round(min(values), 1),
        "max": round(max(values), 1),
        "average": round(sum(values) / len(values), 1),
    }


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
            "/api/routes/<route_id>/history",
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
    
    route = db.session.get(Route, route_id)
    if not route:
        return jsonify({"error": "Route not found"}), 404
    
    route_stops = (RouteStop.query
                   .filter_by(route_id=route_id)
                   .order_by(RouteStop.sequence)
                   .all())
    
    return jsonify({
        "route": route.to_dict(),
        "stops": [
            {
                **rs.to_dict(),
                "scheduled_arrival": format_gtfs_time(rs.scheduled_arrival),
            }
            for rs in route_stops
        ]
    })


@app.route("/api/routes/<int:route_id>/predictions", methods=["GET"])
def get_route_predictions(route_id):
    """
    Return stop-by-stop predictions with scheduled times and delays.
    Similar to the transit app showing 'Delayed X min' at each stop.
    """
    route = db.session.get(Route, route_id)
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
        or not is_position_plausible_for_timetable(route, log.bus_lat, log.bus_lng, log.timestamp)
    ):
        return jsonify(build_schedule_only_response(route_id, route, current_time=datetime.now(UK_TZ)))
    
    # Calculate stop-by-step predictions
    remaining_stops, _, current_stop_seq = count_remaining_stops(route_id, log.bus_lat, log.bus_lng)
    current_eta, eta_method = resolve_live_eta(route, log, current_stop_seq, remaining_stops)

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
        "eta_method": eta_method,
        "bus_available": True,
        "is_live": True,
        "bus_position": {
            "lat": log.bus_lat,
            "lng": log.bus_lng,
            "last_updated": log.timestamp.isoformat() if log.timestamp else None
        },
        "stops": stop_predictions
    })


@app.route("/api/routes/<int:route_id>/history", methods=["GET"])
def get_route_history(route_id):
    """Return recent BusLog history for a route or a specific vehicle."""
    route = db.session.get(Route, route_id)
    if not route:
        return jsonify({"error": "Route not found"}), 404

    hours = parse_bounded_int(request.args.get("hours"), default=6, min_value=1, max_value=48)
    limit = parse_bounded_int(request.args.get("limit"), default=36, min_value=6, max_value=240)
    vehicle_id = (request.args.get("vehicle_id") or "").strip() or None
    cutoff = datetime.now(UK_TZ) - timedelta(hours=hours)

    history_query = (
        BusLog.query
        .filter_by(route_id=route_id)
        .filter(BusLog.timestamp >= cutoff)
        .filter(BusLog.predicted_eta.isnot(None))
        .filter(BusLog.bus_lat.isnot(None))
        .filter(BusLog.bus_lng.isnot(None))
    )

    if vehicle_id:
        history_query = history_query.filter(BusLog.vehicle_id == vehicle_id)

    logs = (
        history_query
        .order_by(BusLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    logs.reverse()

    points = [build_history_point(log) for log in logs]
    stats = {
        "eta": summarize_history_metric(points, "eta"),
        "delay_minutes": summarize_history_metric(points, "delay_minutes"),
        "passenger_count": summarize_history_metric(points, "passenger_count"),
        "traffic_delay": summarize_history_metric(points, "traffic_delay"),
    }

    return jsonify({
        "route": route.to_dict(),
        "vehicle_id": vehicle_id,
        "hours": hours,
        "limit": limit,
        "sample_count": len(points),
        "points": points,
        "stats": stats,
        "is_live": bool(points),
    })


def get_latest_logs_by_vehicle_for_route(route_id, vehicle_ids, lookback_hours=6):
    """Return the newest recent BusLog for each requested vehicle on a route."""
    valid_vehicle_ids = [vehicle_id for vehicle_id in vehicle_ids if vehicle_id and vehicle_id != "unknown"]
    if not valid_vehicle_ids:
        return {}

    recent_cutoff = datetime.now() - timedelta(hours=lookback_hours)
    logs = (
        BusLog.query
        .filter_by(route_id=route_id)
        .filter(BusLog.vehicle_id.in_(valid_vehicle_ids))
        .filter(BusLog.timestamp >= recent_cutoff)
        .order_by(BusLog.timestamp.desc())
        .all()
    )

    latest_logs = {}
    for log in logs:
        if log.vehicle_id and log.vehicle_id not in latest_logs:
            latest_logs[log.vehicle_id] = log

    return latest_logs


def get_recent_logs_by_vehicle_for_route(route_id, max_age_seconds=STATUS_LOG_FALLBACK_GRACE_SECONDS,
                                         current_time=None):
    """Return the newest recent BusLog for each live vehicle on a route."""
    local_now = to_uk_datetime(current_time)
    recent_cutoff = local_now - timedelta(seconds=max_age_seconds)

    logs = (
        BusLog.query
        .filter_by(route_id=route_id)
        .filter(BusLog.timestamp >= recent_cutoff)
        .filter(BusLog.vehicle_id.isnot(None))
        .filter(BusLog.bus_lat.isnot(None))
        .filter(BusLog.bus_lng.isnot(None))
        .order_by(BusLog.timestamp.desc())
        .all()
    )

    latest_logs = {}
    for log in logs:
        vehicle_id = (log.vehicle_id or "").strip()
        if not vehicle_id or vehicle_id == "unknown":
            continue
        if (
            vehicle_id not in latest_logs
            and is_recent_live_timestamp(log.timestamp, max_age_seconds=max_age_seconds)
        ):
            latest_logs[vehicle_id] = log

    return latest_logs


def resolve_operator_for_vehicle(vehicle_id, fallback_operator=None):
    """Resolve a vehicle operator using explicit data, cached metadata, or the ID prefix."""
    if fallback_operator and fallback_operator != "unknown":
        return fallback_operator

    operator = _latest_bus_metadata.get(vehicle_id, {}).get("operator")
    if operator:
        return operator

    if vehicle_id and "-" in vehicle_id:
        return vehicle_id.split("-", 1)[0] or "unknown"

    return "unknown"


def is_trip_effectively_finished(route, current_lat, current_lng, current_time,
                                 current_stop_seq=None, remaining_stops=None):
    """Return True when a fallback bus is effectively at the final stop and due/finished."""
    if route is None or current_lat is None or current_lng is None:
        return False

    if current_stop_seq is None or remaining_stops is None:
        remaining_stops, _, current_stop_seq = count_remaining_stops(
            route.id,
            current_lat,
            current_lng,
        )

    if remaining_stops is None or remaining_stops > 0:
        return False

    local_time = to_uk_datetime(current_time)
    selected_trip = get_gtfs_schedule_trip(
        route,
        current_time=local_time,
        current_stop_seq=current_stop_seq,
        mode="live",
    )
    if not selected_trip:
        return False

    trip_stops = selected_trip.get("stops", [])
    if not trip_stops:
        return False

    final_stop = trip_stops[-1]
    final_sched_dt = build_gtfs_datetime(
        selected_trip["service_date"],
        final_stop["arrival_time"],
    )
    if final_sched_dt is None:
        return False

    final_sched_dt = final_sched_dt.replace(tzinfo=UK_TZ)
    terminal_distance_km = haversine(
        current_lat,
        current_lng,
        final_stop["lat"],
        final_stop["lng"],
    )
    return (
        current_stop_seq >= final_stop["sequence"]
        and terminal_distance_km <= ORIGIN_STAGING_RADIUS_KM
        and local_time >= final_sched_dt
    )


def is_log_eligible_for_status_fallback(route, log, current_time=None):
    """Return True when a recent BusLog row is safe to reuse for live status."""
    if log is None:
        return False

    vehicle_id = (log.vehicle_id or "").strip()
    if not vehicle_id or vehicle_id == "unknown":
        return False

    if log.bus_lat is None or log.bus_lng is None or log.timestamp is None:
        return False

    if not is_recent_live_timestamp(
        log.timestamp,
        max_age_seconds=STATUS_LOG_FALLBACK_GRACE_SECONDS,
    ):
        return False

    if not is_position_plausible_for_timetable(route, log.bus_lat, log.bus_lng, log.timestamp):
        return False

    remaining_stops, _, current_stop_seq = count_remaining_stops(route.id, log.bus_lat, log.bus_lng)
    if is_trip_effectively_finished(
        route,
        log.bus_lat,
        log.bus_lng,
        log.timestamp if current_time is None else current_time,
        current_stop_seq=current_stop_seq,
        remaining_stops=remaining_stops,
    ):
        logger.info(
            "[Status] Skipping fallback log for route %s (%s) vehicle %s: trip effectively finished",
            route.route_name,
            route.direction,
            vehicle_id,
        )
        return False

    return True


def build_status_bus_entry(route, vehicle_id, operator, bus_lat, bus_lng, vehicle_timestamp,
                           latest_log=None):
    """Build a status payload for a single bus using live coordinates plus latest enrichment."""
    vehicle_timestamp = vehicle_timestamp or (latest_log.timestamp if latest_log is not None else datetime.now(UK_TZ))
    passenger_count = latest_log.passenger_count if latest_log and latest_log.passenger_count is not None else 0
    traffic_delay = latest_log.traffic_delay if latest_log and latest_log.traffic_delay is not None else 0

    remaining_stops, _, current_stop_seq = count_remaining_stops(route.id, bus_lat, bus_lng)
    log_for_eta = SimpleNamespace(
        vehicle_id=vehicle_id,
        bus_lat=bus_lat,
        bus_lng=bus_lng,
        passenger_count=passenger_count,
        traffic_delay=traffic_delay,
        predicted_eta=latest_log.predicted_eta if latest_log else None,
        timestamp=vehicle_timestamp,
    )
    current_eta, eta_method = resolve_live_eta(route, log_for_eta, current_stop_seq, remaining_stops)

    scheduled_service_time = latest_log.scheduled_service_time if latest_log else None
    delay_minutes = latest_log.delay_minutes if latest_log else None
    if scheduled_service_time is None or delay_minutes is None:
        live_service_time, live_delay_minutes, _ = get_current_service_time(
            route.id,
            bus_lat,
            bus_lng,
            current_time=vehicle_timestamp,
        )
        if scheduled_service_time is None:
            scheduled_service_time = live_service_time
        if delay_minutes is None:
            delay_minutes = live_delay_minutes

    if delay_minutes is None:
        delay_minutes = calculate_route_delay(route, current_stop_seq, current_eta)

    stop_predictions = calculate_stop_predictions(
        route.id,
        bus_lat,
        bus_lng,
        current_eta,
        vehicle_timestamp,
    )

    return {
        "vehicle_id": vehicle_id,
        "operator": resolve_operator_for_vehicle(vehicle_id, operator),
        "position": {
            "lat": bus_lat,
            "lng": bus_lng,
        },
        "eta": current_eta,
        "eta_method": eta_method,
        "passenger_count": passenger_count,
        "traffic_delay": traffic_delay,
        "scheduled_service_time": scheduled_service_time,
        "delay_minutes": delay_minutes,
        "remaining_stops": remaining_stops,
        "current_stop_sequence": current_stop_seq,
        "timestamp": vehicle_timestamp.isoformat() if vehicle_timestamp else None,
        "stop_predictions": stop_predictions,
    }


def build_status_bus_list_from_live_snapshot(route, all_vehicles=None, current_time=None):
    """Build the status bus list from live BODS buses plus recent per-vehicle fallback logs."""
    live_vehicles = fetch_all_buses_for_route(route, all_vehicles=all_vehicles)
    recent_logs = get_recent_logs_by_vehicle_for_route(
        route.id,
        current_time=current_time,
    )
    candidate_vehicle_ids = {
        vehicle.get("vehicle_id")
        for vehicle in live_vehicles
        if vehicle.get("vehicle_id")
    } | set(recent_logs.keys())

    latest_logs = get_latest_logs_by_vehicle_for_route(
        route.id,
        list(candidate_vehicle_ids),
    )
    for vehicle_id, log in recent_logs.items():
        latest_logs.setdefault(vehicle_id, log)

    bus_list = []
    seen_vehicle_ids = set()
    for vehicle_data in live_vehicles:
        vehicle_id = vehicle_data.get("vehicle_id") or "unknown"
        seen_vehicle_ids.add(vehicle_id)
        latest_log = latest_logs.get(vehicle_id)
        vehicle_timestamp = (
            parse_iso_datetime(vehicle_data.get("recorded_at"))
            or (latest_log.timestamp if latest_log is not None else None)
            or datetime.now(UK_TZ)
        )
        bus_list.append(build_status_bus_entry(
            route,
            vehicle_id,
            resolve_vehicle_operator(vehicle_data),
            vehicle_data["lat"],
            vehicle_data["lng"],
            vehicle_timestamp,
            latest_log=latest_log,
        ))

    for vehicle_id, fallback_log in sorted(
        recent_logs.items(),
        key=lambda item: item[1].timestamp.timestamp() if item[1].timestamp else 0,
        reverse=True,
    ):
        if vehicle_id in seen_vehicle_ids:
            continue
        if not is_log_eligible_for_status_fallback(route, fallback_log, current_time=current_time):
            continue

        logger.info(
            "[Status] Using recent fallback log for route %s (%s) vehicle %s at %s",
            route.route_name,
            route.direction,
            vehicle_id,
            fallback_log.timestamp.isoformat() if fallback_log.timestamp else "unknown",
        )
        bus_list.append(build_status_bus_entry(
            route,
            vehicle_id,
            resolve_operator_for_vehicle(vehicle_id),
            fallback_log.bus_lat,
            fallback_log.bus_lng,
            fallback_log.timestamp,
            latest_log=latest_logs.get(vehicle_id, fallback_log),
        ))
        seen_vehicle_ids.add(vehicle_id)

    bus_list.sort(key=lambda bus: (
        bus["eta"] is None,
        bus["eta"] if bus["eta"] is not None else float("inf"),
        bus.get("vehicle_id") or "",
    ))
    return bus_list


@app.route("/api/status/<int:route_id>", methods=["GET"])
def get_status(route_id):
    """Return ALL buses for the route with their positions and ETAs."""
    route = db.session.get(Route, route_id)
    if not route:
        return jsonify({"error": "Route not found"}), 404

    latest_log = (
        BusLog.query
        .filter_by(route_id=route_id)
        .order_by(BusLog.timestamp.desc())
        .first()
    )

    live_snapshot = fetch_bods_vehicles_status_snapshot()
    bus_list = build_status_bus_list_from_live_snapshot(
        route,
        all_vehicles=live_snapshot,
        current_time=datetime.now(UK_TZ),
    )

    if not bus_list:
        if latest_log is None:
            return jsonify({"error": "No data yet for this route"}), 404

        if not is_recent_live_timestamp(latest_log.timestamp):
            return jsonify({
                "route": route.to_dict(),
                "bus_available": False,
                "is_live": False,
                "eta_method": "schedule_only",
                "message": "No live bus currently available on this route",
                "buses": [],
                "timestamp": latest_log.timestamp.isoformat() if latest_log.timestamp else None,
            }), 200

    if not bus_list:
        return jsonify({
            "route": route.to_dict(),
            "bus_available": False,
            "is_live": False,
            "eta_method": "schedule_only",
            "message": "No bus currently available on this route",
            "buses": [],
            "timestamp": latest_log.timestamp.isoformat() if latest_log and latest_log.timestamp else None,
        }), 200

    unique_eta_methods = sorted({bus.get("eta_method") for bus in bus_list if bus.get("eta_method")})
    overall_eta_method = unique_eta_methods[0] if len(unique_eta_methods) == 1 else "mixed"
    response_timestamp = max(
        (bus.get("timestamp") for bus in bus_list if bus.get("timestamp")),
        default=latest_log.timestamp.isoformat() if latest_log and latest_log.timestamp else None,
    )

    return jsonify({
        "route": route.to_dict(),
        "bus_available": True,
        "is_live": True,
        "eta_method": overall_eta_method,
        "bus_count": len(bus_list),
        "buses": bus_list,
        "timestamp": response_timestamp,
    })


# =========================================================================
# Entry Point
# =========================================================================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        logger.info("[Startup] Database ready")
        for route_name in sorted({route.route_name for route in Route.query.all() if route.route_name}):
            load_eta_model(route_name)
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
