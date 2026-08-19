"""
SWIFT SYSTEM - Webots Multi-Vehicle Traffic Controller (Module 2 Critical Fix)
Controls individual vehicle instances (CAR_001..CAR_010, BIKE_001..BIKE_005).
Enforces road-bound waypoint navigation, Indian Left-Hand Traffic (LHT), 8-state vehicle machine,
traffic signal integration, safe vehicle following distance, and telemetry export.
"""

import sys
import os
import math
import time
import json
from enum import Enum
from typing import List, Dict, Tuple, Optional, Any

try:
    from controller import Supervisor
    WEBOTS_AVAILABLE = True
except ImportError:
    WEBOTS_AVAILABLE = False

# Import road_network module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from road_network import (
    ROAD_NETWORK,
    VEHICLE_ROUTES,
    read_signal_state,
    get_distance_to_stop_line,
    validate_road_corridor,
    get_nearest_lane_waypoint,
    get_next_forward_waypoint_idx,
    get_lateral_distance_to_lane,
    snap_to_nearest_lane,
    get_lane_projection_and_offset,
    calculate_lookahead_target,
    calculate_lane_centering_heading,
    SHARED_MEMORY_REGISTRY,
    Lane,
    CAR_LENGTH,
    MIN_GAP,
    STOP_VEHICLE_DISTANCE,
    LANE_WIDTH,
)

# Constants
WAYPOINT_TOL = 2.5      # meters tolerance to advance to next waypoint
MAX_ALLOWED_DEVIATION = 6.0  # meters lateral deviation threshold for road snapping (hard road boundary)
DETECTION_DIST = 18.0   # meters forward lookahead distance for signals
MAX_TURN_RATE = math.radians(60.0) # max radians per second turn rate for smooth turns
INITIAL_STATIONARY_DELAY = 1.0  # seconds initial stationary delay

STATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIGNAL_STATE_FILE = os.path.join(STATE_DIR, "traffic_signal_states.json")
POSITIONS_STATE_FILE = os.path.join(STATE_DIR, "vehicle_positions.json")
NUM_NORMAL_VEHICLES = 15
VEHICLE_CENTER_Z = 0.42
ROAD_SURFACE_Z = 0.10
VEHICLE_BOTTOM_OFFSET = 0.32
VEHICLE_LENGTH = 4.4
MIN_FOLLOWING_DISTANCE = 4.0

ALL_VEHICLE_IDS = [
    "CAR_001", "CAR_002", "CAR_003", "CAR_004", "CAR_005",
    "CAR_006", "CAR_007", "CAR_008", "CAR_009", "CAR_010",
    "BIKE_001", "BIKE_002", "BIKE_003", "BIKE_004", "BIKE_005",
    "AMBULANCE_001"
]


def get_clockwise_route_waypoints() -> List[Tuple[float, float]]:
    wps = []
    from road_network import CLOCKWISE_LANE_LOOP
    for lane_id in CLOCKWISE_LANE_LOOP:
        wps.extend(ROAD_NETWORK[lane_id].waypoints)
    return wps


def get_counter_clockwise_route_waypoints() -> List[Tuple[float, float]]:
    counter_loop = ["LANE_J4_J1_NB", "LANE_J1_J2_EB", "LANE_J2_J3_SB", "LANE_J3_J4_WB"]
    wps = []
    for lane_id in counter_loop:
        wps.extend(ROAD_NETWORK[lane_id].waypoints)
    return wps


def normalize_angle(angle: float) -> float:
    """Wraps angle into [-pi, pi]."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle



def update_heading(current_heading: float, target_heading: float, max_turn_rate: float, dt: float) -> float:
    """Smoothly interpolates heading toward target_heading using max_turn_rate."""
    h_err = normalize_angle(target_heading - current_heading)
    if abs(h_err) <= 0.05:
        return target_heading
    max_step = max_turn_rate * dt
    step = max(-max_step, min(max_step, h_err))
    return normalize_angle(current_heading + step)


class VehicleState(str, Enum):
    SPAWNING = "SPAWNING"
    MOVING = "MOVING"
    APPROACHING_JUNCTION = "APPROACHING_JUNCTION"
    CHECK_SIGNAL = "CHECK_SIGNAL"
    WAITING_RED = "WAITING_RED"
    MOVING_THROUGH_JUNCTION = "MOVING_THROUGH_JUNCTION"
    FOLLOWING_VEHICLE = "FOLLOWING_VEHICLE"
    STOPPED = "STOPPED"
    DESTINATION_REACHED = "DESTINATION_REACHED"

    # Backward compatibility aliases
    STOPPING_FOR_RED = "STOPPING_FOR_RED"
    WAITING_IN_QUEUE = "WAITING_IN_QUEUE"
    PASSING_JUNCTION = "PASSING_JUNCTION"
    CHANGING_WAYPOINT = "CHANGING_WAYPOINT"
    APPROACHING_SIGNAL = "APPROACHING_SIGNAL"


VEHICLE_CONFIGS = {
    # 10 CARS
    "CAR_001": {"type": "CAR", "normal_speed": 6.0, "turn_speed": 3.5, "accel_rate": 3.0, "decel_rate": 6.0, "length": 4.4, "width": 1.8},
    "CAR_002": {"type": "CAR", "normal_speed": 6.0, "turn_speed": 3.5, "accel_rate": 3.0, "decel_rate": 6.0, "length": 4.4, "width": 1.8},
    "CAR_003": {"type": "CAR", "normal_speed": 6.0, "turn_speed": 3.5, "accel_rate": 3.0, "decel_rate": 6.0, "length": 4.4, "width": 1.8},
    "CAR_004": {"type": "CAR", "normal_speed": 6.0, "turn_speed": 3.5, "accel_rate": 3.0, "decel_rate": 6.0, "length": 4.4, "width": 1.8},
    "CAR_005": {"type": "CAR", "normal_speed": 6.2, "turn_speed": 3.6, "accel_rate": 3.0, "decel_rate": 6.0, "length": 4.4, "width": 1.8},
    "CAR_006": {"type": "CAR", "normal_speed": 6.0, "turn_speed": 3.5, "accel_rate": 3.0, "decel_rate": 6.0, "length": 4.4, "width": 1.8},
    "CAR_007": {"type": "CAR", "normal_speed": 6.5, "turn_speed": 3.8, "accel_rate": 3.2, "decel_rate": 6.0, "length": 4.4, "width": 1.8},
    "CAR_008": {"type": "CAR", "normal_speed": 5.8, "turn_speed": 3.2, "accel_rate": 2.8, "decel_rate": 6.0, "length": 4.4, "width": 1.8},
    "CAR_009": {"type": "CAR", "normal_speed": 6.0, "turn_speed": 3.5, "accel_rate": 3.0, "decel_rate": 6.0, "length": 4.4, "width": 1.8},
    "CAR_010": {"type": "CAR", "normal_speed": 6.2, "turn_speed": 3.6, "accel_rate": 3.0, "decel_rate": 6.0, "length": 4.4, "width": 1.8},

    # 5 BIKES / MOTORCYCLES
    "BIKE_001": {"type": "BIKE", "normal_speed": 7.0, "turn_speed": 4.2, "accel_rate": 4.0, "decel_rate": 7.0, "length": 2.0, "width": 0.8},
    "BIKE_002": {"type": "BIKE", "normal_speed": 7.5, "turn_speed": 4.5, "accel_rate": 4.2, "decel_rate": 7.0, "length": 2.0, "width": 0.8},
    "BIKE_003": {"type": "BIKE", "normal_speed": 7.0, "turn_speed": 4.2, "accel_rate": 4.0, "decel_rate": 7.0, "length": 2.0, "width": 0.8},
    "BIKE_004": {"type": "BIKE", "normal_speed": 7.2, "turn_speed": 4.3, "accel_rate": 4.1, "decel_rate": 7.0, "length": 2.0, "width": 0.8},
    "BIKE_005": {"type": "BIKE", "normal_speed": 7.0, "turn_speed": 4.2, "accel_rate": 4.0, "decel_rate": 7.0, "length": 2.0, "width": 0.8},

    # AMBULANCE
    "AMBULANCE_001": {"type": "AMBULANCE", "normal_speed": 8.5, "turn_speed": 5.0, "accel_rate": 4.5, "decel_rate": 8.0, "length": 5.5, "width": 2.2},
}


# Valid initial spawn positions directly on LHT road waypoints
VEHICLE_SPAWNS = {
    "CAR_001": {"x": -250.0, "y": 253.5, "heading": 0.0},
    "CAR_002": {"x": -246.5, "y": 250.0, "heading": -1.5708},
    "CAR_003": {"x": -248.43, "y": -246.87, "heading": -0.4636},
    "CAR_004": {"x": -252.47, "y": 247.53, "heading": 2.3562},
    "CAR_005": {"x": 247.53, "y": 252.47, "heading": 0.7854},
    "CAR_006": {"x": 219.72, "y": -46.51, "heading": 0.0792},
    "CAR_007": {"x": -251.35, "y": -253.23, "heading": 2.7468},
    "CAR_008": {"x": 153.28, "y": -451.23, "heading": -1.9296},
    "CAR_009": {"x": -150.0, "y": 253.5, "heading": 0.0},
    "CAR_010": {"x": -251.37, "y": -246.78, "heading": 0.4023},

    "BIKE_001": {"x": 50.0, "y": 253.5, "heading": 0.0},
    "BIKE_002": {"x": -246.5, "y": 50.0, "heading": -1.5708},
    "BIKE_003": {"x": -88.43, "y": -326.87, "heading": -0.4636},
    "BIKE_004": {"x": 247.48, "y": 189.65, "heading": -1.6705},
    "BIKE_005": {"x": -50.0, "y": 253.5, "heading": 0.0},

    "AMBULANCE_001": {"x": -248.43, "y": -246.87, "heading": -0.4636},
}


class NormalVehicleController:
    """
    Independent Vehicle Controller program/instance.
    Governs a single vehicle's road-bound navigation, speed, state machine, and signal compliance.
    """
    def __init__(self, vehicle_id: Optional[str] = None):
        if WEBOTS_AVAILABLE:
            self.supervisor = Supervisor()
            self.vehicle_id = vehicle_id or self.supervisor.getName()
            self.time_step = int(self.supervisor.getBasicTimeStep())
            self.self_node = self.supervisor.getSelf()
            self.translation_field = self.self_node.getField("translation") if self.self_node else None
            self.rotation_field = self.self_node.getField("rotation") if self.self_node else None
        else:
            self.supervisor = None
            self.vehicle_id = vehicle_id or "CAR_001"
            self.time_step = 32
            self.self_node = None
            self.translation_field = None
            self.rotation_field = None

        config = VEHICLE_SPAWNS.get(self.vehicle_id, {"x": -230.0, "y": 253.5, "heading": 0.0})
        v_cfg = VEHICLE_CONFIGS.get(self.vehicle_id, {
            "type": "CAR", "normal_speed": 6.0, "turn_speed": 3.5, "accel_rate": 3.0, "decel_rate": 6.0, "length": 4.4, "width": 1.8
        })

        self.v_type = v_cfg.get("type", "CAR")
        self.normal_speed = v_cfg.get("normal_speed", 6.0)
        self.turn_speed = v_cfg.get("turn_speed", 3.5)
        self.accel_rate = v_cfg.get("accel_rate", 3.0)
        self.decel_rate = v_cfg.get("decel_rate", 6.0)
        self.vehicle_length = v_cfg.get("length", 4.4)
        self.vehicle_width = v_cfg.get("width", 1.8)

        self.x = config["x"]
        self.y = config["y"]
        self.z = 0.10  # Top road surface elevation
        self.heading = config["heading"]
        self.current_speed = 0.0
        self.elapsed_time = 0.0

        # Assigned route sequence
        self.route = VEHICLE_ROUTES.get(self.vehicle_id, ["LANE_J1_J2_EB", "LANE_J2_J3_SB", "LANE_J3_J4_WB", "LANE_J4_J1_NB"])
        self.route_lane_idx = 0
        
        # Enforce exact initial LHT road placement and snapping
        self.current_lane, self.current_wp_idx, (self.x, self.y) = snap_to_nearest_lane(self.x, self.y, self.route)
        self.target_heading = self.current_lane.target_heading
        self.heading = self.target_heading
        self.is_turning = False

        self.state = VehicleState.SPAWNING
        self.is_spawned = True
        self.is_active = True
        self.last_debug_log = ""

        # Set initial position directly on LHT lane waypoint
        if self.translation_field:
            self.translation_field.setSFVec3f([self.x, self.y, self.z])
        if self.rotation_field:
            self.rotation_field.setSFRotation([0.0, 0.0, 1.0, self.heading])

        self.state = VehicleState.MOVING
        self._update_shared_state()
        print(f"[VEHICLE SPAWN]\n{self.vehicle_id} ({self.v_type}) created on {self.current_lane.lane_id}", flush=True)
        print(f"[{self.vehicle_id}] START | TYPE: {self.v_type} | ROUTE: {self.route} | POS: ({self.x:.1f}, {self.y:.1f})", flush=True)


    def _update_shared_state(self):
        """Exports JSON telemetry and shared memory record for inter-vehicle detection."""
        SHARED_MEMORY_REGISTRY[self.vehicle_id] = (self.x, self.y, self.heading)
        try:
            state_file = os.path.join(STATE_DIR, f"vehicle_pos_{self.vehicle_id}.json")
            tmp_file = f"{state_file}.tmp"

            target_wp = self.current_lane.waypoints[self.current_wp_idx] if self.current_wp_idx < len(self.current_lane.waypoints) else self.current_lane.waypoints[-1]
            next_wp = self.current_lane.waypoints[min(self.current_wp_idx + 1, len(self.current_lane.waypoints) - 1)]

            data = {
                "vehicle_id": self.vehicle_id,
                "vehicleId": self.vehicle_id,
                "vehicle_type": self.v_type,
                "vehicleType": self.v_type,
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
                "currentWaypoint": target_wp,
                "nextWaypoint": next_wp,
                "targetJunction": self.current_lane.next_junction or "NONE",
                "destination": self.route[-1],
                "lane": self.current_lane.lane_id,
                "state": str(self.state),
                "timestamp": round(self.elapsed_time, 2),
                "is_spawned": self.is_spawned,
                "is_active": self.is_active,
            }
            with open(tmp_file, "w") as f:
                json.dump(data, f)
            os.replace(tmp_file, state_file)
        except Exception:
            pass

    def _get_other_vehicles(self) -> Dict[str, Tuple[float, float, float]]:
        other_vehicles = {}
        other_ids = [v for v in ALL_VEHICLE_IDS if v != self.vehicle_id]

        if self.supervisor:
            for v_id in other_ids:
                node = self.supervisor.getFromDef(v_id)
                if node:
                    t_field = node.getField("translation")
                    r_field = node.getField("rotation")
                    if t_field:
                        vec = t_field.getSFVec3f()
                        rot = r_field.getSFRotation() if r_field else [0, 0, 1, 0]
                        h = rot[3] if len(rot) >= 4 else 0.0
                        other_vehicles[v_id] = (vec[0], vec[1], h)

        for v_id in other_ids:
            if v_id not in other_vehicles:
                if v_id in SHARED_MEMORY_REGISTRY:
                    other_vehicles[v_id] = SHARED_MEMORY_REGISTRY[v_id]
                else:
                    s_file = os.path.join(STATE_DIR, f"vehicle_pos_{v_id}.json")
                    if os.path.exists(s_file):
                        try:
                            if (time.time() - os.path.getmtime(s_file)) <= 2.0:
                                with open(s_file, "r") as f:
                                    data = json.load(f)
                                other_vehicles[v_id] = (data["x"], data["y"], data.get("heading", 0.0))
                        except Exception:
                            pass

        return other_vehicles

    def _get_nearest_lead_vehicle(self, other_vehicles: Dict[str, Tuple[float, float, float]]) -> Tuple[Optional[str], float]:
        nearest_id = None
        min_dist = 999.0

        for other_id, (ox, oy, o_h) in other_vehicles.items():
            dx = ox - self.x
            dy = oy - self.y

            fw_proj = dx * math.cos(self.heading) + dy * math.sin(self.heading)
            lat_dist = abs(-dx * math.sin(self.heading) + dy * math.cos(self.heading))
            h_diff = abs(normalize_angle(o_h - self.heading))

            if fw_proj >= 0.5 and lat_dist <= (LANE_WIDTH / 1.5) and h_diff <= math.radians(45.0):
                if fw_proj < min_dist:
                    min_dist = fw_proj
                    nearest_id = other_id

        return nearest_id, min_dist

    def update_logic(self, dt: float):
        self.elapsed_time += dt

        # Initial Stationary Delay period
        if self.elapsed_time < INITIAL_STATIONARY_DELAY:
            self.current_speed = 0.0
            self.state = VehicleState.STOPPED
            if self.translation_field:
                self.translation_field.setSFVec3f([self.x, self.y, self.z])
            if self.rotation_field:
                self.rotation_field.setSFRotation([0.0, 0.0, 1.0, self.heading])
            self._update_shared_state()
            return

        # 1. MANDATORY ROAD ASSIGNMENT VALIDATION
        # Section 1 Rule: A vehicle MUST NOT be allowed to move unless currentRoad, currentLane, and currentWaypoint are valid.
        if (self.current_lane is None or 
            self.current_lane.lane_id is None or 
            self.current_wp_idx is None or 
            self.current_wp_idx >= len(self.current_lane.waypoints)):
            self.current_speed = 0.0
            self.state = VehicleState.STOPPED
            self._update_shared_state()
            return

        # 2. HARD ROAD BOUNDARY & AUTOMATIC ROAD RECOVERY
        # Section 4 & 5 Rules: Calculate distance from vehicle to assigned lane; if > max_dev, stop & recover.
        dist_to_lane = get_lateral_distance_to_lane(self.x, self.y, self.current_lane)
        max_dev = 8.5 if (self.is_turning or self.state in [VehicleState.MOVING_THROUGH_JUNCTION, VehicleState.PASSING_JUNCTION]) else MAX_ALLOWED_DEVIATION
        if dist_to_lane > max_dev or not validate_road_corridor(self.x, self.y):
            print(f"[AUTOMATIC_ROAD_RECOVERY] vehicle={self.vehicle_id} pos=({self.x:.2f}, {self.y:.2f}) dist={dist_to_lane:.2f}m > max={max_dev:.1f}m | Snapping to lane {self.current_lane.lane_id}", flush=True)
            self.current_speed = 0.0
            self.state = VehicleState.STOPPED
            self.current_lane, self.current_wp_idx, (self.x, self.y) = snap_to_nearest_lane(self.x, self.y, self.route)
            self.heading = self.current_lane.target_heading
            self._update_shared_state()
            return


        # 3. Waypoint Progression Along Current Lane
        target_wp = self.current_lane.waypoints[self.current_wp_idx]

        # Verify current_wp_idx is ahead along travel direction
        dx = target_wp[0] - self.x
        dy = target_wp[1] - self.y
        dot = dx * self.current_lane.unit_vector[0] + dy * self.current_lane.unit_vector[1]
        if dot < -5.0 and self.current_wp_idx < len(self.current_lane.waypoints) - 1:
            self.current_wp_idx = get_next_forward_waypoint_idx(self.x, self.y, self.heading, self.current_lane)
            target_wp = self.current_lane.waypoints[self.current_wp_idx]

        dist_to_wp = math.hypot(target_wp[0] - self.x, target_wp[1] - self.y)


        if dist_to_wp <= WAYPOINT_TOL:
            if self.current_wp_idx < len(self.current_lane.waypoints) - 1:
                self.current_wp_idx += 1
                self.state = VehicleState.CHANGING_WAYPOINT
            else:
                # Transition to next road lane in route
                old_lane = self.current_lane.lane_id
                self.route_lane_idx = (self.route_lane_idx + 1) % len(self.route)
                self.current_lane = ROAD_NETWORK[self.route[self.route_lane_idx]]
                self.current_wp_idx = 0
                self.is_turning = True
                self.state = VehicleState.MOVING_THROUGH_JUNCTION
                print(f"[{self.vehicle_id}] LANE_TRANSITION: {old_lane} -> {self.current_lane.lane_id}", flush=True)

            target_wp = self.current_lane.waypoints[self.current_wp_idx]

        # Calculate Heading Toward Look-ahead Target with Lane Centering
        lookahead_dist = max(4.0, self.current_speed * 1.2)
        self.target_heading = calculate_lane_centering_heading(self.x, self.y, self.current_lane, lookahead_dist=lookahead_dist, k_p=0.3)

        self.heading = update_heading(self.heading, self.target_heading, MAX_TURN_RATE, dt)
        if abs(normalize_angle(self.current_lane.target_heading - self.heading)) <= 0.1:
            self.is_turning = False

        # 4. Traffic Signal Compliance
        dist_to_sl = get_distance_to_stop_line(self.x, self.y, self.current_lane)
        sig_name = "NONE"
        sig_state = "GREEN"

        if self.current_lane.controlled_signal and dist_to_sl is not None:
            j_id, app = self.current_lane.controlled_signal
            sig_name = f"{j_id}_{app}"
            sig_state = read_signal_state(j_id, app)

        # 5. Lead Vehicle Search & Safe Spacing
        other_vehicles = self._get_other_vehicles()
        lead_id, lead_dist = self._get_nearest_lead_vehicle(other_vehicles)

        # 6. Decision Hierarchy
        red_stop = False
        signal_slowing = False
        queue_stop = False
        queue_slowing = False
        safety_stop = False

        stop_gap = self.vehicle_length + MIN_GAP

        # Priority 1: SAFETY / COLLISION
        if lead_dist <= self.vehicle_length + 0.2:
            safety_stop = True

        # Priority 2: VEHICLE AHEAD / QUEUE
        safe_following_dist = self.vehicle_length + MIN_GAP + (0.4 * self.current_speed)
        if lead_id is not None:
            if lead_dist <= stop_gap:
                queue_stop = True
            elif lead_dist <= safe_following_dist:
                queue_slowing = True

        # Priority 3: TRAFFIC SIGNAL
        if dist_to_sl is not None and 0.0 <= dist_to_sl <= DETECTION_DIST:
            if sig_state == "RED":
                if dist_to_sl <= 2.5:
                    red_stop = True
                else:
                    signal_slowing = True
            elif sig_state == "YELLOW" and dist_to_sl > 5.0:
                signal_slowing = True

        # Target Speed Determination
        desired_speed = self.turn_speed if self.is_turning else self.normal_speed

        if safety_stop:
            self.state = VehicleState.STOPPED
            target_speed = 0.0
        elif queue_stop:
            self.state = VehicleState.FOLLOWING_VEHICLE
            target_speed = 0.0
        elif red_stop:
            self.state = VehicleState.WAITING_RED
            target_speed = 0.0
        elif signal_slowing or queue_slowing:
            self.state = VehicleState.APPROACHING_JUNCTION
            if signal_slowing and dist_to_sl:
                target_speed = min(desired_speed, max(0.5, dist_to_sl * 0.35))
            elif queue_slowing:
                target_speed = min(desired_speed, max(0.5, (lead_dist - stop_gap) * 0.4))
            else:
                target_speed = desired_speed
        else:
            self.state = VehicleState.MOVING if not self.is_turning else VehicleState.MOVING_THROUGH_JUNCTION
            target_speed = desired_speed

        # 7. Apply Speed Acceleration / Deceleration
        if target_speed < self.current_speed:
            self.current_speed = max(target_speed, self.current_speed - self.decel_rate * dt)
        else:
            self.current_speed = min(target_speed, self.current_speed + self.accel_rate * dt)

        # 8. Apply Movement toward active waypoint along road
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
    controller = NormalVehicleController()
    controller.run()
