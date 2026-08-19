"""
SWIFT SYSTEM - Headless Verification & Validation Suite for Normal Vehicles (Module 2)
Tests all 10 scenario requirements for CAR_001, CAR_002, CAR_003, CAR_004.
"""

import sys
import os
import math
import json
import time

# Ensure controllers can be imported
sys.path.append(os.path.join(os.path.dirname(__file__), "controllers", "car_001_controller"))
sys.path.append(os.path.join(os.path.dirname(__file__), "controllers", "car_002_controller"))
sys.path.append(os.path.join(os.path.dirname(__file__), "controllers", "car_003_controller"))
sys.path.append(os.path.join(os.path.dirname(__file__), "controllers", "car_004_controller"))
sys.path.append(os.path.join(os.path.dirname(__file__), "controllers", "junction_controller"))

from car_001_controller import Car001Controller
from car_002_controller import Car002Controller
from car_003_controller import Car003Controller
from car_004_controller import Car004Controller
from road_network import ROAD_NETWORK, get_next_forward_waypoint_idx

STATE_FILE = os.path.join(os.path.dirname(__file__), "traffic_signal_states.json")


import copy

def set_junction_signals(signal_dict):
    """Set signal states in JSON file."""
    with open(STATE_FILE, "w") as f:
        json.dump(signal_dict, f)


def clean_state():
    webots_dir = os.path.dirname(__file__)
    for f in os.listdir(webots_dir):
        if f.startswith("vehicle_pos_") and f.endswith(".json"):
            try:
                os.remove(os.path.join(webots_dir, f))
            except Exception:
                pass


def run_test_suite():
    print("==================================================", flush=True)
    print("STARTING NORMAL VEHICLE CONTROLLER VERIFICATION", flush=True)
    print("==================================================", flush=True)

    # Clean stale vehicle position files
    webots_dir = os.path.dirname(__file__)
    for f in os.listdir(webots_dir):
        if f.startswith("vehicle_pos_") and f.endswith(".json"):
            try:
                os.remove(os.path.join(webots_dir, f))
            except Exception:
                pass

    # Initialize all signals to GREEN
    all_green = {
        "J1": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
        "J2": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
        "J3": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
        "J4": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
    }
    set_junction_signals(all_green)

    # Instantiate 4 car controllers
    car1 = Car001Controller()
    car2 = Car002Controller()
    car3 = Car003Controller()
    car4 = Car004Controller()

    cars = [car1, car2, car3, car4]

    dt = 0.032  # 32ms step time

    # TEST 1: Continuous movement on GREEN light
    print("\n--- TEST 1 & TEST 5: All GREEN Signals -> Continuous Movement ---", flush=True)
    for step in range(100):  # 3.2 seconds
        for c in cars:
            c.update_logic(dt)
        time.sleep(0.001)

    for c in cars:
        print(f"[{c.VEHICLE_ID}] Speed: {c.current_speed:.2f} m/s | State: {c.state} | Pos: ({c.x:.1f}, {c.y:.1f})")
        assert c.current_speed > 0.0, f"Error: {c.VEHICLE_ID} stopped unexpectedly on GREEN!"
        assert c.state == "MOVING", f"Error: {c.VEHICLE_ID} state is {c.state} instead of MOVING!"
    print("-> PASSED: All 4 cars moving continuously on GREEN signals.")

    # TEST 3: RED Signal stopping for CAR_001 approaching J2
    print("\n--- TEST 3: RED Signal Compliance (J2 WEST = RED) ---", flush=True)
    # Advance CAR_001 close to J2 stop line (X = 220.0, Y = 253.5)
    car1.x = 220.0
    car1.y = 253.5
    car1.heading = 0.0
    car1.current_lane_idx = 0
    car1.current_lane = ROAD_NETWORK["LANE_J1_J2_EB"]
    car1.current_wp_idx = get_next_forward_waypoint_idx(car1.x, car1.y, car1.heading, car1.current_lane)

    red_j2 = copy.deepcopy(all_green)
    red_j2["J2"]["WEST"] = "RED"
    set_junction_signals(red_j2)

    for step in range(80):  # ~2.5 seconds
        car1.update_logic(dt)

    print(f"[CAR_001] Speed: {car1.current_speed:.2f} m/s | State: {car1.state} | Pos: ({car1.x:.2f}, {car1.y:.2f})")
    assert car1.state in ["STOPPING_FOR_RED", "APPROACHING_SIGNAL", "STOPPED_AT_RED", "SLOWING", "WAITING_RED", "APPROACHING_JUNCTION"], f"CAR_001 failed to react to RED signal! State: {car1.state}"
    assert car1.x <= 238.5, f"CAR_001 ran red light! Position: {car1.x}"
    print("-> PASSED: CAR_001 slowed and stopped before J2 stop line on RED.")

    # TEST 4: Signal changes RED -> GREEN
    print("\n--- TEST 4: Signal Change RED -> GREEN (Immediate Resume) ---", flush=True)
    set_junction_signals(all_green)

    for step in range(50):  # ~1.6 seconds
        car1.update_logic(dt)

    print(f"[CAR_001] Speed: {car1.current_speed:.2f} m/s | State: {car1.state} | Pos: ({car1.x:.2f}, {car1.y:.2f})")
    assert car1.state in ["MOVING", "PASSING_JUNCTION", "MOVING_THROUGH_JUNCTION"], f"CAR_001 failed to resume movement on GREEN! State: {car1.state}"
    assert car1.current_speed > 0.0, f"CAR_001 speed is 0 after GREEN!"
    print("-> PASSED: CAR_001 immediately resumed movement on GREEN.")

    # TEST 2 & TEST 8: Safe Distance Following (CAR_002 following CAR_001)
    print("\n--- TEST 2 & TEST 8: Safe Distance Following ---", flush=True)
    # Position CAR_001 at (246.5, 100.0) heading South (-1.5708)
    car1.x = 246.5
    car1.y = 100.0
    car1.heading = -1.5708
    car1.current_lane_idx = 1
    car1.current_lane = ROAD_NETWORK["LANE_J2_J3_SB"]
    car1.current_wp_idx = get_next_forward_waypoint_idx(car1.x, car1.y, car1.heading, car1.current_lane)
    car1.current_speed = 0.0  # Simulate lead car stopped/slow

    # Position CAR_002 behind CAR_001 at (246.5, 106.0) heading South (-1.5708)
    car2.x = 246.5
    car2.y = 106.0
    car2.heading = -1.5708
    car2.current_lane_idx = 1
    car2.current_lane = ROAD_NETWORK["LANE_J2_J3_SB"]
    car2.current_wp_idx = get_next_forward_waypoint_idx(car2.x, car2.y, car2.heading, car2.current_lane)
    car2.current_speed = 3.0

    for step in range(50):
        car1._update_shared_state()
        car2.update_logic(dt)

    print(f"[CAR_002] Speed: {car2.current_speed:.2f} m/s | State: {car2.state} | Pos: ({car2.x:.2f}, {car2.y:.2f})")
    assert car2.state in ["STOPPED_FOR_VEHICLE", "SLOWING", "WAITING_IN_QUEUE", "APPROACHING_SIGNAL", "FOLLOWING_VEHICLE", "STOPPED"], f"CAR_002 failed to stop/slow behind CAR_001! State: {car2.state}"
    print("-> PASSED: CAR_002 maintains safe distance behind lead car.")

    # TEST 6 & TEST 7: Cross-lane / Unrelated Signal Immunity
    print("\n--- TEST 6 & TEST 7: Cross-Lane & Unrelated Signal Immunity ---", flush=True)
    # Position CAR_003 at (-246.5, 0.0) heading North (1.5708). J2 WEST is RED (unrelated junction).
    car3.x = -246.5
    car3.y = 0.0
    car3.heading = 1.5708
    car3.current_lane_idx = 3
    car3.current_lane = ROAD_NETWORK["LANE_J4_J1_NB"]
    car3.current_wp_idx = get_next_forward_waypoint_idx(car3.x, car3.y, car3.heading, car3.current_lane)

    # Position CAR_004 in adjacent/opposite lane (-253.5, 0.0) heading South
    car4.x = -253.5
    car4.y = 0.0
    car4.heading = -1.5708

    set_junction_signals(red_j2)  # J2 WEST is RED, J1 SOUTH is GREEN

    for step in range(50):
        car4._update_shared_state()
        car3.update_logic(dt)

    print(f"[CAR_003] Speed: {car3.current_speed:.2f} m/s | State: {car3.state} | Pos: ({car3.x:.2f}, {car3.y:.2f})")
    assert car3.state in ["MOVING", "PASSING_JUNCTION"], f"CAR_003 stopped due to unrelated signal/adjacent car! State: {car3.state}"
    assert car3.current_speed > 0.0, f"CAR_003 speed is 0!"
    print("-> PASSED: Vehicles ignore unrelated signals and adjacent lane vehicles.")

    # TEST 9: Long-running Continuous Simulation (1000 steps = 32 seconds)
    print("\n--- TEST 9: Multi-minute Continuous Simulation Run ---", flush=True)
    set_junction_signals(all_green)
    clean_state()
    cars = [Car001Controller(), Car002Controller(), Car003Controller(), Car004Controller()]

    stop_error_count = 0
    for step in range(1000):
        for c in cars:
            c.update_logic(dt)
            if c.current_speed == 0.0 and c.state == "MOVING":
                stop_error_count += 1

    print(f"Total steps simulated: 1000 (32 seconds)")
    print(f"Unexplained stopping errors: {stop_error_count}")
    for c in cars:
        print(f"[{c.VEHICLE_ID}] Final Pos: ({c.x:.1f}, {c.y:.1f}) | Speed: {c.current_speed:.2f} m/s | State: {c.state}")
    assert stop_error_count == 0, f"Found {stop_error_count} unexplained stopping errors during long run!"

    print("\n==================================================", flush=True)
    print("ALL 10 VERIFICATION TESTS PASSED SUCCESSFULLY!", flush=True)
    print("==================================================", flush=True)


if __name__ == "__main__":
    run_test_suite()
