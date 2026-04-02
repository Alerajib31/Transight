"""
BODS SIRI-VM XML Parser
Parses real-time bus location data from Bus Open Data Service
"""
import xml.etree.ElementTree as ET
import requests
import logging

logger = logging.getLogger("transight")

# XML namespaces used by SIRI
NAMESPACES = {
    'siri': 'http://www.siri.org.uk/siri',
}


def parse_siri_vm(xml_data):
    """
    Parse SIRI-VM XML and extract vehicle activities.
    Returns list of vehicle dicts with position, line, direction, etc.
    """
    vehicles = []
    
    try:
        root = ET.fromstring(xml_data)
        
        # Find VehicleMonitoringDelivery
        vm_deliveries = root.findall('.//siri:VehicleMonitoringDelivery', NAMESPACES)
        
        for delivery in vm_deliveries:
            activities = delivery.findall('.//siri:VehicleActivity', NAMESPACES)
            
            for activity in activities:
                try:
                    vehicle = activity.find('.//siri:MonitoredVehicleJourney', NAMESPACES)
                    if vehicle is None:
                        continue
                    
                    # Extract vehicle data
                    vehicle_data = {}
                    
                    # Line reference (route number)
                    line_ref = vehicle.find('siri:LineRef', NAMESPACES)
                    vehicle_data['line'] = line_ref.text if line_ref is not None else None
                    
                    # Direction
                    direction = vehicle.find('siri:DirectionRef', NAMESPACES)
                    vehicle_data['direction'] = direction.text if direction is not None else None
                    
                    # Destination
                    dest = vehicle.find('siri:DestinationName', NAMESPACES)
                    vehicle_data['destination'] = dest.text if dest is not None else None
                    
                    # Operator
                    operator = vehicle.find('siri:OperatorRef', NAMESPACES)
                    vehicle_data['operator'] = operator.text if operator is not None else None
                    
                    # Vehicle location
                    loc = vehicle.find('siri:VehicleLocation', NAMESPACES)
                    if loc is not None:
                        lat = loc.find('siri:Latitude', NAMESPACES)
                        lng = loc.find('siri:Longitude', NAMESPACES)
                        if lat is not None and lng is not None:
                            vehicle_data['lat'] = float(lat.text)
                            vehicle_data['lng'] = float(lng.text)
                    
                    # Vehicle reference
                    veh_ref = vehicle.find('siri:VehicleRef', NAMESPACES)
                    vehicle_data['vehicle_id'] = veh_ref.text if veh_ref is not None else None
                    
                    # Bearing (direction in degrees)
                    bearing = vehicle.find('siri:Bearing', NAMESPACES)
                    vehicle_data['bearing'] = float(bearing.text) if bearing is not None else None
                    
                    # Speed
                    speed = vehicle.find('siri:Speed', NAMESPACES)
                    vehicle_data['speed'] = float(speed.text) if speed is not None else None
                    
                    # Recorded at time
                    recorded = activity.find('.//siri:RecordedAtTime', NAMESPACES)
                    vehicle_data['recorded_at'] = recorded.text if recorded is not None else None
                    
                    # Only add if we have position data
                    if 'lat' in vehicle_data and 'lng' in vehicle_data:
                        vehicles.append(vehicle_data)
                        
                except Exception as e:
                    logger.warning(f"Error parsing vehicle activity: {e}")
                    continue
                    
    except ET.ParseError as e:
        logger.error(f"XML parse error: {e}")
    except Exception as e:
        logger.error(f"Error parsing SIRI-VM: {e}")
    
    return vehicles


def fetch_bods_vehicles(api_key, line_ref=None, operator_ref=None, bounding_box=None):
    """
    Fetch real-time vehicle positions from BODS API.
    
    Args:
        api_key: BODS API key
        line_ref: Filter by route number (e.g., '72')
        operator_ref: Filter by operator (e.g., 'FBRI' for First Bus)
        bounding_box: Filter by area (lat1,lng1,lat2,lng2)
    
    Returns:
        List of vehicle dicts with position data
    """
    url = 'https://data.bus-data.dft.gov.uk/api/v1/datafeed/'
    params = {'api_key': api_key}
    
    if line_ref:
        params['lineRef'] = line_ref
    if operator_ref:
        params['operatorRef'] = operator_ref
    if bounding_box:
        params['boundingBox'] = bounding_box
    
    try:
        logger.info(f"[BODS] Fetching vehicles with params: {params}")
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        
        # Parse XML response
        vehicles = parse_siri_vm(resp.content)
        logger.info(f"[BODS] Found {len(vehicles)} vehicle(s)")
        
        return vehicles
        
    except requests.exceptions.RequestException as e:
        logger.error(f"[BODS] API request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"[BODS] Unexpected error: {e}")
        return []


if __name__ == "__main__":
    # Test the parser
    import os
    
    BODS_API_KEY = os.getenv('BODS_API_KEY')
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing BODS parser...")

    if not BODS_API_KEY:
        raise SystemExit("Set BODS_API_KEY in your environment before testing bods_parser.py")
    
    test_line_ref = os.getenv("TEST_LINE_REF", "72")
    print(f"Testing BODS fetch for line_ref={test_line_ref!r} ...")
    vehicles = fetch_bods_vehicles(BODS_API_KEY, line_ref=test_line_ref)

    print(f"\nFound {len(vehicles)} vehicles for route {test_line_ref}:")
    for v in vehicles[:5]:
        print(f"  - Line {v.get('line')} ({v.get('direction')}): {v.get('lat'):.4f}, {v.get('lng'):.4f}")
        print(f"    To: {v.get('destination')}, Speed: {v.get('speed')} km/h, Bearing: {v.get('bearing')}°")
