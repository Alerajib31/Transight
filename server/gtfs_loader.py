"""
Load GTFS data into database.
Run: python gtfs_loader.py <path_to_gtfs.zip>
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from models import Stop, RouteStop, Route
from gtfs_parser import parse_gtfs_zip, get_stops_for_route

def load_gtfs(zip_path):
    """Load GTFS data from zip file into database."""

    print(f"[1/4] Parsing GTFS zip: {zip_path}")
    gtfs_data = parse_gtfs_zip(zip_path)

    with app.app_context():
        print("[2/4] Clearing existing GTFS data...")
        RouteStop.query.delete()
        Stop.query.delete()
        db.session.commit()

        print("[3/4] Loading stops...")
        stop_map = {}
        for stop_data in gtfs_data['stops']:
            stop = Stop(
                stop_id=stop_data['stop_id'],
                stop_name=stop_data['stop_name'],
                lat=stop_data['lat'],
                lng=stop_data['lng']
            )
            db.session.add(stop)
            stop_map[stop_data['stop_id']] = stop

        db.session.commit()
        print(f"✓ Loaded {len(stop_map)} stops")

        print("[4/4] Linking stops to routes...")
        routes = Route.query.all()

        for route in routes:
            stops = get_stops_for_route(
                gtfs_data,
                route.route_name,
                route.direction
            )

            if not stops:
                print(f"  ⚠ No stops found for Route {route.route_name} ({route.direction})")
                continue

            for stop_data in stops:
                if stop_data['stop_id'] in stop_map:
                    route_stop = RouteStop(
                        route_id=route.id,
                        stop_id=stop_map[stop_data['stop_id']].id,
                        sequence=stop_data['sequence'],
                        scheduled_arrival=stop_data.get('arrival_time')
                    )
                    db.session.add(route_stop)

            db.session.commit()
            print(f"  ✓ Route {route.route_name} ({route.direction}): {len(stops)} stops")

        print("\n✅ GTFS data loaded successfully!")
        print("\nNext steps:")
        print("  1. Upload your Bristol GTFS zip file to the project root")
        print("  2. Run: python server/gtfs_loader.py bristol_gtfs.zip")
        print("  3. Start the backend: python server/app.py")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gtfs_loader.py <path_to_gtfs.zip>")
        print("\nExample: python gtfs_loader.py ../bristol_buses_gtfs.zip")
        exit(1)

    zip_path = sys.argv[1]

    if not os.path.exists(zip_path):
        print(f"Error: File not found: {zip_path}")
        exit(1)

    load_gtfs(zip_path)
