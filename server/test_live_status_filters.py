"""Focused tests for live status bus visibility and fallback filtering."""

import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module


def make_stop(sequence, lat, lng):
    """Create a lightweight route stop object for unit tests."""
    return SimpleNamespace(
        sequence=sequence,
        stop=SimpleNamespace(lat=lat, lng=lng),
    )


def make_route():
    """Create a lightweight route object for unit tests."""
    return SimpleNamespace(
        id=4,
        route_name="A1",
        direction="inbound",
        origin_name="Bristol Airport",
        destination_name="Bristol City Centre (Marlborough St)",
        origin_lat=51.3826,
        origin_lng=-2.7191,
        dest_lat=51.4586,
        dest_lng=-2.5945,
        typical_duration_min=47.0,
        total_stops=2,
        route_stops=[
            make_stop(0, 51.0000, -2.0000),
            make_stop(1, 51.1000, -2.1000),
        ],
    )


def make_log(vehicle_id, minutes_ago=0, eta=10.0):
    """Create a lightweight BusLog-like object for unit tests."""
    timestamp = datetime(2026, 4, 3, 5, 0, tzinfo=app_module.UK_TZ) - timedelta(
        minutes=minutes_ago
    )
    return SimpleNamespace(
        vehicle_id=vehicle_id,
        bus_lat=51.0100,
        bus_lng=-2.0100,
        passenger_count=3,
        traffic_delay=45.0,
        predicted_eta=eta,
        scheduled_service_time="05:00",
        delay_minutes=2.0,
        timestamp=timestamp,
    )


class LiveStatusFilterTests(unittest.TestCase):
    """Exercise the new status visibility rules with lightweight fixtures."""

    def setUp(self):
        self.route = make_route()

    def test_origin_staging_bus_is_hidden_before_four_minute_window(self):
        trip = {
            "service_date": date(2026, 4, 3),
            "stops": [
                {
                    "sequence": 0,
                    "lat": 51.0000,
                    "lng": -2.0000,
                    "arrival_time": "05:00:00",
                    "departure_time": "05:00:00",
                },
                {
                    "sequence": 1,
                    "lat": 51.1000,
                    "lng": -2.1000,
                    "arrival_time": "05:30:00",
                    "departure_time": "05:30:00",
                },
            ],
        }

        with patch.object(app_module, "get_gtfs_schedule_trip", return_value=trip):
            visible = app_module.is_position_plausible_for_timetable(
                self.route,
                51.0000,
                -2.0000,
                datetime(2026, 4, 3, 4, 55, tzinfo=app_module.UK_TZ),
            )

        self.assertFalse(visible)

    def test_origin_staging_bus_is_shown_within_four_minute_window(self):
        trip = {
            "service_date": date(2026, 4, 3),
            "stops": [
                {
                    "sequence": 0,
                    "lat": 51.0000,
                    "lng": -2.0000,
                    "arrival_time": "05:00:00",
                    "departure_time": "05:00:00",
                },
                {
                    "sequence": 1,
                    "lat": 51.1000,
                    "lng": -2.1000,
                    "arrival_time": "05:30:00",
                    "departure_time": "05:30:00",
                },
            ],
        }

        with patch.object(app_module, "get_gtfs_schedule_trip", return_value=trip):
            visible = app_module.is_position_plausible_for_timetable(
                self.route,
                51.0000,
                -2.0000,
                datetime(2026, 4, 3, 4, 56, tzinfo=app_module.UK_TZ),
            )

        self.assertTrue(visible)

    def test_origin_staging_bus_is_shown_after_departure(self):
        trip = {
            "service_date": date(2026, 4, 3),
            "stops": [
                {
                    "sequence": 0,
                    "lat": 51.0000,
                    "lng": -2.0000,
                    "arrival_time": "05:00:00",
                    "departure_time": "05:00:00",
                },
                {
                    "sequence": 1,
                    "lat": 51.1000,
                    "lng": -2.1000,
                    "arrival_time": "05:30:00",
                    "departure_time": "05:30:00",
                },
            ],
        }

        with patch.object(app_module, "get_gtfs_schedule_trip", return_value=trip):
            visible = app_module.is_position_plausible_for_timetable(
                self.route,
                51.0000,
                -2.0000,
                datetime(2026, 4, 3, 5, 0, tzinfo=app_module.UK_TZ),
            )

        self.assertTrue(visible)

    @patch.object(app_module, "calculate_stop_predictions", return_value=[])
    @patch.object(app_module, "get_current_service_time", return_value=("05:00", 2.0, None))
    @patch.object(app_module, "resolve_live_eta", side_effect=lambda route, log, current_stop_seq, remaining_stops: (log.predicted_eta, "test"))
    @patch.object(app_module, "count_remaining_stops", return_value=(3, 4.5, 1))
    @patch.object(app_module, "is_log_eligible_for_status_fallback", return_value=True)
    def test_status_builder_merges_live_and_recent_fallback_logs(
        self,
        _eligible_mock,
        _count_mock,
        _eta_mock,
        _service_mock,
        _stops_mock,
    ):
        now = datetime(2026, 4, 3, 5, 0, tzinfo=app_module.UK_TZ)
        live_vehicle = {
            "vehicle_id": "FBRI-live-1",
            "lat": 51.0200,
            "lng": -2.0200,
            "recorded_at": now.isoformat(),
            "operator": "FBRI",
        }
        live_log = make_log("FBRI-live-1", eta=9.0)
        fallback_log_1 = make_log("FBRI-fallback-1", eta=12.0)
        fallback_log_2 = make_log("FBRI-fallback-2", eta=15.0)

        with patch.object(app_module, "fetch_all_buses_for_route", return_value=[live_vehicle]), \
             patch.object(
                 app_module,
                 "get_recent_logs_by_vehicle_for_route",
                 return_value={
                     "FBRI-live-1": live_log,
                     "FBRI-fallback-1": fallback_log_1,
                     "FBRI-fallback-2": fallback_log_2,
                 },
             ), \
             patch.object(
                 app_module,
                 "get_latest_logs_by_vehicle_for_route",
                 return_value={
                     "FBRI-live-1": live_log,
                     "FBRI-fallback-1": fallback_log_1,
                     "FBRI-fallback-2": fallback_log_2,
                 },
             ):
            buses = app_module.build_status_bus_list_from_live_snapshot(
                self.route,
                all_vehicles=[],
                current_time=now,
            )

        self.assertEqual(len(buses), 3)
        self.assertEqual(
            [bus["vehicle_id"] for bus in buses],
            ["FBRI-live-1", "FBRI-fallback-1", "FBRI-fallback-2"],
        )

    def test_fallback_log_rejects_old_vehicle(self):
        old_log = make_log("FBRI-old", minutes_ago=3)

        eligible = app_module.is_log_eligible_for_status_fallback(
            self.route,
            old_log,
            current_time=datetime(2026, 4, 3, 5, 0, tzinfo=app_module.UK_TZ),
        )

        self.assertFalse(eligible)

    def test_fallback_log_rejects_implausible_vehicle(self):
        with patch.object(app_module, "is_position_plausible_for_timetable", return_value=False):
            eligible = app_module.is_log_eligible_for_status_fallback(
                self.route,
                make_log("FBRI-implausible"),
                current_time=datetime(2026, 4, 3, 5, 0, tzinfo=app_module.UK_TZ),
            )

        self.assertFalse(eligible)

    def test_fallback_log_rejects_finished_trip(self):
        with patch.object(app_module, "is_position_plausible_for_timetable", return_value=True), \
             patch.object(app_module, "count_remaining_stops", return_value=(0, 0.0, 1)), \
             patch.object(app_module, "is_trip_effectively_finished", return_value=True):
            eligible = app_module.is_log_eligible_for_status_fallback(
                self.route,
                make_log("FBRI-finished"),
                current_time=datetime(2026, 4, 3, 5, 0, tzinfo=app_module.UK_TZ),
            )

        self.assertFalse(eligible)


if __name__ == "__main__":
    unittest.main()
