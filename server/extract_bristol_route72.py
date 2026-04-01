"""
Extract real Bristol Route 72 data from GTFS.
This finds the correct Route 72 (Temple Meads to UWE Frenchay) from the GTFS file.
"""

import zipfile
import io
import csv
import os

GTFS_PATH = os.path.join(os.path.dirname(__file__), '..', 'itm_south_west_gtfs.zip')

def extract_bristol_route72():
    """Find Bristol Route 72 in GTFS and extract its stops."""
    
    with zipfile.ZipFile(GTFS_PATH, 'r') as zf:
        # First, find all Route 72 entries
        print("=== Looking for Route 72 in GTFS ===\n")
        
        # Read routes
        routes_72 = []
        with zf.open('routes.txt') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
            for row in reader:
                if row['route_short_name'] == '72':
                    routes_72.append({
                        'route_id': row['route_id'],
                        'route_short_name': row['route_short_name'],
                        'route_long_name': row.get('route_long_name', ''),
                        'agency_id': row.get('agency_id', '')
                    })
        
        print(f"Found {len(routes_72)} Route 72 entries:")
        for r in routes_72:
            print(f"  ID: {r['route_id']}, Name: {r['route_long_name']}, Agency: {r['agency_id']}")
        
        # Read agency info
        print("\n=== Agency Information ===")
        agencies = {}
        with zf.open('agency.txt') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
            for row in reader:
                agencies[row['agency_id']] = {
                    'name': row.get('agency_name', ''),
                    'url': row.get('agency_url', '')
                }
        
        for r in routes_72:
            agency = agencies.get(r['agency_id'], {})
            print(f"  {r['route_id']}: {agency.get('name', 'Unknown')} ({agency.get('url', '')})")
        
        # Try to identify Bristol Route 72
        # Look for trips that go between Temple Meads and UWE/Frenchay
        print("\n=== Analyzing trips for each Route 72 ===")
        
        for route in routes_72:
            route_id = route['route_id']
            
            # Find trips for this route
            trips = []
            with zf.open('trips.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    if row['route_id'] == route_id:
                        trips.append({
                            'trip_id': row['trip_id'],
                            'direction_id': row.get('direction_id', '0'),
                            'service_id': row['service_id']
                        })
            
            print(f"\nRoute {route_id}: {len(trips)} trips")
            
            if not trips:
                continue
            
            # Sample first trip
            sample_trip = trips[0]
            print(f"  Sample trip: {sample_trip['trip_id']} (direction: {sample_trip['direction_id']})")
            
            # Get stop times for this trip
            stop_times = []
            with zf.open('stop_times.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    if row['trip_id'] == sample_trip['trip_id']:
                        stop_times.append({
                            'stop_id': row['stop_id'],
                            'arrival_time': row['arrival_time'],
                            'stop_sequence': int(row['stop_sequence'])
                        })
            
            stop_times.sort(key=lambda x: x['stop_sequence'])
            
            # Get stop details
            stops_info = {}
            with zf.open('stops.txt') as f:
                reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
                for row in reader:
                    stops_info[row['stop_id']] = {
                        'stop_id': row['stop_id'],
                        'stop_name': row['stop_name'],
                        'lat': float(row['stop_lat']),
                        'lng': float(row['stop_lon'])
                    }
            
            # Print first and last few stops
            print(f"  Total stops: {len(stop_times)}")
            if stop_times:
                first_stop = stops_info.get(stop_times[0]['stop_id'], {})
                last_stop = stops_info.get(stop_times[-1]['stop_id'], {})
                print(f"  First: {first_stop.get('stop_name', 'Unknown')} ({first_stop.get('lat')}, {first_stop.get('lng')})")
                print(f"  Last: {last_stop.get('stop_name', 'Unknown')} ({last_stop.get('lat')}, {last_stop.get('lng')})")
                
                # Check if this looks like Bristol (lat ~51.4-51.5, lng ~-2.5 to -2.6)
                first_lat = first_stop.get('lat', 0)
                first_lng = first_stop.get('lng', 0)
                
                if 51.4 <= first_lat <= 51.5 and -2.65 <= first_lng <= -2.5:
                    print(f"  ✓✓✓ This looks like BRISTOL Route 72! ✓✓✓")
                    
                    # Print all stops
                    print(f"\n  All stops for Route {route_id}:")
                    for i, st in enumerate(stop_times):
                        stop = stops_info.get(st['stop_id'], {})
                        print(f"    {i+1}. {stop.get('stop_name', 'Unknown')} ({st['arrival_time']})")
                    
                    # Save this data
                    return {
                        'route_id': route_id,
                        'stops': [
                            {
                                'stop_id': st['stop_id'],
                                'stop_name': stops_info[st['stop_id']]['stop_name'],
                                'lat': stops_info[st['stop_id']]['lat'],
                                'lng': stops_info[st['stop_id']]['lng'],
                                'arrival_time': st['arrival_time'],
                                'sequence': i
                            }
                            for i, st in enumerate(stop_times)
                            if st['stop_id'] in stops_info
                        ]
                    }
        
        return None

if __name__ == "__main__":
    result = extract_bristol_route72()
    
    if result:
        print(f"\n\n=== SUCCESS ===")
        print(f"Found Bristol Route 72 with {len(result['stops'])} stops!")
        print(f"Route ID: {result['route_id']}")
        
        # Save to file for use in seed.py
        import json
        output_path = os.path.join(os.path.dirname(__file__), 'bristol_route72_stops.json')
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nSaved to: {output_path}")
    else:
        print("\n\n=== FAILED ===")
        print("Could not find Bristol Route 72 in GTFS!")
