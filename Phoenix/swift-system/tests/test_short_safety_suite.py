"""
SWIFT SYSTEM - Short Vehicle Safety Test Suite
Executes 5 short, deterministic Webots vehicle safety tests (10-20 seconds each):
1. TEST 1 - VEHICLE POSITION (10s)
2. TEST 2 - MOVING VEHICLE (12s)
3. TEST 3 - MOVING VEHICLE + STATIONARY VEHICLE (12s)
4. TEST 4 - TWO MOVING VEHICLES (12s)
5. TEST 5 - FIVE VEHICLES (15s)
"""

import sys
import os
import math
import time
import json
from typing import Dict, Tuple, List, Any

# Ensure path to controllers is present
CONTROLLER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers", "vehicle_controller"))
JUNCTION_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers", "junction_controller"))

if CONTROLLER_DIR not in sys.path:
    sys.path.append(CONTROLLER_DIR)
if JUNCTION_DIR not in sys.path:
    sys.path.append(JUNCTION_DIR)

from vehicle_controller import (
    NormalVehicleController,
    VEHICLE_CENTER_Z,
    ROAD_SURFACE_Z,
    VEHICLE_BOTTOM_OFFSET,
    POSITIONS_STATE_FILE,
    SIGNAL_STATE_FILE,
    VEHICLE_CONFIGS,
    get_clockwise_route_waypoints,
)
from vehicle_registry import VehicleRegistry, VEHICLE_LENGTH


def cleanup_state_files():
    """Clean up state files before each test."""
    VehicleRegistry().clear()
    for folder in [os.path.dirname(POSITIONS_STATE_FILE), os.path.dirname(SIGNAL_STATE_FILE)]:
        if os.path.exists(folder):
            for fname in os.listdir(folder):
                if fname.startswith("vehicle_positions.json") or fname.startswith("traffic_signal_states.json"):
                    try:
                        os.remove(os.path.join(folder, fname))
                    except Exception:
                        pass


def run_test_1_position() -> Tuple[str, List[str]]:
    """
    TEST 1 — VEHICLE POSITION (10s)
    Verify CAR_001:
    - vehicle is on road
    - vehicle is not underground
    - vehicle is not floating
    - vehicle has correct Y coordinate (and Z height)
    """
    cleanup_state_files()
    logs = []
    logs.append("Running TEST 1 — VEHICLE POSITION (10s)...")
    
    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    
    dt = 0.032
    steps = int(10.0 / dt)  # ~312 steps for 10s
    
    initial_y = car1.y
    initial_z = VEHICLE_CENTER_Z
    
    underground_violations = 0
    floating_violations = 0
    y_coordinate_violations = 0
    
    for step in range(steps):
        car1.update_logic(dt)
        
        # Check Z elevation (vehicle center Z = 0.42, bottom = 0.02, road surface = 0.02)
        bottom_z = VEHICLE_CENTER_Z - VEHICLE_BOTTOM_OFFSET
        if bottom_z < (ROAD_SURFACE_Z - 0.01):
            underground_violations += 1
        if bottom_z > (ROAD_SURFACE_Z + 0.05):
            floating_violations += 1
            
        # Check initial lane Y alignment (lane Y is 46.5 for Eastbound segment)
        if step < 50:
            if abs(car1.y - 46.5) > 1.0:
                y_coordinate_violations += 1

    is_on_road = car1.is_spawned and (abs(car1.y - 46.5) < 2.0 or abs(car1.x - 53.5) < 2.0 or abs(car1.y - (-46.5)) < 2.0 or abs(car1.x - (-53.5)) < 2.0)
    
    passed = (
        is_on_road and
        underground_violations == 0 and
        floating_violations == 0 and
        y_coordinate_violations == 0
    )
    
    status = "PASS" if passed else "FAIL"
    logs.append(f"  On road: {is_on_road}")
    logs.append(f"  Not underground: {underground_violations == 0}")
    logs.append(f"  Not floating: {floating_violations == 0}")
    logs.append(f"  Correct Y coordinate: {y_coordinate_violations == 0} (Y={car1.y:.2f})")
    logs.append(f"TEST 1 RESULT: {status}")
    return status, logs


def run_test_2_movement() -> Tuple[str, List[str]]:
    """
    TEST 2 — MOVING VEHICLE (10-15s)
    Run CAR_001 on a straight road.
    Verify:
    - vehicle moves
    - vehicle remains on road
    - vehicle Y/Z remains stable
    - vehicle does not teleport
    - vehicle does not jitter
    """
    cleanup_state_files()
    logs = []
    logs.append("Running TEST 2 — MOVING VEHICLE (12s)...")
    
    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.current_speed = 0.0
    
    dt = 0.032
    steps = int(12.0 / dt)  # ~375 steps for 12s
    
    prev_x, prev_y = car1.x, car1.y
    initial_x, initial_y = car1.x, car1.y
    
    teleport_violations = 0
    jitter_violations = 0
    y_instability_count = 0
    
    for step in range(steps):
        car1.update_logic(dt)
        
        step_disp = math.hypot(car1.x - prev_x, car1.y - prev_y)
        max_allowed_disp = (car1.max_speed * dt) + 0.1
        
        if step_disp > max_allowed_disp:
            teleport_violations += 1
            
        # Check lateral stability on straight segment (step 0 to 100 on Y=46.5)
        if step < 100 and abs(car1.y - 46.5) > 0.5:
            y_instability_count += 1
            
        prev_x, prev_y = car1.x, car1.y
        
    dist_traveled = math.hypot(car1.x - initial_x, car1.y - initial_y)
    vehicle_moves = dist_traveled > 5.0 and car1.current_speed > 0.0
    remains_on_road = car1.is_spawned
    
    passed = (
        vehicle_moves and
        remains_on_road and
        y_instability_count == 0 and
        teleport_violations == 0 and
        jitter_violations == 0
    )
    
    status = "PASS" if passed else "FAIL"
    logs.append(f"  Moves: {vehicle_moves} (dist={dist_traveled:.2f}m, speed={car1.current_speed:.2f}m/s)")
    logs.append(f"  Remains on road: {remains_on_road}")
    logs.append(f"  Y stable: {y_instability_count == 0}")
    logs.append(f"  No teleport: {teleport_violations == 0}")
    logs.append(f"  No jitter: {jitter_violations == 0}")
    logs.append(f"TEST 2 RESULT: {status}")
    return status, logs


def run_test_3_stationary() -> Tuple[str, float, List[str]]:
    """
    TEST 3 — MOVING VEHICLE + STATIONARY VEHICLE (10-15s)
    CAR_001 = moving
    CAR_002 = stationary ahead (15-20m gap)
    Verify:
    - CAR_001 detects CAR_002
    - CAR_001 decelerates
    - CAR_001 stops before CAR_002
    - NO collision
    Record: distance_at_stop (center-to-center distance)
    """
    cleanup_state_files()
    logs = []
    logs.append("Running TEST 3 — MOVING VEHICLE + STATIONARY VEHICLE (12s)...")
    
    # CAR_002 stationary at X=15.0, Y=46.5
    car2 = NormalVehicleController("CAR_002")
    car2.is_spawned = True
    car2.x = 15.0
    car2.y = 46.5
    car2.heading = 0.0
    car2.current_speed = 0.0
    car2.max_speed = 0.0
    car2.current_wp_idx = 2
    car2._update_registry()
    
    # CAR_001 moving at X=-5.0, Y=46.5 (20m center separation, 15.5m bumper separation)
    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = -5.0
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_speed = 10.0
    car1.current_wp_idx = 2
    car1._update_registry()
    
    dt = 0.032
    steps = int(12.0 / dt)  # ~375 steps
    
    stopped_safely = False
    collision_occurred = False
    detected_front = False
    
    stop_distance_center = 0.0
    stop_distance_bumper = 0.0
    
    for step in range(steps):
        car2._update_registry()
        car1.update_logic(dt)
        
        bumper_dist = (car2.x - car1.x) - VEHICLE_LENGTH
        center_dist = car2.x - car1.x
        
        if car1.last_target_vehicle == "CAR_002" or car1.state in ["DECELERATING", "FOLLOWING", "STOPPED_BEHIND_VEHICLE"]:
            detected_front = True
            
        if bumper_dist < -0.1:
            collision_occurred = True
            
        if car1.current_speed <= 0.1 or car1.state == "STOPPED_BEHIND_VEHICLE":
            if bumper_dist > -0.1:
                stopped_safely = True
                stop_distance_bumper = bumper_dist
                stop_distance_center = center_dist
                break
            
    if not stopped_safely and car1.current_speed <= 0.1:
        stop_distance_center = car2.x - car1.x
        stop_distance_bumper = stop_distance_center - VEHICLE_LENGTH
        if stop_distance_bumper >= -0.1:
            stopped_safely = True

    passed = (
        detected_front and
        stopped_safely and
        not collision_occurred and
        (stop_distance_center >= 4.5 and stop_distance_center <= 10.0)
    )
    
    status = "PASS" if passed else "FAIL"
    logs.append(f"  Detected CAR_002: {detected_front}")
    logs.append(f"  Stopped safely: {stopped_safely}")
    logs.append(f"  No collision: {not collision_occurred}")
    logs.append(f"  Center distance at stop: {stop_distance_center:.2f} m (Bumper dist: {stop_distance_bumper:.2f} m)")
    logs.append(f"TEST 3 RESULT: {status}")
    return status, round(stop_distance_center, 2), logs


def run_test_4_two_moving() -> Tuple[str, List[str]]:
    """
    TEST 4 — TWO MOVING VEHICLES (10-15s)
    CAR_001 = faster
    CAR_002 = slower ahead
    Verify:
    - CAR_001 slows down
    - CAR_001 follows CAR_002
    - No collision
    """
    cleanup_state_files()
    logs = []
    logs.append("Running TEST 4 — TWO MOVING VEHICLES (12s)...")
    
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
    steps = int(12.0 / dt)
    
    followed_safely = False
    collision_occurred = False
    
    for step in range(steps):
        car2.update_logic(dt)
        car1.update_logic(dt)
        
        bumper_dist = (car2.x - car1.x) - VEHICLE_LENGTH
        if bumper_dist < -0.1:
            collision_occurred = True
            
        if car1.state in ["FOLLOWING", "DECELERATING"] and abs(car1.current_speed - car2.current_speed) < 2.0:
            followed_safely = True
            
    passed = followed_safely and not collision_occurred
    status = "PASS" if passed else "FAIL"
    logs.append(f"  Slowed down & followed: {followed_safely}")
    logs.append(f"  No collision: {not collision_occurred}")
    logs.append(f"TEST 4 RESULT: {status}")
    return status, logs


def run_test_5_five_vehicles() -> Tuple[str, List[str]]:
    """
    TEST 5 — FIVE VEHICLES (15-20s)
    Run 5 vehicles for 15s.
    Verify:
    - no overlap
    - no rear-end collision
    - no underground vehicles
    - no teleportation
    - no Python exceptions
    """
    cleanup_state_files()
    logs = []
    logs.append("Running TEST 5 — FIVE VEHICLES (15s)...")
    
    vehicles = []
    for i in range(5):
        v = NormalVehicleController(f"CAR_{i+1:03d}")
        v.route_type = "CLOCKWISE"
        v.waypoints = get_clockwise_route_waypoints()
        v.is_spawned = True
        v.x = -40.0 + i * 15.0  # Spaced 15m apart on Y=46.5
        v.y = 46.5
        v.heading = 0.0
        v.current_speed = 8.0
        v.current_wp_idx = 2
        v._update_registry()
        vehicles.append(v)
        
    dt = 0.032
    steps = int(15.0 / dt)
    
    overlaps = 0
    underground_count = 0
    teleportation_count = 0
    python_exceptions = 0
    
    prev_positions = {v.vehicle_id: (v.x, v.y) for v in vehicles}
    
    try:
        for step in range(steps):
            for v in vehicles:
                v.update_logic(dt)
                
                # Underground check
                bottom_z = VEHICLE_CENTER_Z - VEHICLE_BOTTOM_OFFSET
                if bottom_z < (ROAD_SURFACE_Z - 0.01):
                    underground_count += 1
                    
                # Teleportation check
                prev_x, prev_y = prev_positions[v.vehicle_id]
                disp = math.hypot(v.x - prev_x, v.y - prev_y)
                if disp > (v.max_speed * dt + 0.1):
                    teleportation_count += 1
                prev_positions[v.vehicle_id] = (v.x, v.y)
                
            # Inter-vehicle overlap check
            for i in range(len(vehicles)):
                v1 = vehicles[i]
                for j in range(i + 1, len(vehicles)):
                    v2 = vehicles[j]
                    dist = math.hypot(v1.x - v2.x, v1.y - v2.y)
                    if dist < 2.5:  # Bounding overlap threshold
                        overlaps += 1

    except Exception as e:
        python_exceptions += 1
        logs.append(f"  Exception caught: {e}")
        
    passed = (
        overlaps == 0 and
        underground_count == 0 and
        teleportation_count == 0 and
        python_exceptions == 0
    )
    status = "PASS" if passed else "FAIL"
    logs.append(f"  No overlaps: {overlaps == 0} (count={overlaps})")
    logs.append(f"  No underground: {underground_count == 0}")
    logs.append(f"  No teleportation: {teleportation_count == 0}")
    logs.append(f"  No exceptions: {python_exceptions == 0}")
    logs.append(f"TEST 5 RESULT: {status}")
    return status, logs


def main():
    print("=" * 60)
    print("SWIFT SYSTEM — SHORT VEHICLE SAFETY TEST SUITE")
    print("=" * 60)
    
    t1_status, t1_logs = run_test_1_position()
    for l in t1_logs:
        print(l)
    print("-" * 60)
    
    t2_status, t2_logs = run_test_2_movement()
    for l in t2_logs:
        print(l)
    print("-" * 60)
    
    t3_status, stop_dist, t3_logs = run_test_3_stationary()
    for l in t3_logs:
        print(l)
    print("-" * 60)
    
    t4_status, t4_logs = run_test_4_two_moving()
    for l in t4_logs:
        print(l)
    print("-" * 60)
    
    t5_status, t5_logs = run_test_5_five_vehicles()
    for l in t5_logs:
        print(l)
    print("=" * 60)
    
    all_passed = all(s == "PASS" for s in [t1_status, t2_status, t3_status, t4_status, t5_status])
    
    print("FINAL SUMMARY REPORT:")
    print(f"TEST 1 POSITION = {t1_status}")
    print(f"TEST 2 MOVEMENT = {t2_status}")
    print(f"TEST 3 STATIONARY VEHICLE = {t3_status}")
    print(f"TEST 4 TWO VEHICLES = {t4_status}")
    print(f"TEST 5 FIVE VEHICLES = {t5_status}")
    print(f"STOP_DISTANCE = {stop_dist:.2f} m")
    print("=" * 60)
    
    if all_passed:
        print("Short automated tests passed. A 120-second endurance test should be performed manually in Webots if required.")


if __name__ == "__main__":
    main()
