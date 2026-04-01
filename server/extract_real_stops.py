"""Extract the earliest valid Bristol Route 72 trips from GTFS."""

import json
import os
from datetime import datetime

from gtfs_parser import get_cached_gtfs_data, select_next_route_trip

BASE_DIR = os.path.dirname(__file__)
GTFS_PATH = os.path.join(BASE_DIR, "..", "itm_south_west_gtfs.zip")
OUTPUT_PATH = os.path.join(BASE_DIR, "bristol_route72_real.json")


def serialize_trip(trip):
    """Convert a GTFS trip payload into the seed JSON shape."""
    return [
        {
            "stop_id": stop["stop_id"],
            "stop_name": stop["stop_name"],
            "lat": stop["lat"],
            "lng": stop["lng"],
            "arrival_time": stop["arrival_time"],
            "sequence": stop["sequence"],
        }
        for stop in trip["stops"]
    ]


def main():
    gtfs_data = get_cached_gtfs_data(GTFS_PATH)
    if not gtfs_data:
        raise FileNotFoundError(f"GTFS data not available at {GTFS_PATH}")

    reference_time = datetime(2026, 4, 1, 3, 15)

    outbound_trip = select_next_route_trip(
        gtfs_data,
        "72",
        "outbound",
        reference_time,
        origin_name="Temple Meads Stn",
        destination_name="Frenchay Campus",
    )
    inbound_trip = select_next_route_trip(
        gtfs_data,
        "72",
        "inbound",
        reference_time,
        origin_name="Frenchay Campus",
        destination_name="Temple Meads Stn",
    )

    if not outbound_trip or not inbound_trip:
        raise RuntimeError("Could not resolve both Route 72 baseline trips from GTFS")

    result = {
        "outbound": serialize_trip(outbound_trip),
        "inbound": serialize_trip(inbound_trip),
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    print(f"Saved Route 72 timetable to {OUTPUT_PATH}")
    print(f"Outbound starts {result['outbound'][0]['arrival_time']} at {result['outbound'][0]['stop_name']}")
    print(f"Inbound starts {result['inbound'][0]['arrival_time']} at {result['inbound'][0]['stop_name']}")


if __name__ == "__main__":
    main()
