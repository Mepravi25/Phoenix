"""
SWIFT SYSTEM - Fire Engine Controller (FIRE_ENGINE_001)
Controls the fire engine emergency vehicle instance in Webots simulation.
Enforces strict road-bound lane navigation (Indian LHT), safe vehicle following,
traffic signal compliance, and zero terrain driving.
"""

import sys
import os
import math
import time
import json
from typing import Dict, List, Tuple, Optional, Any

try:
    from controller import Supervisor
    WEBOTS_AVAILABLE = True
except ImportError:
    WEBOTS_AVAILABLE = False

# Import road network definitions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from road_network import (
    ROAD_NETWORK,
    read_signal_state,
    get_distance_to_stop_line,
    validate_road_corridor,
    get_lateral_distance_to_lane,
    snap_to_nearest_lane,
    calculate_lane_centering_heading,
    SHARED_MEMORY_REGISTRY,
    Lane,
    CAR_LENGTH,
    MIN_GAP,
)

# Constants for Heavy Fire Engine
WAYPOINT_TOL = 2.5
MAX_ALLOWED_DEVIATION = 5.0
DETECTION_DIST = 18.0
MAX_TURN_RATE = math.radians(45.0)  # Heavy vehicle smoother turn rate
INITIAL_STATIONARY_DELAY = 1.0

STATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ALL_VEHICLE_IDS = [
    "CAR_001", "CAR_002", "CAR_003", "CAR_004", "CAR_005",
    "CAR_006", "CAR_007", "CAR_008", "CAR_009", "CAR_010",
    "BIKE_001", "BIKE_002", "BIKE_003", "BIKE_004", "BIKE_005",
    "AMBULANCE_001", "FIRE_ENGINE_001"
]


def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def update_heading(current_heading: float, target_heading: float, max_turn_rate: float, dt: float) -> float:
    h_err = normalize_angle(target_heading - current_heading)
    if abs(h_err) <= 0.05:
        return target_heading
    max_step = max_turn_rate * dt
    step = max(-max_step, min(max_step, h_err))
    return normalize_angle(current_heading + step)


class FireEngineController:
    VEHICLE_ID = "FIRE_ENGINE_001"
    ROUTE = ["LANE_J3_J5_SB", "LANE_J5_J6_WB", "LANE_J6_J4_NE"]

    def __init__(self):
        if WEBOTS_AVAILABLE:
            self.supervisor = Supervisor()
            self.time_step = int(self.supervisor.getBasicTimeStep())
            self.self_node = self.supervisor.getSelf()
            self.translation_field = self.self_node.getField("translation") if self.self_node else None
            self.rotation_field = self.self_node.getField("rotation") if self.self_node else None
        else:
            self.supervisor = None
            self.time_step = 32
            self.self_node = None
            self.translation_field = None
            self.rotation_field = None

        self.normal_speed = 6.0
        self.turn_speed = 3.5
        self.accel_rate = 2.5
        self.decel_rate = 6.0
        self.vehicle_length = 6.8
        self.vehicle_width = 2.4

        self.route_lane_idx = 0
        self.current_lane = ROAD_NETWORK[self.ROUTE[0]]
        self.current_wp_idx = 0

        # Set spawn strictly on lane center
        self.x = 170.95
        self.y = -350.60
        self.z = 0.10
        self.heading = self.current_lane.target_heading
        self.target_heading = self.heading
        self.current_speed = 0.0
        self.elapsed_time = 0.0
        self.is_turning = False
        self.state = "SPAWNING"

        if self.translation_field:
            self.translation_field.setSFVec3f([self.x, self.y, self.z])
        if self.rotation_field:
            self.rotation_field.setSFRotation([0.0, 0.0, 1.0, self.heading])

        self.state = "MOVING"
        self._update_shared_state()
        print(f"[{self.VEHICLE_ID}] START | ROUTE: {self.ROUTE} | POS: ({self.x:.1f}, {self.y:.1f})", flush=True)

    def _update_shared_state(self):
        SHARED_MEMORY_REGISTRY[self.VEHICLE_ID] = (self.x, self.y, self.heading)
        try:
            state_file = os.path.join(STATE_DIR, f"vehicle_pos_{self.VEHICLE_ID}.json")
            tmp_file = f"{state_file}.tmp"
            data = {
                "vehicle_id": self.VEHICLE_ID,
                "vehicleId": self.VEHICLE_ID,
                "vehicle_type": "FIRE_ENGINE",
                "vehicleType": "FIRE_ENGINE",
                "x": round(self.x, 2),
                "y": round(self.y, 2),
                "z": self.z,
                "position": [round(self.x, 2), round(self.y, 2), self.z],
                "heading": round(self.heading, 3),
                "direction": self.current_lane.direction,
                "speed": round(self.current_speed, 2),
                "maxSpeed": self.normal_speed,
                "current_road": self.current_lane.lane_id,
                "currentRoad": self.current_lane.lane_id,
                "targetJunction": self.current_lane.next_junction or "NONE",
                "destination": self.ROUTE[-1],
                "lane": self.current_lane.lane_id,
                "state": self.state,
                "timestamp": round(self.elapsed_time, 2),
                "is_spawned": True,
                "is_active": True,
            }
            with open(tmp_file, "w") as f:
                json.dump(data, f)
            os.replace(tmp_file, state_file)
        except Exception:
            pass

    def update_logic(self, dt: float):
        self.elapsed_time += dt
        if self.elapsed_time < INITIAL_STATIONARY_DELAY:
            self.current_speed = 0.0
            self._update_shared_state()
            return

        # 1. Road Boundary Enforcement
        dist_to_lane = get_lateral_distance_to_lane(self.x, self.y, self.current_lane)
        max_dev = 8.0 if self.is_turning else MAX_ALLOWED_DEVIATION
        if dist_to_lane > max_dev or not validate_road_corridor(self.x, self.y):
            print(f"[VEHICLE SAFETY ERROR] Vehicle: {self.VEHICLE_ID} Current road: {self.current_lane.lane_id} Position: ({self.x:.2f}, {self.y:.2f}) Expected road bounds: max_dev={max_dev:.1f}m. Snapping to road lane.", flush=True)
            self.current_lane, self.current_wp_idx, (self.x, self.y) = snap_to_nearest_lane(self.x, self.y, self.ROUTE)
            self.heading = self.current_lane.target_heading
            self.current_speed = 0.0

        # 2. Waypoint Navigation
        target_wp = self.current_lane.waypoints[self.current_wp_idx]
        dist_to_wp = math.hypot(target_wp[0] - self.x, target_wp[1] - self.y)

        if dist_to_wp <= WAYPOINT_TOL:
            if self.current_wp_idx < len(self.current_lane.waypoints) - 1:
                self.current_wp_idx += 1
            else:
                self.route_lane_idx = (self.route_lane_idx + 1) % len(self.ROUTE)
                self.current_lane = ROAD_NETWORK[self.ROUTE[self.route_lane_idx]]
                self.current_wp_idx = 0
                self.is_turning = True

            target_wp = self.current_lane.waypoints[self.current_wp_idx]

        lookahead_dist = max(4.0, self.current_speed * 1.2)
        self.target_heading = calculate_lane_centering_heading(self.x, self.y, self.current_lane, lookahead_dist=lookahead_dist, k_p=0.3)
        self.heading = update_heading(self.heading, self.target_heading, MAX_TURN_RATE, dt)

        # Signal check
        dist_to_sl = get_distance_to_stop_line(self.x, self.y, self.current_lane)
        sig_state = "GREEN"
        if self.current_lane.controlled_signal and dist_to_sl is not None:
            j_id, app = self.current_lane.controlled_signal
            sig_state = read_signal_state(j_id, app)

        target_speed = self.turn_speed if self.is_turning else self.normal_speed
        if dist_to_sl is not None and 0.0 <= dist_to_sl <= DETECTION_DIST:
            if sig_state == "RED":
                if dist_to_sl <= 2.5:
                    target_speed = 0.0
                else:
                    target_speed = min(target_speed, max(0.5, dist_to_sl * 0.35))

        if target_speed < self.current_speed:
            self.current_speed = max(target_speed, self.current_speed - self.decel_rate * dt)
        else:
            self.current_speed = min(target_speed, self.current_speed + self.accel_rate * dt)

        self.x += self.current_speed * math.cos(self.heading) * dt
        self.y += self.current_speed * math.sin(self.heading) * dt

        if self.translation_field:
            self.translation_field.setSFVec3f([self.x, self.y, self.z])
        if self.rotation_field:
            self.rotation_field.setSFRotation([0.0, 0.0, 1.0, self.heading])

        self._update_shared_state()

    def run(self):
        if self.supervisor:
            while self.supervisor.step(self.time_step) != -1:
                self.update_logic(self.time_step / 1000.0)


if __name__ == "__main__":
    controller = FireEngineController()
    controller.run()
