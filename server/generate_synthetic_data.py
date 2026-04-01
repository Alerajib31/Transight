"""
Generate synthetic training data for XGBoost without consuming API limits.
Run: python generate_synthetic_data.py
"""

import random
from datetime import datetime, timedelta

from app import app, db
from models import BusLog, Route

def generate_synthetic_data(num_samples=200):
    """Generate realistic BusLog entries for model training."""

    with app.app_context():
        # Get existing routes
        routes = Route.query.all()
        if not routes:
            print("Error: No routes found. Run seed.py first!")
            return

        print(f"Generating {num_samples} synthetic samples...")

        # Delete existing logs (optional)
        BusLog.query.delete()
        db.session.commit()

        # Generate samples
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

            # Random timestamp (last 30 days)
            timestamp = datetime.now() - timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )

            # Realistic parameters
            hour = timestamp.hour
            is_rush_hour = (7 <= hour <= 9) or (17 <= hour <= 19)
            is_weekend = timestamp.weekday() >= 5

            # More passengers during rush hour
            passenger_count = random.randint(5, 25) if is_rush_hour else random.randint(0, 15)

            # More traffic during rush hour
            traffic_delay = random.uniform(30, 180) if is_rush_hour else random.uniform(0, 60)

            # Weekend patterns
            if is_weekend:
                passenger_count = int(passenger_count * 0.7)
                traffic_delay = traffic_delay * 0.5

            # Place the synthetic bus near a real stop on the route.
            bus_lat = current_stop.stop.lat + random.uniform(-0.0015, 0.0015)
            bus_lng = current_stop.stop.lng + random.uniform(-0.0015, 0.0015)

            # Build a target ETA that mirrors the live route-progress logic.
            typical_duration = route.typical_duration_min or 50.0
            remaining_route_min = typical_duration * (1 - progress_ratio)
            stop_delay_min = remaining_stops * random.uniform(0.35, 0.75)
            crowd_delay_min = (passenger_count * random.uniform(8, 14)) / 60.0
            traffic_delay_min = traffic_delay / 60.0
            noise = random.uniform(-2.5, 2.5)

            predicted_eta = max(
                0.5,
                (remaining_route_min * random.uniform(0.75, 1.05))
                + stop_delay_min
                + crowd_delay_min
                + traffic_delay_min
                + noise,
            )

            # Create log entry
            log = BusLog(
                route_id=route.id,
                bus_lat=bus_lat,
                bus_lng=bus_lng,
                passenger_count=passenger_count,
                traffic_delay=traffic_delay,
                predicted_eta=predicted_eta,
                timestamp=timestamp
            )
            db.session.add(log)

            if (i + 1) % 50 == 0:
                print(f"  Generated {i + 1}/{num_samples} samples...")

        db.session.commit()
        print(f"\n✅ Generated {num_samples} synthetic samples!")
        print(f"   Rush hour samples: {sum(1 for _ in range(num_samples) if (7 <= random.randint(0,23) <= 9))}")
        print(f"   Weekend samples: {sum(1 for _ in range(num_samples) if random.randint(0,6) >= 5)}")
        print("\nNext step: python train_xgboost.py")


if __name__ == "__main__":
    generate_synthetic_data(num_samples=200)
