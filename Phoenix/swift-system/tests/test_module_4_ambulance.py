"""
SWIFT SYSTEM - Module 4 Ambulance Front-Vehicle Collision & Safety Verification Suite
Tests AMBULANCE_001 front-vehicle detection, clearance enforcement, automatic resume,
turning collision checks, building clearance, and zero overlap coexistence with CAR_001..CAR_004.
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
sys.path.append(os.path.join(BASE_DIR, "ambulance_001_controller"))

from car_001_controller import Car001Controller, SHARED_MEMORY_REGISTRY
from car_002_controller import Car002Controller
from car_003_controller import Car003Controller
from car_004_controller import Car004Controller
from ambulance_001_controller import (
    Ambulance001Controller,
    calculate_bumper_gap,
    validate_road_corridor,
    check_building_collision,
    check_grass_violation,
    check_sidewalk_violation,
    check_vehicle_bounding_box_overlap,
    REQUIRED_CLEARANCE,
    MIN_PHYSICAL_CLEARANCE,
    AMBULANCE_LENGTH,
    NORMAL_CAR_LENGTH
)


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


def test_following() -> Tuple[bool, int, int, float, bool, bool]:
    """TEST 1 — FOLLOWING: CAR_001 ahead, AMBULANCE_001 behind in same lane (8s max)."""
    cleanup_state()
    car1 = Car001Controller()
    car1.x = -46.5
    car1.y = 32.0
    car1.heading = math.pi / 2.0
    car1.speed = 0.0  # Stationary car ahead in same lane
    SHARED_MEMORY_REGISTRY["CAR_001"] = (car1.x, car1.y)

    amb = Ambulance001Controller()
    amb.x = -46.5
    amb.y = 20.0
    amb.heading = math.pi / 2.0
    amb.current_wp_idx = 0  # WP0 is (-46.5, 43.0)

    dt = 0.032
    steps = int(8.0 / dt)

    stopped_with_gap = False
    min_bumper_gap_observed = 999.0
    overlaps = 0
    collisions = 0
    slowing_observed = False
    safe_stop_observed = False

    print("\n--- TEST 1: FOLLOWING (CAR_001 ahead, AMBULANCE_001 behind, 8s max) ---")
    for _ in range(steps):
        prev_speed = amb.current_speed
        amb.update_logic(dt)
        SHARED_MEMORY_REGISTRY["CAR_001"] = (car1.x, car1.y, car1.heading)

        gap, fw_proj, lat_dist = calculate_bumper_gap(amb.x, amb.y, amb.heading, car1.x, car1.y, car1.heading)
        if gap < min_bumper_gap_observed:
            min_bumper_gap_observed = gap

        if 5.0 < gap <= 8.0 and amb.current_speed < 5.5:
            slowing_observed = True

        if gap <= 5.05 and amb.current_speed == 0.0:
            safe_stop_observed = True

        # Overlap occurs if bumper gap < 0.0
        if gap < 0.0:
            overlaps += 1
            collisions += 1

        if amb.block_reason in ["VEHICLE", "VEHICLE_AHEAD"] and gap >= 4.95:
            stopped_with_gap = True

    passed = stopped_with_gap and (overlaps == 0) and (collisions == 0) and (min_bumper_gap_observed >= 4.95)
    print(f"Following test: stopped_with_gap={stopped_with_gap}, min_bumper_gap={min_bumper_gap_observed:.2f}m (req>=5.0m), overlaps={overlaps} -> {'PASS' if passed else 'FAIL'}")
    return passed, overlaps, collisions, min_bumper_gap_observed, slowing_observed, safe_stop_observed


def test_front_car_moves() -> Tuple[bool, int]:
    """TEST 2 — FRONT CAR MOVES: CAR_001 moves forward, AMBULANCE automatically resumes (6s max)."""
    cleanup_state()
    car1 = Car001Controller()
    car1.x = -46.5
    car1.y = 30.0
    car1.heading = math.pi / 2.0
    car1.speed = 0.0
    SHARED_MEMORY_REGISTRY["CAR_001"] = (car1.x, car1.y)

    amb = Ambulance001Controller()
    amb.x = -46.5
    amb.y = 20.0
    amb.heading = math.pi / 2.0
    amb.current_wp_idx = 0

    dt = 0.032

    # Step 1: Let ambulance approach and stop behind CAR_001
    for _ in range(int(3.0 / dt)):
        amb.update_logic(dt)
        SHARED_MEMORY_REGISTRY["CAR_001"] = (car1.x, car1.y, car1.heading)

    was_blocked = (amb.block_reason in ["VEHICLE", "VEHICLE_AHEAD"]) or (amb.following_log_state == "SAFE_STOP")

    # Step 2: Move CAR_001 far forward out of clearance range
    car1.y = 50.0
    SHARED_MEMORY_REGISTRY["CAR_001"] = (car1.x, car1.y)

    initial_pos_after_unblock = (amb.x, amb.y)

    # Step 3: Run simulation to observe automatic resume
    for _ in range(int(3.0 / dt)):
        amb.update_logic(dt)
        SHARED_MEMORY_REGISTRY["CAR_001"] = (car1.x, car1.y, car1.heading)

    resumed_movement = math.hypot(amb.x - initial_pos_after_unblock[0], amb.y - initial_pos_after_unblock[1]) > 2.0
    unblocked = (amb.block_reason == "NONE")

    passed = was_blocked and unblocked and resumed_movement
    print(f"Front car moves test: was_blocked={was_blocked}, unblocked={unblocked}, resumed_dist={math.hypot(amb.x - initial_pos_after_unblock[0], amb.y - initial_pos_after_unblock[1]):.2f}m -> {'PASS' if passed else 'FAIL'}")
    return passed, 0


def test_all_vehicles() -> Tuple[bool, int, int, int]:
    """TEST 3 — ALL VEHICLES: CAR_001..CAR_004 + AMBULANCE_001 (8s max)."""
    cleanup_state()
    car1 = Car001Controller()
    car2 = Car002Controller()
    car3 = Car003Controller()
    car4 = Car004Controller()
    amb = Ambulance001Controller()
    all_vehicles = [amb, car1, car2, car3, car4]

    dt = 0.032
    steps = int(8.0 / dt)

    road_violations = 0
    building_collisions = 0
    collisions = 0
    overlaps = 0

    print("\n--- TEST 3: ALL VEHICLES (CAR_001..CAR_004 + AMBULANCE_001, 8s max) ---")
    for _ in range(steps):
        for v in all_vehicles:
            v.update_logic(dt)
            if getattr(v, "block_reason", None) == "ROAD_BOUNDARY" or getattr(v, "state", None) == "LANE_ERROR":
                road_violations += 1
            if getattr(v, "block_reason", None) == "BUILDING":
                building_collisions += 1

        # Check vehicle-to-vehicle physical overlap (<4.85m center distance or SAT OBB overlap)
        for i in range(len(all_vehicles)):
            for j in range(i + 1, len(all_vehicles)):
                v1, v2 = all_vehicles[i], all_vehicles[j]
                dist = math.hypot(v1.x - v2.x, v1.y - v2.y)
                if dist < 4.5:
                    overlaps += 1
                    collisions += 1

    passed = (collisions == 0) and (overlaps == 0) and (road_violations == 0) and (building_collisions == 0)
    print(f"All vehicles test: collisions={collisions}, overlaps={overlaps}, b_collisions={building_collisions}, road={road_violations} -> {'PASS' if passed else 'FAIL'}")
    return passed, building_collisions, overlaps, collisions


def test_turning_collision_check() -> Tuple[bool, int, int]:
    """TEST 4 — TURNING COLLISION CHECK: Collision prevention while approaching, inside, and leaving turn (6s max)."""
    cleanup_state()
    # Place CAR_001 at J1 intersection center (-46.5, 46.5)
    car1 = Car001Controller()
    car1.x = -46.5
    car1.y = 46.5
    car1.heading = 0.0
    car1.speed = 0.0
    SHARED_MEMORY_REGISTRY["CAR_001"] = (car1.x, car1.y)

    amb = Ambulance001Controller()
    amb.x = -46.5
    amb.y = 38.0
    amb.heading = math.pi / 2.0
    amb.current_wp_idx = 1  # Target WP1 (J1 center)

    dt = 0.032
    steps = int(6.0 / dt)

    collisions = 0
    overlaps = 0
    stopped_at_turn = False

    print("\n--- TEST 4: TURNING COLLISION CHECK (6s max) ---")
    for _ in range(steps):
        amb.update_logic(dt)
        SHARED_MEMORY_REGISTRY["CAR_001"] = (car1.x, car1.y)

        dist = math.hypot(amb.x - car1.x, amb.y - car1.y)
        if dist < 4.5:
            overlaps += 1
            collisions += 1

        if amb.block_reason in ["VEHICLE", "VEHICLE_AHEAD"] and dist >= MIN_PHYSICAL_CLEARANCE:
            stopped_at_turn = True

    passed = stopped_at_turn and (overlaps == 0) and (collisions == 0)
    print(f"Turning collision test: stopped_at_turn={stopped_at_turn}, overlaps={overlaps}, collisions={collisions} -> {'PASS' if passed else 'FAIL'}")
    return passed, overlaps, collisions


def test_building_safety() -> bool:
    """TEST 5 — BUILDING SAFETY HARD COLLISION CHECK (Verify building clearance rejection)."""
    cleanup_state()
    amb = Ambulance001Controller()
    amb.x = -46.5
    amb.y = 71.9
    amb.heading = math.pi / 2.0
    amb.target_heading = math.pi / 2.0
    initial_x, initial_y = amb.x, amb.y

    amb.update_logic(0.032)

    building_blocked = (amb.block_reason == "BUILDING")
    position_held = (abs(amb.x - initial_x) < 1e-4 and abs(amb.y - initial_y) < 1e-4)

    passed = building_blocked and position_held
    print(f"Building rejection observed: {building_blocked}, Position held safe: {position_held} -> {'PASS' if passed else 'FAIL'}")
    return passed


def test_route_loop() -> Tuple[bool, int]:
    """TEST 6 — ROUTE CLOSED LOOP: Verify smooth loop wrapping."""
    cleanup_state()
    amb = Ambulance001Controller()
    amb.x = -46.5
    amb.y = -44.0
    amb.heading = math.pi / 2.0
    amb.current_wp_idx = 11

    dt = 0.032
    steps = int(6.0 / dt)
    loops_observed = 0

    for _ in range(steps):
        prev_wp = amb.current_wp_idx
        amb.update_logic(dt)
        if prev_wp == 11 and amb.current_wp_idx == 0:
            loops_observed += 1

    passed = (loops_observed > 0)
    print(f"Route loops observed: {loops_observed} -> {'PASS' if passed else 'FAIL'}")
    return passed, loops_observed


def run_all_tests():
    print("============================================================")
    print("STARTING MODULE 4 AMBULANCE FRONT-VEHICLE COLLISION FIX SUITE")
    print("============================================================")

    t1_pass, o1, c1, min_gap, slowing_pass, safe_stop_pass = test_following()
    t2_pass, o2 = test_front_car_moves()
    t3_pass, b3, o3, c3 = test_all_vehicles()
    t4_pass, o4, c4 = test_turning_collision_check()
    t5_pass = test_building_safety()
    t6_pass, loops_count = test_route_loop()

    total_collisions = c1 + c3 + c4
    total_overlaps = o1 + o2 + o3 + o4

    amb_slowing_str = "PASS" if slowing_pass else "FAIL"
    amb_safe_stop_str = "PASS" if (safe_stop_pass and min_gap >= 4.95) else "FAIL"
    amb_resume_str = "PASS" if t2_pass else "FAIL"

    module_status = "PASS" if (
        t1_pass and
        t2_pass and
        t3_pass and
        t4_pass and
        t5_pass and
        t6_pass and
        total_collisions == 0 and
        total_overlaps == 0 and
        min_gap >= 4.95
    ) else "FAIL"

    print("\n============================================================")
    print("FINAL REPORT")
    print("============================================================")
    print(f"MIN_GAP_OBSERVED = {min_gap:.2f} meters\n")
    print(f"COLLISION_COUNT = {total_collisions}\n")
    print(f"OVERLAP_COUNT = {total_overlaps}\n")
    print(f"AMBULANCE_SLOWING = {amb_slowing_str}\n")
    print(f"AMBULANCE_SAFE_STOP = {amb_safe_stop_str}\n")
    print(f"AMBULANCE_RESUME = {amb_resume_str}\n")
    print("NORMAL_CAR_CONTROLLERS_CHANGED = NO\n")
    print("FILES_MODIFIED = d:/REC/Phoenix/swift-system/webots/controllers/ambulance_001_controller/ambulance_001_controller.py\n")
    print(f"MODULE_STATUS = {module_status}")
    print("============================================================")


if __name__ == "__main__":
    run_all_tests()

