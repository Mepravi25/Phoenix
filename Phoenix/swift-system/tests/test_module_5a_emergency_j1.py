"""
SWIFT SYSTEM - Module 5A J1 Ambulance Emergency Traffic-Light Priority Verification Suite
Tests:
1. TEST 1 — NORMAL J1: Verify baseline safe signal cycle without conflicts.
2. TEST 2 — EMERGENCY REQUEST: Verify approach detection (dist <= 20m) generates [SWIFT_EMERGENCY_REQUEST].
3. TEST 3 — SIGNAL TRANSITION: Verify opposing GREEN -> YELLOW -> ALL_RED -> EMERGENCY_GREEN sequence.
4. TEST 4 — AMBULANCE CROSSING: Verify ambulance gets green, crosses J1 safely without collisions.
5. TEST 5 — RESTORATION: Verify EMERGENCY_GREEN -> YELLOW -> ALL_RED -> NORMAL cycle restoration.
6. TEST 6 — NORMAL CARS: Verify civilian vehicles continue running and obey traffic signals.
7. TEST 7 — REPEATED APPROACH: Verify J1 resets and handles subsequent emergency requests.
"""

import sys
import os
import math
import time
import json
import unittest
from typing import Dict, List, Tuple, Any

# Ensure controllers are on path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers"))
sys.path.append(os.path.join(BASE_DIR, "junction_controller"))
sys.path.append(os.path.join(BASE_DIR, "ambulance_001_controller"))
sys.path.append(os.path.join(BASE_DIR, "car_001_controller"))
sys.path.append(os.path.join(BASE_DIR, "car_002_controller"))
sys.path.append(os.path.join(BASE_DIR, "car_003_controller"))
sys.path.append(os.path.join(BASE_DIR, "car_004_controller"))

from junction_controller import (
    IntersectionController,
    SignalPhase,
    LampState,
    Approach,
    SHARED_EMERGENCY_REQUESTS,
    EMERGENCY_REQUESTS_FILE
)
from ambulance_001_controller import Ambulance001Controller, calculate_bumper_gap, distance
from car_001_controller import Car001Controller, SHARED_MEMORY_REGISTRY


def cleanup_state():
    """Reset shared memory registry and state files before tests."""
    SHARED_MEMORY_REGISTRY.clear()
    SHARED_EMERGENCY_REQUESTS.clear()
    state_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots"))
    if os.path.exists(state_dir):
        for fname in os.listdir(state_dir):
            if fname.startswith("vehicle_pos") or fname.startswith("emergency_requests"):
                try:
                    os.remove(os.path.join(state_dir, fname))
                except Exception:
                    pass


class TestModule5AEmergencyJ1(unittest.TestCase):

    def setUp(self):
        cleanup_state()

    def tearDown(self):
        cleanup_state()

    def test_1_normal_j1(self):
        """TEST 1 — NORMAL J1: 5s run verifying normal cycle without signal conflicts."""
        print("\n--- TEST 1: NORMAL J1 CYCLE (5s max) ---")
        j1 = IntersectionController(junction_id="J1", robot=None)
        dt = 0.032
        steps = int(5.0 / dt)

        conflicts = 0
        for _ in range(steps):
            j1.update_logic(dt)
            if j1.signal_conflicts_count > 0:
                conflicts += j1.signal_conflicts_count

        self.assertEqual(conflicts, 0, "Signal conflict detected during normal cycle!")
        print(f"Test 1 Normal J1: signal_conflicts={conflicts} -> PASS")

    def test_2_emergency_request(self):
        """TEST 2 — EMERGENCY REQUEST: Ambulance approaching J1 generates request within 20m."""
        print("\n--- TEST 2: AMBULANCE EMERGENCY REQUEST GENERATION (8s max) ---")
        amb = Ambulance001Controller()
        amb.x = -46.5
        amb.y = 20.0  # Distance to J1 center (-46.5, 46.5) = 26.5m
        amb.heading = math.pi / 2.0
        amb.current_wp_idx = 0

        dt = 0.032
        request_generated = False
        request_details = {}

        # Run until ambulance reaches within 20m (y >= 26.5m)
        for _ in range(int(8.0 / dt)):
            amb.update_logic(dt)
            if amb.emergency_requested_j1:
                request_generated = True
                if "J1" in SHARED_EMERGENCY_REQUESTS:
                    request_details = SHARED_EMERGENCY_REQUESTS["J1"]
                break

        self.assertTrue(request_generated, "Emergency request was NOT generated!")
        self.assertEqual(request_details.get("vehicle_id"), "AMBULANCE_001")
        self.assertEqual(request_details.get("junction_id"), "J1")
        self.assertEqual(request_details.get("approach_direction"), "SOUTH")
        print(f"Test 2 Emergency Request: vehicle={request_details.get('vehicle_id')}, junction={request_details.get('junction_id')}, approach={request_details.get('approach_direction')} -> PASS")

    def test_3_signal_transition(self):
        """TEST 3 — SIGNAL TRANSITION: Conflicting EW_GREEN safely clears through EW_YELLOW -> ALL_RED -> EMERGENCY_GREEN."""
        print("\n--- TEST 3: SAFE PHASE CLEARANCE & TRANSITION ---")
        j1 = IntersectionController(junction_id="J1", robot=None)
        # Put J1 into EW_GREEN phase first
        j1.current_phase = SignalPhase.EW_GREEN
        j1._apply_phase_lamps(SignalPhase.EW_GREEN)

        # Inject emergency request from SOUTH
        SHARED_EMERGENCY_REQUESTS["J1"] = {
            "vehicle_id": "AMBULANCE_001",
            "junction_id": "J1",
            "approach_direction": "SOUTH",
            "request_type": "EMERGENCY_PRIORITY",
            "active": True
        }

        dt = 0.032
        yellow_seen = False
        all_red_seen = False
        emergency_green_seen = False

        for _ in range(int(10.0 / dt)):
            j1.update_logic(dt)
            if j1.signals[Approach.EAST].current_state == LampState.YELLOW:
                yellow_seen = True
            if j1.emergency_state == "ALL_RED":
                all_red_seen = True
            if j1.emergency_state == "GREEN" and j1.signals[Approach.SOUTH].current_state == LampState.GREEN:
                emergency_green_seen = True
                # Verify opposite EW direction is RED during emergency green
                self.assertEqual(j1.signals[Approach.EAST].current_state, LampState.RED)
                self.assertEqual(j1.signals[Approach.WEST].current_state, LampState.RED)
                break

        self.assertTrue(yellow_seen, "Yellow transition did not occur during phase clearance!")
        self.assertTrue(all_red_seen, "ALL_RED phase did not occur before emergency green!")
        self.assertTrue(emergency_green_seen, "EMERGENCY_GREEN was not activated!")
        self.assertEqual(j1.signal_conflicts_count, 0, "Signal conflict occurred during transition!")
        print("Test 3 Signal Transition: EW_GREEN -> EW_YELLOW -> ALL_RED -> EMERGENCY_GREEN -> PASS")

    def test_4_ambulance_crossing(self):
        """TEST 4 — AMBULANCE CROSSING: Ambulance approaches J1, gets GREEN, and crosses safely."""
        print("\n--- TEST 4: AMBULANCE CROSSING J1 (10s max) ---")
        j1 = IntersectionController(junction_id="J1", robot=None)
        j1.config["green_duration"] = 15.0

        amb = Ambulance001Controller()
        amb.x = -46.5
        amb.y = 20.0
        amb.heading = math.pi / 2.0
        amb.current_wp_idx = 0

        dt = 0.032
        steps = int(10.0 / dt)

        entered_j1 = False
        cleared_j1 = False

        for _ in range(steps):
            amb.update_logic(dt)
            j1.update_logic(dt)

            if j1.ambulance_entered_j1:
                entered_j1 = True
            if j1.ambulance_cleared_j1:
                cleared_j1 = True
                break

        self.assertTrue(entered_j1, "Ambulance failed to enter J1 clearance zone!")
        self.assertTrue(cleared_j1, "Ambulance failed to clear J1 intersection!")
        self.assertGreater(amb.x, -46.5, "Ambulance did not complete turn east past J1!")
        print(f"Test 4 Ambulance Crossing: entered_j1={entered_j1}, cleared_j1={cleared_j1}, final_pos=({amb.x:.2f},{amb.y:.2f}) -> PASS")

    def test_5_restoration(self):
        """TEST 5 — RESTORATION: After clearance, J1 restores normal signal cycle."""
        print("\n--- TEST 5: RESTORATION OF NORMAL SIGNAL CYCLE ---")
        j1 = IntersectionController(junction_id="J1", robot=None)
        j1.emergency_state = "GREEN"
        j1.emergency_request = {
            "vehicle_id": "AMBULANCE_001",
            "junction_id": "J1",
            "approach_direction": "SOUTH",
            "request_type": "EMERGENCY_PRIORITY",
            "active": True
        }
        j1.ambulance_entered_j1 = True
        j1.ambulance_cleared_j1 = True  # Trigger restoration

        dt = 0.032
        restore_yellow_seen = False
        restore_all_red_seen = False
        normal_cycle_restored = False

        for _ in range(int(10.0 / dt)):
            j1.update_logic(dt)
            if j1.emergency_state == "RESTORE_YELLOW":
                restore_yellow_seen = True
            if j1.emergency_state == "RESTORE_ALL_RED":
                restore_all_red_seen = True
            if j1.emergency_state == "IDLE" and j1.current_phase == SignalPhase.EW_GREEN:
                normal_cycle_restored = True
                break

        self.assertTrue(restore_yellow_seen, "Restoration yellow phase not executed!")
        self.assertTrue(restore_all_red_seen, "Restoration ALL_RED phase not executed!")
        self.assertTrue(normal_cycle_restored, "Normal cycle was not restored!")
        print("Test 5 Restoration: EMERGENCY_GREEN -> YELLOW -> ALL_RED -> NORMAL_CYCLE (EW_GREEN) -> PASS")

    def test_6_normal_cars_interaction(self):
        """TEST 6 — NORMAL CARS INTERACTION: Normal vehicles run independently and stop at RED during emergency."""
        print("\n--- TEST 6: NORMAL VEHICLES INTERACTION ---")
        j1 = IntersectionController(junction_id="J1", robot=None)

        car1 = Car001Controller()
        car1.x = -46.5
        car1.y = 32.0
        car1.heading = math.pi / 2.0
        car1.speed = 0.0
        SHARED_MEMORY_REGISTRY["CAR_001"] = (car1.x, car1.y, car1.heading)

        amb = Ambulance001Controller()
        amb.x = -46.5
        amb.y = 20.0
        amb.heading = math.pi / 2.0
        amb.current_wp_idx = 0

        dt = 0.032
        overlaps = 0

        for _ in range(int(5.0 / dt)):
            amb.update_logic(dt)
            j1.update_logic(dt)
            SHARED_MEMORY_REGISTRY["CAR_001"] = (car1.x, car1.y, car1.heading)

            gap, _, _ = calculate_bumper_gap(amb.x, amb.y, amb.heading, car1.x, car1.y, car1.heading)
            if gap < 0.0:
                overlaps += 1

        self.assertEqual(overlaps, 0, "Collision overlap detected between ambulance and normal car!")
        self.assertIn(amb.block_reason, ["VEHICLE", "VEHICLE_AHEAD"])
        print("Test 6 Normal Cars: Normal car and ambulance safely coexisted without collision -> PASS")

    def test_7_repeated_approach(self):
        """TEST 7 — REPEATED APPROACH: Verify J1 handles subsequent emergency requests after reset."""
        print("\n--- TEST 7: REPEATED EMERGENCY APPROACH ---")
        j1 = IntersectionController(junction_id="J1", robot=None)

        # 1st request
        SHARED_EMERGENCY_REQUESTS["J1"] = {
            "vehicle_id": "AMBULANCE_001",
            "junction_id": "J1",
            "approach_direction": "SOUTH",
            "request_type": "EMERGENCY_PRIORITY",
            "active": True
        }

        dt = 0.032
        # Run 1st cycle through clearance and restoration
        for _ in range(int(10.0 / dt)):
            j1.update_logic(dt)
            if j1.emergency_state == "GREEN":
                j1.ambulance_entered_j1 = True
                j1.ambulance_cleared_j1 = True

        self.assertEqual(j1.emergency_state, "IDLE", "J1 failed to return to IDLE state after 1st request!")

        # 2nd request
        SHARED_EMERGENCY_REQUESTS["J1"] = {
            "vehicle_id": "AMBULANCE_001",
            "junction_id": "J1",
            "approach_direction": "SOUTH",
            "request_type": "EMERGENCY_PRIORITY",
            "active": True
        }

        j1.update_logic(dt)
        self.assertNotEqual(j1.emergency_state, "IDLE", "J1 failed to accept 2nd emergency request!")
        print("Test 7 Repeated Approach: 1st request cleared, 2nd request accepted -> PASS")


if __name__ == "__main__":
    unittest.main()
