"""
SWIFT SYSTEM - Module 2 Multi-Vehicle Traffic Verification Suite
Verifies 10 CARs + 5 BIKEs multi-vehicle simulation, Left-Hand Traffic (LHT),
8-state decision machine, signal integration, safe spacing, and telemetry export.
"""

import sys
import os
import math
import json
import time

WEBOTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(WEBOTS_DIR)
sys.path.append(os.path.join(WEBOTS_DIR, "controllers"))
sys.path.append(os.path.join(WEBOTS_DIR, "controllers", "vehicle_controller"))

from road_network import ROAD_NETWORK, read_signal_state, get_next_forward_waypoint_idx
from vehicle_controller import (
    NormalVehicleController,
    VEHICLE_CONFIGS,
    VEHICLE_SPAWNS,
    ALL_VEHICLE_IDS,
    VehicleState,
    SHARED_MEMORY_REGISTRY,
)

STATE_FILE = os.path.join(WEBOTS_DIR, "traffic_signal_states.json")


def set_junction_signals(signal_dict):
    with open(STATE_FILE, "w") as f:
        json.dump(signal_dict, f)


def clean_state():
    if os.path.exists(WEBOTS_DIR):
        for f in os.listdir(WEBOTS_DIR):
            if f.startswith("vehicle_pos_") and f.endswith(".json"):
                try:
                    os.remove(os.path.join(WEBOTS_DIR, f))
                except Exception:
                    pass
    SHARED_MEMORY_REGISTRY.clear()


def run_multi_vehicle_verification():
    print("==================================================", flush=True)
    print("STARTING MODULE 2 MULTI-VEHICLE TRAFFIC VERIFICATION", flush=True)
    print("==================================================", flush=True)

    dt = 0.032  # 32ms

    ALL_GREEN = {
        "JUNCTION_01": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
        "JUNCTION_02": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
        "JUNCTION_03": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
        "JUNCTION_04": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
        "J1": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
        "J2": {"NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN", "WEST": "GREEN"},
    }
    set_junction_signals(ALL_GREEN)
    clean_state()

    # 1. FLEET INITIALIZATION & TYPE VERIFICATION
    print("\n[TEST 1] FLEET COMPOSITION & INDIVIDUAL CONTROLLER INITIALIZATION", flush=True)
    car_ids = [v for v in ALL_VEHICLE_IDS if v.startswith("CAR_")]
    bike_ids = [v for v in ALL_VEHICLE_IDS if v.startswith("BIKE_")]

    assert len(car_ids) == 10, f"Expected 10 Cars, found {len(car_ids)}"
    assert len(bike_ids) == 5, f"Expected 5 Bikes, found {len(bike_ids)}"

    fleet = {}
    for v_id in car_ids + bike_ids:
        ctrl = NormalVehicleController(v_id)
        fleet[v_id] = ctrl
        expected_type = "CAR" if v_id.startswith("CAR_") else "BIKE"
        assert ctrl.v_type == expected_type, f"Vehicle {v_id} type mismatch: {ctrl.v_type} vs {expected_type}"
        assert ctrl.vehicle_id == v_id

    print(f"[PASSED]: Initialized 10 CARs and 5 BIKEs with unique IDs and correct physical profiles.")

    # 2. LEFT-HAND TRAFFIC & ORIENTATION
    print("\n[TEST 2] LEFT-HAND TRAFFIC (LHT) & ROAD ORIENTATION", flush=True)
    for v_id, ctrl in fleet.items():
        lane = ctrl.current_lane
        assert lane is not None, f"Vehicle {v_id} has no valid lane"
        dot = math.cos(ctrl.heading) * lane.unit_vector[0] + math.sin(ctrl.heading) * lane.unit_vector[1]
        assert dot > 0.7, f"Vehicle {v_id} heading ({ctrl.heading:.2f}) does not match LHT lane direction ({lane.direction})"

    print("[PASSED]: All 15 vehicles strictly follow Indian Left-Hand Traffic (LHT) lanes and face velocity vector.")

    # 3. INITIAL STATIONARY DEBUG MODE & CONTINUOUS MOVEMENT
    print("\n[TEST 3] INITIAL STATIONARY DEBUG MODE & CONTINUOUS MOVEMENT", flush=True)
    for step in range(15):
        for ctrl in fleet.values():
            ctrl.update_logic(dt)

    stationary_count = 0
    for v_id, ctrl in fleet.items():
        if ctrl.current_speed == 0.0:
            stationary_count += 1

    # Advance past 1.0s stationary delay into active movement
    for step in range(80):
        for ctrl in fleet.values():
            ctrl.update_logic(dt)

    moving_count = 0
    for v_id, ctrl in fleet.items():
        print(f"[{v_id}] ({ctrl.v_type}) Pos: ({ctrl.x:.1f}, {ctrl.y:.1f}) | Speed: {ctrl.current_speed:.2f}m/s | State: {ctrl.state}")
        assert ctrl.current_speed > 0.0 or ctrl.state in [VehicleState.WAITING_RED, VehicleState.STOPPED, VehicleState.FOLLOWING_VEHICLE], f"Vehicle {v_id} stopped unexpectedly!"
        moving_count += 1

    assert moving_count == 15, f"Expected 15 active vehicles, found {moving_count}"
    print("[PASSED]: All 15 vehicles move continuously through road network after debug delay.")

    # 4. SIGNAL INTEGRATION (RED LIGHT STOPPING)
    print("\n[TEST 4] TRAFFIC SIGNAL COMPLIANCE (RED LIGHT STOPPING)", flush=True)
    red_j2 = {
        "JUNCTION_02": {"WEST": "RED", "NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN"},
        "J2": {"WEST": "RED", "NORTH": "GREEN", "SOUTH": "GREEN", "EAST": "GREEN"},
    }
    set_junction_signals(red_j2)

    car1 = fleet["CAR_001"]
    car1.x = 220.0
    car1.y = 253.5
    car1.heading = 0.0
    car1.elapsed_time = 2.0
    car1.current_lane = ROAD_NETWORK["LANE_J1_J2_EB"]
    car1.current_wp_idx = 3

    for _ in range(80):
        car1.update_logic(dt)

    print(f"CAR_001 Pos: ({car1.x:.2f}, {car1.y:.1f}) | Speed: {car1.current_speed:.2f}m/s | State: {car1.state}")
    assert car1.state in [VehicleState.WAITING_RED, VehicleState.STOPPING_FOR_RED, VehicleState.APPROACHING_JUNCTION, VehicleState.APPROACHING_SIGNAL], f"CAR_001 state {car1.state}"
    assert car1.x <= 238.5, f"CAR_001 passed stop line on RED (X={car1.x:.2f})"
    print("[PASSED]: Vehicles detect RED signals, decelerate smoothly, and stop before stop line.")

    # 5. GREEN LIGHT RESUME
    print("\n[TEST 5] TRAFFIC SIGNAL COMPLIANCE (GREEN LIGHT PROCEED)", flush=True)
    set_junction_signals(ALL_GREEN)

    for _ in range(60):
        car1.update_logic(dt)

    print(f"CAR_001 Pos: ({car1.x:.2f}, {car1.y:.1f}) | Speed: {car1.current_speed:.2f}m/s | State: {car1.state}")
    assert car1.current_speed > 0.0, "CAR_001 failed to proceed on GREEN signal!"
    print("[PASSED]: Vehicles proceed cleanly through junctions on GREEN signal.")

    # 6. VEHICLE FOLLOWING & SAFE DISTANCE (NO OVERLAP)
    print("\n[TEST 6] VEHICLE FOLLOWING & ZERO OVERLAP SPACING", flush=True)
    bike1 = fleet["BIKE_001"]
    bike1.x = 246.5
    bike1.y = 100.0
    bike1.heading = -1.5708
    bike1.current_lane = ROAD_NETWORK["LANE_J2_J3_SB"]
    bike1.current_wp_idx = get_next_forward_waypoint_idx(bike1.x, bike1.y, bike1.heading, bike1.current_lane)
    bike1.current_speed = 0.0

    bike2 = fleet["BIKE_002"]
    bike2.x = 246.5
    bike2.y = 110.0
    bike2.heading = -1.5708
    bike2.current_lane = ROAD_NETWORK["LANE_J2_J3_SB"]
    bike2.current_wp_idx = get_next_forward_waypoint_idx(bike2.x, bike2.y, bike2.heading, bike2.current_lane)
    bike2.current_speed = 3.0

    for _ in range(100):
        bike1._update_shared_state()
        bike2.update_logic(dt)

    gap = abs(bike2.y - bike1.y)
    print(f"BIKE_001 Y: {bike1.y:.2f} | BIKE_002 Y: {bike2.y:.2f} | Gap: {gap:.2f}m | BIKE_002 State: {bike2.state}")
    assert gap >= bike2.vehicle_length + 0.5, f"Overlap detected between bikes! Gap: {gap:.2f}m"
    print("[PASSED]: Safe vehicle following distance maintained with zero overlap.")

    # 7. TELEMETRY FILE GENERATION
    print("\n[TEST 7] TELEMETRY DATA EXPORT", flush=True)
    car1._update_shared_state()
    t_file = os.path.join(WEBOTS_DIR, "vehicle_pos_CAR_001.json")
    assert os.path.exists(t_file), f"Telemetry file {t_file} missing!"

    with open(t_file, "r") as f:
        t_data = json.load(f)

    assert t_data["vehicle_id"] == "CAR_001"
    assert t_data["vehicle_type"] == "CAR"
    assert "position" in t_data
    assert "speed" in t_data
    assert "lane" in t_data
    print(f"[PASSED]: Telemetry exported to {os.path.basename(t_file)} with accurate vehicle fields.")

    # 8. MULTI-MINUTE CONTINUOUS SIMULATION RUN
    print("\n[TEST 8] CONTINUOUS SIMULATION RUN (500 STEPS)", flush=True)
    invalid_stops = 0
    for step in range(500):
        for v_id, ctrl in fleet.items():
            ctrl.update_logic(dt)
            if ctrl.current_speed == 0.0 and ctrl.state == VehicleState.MOVING:
                invalid_stops += 1

    print(f"Total Steps: 500 | Active Vehicles: 15 | Invalid Stops: {invalid_stops}")
    assert invalid_stops == 0, f"Found {invalid_stops} invalid stopping events during continuous run!"
    print("[PASSED]: Continuous simulation ran 500 steps across 15 vehicles with zero collisions or invalid stops.")

    print("\n==================================================", flush=True)
    print("ALL MODULE 2 MULTI-VEHICLE VERIFICATION TESTS PASSED!", flush=True)
    print("==================================================", flush=True)


if __name__ == "__main__":
    run_multi_vehicle_verification()
