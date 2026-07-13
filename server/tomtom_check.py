"""
Quick live check of both TomTom endpoints Transight uses.

Reads the keys from the repo-root .env and calls the Traffic Flow and Routing
APIs with Bristol coordinates, reporting WORKING / FAILING for each.

Run from the server/ directory: python tomtom_check.py
"""
import os

import requests

# Load keys from repo-root .env (one level up from server/)
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
env = {}
with open(ENV_PATH, encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")

TRAFFIC_KEY = env.get("TOMTOM_API_KEY")
ROUTING_KEY = env.get("TOMTOM_ROUTING_KEY")

print(f"Traffic key present: {bool(TRAFFIC_KEY)} | Routing key present: {bool(ROUTING_KEY)}\n")

# 1) Traffic Flow API (Temple Meads area)
print("=== TomTom Traffic Flow API ===")
try:
    r = requests.get(
        "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json",
        params={"point": "51.44898,-2.58262", "unit": "KMPH", "key": TRAFFIC_KEY},
        timeout=10,
    )
    print(f"HTTP {r.status_code}")
    if r.ok:
        flow = r.json().get("flowSegmentData", {})
        print(f"  currentSpeed={flow.get('currentSpeed')} freeFlowSpeed={flow.get('freeFlowSpeed')} "
              f"confidence={flow.get('confidence')}")
        print("  RESULT: WORKING")
    else:
        print(f"  body: {r.text[:200]}")
        print("  RESULT: FAILING")
except Exception as exc:
    print(f"  ERROR: {exc}\n  RESULT: FAILING")

# 2) Routing API (Temple Meads -> Frenchay Campus)
print("\n=== TomTom Routing API ===")
try:
    r = requests.get(
        "https://api.tomtom.com/routing/1/calculateRoute/51.44898,-2.58262:51.50019,-2.54622/json",
        params={"key": ROUTING_KEY, "traffic": "true", "routeType": "fastest"},
        timeout=10,
    )
    print(f"HTTP {r.status_code}")
    if r.ok:
        summary = r.json()["routes"][0]["summary"]
        print(f"  distance={summary['lengthInMeters']/1000:.2f}km "
              f"time={summary['travelTimeInSeconds']/60:.1f}min "
              f"trafficDelay={summary.get('trafficDelayInSeconds')}s")
        print("  RESULT: WORKING")
    else:
        print(f"  body: {r.text[:200]}")
        print("  RESULT: FAILING")
except Exception as exc:
    print(f"  ERROR: {exc}\n  RESULT: FAILING")
