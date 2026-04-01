"""
Generate synthetic Route 72 BusLog rows for XGBoost training.
Run: python generate_synthetic_data.py
"""

import argparse
import random
from datetime import datetime, timedelta

from app import app, db
from models import BusLog, Route


def format_service_time(value):
    """Convert HH:MM:SS timetable values to the HH:MM BusLog format."""
    if not value:
        return None

    parts = str(value).split(":")
    if len(parts) < 2:
        return None

    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"


def generate_synthetic_data(num_samples=10000):
    """Generate realistic Route 72 BusLog entries for model training."""
    with app.app_context():
        routes = (
            Route.query
            .filter_by(route_name="72")
            .order_by(Route.id)
            .all()
        )
        if not routes:
            print("Error: No Route 72 rows found. Run seed.py first!")
            return

        print(f"Generating {num_samples} Route 72 synthetic samples...")

        # Replace old synthetic history so the trainer sees a clean dataset.
        BusLog.query.delete()
        db.session.commit()

        rush_hour_samples = 0
        weekend_samples = 0

        for i in range(num_samples):
            route = random.choice(routes)
            route_stops = sorted(route.route_stops, key=lambda rs: rs.sequence)
            if not route_stops:
                continue

            current_stop = random.choice(route_stops)
            total_stops = route.total_stops or len(route_stops)
            current_stop_seq = current_stop.sequence
            remaining_stops = max(total_stops - current_stop_seq - 1, 0)
            progress_ratio = current_stop_seq / float(max(total_stops - 1, 1))

            timestamp = datetime.now() - timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )

            hour = timestamp.hour
            is_rush_hour = (7 <= hour <= 9) or (17 <= hour <= 19)
            is_weekend = timestamp.weekday() >= 5

            if is_rush_hour:
                rush_hour_samples += 1
            if is_weekend:
                weekend_samples += 1

            passenger_count = random.randint(5, 25) if is_rush_hour else random.randint(0, 15)
            traffic_delay = random.uniform(45, 240) if is_rush_hour else random.uniform(0, 90)

            if is_weekend:
                passenger_count = int(passenger_count * 0.7)
                traffic_delay *= 0.5

            # Place the synthetic bus near a real stop on the route.
            bus_lat = current_stop.stop.lat + random.uniform(-0.0015, 0.0015)
            bus_lng = current_stop.stop.lng + random.uniform(-0.0015, 0.0015)

            # Build the ETA target from travel time, traffic, passenger load,
            # remaining stops, and schedule deviation while keeping training
            # compatible with the current XGBoost feature columns.
            typical_duration = route.typical_duration_min or 50.0
            remaining_route_min = typical_duration * (1 - progress_ratio)
            base_travel_min = max(0.5, remaining_route_min * random.uniform(0.85, 1.10))
            stop_delay_min = remaining_stops * random.uniform(0.4, 0.8)
            crowd_delay_min = (passenger_count * random.uniform(8, 14)) / 60.0
            traffic_delay_min = traffic_delay / 60.0
            schedule_delay_min = random.uniform(0, 7) if is_rush_hour else random.uniform(0, 4)
            noise = random.uniform(-1.5, 1.5)

            predicted_eta = max(
                0.5,
                base_travel_min
                + stop_delay_min
                + crowd_delay_min
                + traffic_delay_min
                + schedule_delay_min
                + noise,
            )

            first_stop_time = route_stops[0].scheduled_arrival
            service_time = format_service_time(first_stop_time)
            delay_minutes = round(schedule_delay_min, 1)

            log = BusLog(
                route_id=route.id,
                vehicle_id=f"synthetic-{route.direction}-{(i % 20) + 1}",
                bus_lat=bus_lat,
                bus_lng=bus_lng,
                passenger_count=passenger_count,
                traffic_delay=traffic_delay,
                predicted_eta=predicted_eta,
                scheduled_service_time=service_time,
                delay_minutes=delay_minutes,
                timestamp=timestamp,
            )
            db.session.add(log)

            if (i + 1) % 1000 == 0:
                print(f"  Generated {i + 1}/{num_samples} samples...")

        db.session.commit()
        print(f"\nGenerated {num_samples} synthetic Route 72 samples.")
        print(f"  Rush hour samples: {rush_hour_samples}")
        print(f"  Weekend samples: {weekend_samples}")
        print("\nNext step: python train_xgboost.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic Route 72 training data.")
    parser.add_argument(
        "--rows",
        type=int,
        default=10000,
        help="Number of synthetic BusLog rows to generate (default: 10000).",
    )
    args = parser.parse_args()
    generate_synthetic_data(num_samples=args.rows)
