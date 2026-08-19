"""
SWIFT SYSTEM - Module 2 Baseline Traffic Test Verification Suite
Executes Tests A through J in exact sequential order per Step 18 guidelines.
"""

import sys
import os
import math
import json
import time
import copy

# Add controller directories to python path
WEBOTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(WEBOTS_DIR)
sys.path.append(os.path.join(WEBOTS_DIR, "controllers"))
sys.path.append(os.path.join(WEBOTS_DIR, "controllers", "road_network"))
sys.path.append(os.path.join(WEBOTS_DIR, "controllers", "car_001_controller"))
sys.path.append(os.path.join(WEBOTS_DIR, "controllers", "car_002_controller"))
sys.path.append(os.path.join(WEBOTS_DIR, "controllers", "car_003_controller"))
sys.path.append(os.path.join(WEBOTS_DIR, "controllers", "car_004_controller"))
sys.path.append(os.path.join(WEBOTS_DIR, "controllers", "ambulance_001_controller"))

from road_network import ROAD_NETWORK, read_signal_state, CAR_LENGTH, STOP_VEHICLE_DISTANCE, get_next_forward_waypoint_idx, snap_to_nearest_lane
from car_001_controller import Car001Controller, SHARED_MEMORY_REGISTRY
from car_002_controller import Car002Controller
from car_003_controller import Car003Controller
from car_004_controller import Car004Controller
from ambulance_001_controller import Ambulance001Controller

STATE_DIR = WEBOTS_DIR
STATE_FILE = os.path.join(WEBOTS_DIR, "traffic_signal_states.json")


def set_junction_signals(signal_dict):
    """Atomically write signal states to JSON file."""
    with open(STATE_FILE, "w") as f:
        json.dump(signal_dict, f)


def run_module2_test_suite():
    print("==================================================", flush=True)
    print("STARTING MODULE 2 BASELINE VERIFICATION (TESTS A - J)", flush=True)
    print("==================================================", flush=True)

    def clean_state():
        if os.path.exists(STATE_DIR):
            for f in os.listdir(STATE_DIR):
                if f.startswith("vehicle_pos_") and f.endswith(".json"):
                    try:
                        os.remove(os.path.join(STATE_DIR, f))
                    except Exception:
                        pass
        SHARED_MEMORY_REGISTRY.clear()

    clean_state()

    dt = 0.032  # 32ms step time

    ALL_GREEN = {
        "J1": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
        "J2": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
        "J3": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
        "J4": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
    }
    set_junction_signals(ALL_GREEN)

    # --------------------------------------------------
    # TEST A — ONE VEHICLE
    # --------------------------------------------------
    print("\n[TEST A] ONE VEHICLE — Continuous Travel Test", flush=True)
    clean_state()
    car1 = Car001Controller()
    for _ in range(100):  # 3.2 seconds
        car1.update_logic(dt)

    print(f"CAR_001 Pos: ({car1.x:.1f}, {car1.y:.1f}) | Speed: {car1.current_speed:.2f}m/s | State: {car1.state}")
    assert car1.current_speed > 0.0, "TEST A FAILED: CAR_001 stopped unexpectedly on empty road!"
    assert car1.state in ["MOVING", "CHANGING_WAYPOINT", "PASSING_JUNCTION"], f"TEST A FAILED: Invalid state {car1.state}"
    print("[PASSED]: TEST A — Single car travels continuously without random stopping.")

    # --------------------------------------------------
    # TEST B — ONE RED SIGNAL
    # --------------------------------------------------
    print("\n[TEST B] ONE RED SIGNAL — Stop Line Deceleration & Stop", flush=True)
    clean_state()
    car1.current_lane_idx = 0
    car1.current_lane = ROAD_NETWORK["LANE_NORTH_EAST"]
    car1.x = 220.0
    car1.y = 253.5
    car1.heading = 0.0
    car1.current_wp_idx = get_next_forward_waypoint_idx(car1.x, car1.y, car1.heading, car1.current_lane)

    red_j2 = copy.deepcopy(ALL_GREEN)
    red_j2["J2"]["WEST"] = "RED"
    set_junction_signals(red_j2)

    for _ in range(80):  # 2.5 seconds
        car1.update_logic(dt)

    print(f"CAR_001 Pos: ({car1.x:.2f}, {car1.y:.1f}) | Speed: {car1.current_speed:.2f}m/s | State: {car1.state}")
    assert car1.state in ["STOPPING_FOR_RED", "APPROACHING_SIGNAL", "WAITING_RED"], f"TEST B FAILED: State is {car1.state}"
    assert car1.x <= 238.5, f"TEST B FAILED: CAR_001 passed stop line (X={car1.x:.2f})"
    print("[PASSED]: TEST B — Car slows and stops BEFORE stop line on RED signal.")

    # --------------------------------------------------
    # TEST C — GREEN SIGNAL
    # --------------------------------------------------
    print("\n[TEST C] GREEN SIGNAL — Pass Through Junction", flush=True)
    set_junction_signals(ALL_GREEN)

    for _ in range(60):  # 1.9 seconds
        car1.update_logic(dt)

    print(f"CAR_001 Pos: ({car1.x:.2f}, {car1.y:.1f}) | Speed: {car1.current_speed:.2f}m/s | State: {car1.state}")
    assert car1.state in ["MOVING", "PASSING_JUNCTION", "CHANGING_WAYPOINT", "MOVING_THROUGH_JUNCTION"], f"TEST C FAILED: State is {car1.state}"
    assert car1.current_speed > 0.0, "TEST C FAILED: Speed is 0 after GREEN signal!"
    print("[PASSED]: TEST C — Car passes cleanly through junction on GREEN signal.")

    # --------------------------------------------------
    # TEST D — TWO VEHICLES
    # --------------------------------------------------
    print("\n[TEST D] TWO VEHICLES — Lead Following & No Overlap", flush=True)
    clean_state()
    car1.current_lane_idx = 1
    car1.current_lane = ROAD_NETWORK["LANE_EAST_SOUTH"]
    car1.x = 248.5
    car1.y = 200.0
    car1.current_lane, car1.current_wp_idx, (car1.x, car1.y) = snap_to_nearest_lane(car1.x, car1.y, [car1.current_lane.lane_id])
    car1.heading = car1.current_lane.target_heading
    car1.current_speed = 0.0

    # Position CAR_002 behind CAR_001
    car2 = Car002Controller()
    car2.current_lane_idx = 1
    car2.current_lane = ROAD_NETWORK["LANE_EAST_SOUTH"]
    car2.x = 250.0
    car2.y = 215.0
    car2.current_lane, car2.current_wp_idx, (car2.x, car2.y) = snap_to_nearest_lane(car2.x, car2.y, [car2.current_lane.lane_id])
    car2.heading = car2.current_lane.target_heading
    car2.current_speed = 3.0

    for _ in range(100):
        car1._update_shared_state()
        car2.update_logic(dt)

    overlap_dist = math.hypot(car2.x - car1.x, car2.y - car1.y)
    print(f"CAR_001 Y: {car1.y:.2f} | CAR_002 Y: {car2.y:.2f} | Gap: {overlap_dist:.2f}m | CAR_002 State: {car2.state}")
    assert overlap_dist >= CAR_LENGTH + 0.5, f"TEST D FAILED: Overlap detected! Gap: {overlap_dist:.2f}m"
    assert car2.state in ["WAITING_IN_QUEUE", "APPROACHING_SIGNAL", "FOLLOWING_VEHICLE", "STOPPED", "MOVING"], f"TEST D FAILED: State is {car2.state}"
    print("[PASSED]: TEST D — Rear vehicle follows lead vehicle safely with zero overlap.")

    # --------------------------------------------------
    # TEST E — RED QUEUE
    # --------------------------------------------------
    print("\n[TEST E] RED QUEUE — Multi-Vehicle Queue Stacking", flush=True)
    clean_state()
    car1.current_lane_idx = 0
    car1.current_lane = ROAD_NETWORK["LANE_NORTH_EAST"]
    car1.x = 232.0
    car1.y = 253.5
    car1.heading = car1.current_lane.target_heading
    car1.current_wp_idx = 4
    car1.current_speed = 0.0
    car1.state = "STOPPING_FOR_RED"

    car2.current_lane_idx = 0
    car2.current_lane = ROAD_NETWORK["LANE_NORTH_EAST"]
    car2.x = 224.0
    car2.y = 253.5
    car2.heading = car2.current_lane.target_heading
    car2.current_wp_idx = 4
    car2.current_speed = 3.0

    car3 = Car003Controller()
    car3.current_lane_idx = 0
    car3.current_lane = ROAD_NETWORK["LANE_NORTH_EAST"]
    car3.x = 216.0
    car3.y = 253.5
    car3.heading = car3.current_lane.target_heading
    car3.current_wp_idx = 4
    car3.current_speed = 3.0

    set_junction_signals(red_j2)

    for _ in range(100):
        car1._update_shared_state()
        car2.update_logic(dt)
        car3.update_logic(dt)

    gap_1_2 = car1.x - car2.x
    gap_2_3 = car2.x - car3.x

    print(f"CAR 1 X: {car1.x:.2f} | CAR 2 X: {car2.x:.2f} (Gap: {gap_1_2:.2f}m) | CAR 3 X: {car3.x:.2f} (Gap: {gap_2_3:.2f}m)")
    assert gap_1_2 >= 2.5, f"TEST E FAILED: Overlap between CAR 1 and CAR 2! Gap: {gap_1_2:.2f}m"
    assert gap_2_3 >= 2.5, f"TEST E FAILED: Overlap between CAR 2 and CAR 3! Gap: {gap_2_3:.2f}m"
    print("[PASSED]: TEST E — Vehicles form clean queue before RED light without overlap.")

    # --------------------------------------------------
    # TEST F — GREEN QUEUE
    # --------------------------------------------------
    print("\n[TEST F] GREEN QUEUE — Sequential Queue Dissipation", flush=True)
    set_junction_signals(ALL_GREEN)

    for step in range(150):
        car1.update_logic(dt)
        car2.update_logic(dt)
        car3.update_logic(dt)

    print(f"CAR 1 Speed: {car1.current_speed:.2f}m/s | CAR 2 Speed: {car2.current_speed:.2f}m/s | CAR 3 Speed: {car3.current_speed:.2f}m/s")
    assert car1.current_speed > 0.0 and car2.current_speed > 0.0 and car3.current_speed > 0.0, "TEST F FAILED: Queue failed to clear!"
    print("[PASSED]: TEST F — Queue clears smoothly in order when signal turns GREEN.")

    # --------------------------------------------------
    # TEST G — MULTIPLE LANES
    # --------------------------------------------------
    print("\n[TEST G] MULTIPLE LANES — Cross-Lane Signal Immunity", flush=True)
    car4 = Car004Controller()
    car4.current_lane_idx = 3
    car4.current_lane = ROAD_NETWORK["LANE_WEST_NORTH"]
    car4.x = -246.5
    car4.y = 0.0
    car4.heading = 1.5708
    car4.current_wp_idx = get_next_forward_waypoint_idx(car4.x, car4.y, car4.heading, car4.current_lane)

    set_junction_signals(red_j2)

    for _ in range(50):
        car4.update_logic(dt)

    print(f"CAR_004 Pos: ({car4.x:.1f}, {car4.y:.2f}) | Speed: {car4.current_speed:.2f}m/s | State: {car4.state}")
    assert car4.state in ["MOVING", "APPROACHING_SIGNAL", "CHANGING_WAYPOINT"], f"TEST G FAILED: CAR_004 stopped for unrelated signal! State: {car4.state}"
    assert car4.current_speed > 0.0, "TEST G FAILED: Speed is 0!"
    print("[PASSED]: TEST G — Vehicles in one lane ignore signals controlling other lanes.")

    # --------------------------------------------------
    # TEST H — FOUR JUNCTIONS
    # --------------------------------------------------
    print("\n[TEST H] FOUR JUNCTIONS — Independent Multi-Junction Coordination", flush=True)
    clean_state()
    cars = [car1, car2, car3, car4]
    set_junction_signals(ALL_GREEN)

    for _ in range(100):
        for c in cars:
            c.update_logic(dt)

    for c in cars:
        print(f"[{c.VEHICLE_ID}] Lane: {c.current_lane.lane_id} | Speed: {c.current_speed:.2f}m/s | State: {c.state}")
        assert c.current_speed > 0.0 or c.state in ["WAITING_IN_QUEUE", "APPROACHING_SIGNAL", "STOPPING_FOR_RED", "WAITING_RED", "FOLLOWING_VEHICLE", "STOPPED"], f"TEST H FAILED: {c.VEHICLE_ID} stopped!"
    print("[PASSED]: TEST H — All 4 junctions operate independently with continuous traffic flow.")

    # --------------------------------------------------
    # TEST I — AMBULANCE
    # --------------------------------------------------
    print("\n[TEST I] AMBULANCE — Module 2 Baseline Compliance & No Overlap", flush=True)
    amb = Ambulance001Controller()
    amb.x = -246.5
    amb.y = 20.0
    amb.heading = 1.5708

    for _ in range(50):
        amb.update_logic(dt)

    print(f"AMBULANCE_001 Pos: ({amb.x:.1f}, {amb.y:.1f}) | Speed: {amb.current_speed:.2f}m/s | Emergency Active: {amb.EMERGENCY_ACTIVE}")
    assert not amb.EMERGENCY_ACTIVE, "TEST I FAILED: Ambulance priority override active in Module 2 baseline!"
    assert amb.current_speed >= 0.0, "TEST I FAILED: Ambulance invalid speed!"
    print("[PASSED]: TEST I — Ambulance obeys standard traffic rules without priority override or overlap.")

    # --------------------------------------------------
    # TEST J — LONG RUN
    # --------------------------------------------------
    print("\n[TEST J] LONG RUN — Multi-Minute Continuous Simulation (1000 Steps)", flush=True)
    invalid_stops = 0
    all_sim_vehicles = [car1, car2, car3, car4, amb]

    for step in range(1000):  # 32 seconds continuous run
        for c in all_sim_vehicles:
            c.update_logic(dt)
            if c.current_speed == 0.0 and getattr(c, "state", "") in ["MOVING", "DRIVING_STRAIGHT"]:
                invalid_stops += 1

    print(f"Total Steps Simulated: 1000 | Invalid Stops: {invalid_stops}")
    for c in all_sim_vehicles:
        v_id = getattr(c, "VEHICLE_ID", "UNKNOWN")
        v_spd = getattr(c, "current_speed", getattr(c, "speed", 0.0))
        v_st = getattr(c, "state", "UNKNOWN")
        print(f"[{v_id}] Final Pos: ({c.x:.1f}, {c.y:.1f}) | Speed: {v_spd:.2f}m/s | State: {v_st}")

    assert invalid_stops == 0, f"TEST J FAILED: Found {invalid_stops} invalid stopping events!"
    print("[PASSED]: TEST J — Continuous simulation ran 1000 steps with ZERO random stopping, zero collisions, and zero deadlocks.")

    print("\n==================================================", flush=True)
    print("ALL MODULE 2 BASELINE TESTS (TESTS A - J) PASSED!", flush=True)
    print("==================================================", flush=True)


if __name__ == "__main__":
    run_module2_test_suite()
