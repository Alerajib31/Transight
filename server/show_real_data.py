"""
Show the real logged BusLog data per route.

Mirrors the real-sample filter used by train_xgboost.py (non-null position + ETA).
Note: synthetic training data is generated in memory and never stored, so every
row in bus_logs is real logged data.

Run from the server/ directory: python show_real_data.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import func

from app import app
from models import BusLog, Route

with app.app_context():
    total = BusLog.query.count()
    print(f"TOTAL bus_logs rows in database: {total}\n")

    for route_name in ("72", "A1"):
        usable = (
            BusLog.query
            .join(Route, BusLog.route_id == Route.id)
            .filter(func.lower(Route.route_name) == route_name.lower())
            .filter(BusLog.predicted_eta.isnot(None))
            .filter(BusLog.bus_lat.isnot(None))
            .filter(BusLog.bus_lng.isnot(None))
        )
        count = usable.count()
        print(f"Route {route_name}: {count} usable REAL samples (non-null position + ETA)")

        for log in usable.order_by(BusLog.timestamp.desc()).limit(3):
            print(f"    id={log.id} vehicle={log.vehicle_id} "
                  f"pos=({log.bus_lat:.4f},{log.bus_lng:.4f}) "
                  f"eta={log.predicted_eta} pax={log.passenger_count} "
                  f"delay={log.delay_minutes} at={log.timestamp}")
        print()
