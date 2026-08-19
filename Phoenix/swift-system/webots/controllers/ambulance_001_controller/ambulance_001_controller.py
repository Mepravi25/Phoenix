"""
SWIFT SYSTEM - AMBULANCE_001 Controller
Independent Emergency Vehicle Controller for AMBULANCE_001 (Module 4).
Enforces isolated controller state, pre-flight route validation,
1-meter building clearance safety margin, multi-stage road/grass/sidewalk checks,
substepped collision detection, deterministic loop routing, stuck watchdog logging,
flashing emergency light bar, siren simulation, and telemetry logging.
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


def normalize_angle(angle: float) -> float:
    """Wrap angle in radians to [-pi, pi]."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def normalize_vector(vec: Tuple[float, float]) -> Tuple[float, float]:
    """Normalize a 2D vector."""
    norm = math.hypot(vec[0], vec[1])
    if norm < 1e-6:
        return (0.0, 0.0)
    return (vec[0] / norm, vec[1] / norm)


def get_direction(p1: Tuple[float, float], p2: Tuple[float, float]) -> Tuple[float, float]:
    """Get normalized direction vector from p1 to p2."""
    return normalize_vector((p2[0] - p1[0], p2[1] - p1[1]))


def get_target_heading(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate target heading in radians from p1 to p2."""
    return math.atan2(p2[1] - p1[1], p2[0] - p1[0])


def is_waypoint_reached(pos: Tuple[float, float], wp: Dict[str, float], tol: float = 1.5) -> bool:
    """Check if current position is within tolerance of waypoint."""
    return distance(pos, (wp["x"], wp["y"])) <= tol


def is_turning(incoming_dir: Tuple[float, float], outgoing_dir: Tuple[float, float]) -> bool:
    """Check if angle between incoming and outgoing directions indicates a turn."""
    dot = incoming_dir[0] * outgoing_dir[0] + incoming_dir[1] * outgoing_dir[1]
    dot = max(-1.0, min(1.0, dot))
    angle_diff = math.acos(dot)
    return angle_diff > 0.3  # > ~17 degrees is a turn


def update_heading(current_heading: float, target_heading: float, max_turn_rate: float, dt: float) -> float:
    """Smoothly update heading towards target_heading using shortest angular distance."""
    h_err = normalize_angle(target_heading - current_heading)
    if abs(h_err) <= 0.08:
        return target_heading
    max_step = max_turn_rate * dt
    step = max(-max_step, min(max_step, h_err))
    return normalize_angle(current_heading + step)


# Central Configuration Constants for Module 4
STRAIGHT_SPEED = 5.5          # m/s
TURN_SPEED = 3.0              # m/s
WAYPOINT_TOLERANCE = 1.5      # meters
HEADING_TOLERANCE = 0.08      # radians (~4.6 degrees)
BUILDING_CLEARANCE = 1.0      # meters clearance margin from building geometry
MAX_SUBSTEP_DIST = 0.1        # meters max movement per sub-step to prevent tunneling
STUCK_TIMEOUT = 3.0           # seconds
ROAD_SURFACE_Z = 0.02
VEHICLE_BOTTOM_OFFSET = 0.40
VEHICLE_CENTER_Z = ROAD_SURFACE_Z + VEHICLE_BOTTOM_OFFSET  # 0.42m
MAX_TURN_RATE = math.radians(90.0)  # rad/s (~1.57 rad/s)
LIGHT_FLASH_INTERVAL = 0.3    # seconds between red/blue toggle
SIREN_TOGGLE_INTERVAL = 0.5   # seconds between siren high/low toggle

AMBULANCE_LENGTH = 5.2        # meters
AMBULANCE_WIDTH = 2.0         # meters
NORMAL_CAR_LENGTH = 4.5       # meters
NORMAL_CAR_WIDTH = 1.8        # meters
SAFETY_MARGIN = 1.0           # meters

MIN_FOLLOWING_DISTANCE = 5.0       # meters hard minimum bumper-to-bumper gap
FOLLOWING_WARNING_DISTANCE = 8.0   # meters warning distance to begin slowing down
SAFE_DECELERATION = 4.0            # m/s² conservative deceleration

# Minimum required longitudinal clearance
REQUIRED_CLEARANCE = (AMBULANCE_LENGTH / 2.0) + (NORMAL_CAR_LENGTH / 2.0) + MIN_FOLLOWING_DISTANCE  # 9.85 meters center-to-center
MIN_PHYSICAL_CLEARANCE = (AMBULANCE_LENGTH / 2.0) + (NORMAL_CAR_LENGTH / 2.0)                        # 4.85 meters center-to-center
LANE_CORRIDOR_WIDTH = 2.0     # meters max lateral distance for same-lane obstacle
LOOKAHEAD_RANGE = 20.0        # meters forward lookahead range for detection logging


def calculate_bumper_gap(
    ax: float, ay: float, a_heading: float,
    ox: float, oy: float, o_heading: float
) -> Tuple[float, float, float]:
    """
    Calculate bumper-to-bumper gap between ambulance front bumper and target vehicle rear bumper.
    Returns: (gap, fw_proj, lat_dist)
    """
    a_hl = AMBULANCE_LENGTH / 2.0  # 2.6m
    ax_front = ax + math.cos(a_heading) * a_hl
    ay_front = ay + math.sin(a_heading) * a_hl

    o_hl = NORMAL_CAR_LENGTH / 2.0  # 2.25m
    ox_rear = ox - math.cos(o_heading) * o_hl
    oy_rear = oy - math.sin(o_heading) * o_hl

    fw_x = math.cos(a_heading)
    fw_y = math.sin(a_heading)
    lat_x = -math.sin(a_heading)
    lat_y = math.cos(a_heading)

    dx_bumper = ox_rear - ax_front
    dy_bumper = oy_rear - ay_front

    gap_longitudinal = dx_bumper * fw_x + dy_bumper * fw_y
    gap_euclidean = math.hypot(dx_bumper, dy_bumper)

    # For following control along road corridor, gap is longitudinal bumper clearance ahead
    gap = gap_longitudinal if gap_longitudinal > 0.0 else gap_euclidean

    dx = ox - ax
    dy = oy - ay

    fw_proj = dx * fw_x + dy * fw_y
    lat_dist = abs(dx * lat_x + dy * lat_y)

    return gap, fw_proj, lat_dist


STATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Shared in-memory registry for fast in-process simulation
try:
    from car_001_controller import SHARED_MEMORY_REGISTRY
except ImportError:
    SHARED_MEMORY_REGISTRY: Dict[str, Tuple[float, ...]] = {}



def check_vehicle_bounding_box_overlap(
    ax: float, ay: float, a_heading: float,
    ox: float, oy: float, o_heading: float,
    margin: float = 0.5
) -> bool:
    """
    Check if ambulance 2D bounding box at (ax, ay, a_heading) overlaps
    with another vehicle's 2D bounding box at (ox, oy, o_heading) including safety margin.
    Uses Separating Axis Theorem (SAT) for 2D oriented rectangles.
    """
    a_hl = (AMBULANCE_LENGTH / 2.0) + (margin / 2.0)
    a_hw = (AMBULANCE_WIDTH / 2.0) + (margin / 2.0)
    o_hl = (NORMAL_CAR_LENGTH / 2.0) + (margin / 2.0)
    o_hw = (NORMAL_CAR_WIDTH / 2.0) + (margin / 2.0)

    center_dist = math.hypot(ox - ax, oy - ay)
    max_reach = math.hypot(a_hl, a_hw) + math.hypot(o_hl, o_hw)
    if center_dist > max_reach:
        return False

    cos_a, sin_a = math.cos(a_heading), math.sin(a_heading)
    a_corners = [
        (ax + a_hl * cos_a - a_hw * sin_a, ay + a_hl * sin_a + a_hw * cos_a),
        (ax + a_hl * cos_a + a_hw * sin_a, ay + a_hl * sin_a - a_hw * cos_a),
        (ax - a_hl * cos_a - a_hw * sin_a, ay - a_hl * sin_a + a_hw * cos_a),
        (ax - a_hl * cos_a + a_hw * sin_a, ay - a_hl * sin_a - a_hw * cos_a),
    ]

    cos_o, sin_o = math.cos(o_heading), math.sin(o_heading)
    o_corners = [
        (ox + o_hl * cos_o - o_hw * sin_o, oy + o_hl * sin_o + o_hw * cos_o),
        (ox + o_hl * cos_o + o_hw * sin_o, oy + o_hl * sin_o - o_hw * cos_o),
        (ox - o_hl * cos_o - o_hw * sin_o, oy - o_hl * sin_o + o_hw * cos_o),
        (ox - o_hl * cos_o + o_hw * sin_o, oy - o_hl * sin_o - o_hw * cos_o),
    ]

    axes = [
        (cos_a, sin_a),
        (-sin_a, cos_a),
        (cos_o, sin_o),
        (-sin_o, cos_o),
    ]

    for axis_x, axis_y in axes:
        a_projs = [c[0] * axis_x + c[1] * axis_y for c in a_corners]
        o_projs = [c[0] * axis_x + c[1] * axis_y for c in o_corners]

        if min(a_projs) > max(o_projs) or min(o_projs) > max(a_projs):
            return False

    return True

# 16 City Buildings Registry derived from swift_city.wbt geometry
BUILDINGS = [
    {"name": "building_central_nw", "min_x": -31.0, "max_x": -9.0, "min_y": 9.0, "max_y": 31.0},
    {"name": "building_central_ne", "min_x": 10.0, "max_x": 30.0, "min_y": 9.0, "max_y": 31.0},
    {"name": "building_central_sw", "min_x": -32.0, "max_x": -8.0, "min_y": -30.0, "max_y": -10.0},
    {"name": "building_central_se", "min_x": 9.0, "max_x": 31.0, "min_y": -31.0, "max_y": -9.0},
    {"name": "building_north_5", "min_x": -62.0, "max_x": -38.0, "min_y": 73.0, "max_y": 91.0},
    {"name": "building_north_6", "min_x": -15.0, "max_x": 15.0, "min_y": 73.0, "max_y": 91.0},
    {"name": "building_north_7", "min_x": 39.0, "max_x": 61.0, "min_y": 73.0, "max_y": 91.0},
    {"name": "building_south_8", "min_x": -61.0, "max_x": -39.0, "min_y": -91.0, "max_y": -73.0},
    {"name": "building_south_9", "min_x": -16.0, "max_x": 16.0, "min_y": -91.0, "max_y": -73.0},
    {"name": "building_south_10", "min_x": 38.0, "max_x": 62.0, "min_y": -91.0, "max_y": -73.0},
    {"name": "building_west_11", "min_x": -91.0, "max_x": -73.0, "min_y": 38.0, "max_y": 62.0},
    {"name": "building_west_12", "min_x": -91.0, "max_x": -73.0, "min_y": -15.0, "max_y": 15.0},
    {"name": "building_west_13", "min_x": -91.0, "max_x": -73.0, "min_y": -61.0, "max_y": -39.0},
    {"name": "building_east_hospital_14", "min_x": 73.0, "max_x": 91.0, "min_y": 37.0, "max_y": 63.0},
    {"name": "building_east_15", "min_x": 73.0, "max_x": 91.0, "min_y": -16.0, "max_y": 16.0},
    {"name": "building_east_16", "min_x": 73.0, "max_x": 91.0, "min_y": -61.0, "max_y": -39.0},
]

# Sidewalk Boxes Registry from swift_city.wbt
SIDEWALKS = [
    # Sidewalk Center
    {"name": "sidewalk_center_north", "min_x": -35.0, "max_x": 35.0, "min_y": 40.0, "max_y": 43.0},
    {"name": "sidewalk_center_south", "min_x": -35.0, "max_x": 35.0, "min_y": -43.0, "max_y": -40.0},
    {"name": "sidewalk_center_west",  "min_x": -43.0, "max_x": -40.0, "min_y": -35.0, "max_y": 35.0},
    {"name": "sidewalk_center_east",  "min_x": 40.0,  "max_x": 43.0,  "min_y": -35.0, "max_y": 35.0},
    # Sidewalk Outer
    {"name": "sidewalk_outer_north", "min_x": -35.0, "max_x": 35.0, "min_y": 57.0, "max_y": 60.0},
    {"name": "sidewalk_outer_south", "min_x": -35.0, "max_x": 35.0, "min_y": -60.0, "max_y": -57.0},
    {"name": "sidewalk_outer_west",  "min_x": -60.0, "max_x": -57.0, "min_y": -35.0, "max_y": 35.0},
    {"name": "sidewalk_outer_east",  "min_x": 57.0,  "max_x": 60.0,  "min_y": -35.0, "max_y": 35.0},
    # Sidewalk Corners
    {"name": "sidewalk_corner_nw", "min_x": -84.0, "max_x": -59.0, "min_y": 59.0,  "max_y": 84.0},
    {"name": "sidewalk_corner_ne", "min_x": 59.0,  "max_x": 84.0,  "min_y": 59.0,  "max_y": 84.0},
    {"name": "sidewalk_corner_sw", "min_x": -84.0, "max_x": -59.0, "min_y": -84.0, "max_y": -59.0},
    {"name": "sidewalk_corner_se", "min_x": 59.0,  "max_x": 84.0,  "min_y": -84.0, "max_y": -59.0},
]


from road_network import validate_road_corridor


def check_building_collision(x: float, y: float, heading: float, clearance: float = BUILDING_CLEARANCE) -> Optional[str]:
    """
    Check if the ambulance bounding box at (x, y, heading) comes within clearance margin of any building.
    Returns the building name if a collision/clearance violation occurs, else None.
    """
    cos_h = math.cos(heading)
    sin_h = math.sin(heading)

    half_l = AMBULANCE_LENGTH / 2.0
    half_w = AMBULANCE_WIDTH / 2.0

    local_corners = [
        (half_l, half_w),
        (half_l, -half_w),
        (-half_l, half_w),
        (-half_l, -half_w),
        (0.0, 0.0)
    ]

    corners_world = [
        (x + lx * cos_h - ly * sin_h, y + lx * sin_h + ly * cos_h)
        for lx, ly in local_corners
    ]

    for b in BUILDINGS:
        min_x = b["min_x"] - clearance
        max_x = b["max_x"] + clearance
        min_y = b["min_y"] - clearance
        max_y = b["max_y"] + clearance

        for cx, cy in corners_world:
            if min_x <= cx <= max_x and min_y <= cy <= max_y:
                return b["name"]

        b_cx = (b["min_x"] + b["max_x"]) / 2.0
        b_cy = (b["min_y"] + b["max_y"]) / 2.0
        if abs(b_cx - x) <= (half_l + clearance) and abs(b_cy - y) <= (half_w + clearance):
            return b["name"]

    return None


def check_grass_violation(x: float, y: float) -> bool:
    """Check if position is inside the central green grass area."""
    return (-40.0 < x < 40.0) and (-40.0 < y < 40.0)


def check_sidewalk_violation(x: float, y: float) -> bool:
    """Check if position intersects any sidewalk box."""
    for s in SIDEWALKS:
        if s["min_x"] <= x <= s["max_x"] and s["min_y"] <= y <= s["max_y"]:
            return True
    return False


# Expanded Road-Centerline Loop Waypoints (Explicit Intersection Entry, Turn, and Exit)
LOOP_WAYPOINTS = [
    {"x": -46.5, "y": 43.0},   # WP0: J1 Entry (South approach)
    {"x": -46.5, "y": 46.5},   # WP1: J1 Center / Turn Point
    {"x": -43.0, "y": 46.5},   # WP2: J1 Exit (Eastbound on North Road)
    {"x": 43.0,  "y": 46.5},   # WP3: J2 Entry (West approach)
    {"x": 46.5,  "y": 46.5},   # WP4: J2 Center / Turn Point
    {"x": 46.5,  "y": 43.0},   # WP5: J2 Exit (Southbound on East Road)
    {"x": 46.5,  "y": -43.0},  # WP6: J4 Entry (North approach)
    {"x": 46.5,  "y": -46.5},  # WP7: J4 Center / Turn Point
    {"x": 43.0,  "y": -46.5},  # WP8: J4 Exit (Westbound on South Road)
    {"x": -43.0, "y": -46.5},  # WP9: J3 Entry (East approach)
    {"x": -46.5, "y": -46.5},  # WP10: J3 Center / Turn Point
    {"x": -46.5, "y": -43.0},  # WP11: J3 Exit (Northbound on West Road)
]


def validate_route(waypoints: List[Dict[str, float]]) -> bool:
    """Validate every route waypoint before simulation starts."""
    for idx, wp in enumerate(waypoints):
        x, y = wp["x"], wp["y"]
        if not (math.isfinite(x) and math.isfinite(y)):
            print(f"[AMBULANCE_ROUTE_ERROR] waypoint={idx} position=({x},{y}) reason=NON_FINITE_COORDINATES", flush=True)
            return False
        z = wp.get("z", VEHICLE_CENTER_Z)
        if not math.isfinite(z) or abs(z - VEHICLE_CENTER_Z) > 0.1:
            print(f"[AMBULANCE_ROUTE_ERROR] waypoint={idx} position=({x},{y}) reason=INVALID_ROAD_LEVEL_Z", flush=True)
            return False
        if not validate_road_corridor(x, y):
            print(f"[AMBULANCE_ROUTE_ERROR] waypoint={idx} position=({x},{y}) reason=OUTSIDE_ROAD_CORRIDOR", flush=True)
            return False
        b_block = check_building_collision(x, y, 0.0, clearance=BUILDING_CLEARANCE)
        if b_block:
            print(f"[AMBULANCE_ROUTE_ERROR] waypoint={idx} position=({x},{y}) reason=INSIDE_BUILDING_CLEARANCE_{b_block}", flush=True)
            return False
        if check_grass_violation(x, y):
            print(f"[AMBULANCE_ROUTE_ERROR] waypoint={idx} position=({x},{y}) reason=INSIDE_GRASS", flush=True)
            return False
        if check_sidewalk_violation(x, y):
            print(f"[AMBULANCE_ROUTE_ERROR] waypoint={idx} position=({x},{y}) reason=INSIDE_SIDEWALK", flush=True)
            return False
    return True


class Ambulance001Controller:
    """Independent controller for AMBULANCE_001 with robust front-vehicle clearance & collision avoidance."""
    VEHICLE_ID = "AMBULANCE_001"
    SPAWN_X = -46.5
    SPAWN_Y = 20.0
    SPAWN_HEADING = math.pi / 2.0  # 1.5708 rad (facing North towards J1)
    INITIAL_WP_IDX = 0  # Heading towards WP0 (-46.5, 43.0)

    def __init__(self):
        if WEBOTS_AVAILABLE:
            self.supervisor = Supervisor()
            self.time_step = int(self.supervisor.getBasicTimeStep())
            self.self_node = self.supervisor.getSelf()
            self.translation_field = self.self_node.getField("translation") if self.self_node else None
            self.rotation_field = self.self_node.getField("rotation") if self.self_node else None
            self.red_led = self.supervisor.getDevice("AMBULANCE_RED_LIGHT")
            self.blue_led = self.supervisor.getDevice("AMBULANCE_BLUE_LIGHT")
        else:
            self.supervisor = None
            self.time_step = 32
            self.self_node = None
            self.translation_field = None
            self.rotation_field = None
            self.red_led = None
            self.blue_led = None

        self.x = self.SPAWN_X
        self.y = self.SPAWN_Y
        self.z = VEHICLE_CENTER_Z
        self.heading = self.SPAWN_HEADING
        self.speed = STRAIGHT_SPEED
        self.current_speed = 0.0
        self.current_wp_idx = self.INITIAL_WP_IDX
        self.waypoints = LOOP_WAYPOINTS
        self.elapsed_time = 0.0

        self.EMERGENCY_ACTIVE = False  # Module 2 Baseline: Ambulance obeys standard signals without priority override

        self.last_position = (self.x, self.y)
        self.last_progress_time = 0.0
        self.stuck_logged = False
        self.block_reason = "NONE"
        self.blocked_by: Optional[str] = None
        self.target_front_vehicle: Optional[str] = None
        self.following_log_state: str = "CLEAR"
        self.is_blocked_ahead: bool = False
        self.state = "DRIVING_STRAIGHT"
        self.turn_state = "DRIVING_STRAIGHT"
        self.target_heading = self.SPAWN_HEADING

        # Emergency Light & Siren state
        self.light_toggle_timer = 0.0
        self.light_state = 0  # 0: RED ON / BLUE OFF, 1: RED OFF / BLUE ON
        self.siren_toggle_timer = 0.0
        self.siren_state = "SIREN_HIGH"  # "SIREN_HIGH" or "SIREN_LOW"

        # Module 5A J1 Emergency Priority Request state
        self.emergency_requested_j1 = False

        # Pre-flight Route Validation
        if not validate_route(self.waypoints):
            self.state = "ROUTE_ERROR"
            self.block_reason = "ROUTE_ERROR"

        # Initial spawn road boundary validation
        if not validate_road_corridor(self.x, self.y):
            print(f"[AMBULANCE_ROAD_BLOCK] vehicle={self.VEHICLE_ID} position=({self.x:.1f},{self.y:.1f})", flush=True)
            self.state = "ROAD_ERROR"
            self.block_reason = "ROAD_BOUNDARY"

        # Initial Webots transform sync
        if self.translation_field:
            self.translation_field.setSFVec3f([self.x, self.y, self.z])
        if self.rotation_field:
            self.rotation_field.setSFRotation([0.0, 0.0, 1.0, self.heading])

        # Initial LED state
        self._update_leds()

        # Startup logging
        print(f"[{self.VEHICLE_ID}] CONTROLLER_STARTED", flush=True)
        print(f"[{self.VEHICLE_ID}] SPAWN=({self.SPAWN_X:.1f}, {self.SPAWN_Y:.1f})", flush=True)
        print(f"[{self.VEHICLE_ID}] WAYPOINT={self.current_wp_idx}", flush=True)

        self._update_shared_state()

    def _check_j1_emergency_request(self):
        """Module 5A: Minimal Emergency Priority Request Communication Interface."""
        if not self.EMERGENCY_ACTIVE:
            return  # Module 2 Baseline: No emergency priority requests
        j1_center = (-46.5, 46.5)
        dist_to_j1 = distance((self.x, self.y), j1_center)

        # Approach detection (within 20m of J1 on approach waypoints 0 or 1)
        approaching_j1 = (self.current_wp_idx in [0, 1]) and (dist_to_j1 <= 20.0)

        if approaching_j1 and not self.emergency_requested_j1:
            self.emergency_requested_j1 = True
            print("[SWIFT_EMERGENCY_REQUEST]", flush=True)
            print(f"vehicle={self.VEHICLE_ID}", flush=True)
            print("junction=J1", flush=True)
            print("approach=SOUTH", flush=True)

            req_data = {
                "vehicle_id": self.VEHICLE_ID,
                "junction_id": "J1",
                "approach_direction": "SOUTH",
                "request_type": "EMERGENCY_PRIORITY",
                "timestamp": self.elapsed_time,
                "active": True
            }

            # Shared memory export
            try:
                from junction_controller import SHARED_EMERGENCY_REQUESTS
                SHARED_EMERGENCY_REQUESTS["J1"] = req_data
            except ImportError:
                pass

            # State file export
            try:
                req_file = os.path.join(STATE_DIR, "emergency_requests.json")
                tmp_file = f"{req_file}.tmp"
                with open(tmp_file, "w") as f:
                    json.dump(req_data, f)
                os.replace(tmp_file, req_file)
            except Exception:
                pass

        elif self.emergency_requested_j1 and self.current_wp_idx not in [0, 1, 2] and dist_to_j1 > 25.0:
            self.emergency_requested_j1 = False
            print("[SWIFT_EMERGENCY_CANCELLED]", flush=True)
            try:
                from junction_controller import SHARED_EMERGENCY_REQUESTS
                if "J1" in SHARED_EMERGENCY_REQUESTS:
                    SHARED_EMERGENCY_REQUESTS["J1"]["active"] = False
            except ImportError:
                pass

    def _update_leds(self):
        """Update hardware LED nodes if present."""
        if self.red_led:
            self.red_led.set(1 if self.light_state == 0 else 0)
        if self.blue_led:
            self.blue_led.set(1 if self.light_state == 1 else 0)

    def _update_shared_state(self):
        """Update ambulance position in memory and disk state file."""
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
                "wp_idx": self.current_wp_idx,
                "state": self.state,
                "turn_state": self.turn_state,
                "block_reason": self.block_reason,
                "emergency_active": self.EMERGENCY_ACTIVE,
                "light_state": "RED" if self.light_state == 0 else "BLUE",
                "siren_state": self.siren_state,
                "timestamp": self.elapsed_time,
            }
            with open(tmp_file, "w") as f:
                json.dump(data, f)
            os.replace(tmp_file, state_file)
        except Exception:
            pass

    def _get_other_vehicles(self) -> Dict[str, Dict[str, float]]:
        """Get current positions and headings of all normal traffic vehicles."""
        other_vehicles = {}
        other_ids = ["CAR_001", "CAR_002", "CAR_003", "CAR_004"]

        if self.supervisor:
            for v_id in other_ids:
                node = self.supervisor.getFromDef(v_id)
                if node:
                    t_field = node.getField("translation")
                    r_field = node.getField("rotation")
                    if t_field:
                        vec = t_field.getSFVec3f()
                        heading = 0.0
                        if r_field:
                            rot = r_field.getSFRotation()
                            if len(rot) >= 4:
                                heading = rot[3]
                        other_vehicles[v_id] = {"x": vec[0], "y": vec[1], "heading": heading}

        if not other_vehicles:
            for v_id in other_ids:
                if v_id in SHARED_MEMORY_REGISTRY:
                    pos = SHARED_MEMORY_REGISTRY[v_id]
                    x_pos, y_pos = pos[0], pos[1]
                    heading = pos[2] if len(pos) >= 3 else None

                    if heading is None:
                        s_file = os.path.join(STATE_DIR, f"vehicle_pos_{v_id}.json")
                        if os.path.exists(s_file):
                            try:
                                with open(s_file, "r") as f:
                                    data = json.load(f)
                                heading = data.get("heading", self.heading)
                            except Exception:
                                pass
                    if heading is None:
                        heading = self.heading

                    other_vehicles[v_id] = {"x": x_pos, "y": y_pos, "heading": heading}
                else:
                    s_file = os.path.join(STATE_DIR, f"vehicle_pos_{v_id}.json")
                    if os.path.exists(s_file):
                        try:
                            with open(s_file, "r") as f:
                                data = json.load(f)
                            if abs(self.elapsed_time - data.get("timestamp", 0.0)) <= 2.0:
                                other_vehicles[v_id] = {"x": data["x"], "y": data["y"], "heading": data.get("heading", self.heading)}
                        except Exception:
                            pass

        return other_vehicles

    def _get_nearest_front_vehicle(
        self,
        other_vehicles: Dict[str, Dict[str, float]]
    ) -> Tuple[Optional[str], float, float, float]:
        """
        Find nearest front vehicle in same lane corridor.
        Returns: (vehicle_id, gap, fw_proj, lat_dist) or (None, 999.0, 0.0, 0.0)
        """
        nearest_id = None
        min_gap = 999.0
        best_fw_proj = 0.0
        best_lat_dist = 0.0

        for other_id, o_data in other_vehicles.items():
            ox, oy = o_data["x"], o_data["y"]
            o_heading = o_data.get("heading", self.heading)

            gap, fw_proj, lat_dist = calculate_bumper_gap(
                self.x, self.y, self.heading,
                ox, oy, o_heading
            )

            if fw_proj > 0.0 and lat_dist <= LANE_CORRIDOR_WIDTH and fw_proj < LOOKAHEAD_RANGE:
                heading_diff = abs(normalize_angle(o_heading - self.heading))
                if heading_diff <= math.radians(90.0) or heading_diff >= math.radians(270.0) or lat_dist <= 1.5:
                    if gap < min_gap:
                        min_gap = gap
                        nearest_id = other_id
                        best_fw_proj = fw_proj
                        best_lat_dist = lat_dist

        return nearest_id, min_gap, best_fw_proj, best_lat_dist

    def _check_vehicle_clearance(
        self,
        ax: float,
        ay: float,
        a_heading: float,
        other_vehicles: Dict[str, Dict[str, float]]
    ) -> Tuple[bool, Optional[str], float, bool]:
        """
        Predictive clearance & collision check BEFORE updating position.
        Returns:
            (is_blocked, blocking_vehicle_id, gap, is_front_vehicle)
        """
        # 1. Check same-lane front vehicle clearance violation (MIN_FOLLOWING_DISTANCE = 5.0m bumper-to-bumper)
        for other_id, o_data in other_vehicles.items():
            ox, oy = o_data["x"], o_data["y"]
            o_heading = o_data.get("heading", a_heading)

            gap, fw_proj, lat_dist = calculate_bumper_gap(ax, ay, a_heading, ox, oy, o_heading)

            # Same lane corridor & ahead
            if fw_proj > 0.0 and lat_dist <= LANE_CORRIDOR_WIDTH:
                heading_diff = abs(normalize_angle(o_heading - a_heading))
                if heading_diff <= math.radians(90.0) or heading_diff >= math.radians(270.0) or lat_dist <= 1.5:
                    if gap < MIN_FOLLOWING_DISTANCE:
                        return True, other_id, gap, True

        # 2. Check 2D bounding box physical overlap for ANY vehicle (including crossing/turning)
        for other_id, o_data in other_vehicles.items():
            ox, oy = o_data["x"], o_data["y"]
            o_heading = o_data.get("heading", 0.0)
            gap, fw_proj, lat_dist = calculate_bumper_gap(ax, ay, a_heading, ox, oy, o_heading)
            center_dist = math.hypot(ox - ax, oy - ay)

            if check_vehicle_bounding_box_overlap(ax, ay, a_heading, ox, oy, o_heading, margin=0.2):
                is_front = (fw_proj > 0.0 and lat_dist <= LANE_CORRIDOR_WIDTH)
                return True, other_id, gap, is_front

        return False, None, 999.0, False

    def update_logic(self, dt: float):
        self.elapsed_time += dt

        # Module 5A Emergency Priority Request Check
        self._check_j1_emergency_request()

        # 1. Update Flashing Emergency Light Bar
        self.light_toggle_timer += dt
        if self.light_toggle_timer >= LIGHT_FLASH_INTERVAL:
            self.light_toggle_timer -= LIGHT_FLASH_INTERVAL
            self.light_state = 1 - self.light_state
            self._update_leds()

        # 2. Update Siren Signal State
        self.siren_toggle_timer += dt
        if self.siren_toggle_timer >= SIREN_TOGGLE_INTERVAL:
            self.siren_toggle_timer -= SIREN_TOGGLE_INTERVAL
            self.siren_state = "SIREN_LOW" if self.siren_state == "SIREN_HIGH" else "SIREN_HIGH"

        if self.state in ["ROAD_ERROR", "ROUTE_ERROR"]:
            self.current_speed = 0.0
            self._update_shared_state()
            return

        pos = (self.x, self.y)
        cur_wp = self.waypoints[self.current_wp_idx]

        # Get positions of all vehicles and find nearest front vehicle in same lane
        other_vehicles = self._get_other_vehicles()
        front_id, front_gap, _, _ = self._get_nearest_front_vehicle(other_vehicles)

        # 3. Waypoint Arrival & Monotonic Advancement
        if is_waypoint_reached(pos, cur_wp, WAYPOINT_TOLERANCE):
            old_wp_idx = self.current_wp_idx
            self.current_wp_idx = (self.current_wp_idx + 1) % len(self.waypoints)
            print(f"[{self.VEHICLE_ID}] WAYPOINT={self.current_wp_idx}", flush=True)

            if old_wp_idx == len(self.waypoints) - 1 and self.current_wp_idx == 0:
                print(f"[{self.VEHICLE_ID}] ROUTE_LOOP", flush=True)

            # Target heading calculation to next waypoint
            prev_wp = self.waypoints[old_wp_idx]
            cur_wp = self.waypoints[self.current_wp_idx]
            prev_prev_wp = self.waypoints[(old_wp_idx - 1) % len(self.waypoints)]

            incoming_dir = get_direction((prev_prev_wp["x"], prev_prev_wp["y"]), (prev_wp["x"], prev_wp["y"]))
            outgoing_dir = get_direction((prev_wp["x"], prev_wp["y"]), (cur_wp["x"], cur_wp["y"]))

            self.target_heading = get_target_heading((prev_wp["x"], prev_wp["y"]), (cur_wp["x"], cur_wp["y"]))

            if is_turning(incoming_dir, outgoing_dir):
                self.turn_state = "TURNING"
                print(f"[{self.VEHICLE_ID}] TURN_START", flush=True)

        # 4. Speed selection based on turn state and progressive front-vehicle distance control
        if self.turn_state == "TURNING":
            base_speed = TURN_SPEED
        else:
            prev_wp_idx = (self.current_wp_idx - 1) % len(self.waypoints)
            prev_wp = self.waypoints[prev_wp_idx]
            cur_wp = self.waypoints[self.current_wp_idx]
            self.target_heading = get_target_heading((prev_wp["x"], prev_wp["y"]), (cur_wp["x"], cur_wp["y"]))
            base_speed = STRAIGHT_SPEED

        # Progressive Speed Control & Stopping Distance Estimation
        if front_id is not None:
            stopping_dist = (self.current_speed ** 2) / (2.0 * SAFE_DECELERATION)
            effective_warning_dist = max(FOLLOWING_WARNING_DISTANCE, MIN_FOLLOWING_DISTANCE + stopping_dist)

            if front_gap <= MIN_FOLLOWING_DISTANCE:
                target_speed = 0.0
                self.block_reason = "VEHICLE_AHEAD"
                self.is_blocked_ahead = True
                self.blocked_by = front_id
                if self.following_log_state != "SAFE_STOP":
                    self.following_log_state = "SAFE_STOP"
                    self.target_front_vehicle = front_id
                    print(f"[AMBULANCE_SAFE_STOP] target={front_id} gap={front_gap:.2f}", flush=True)
            elif front_gap <= effective_warning_dist:
                speed_ratio = (front_gap - MIN_FOLLOWING_DISTANCE) / (effective_warning_dist - MIN_FOLLOWING_DISTANCE)
                target_speed = base_speed * max(0.0, min(1.0, speed_ratio))
                if self.following_log_state == "SAFE_STOP":
                    print(f"[AMBULANCE_RESUME] target={front_id} gap={front_gap:.2f}", flush=True)
                    self.following_log_state = "SLOWING"
                elif self.following_log_state != "SLOWING":
                    self.following_log_state = "SLOWING"
                    self.target_front_vehicle = front_id
                    print(f"[AMBULANCE_SLOWING] target={front_id} gap={front_gap:.2f}", flush=True)
            else:
                target_speed = base_speed
                if self.following_log_state == "SAFE_STOP":
                    print(f"[AMBULANCE_RESUME] target={front_id} gap={front_gap:.2f}", flush=True)
                    self.following_log_state = "FOLLOWING"
                elif self.following_log_state != "FOLLOWING" or self.target_front_vehicle != front_id:
                    self.following_log_state = "FOLLOWING"
                    self.target_front_vehicle = front_id
                    print(f"[AMBULANCE_FOLLOW] target={front_id} gap={front_gap:.2f} speed={target_speed:.2f}", flush=True)
        else:
            if self.following_log_state == "SAFE_STOP" and self.target_front_vehicle:
                print(f"[AMBULANCE_RESUME] target={self.target_front_vehicle} gap=999.00", flush=True)
            self.following_log_state = "CLEAR"
            self.target_front_vehicle = None
            target_speed = base_speed

        # 5. Heading Update & Turn Completion
        self.heading = update_heading(self.heading, self.target_heading, MAX_TURN_RATE, dt)

        angle_error = normalize_angle(self.target_heading - self.heading)
        if self.turn_state == "TURNING" and abs(angle_error) <= HEADING_TOLERANCE:
            self.turn_state = "DRIVING_STRAIGHT"
            print(f"[{self.VEHICLE_ID}] TURN_COMPLETE", flush=True)

        self.speed = target_speed

        # =========================================================
        # 6-11. SUBSTEPPED MOVEMENT & MULTI-STAGE SAFETY VALIDATION
        # =========================================================
        total_dist = self.speed * dt
        num_substeps = max(1, math.ceil(total_dist / MAX_SUBSTEP_DIST))
        substep_dt = dt / num_substeps

        curr_x = self.x
        curr_y = self.y
        new_block_reason = "NONE"
        blocked_vehicle_id = None
        blocked_dist = 0.0
        blocked_is_front = False

        for _ in range(num_substeps):
            dx_step = self.speed * math.cos(self.heading) * substep_dt
            dy_step = self.speed * math.sin(self.heading) * substep_dt
            prop_x = curr_x + dx_step
            prop_y = curr_y + dy_step

            # Step 3: Validate road corridor
            if not validate_road_corridor(prop_x, prop_y):
                new_block_reason = "ROAD_BOUNDARY"
                print(f"[AMBULANCE_ROAD_BLOCK] position=({prop_x:.2f}, {prop_y:.2f})", flush=True)
                break

            # Step 4: Validate building clearance
            b_block = check_building_collision(prop_x, prop_y, self.heading, clearance=BUILDING_CLEARANCE)
            if b_block:
                new_block_reason = "BUILDING"
                print(f"[AMBULANCE_BUILDING_BLOCK] position=({prop_x:.2f}, {prop_y:.2f}) building={b_block}", flush=True)
                break

            # Step 5: Validate grass
            if check_grass_violation(prop_x, prop_y):
                new_block_reason = "GRASS"
                print(f"[AMBULANCE_GRASS_BLOCK] position=({prop_x:.2f}, {prop_y:.2f})", flush=True)
                break

            # Step 6: Validate sidewalk
            if check_sidewalk_violation(prop_x, prop_y):
                new_block_reason = "SIDEWALK"
                print(f"[AMBULANCE_SIDEWALK_BLOCK] position=({prop_x:.2f}, {prop_y:.2f})", flush=True)
                break

            # Step 7: Predictive vehicle clearance check BEFORE applying position
            veh_blocked, block_id, dist_v, is_front = self._check_vehicle_clearance(prop_x, prop_y, self.heading, other_vehicles)

            if veh_blocked:
                new_block_reason = "VEHICLE_AHEAD" if is_front else "VEHICLE"
                blocked_vehicle_id = block_id
                blocked_dist = dist_v
                blocked_is_front = is_front
                break

            curr_x = prop_x
            curr_y = prop_y

        # Handle Block / Resume transitions
        is_front_stopped = (front_id is not None and front_gap <= MIN_FOLLOWING_DISTANCE + 0.05)

        if new_block_reason in ["VEHICLE", "VEHICLE_AHEAD"] or is_front_stopped:
            self.current_speed = 0.0
            self.block_reason = "VEHICLE_AHEAD" if (blocked_is_front or is_front_stopped) else "VEHICLE"
            if not self.is_blocked_ahead:
                self.is_blocked_ahead = True
                self.blocked_by = blocked_vehicle_id or front_id
                target_name = self.blocked_by or "CAR_001"
                if self.following_log_state != "SAFE_STOP":
                    self.following_log_state = "SAFE_STOP"
                    gap_val = blocked_dist if veh_blocked else front_gap
                    print(f"[AMBULANCE_SAFE_STOP] target={target_name} gap={gap_val:.2f}", flush=True)
        elif new_block_reason != "NONE":
            self.current_speed = 0.0
            self.block_reason = new_block_reason
        else:
            if self.is_blocked_ahead:
                self.is_blocked_ahead = False
                resumed_target = self.blocked_by or self.target_front_vehicle or "CAR_001"
                if self.following_log_state == "SAFE_STOP":
                    print(f"[AMBULANCE_RESUME] target={resumed_target} gap={front_gap:.2f}", flush=True)
                    self.following_log_state = "FOLLOWING"
                self.blocked_by = None
            self.block_reason = "NONE"
            self.current_speed = self.speed
            self.x = curr_x
            self.y = curr_y

        # Watchdog Timer for stuck detection
        disp = distance((self.x, self.y), self.last_position)
        if disp > 0.05:
            self.last_position = (self.x, self.y)
            self.last_progress_time = self.elapsed_time
            self.stuck_logged = False
        elif (self.elapsed_time - self.last_progress_time >= STUCK_TIMEOUT) and (self.block_reason not in ["VEHICLE", "VEHICLE_AHEAD"]):
            if not self.stuck_logged:
                self.stuck_logged = True
                print(f"[{self.VEHICLE_ID}] STUCK", flush=True)
                print(f"[AMBULANCE_STUCK] waypoint={self.current_wp_idx} position=({self.x:.2f}, {self.y:.2f}) heading={self.heading:.3f} target_heading={self.target_heading:.3f} last_block_reason={self.block_reason}", flush=True)

        # Webots Transform Sync
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
    controller = Ambulance001Controller()
    controller.run()
