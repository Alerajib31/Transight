"""
Generate route-specific synthetic ETA training samples without mutating BusLog.
Run: python generate_synthetic_data.py --route 72
"""

import argparse
import logging
import random
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import func

from app import app, haversine
from models import Route

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("transight")

FEATURE_COLUMNS = [
    "passenger_count",
    "traffic_delay",
    "hour",
    "day_of_week",
    "current_stop_sequence",
    "remaining_stops",
    "total_stops",
    "progress_ratio",
]
DEFAULT_ROWS = 4000


def normalize_route_name(route_name):
    """Normalize a route name for file paths and case-insensitive lookups."""
    return (route_name or "").strip().lower()


def build_synthetic_training_dataframe(route_name, num_samples=DEFAULT_ROWS, seed=42):
    """Return synthetic training rows for a route as a pandas DataFrame."""
    normalized_route = normalize_route_name(route_name)
    rng = random.Random(seed)
    samples = []
    rush_hour_samples = 0
    weekend_samples = 0

    with app.app_context():
        routes = (
            Route.query
            .filter(func.lower(Route.route_name) == normalized_route)
            .order_by(Route.id)
            .all()
        )

        if not routes:
            raise ValueError(
                f"No routes found for route_name='{route_name}'. Seed/load the route first."
            )

        for _ in range(num_samples):
            route = rng.choice(routes)
            route_stops = sorted(route.route_stops, key=lambda rs: rs.sequence)
            if not route_stops:
                continue

            current_stop = rng.choice(route_stops)
            total_stops = route.total_stops or len(route_stops)
            current_stop_seq = min(max(current_stop.sequence, 0), max(total_stops - 1, 0))
            remaining_stops = max(total_stops - current_stop_seq - 1, 0)
            progress_ratio = current_stop_seq / float(max(total_stops - 1, 1))

            timestamp = datetime.now() - timedelta(
                days=rng.randint(0, 45),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )
            hour = timestamp.hour
            day_of_week = timestamp.weekday()
            is_rush_hour = (7 <= hour <= 9) or (16 <= hour <= 18)
            is_weekend = day_of_week >= 5

            if is_rush_hour:
                rush_hour_samples += 1
            if is_weekend:
                weekend_samples += 1

            typical_duration = route.typical_duration_min or max(20.0, total_stops * 1.8)
            duration_scale = min(max(typical_duration / 55.0, 0.75), 1.60)
            route_distance_km = max(
                haversine(route.origin_lat, route.origin_lng, route.dest_lat, route.dest_lng),
                1.0,
            )
            remaining_distance_km = max(
                haversine(
                    current_stop.stop.lat,
                    current_stop.stop.lng,
                    route.dest_lat,
                    route.dest_lng,
                ),
                0.15,
            )
            distance_ratio = min(remaining_distance_km / route_distance_km, 1.15)
            remaining_ratio = max(0.05, ((1 - progress_ratio) * 0.6) + (distance_ratio * 0.4))

            if normalized_route == "a1":
                passenger_low, passenger_high = (2, 18)
                rush_passenger_bonus = (5, 10)
                traffic_base = (15, 80)
                traffic_rush = (60, 220)
                stop_delay_bounds = (0.25, 0.55)
            else:
                passenger_low, passenger_high = (0, 16)
                rush_passenger_bonus = (6, 12)
                traffic_base = (10, 110)
                traffic_rush = (70, 260)
                stop_delay_bounds = (0.35, 0.75)

            passenger_count = rng.randint(passenger_low, passenger_high)
            if is_rush_hour:
                passenger_count += rng.randint(*rush_passenger_bonus)
                traffic_delay = rng.uniform(*traffic_rush) * duration_scale
            else:
                traffic_delay = rng.uniform(*traffic_base) * duration_scale

            if is_weekend:
                passenger_count = max(0, int(passenger_count * 0.8))
                traffic_delay *= 0.8

            base_travel_min = typical_duration * remaining_ratio * rng.uniform(0.88, 1.12)
            stop_delay_min = remaining_stops * rng.uniform(*stop_delay_bounds)
            crowd_delay_min = (passenger_count * rng.uniform(8, 14)) / 60.0
            traffic_delay_min = (traffic_delay / 60.0) * rng.uniform(0.9, 1.15)
            schedule_delay_min = (
                rng.uniform(0.5, 6.5) if is_rush_hour else rng.uniform(0.0, 3.5)
            )
            noise = rng.uniform(-1.0, 1.0)

            predicted_eta = max(
                0.5,
                min(
                    typical_duration * 1.75,
                    base_travel_min
                    + stop_delay_min
                    + crowd_delay_min
                    + traffic_delay_min
                    + schedule_delay_min
                    + noise,
                ),
            )

            samples.append({
                "route_name": route.route_name,
                "direction": route.direction,
                "source": "synthetic",
                "passenger_count": passenger_count,
                "traffic_delay": round(traffic_delay, 2),
                "hour": hour,
                "day_of_week": day_of_week,
                "current_stop_sequence": current_stop_seq,
                "remaining_stops": remaining_stops,
                "total_stops": total_stops,
                "progress_ratio": round(progress_ratio, 6),
                "predicted_eta": round(predicted_eta, 3),
            })

    df = pd.DataFrame(samples)
    logger.info(
        "[Synthetic] Generated %s in-memory sample(s) for route %s across %s direction(s)",
        len(df),
        route_name,
        len({route.direction for route in routes}),
    )
    logger.info(
        "[Synthetic] Rush-hour=%s Weekend=%s ETA range=%.1f..%.1f min",
        rush_hour_samples,
        weekend_samples,
        float(df["predicted_eta"].min()) if not df.empty else 0.0,
        float(df["predicted_eta"].max()) if not df.empty else 0.0,
    )
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate route-specific synthetic ETA samples without mutating BusLog."
    )
    parser.add_argument(
        "--route",
        required=True,
        help="Route short name to synthesize, for example 72 or A1.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_ROWS,
        help=f"Number of synthetic rows to build in memory (default: {DEFAULT_ROWS}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for repeatable synthetic generation.",
    )
    args = parser.parse_args()

    dataframe = build_synthetic_training_dataframe(
        route_name=args.route,
        num_samples=args.rows,
        seed=args.seed,
    )
    logger.info(
        "[Synthetic] Completed preview build for route %s with %s rows",
        args.route,
        len(dataframe),
    )
