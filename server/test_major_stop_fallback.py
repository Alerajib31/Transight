"""Focused tests for route-specific crowd-detection fallback stops."""

import unittest
from types import SimpleNamespace

import app as app_module


def make_route(route_name, direction):
    """Create a route object with no database stops loaded."""
    return SimpleNamespace(
        route_name=route_name,
        direction=direction,
        route_stops=[],
    )


class MajorStopFallbackTests(unittest.TestCase):
    def test_a1_outbound_uses_a1_airport_fallback(self):
        is_near, stop_name, distance = app_module.is_near_major_stop(
            51.38743,
            -2.70987,
            make_route("A1", "outbound"),
        )

        self.assertTrue(is_near)
        self.assertEqual(stop_name, "Public Transport Interchange")
        self.assertEqual(distance, 0.0)

    def test_72_outbound_still_uses_72_fallback(self):
        is_near, stop_name, distance = app_module.is_near_major_stop(
            51.44898,
            -2.58262,
            make_route("72", "outbound"),
        )

        self.assertTrue(is_near)
        self.assertEqual(stop_name, "Temple Meads Stn")
        self.assertEqual(distance, 0.0)

    def test_unknown_route_without_db_stops_has_no_route_72_fallback(self):
        is_near, stop_name, distance = app_module.is_near_major_stop(
            51.44898,
            -2.58262,
            make_route("X9", "outbound"),
        )

        self.assertFalse(is_near)
        self.assertIsNone(stop_name)
        self.assertEqual(distance, float("inf"))


if __name__ == "__main__":
    unittest.main()
