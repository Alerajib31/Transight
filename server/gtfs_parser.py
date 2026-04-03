"""
GTFS Parser for Bristol bus timetables.

Provides helpers for selecting the next scheduled trip and the live trip
closest to the current bus position/time.
"""

import io
import os
import zipfile
import csv
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import lru_cache
import logging

logger = logging.getLogger("transight")

def parse_gtfs_zip(zip_path):
    """
    Parse GTFS zip file and extract relevant data.

    Returns dict with:
    - stops: List of {stop_id, stop_name, lat, lng}
    - routes: List of {route_id, route_short_name, route_long_name}
    - stop_times: List of {trip_id, stop_id, arrival_time, stop_sequence}
    - trips: List of {trip_id, route_id, service_id, direction_id}
    - calendar: Dict of {service_id: calendar_row}
    - calendar_dates: Dict of {service_id: {YYYYMMDD: exception_type}}
    """
    data = {
        'stops': [],
        'routes': [],
        'stop_times': [],
        'trips': [],
        'calendar': {},
        'calendar_dates': {},
        'stop_lookup': {},
        'routes_by_short_name': defaultdict(list),
        'trips_by_route_direction': defaultdict(list),
        'stop_times_by_trip': defaultdict(list),
    }

    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Parse stops.txt
        if 'stops.txt' in zf.namelist():
            with zf.open('stops.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    stop = {
                        'stop_id': row['stop_id'],
                        'stop_name': row['stop_name'],
                        'lat': float(row['stop_lat']),
                        'lng': float(row['stop_lon'])
                    }
                    data['stops'].append(stop)
                    data['stop_lookup'][stop['stop_id']] = stop
            logger.info(f"[GTFS] Loaded {len(data['stops'])} stops")

        # Parse routes.txt
        if 'routes.txt' in zf.namelist():
            with zf.open('routes.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    route = {
                        'route_id': row['route_id'],
                        'route_short_name': row['route_short_name'],
                        'route_long_name': row.get('route_long_name', ''),
                        'agency_id': row.get('agency_id', ''),
                    }
                    data['routes'].append(route)
                    data['routes_by_short_name'][route['route_short_name']].append(route)
            logger.info(f"[GTFS] Loaded {len(data['routes'])} routes")

        # Parse trips.txt
        if 'trips.txt' in zf.namelist():
            with zf.open('trips.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    trip = {
                        'trip_id': row['trip_id'],
                        'route_id': row['route_id'],
                        'service_id': row['service_id'],
                        'direction_id': row.get('direction_id', '0')
                    }
                    data['trips'].append(trip)
                    data['trips_by_route_direction'][(trip['route_id'], trip['direction_id'])].append(trip)
            logger.info(f"[GTFS] Loaded {len(data['trips'])} trips")

        # Parse stop_times.txt
        if 'stop_times.txt' in zf.namelist():
            with zf.open('stop_times.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    stop_time = {
                        'trip_id': row['trip_id'],
                        'stop_id': row['stop_id'],
                        'arrival_time': row['arrival_time'],
                        'departure_time': row['departure_time'],
                        'stop_sequence': int(row['stop_sequence'])
                    }
                    data['stop_times'].append(stop_time)
                    data['stop_times_by_trip'][stop_time['trip_id']].append(stop_time)
            logger.info(f"[GTFS] Loaded {len(data['stop_times'])} stop times")

        if 'calendar.txt' in zf.namelist():
            with zf.open('calendar.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    data['calendar'][row['service_id']] = row
            logger.info(f"[GTFS] Loaded {len(data['calendar'])} calendar rows")

        if 'calendar_dates.txt' in zf.namelist():
            with zf.open('calendar_dates.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    service_id = row['service_id']
                    if service_id not in data['calendar_dates']:
                        data['calendar_dates'][service_id] = {}
                    data['calendar_dates'][service_id][row['date']] = row['exception_type']
            logger.info(f"[GTFS] Loaded {len(data['calendar_dates'])} calendar exception groups")

    for trip_id in data['stop_times_by_trip']:
        data['stop_times_by_trip'][trip_id].sort(key=lambda item: item["stop_sequence"])

    return data


@lru_cache(maxsize=4)
def _cached_gtfs(zip_path, mtime):
    return parse_gtfs_zip(zip_path)


def get_cached_gtfs_data(zip_path):
    """Load and cache GTFS data, refreshing when the zip file changes."""
    try:
        mtime = os.path.getmtime(zip_path)
    except OSError:
        return None

    return _cached_gtfs(zip_path, mtime)


def parse_gtfs_time(value):
    """Parse a GTFS HH:MM:SS string into hour/minute/second."""
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


def gtfs_time_to_seconds(value):
    """Convert GTFS HH:MM[:SS] to seconds since midnight."""
    parsed = parse_gtfs_time(value)
    if not parsed:
        return None

    hour, minute, second = parsed
    return (hour * 3600) + (minute * 60) + second


def build_gtfs_datetime(service_date, value):
    """Build a datetime from a GTFS time, preserving >24 hour rollover."""
    parsed = parse_gtfs_time(value)
    if not parsed:
        return None

    hour, minute, second = parsed
    day_offset, hour = divmod(hour, 24)
    return datetime.combine(service_date, datetime.min.time()) + timedelta(
        days=day_offset,
        hours=hour,
        minutes=minute,
        seconds=second,
    )


def normalize_name(value):
    """Normalize a stop or route name for loose matching."""
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def names_match(expected, actual):
    """Return True when two stop names are close enough to be the same stop."""
    expected_norm = normalize_name(expected)
    actual_norm = normalize_name(actual)
    if not expected_norm or not actual_norm:
        return False
    return expected_norm in actual_norm or actual_norm in expected_norm


def haversine_km(lat1, lng1, lat2, lng2):
    """Return the great-circle distance between two points in kilometres."""
    radius_km = 6371.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def endpoint_matches(expected_name=None, actual_name=None,
                     expected_lat=None, expected_lng=None,
                     actual_lat=None, actual_lng=None,
                     max_distance_km=1.5):
    """Match route endpoints by name first, then by coordinate proximity."""
    if expected_name and actual_name and names_match(expected_name, actual_name):
        return True

    if None not in (expected_lat, expected_lng, actual_lat, actual_lng):
        return haversine_km(expected_lat, expected_lng, actual_lat, actual_lng) <= max_distance_km

    return not any(value is not None for value in (expected_name, expected_lat, expected_lng))


def is_service_active(gtfs_data, service_id, target_date):
    """Check whether a GTFS service_id is active on a given date."""
    date_key = target_date.strftime("%Y%m%d")
    exceptions = gtfs_data.get("calendar_dates", {}).get(service_id, {})
    if date_key in exceptions:
        return exceptions[date_key] == "1"

    calendar_row = gtfs_data.get("calendar", {}).get(service_id)
    if not calendar_row:
        return False

    if not (calendar_row["start_date"] <= date_key <= calendar_row["end_date"]):
        return False

    weekday_key = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ][target_date.weekday()]
    return calendar_row.get(weekday_key) == "1"


def build_trip_payload(trip, trip_stop_times, stop_lookup, service_date):
    """Construct a trip payload with stop metadata and datetimes."""
    if not trip_stop_times:
        return None

    stops = []
    for stop_time in trip_stop_times:
        stop_info = stop_lookup.get(stop_time["stop_id"])
        if not stop_info:
            continue

        stops.append({
            "stop_id": stop_info["stop_id"],
            "stop_name": stop_info["stop_name"],
            "lat": stop_info["lat"],
            "lng": stop_info["lng"],
            "sequence": max(0, stop_time["stop_sequence"] - 1),
            "arrival_time": stop_time["arrival_time"],
            "departure_time": stop_time.get("departure_time") or stop_time["arrival_time"],
        })

    if not stops:
        return None

    first_departure_dt = build_gtfs_datetime(service_date, stops[0]["departure_time"])
    last_arrival_dt = build_gtfs_datetime(service_date, stops[-1]["arrival_time"])
    if first_departure_dt is None or last_arrival_dt is None:
        return None

    return {
        "trip_id": trip["trip_id"],
        "service_id": trip["service_id"],
        "route_id": trip["route_id"],
        "direction_id": trip["direction_id"],
        "service_date": service_date,
        "first_departure_dt": first_departure_dt,
        "last_arrival_dt": last_arrival_dt,
        "service_time": stops[0]["arrival_time"],
        "stops": stops,
    }


def get_trip_candidates(gtfs_data, route_name, direction, service_date,
                        origin_name=None, destination_name=None,
                        origin_lat=None, origin_lng=None,
                        destination_lat=None, destination_lng=None,
                        agency_id=None):
    """Return active trip candidates for a route/direction on a specific date."""
    preferred_direction_id = '0' if direction == 'outbound' else '1'
    direction_ids = [preferred_direction_id]
    if origin_name or destination_name:
        alternate_direction_id = '1' if preferred_direction_id == '0' else '0'
        direction_ids.append(alternate_direction_id)
    stop_lookup = gtfs_data.get("stop_lookup", {})
    stop_times_by_trip = gtfs_data.get("stop_times_by_trip", {})

    matching_routes = list(gtfs_data.get("routes_by_short_name", {}).get(route_name, []))
    if not matching_routes:
        return []

    if agency_id is not None:
        before_count = len(matching_routes)
        matching_routes = [r for r in matching_routes if r.get("agency_id") == agency_id]
        logger.info(
            f"[GTFS] agency_id filter '{agency_id}' for route '{route_name}': "
            f"{before_count} -> {len(matching_routes)} matching routes"
        )
        if not matching_routes:
            logger.warning(
                f"[GTFS] No routes found for route_short_name='{route_name}' "
                f"with agency_id='{agency_id}'. "
                f"Check agency_id value against routes.txt in the GTFS zip."
            )
            return []

    route_ids = {route["route_id"] for route in matching_routes}
    candidate_trips = []
    route_direction_index = gtfs_data.get("trips_by_route_direction", {})
    seen_trip_ids = set()
    for route_id in route_ids:
        for direction_id in direction_ids:
            for trip in route_direction_index.get((route_id, direction_id), []):
                trip_id = trip["trip_id"]
                if trip_id in seen_trip_ids:
                    continue
                if is_service_active(gtfs_data, trip["service_id"], service_date):
                    candidate_trips.append(trip)
                    seen_trip_ids.add(trip_id)

    payloads = []
    fallback_payloads = []
    for trip in candidate_trips:
        payload = build_trip_payload(
            trip,
            stop_times_by_trip.get(trip["trip_id"], []),
            stop_lookup,
            service_date,
        )
        if not payload:
            continue

        fallback_payloads.append(payload)
        first_stop_name = payload["stops"][0]["stop_name"]
        last_stop_name = payload["stops"][-1]["stop_name"]
        first_stop = payload["stops"][0]
        last_stop = payload["stops"][-1]

        if not endpoint_matches(
            expected_name=origin_name,
            actual_name=first_stop_name,
            expected_lat=origin_lat,
            expected_lng=origin_lng,
            actual_lat=first_stop["lat"],
            actual_lng=first_stop["lng"],
        ):
            continue
        if not endpoint_matches(
            expected_name=destination_name,
            actual_name=last_stop_name,
            expected_lat=destination_lat,
            expected_lng=destination_lng,
            actual_lat=last_stop["lat"],
            actual_lng=last_stop["lng"],
        ):
            continue
        payloads.append(payload)

    return payloads or fallback_payloads


def select_next_route_trip(gtfs_data, route_name, direction, reference_time,
                           origin_name=None, destination_name=None,
                           origin_lat=None, origin_lng=None,
                           destination_lat=None, destination_lng=None,
                           lookahead_days=7):
    """Select the next valid scheduled trip for the given route and local time."""
    local_reference = reference_time.replace(tzinfo=None) if reference_time.tzinfo else reference_time

    for day_offset in range(lookahead_days + 1):
        service_date = local_reference.date() + timedelta(days=day_offset)
        candidates = get_trip_candidates(
            gtfs_data,
            route_name,
            direction,
            service_date,
            origin_name=origin_name,
            destination_name=destination_name,
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            destination_lat=destination_lat,
            destination_lng=destination_lng,
        )
        if not candidates:
            continue

        if day_offset == 0:
            candidates = [
                trip for trip in candidates
                if trip["first_departure_dt"] >= local_reference
            ]
            if not candidates:
                continue

        candidates.sort(key=lambda trip: (trip["first_departure_dt"], trip["trip_id"]))
        return candidates[0]

    return None


def select_live_route_trip(gtfs_data, route_name, direction, reference_time,
                           current_stop_sequence, origin_name=None, destination_name=None,
                           origin_lat=None, origin_lng=None,
                           destination_lat=None, destination_lng=None):
    """Select the active trip whose current-stop schedule best matches the given time."""
    local_reference = reference_time.replace(tzinfo=None) if reference_time.tzinfo else reference_time
    service_date = local_reference.date()
    candidates = get_trip_candidates(
        gtfs_data,
        route_name,
        direction,
        service_date,
        origin_name=origin_name,
        destination_name=destination_name,
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        destination_lat=destination_lat,
        destination_lng=destination_lng,
    )
    if not candidates:
        return None

    best_trip = None
    best_delta = None

    for trip in candidates:
        if current_stop_sequence < 0 or current_stop_sequence >= len(trip["stops"]):
            continue

        stop = trip["stops"][current_stop_sequence]
        scheduled_dt = build_gtfs_datetime(service_date, stop["arrival_time"])
        if scheduled_dt is None:
            continue

        delta_seconds = abs((local_reference - scheduled_dt).total_seconds())
        if best_delta is None or delta_seconds < best_delta:
            best_delta = delta_seconds
            best_trip = trip

    return best_trip


def get_stops_for_route(gtfs_data, route_short_name, direction,
                        origin_name=None, destination_name=None,
                        origin_lat=None, origin_lng=None,
                        destination_lat=None, destination_lng=None):
    """
    Get ordered list of stops for a specific route and direction.

    Args:
        gtfs_data: Parsed GTFS data
        route_short_name: Route number (e.g., "72")
        direction: "outbound" or "inbound" (maps to direction_id 0/1)

    Returns:
        List of stops in order with {stop_id, stop_name, lat, lng, sequence}
    """
    service_date = date.today()
    candidates = get_trip_candidates(
        gtfs_data,
        route_short_name,
        direction,
        service_date,
        origin_name=origin_name,
        destination_name=destination_name,
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        destination_lat=destination_lat,
        destination_lng=destination_lng,
    )
    if not candidates:
        return []

    trip = candidates[0]
    return [
        {
            "stop_id": stop["stop_id"],
            "stop_name": stop["stop_name"],
            "lat": stop["lat"],
            "lng": stop["lng"],
            "sequence": stop["sequence"],
            "arrival_time": stop["arrival_time"],
        }
        for stop in trip["stops"]
    ]
