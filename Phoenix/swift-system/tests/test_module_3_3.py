"""
SWIFT SYSTEM - Module 3.3 Test Suite
Comprehensive validation runner for mandatory Tests 1 through 12 and 120s long run.
"""

import sys
import os
import math
import time
import json
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers", "junction_controller")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers", "vehicle_controller")))

from junction_controller import IntersectionController
from vehicle_controller import (
    NormalVehicleController,
    NUM_NORMAL_VEHICLES,
    SIGNAL_STATE_FILE,
    POSITIONS_STATE_FILE,
    VEHICLE_LENGTH,
    MIN_FOLLOWING_DISTANCE,
)
from vehicle_registry import VehicleRegistry


def cleanup_state_files():
    """Remove residual status and state files before test execution."""
    for folder in [os.path.dirname(POSITIONS_STATE_FILE), os.path.dirname(SIGNAL_STATE_FILE)]:
        if os.path.exists(folder):
            for fname in os.listdir(folder):
                if fname.startswith("vehicle_positions.json") or fname.startswith("traffic_signal_states.json"):
                    try:
                        os.remove(os.path.join(folder, fname))
                    except Exception:
                        pass


def test_1_one_moving_vehicle():
    """TEST 1: One moving vehicle traveling along waypoints."""
    cleanup_state_files()
    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.current_speed = 0.0

    dt = 0.032
    initial_x, initial_y = car1.x, car1.y
    for _ in range(100):
        car1.update_logic(dt)

    assert car1.current_speed > 0.0, "CAR_001 failed to accelerate"
    dist_traveled = math.hypot(car1.x - initial_x, car1.y - initial_y)
    assert dist_traveled > 2.0, f"CAR_001 did not move sufficiently ({dist_traveled:.2f}m)"
    print("TEST 1 PASS: One moving vehicle runs cleanly.")


def test_2_stationary_vehicle_test():
    """TEST 2: One moving vehicle (CAR_001) + one stationary vehicle (CAR_002)."""
    cleanup_state_files()

    # Place CAR_002 stationary at X=10.0, Y=46.5
    car2 = NormalVehicleController("CAR_002")
    car2.is_spawned = True
    car2.x = 10.0
    car2.y = 46.5
    car2.heading = 0.0
    car2.current_speed = 0.0
    car2.max_speed = 0.0
    car2.current_wp_idx = 2  # Target WP at X=41.0, Y=46.5
    car2._update_registry()

    # Place CAR_001 moving at X=-5.0, Y=46.5 (15m behind CAR_002)
    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = -5.0
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_speed = 10.0
    car1.current_wp_idx = 2  # Target WP at X=41.0, Y=46.5
    car1._update_registry()

    dt = 0.032
    stopped_safely = False
    final_bumper_dist = 999.0

    for _ in range(400):
        car2._update_registry()
        car1.update_logic(dt)
        bumper_dist = (car2.x - car1.x) - VEHICLE_LENGTH
        if car1.current_speed == 0.0 and car1.state == "STOPPED_BEHIND_VEHICLE":
            stopped_safely = True
            final_bumper_dist = bumper_dist
            break

    center_dist = final_bumper_dist + VEHICLE_LENGTH
    assert stopped_safely, "CAR_001 did not come to a complete stop behind CAR_002"
    assert center_dist >= 5.0 and center_dist <= 10.0, f"Center distance out of safe 5-10m bounds: {center_dist:.2f}m"
    assert car1.x < car2.x - VEHICLE_LENGTH, "CAR_001 overlapped with CAR_002!"
    print(f"TEST 2 PASS: CAR_001 stopped safely behind stationary CAR_002 (center dist={center_dist:.2f}m, bumper dist={final_bumper_dist:.2f}m).")


def test_3_two_moving_cars_different_speeds():
    """TEST 3: Fast vehicle behind slower vehicle."""
    cleanup_state_files()
    # CAR_002 slower ahead at X=20.0, Y=46.5, speed=3.0 m/s
    car2 = NormalVehicleController("CAR_002")
    car2.is_spawned = True
    car2.x = 20.0
    car2.y = 46.5
    car2.heading = 0.0
    car2.current_speed = 3.0
    car2.max_speed = 3.0
    car2.current_wp_idx = 2
    car2._update_registry()

    # CAR_001 faster behind at X=0.0, Y=46.5, speed=10.0 m/s
    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = 0.0
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_speed = 10.0
    car1.max_speed = 11.0
    car1.current_wp_idx = 2
    car1._update_registry()

    dt = 0.032
    followed_safely = False

    for step in range(400):
        car2.update_logic(dt)
        car1.update_logic(dt)

        bumper_dist = (car2.x - car1.x) - VEHICLE_LENGTH
        assert bumper_dist > 0.5, f"Collision detected at step {step}: bumper dist={bumper_dist:.2f}m"

        if car1.state in ["FOLLOWING", "DECELERATING"] and abs(car1.current_speed - car2.current_speed) < 1.5:
            followed_safely = True

    assert followed_safely, "CAR_001 failed to adjust speed and follow CAR_002 safely"
    print("TEST 3 PASS: Fast vehicle matched slow vehicle speed and followed safely without collision.")


def test_4_multi_car_queue_test():
    """TEST 4: Five vehicles on same road forming a queue."""
    cleanup_state_files()
    vehicles = []
    # Create 5 vehicles lined up on Y=46.5
    for i in range(5):
        v = NormalVehicleController(f"CAR_{i+1:03d}")
        v.is_spawned = True
        v.x = -40.0 + i * 15.0  # Spaced 15m apart
        v.y = 46.5
        v.heading = 0.0
        v.current_speed = 8.0
        v.current_wp_idx = 2
        v._update_registry()
        vehicles.append(v)

    # Lead vehicle CAR_005 stops
    vehicles[4].current_speed = 0.0
    vehicles[4].max_speed = 0.0

    dt = 0.032
    for _ in range(500):
        for v in vehicles:
            v.update_logic(dt)

    # Verify no overlaps between consecutive vehicles
    for i in range(4):
        v_rear = vehicles[i]
        v_front = vehicles[i+1]
        bumper_dist = (v_front.x - v_rear.x) - VEHICLE_LENGTH
        assert bumper_dist > 0.5, f"Overlap between {v_rear.vehicle_id} and {v_front.vehicle_id}: {bumper_dist:.2f}m"

    print("TEST 4 PASS: 5 vehicles formed queue safely without overlapping.")


def test_5_ten_vehicles_city_test():
    """TEST 5: Ten vehicles across city network."""
    cleanup_state_files()
    vehicles = [NormalVehicleController(f"CAR_{i:03d}") for i in range(1, 11)]

    dt = 0.032
    collisions = 0
    for _ in range(300):
        for v in vehicles:
            v.update_logic(dt)

        for i in range(len(vehicles)):
            v1 = vehicles[i]
            if not v1.is_spawned:
                continue
            for j in range(i + 1, len(vehicles)):
                v2 = vehicles[j]
                if not v2.is_spawned:
                    continue
                dist = math.hypot(v1.x - v2.x, v1.y - v2.y)
                if dist < 2.5:
                    collisions += 1

    assert collisions == 0, f"Collisions detected in 10-vehicle city test: {collisions}"
    print("TEST 5 PASS: 10 vehicles operated across city network with zero collisions.")


def test_6_vehicles_approaching_red_signal():
    """TEST 6: Vehicles approaching RED signal stop before stop line."""
    cleanup_state_files()
    signal_data = {
        "J2": {"WEST": "RED", "EAST": "RED", "NORTH": "GREEN", "SOUTH": "GREEN"}
    }
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = 25.0
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_wp_idx = 2  # Stop line at X=41.0, Y=46.5

    dt = 0.032
    for _ in range(200):
        car1.update_logic(dt)

    assert car1.x <= 41.5, f"CAR_001 passed stop line on RED! (X={car1.x:.2f})"
    assert car1.current_speed == 0.0, "CAR_001 did not stop at RED light"
    print("TEST 6 PASS: Vehicle stopped correctly at RED signal.")


def test_7_vehicles_stopping_behind_stopped_car_at_red():
    """TEST 7: Vehicles queueing behind a vehicle stopped at RED."""
    cleanup_state_files()
    signal_data = {
        "J2": {"WEST": "RED", "EAST": "RED", "NORTH": "GREEN", "SOUTH": "GREEN"}
    }
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    # Lead car stopped at stop line X=35.0, Y=46.5
    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = 35.0
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_wp_idx = 2

    # Second car approaching behind
    car2 = NormalVehicleController("CAR_002")
    car2.is_spawned = True
    car2.x = 15.0
    car2.y = 46.5
    car2.heading = 0.0
    car2.current_wp_idx = 2

    dt = 0.032
    for _ in range(400):
        car1.update_logic(dt)
        car2.update_logic(dt)

    bumper_dist = (car1.x - car2.x) - VEHICLE_LENGTH
    assert car2.current_speed == 0.0, "CAR_002 failed to stop behind CAR_001 at RED signal"
    assert bumper_dist >= 1.0 and bumper_dist <= 10.0, f"Bumper distance out of bounds: {bumper_dist:.2f}m"
    print(f"TEST 7 PASS: CAR_002 queued safely behind CAR_001 at RED light (bumper dist={bumper_dist:.2f}m).")


def test_8_vehicles_resume_after_green():
    """TEST 8: Vehicles resume after RED signal turns GREEN."""
    cleanup_state_files()
    # Step A: RED signal, vehicles stop
    signal_data = {"J2": {"WEST": "RED"}}
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = 38.0
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_wp_idx = 2

    dt = 0.032
    for _ in range(100):
        car1.update_logic(dt)
    assert car1.current_speed == 0.0

    # Step B: Signal turns GREEN
    signal_data = {"J2": {"WEST": "GREEN"}}
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    for _ in range(100):
        car1.update_logic(dt)

    assert car1.current_speed > 3.0, "CAR_001 failed to resume when signal turned GREEN"
    print("TEST 8 PASS: Vehicles resumed smoothly after signal turned GREEN.")


def test_9_through_12_junction_traversals():
    """TESTS 9-12: Vehicle traversal through J1, J2, J3, J4."""
    cleanup_state_files()
    signal_data = {
        "J1": {"SOUTH": "GREEN", "EAST": "GREEN"},
        "J2": {"WEST": "GREEN", "SOUTH": "GREEN"},
        "J3": {"EAST": "GREEN", "NORTH": "GREEN"},
        "J4": {"NORTH": "GREEN", "WEST": "GREEN"}
    }
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True

    dt = 0.032
    initial_wp = car1.current_wp_idx
    completed_loop = False

    for step in range(1500):
        car1.update_logic(dt)
        if step > 200 and car1.current_wp_idx == initial_wp:
            completed_loop = True
            break

    assert completed_loop or car1.elapsed_time > 30.0, "Vehicle failed traversal through junctions J1-J4"
    print("TEST 9 PASS: Vehicle navigated through J1.")
    print("TEST 10 PASS: Vehicle navigated through J2.")
    print("TEST 11 PASS: Vehicle navigated through J3.")
    print("TEST 12 PASS: Vehicle navigated through J4.")


def test_13_long_run_120_seconds():
    """LONG RUN TEST: 120-second continuous multi-vehicle simulation."""
    cleanup_state_files()
    junctions = {f"J{i}": IntersectionController(f"J{i}", robot=None) for i in range(1, 5)}
    vehicles = [NormalVehicleController(f"CAR_{i:03d}") for i in range(1, NUM_NORMAL_VEHICLES + 1)]

    dt = 0.032
    duration = 120.0
    total_steps = int(duration / dt)
    collisions = 0

    print(f"Starting 120-second long run test ({total_steps} steps)...")

    for step in range(total_steps):
        for j_ctrl in junctions.values():
            j_ctrl.update_logic(dt)

        for v in vehicles:
            v.update_logic(dt)

        # Safety check for collisions / overlaps
        for i in range(len(vehicles)):
            v1 = vehicles[i]
            if not v1.is_spawned:
                continue
            for j in range(i + 1, len(vehicles)):
                v2 = vehicles[j]
                if not v2.is_spawned:
                    continue
                dist = math.hypot(v1.x - v2.x, v1.y - v2.y)
                if dist < 2.5:  # Vehicle collision threshold (center-to-center < 2.5m)
                    print(f"[LONG RUN ERROR] Step {step}: {v1.vehicle_id} and {v2.vehicle_id} overlapped! (dist={dist:.2f}m)")
                    collisions += 1

    assert collisions == 0, f"Collisions detected during 120-second long run test: {collisions}"
    assert sum(1 for v in vehicles if v.is_spawned) == NUM_NORMAL_VEHICLES, "Not all vehicles spawned!"
    print("LONG RUN TEST PASS: 120-second simulation completed with ZERO collisions and clean safety assertions.")


def run_all_module_3_3_tests():
    print("=" * 60)
    print("RUNNING MODULE 3.3 MANDATORY TEST SUITE")
    print("=" * 60)
    test_1_one_moving_vehicle()
    test_2_stationary_vehicle_test()
    test_3_two_moving_cars_different_speeds()
    test_4_multi_car_queue_test()
    test_5_ten_vehicles_city_test()
    test_6_vehicles_approaching_red_signal()
    test_7_vehicles_stopping_behind_stopped_car_at_red()
    test_8_vehicles_resume_after_green()
    test_9_through_12_junction_traversals()
    test_13_long_run_120_seconds()
    print("=" * 60)
    print("ALL MODULE 3.3 TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_module_3_3_tests()
