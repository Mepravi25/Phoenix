"""
Unit Tests for JunctionController and IntersectionController (Module 2)
Verifies:
1. Signal lamp state transitions
2. Safe cycle logic (conflicting directions are never GREEN simultaneously)
3. All-Red safety phase implementation
4. Configurable timing values
5. Emergency override priority interface
"""

import os
import sys
import unittest

# Ensure webots controllers directory is on Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers", "junction_controller")))

from junction_controller import (
    IntersectionController,
    SignalPhase,
    LampState,
    Approach,
    SIGNAL_CONFIG
)


class TestJunctionController(unittest.TestCase):

    def setUp(self):
        self.config = {
            "green_duration": 15.0,
            "yellow_duration": 3.0,
            "all_red_duration": 1.0
        }
        self.controller = IntersectionController(junction_id="J1", robot=None, config=self.config)

    def test_initial_state(self):
        """Initial state should be NS_GREEN, with NS Green and EW Red."""
        self.assertEqual(self.controller.current_phase, SignalPhase.NS_GREEN)
        self.assertEqual(self.controller.signals[Approach.NORTH].current_state, LampState.GREEN)
        self.assertEqual(self.controller.signals[Approach.SOUTH].current_state, LampState.GREEN)
        self.assertEqual(self.controller.signals[Approach.EAST].current_state, LampState.RED)
        self.assertEqual(self.controller.signals[Approach.WEST].current_state, LampState.RED)

    def test_full_cycle(self):
        """Verify full safe signal cycle transitions and all-red safety buffer."""
        # Step through 15s NS Green -> NS Yellow
        self.controller.update_logic(15.0)
        self.assertEqual(self.controller.current_phase, SignalPhase.NS_YELLOW)
        self.assertEqual(self.controller.signals[Approach.NORTH].current_state, LampState.YELLOW)
        self.assertEqual(self.controller.signals[Approach.EAST].current_state, LampState.RED)

        # Step through 3s NS Yellow -> ALL RED 1
        self.controller.update_logic(3.0)
        self.assertEqual(self.controller.current_phase, SignalPhase.ALL_RED_NS_TO_EW)
        for app in Approach:
            self.assertEqual(self.controller.signals[app].current_state, LampState.RED)

        # Step through 1s ALL RED 1 -> EW Green
        self.controller.update_logic(1.0)
        self.assertEqual(self.controller.current_phase, SignalPhase.EW_GREEN)
        self.assertEqual(self.controller.signals[Approach.EAST].current_state, LampState.GREEN)
        self.assertEqual(self.controller.signals[Approach.WEST].current_state, LampState.GREEN)
        self.assertEqual(self.controller.signals[Approach.NORTH].current_state, LampState.RED)
        self.assertEqual(self.controller.signals[Approach.SOUTH].current_state, LampState.RED)

        # Step through 15s EW Green -> EW Yellow
        self.controller.update_logic(15.0)
        self.assertEqual(self.controller.current_phase, SignalPhase.EW_YELLOW)

        # Step through 3s EW Yellow -> ALL RED 2
        self.controller.update_logic(3.0)
        self.assertEqual(self.controller.current_phase, SignalPhase.ALL_RED_EW_TO_NS)
        for app in Approach:
            self.assertEqual(self.controller.signals[app].current_state, LampState.RED)

        # Step through 1s ALL RED 2 -> NS Green (Repeat)
        self.controller.update_logic(1.0)
        self.assertEqual(self.controller.current_phase, SignalPhase.NS_GREEN)

    def test_no_conflicting_greens(self):
        """Ensure North/South and East/West are NEVER GREEN at the same time."""
        total_test_time = 100.0  # test across multiple full cycles
        dt = 0.5
        t = 0.0
        while t < total_test_time:
            self.controller.update_logic(dt)
            ns_green = (self.controller.signals[Approach.NORTH].current_state == LampState.GREEN or
                        self.controller.signals[Approach.SOUTH].current_state == LampState.GREEN)
            ew_green = (self.controller.signals[Approach.EAST].current_state == LampState.GREEN or
                        self.controller.signals[Approach.WEST].current_state == LampState.GREEN)
            
            self.assertFalse(ns_green and ew_green, f"Conflict detected at t={t}: NS and EW are both GREEN!")
            t += dt

    def test_emergency_priority_interface(self):
        """Test emergency priority override request and clear."""
        # Request priority for NORTH approach
        res = self.controller.request_priority("NORTH", duration=10.0)
        self.assertTrue(res)
        self.assertTrue(self.controller.priority_active)
        self.assertEqual(self.controller.current_phase, SignalPhase.EMERGENCY_OVERRIDE)
        self.assertEqual(self.controller.signals[Approach.NORTH].current_state, LampState.GREEN)
        self.assertEqual(self.controller.signals[Approach.EAST].current_state, LampState.RED)

        # Update logic during priority override
        self.controller.update_logic(5.0)
        self.assertTrue(self.controller.priority_active)

        # Let priority expire
        self.controller.update_logic(6.0)
        self.assertFalse(self.controller.priority_active)
        # Should return to safe ALL_RED phase before normal cycle
        self.assertEqual(self.controller.current_phase, SignalPhase.ALL_RED_NS_TO_EW)


if __name__ == "__main__":
    unittest.main()
