"""Check what stops we loaded"""
from app import app, db
from models import Route, RouteStop

with app.app_context():
    routes = Route.query.all()
    for route in routes:
        print(f"\nRoute {route.route_name} ({route.direction}):")
        stops = RouteStop.query.filter_by(route_id=route.id).order_by(RouteStop.sequence).all()
        print(f"  Total stops: {len(stops)}")
        
        for rs in stops[:5]:  # Show first 5
            print(f"  {rs.sequence}: {rs.stop.stop_name} ({rs.stop.lat:.4f}, {rs.stop.lng:.4f})")
        
        if len(stops) > 5:
            print(f"  ... and {len(stops) - 5} more stops")
