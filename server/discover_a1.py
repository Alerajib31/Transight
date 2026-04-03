"""
A1 Airport Flyer — Empirical Discovery Script

Run BEFORE seed_a1.py to confirm the actual BODS operator code, LineRef,
and GTFS agency_id for the A1 route.

Usage:
    BODS_API_KEY=<key> python discover_a1.py
    BODS_API_KEY=<key> python discover_a1.py --gtfs ../itm_south_west_gtfs.zip
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from bods_parser import fetch_bods_vehicles


BODS_API_KEY = os.getenv("BODS_API_KEY", "")
# Keywords to identify A1 Airport Flyer vehicles by destination name
A1_DESTINATION_KEYWORDS = ["airport", "flyer", "a1"]
# Common A1 line reference values to check in BODS data
A1_LINE_REFS = ["A1", "a1", "A1X", "A1x"]


def discover_bods_a1() -> None:
    """Fetch all BODS vehicles and identify those matching A1 Airport Flyer."""
    print("\n--- BODS Discovery: A1 Airport Flyer ---")

    if not BODS_API_KEY:
        print("[ERROR] BODS_API_KEY not set. Export it before running this script.")
        sys.exit(1)

    print("Fetching all BODS vehicles (no line_ref filter)...")
    try:
        all_vehicles = fetch_bods_vehicles(api_key=BODS_API_KEY)
    except Exception as exc:
        print(f"[ERROR] BODS fetch failed: {exc}")
        sys.exit(1)

    print(f"Total vehicles returned: {len(all_vehicles)}")

    # Match by destination name (case-insensitive) or line ref
    airport_vehicles = [
        v for v in all_vehicles
        if any(kw in (v.get("destination") or "").lower() for kw in A1_DESTINATION_KEYWORDS)
        or (v.get("line") or "").strip().upper() in [r.upper() for r in A1_LINE_REFS]
    ]

    print(f"\nVehicles matching A1/Airport Flyer: {len(airport_vehicles)}")

    if not airport_vehicles:
        print("\n[WARNING] No A1 vehicles found. Possible reasons:")
        print("  - No A1 buses currently in service (try during peak hours)")
        print("  - Operator code is not FBRI/FBRA — inspect raw output below")
        print("\nTop-10 destinations in BODS feed (to help identify A1):")
        from collections import Counter
        dests = Counter((v.get("destination") or "unknown").lower() for v in all_vehicles)
        for dest, count in dests.most_common(10):
            print(f"  {count:3d}x  {dest}")
        print("\nDistinct line refs in feed:")
        lines = sorted(set((v.get("line") or "").strip() for v in all_vehicles if v.get("line")))
        print("  ", ", ".join(lines[:40]))
    else:
        print("\nA1 vehicles found:")
        seen_operators = set()
        seen_lines = set()
        seen_directions = set()
        for v in airport_vehicles:
            op = v.get("operator") or "unknown"
            line = (v.get("line") or "").strip()
            direction = v.get("direction") or "unknown"
            dest = v.get("destination") or "unknown"
            seen_operators.add(op)
            seen_lines.add(line)
            seen_directions.add(direction)
            print(f"  vehicle={v.get('vehicle_id')}  line={line!r}  op={op!r}  "
                  f"dir={direction!r}  dest={dest!r}  "
                  f"pos=({v.get('lat', 0):.4f},{v.get('lng', 0):.4f})")

        print(f"\nSUMMARY:")
        print(f"  Distinct operator codes: {sorted(seen_operators)}")
        print(f"  Distinct line refs:      {sorted(seen_lines)}")
        print(f"  Distinct directions:     {sorted(seen_directions)}")
        print(f"\nACTION: Use these values in seed_a1.py and BODS_OPERATOR_ALLOWLIST.")


def discover_gtfs_a1(gtfs_zip: str) -> None:
    """Inspect GTFS zip to find A1 route_short_name and agency_id."""
    print(f"\n--- GTFS Discovery: A1 routes in {gtfs_zip} ---")

    if not os.path.exists(gtfs_zip):
        print(f"[ERROR] GTFS zip not found: {gtfs_zip}")
        return

    try:
        from gtfs_parser import parse_gtfs_zip
        print("Parsing GTFS zip (may take a few seconds)...")
        gtfs_data = parse_gtfs_zip(gtfs_zip)
    except Exception as exc:
        print(f"[ERROR] GTFS parse failed: {exc}")
        return

    routes_by_name = gtfs_data.get("routes_by_short_name", {})
    a1_routes = routes_by_name.get("A1", []) or routes_by_name.get("a1", [])

    print(f"\nRoutes with short_name 'A1': {len(a1_routes)}")

    if not a1_routes:
        print("[WARNING] No routes with route_short_name='A1' found.")
        print("Checking nearby names...")
        candidates = [name for name in routes_by_name if "a1" in name.lower() or "airport" in name.lower()]
        if candidates:
            print(f"  Potential matches: {candidates[:10]}")
        else:
            print("  No candidates found. Check the GTFS file manually.")
        return

    print("\nAll A1 entries (check agency_id to identify First Bristol):")
    seen_agencies = set()
    for r in a1_routes:
        agency = r.get("agency_id", "unknown")
        seen_agencies.add(agency)
        print(f"  route_id={r.get('route_id')!r}  agency_id={agency!r}  "
              f"long_name={r.get('route_long_name', '')!r}")

    print(f"\nDistinct agency_ids for 'A1': {sorted(seen_agencies)}")
    print(f"\nACTION: Use the First Bristol agency_id in seed_a1.py and gtfs_parser agency_id kwarg.")
    print(f"  If only one agency_id exists, collision risk is low.")
    print(f"  If multiple exist, pass the First Bristol one as agency_id to get_trip_candidates().")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discover A1 Airport Flyer identifiers in BODS and GTFS")
    parser.add_argument(
        "--gtfs",
        metavar="ZIP_PATH",
        default=os.path.join(os.path.dirname(__file__), "..", "itm_south_west_gtfs.zip"),
        help="Path to GTFS zip (default: ../itm_south_west_gtfs.zip)",
    )
    parser.add_argument(
        "--bods-only", action="store_true", help="Only run BODS discovery, skip GTFS"
    )
    parser.add_argument(
        "--gtfs-only", action="store_true", help="Only run GTFS discovery, skip BODS"
    )
    args = parser.parse_args()

    if not args.gtfs_only:
        discover_bods_a1()

    if not args.bods_only:
        discover_gtfs_a1(args.gtfs)

    print("\nDone. Record the operator codes and agency_id values, then run seed_a1.py.")
