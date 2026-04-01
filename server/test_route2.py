"""Test route 2 (inbound) status"""
from app import app

with app.test_client() as client:
    resp = client.get('/api/status/2')
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.get_json()
        print(f"\nKeys: {list(data.keys())}")
        print(f"Bus available: {data.get('bus_available')}")
        print(f"Bus count: {data.get('bus_count')}")
        print(f"Buses: {len(data.get('buses', []))}")
        
        if data.get('buses'):
            for i, bus in enumerate(data['buses']):
                print(f"\nBus #{i+1}:")
                print(f"  vehicle_id: {bus.get('vehicle_id')}")
                print(f"  eta: {bus.get('eta')}")
