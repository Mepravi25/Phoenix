"""
SWIFT SYSTEM - CAR_002 Controller
Module 2 Baseline Traffic Simulation

Independent controller for CAR_002 (Crimson Red - Clockwise Loop).
Enforces 6-state decision hierarchy, explicit lane network association,
stop line queueing, safe distance spacing, and STEP 17 debug output.
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

# Import road_network module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from road_network import (
    ROAD_NETWORK,
    CLOCKWISE_LANE_LOOP,
    SHARED_MEMORY_REGISTRY,
    read_signal_state,
    get_distance_to_stop_line,
    validate_road_corridor,
    get_nearest_lane_waypoint,
    get_lateral_distance_to_lane,
    snap_to_nearest_lane,
    calculate_lane_centering_heading,
    MAX_ROAD_DEVIATION,
    Lane,
    CAR_LENGTH,
    MIN_GAP,
    STOP_VEHICLE_DISTANCE,
    LANE_WIDTH,
)


# Constants
NORMAL_SPEED = 5.0      # m/s
TURN_SPEED = 3.0        # m/s
WAYPOINT_TOL = 1.5      # meters
ACCEL_RATE = 2.5        # m/s²
DECEL_RATE = 5.0        # m/s²
DETECTION_DIST = 15.0   # meters forward detection for signals
MAX_TURN_RATE = math.radians(90.0)

STATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def update_heading(current_heading: float, target_heading: float, max_turn_rate: float, dt: float) -> float:
    h_err = normalize_angle(target_heading - current_heading)
    if abs(h_err) <= 0.08:
        return target_heading
    max_step = max_turn_rate * dt
    step = max(-max_step, min(max_step, h_err))
    return normalize_angle(current_heading + step)


class Car002Controller:
    VEHICLE_ID = "CAR_002"
    SPAWN_LANE = "LANE_J2_J3_SB"
    SPAWN_X = 246.5
    SPAWN_Y = 230.0
    SPAWN_HEADING = -1.5708

    INITIAL_WP_IDX = 0

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

        self.x = self.SPAWN_X
        self.y = self.SPAWN_Y
        self.z = 0.42
        self.heading = self.SPAWN_HEADING
        self.current_speed = 0.0
        self.elapsed_time = 0.0

        self.lane_loop = CLOCKWISE_LANE_LOOP
        self.current_lane_idx = 1
        self.current_lane, self.current_wp_idx, (self.x, self.y) = snap_to_nearest_lane(self.x, self.y, [self.lane_loop[self.current_lane_idx]])
        self.target_heading = self.current_lane.target_heading
        self.heading = self.target_heading
        self.is_turning = False
        self.state = "MOVING"
        self.is_spawned = True
        self.is_active = True
        self.stuck_logged = False
        self.last_debug_log = ""


        if self.translation_field:
            self.translation_field.setSFVec3f([self.x, self.y, self.z])
        if self.rotation_field:
            self.rotation_field.setSFRotation([0.0, 0.0, 1.0, self.heading])

        self._update_shared_state()
        print(f"[VEHICLE SPAWN]\n{self.VEHICLE_ID} created", flush=True)
        print(f"[VEHICLE ACTIVE]\n{self.VEHICLE_ID} active", flush=True)
        print(f"[{self.VEHICLE_ID}] START | LANE: {self.current_lane.lane_id} | POS: ({self.x:.1f}, {self.y:.1f})", flush=True)

    def _update_shared_state(self):
        SHARED_MEMORY_REGISTRY[self.VEHICLE_ID] = (self.x, self.y, self.heading)
        try:
            state_file = os.path.join(STATE_DIR, f"vehicle_pos_{self.VEHICLE_ID}.json")
            tmp_file = f"{state_file}.tmp"
            data = {
                "vehicle_id": self.VEHICLE_ID,
                "x": self.x,
                "y": self.y,
                "z": self.z,
                "heading": self.heading,
                "speed": self.current_speed,
                "lane": self.current_lane.lane_id,
                "state": self.state,
                "timestamp": self.elapsed_time,
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
        other_ids = ["CAR_001", "CAR_002", "CAR_003", "CAR_004", "AMBULANCE_001"]
        if self.VEHICLE_ID in other_ids:
            other_ids.remove(self.VEHICLE_ID)

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

        # Fallback to shared memory and file state
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
        """Find lead vehicle ahead in same lane corridor."""
        nearest_id = None
        min_dist = 999.0

        for other_id, (ox, oy, o_h) in other_vehicles.items():
            dx = ox - self.x
            dy = oy - self.y

            fw_proj = dx * math.cos(self.heading) + dy * math.sin(self.heading)
            lat_dist = abs(-dx * math.sin(self.heading) + dy * math.cos(self.heading))
            h_diff = abs(normalize_angle(o_h - self.heading))

            if fw_proj >= 1.0 and lat_dist <= (LANE_WIDTH / 2.0) and h_diff <= math.radians(45.0):
                if fw_proj < min_dist:
                    min_dist = fw_proj
                    nearest_id = other_id

        return nearest_id, min_dist

    def _print_debug(
        self,
        reason: str,
        sig_name: str = "NONE",
        sig_state: str = "NONE",
        dist_stop: float = 999.0,
        lead_id: Optional[str] = None,
        lead_dist: float = 999.0,
    ):
        """STEP 17 Debug output formatting."""
        valid_reasons = ["RED_SIGNAL", "VEHICLE_AHEAD", "COLLISION_SAFETY", "CLEAR_PATH"]
        if reason not in valid_reasons:
            print(f"ERROR — INVALID STOP | Vehicle {self.VEHICLE_ID} reason: {reason}", flush=True)

        lead_str = lead_id if lead_id else "NONE"
        lead_dist_str = f"{lead_dist:.1f}m" if lead_id else "N/A"
        dist_stop_str = f"{dist_stop:.1f}m" if dist_stop < 900.0 else "N/A"

        debug_msg = (
            f"--------------------------------------------------\n"
            f"## VEHICLE STOP DEBUG\n"
            f"Vehicle ID: {self.VEHICLE_ID}\n"
            f"Current Lane: {self.current_lane.lane_id}\n"
            f"Direction: {self.current_lane.direction}\n"
            f"Current Position: ({self.x:.1f}, {self.y:.1f})\n"
            f"Current State: {self.state}\n"
            f"Target Signal: {sig_name}\n"
            f"Signal State: {sig_state}\n"
            f"Distance To Stop Line: {dist_stop_str}\n"
            f"Vehicle Ahead: {lead_str}\n"
            f"Distance To Vehicle Ahead: {lead_dist_str}\n"
            f"Stopping Reason: {reason}\n"
            f"--------------------------------------------------"
        )
        if self.last_debug_log != debug_msg:
            print(debug_msg, flush=True)
            self.last_debug_log = debug_msg

    def update_logic(self, dt: float):
        self.elapsed_time += dt

        # 0. Road Assignment & Boundary Safety Validation
        if (self.current_lane is None or 
            self.current_lane.lane_id is None or 
            self.current_wp_idx is None or 
            self.current_wp_idx >= len(self.current_lane.waypoints)):
            self.current_speed = 0.0
            self.state = "STOPPED"
            self._update_shared_state()
            return

        dist_to_lane = get_lateral_distance_to_lane(self.x, self.y, self.current_lane)
        if dist_to_lane > MAX_ROAD_DEVIATION or not validate_road_corridor(self.x, self.y):
            print(f"[AUTOMATIC_ROAD_RECOVERY] vehicle={self.VEHICLE_ID} pos=({self.x:.2f}, {self.y:.2f}) dist={dist_to_lane:.2f}m > max={MAX_ROAD_DEVIATION}m | Recovering to lane", flush=True)
            self.current_lane, self.current_wp_idx, (self.x, self.y) = snap_to_nearest_lane(self.x, self.y, self.lane_loop)
            self.heading = self.current_lane.target_heading
            self.current_speed = 0.0
            self.state = "STOPPED"
            self._update_shared_state()
            return

        # 1. Waypoint Progression & Transition

        target_wp = self.current_lane.waypoints[self.current_wp_idx]

        # Validate target waypoint
        if not (math.isfinite(target_wp[0]) and math.isfinite(target_wp[1])):
            print(f"ERROR: [{self.VEHICLE_ID}] Invalid target waypoint: {target_wp}", flush=True)
            self.current_wp_idx = (self.current_wp_idx + 1) % len(self.current_lane.waypoints)
            target_wp = self.current_lane.waypoints[self.current_wp_idx]

        dist_to_wp = math.hypot(target_wp[0] - self.x, target_wp[1] - self.y)

        if dist_to_wp <= WAYPOINT_TOL:
            if self.current_wp_idx < len(self.current_lane.waypoints) - 1:
                self.current_wp_idx += 1
                self.state = "CHANGING_WAYPOINT"
            else:
                old_lane = self.current_lane.lane_id
                prev_lane_idx = self.current_lane_idx
                self.current_lane_idx = (self.current_lane_idx + 1) % len(self.lane_loop)
                self.current_lane = ROAD_NETWORK[self.lane_loop[self.current_lane_idx]]
                self.current_wp_idx = 0
                self.is_turning = True
                self.state = "PASSING_JUNCTION"
                if prev_lane_idx == len(self.lane_loop) - 1:
                    print(f"[ROUTE COMPLETE]\n{self.VEHICLE_ID} completed route -> restarting route", flush=True)
                    print(f"[{self.VEHICLE_ID}] ROUTE_LOOP_RESET: Resetting route to start of {self.current_lane.lane_id}", flush=True)
                else:
                    print(f"[{self.VEHICLE_ID}] LANE_TRANSITION: {old_lane} -> {self.current_lane.lane_id}", flush=True)

            target_wp = self.current_lane.waypoints[self.current_wp_idx]

        # Calculate Dynamic Target Heading toward active look-ahead point with lane centering
        lookahead_dist = max(4.0, self.current_speed * 1.2)
        self.target_heading = calculate_lane_centering_heading(self.x, self.y, self.current_lane, lookahead_dist=lookahead_dist, k_p=0.3)

        self.heading = update_heading(self.heading, self.target_heading, MAX_TURN_RATE, dt)
        if abs(normalize_angle(self.current_lane.target_heading - self.heading)) <= 0.08:
            self.is_turning = False

        # 2. Distance to Associated Signal Stop Line
        dist_to_sl = get_distance_to_stop_line(self.x, self.y, self.current_lane)
        sig_name = "NONE"
        sig_state = "GREEN"

        if self.current_lane.controlled_signal and dist_to_sl is not None:
            j_id, app = self.current_lane.controlled_signal
            sig_name = f"{j_id}_{app}"
            sig_state = read_signal_state(j_id, app)

        # 3. Lead Vehicle Search
        other_vehicles = self._get_other_vehicles()
        lead_id, lead_dist = self._get_nearest_lead_vehicle(other_vehicles)

        # 4. STEP 15 DECISION HIERARCHY
        red_stop = False
        signal_slowing = False
        queue_stop = False
        queue_slowing = False
        safety_stop = False

        # Priority 1: SAFETY / COLLISION
        if lead_dist <= CAR_LENGTH + 0.2:
            safety_stop = True

        # Priority 2: VEHICLE AHEAD / QUEUE
        safe_following_dist = CAR_LENGTH + MIN_GAP + (0.5 * self.current_speed)
        if lead_id is not None:
            if lead_dist <= STOP_VEHICLE_DISTANCE:
                queue_stop = True
            elif lead_dist <= safe_following_dist:
                queue_slowing = True

        # Priority 3: TRAFFIC SIGNAL
        if dist_to_sl is not None and 0.0 <= dist_to_sl <= DETECTION_DIST:
            if sig_state == "RED":
                if dist_to_sl <= 2.0:
                    red_stop = True
                else:
                    signal_slowing = True
            elif sig_state == "YELLOW" and dist_to_sl > 4.0:
                signal_slowing = True

        # Determine State & Target Speed
        desired_speed = TURN_SPEED if self.is_turning else NORMAL_SPEED

        if safety_stop:
            self.state = "WAITING_IN_QUEUE"
            target_speed = 0.0
            self._print_debug("COLLISION_SAFETY", sig_name, sig_state, dist_to_sl or 999.0, lead_id, lead_dist)
        elif queue_stop:
            self.state = "WAITING_IN_QUEUE"
            target_speed = 0.0
            self._print_debug("VEHICLE_AHEAD", sig_name, sig_state, dist_to_sl or 999.0, lead_id, lead_dist)
        elif red_stop:
            self.state = "STOPPING_FOR_RED"
            target_speed = 0.0
            self._print_debug("RED_SIGNAL", sig_name, sig_state, dist_to_sl or 999.0, lead_id, lead_dist)
        elif signal_slowing or queue_slowing:
            self.state = "APPROACHING_SIGNAL"
            if signal_slowing and dist_to_sl:
                target_speed = min(desired_speed, max(0.5, dist_to_sl * 0.35))
            elif queue_slowing:
                target_speed = min(desired_speed, max(0.5, (lead_dist - STOP_VEHICLE_DISTANCE) * 0.4))
            else:
                target_speed = desired_speed
        else:
            self.state = "MOVING" if not self.is_turning else "PASSING_JUNCTION"
            target_speed = desired_speed

        # 5. Smooth Movement
        if target_speed < self.current_speed:
            self.current_speed = max(target_speed, self.current_speed - DECEL_RATE * dt)
        else:
            self.current_speed = min(target_speed, self.current_speed + ACCEL_RATE * dt)

        # 6. Apply Movement
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
    controller = Car002Controller()
    controller.run()
