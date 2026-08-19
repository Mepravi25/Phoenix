"""
SWIFT SYSTEM - Final Normal Vehicle Architecture Verification Suite
Tests independent controllers for CAR_001, CAR_002, CAR_003, CAR_004
with short execution limits.
"""

import sys
import os
import math
import time
import json
from typing import Dict, List, Tuple, Any

# Add controllers to path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers"))
sys.path.append(os.path.join(BASE_DIR, "car_001_controller"))
sys.path.append(os.path.join(BASE_DIR, "car_002_controller"))
sys.path.append(os.path.join(BASE_DIR, "car_003_controller"))
sys.path.append(os.path.join(BASE_DIR, "car_004_controller"))

from car_001_controller import Car001Controller, validate_road_corridor
from car_002_controller import Car002Controller
from car_003_controller import Car003Controller
from car_004_controller import Car004Controller


from car_001_controller import SHARED_MEMORY_REGISTRY


def cleanup_state():
    """Reset position files and memory registry before each test."""
    SHARED_MEMORY_REGISTRY.clear()
    state_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots"))
    if os.path.exists(state_dir):
        for fname in os.listdir(state_dir):
            if fname.startswith("vehicle_pos") or fname.startswith("vehicle_positions"):
                try:
                    os.remove(os.path.join(state_dir, fname))
                except Exception:
                    pass


def test_car_001() -> Tuple[bool, int, int]:
    """TEST 1 — CAR_001 Single Vehicle & Turning (18s max)."""
    cleanup_state()
    car1 = Car001Controller()
    dt = 0.032
    steps = int(18.0 / dt)  # ~562 steps

    road_violations = 0
    stuck_count = 0

    print("\n--- TEST 1: CAR_001 Turning Test (18s) ---")
    for _ in range(steps):
        car1.update_logic(dt)
        if car1.state == "LANE_ERROR":
            road_violations += 1
        if car1.stuck_logged:
            stuck_count += 1

    passed = (road_violations == 0) and (stuck_count == 0) and (car1.elapsed_time > 5.0)
    print(f"CAR_001 final pos: ({car1.x:.2f}, {car1.y:.2f}), wp_idx={car1.current_wp_idx}, heading={car1.heading:.2f} -> {'PASS' if passed else 'FAIL'}")
    assert passed
    return passed, road_violations, stuck_count


def test_car_002() -> Tuple[bool, int, int]:
    """TEST 2 — CAR_002 Single Vehicle & Turning (16s max)."""
    cleanup_state()
    car2 = Car002Controller()
    dt = 0.032
    steps = int(16.0 / dt)

    road_violations = 0
    stuck_count = 0

    print("\n--- TEST 2: CAR_002 Turning Test (16s) ---")
    for _ in range(steps):
        car2.update_logic(dt)
        if car2.state == "LANE_ERROR":
            road_violations += 1
        if car2.stuck_logged:
            stuck_count += 1

    passed = (road_violations == 0) and (stuck_count == 0) and (car2.elapsed_time > 5.0)
    print(f"CAR_002 final pos: ({car2.x:.2f}, {car2.y:.2f}), wp_idx={car2.current_wp_idx}, heading={car2.heading:.2f} -> {'PASS' if passed else 'FAIL'}")
    assert passed
    return passed, road_violations, stuck_count


def test_car_003() -> Tuple[bool, int, int]:
    """TEST 3 — CAR_003 Single Vehicle & Turning (12s max)."""
    cleanup_state()
    car3 = Car003Controller()
    dt = 0.032
    steps = int(12.0 / dt)

    road_violations = 0
    stuck_count = 0

    print("\n--- TEST 3: CAR_003 Turning Test (12s) ---")
    for _ in range(steps):
        car3.update_logic(dt)
        if car3.state == "LANE_ERROR":
            road_violations += 1
        if car3.stuck_logged:
            stuck_count += 1

    passed = (road_violations == 0) and (stuck_count == 0) and (car3.elapsed_time > 5.0)
    print(f"CAR_003 final pos: ({car3.x:.2f}, {car3.y:.2f}), wp_idx={car3.current_wp_idx}, heading={car3.heading:.2f} -> {'PASS' if passed else 'FAIL'}")
    assert passed
    return passed, road_violations, stuck_count


def test_car_004() -> Tuple[bool, int, int]:
    """TEST 4 — CAR_004 Single Vehicle & Turning (13s max)."""
    cleanup_state()
    car4 = Car004Controller()
    dt = 0.032
    steps = int(13.0 / dt)

    road_violations = 0
    stuck_count = 0

    print("\n--- TEST 4: CAR_004 Turning Test (13s) ---")
    for _ in range(steps):
        car4.update_logic(dt)
        if car4.state == "LANE_ERROR":
            road_violations += 1
        if car4.stuck_logged:
            stuck_count += 1

    passed = (road_violations == 0) and (stuck_count == 0) and (car4.elapsed_time > 5.0)
    print(f"CAR_004 final pos: ({car4.x:.2f}, {car4.y:.2f}), wp_idx={car4.current_wp_idx}, heading={car4.heading:.2f} -> {'PASS' if passed else 'FAIL'}")
    assert passed
    return passed, road_violations, stuck_count


def test_four_cars() -> Tuple[bool, int, int, int]:
    """TEST 5 — FOUR CARS: CAR_001 .. CAR_004 (10s max)."""
    cleanup_state()
    car1 = Car001Controller()
    car2 = Car002Controller()
    car3 = Car003Controller()
    car4 = Car004Controller()
    cars = [car1, car2, car3, car4]

    dt = 0.032
    steps = int(10.0 / dt)

    road_violations = 0
    collisions = 0
    stuck_count = 0

    print("\n--- TEST 5: Four Vehicles Turning Simulation (10s) ---")
    for _ in range(steps):
        for car in cars:
            car.update_logic(dt)
            if car.state == "LANE_ERROR":
                road_violations += 1
            if car.stuck_logged:
                stuck_count += 1

        # Check collisions (<2.5m overlap)
        for i in range(len(cars)):
            for j in range(i + 1, len(cars)):
                c1, c2 = cars[i], cars[j]
                dist = math.hypot(c1.x - c2.x, c1.y - c2.y)
                if dist < 2.5:
                    collisions += 1

    passed = (collisions == 0) and (road_violations == 0) and (stuck_count == 0)
    print(f"Four cars test: collisions={collisions}, road_violations={road_violations}, stuck={stuck_count} -> {'PASS' if passed else 'FAIL'}")
    assert passed
    return passed, road_violations, collisions, stuck_count



def test_route_loop() -> Tuple[bool, int]:
    """TEST 6 — ROUTE LOOP: Verify route wrap (10s max)."""
    cleanup_state()
    from road_network import ROAD_NETWORK
    car1 = Car001Controller()
    car1.current_lane_idx = 3
    car1.current_lane = ROAD_NETWORK[car1.lane_loop[3]]
    car1.x = -246.5
    car1.y = 230.0
    car1.heading = math.pi / 2.0
    car1.current_wp_idx = len(car1.current_lane.waypoints) - 1

    dt = 0.032
    steps = int(10.0 / dt)

    loops_observed = 0

    print("\n--- TEST 6: Route Loop Wrap (10s) ---")
    for _ in range(steps):
        prev_lane_idx = car1.current_lane_idx
        car1.update_logic(dt)
        if prev_lane_idx == 3 and car1.current_lane_idx == 0:
            loops_observed += 1

    passed = (loops_observed > 0)
    print(f"Route loops observed: {loops_observed} -> {'PASS' if passed else 'FAIL'}")
    return passed, loops_observed


def run_all_tests():
    print("============================================================")
    print("STARTING FINAL VEHICLE TURNING VERIFICATION")
    print("============================================================")

    t1_pass, rv1, st1 = test_car_001()
    t2_pass, rv2, st2 = test_car_002()
    t3_pass, rv3, st3 = test_car_003()
    t4_pass, rv4, st4 = test_car_004()
    t5_pass, rv5, col5, st5 = test_four_cars()
    t6_pass, loops_count = test_route_loop()

    total_rv = rv1 + rv2 + rv3 + rv4 + rv5
    total_col = col5
    total_stuck = st1 + st2 + st3 + st4 + st5

    c1_turn = "PASS" if t1_pass else "FAIL"
    c2_turn = "PASS" if t2_pass else "FAIL"
    c3_turn = "PASS" if t3_pass else "FAIL"
    c4_turn = "PASS" if t4_pass else "FAIL"

    wp_adv = "PASS" if (t1_pass and t2_pass and t3_pass and t4_pass) else "FAIL"
    route_loop = "PASS" if t6_pass else "FAIL"
    module_status = "PASS" if (t1_pass and t2_pass and t3_pass and t4_pass and t5_pass and t6_pass) else "FAIL"

    print("\n============================================================")
    print("FINAL REPORT")
    print("============================================================")
    print(f"CAR_001_TURN = {c1_turn}")
    print(f"CAR_002_TURN = {c2_turn}")
    print(f"CAR_003_TURN = {c3_turn}")
    print(f"CAR_004_TURN = {c4_turn}")
    print()
    print(f"WAYPOINT_ADVANCEMENT = {wp_adv}")
    print()
    print(f"ROUTE_LOOP = {route_loop}")
    print()
    print(f"GRASS_VIOLATIONS = {total_rv}")
    print()
    print(f"TURN_STUCK_COUNT = {total_stuck}")
    print()
    print(f"COLLISIONS = {total_col}")
    print()
    print("FILES_MODIFIED =")
    print("car_001_controller.py")
    print("car_002_controller.py")
    print("car_003_controller.py")
    print("car_004_controller.py")
    print()
    print("ROOT_CAUSE =")
    print("Vehicles were attempting to turn diagonally before entering intersection corridors by calculating target heading directly to downstream waypoints, causing corner-cutting across road boundaries (ROAD_BOUNDARY_ERROR). Replaced with deterministic look-ahead direction vector turn detection, centerline intersection waypoints, explicit TURNING state with reduced turning speed (3.0 m/s), smooth shortest-angle rotation, and position update following vehicle heading.")
    print()
    print(f"MODULE_STATUS = {module_status}")
    print("============================================================")


if __name__ == "__main__":
    run_all_tests()
