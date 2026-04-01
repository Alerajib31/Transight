"""Test API endpoints"""
from app import app

with app.test_client() as client:
    # Test stops API
    print("Testing /api/routes/1/stops...")
    resp = client.get('/api/routes/1/stops')
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.get_json()
        stops = data.get('stops', [])
        print(f"Total stops: {len(stops)}")
        
        if stops:
            first = stops[0]
            print(f"First stop keys: {list(first.keys())}")
            print(f"First stop: {first}")
            
            # Check the structure
            if 'stop' in first:
                print(f"Stop name: {first['stop'].get('stop_name')}")
                print(f"Stop lat: {first['stop'].get('lat')}")
                print(f"Stop lng: {first['stop'].get('lng')}")
            else:
                print("WARNING: 'stop' key not found in stop data!")
    else:
        print(f"Error: {resp.get_json()}")
    
    print()
    
    # Test status API
    print("Testing /api/status/1...")
    resp = client.get('/api/status/1')
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.get_json()
        print(f"Bus available: {data.get('bus_available')}")
        print(f"Status keys: {list(data.keys())}")
        if data.get('status'):
            status = data['status']
            print(f"ETA: {status.get('predicted_eta')}")
            print(f"Bus lat: {status.get('bus_lat')}")
            print(f"Bus lng: {status.get('bus_lng')}")
