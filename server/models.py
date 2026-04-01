"""
Transight — Database Models (SQLAlchemy)
Defines the scalable schema: Route (config) and BusLog (history).
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


class Route(db.Model):
    """
    Stores the configuration of each monitored bus route.
    Adding a new row here automatically includes it in the Fusion Engine loop.
    """
    __tablename__ = "routes"

    id = db.Column(db.Integer, primary_key=True)
    route_name = db.Column(db.String(20), nullable=False)          # e.g. "72"
    direction = db.Column(db.String(20), nullable=False)           # "outbound" / "inbound"
    origin_name = db.Column(db.String(120), nullable=False)        # e.g. "Temple Meads"
    origin_lat = db.Column(db.Float, nullable=False)
    origin_lng = db.Column(db.Float, nullable=False)
    destination_name = db.Column(db.String(120), nullable=False)   # e.g. "UWE Frenchay"
    dest_lat = db.Column(db.Float, nullable=False)
    dest_lng = db.Column(db.Float, nullable=False)
    # Route waypoints as JSON array of [lat, lng] pairs
    route_path = db.Column(db.JSON, nullable=True)
    # GTFS trip ID for timetable lookup
    gtfs_trip_id = db.Column(db.String(50), nullable=True)
    # Typical trip duration in minutes (from timetable data)
    typical_duration_min = db.Column(db.Float, nullable=True)
    # Total number of stops on this route
    total_stops = db.Column(db.Integer, nullable=True)

    logs = db.relationship("BusLog", backref="route", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "route_name": self.route_name,
            "direction": self.direction,
            "origin_name": self.origin_name,
            "origin_lat": self.origin_lat,
            "origin_lng": self.origin_lng,
            "destination_name": self.destination_name,
            "dest_lat": self.dest_lat,
            "dest_lng": self.dest_lng,
            "route_path": self.route_path or [],
            "gtfs_trip_id": self.gtfs_trip_id,
            "typical_duration_min": self.typical_duration_min,
            "total_stops": self.total_stops,
        }


class BusLog(db.Model):
    """
    Historical log of each Fusion Engine cycle.
    Each row captures GPS, crowd count, traffic, and the predicted ETA.
    """
    __tablename__ = "bus_logs"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"), nullable=False)
    vehicle_id = db.Column(db.String(50), nullable=True)  # BODS vehicle reference
    bus_lat = db.Column(db.Float)
    bus_lng = db.Column(db.Float)
    passenger_count = db.Column(db.Integer, default=0)
    traffic_delay = db.Column(db.Float, default=0.0)       # seconds of extra delay
    predicted_eta = db.Column(db.Float)                     # minutes to destination
    # Scheduled service departure time (the service this bus is running)
    scheduled_service_time = db.Column(db.String(5), nullable=True)  # HH:MM format
    # Delay compared to schedule (minutes, positive = late)
    delay_minutes = db.Column(db.Float, nullable=True)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            "id": self.id,
            "route_id": self.route_id,
            "vehicle_id": self.vehicle_id,
            "bus_lat": self.bus_lat,
            "bus_lng": self.bus_lng,
            "passenger_count": self.passenger_count,
            "traffic_delay": self.traffic_delay,
            "predicted_eta": self.predicted_eta,
            "scheduled_service_time": self.scheduled_service_time,
            "delay_minutes": self.delay_minutes,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class Stop(db.Model):
    """Bus stop information from GTFS."""
    __tablename__ = "stops"

    id = db.Column(db.Integer, primary_key=True)
    stop_id = db.Column(db.String(50), unique=True, nullable=False)  # GTFS stop_id
    stop_name = db.Column(db.String(200), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'stop_id': self.stop_id,
            'stop_name': self.stop_name,
            'lat': self.lat,
            'lng': self.lng
        }


class RouteStop(db.Model):
    """Association between routes and stops (ordered)."""
    __tablename__ = "route_stops"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"), nullable=False)
    stop_id = db.Column(db.Integer, db.ForeignKey("stops.id"), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)  # Order of stop in route
    scheduled_arrival = db.Column(db.String(20))  # HH:MM:SS from GTFS

    route = db.relationship("Route", backref="route_stops")
    stop = db.relationship("Stop")

    def to_dict(self):
        return {
            'route_id': self.route_id,
            'stop': self.stop.to_dict() if self.stop else None,
            'sequence': self.sequence,
            'scheduled_arrival': self.scheduled_arrival
        }
