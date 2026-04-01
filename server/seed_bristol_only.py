"""
Transight — Database Seeder for Bristol Route 72 Only
Loads only Bristol-specific GTFS data.

Run: python seed_bristol_only.py
"""

import os
import sys
import zipfile
import io
import csv

sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from models import Route, Stop, RouteStop


def parse_bristol_gtfs(zip_path):
    """Parse GTFS and filter for Bristol Route 72 only."""
    data = {'stops': {}, 'routes': {}, 'trips': {}, 'stop_times': []}
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Parse routes - look for Route 72 in Bristol
        if 'routes.txt' in zf.namelist():
            with zf.open('routes.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    if row['route_short_name'] == '72':
                        # Check if it's a Bristol route (by agency or route name)
                        route_long = row.get('route_long_name', '').lower()
                        agency_id = row.get('agency_id', '')
                        # First Bus Bristol agency ID is typically 'FBRI' or similar
                        data['routes'][row['route_id']] = {
                            'route_id': row['route_id'],
                            'route_short_name': row['route_short_name'],
                            'route_long_name': row.get('route_long_name', ''),
                            'agency_id': agency_id
                        }
            print(f"[GTFS] Found {len(data['routes'])} Route 72 entries")
            
            # Print all Route 72s to help identify Bristol
            for rid, rdata in data['routes'].items():
                print(f"  - {rid}: {rdata['route_long_name']} (Agency: {rdata['agency_id']})")
        
        # Parse trips
        if 'trips.txt' in zf.namelist():
            with zf.open('trips.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    if row['route_id'] in data['routes']:
                        trip_id = row['trip_id']
                        data['trips'][trip_id] = {
                            'trip_id': trip_id,
                            'route_id': row['route_id'],
                            'direction_id': row.get('direction_id', '0'),
                            'service_id': row['service_id']
                        }
            print(f"[GTFS] Found {len(data['trips'])} trips for Route 72")
        
        # Parse stop times
        if 'stop_times.txt' in zf.namelist():
            with zf.open('stop_times.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    if row['trip_id'] in data['trips']:
                        data['stop_times'].append({
                            'trip_id': row['trip_id'],
                            'stop_id': row['stop_id'],
                            'arrival_time': row['arrival_time'],
                            'stop_sequence': int(row['stop_sequence'])
                        })
            print(f"[GTFS] Found {len(data['stop_times'])} stop times")
        
        # Parse stops - only those used by Route 72
        used_stop_ids = set(st['stop_id'] for st in data['stop_times'])
        if 'stops.txt' in zf.namelist():
            with zf.open('stops.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    if row['stop_id'] in used_stop_ids:
                        data['stops'][row['stop_id']] = {
                            'stop_id': row['stop_id'],
                            'stop_name': row['stop_name'],
                            'lat': float(row['stop_lat']),
                            'lng': float(row['stop_lon'])
                        }
            print(f"[GTFS] Found {len(data['stops'])} unique stops")
    
    return data


def get_stops_for_trip(data, trip_id):
    """Get ordered stops for a specific trip."""
    stop_times = sorted(
        [st for st in data['stop_times'] if st['trip_id'] == trip_id],
        key=lambda x: x['stop_sequence']
    )
    
    stops = []
    for st in stop_times:
        stop_info = data['stops'].get(st['stop_id'])
        if stop_info:
            stops.append({
                **stop_info,
                'sequence': st['stop_sequence'] - 1,  # 0-indexed
                'arrival_time': st['arrival_time']
            })
    return stops


def seed():
    """Seed database with Bristol Route 72 only."""
    with app.app_context():
        print("[INFO] Recreating database tables...")
        db.drop_all()
        db.create_all()

        # Create routes
        routes_data = [
            {
                "route_name": "72",
                "direction": "outbound",
                "origin_name": "Temple Meads Station",
                "origin_lat": 51.4490,
                "origin_lng": -2.5810,
                "destination_name": "UWE Frenchay Campus",
                "dest_lat": 51.5000,
                "dest_lng": -2.5470,
                "route_path": [
                    [51.4490, -2.5810],
                    [51.4550, -2.5830],
                    [51.4580, -2.5870],
                    [51.4620, -2.5750],
                    [51.4680, -2.5650],
                    [51.4750, -2.5580],
                    [51.4850, -2.5520],
                    [51.4950, -2.5480],
                    [51.5000, -2.5470],
                ],
                "typical_duration_min": 56.0,
                "total_stops": 31,
            },
            {
                "route_name": "72",
                "direction": "inbound",
                "origin_name": "UWE Frenchay Campus",
                "origin_lat": 51.5000,
                "origin_lng": -2.5470,
                "destination_name": "Temple Meads Station",
                "dest_lat": 51.4490,
                "dest_lng": -2.5810,
                "route_path": [
                    [51.5000, -2.5470],
                    [51.4950, -2.5480],
                    [51.4850, -2.5520],
                    [51.4750, -2.5580],
                    [51.4680, -2.5650],
                    [51.4620, -2.5750],
                    [51.4580, -2.5870],
                    [51.4550, -2.5830],
                    [51.4490, -2.5810],
                ],
                "typical_duration_min": 56.0,
                "total_stops": 28,
            },
        ]
        
        route_objects = {}
        for data in routes_data:
            route = Route(**data)
            db.session.add(route)
            db.session.flush()
            route_objects[data['direction']] = route
            print(f"[OK] Created Route {data['route_name']} ({data['direction']})")

        # Load GTFS data
        gtfs_path = os.path.join(os.path.dirname(__file__), '..', 'itm_south_west_gtfs.zip')
        if not os.path.exists(gtfs_path):
            print(f"[ERROR] GTFS file not found: {gtfs_path}")
            db.session.commit()
            return

        print(f"\n[INFO] Loading GTFS data...")
        gtfs_data = parse_bristol_gtfs(gtfs_path)
        
        if not gtfs_data['routes']:
            print("[ERROR] No Route 72 found in GTFS!")
            db.session.commit()
            return
        
        # Let user select which Route 72 to use (or auto-select Bristol)
        bristol_route_id = None
        for rid, rdata in gtfs_data['routes'].items():
            if 'bristol' in rdata['route_long_name'].lower() or 'uwe' in rdata['route_long_name'].lower():
                bristol_route_id = rid
                print(f"\n[OK] Selected Bristol Route 72: {rid} - {rdata['route_long_name']}")
                break
        
        if not bristol_route_id:
            # Default to first Route 72
            bristol_route_id = list(gtfs_data['routes'].keys())[0]
            print(f"\n[WARNING] Could not identify Bristol route, using: {bristol_route_id}")
        
        # Get trips for this route
        trips = [t for t in gtfs_data['trips'].values() if t['route_id'] == bristol_route_id]
        
        # Separate by direction
        outbound_trips = [t for t in trips if t['direction_id'] == '0']
        inbound_trips = [t for t in trips if t['direction_id'] == '1']
        
        print(f"\n[INFO] Found {len(outbound_trips)} outbound trips, {len(inbound_trips)} inbound trips")
        
        # Load stops for each direction
        for direction, trip_list in [('outbound', outbound_trips), ('inbound', inbound_trips)]:
            if not trip_list:
                continue
            
            # Use first trip of the day
            trip = trip_list[0]
            stops = get_stops_for_trip(gtfs_data, trip['trip_id'])
            
            if not stops:
                print(f"  ⚠ No stops found for {direction}")
                continue
            
            route = route_objects[direction]
            
            # Check if stops are in Bristol area (lat ~51.4-51.5, lng ~-2.5 to -2.6)
            bristol_stops = []
            for s in stops:
                if 51.3 <= s['lat'] <= 51.6 and -2.7 <= s['lng'] <= -2.4:
                    bristol_stops.append(s)
            
            if not bristol_stops:
                print(f"  ⚠ No Bristol-area stops found for {direction}, using all {len(stops)} stops")
                bristol_stops = stops
            
            print(f"  [OK] Loading {len(bristol_stops)} stops for {direction}...")
            
            # Add stops to database
            for stop_data in bristol_stops:
                # Check if stop already exists
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
                    stop_id = stop.id
                else:
                    stop_id = existing.id
                
                # Create route-stop association
                route_stop = RouteStop(
                    route_id=route.id,
                    stop_id=stop_id,
                    sequence=stop_data['sequence'],
                    scheduled_arrival=stop_data['arrival_time']
                )
                db.session.add(route_stop)
            
            # Update route stop count
            route.total_stops = len(bristol_stops)
            
        db.session.commit()
        print("\n✅ Database seeded successfully!")


if __name__ == "__main__":
    seed()
