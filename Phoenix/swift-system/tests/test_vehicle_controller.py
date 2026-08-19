"""
Unit tests for SWIFT SYSTEM Module 3 - Normal Vehicle Controller.
"""

import sys
import os
import math
import json
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webots", "controllers", "vehicle_controller")))
from vehicle_controller import (
    NormalVehicleController,
    VEHICLE_CONFIGS,
    get_clockwise_route_waypoints,
    get_counter_clockwise_route_waypoints,
    SIGNAL_STATE_FILE,
    POSITIONS_STATE_FILE,
)


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Clean up state files before and after each test."""
    for filepath in [SIGNAL_STATE_FILE, POSITIONS_STATE_FILE]:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
    yield
    for filepath in [SIGNAL_STATE_FILE, POSITIONS_STATE_FILE]:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass


def test_vehicle_initialization():
    car1 = NormalVehicleController("CAR_001")
    assert car1.vehicle_id == "CAR_001"
    assert car1.spawn_delay == 0.0
    assert car1.max_speed == 11.0
    assert len(car1.waypoints) > 0

    car5 = NormalVehicleController("CAR_005")
    assert car5.vehicle_id == "CAR_005"
    assert car5.spawn_delay == 8.0
    assert car5.max_speed == 11.2


def test_staggered_spawning():
    car2 = NormalVehicleController("CAR_002")
    assert car2.is_spawned is False
    assert car2.current_speed == 0.0

    # Step at t = 1.0s (less than spawn_delay 2.0s)
    car2.update_logic(1.0)
    assert car2.is_spawned is False

    # Step at t = 2.1s (exceeds spawn_delay 2.0s)
    car2.update_logic(1.1)
    assert car2.is_spawned is True


def test_waypoint_movement():
    car1 = NormalVehicleController("CAR_001")
    car1.update_logic(0.1) # Activate
    initial_x, initial_y = car1.x, car1.y

    # Simulate 2 seconds of movement
    dt = 0.032
    for _ in range(60):
        car1.update_logic(dt)

    assert car1.current_speed > 0.0
    assert math.hypot(car1.x - initial_x, car1.y - initial_y) > 0.5


def test_red_light_stopping():
    # Set J2 WEST signal to RED in state file
    signal_data = {
        "J2": {"WEST": "RED", "EAST": "RED", "NORTH": "GREEN", "SOUTH": "GREEN"}
    }
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    # Place CAR_001 10m before J2 WEST stop line (X=41.0, Y=46.5)
    car1.x = 31.0
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_wp_idx = 2  # Waypoint index pointing to stop line

    dt = 0.032
    # Advance simulation until vehicle approaches stop line
    for _ in range(100):
        car1.update_logic(dt)

    # Vehicle must stop before crossing stop line (X <= 41.5)
    assert car1.x <= 41.5
    assert car1.current_speed == 0.0


def test_green_light_proceeding():
    # Set J2 WEST signal to GREEN
    signal_data = {
        "J2": {"WEST": "GREEN", "EAST": "GREEN", "NORTH": "RED", "SOUTH": "RED"}
    }
    with open(SIGNAL_STATE_FILE, "w") as f:
        json.dump(signal_data, f)

    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = 31.0
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_wp_idx = 2

    dt = 0.032
    for _ in range(50):
        car1.update_logic(dt)

    # Vehicle must accelerate and move past stop line
    assert car1.current_speed > 3.0
    assert car1.x > 31.0


def test_safe_distance_car_following():
    # Mock positions file with CAR_002 stopped ahead at X=15.0, Y=46.5
    car2 = NormalVehicleController("CAR_002")
    car2.is_spawned = True
    car2.x = 15.0
    car2.y = 46.5
    car2.heading = 0.0
    car2.current_speed = 0.0
    car2._update_registry()

    car1 = NormalVehicleController("CAR_001")
    car1.is_spawned = True
    car1.x = 0.0  # 15m center distance behind CAR_002 (at X=15.0), bumper distance = 10.5m
    car1.y = 46.5
    car1.heading = 0.0
    car1.current_wp_idx = 2  # Target waypoint at X=41.0, Y=46.5 (ahead in +X direction)
    car1._update_registry()

    dt = 0.032
    for _ in range(100):
        car1.update_logic(dt)

    # CAR_001 must slow down / stop to maintain safe distance and avoid collision
    assert car1.current_speed == 0.0
    assert car1.x < 15.0 - 4.5  # Does not collide with CAR_002
