"""
SWIFT SYSTEM - Module 3.4 Automated Test Suite
Executes 8 short, deterministic vehicle movement, safety, and deadlock tests (TEST A through TEST H):
1. TEST A - Stationary vehicle safety stop
2. TEST B - Moving vehicle following
3. TEST C - Opposite lane isolation
4. TEST D - 5-vehicle queue formation
5. TEST E - 10-vehicle city traffic pass-through check
6. TEST F - Vehicles stopping at RED signal
7. TEST G - Vehicles resuming on GREEN signal
8. TEST H - Waypoint progression assignment
"""

import sys
import os
import math
import time
import json
from typing import Dict, Tuple, List, Any, Optional

# Setup import paths
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
    VEHICLE_CONFIGS,
    get_clockwise_route_waypoints,
    get_counter_clockwise_route_waypoints,
)
from vehicle_registry import VehicleRegistry, VEHICLE_LENGTH


def cleanup_state_files():
    """Removes residual position and signal JSON state files and resets shared registry."""
    VehicleRegistry().clear()
    for folder in [os.path.dirname(POSITIONS_STATE_FILE), os.path.dirname(SIGNAL_STATE_FILE)]:
        if os.path.exists(folder):
            for fname in os.listdir(folder):
                if fname.startswith("vehicle_positions") or fname.startswith("traffic_signal"):
                    try:
                        os.remove(os.path.join(folder, fname))
                    except Exception:
                        pass


def create_test_vehicle(
    vehicle_id: str,
    x: float,
    y: float,
    heading: float = 0.0,
    speed: float = 0.0,
    max_speed: float = 11.0,
    waypoints: Optional[List[Dict[str, Any]]] = None,
    wp_idx: int = 1,
) -> NormalVehicleController:
    """Helper to instantiate and register a test vehicle at isolated test coordinates."""
    v = NormalVehicleController(vehicle_id)
    if waypoints is not None:
        v.waypoints = waypoints
    v.current_wp_idx = wp_idx
    v.x = x
    v.y = y
    v.heading = heading
    v.current_speed = speed
    v.max_speed = max_speed
    v.is_spawned = True
    v.state = VehicleState.DRIVING if speed > 0 else VehicleState.STOPPED_BEHIND_VEHICLE
    v.last_position = (x, y)
    v.last_progress_time = 0.0
    v._update_registry()
    return v


def run_test_a_stationary() -> Tuple[str, List[str]]:
    """
    TEST A: CAR_001 moving, CAR_002 stationary in same lane.
    Expected: CAR_001 stops safely without collision.
    """
    cleanup_state_files()
    logs = ["Running TEST A — Stationary Vehicle Safety Stop..."]

    eastbound_wps = [
        {"x": -50.0, "y": 46.5, "target_j": None, "approach": None, "is_stop_line": False},
        {"x": 100.0, "y": 46.5, "target_j": None, "approach": None, "is_stop_line": False},
    ]

    car2 = create_test_vehicle("TA_CAR_002", x=15.0, y=46.5, heading=0.0, speed=0.0, max_speed=0.0, waypoints=eastbound_wps, wp_idx=1)
    car1 = create_test_vehicle("TA_CAR_001", x=-10.0, y=46.5, heading=0.0, speed=8.0, max_speed=11.0, waypoints=eastbound_wps, wp_idx=1)

    dt = 0.032
    stopped_safely = False
    collision = False

    for _ in range(400):
        car2._update_registry()
        car1.update_logic(dt)
        bumper_dist = (car2.x - car1.x) - VEHICLE_LENGTH

        if bumper_dist < -0.1:
            collision = True
            break
        if car1.current_speed <= 0.1 and car1.state in [VehicleState.STOPPED_BEHIND_VEHICLE, VehicleState.WAITING_FOR_CLEARANCE]:
            stopped_safely = True
            break

    center_dist = car2.x - car1.x
    passed = stopped_safely and not collision and (center_dist >= 5.0 and center_dist <= 12.0)
    status = "PASS" if passed else "FAIL"
    logs.append(f"  Stopped safely: {stopped_safely}, No collision: {not collision}, Center dist: {center_dist:.2f}m")
    logs.append(f"TEST A RESULT: {status}")
    return status, logs


def run_test_b_following() -> Tuple[str, List[str]]:
    """
    TEST B: CAR_001 faster behind CAR_002 slower.
    Expected: CAR_001 slows down and follows CAR_002 safely.
    """
    cleanup_state_files()
    logs = ["Running TEST B — Moving Vehicle Following..."]

    eastbound_wps = [
        {"x": -50.0, "y": 46.5, "target_j": None, "approach": None, "is_stop_line": False},
        {"x": 100.0, "y": 46.5, "target_j": None, "approach": None, "is_stop_line": False},
    ]

    car2 = create_test_vehicle("TB_CAR_002", x=20.0, y=46.5, heading=0.0, speed=3.0, max_speed=3.0, waypoints=eastbound_wps, wp_idx=1)
    car1 = create_test_vehicle("TB_CAR_001", x=0.0, y=46.5, heading=0.0, speed=10.0, max_speed=11.0, waypoints=eastbound_wps, wp_idx=1)

    dt = 0.032
    followed_safely = False
    collision = False

    for _ in range(200):
        car2.update_logic(dt)
        car1.update_logic(dt)

        bumper_dist = (car2.x - car1.x) - VEHICLE_LENGTH
        if bumper_dist < -0.1:
            collision = True
            break
        if car1.state in [VehicleState.FOLLOWING_VEHICLE, VehicleState.DECELERATING] and abs(car1.current_speed - car2.current_speed) < 2.0:
            followed_safely = True

    passed = followed_safely and not collision
    status = "PASS" if passed else "FAIL"
    logs.append(f"  Followed safely: {followed_safely}, No collision: {not collision}")
    logs.append(f"TEST B RESULT: {status}")
    return status, logs


def run_test_c_opposite_lane() -> Tuple[str, List[str]]:
    """
    TEST C: CAR_001 (Eastbound on Y=46.5) and CAR_002 (Westbound on Y=53.5).
    Expected: No false collision stop; vehicles pass each other freely.
    """
    cleanup_state_files()
    logs = ["Running TEST C — Opposite Lane Isolation..."]

    eastbound_wps = [
        {"x": -50.0, "y": 46.5, "target_j": None, "approach": None, "is_stop_line": False},
        {"x": 100.0, "y": 46.5, "target_j": None, "approach": None, "is_stop_line": False},
    ]
    westbound_wps = [
        {"x": 100.0, "y": 53.5, "target_j": None, "approach": None, "is_stop_line": False},
        {"x": -50.0, "y": 53.5, "target_j": None, "approach": None, "is_stop_line": False},
    ]

    car1 = create_test_vehicle("TC_CAR_001", x=0.0, y=46.5, heading=0.0, speed=8.0, max_speed=11.0, waypoints=eastbound_wps, wp_idx=1)
    car2 = create_test_vehicle("TC_CAR_002", x=30.0, y=53.5, heading=math.pi, speed=8.0, max_speed=11.0, waypoints=westbound_wps, wp_idx=1)

    dt = 0.032
    false_stops = 0

    for _ in range(200):
        car1.update_logic(dt)
        car2.update_logic(dt)

        if car1.state in [VehicleState.STOPPED_BEHIND_VEHICLE, VehicleState.WAITING_FOR_CLEARANCE]:
            false_stops += 1

    passed = (false_stops == 0 and car1.current_speed > 5.0)
    status = "PASS" if passed else "FAIL"
    logs.append(f"  False collision stops: {false_stops}, Speed maintained: {car1.current_speed > 5.0}")
    logs.append(f"TEST C RESULT: {status}")
    return status, logs


def run_test_d_five_car_queue() -> Tuple[str, List[str]]:
    """
    TEST D: 5 vehicles in same lane lined up behind a stationary lead.
    Expected: Safe queue formed with zero overlap.
    """
    cleanup_state_files()
    logs = ["Running TEST D — 5-Vehicle Queue Formation..."]

    eastbound_wps = [
        {"x": -50.0, "y": 46.5, "target_j": None, "approach": None, "is_stop_line": False},
        {"x": 100.0, "y": 46.5, "target_j": None, "approach": None, "is_stop_line": False},
    ]

    vehicles = []
    for i in range(5):
        speed = 0.0 if i == 4 else 8.0
        max_sp = 0.0 if i == 4 else 11.0
        v = create_test_vehicle(
            f"TD_CAR_{i+1:03d}",
            x=-40.0 + i * 15.0,
            y=46.5,
            heading=0.0,
            speed=speed,
            max_speed=max_sp,
            waypoints=eastbound_wps,
            wp_idx=1
        )
        vehicles.append(v)

    dt = 0.032
    overlaps = 0

    for _ in range(400):
        for v in vehicles:
            v.update_logic(dt)

        for i in range(4):
            v_rear = vehicles[i]
            v_front = vehicles[i+1]
            dist = math.hypot(v_front.x - v_rear.x, v_front.y - v_rear.y)
            if dist < 2.5:
                overlaps += 1

    passed = (overlaps == 0)
    status = "PASS" if passed else "FAIL"
    logs.append(f"  Queue overlaps detected: {overlaps}")
    logs.append(f"TEST D RESULT: {status}")
    return status, logs


def run_test_e_ten_vehicles_city() -> Tuple[str, List[str]]:
    """
    TEST E: 10 vehicles across city.
    Expected: Zero pass-through or collisions.
    """
    cleanup_state_files()
    logs = ["Running TEST E — 10-Vehicle City Traffic..."]

    vehicles = [NormalVehicleController(f"TE_CAR_{i:03d}") for i in range(1, 11)]
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

    passed = (collisions == 0)
    status = "PASS" if passed else "FAIL"
    logs.append(f"  Total city collisions: {collisions}")
    logs.append(f"TEST E RESULT: {status}")
    return status, logs


def run_test_f_red_signal() -> Tuple[str, List[str]]:
    """
    TEST F: Vehicles approaching RED signal.
    Expected: All vehicles stop before stop line.
    """
    cleanup_state_files()
    logs = ["Running TEST F — RED Signal Stop..."]

    signal_data = {"J2": {"WEST": "RED"}}
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    route_wps = get_clockwise_route_waypoints()
    car1 = create_test_vehicle("TF_CAR_001", x=25.0, y=46.5, heading=0.0, speed=8.0, max_speed=11.0, waypoints=route_wps, wp_idx=2)

    dt = 0.032
    for _ in range(200):
        car1.update_logic(dt)

    stopped_before_line = car1.x <= 41.5 and car1.current_speed == 0.0
    passed = stopped_before_line
    status = "PASS" if passed else "FAIL"
    logs.append(f"  Stopped before line: {stopped_before_line} (X={car1.x:.2f})")
    logs.append(f"TEST F RESULT: {status}")
    return status, logs


def run_test_g_green_resumption() -> Tuple[str, List[str]]:
    """
    TEST G: RED -> GREEN signal transition.
    Expected: Stopped vehicle resumes driving smoothly.
    """
    cleanup_state_files()
    logs = ["Running TEST G — GREEN Signal Resumption..."]

    signal_data = {"J2": {"WEST": "RED"}}
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    route_wps = get_clockwise_route_waypoints()
    car1 = create_test_vehicle("TG_CAR_001", x=38.0, y=46.5, heading=0.0, speed=0.0, max_speed=11.0, waypoints=route_wps, wp_idx=2)

    dt = 0.032
    for _ in range(100):
        car1.update_logic(dt)

    assert car1.current_speed == 0.0, "Vehicle failed to stop on RED"

    # Switch signal to GREEN
    signal_data = {"J2": {"WEST": "GREEN"}}
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    for _ in range(100):
        car1.update_logic(dt)

    resumed = car1.current_speed > 3.0
    passed = resumed
    status = "PASS" if passed else "FAIL"
    logs.append(f"  Resumed on GREEN: {resumed} (speed={car1.current_speed:.2f}m/s)")
    logs.append(f"TEST G RESULT: {status}")
    return status, logs


def run_test_h_waypoint_progression() -> Tuple[str, List[str]]:
    """
    TEST H: Vehicle completes waypoint.
    Expected: Next waypoint assigned cleanly without getting stuck.
    """
    cleanup_state_files()
    logs = ["Running TEST H — Waypoint Progression Assignment..."]

    route_wps = get_clockwise_route_waypoints()
    car1 = create_test_vehicle("TH_CAR_001", x=-40.0, y=46.5, heading=0.0, speed=8.0, max_speed=11.0, waypoints=route_wps, wp_idx=0)

    dt = 0.032
    initial_wp = car1.current_wp_idx

    for _ in range(150):
        car1.update_logic(dt)

    advanced = car1.current_wp_idx != initial_wp
    passed = advanced
    status = "PASS" if passed else "FAIL"
    logs.append(f"  Waypoint advanced: {advanced} (WP_{initial_wp} -> WP_{car1.current_wp_idx})")
    logs.append(f"TEST H RESULT: {status}")
    return status, logs


def main():
    print("=" * 60)
    print("SWIFT SYSTEM — MODULE 3.4 AUTOMATED TEST SUITE")
    print("=" * 60)

    results = {}
    all_logs = []

    for name, func in [
        ("TEST_A", run_test_a_stationary),
        ("TEST_B", run_test_b_following),
        ("TEST_C", run_test_c_opposite_lane),
        ("TEST_D", run_test_d_five_car_queue),
        ("TEST_E", run_test_e_ten_vehicles_city),
        ("TEST_F", run_test_f_red_signal),
        ("TEST_G", run_test_g_green_resumption),
        ("TEST_H", run_test_h_waypoint_progression),
    ]:
        status, logs = func()
        results[name] = status
        for l in logs:
            print(l)
            all_logs.append(l)
        print("-" * 60)

    print("MODULE 3.4 AUTOMATED TEST SUMMARY:")
    for k, v in results.items():
        print(f"{k} = {v}")
    print("=" * 60)


if __name__ == "__main__":
    main()
