"""
SWIFT SYSTEM - Final End-to-End Integration & Webots Liveness Test Suite
Verifies:
1. Webots OFF behavior: Backend returns simulation_connected=False & simulation_status=unavailable.
2. Webots ON behavior: Backend performs traffic analysis & returns recommended route from Webots.
3. Destination mapping & route changes: Civic Centre (#6) -> Central Square (#11) & Lakeside Medical Centre (#23).
4. Validation: Same source & destination error checking.
"""

import unittest
import sys
import os
import asyncio

# Add Phoenix/swift-system to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.api.endpoints import resolve_location, handle_route_request
from fastapi import HTTPException


class TestEndToEndIntegration(unittest.TestCase):

    def setUp(self):
        # Reset env overrides before each test
        os.environ.pop("FORCE_WEBOTS_OFFLINE", None)
        os.environ.pop("FORCE_WEBOTS_ONLINE", None)

    def tearDown(self):
        os.environ.pop("FORCE_WEBOTS_OFFLINE", None)
        os.environ.pop("FORCE_WEBOTS_ONLINE", None)

    def test_location_resolution(self):
        """Verify location names and numeric IDs resolve correctly"""
        node_id, name = resolve_location("Civic Centre")
        self.assertEqual(node_id, 6)
        self.assertEqual(name, "Civic Centre")

        node_id, name = resolve_location(11)
        self.assertEqual(node_id, 11)
        self.assertEqual(name, "Central Square")

        node_id, name = resolve_location("23")
        self.assertEqual(node_id, 23)
        self.assertEqual(name, "Lakeside Medical Centre")

    def test_webots_offline_behavior(self):
        """TEST A — Webots OFF: Server must report simulation_connected=False & simulation_status=unavailable"""
        os.environ["FORCE_WEBOTS_OFFLINE"] = "1"
        payload = {
            "start": 6,
            "end": 11,
            "source": "Civic Centre",
            "destination": "Central Square"
        }
        data = asyncio.run(handle_route_request(payload))

        self.assertFalse(data.get("simulation_connected"))
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("simulation_status"), "unavailable")
        self.assertIn("Simulation unavailable", data.get("error", ""))

    def test_webots_online_behavior(self):
        """TEST B — Webots ON: Civic Centre (#6) -> Central Square (#11)"""
        os.environ["FORCE_WEBOTS_ONLINE"] = "1"
        payload = {
            "start": 6,
            "end": 11,
            "source": "Civic Centre",
            "destination": "Central Square"
        }
        data = asyncio.run(handle_route_request(payload))

        self.assertTrue(data.get("simulation_connected"))
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("simulation_status"), "completed")
        self.assertEqual(data.get("source"), "Civic Centre")
        self.assertEqual(data.get("destination"), "Central Square")
        self.assertIn("Central Square", data.get("recommended_route", []))
        self.assertIn(11, data.get("path", []))

    def test_second_destination(self):
        """TEST C — Second Destination: Civic Centre (#6) -> Lakeside Medical Centre (#23)"""
        os.environ["FORCE_WEBOTS_ONLINE"] = "1"
        payload = {
            "start": 6,
            "end": 23,
            "source": "Civic Centre",
            "destination": "Lakeside Medical Centre"
        }
        data = asyncio.run(handle_route_request(payload))

        self.assertTrue(data.get("simulation_connected"))
        self.assertEqual(data.get("source"), "Civic Centre")
        self.assertEqual(data.get("destination"), "Lakeside Medical Centre")
        self.assertIn("Lakeside Medical Centre", data.get("recommended_route", []))
        self.assertIn(23, data.get("path", []))

    def test_validation_same_source_and_destination(self):
        """Test validation error when source equals destination"""
        payload = {
            "start": 6,
            "end": 6,
            "source": "Civic Centre",
            "destination": "Civic Centre"
        }
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(handle_route_request(payload))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Current location and destination must be different", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
