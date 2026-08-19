"""
SWIFT SYSTEM - Module 3 Final Fast Verification Suite
Executes 5 deterministic, short safety and release tests (<10 seconds per test):
- TEST 1: Free Driving (CAR_001)
- TEST 2: Vehicle Following (CAR_001 behind stationary CAR_002)
- TEST 3: Vehicle Resume (CAR_002 moves away -> CAR_001 resumes)
- TEST 4: Traffic Signal Red Stop & Green Resume
- TEST 5: Three-Vehicle Concurrent Traffic (CAR_001, CAR_002, CAR_003)
"""

import sys
import os
import math
import time
import json
from typing import Dict, Tuple, List, Any

# Add controller directories to sys.path
CONTROLLER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers", "vehicle_controller"))
JUNCTION_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers", "junction_controller"))

if CONTROLLER_DIR not in sys.path:
    sys.path.append(CONTROLLER_DIR)
if JUNCTION_DIR not in sys.path:
    sys.path.append(JUNCTION_DIR)

from vehicle_controller import (
    NormalVehicleController,
    VehicleState,
    VEHICLE_CENTER_Z,
    ROAD_SURFACE_Z,
    POSITIONS_STATE_FILE,
    SIGNAL_STATE_FILE,
)
from vehicle_registry import VehicleRegistry, VEHICLE_LENGTH, MIN_FOLLOWING_DISTANCE


def cleanup_state_files():
    """Clean up registry and signal state files before each test."""
    VehicleRegistry().clear()
    for filepath in [POSITIONS_STATE_FILE, SIGNAL_STATE_FILE]:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass


def run_test_1_free_driving() -> bool:
    """TEST 1: Free Driving — CAR_001 moves continuously with no obstacle."""
    cleanup_state_files()
    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = -35.0
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_speed = 0.0
    car1.current_wp_idx = 1
    car1._update_registry()

    dt = 0.032
    initial_x = car1.x
    for _ in range(200):  # ~6.4s simulation time
        car1.update_logic(dt)

    dist_traveled = car1.x - initial_x
    pass_cond = (dist_traveled > 10.0) and (car1.current_speed > 5.0) and (car1.state in ["DRIVING", "FOLLOWING_VEHICLE"])
    print(f"[TEST 1] Free Driving: dist={dist_traveled:.2f}m, speed={car1.current_speed:.2f}m/s -> {'PASS' if pass_cond else 'FAIL'}")
    return pass_cond


def run_test_2_following() -> Tuple[bool, int]:
    """TEST 2: Vehicle Following — CAR_001 stops safely behind stationary CAR_002 without collision."""
    cleanup_state_files()

    # Place CAR_002 stationary at X=15.0, Y=46.5
    car2 = NormalVehicleController("CAR_002")
    car2.is_spawned = True
    car2.x = 15.0
    car2.y = 46.5
    car2.heading = 0.0
    car2.current_speed = 0.0
    car2.max_speed = 0.0
    car2.current_wp_idx = 2
    car2._update_registry()

    # Place CAR_001 moving at X=-5.0, Y=46.5 (20m center dist, 15.5m bumper gap)
    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = -5.0
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_speed = 10.0
    car1.current_wp_idx = 2
    car1._update_registry()

    dt = 0.032
    collisions = 0

    for _ in range(250):  # ~8.0s simulation time
        car2._update_registry()
        car1.update_logic(dt)

        center_dist = math.hypot(car2.x - car1.x, car2.y - car1.y)
        if center_dist < 2.5:
            collisions += 1

    bumper_dist = (car2.x - car1.x) - VEHICLE_LENGTH
    pass_cond = (collisions == 0) and (car1.current_speed == 0.0) and (car1.x < car2.x - VEHICLE_LENGTH) and (bumper_dist >= 1.0)
    print(f"[TEST 2] Following: bumper_gap={bumper_dist:.2f}m, speed={car1.current_speed:.2f}m/s, collisions={collisions} -> {'PASS' if pass_cond else 'FAIL'}")
    return pass_cond, collisions


def run_test_3_resume() -> bool:
    """TEST 3: Vehicle Resume — CAR_002 moves away, CAR_001 automatically resumes driving."""
    cleanup_state_files()

    # Clear signal state to GREEN for test
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump({"J2": {"WEST": "GREEN"}}, f)

    # Place CAR_002 stationary at X=10.0, Y=46.5
    car2 = NormalVehicleController("CAR_002")
    car2.is_spawned = True
    car2.x = 10.0
    car2.y = 46.5
    car2.heading = 0.0
    car2.current_speed = 0.0
    car2.max_speed = 0.0
    car2.current_wp_idx = 1
    car2._update_registry()

    # Place CAR_001 stopped behind CAR_002 at X=1.5, Y=46.5 (bumper gap = 4.0m)
    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = 1.5
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_speed = 0.0
    car1.state = VehicleState.STOPPED_BEHIND_VEHICLE
    car1.current_wp_idx = 1
    car1._update_registry()

    dt = 0.032
    # Register both cars before step logic
    car2._update_registry()
    car1._update_registry()

    car1.update_logic(dt)
    is_initially_stopped = (car1.current_speed == 0.0)

    # Step A: Move CAR_002 forward to X=40.0m (path cleared!)
    car2.x = 40.0
    car2._update_registry()

    # Step B: Advance CAR_001 logic for ~5 seconds
    for _ in range(150):
        car2._update_registry()
        car1.update_logic(dt)

    pass_cond = is_initially_stopped and (car1.current_speed > 3.0) and (car1.x > 8.0) and (car1.state in ["DRIVING", "FOLLOWING_VEHICLE"])
    print(f"[TEST 3] Resume: initially_stopped={is_initially_stopped}, final_speed={car1.current_speed:.2f}m/s, x={car1.x:.2f}m -> {'PASS' if pass_cond else 'FAIL'}")
    return pass_cond


def run_test_4_red_green() -> bool:
    """TEST 4: Red/Green — Vehicle stops at RED signal, resumes when signal turns GREEN."""
    cleanup_state_files()

    # Set J2 WEST signal to RED
    signal_data = {"J2": {"WEST": "RED"}}
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = 25.0
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_speed = 8.0
    car1.current_wp_idx = 2  # Stop line WP at X=41.0, Y=46.5
    car1._update_registry()

    dt = 0.032
    # Phase A: Approach RED light for 150 steps (~4.8s)
    for _ in range(150):
        car1.update_logic(dt)

    stopped_at_red = (car1.current_speed == 0.0) and (car1.x <= 41.5)

    # Phase B: Change J2 WEST signal to GREEN
    signal_data["J2"]["WEST"] = "GREEN"
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    # Step logic for 150 steps (~4.8s)
    for _ in range(150):
        car1.update_logic(dt)

    resumed_on_green = (car1.current_speed > 3.0) and (car1.x > 41.0)
    pass_cond = stopped_at_red and resumed_on_green
    print(f"[TEST 4] Red/Green: stopped_at_red={stopped_at_red}, resumed_on_green={resumed_on_green} -> {'PASS' if pass_cond else 'FAIL'}")
    return pass_cond


def run_test_5_three_vehicles() -> Tuple[bool, int, int]:
    """TEST 5: Three Vehicles — Concurrent execution of CAR_001, CAR_002, CAR_003 for 10s (~300 steps)."""
    cleanup_state_files()

    car1 = NormalVehicleController("CAR_001")
    car2 = NormalVehicleController("CAR_002")
    car3 = NormalVehicleController("CAR_003")

    vehicles = [car1, car2, car3]
    dt = 0.032
    steps = 300  # ~9.6 seconds

    collisions = 0
    stuck_cars = 0

    for step in range(steps):
        for v in vehicles:
            v.update_logic(dt)

        # Check pairwise collisions
        for i in range(len(vehicles)):
            for j in range(i + 1, len(vehicles)):
                v1, v2 = vehicles[i], vehicles[j]
                if v1.is_spawned and v2.is_spawned:
                    dist = math.hypot(v1.x - v2.x, v1.y - v2.y)
                    if dist < 2.5:
                        collisions += 1

    for v in vehicles:
        if v.stuck_logged:
            stuck_cars += 1

    pass_cond = (collisions == 0) and (stuck_cars == 0)
    print(f"[TEST 5] Three Vehicles: collisions={collisions}, stuck={stuck_cars} -> {'PASS' if pass_cond else 'FAIL'}")
    return pass_cond, collisions, stuck_cars


def execute_all_tests():
    print("=" * 60)
    print("MODULE 3 FINAL — SHORT VERIFICATION SUITE RUNNER")
    print("=" * 60)

    t1_pass = run_test_1_free_driving()
    t2_pass, c2 = run_test_2_following()
    t3_pass = run_test_3_resume()
    t4_pass = run_test_4_red_green()
    t5_pass, c5, stuck5 = run_test_5_three_vehicles()

    total_collisions = c2 + c5
    module_3_pass = t1_pass and t2_pass and t3_pass and t4_pass and t5_pass

    print("=" * 60)
    print("SUMMARY RESULTS:")
    print(f"FREE_DRIVING: {'PASS' if t1_pass else 'FAIL'}")
    print(f"FOLLOWING: {'PASS' if t2_pass else 'FAIL'}")
    print(f"RESUME: {'PASS' if t3_pass else 'FAIL'}")
    print(f"RED_GREEN: {'PASS' if t4_pass else 'FAIL'}")
    print(f"THREE_VEHICLES: {'PASS' if t5_pass else 'FAIL'}")
    print(f"COLLISION_COUNT: {total_collisions}")
    print(f"STUCK_VEHICLES: {stuck5}")
    print(f"MODULE_3_STATUS: {'PASS' if module_3_pass else 'FAIL'}")
    print("=" * 60)


if __name__ == "__main__":
    execute_all_tests()
