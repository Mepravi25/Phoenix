"""
SWIFT SYSTEM - Vehicle Registry & Detection Engine
Module 3 Final: Normal Vehicle Collision Avoidance & Safe Following

Manages central vehicle state registry, same-lane vehicle ahead detection using
vector geometry projection, bumper-to-bumper distance calculation, and spawn safety checks.
"""

import os
import math
import time
import json
from typing import Dict, Tuple, Optional, Any


def wrap_angle(angle: float) -> float:
    """Wrap angle in radians to [-pi, pi]."""
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


# Central Configuration Constants
POSITIONS_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "vehicle_positions.json"
)
SIGNAL_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "traffic_signal_states.json"
)

VEHICLE_LENGTH = 4.5       # meters (bounding length)
VEHICLE_WIDTH = 1.8        # meters (bounding width)
VEHICLE_DETECTION_RANGE = 35.0  # meters (forward lookahead range)
LANE_TOLERANCE = 2.0       # meters lateral offset tolerance
MIN_FOLLOWING_DISTANCE = 4.0    # meters (bumper-to-bumper minimum stop gap)
MIN_VEHICLE_CLEARANCE = 3.0     # meters (center-to-center clearance gap)
MIN_SPAWN_DISTANCE = 10.0       # meters (center-to-center spawn clearance)
RESUME_HYSTERESIS = 1.0         # meters hysteresis for resuming following


class VehicleRegistry:
    """
    Process-safe vehicle state registry and detection engine.
    Supports atomic read/write of vehicle telemetry and vector projection obstacle detection.
    """
    _shared_cache: Dict[str, Dict[str, Any]] = {}

    def __init__(self, filepath: str = POSITIONS_STATE_FILE):
        self.filepath = filepath
        self._memory_cache = VehicleRegistry._shared_cache

    def clear(self):
        """Clears memory cache and deletes state files."""
        VehicleRegistry._shared_cache.clear()
        folder = os.path.dirname(self.filepath)
        if os.path.exists(folder):
            for fname in os.listdir(folder):
                if "vehicle_positions" in fname or "traffic_signal" in fname:
                    fpath = os.path.join(folder, fname)
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass

    def get_all_vehicles(self) -> Dict[str, Dict[str, Any]]:
        """Reads all vehicle states from shared storage atomically with retries."""
        if os.path.exists(self.filepath):
            for _ in range(3):
                try:
                    with open(self.filepath, "r") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        VehicleRegistry._shared_cache = data
                    break
                except Exception:
                    time.sleep(0.001)
        else:
            VehicleRegistry._shared_cache = {}

        return VehicleRegistry._shared_cache

    def register_vehicle(self, vehicle_id: str, data: Dict[str, Any]):
        """Registers or updates a single vehicle's state in the registry."""
        VehicleRegistry._shared_cache[vehicle_id] = data
        try:
            tmp_file = f"{self.filepath}.{vehicle_id}.tmp"
            with open(tmp_file, "w") as f:
                json.dump(VehicleRegistry._shared_cache, f)
            os.replace(tmp_file, self.filepath)
        except Exception:
            pass

    def get_vehicle(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        """Gets a single vehicle record by ID."""
        vehicles = self.get_all_vehicles()
        return vehicles.get(vehicle_id)

    def detect_vehicle_ahead(
        self,
        subject_id: str,
        x: float,
        y: float,
        heading: float,
        max_range: float = VEHICLE_DETECTION_RANGE,
        lane_tolerance: float = LANE_TOLERANCE,
    ) -> Tuple[Optional[str], float, float, float]:
        """
        Detects the nearest same-lane vehicle directly ahead using vector projection.

        Returns:
            (front_vehicle_id, bumper_distance, forward_center_distance, front_vehicle_speed)
            If no vehicle detected, returns (None, 999.0, 999.0, 0.0)
        """
        vehicles = self.get_all_vehicles()

        cos_h = math.cos(heading)
        sin_h = math.sin(heading)

        min_bumper_dist = 999.0
        best_fw_dist = 999.0
        best_vehicle_id = None
        best_speed = 0.0

        for other_id, other_pos in vehicles.items():
            if other_id == subject_id:
                continue

            if not other_pos.get("is_spawned", True):
                continue

            ox = other_pos.get("x", 0.0)
            oy = other_pos.get("y", 0.0)
            o_heading = other_pos.get("heading", 0.0)
            o_speed = other_pos.get("speed", 0.0)

            dx = ox - x
            dy = oy - y

            fw_dist = dx * cos_h + dy * sin_h
            lat_dist = abs(-dx * sin_h + dy * cos_h)
            heading_diff = abs(wrap_angle(o_heading - heading))

            # Must be ahead along forward vector
            if fw_dist <= 0.1:
                continue

            # Must be within lateral lane corridor
            if lat_dist > lane_tolerance:
                continue

            # Heading alignment (must be traveling in approximately same direction <= 45 degrees)
            if heading_diff > math.radians(45.0):
                continue

            bumper_dist = fw_dist - VEHICLE_LENGTH

            if bumper_dist < max_range:
                if bumper_dist < min_bumper_dist:
                    min_bumper_dist = bumper_dist
                    best_fw_dist = fw_dist
                    best_vehicle_id = other_id
                    best_speed = o_speed

        if best_vehicle_id is not None:
            return best_vehicle_id, min_bumper_dist, best_fw_dist, best_speed
        else:
            return None, 999.0, 999.0, 0.0

    def predict_conflict(
        self,
        subject_id: str,
        pred_x: float,
        pred_y: float,
        pred_heading: float,
        safety_buffer: float = 1.5,
    ) -> Tuple[bool, Optional[str], float, float]:
        """
        Predictive 2D bounding envelope safety check BEFORE applying movement.
        Returns:
            (has_conflict, conflicting_vehicle_id, predicted_center_distance, minimum_allowed_distance)
        """
        vehicles = self.get_all_vehicles()
        cos_h = math.cos(pred_heading)
        sin_h = math.sin(pred_heading)

        for other_id, other_pos in vehicles.items():
            if other_id == subject_id:
                continue
            if not other_pos.get("is_spawned", True):
                continue

            ox = other_pos.get("x", 0.0)
            oy = other_pos.get("y", 0.0)
            o_heading = other_pos.get("heading", 0.0)

            dx = ox - pred_x
            dy = oy - pred_y

            center_dist = math.hypot(dx, dy)
            fw_dist = dx * cos_h + dy * sin_h
            lat_dist = abs(-dx * sin_h + dy * cos_h)
            heading_diff = abs(wrap_angle(o_heading - pred_heading))

            # Critical physical bounding overlap check (center-to-center < 3.0m)
            if center_dist < 3.0:
                return True, other_id, center_dist, 3.0

            # Immediate forward obstacle overlap (bumper_dist < 1.5m in same lane)
            if fw_dist > 0.1 and lat_dist < LANE_TOLERANCE and heading_diff <= math.radians(45.0):
                bumper_dist = fw_dist - VEHICLE_LENGTH
                if bumper_dist < 1.5:
                    return True, other_id, center_dist, 1.5

        return False, None, 999.0, 3.0

    def check_deadlocks(self) -> List[Tuple[str, str, str]]:
        """Detects pairwise circular wait dependencies between vehicles."""
        vehicles = self.get_all_vehicles()
        wait_graph = {}
        for vid, vdata in vehicles.items():
            st = vdata.get("state", "")
            if st in ["FOLLOWING_VEHICLE", "STOPPED_BEHIND_VEHICLE", "WAITING_FOR_CLEARANCE"]:
                target_v = vdata.get("target_vehicle")
                if target_v:
                    wait_graph[vid] = target_v

        deadlocks = []
        for vid, target_v in wait_graph.items():
            if target_v in wait_graph and wait_graph[target_v] == vid:
                pair = sorted([vid, target_v])
                deadlock_tuple = (pair[0], pair[1], "INTERSECTION")
                if deadlock_tuple not in deadlocks:
                    deadlocks.append(deadlock_tuple)

        return deadlocks

    def check_spawn_collision(self, x: float, y: float, min_spawn_dist: float = MIN_SPAWN_DISTANCE) -> bool:
        """Checks if a spawn location at (x, y) is blocked by any active vehicle."""
        vehicles = self.get_all_vehicles()
        for other_id, other_pos in vehicles.items():
            if not other_pos.get("is_spawned", True):
                continue
            ox = other_pos.get("x", 0.0)
            oy = other_pos.get("y", 0.0)
            dist = math.hypot(ox - x, oy - y)
            if dist < min_spawn_dist:
                return True
        return False


