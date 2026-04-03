"""
Transight — A1 Airport Flyer Route Seeder

Safe upsert: does NOT drop or recreate tables.
Run discover_a1.py first to confirm operator codes and agency_id.

Usage:
    python seed_a1.py [--confirm]

    --confirm   Required flag to actually write to the database.
                Without it, prints what would be inserted.
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from models import Route


# ---------------------------------------------------------------------------
# A1 Airport Flyer Configuration
# UPDATE THESE VALUES after running discover_a1.py
# ---------------------------------------------------------------------------

# BODS operator code for A1 Airport Flyer (First Bristol assumed; verify first)
A1_OPERATOR_CODE = "FBRI"

# GTFS agency_id for First Bristol in the South West GTFS feed (verify first)
# Set to None if only one agency uses "A1" route_short_name (collision-free)
A1_GTFS_AGENCY_ID = "OP736"  # Confirmed via discover_a1.py --gtfs-only

# A1 route geometry (Bristol City Centre -> Bristol Airport)
# Source: known coordinates; verify against map after seeding
A1_ROUTES = [
    {
        "route_name": "A1",
        "direction": "outbound",
        "origin_name": "Bristol Bus Station",
        "origin_lat": 51.45909,
        "origin_lng": -2.59294,
        "destination_name": "Bristol Airport",
        "dest_lat": 51.3827,
        "dest_lng": -2.7191,
        "route_path": [],          # loaded from GTFS stops after gtfs_loader.py runs
        "gtfs_trip_id": None,      # set after GTFS discovery
        "typical_duration_min": 40.0,
        "total_stops": None,       # set after GTFS loader runs
    },
    {
        "route_name": "A1",
        "direction": "inbound",
        "origin_name": "Bristol Airport",
        "origin_lat": 51.3827,
        "origin_lng": -2.7191,
        "destination_name": "Bristol Bus Station",
        "dest_lat": 51.45909,
        "dest_lng": -2.59294,
        "route_path": [],
        "gtfs_trip_id": None,
        "typical_duration_min": 45.0,
        "total_stops": None,
    },
]


def seed_a1(dry_run: bool = True) -> None:
    """
    Insert or update A1 Route rows. Safe to re-run.

    Args:
        dry_run: If True, print planned inserts without writing.
    """
    mode = "[DRY RUN] " if dry_run else ""

    with app.app_context():
        print(f"\n{mode}A1 Airport Flyer route seeding")
        print(f"{mode}Operator: {A1_OPERATOR_CODE}")
        print(f"{mode}GTFS agency_id: {A1_GTFS_AGENCY_ID or 'not set (auto-detect)'}")
        print()

        # Check existing Route 72 rows are present (sanity check)
        r72_count = Route.query.filter_by(route_name="72").count()
        if r72_count == 0:
            print("[WARNING] No Route 72 rows found. Make sure the database is seeded first.")
        else:
            print(f"Route 72 rows present: {r72_count} (will not be affected)")

        for data in A1_ROUTES:
            existing = Route.query.filter_by(
                route_name=data["route_name"],
                direction=data["direction"],
            ).first()

            if existing:
                print(f"{mode}UPDATE Route {data['route_name']} ({data['direction']}) "
                      f"id={existing.id}")
                if not dry_run:
                    for field, value in data.items():
                        if hasattr(existing, field) and value is not None:
                            setattr(existing, field, value)
            else:
                print(f"{mode}INSERT Route {data['route_name']} ({data['direction']}) — "
                      f"{data['origin_name']} -> {data['destination_name']}")
                if not dry_run:
                    route = Route(**data)
                    db.session.add(route)

        if not dry_run:
            db.session.commit()
            a1_count = Route.query.filter_by(route_name="A1").count()
            print(f"\nDone. A1 rows in database: {a1_count}")
            print("Next: run gtfs_loader.py --route A1 <path/to/gtfs.zip> to load stops.")
        else:
            print(f"\n[DRY RUN] Add --confirm flag to write to database.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed A1 Airport Flyer route rows")
    parser.add_argument(
        "--confirm",
        action="store_true",
        default=False,
        help="Actually write to the database (default: dry run)",
    )
    args = parser.parse_args()
    seed_a1(dry_run=not args.confirm)
