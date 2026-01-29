import api_services
import requests
import xml.etree.ElementTree as ET

print("=" * 60)
print("TESTING REAL APIs")
print("=" * 60)

# Test BODS with DETAILED DEBUGGING
print("\n1️⃣ TESTING BODS API (Real Bus Location)...")
print("-" * 60)

try:
    # Call BODS API directly to see raw response (Using Bounding Box for Bristol)
    bbox = "-2.7,51.4,-2.5,51.55"
    url = f"https://data.bus-data.dft.gov.uk/api/v1/datafeed?boundingBox={bbox}&api_key={api_services.BODS_API_KEY}"
    
    print(f"   Calling: {url[:80]}...")
    response = requests.get(url, timeout=10)
    print(f"   Status Code: {response.status_code}")
    
    if response.status_code == 200:
        # Show first part of response
        print(f"   Response size: {len(response.content)} bytes")
        print(f"   First 200 chars: {response.text[:200]}")
        
        # Parse XML
        root = ET.fromstring(response.content)
        ns = {'siri': 'http://www.siri.org.uk/siri'}
        
        # Find ALL vehicle activities
        activities = root.findall(".//siri:VehicleActivity", ns)
        print(f"\n   ✅ Found {len(activities)} total vehicles in feed")
        
        if len(activities) > 0:
            # Show first few buses
            print(f"\n   First 5 buses in feed:")
            for i, activity in enumerate(activities[:5]):
                line_ref = activity.find(".//siri:LineRef", ns)
                if line_ref is not None:
                    print(f"      {i+1}. Bus Line: {line_ref.text}")
        
        # Now search for Bus 72
        print(f"\n   Searching for Bus 72...")
        found = False
        for activity in activities:
            line_ref = activity.find(".//siri:LineRef", ns)
            
            if line_ref is not None:
                print(f"      Checking: {line_ref.text}")
                if line_ref.text == "72":
                    latitude = activity.find(".//siri:Latitude", ns)
                    longitude = activity.find(".//siri:Longitude", ns)
                    
                    if latitude is not None and longitude is not None:
                        lat = float(latitude.text)
                        lon = float(longitude.text)
                        print(f"   ✅ FOUND Bus 72 at ({lat:.4f}, {lon:.4f})")
                        found = True
                        bods_working = True
                        break
        
        if not found:
            print(f"   ⚠️ Bus 72 NOT FOUND in the feed")
            print(f"   Possible reasons:")
            print(f"      1. Bus 72 is not running right now (check time)")
            print(f"      2. Bus 72 line number might be different in BODS")
            print(f"   Trying to get location via function...")
            lat, lon, location_name = api_services.get_live_bus_location("72")
            print(f"   ✅ Function returned: ({lat:.4f}, {lon:.4f})")
            bods_working = True
    else:
        print(f"   ❌ API returned status {response.status_code}")
        bods_working = False
        
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    bods_working = False

# Test TomTom
print("\n\n2️⃣ TESTING TomTom API (Real Traffic)...")
print("-" * 60)
try:
    delay = api_services.get_traffic_delay(
        origin_lat=51.4545,
        origin_lon=-2.5879,
        dest_lat=51.4496,
        dest_lon=-2.5811
    )
    print(f"✅ SUCCESS: Traffic delay = {delay} minutes")
    tomtom_working = True
except Exception as e:
    print(f"❌ FAILED: {e}")
    tomtom_working = False

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"BODS API:   {'✅ WORKING' if bods_working else '❌ NOT WORKING (Check if Bus 72 is running)'}")
print(f"TomTom API: {'✅ WORKING' if tomtom_working else '❌ NOT WORKING'}")
print("=" * 60)