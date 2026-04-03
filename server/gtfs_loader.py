"""
Load GTFS data into database.

Usage:
    python gtfs_loader.py <path_to_gtfs.zip>                     # load all routes (legacy)
    python gtfs_loader.py <path_to_gtfs.zip> --route A1          # load stops for A1 only
    python gtfs_loader.py <path_to_gtfs.zip> --route A1 --dry-run  # preview without writing
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from models import Stop, RouteStop, Route
from gtfs_parser import parse_gtfs_zip, get_stops_for_route


def load_gtfs(zip_path: str, route_filter=None, dry_run: bool = False) -> None:
    """
    Load GTFS stop data into the database.

    Args:
        zip_path:      Path to the GTFS zip file.
        route_filter:  If supplied, only load/delete stops for this route_name.
                       Route 72 records are untouched when route_filter='A1'.
        dry_run:       If True, print actions without writing to the database.
    """
    mode = "[DRY RUN] " if dry_run else ""
    print(f"{mode}[1/4] Parsing GTFS zip: {zip_path}")
    gtfs_data = parse_gtfs_zip(zip_path)

    with app.app_context():
        # Determine which Route rows to process
        if route_filter:
            routes = Route.query.filter_by(route_name=route_filter).all()
            if not routes:
                print(f"[ERROR] No routes found in database with route_name='{route_filter}'")
                print("[ERROR] Seed the Route rows first (e.g. via seed_a1.py) before loading GTFS stops.")
                sys.exit(1)
        else:
            routes = Route.query.all()

        print(f"{mode}[2/4] Clearing GTFS data for: {', '.join(f'{r.route_name} ({r.direction})' for r in routes)}")

        if not dry_run:
            # Scoped delete: only remove RouteStop rows for the target routes
            for route in routes:
                deleted = RouteStop.query.filter_by(route_id=route.id).delete()
                print(f"  Deleted {deleted} RouteStop rows for route {route.route_name} ({route.direction})")

            if not route_filter:
                # Full reload: also wipe Stop rows (safe only when reloading all routes)
                stop_count = Stop.query.count()
                Stop.query.delete()
                print(f"  Deleted {stop_count} Stop rows (full reload)")

            db.session.commit()
        else:
            for route in routes:
                count = RouteStop.query.filter_by(route_id=route.id).count()
                print(f"  Would delete {count} RouteStop rows for {route.route_name} ({route.direction})")

        print(f"{mode}[3/4] Loading stops from GTFS...")
        stop_map = {}

        if not route_filter:
            # Full reload: insert all stops from GTFS
            for stop_data in gtfs_data['stops']:
                if not dry_run:
                    existing = Stop.query.filter_by(stop_id=stop_data['stop_id']).first()
                    if not existing:
                        stop = Stop(
                            stop_id=stop_data['stop_id'],
                            stop_name=stop_data['stop_name'],
                            lat=stop_data['lat'],
                            lng=stop_data['lng'],
                        )
                        db.session.add(stop)
                        stop_map[stop_data['stop_id']] = stop
                    else:
                        stop_map[stop_data['stop_id']] = existing
                else:
                    stop_map[stop_data['stop_id']] = stop_data  # placeholder

            if not dry_run:
                db.session.commit()
            print(f"{mode}  Loaded {len(stop_map)} stops")
        else:
            # Scoped reload: upsert only the stops used by the target routes
            print(f"  Scoped load: stops will be upserted per-route below")

        print(f"{mode}[4/4] Linking stops to routes...")

        for route in routes:
            stops = get_stops_for_route(
                gtfs_data,
                route.route_name,
                route.direction,
                origin_name=route.origin_name,
                destination_name=route.destination_name,
                origin_lat=route.origin_lat,
                origin_lng=route.origin_lng,
                destination_lat=route.dest_lat,
                destination_lng=route.dest_lng,
            )

            if not stops:
                print(f"  WARNING: No stops found for {route.route_name} ({route.direction})")
                continue

            print(f"  {mode}{route.route_name} ({route.direction}): {len(stops)} stops")

            if not dry_run:
                route.total_stops = len(stops)
                route.route_path = [[stop["lat"], stop["lng"]] for stop in stops]

                for stop_data in stops:
                    # Upsert the Stop record
                    existing = Stop.query.filter_by(stop_id=stop_data['stop_id']).first()
                    if existing:
                        db_stop = existing
                    else:
                        db_stop = Stop(
                            stop_id=stop_data['stop_id'],
                            stop_name=stop_data['stop_name'],
                            lat=stop_data['lat'],
                            lng=stop_data['lng'],
                        )
                        db.session.add(db_stop)
                        db.session.flush()

                    route_stop = RouteStop(
                        route_id=route.id,
                        stop_id=db_stop.id,
                        sequence=stop_data['sequence'],
                        scheduled_arrival=stop_data.get('arrival_time'),
                    )
                    db.session.add(route_stop)

                db.session.commit()
                print(f"  OK: {route.route_name} ({route.direction}) linked {len(stops)} stops")

        if dry_run:
            print(f"\n[DRY RUN] No changes written. Remove --dry-run to apply.")
        else:
            print(f"\nGTFS data loaded successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load GTFS stop data into Transight database")
    parser.add_argument("zip_path", help="Path to GTFS zip file")
    parser.add_argument(
        "--route",
        metavar="ROUTE_NAME",
        default=None,
        help="Only load stops for this route name (e.g. A1). Leaves other routes untouched.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview what would be loaded without writing to the database.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.zip_path):
        print(f"Error: File not found: {args.zip_path}")
        sys.exit(1)

    load_gtfs(args.zip_path, route_filter=args.route, dry_run=args.dry_run)
