"""
Transight — Database Seeder
Populates Route 72 with REAL Bristol stops from First Bus GTFS data.

Run: python seed.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from models import Route, Stop, RouteStop


def load_real_stops():
    """Load real Bristol Route 72 stops from extracted JSON."""
    json_path = os.path.join(os.path.dirname(__file__), 'bristol_route72_real.json')
    
    if not os.path.exists(json_path):
        print(f"[ERROR] Real stops file not found: {json_path}")
        print("[ERROR] Run extract_real_stops.py first!")
        return None, None
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    return data.get('outbound', []), data.get('inbound', [])


def seed():
    with app.app_context():
        print("[INFO] Recreating database tables...")
        db.drop_all()
        db.create_all()

        # Load real stops from GTFS
        outbound_stops, inbound_stops = load_real_stops()
        
        if not outbound_stops or not inbound_stops:
            print("[ERROR] Failed to load real stops!")
            return

        # Create routes with real data
        routes_data = [
            {
                "route_name": "72",
                "direction": "outbound",
                "origin_name": "Temple Meads Stn",
                "origin_lat": 51.44898,
                "origin_lng": -2.58262,
                "destination_name": "Frenchay Campus",
                "dest_lat": 51.50019,
                "dest_lng": -2.54622,
                "route_path": [[s['lat'], s['lng']] for s in outbound_stops],
                "typical_duration_min": 39.0,  # From GTFS baseline trip: 06:02 to 06:41
                "total_stops": len(outbound_stops),
            },
            {
                "route_name": "72",
                "direction": "inbound",
                "origin_name": "Frenchay Campus",
                "origin_lat": 51.50019,
                "origin_lng": -2.54622,
                "destination_name": "Temple Meads Stn",
                "dest_lat": 51.44898,
                "dest_lng": -2.58262,
                "route_path": [[s['lat'], s['lng']] for s in inbound_stops],
                "typical_duration_min": 37.0,  # From GTFS baseline trip: 05:15 to 05:52
                "total_stops": len(inbound_stops),
            },
        ]
        
        route_objects = {}
        for data in routes_data:
            route = Route(**data)
            db.session.add(route)
            db.session.flush()
            route_objects[data['direction']] = route
            print(f"[OK] Created Route {data['route_name']} ({data['direction']}): {data['total_stops']} stops")

        # Create outbound stops
        print(f"\n[INFO] Adding {len(outbound_stops)} outbound stops...")
        for stop_data in outbound_stops:
            stop = Stop(
                stop_id=stop_data['stop_id'],
                stop_name=stop_data['stop_name'],
                lat=stop_data['lat'],
                lng=stop_data['lng']
            )
            db.session.add(stop)
            db.session.flush()
            
            route_stop = RouteStop(
                route_id=route_objects['outbound'].id,
                stop_id=stop.id,
                sequence=stop_data['sequence'],
                scheduled_arrival=stop_data['arrival_time']
            )
            db.session.add(route_stop)

        # Create inbound stops
        print(f"[INFO] Adding {len(inbound_stops)} inbound stops...")
        for stop_data in inbound_stops:
            # Check if stop already exists (shared stops)
            existing = Stop.query.filter_by(stop_id=stop_data['stop_id']).first()
            if not existing:
                stop = Stop(
                    stop_id=stop_data['stop_id'],
                    stop_name=stop_data['stop_name'],
                    lat=stop_data['lat'],
                    lng=stop_data['lng']
                )
                db.session.add(stop)
                db.session.flush()
                stop_id_db = stop.id
            else:
                stop_id_db = existing.id
            
            route_stop = RouteStop(
                route_id=route_objects['inbound'].id,
                stop_id=stop_id_db,
                sequence=stop_data['sequence'],
                scheduled_arrival=stop_data['arrival_time']
            )
            db.session.add(route_stop)

        db.session.commit()
        
        print(f"\n[OK] Successfully seeded database:")
        print(f"  - {len(routes_data)} routes")
        print(f"  - {len(outbound_stops)} outbound stops (Temple Meads → Frenchay)")
        print(f"  - {len(inbound_stops)} inbound stops (Frenchay → Temple Meads)")
        
        print(f"\n[OK] Sample stops:")
        print(f"  Outbound: {outbound_stops[0]['stop_name']} → {outbound_stops[-1]['stop_name']}")
        print(f"  Inbound: {inbound_stops[0]['stop_name']} → {inbound_stops[-1]['stop_name']}")


if __name__ == "__main__":
    seed()
