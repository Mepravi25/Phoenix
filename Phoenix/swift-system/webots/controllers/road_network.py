"""
SWIFT SYSTEM - Webots Road & Lane Network Architecture (Module 2 Critical Fix)
Provides explicit junction positions, road segment definitions, Indian Left-Hand Traffic (LHT)
lane centerlines, waypoints, stop lines, signal associations, and multi-vehicle route mappings
for the expanded simulation city.
"""

import math
import json
import os
from typing import Dict, List, Tuple, Optional, Any

# Map directory paths
STATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SIGNAL_STATE_FILE = os.path.join(STATE_DIR, "traffic_signal_states.json")

# Central Geometry Constants
STOP_LINE_OFFSET = 12.0  # Stop line distance from junction center
JUNCTION_BOX_SIZE = 20.0 # 20m x 20m intersection center box
LANE_WIDTH = 4.0         # meters per directional lane
CAR_LENGTH = 4.4         # meters
MIN_GAP = 1.5            # meters minimum bumper gap
STOP_VEHICLE_DISTANCE = CAR_LENGTH + MIN_GAP
DEFAULT_LANE_OFFSET = 3.5 # meters offset from road centerline for Indian LHT
MAX_ROAD_DEVIATION = 4.0   # meters maximum lateral deviation before forced road recovery
# Shared In-Memory Registry for Zero-Latency Multi-Vehicle Tracking
SHARED_MEMORY_REGISTRY: Dict[str, Tuple[float, float, float]] = {}



# ==========================================
# EXPLICIT JUNCTION COORDINATES & REGISTRY
# ==========================================
JUNCTION_REGISTRY: Dict[str, Dict[str, Any]] = {
    "JUNCTION_01": {
        "id": "JUNCTION_01",
        "name": "Junction 1 (Central North-West Arterial 4-Way Intersection)",
        "center": (-250.0, 250.0, 0.0),
        "size": (22.0, 22.0),
        "approaches": {
            "NORTH": {"stop_line": (-250.0, 264.0), "controlled_lane": "LANE_J1_J8_SB"},
            "SOUTH": {"stop_line": (-250.0, 236.0), "controlled_lane": "LANE_J4_J1_NB"},
            "EAST":  {"stop_line": (-236.0, 250.0), "controlled_lane": "LANE_J2_J1_WB"},
            "WEST":  {"stop_line": (-264.0, 250.0), "controlled_lane": "LANE_J7_J1_EB"},
        }
    },
    "JUNCTION_02": {
        "id": "JUNCTION_02",
        "name": "Junction 2 (Central North-East Mall Gateway 4-Way Intersection)",
        "center": (250.0, 250.0, 0.0),
        "size": (22.0, 22.0),
        "approaches": {
            "NORTH": {"stop_line": (250.0, 264.0), "controlled_lane": "LANE_J15_J2_SB"},
            "SOUTH": {"stop_line": (250.0, 236.0), "controlled_lane": "LANE_J3_J2_NB"},
            "EAST":  {"stop_line": (264.0, 250.0), "controlled_lane": "LANE_J9_J2_WB"},
            "WEST":  {"stop_line": (236.0, 250.0), "controlled_lane": "LANE_J1_J2_EB"},
        }
    },
    "JUNCTION_03": {
        "id": "JUNCTION_03",
        "name": "Junction 3 (Central East Roundabout Hub - Roundabout 1)",
        "center": (220.0, -50.0, 0.0),
        "size": (56.0, 56.0),
        "approaches": {
            "NORTH": {"stop_line": (220.0, -22.0),  "controlled_lane": "LANE_J2_J3_SB"},
            "SOUTH": {"stop_line": (220.0, -78.0), "controlled_lane": "LANE_J5_J3_NB"},
            "WEST":  {"stop_line": (192.0, -50.0), "controlled_lane": "LANE_J4_J3_EB"},
            "EAST":  {"stop_line": (248.0, -50.0), "controlled_lane": "LANE_J11_J3_WB"},
        }
    },
    "JUNCTION_04": {
        "id": "JUNCTION_04",
        "name": "Junction 4 (Government Hospital Gateway Intersection)",
        "center": (-250.0, -250.0, 0.0),
        "size": (22.0, 22.0),
        "approaches": {
            "NORTH": {"stop_line": (-250.0, -236.0), "controlled_lane": "LANE_J1_J4_SB"},
            "SOUTH": {"stop_line": (-250.0, -264.0), "controlled_lane": "LANE_J6_J4_NB"},
            "EAST":  {"stop_line": (-236.0, -250.0), "controlled_lane": "LANE_J3_J4_WB"},
            "WEST":  {"stop_line": (-264.0, -250.0), "controlled_lane": "LANE_J10_J4_EB"},
        }
    },
    "JUNCTION_05": {
        "id": "JUNCTION_05",
        "name": "Junction 5 (South Central Highway Gateway Intersection)",
        "center": (150.0, -450.0, 0.0),
        "size": (22.0, 22.0),
        "approaches": {
            "NORTH": {"stop_line": (150.0, -436.0), "controlled_lane": "LANE_J3_J5_SB"},
            "SOUTH": {"stop_line": (150.0, -464.0), "controlled_lane": "LANE_J13_J5_NB"},
            "EAST":  {"stop_line": (164.0, -450.0), "controlled_lane": "LANE_J14_J5_WB"},
            "WEST":  {"stop_line": (136.0, -450.0), "controlled_lane": "LANE_J6_J5_EB"},
        }
    },
    "JUNCTION_06": {
        "id": "JUNCTION_06",
        "name": "Junction 6 (Dispatch Depot South-West 3-Way Intersection)",
        "center": (-350.0, -450.0, 0.0),
        "size": (20.0, 20.0),
        "approaches": {
            "NORTH": {"stop_line": (-350.0, -436.0), "controlled_lane": "LANE_J4_J6_SB"},
            "SOUTH": {"stop_line": (-350.0, -464.0), "controlled_lane": "LANE_J12_J6_NB"},
            "EAST":  {"stop_line": (-336.0, -450.0), "controlled_lane": "LANE_J5_J6_WB"},
        }
    },
    "JUNCTION_07": {"id": "JUNCTION_07", "center": (-700.0, 700.0, 0.0)},
    "JUNCTION_08": {"id": "JUNCTION_08", "center": (0.0, 850.0, 0.0)},
    "JUNCTION_09": {"id": "JUNCTION_09", "center": (700.0, 700.0, 0.0)},
    "JUNCTION_10": {"id": "JUNCTION_10", "center": (-850.0, 0.0, 0.0)},
    "JUNCTION_11": {"id": "JUNCTION_11", "center": (850.0, 0.0, 0.0)},
    "JUNCTION_12": {"id": "JUNCTION_12", "center": (-700.0, -700.0, 0.0)},
    "JUNCTION_13": {"id": "JUNCTION_13", "center": (0.0, -850.0, 0.0)},
    "JUNCTION_14": {"id": "JUNCTION_14", "center": (700.0, -700.0, 0.0)},
    "JUNCTION_15": {"id": "JUNCTION_15", "center": (450.0, 450.0, 0.0)},
}

# ==========================================
# EXPLICIT HOSPITAL & SCHOOL REGISTRY
# ==========================================
HOSPITAL_REGISTRY: Dict[str, Any] = {
    "GOVT_HOSPITAL": {
        "id": "GOVT_HOSPITAL",
        "name": "Government Hospital & Medical Center",
        "building_center": (-420.0, -250.0, 0.0),
        "emergency_bay": (-360.0, -250.0, 0.0),
        "connected_junction": "JUNCTION_04",
    },
    "PRIVATE_HOSPITAL": {
        "id": "PRIVATE_HOSPITAL",
        "name": "Private Hospital & Specialty Center",
        "building_center": (350.0, -250.0, 0.0),
        "emergency_bay": (300.0, -250.0, 0.0),
        "connected_junction": "JUNCTION_05",
    }
}

SCHOOL_REGISTRY: Dict[str, Any] = {
    "SCHOOL_01": {
        "id": "SCHOOL_01",
        "name": "District School & Athletic Campus",
        "building_center": (0.0, 470.0, 0.0),
        "connected_junction": "JUNCTION_01",
    }
}

# ==========================================
# EXPLICIT ROAD REGISTRY
# ==========================================
ROAD_REGISTRY: Dict[str, Dict[str, Any]] = {
    "ROAD_J1_J2": {"start": (-250.0, 250.0), "end": (250.0, 250.0), "width": 20.0, "connected_junctions": ["JUNCTION_01", "JUNCTION_02"]},
    "ROAD_J1_J4": {"start": (-250.0, 250.0), "end": (-250.0, -250.0), "width": 20.0, "connected_junctions": ["JUNCTION_01", "JUNCTION_04"]},
    "ROAD_J2_J3": {"start": (250.0, 250.0), "end": (220.0, -50.0), "width": 20.0, "connected_junctions": ["JUNCTION_02", "JUNCTION_03"]},
    "ROAD_J4_J3": {"start": (-250.0, -250.0), "end": (220.0, -50.0), "width": 20.0, "connected_junctions": ["JUNCTION_04", "JUNCTION_03"]},
    "ROAD_J4_J5": {"start": (-250.0, -250.0), "end": (150.0, -450.0), "width": 20.0, "connected_junctions": ["JUNCTION_04", "JUNCTION_05"]},
    "ROAD_J3_J5": {"start": (220.0, -50.0), "end": (150.0, -450.0), "width": 20.0, "connected_junctions": ["JUNCTION_03", "JUNCTION_05"]},
    "ROAD_J5_J6": {"start": (150.0, -450.0), "end": (-350.0, -450.0), "width": 20.0, "connected_junctions": ["JUNCTION_05", "JUNCTION_06"]},
    "ROAD_J6_J4": {"start": (-350.0, -450.0), "end": (-250.0, -250.0), "width": 20.0, "connected_junctions": ["JUNCTION_06", "JUNCTION_04"]},
    "ROAD_J1_J7": {"start": (-250.0, 250.0), "end": (-700.0, 700.0), "width": 20.0, "connected_junctions": ["JUNCTION_01", "JUNCTION_07"]},
    "ROAD_J1_J8": {"start": (-250.0, 250.0), "end": (0.0, 850.0), "width": 20.0, "connected_junctions": ["JUNCTION_01", "JUNCTION_08"]},
    "ROAD_J2_J9": {"start": (250.0, 250.0), "end": (700.0, 700.0), "width": 20.0, "connected_junctions": ["JUNCTION_02", "JUNCTION_09"]},
    "ROAD_J4_J10": {"start": (-250.0, -250.0), "end": (-850.0, 0.0), "width": 20.0, "connected_junctions": ["JUNCTION_04", "JUNCTION_10"]},
    "ROAD_J3_J11": {"start": (220.0, -50.0), "end": (850.0, 0.0), "width": 20.0, "connected_junctions": ["JUNCTION_03", "JUNCTION_11"]},
    "ROAD_J6_J12": {"start": (-350.0, -450.0), "end": (-700.0, -700.0), "width": 20.0, "connected_junctions": ["JUNCTION_06", "JUNCTION_12"]},
    "ROAD_J5_J13": {"start": (150.0, -450.0), "end": (0.0, -850.0), "width": 20.0, "connected_junctions": ["JUNCTION_05", "JUNCTION_13"]},
    "ROAD_J5_J14": {"start": (150.0, -450.0), "end": (700.0, -700.0), "width": 20.0, "connected_junctions": ["JUNCTION_05", "JUNCTION_14"]},
    "ROAD_J2_J15": {"start": (250.0, 250.0), "end": (450.0, 450.0), "width": 20.0, "connected_junctions": ["JUNCTION_02", "JUNCTION_15"]},
}


def read_signal_state(junction_id: str, approach: str) -> str:
    """Read current lamp state for a specific junction approach."""
    if not os.path.exists(SIGNAL_STATE_FILE):
        return "GREEN"
    try:
        with open(SIGNAL_STATE_FILE, "r") as f:
            data = json.load(f)
        
        keys_to_check = [junction_id]
        if junction_id.startswith("JUNCTION_0"):
            keys_to_check.append(f"J{int(junction_id[10:])}")
            keys_to_check.append(f"JUNCTION_{int(junction_id[10:])}")
        elif junction_id.startswith("JUNCTION_"):
            keys_to_check.append(f"J{int(junction_id[9:])}")
        elif junction_id.startswith("J") and junction_id[1:].isdigit():
            num = int(junction_id[1:])
            keys_to_check.append(f"JUNCTION_{num:02d}")
            keys_to_check.append(f"JUNCTION_{num}")
            
        for k in keys_to_check:
            if k in data and isinstance(data[k], dict):
                if approach in data[k]:
                    return data[k][approach]
                    
        return "GREEN"
    except Exception:
        return "GREEN"



class Lane:
    """Represents a single directional road lane in Indian Left-Hand Traffic (LHT)."""
    def __init__(
        self,
        lane_id: str,
        direction: str,
        start_point: Tuple[float, float],
        end_point: Tuple[float, float],
        waypoints: List[Tuple[float, float]],
        next_junction: Optional[str] = None,
        controlled_signal: Optional[Tuple[str, str]] = None,
        stop_line: Optional[Tuple[float, float]] = None,
    ):
        self.lane_id = lane_id
        self.direction = direction  # "EAST", "WEST", "NORTH", "SOUTH", "NE", "NW", "SE", "SW"
        self.start_point = start_point
        self.end_point = end_point
        self.waypoints = waypoints
        self.next_junction = next_junction
        self.controlled_signal = controlled_signal  # (junction_id, approach_name)
        self.stop_line = stop_line  # (x, y) coordinate of stop line

        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        dist = math.hypot(dx, dy)
        self.length = dist
        self.unit_vector = (dx / dist, dy / dist) if dist > 1e-6 else (1.0, 0.0)
        self.target_heading = math.atan2(self.unit_vector[1], self.unit_vector[0])


def _build_lht_lane(
    lane_id: str,
    direction_str: str,
    start_center: Tuple[float, float],
    end_center: Tuple[float, float],
    offset: float = DEFAULT_LANE_OFFSET,
    num_pts: int = 6,
    next_junction: Optional[str] = None,
    controlled_signal: Optional[Tuple[str, str]] = None,
) -> Lane:
    """
    Generates a single LHT lane offset relative to the road centerline.
    n_left = (-uy, ux) vector multiplies offset to ensure vehicle drives on the LEFT side of travel direction.
    """
    dx = end_center[0] - start_center[0]
    dy = end_center[1] - start_center[1]
    dist = math.hypot(dx, dy)
    ux, uy = (dx / dist, dy / dist) if dist > 1e-6 else (1.0, 0.0)

    # Left normal vector relative to travel direction
    nx, ny = -uy, ux

    # Lane centerline start & end
    l_start = (start_center[0] + nx * offset, start_center[1] + ny * offset)
    l_end = (end_center[0] + nx * offset, end_center[1] + ny * offset)

    # Calculate stop line if next_junction is defined
    stop_line = None
    if next_junction:
        stop_line = (l_end[0] - ux * STOP_LINE_OFFSET, l_end[1] - uy * STOP_LINE_OFFSET)

    # Waypoints sequence along lane
    wps = []
    for i in range(num_pts):
        t = i / float(num_pts - 1)
        wx = l_start[0] + t * (l_end[0] - l_start[0])
        wy = l_start[1] + t * (l_end[1] - l_start[1])
        wps.append((round(wx, 2), round(wy, 2)))

    return Lane(
        lane_id=lane_id,
        direction=direction_str,
        start_point=(round(l_start[0], 2), round(l_start[1], 2)),
        end_point=(round(l_end[0], 2), round(l_end[1], 2)),
        waypoints=wps,
        next_junction=next_junction,
        controlled_signal=controlled_signal,
        stop_line=stop_line,
    )


# ==========================================
# EXPLICIT ROAD NETWORK LANES (INDIAN LHT)
# ==========================================
ROAD_NETWORK: Dict[str, Lane] = {}

# 1. J1 <-> J2 (Horizontal along Y = 250)
ROAD_NETWORK["LANE_J1_J2_EB"] = _build_lht_lane("LANE_J1_J2_EB", "EAST", (-250.0, 250.0), (250.0, 250.0), next_junction="JUNCTION_02", controlled_signal=("JUNCTION_02", "WEST"))
ROAD_NETWORK["LANE_J2_J1_WB"] = _build_lht_lane("LANE_J2_J1_WB", "WEST", (250.0, 250.0), (-250.0, 250.0), next_junction="JUNCTION_01", controlled_signal=("JUNCTION_01", "EAST"))

# 2. J1 <-> J4 (Vertical along X = -250)
ROAD_NETWORK["LANE_J1_J4_SB"] = _build_lht_lane("LANE_J1_J4_SB", "SOUTH", (-250.0, 250.0), (-250.0, -250.0), next_junction="JUNCTION_04", controlled_signal=("JUNCTION_04", "NORTH"))
ROAD_NETWORK["LANE_J4_J1_NB"] = _build_lht_lane("LANE_J4_J1_NB", "NORTH", (-250.0, -250.0), (-250.0, 250.0), next_junction="JUNCTION_01", controlled_signal=("JUNCTION_01", "SOUTH"))

# 3. J2 <-> J3 (North-East Avenue)
ROAD_NETWORK["LANE_J2_J3_SB"] = _build_lht_lane("LANE_J2_J3_SB", "SOUTH", (250.0, 250.0), (220.0, -50.0), next_junction="JUNCTION_03", controlled_signal=("JUNCTION_03", "NORTH"))
ROAD_NETWORK["LANE_J3_J2_NB"] = _build_lht_lane("LANE_J3_J2_NB", "NORTH", (220.0, -50.0), (250.0, 250.0), next_junction="JUNCTION_02", controlled_signal=("JUNCTION_02", "SOUTH"))

# 4. J4 <-> J3 (Diagonal J4 to J3)
ROAD_NETWORK["LANE_J4_J3_EB"] = _build_lht_lane("LANE_J4_J3_EB", "EAST", (-250.0, -250.0), (220.0, -50.0), next_junction="JUNCTION_03", controlled_signal=("JUNCTION_03", "WEST"))
ROAD_NETWORK["LANE_J3_J4_WB"] = _build_lht_lane("LANE_J3_J4_WB", "WEST", (220.0, -50.0), (-250.0, -250.0), next_junction="JUNCTION_04", controlled_signal=("JUNCTION_04", "EAST"))

# 5. J4 <-> J5 (South Medical Connector)
ROAD_NETWORK["LANE_J4_J5_SE"] = _build_lht_lane("LANE_J4_J5_SE", "SE", (-250.0, -250.0), (150.0, -450.0), next_junction="JUNCTION_05", controlled_signal=("JUNCTION_05", "WEST"))
ROAD_NETWORK["LANE_J5_J4_NW"] = _build_lht_lane("LANE_J5_J4_NW", "NW", (150.0, -450.0), (-250.0, -250.0), next_junction="JUNCTION_04", controlled_signal=("JUNCTION_04", "SOUTH"))

# 6. J3 <-> J5 (East Commercial Avenue)
ROAD_NETWORK["LANE_J3_J5_SB"] = _build_lht_lane("LANE_J3_J5_SB", "SOUTH", (220.0, -50.0), (150.0, -450.0), next_junction="JUNCTION_05", controlled_signal=("JUNCTION_05", "NORTH"))
ROAD_NETWORK["LANE_J5_J3_NB"] = _build_lht_lane("LANE_J5_J3_NB", "NORTH", (150.0, -450.0), (220.0, -50.0), next_junction="JUNCTION_03", controlled_signal=("JUNCTION_03", "SOUTH"))

# 7. J5 <-> J6 (South Highway along Y = -450)
ROAD_NETWORK["LANE_J5_J6_WB"] = _build_lht_lane("LANE_J5_J6_WB", "WEST", (150.0, -450.0), (-350.0, -450.0), next_junction="JUNCTION_06", controlled_signal=("JUNCTION_06", "EAST"))
ROAD_NETWORK["LANE_J6_J5_EB"] = _build_lht_lane("LANE_J6_J5_EB", "EAST", (-350.0, -450.0), (150.0, -450.0), next_junction="JUNCTION_05", controlled_signal=("JUNCTION_05", "WEST"))

# 8. J6 <-> J4 (Dispatch Link)
ROAD_NETWORK["LANE_J6_J4_NE"] = _build_lht_lane("LANE_J6_J4_NE", "NE", (-350.0, -450.0), (-250.0, -250.0), next_junction="JUNCTION_04", controlled_signal=("JUNCTION_04", "SOUTH"))
ROAD_NETWORK["LANE_J4_J6_SB"] = _build_lht_lane("LANE_J4_J6_SB", "SOUTH", (-250.0, -250.0), (-350.0, -450.0), next_junction="JUNCTION_06", controlled_signal=("JUNCTION_06", "NORTH"))

# 9. Outer Arterial Connectors
ROAD_NETWORK["LANE_J1_J7_NW"] = _build_lht_lane("LANE_J1_J7_NW", "NW", (-250.0, 250.0), (-700.0, 700.0), next_junction="JUNCTION_07")
ROAD_NETWORK["LANE_J7_J1_SE"] = _build_lht_lane("LANE_J7_J1_SE", "SE", (-700.0, 700.0), (-250.0, 250.0), next_junction="JUNCTION_01", controlled_signal=("JUNCTION_01", "WEST"))

ROAD_NETWORK["LANE_J1_J8_NE"] = _build_lht_lane("LANE_J1_J8_NE", "NE", (-250.0, 250.0), (0.0, 850.0), next_junction="JUNCTION_08")
ROAD_NETWORK["LANE_J8_J1_SW"] = _build_lht_lane("LANE_J8_J1_SW", "SW", (0.0, 850.0), (-250.0, 250.0), next_junction="JUNCTION_01", controlled_signal=("JUNCTION_01", "NORTH"))

ROAD_NETWORK["LANE_J2_J9_NE"] = _build_lht_lane("LANE_J2_J9_NE", "NE", (250.0, 250.0), (700.0, 700.0), next_junction="JUNCTION_09")
ROAD_NETWORK["LANE_J9_J2_SW"] = _build_lht_lane("LANE_J9_J2_SW", "SW", (700.0, 700.0), (250.0, 250.0), next_junction="JUNCTION_02", controlled_signal=("JUNCTION_02", "EAST"))

ROAD_NETWORK["LANE_J4_J10_NW"] = _build_lht_lane("LANE_J4_J10_NW", "NW", (-250.0, -250.0), (-850.0, 0.0), next_junction="JUNCTION_10")
ROAD_NETWORK["LANE_J10_J4_SE"] = _build_lht_lane("LANE_J10_J4_SE", "SE", (-850.0, 0.0), (-250.0, -250.0), next_junction="JUNCTION_04", controlled_signal=("JUNCTION_04", "WEST"))

ROAD_NETWORK["LANE_J3_J11_EB"] = _build_lht_lane("LANE_J3_J11_EB", "EAST", (220.0, -50.0), (850.0, 0.0), next_junction="JUNCTION_11")
ROAD_NETWORK["LANE_J11_J3_WB"] = _build_lht_lane("LANE_J11_J3_WB", "WEST", (850.0, 0.0), (220.0, -50.0), next_junction="JUNCTION_03", controlled_signal=("JUNCTION_03", "EAST"))

ROAD_NETWORK["LANE_J5_J13_SB"] = _build_lht_lane("LANE_J5_J13_SB", "SOUTH", (150.0, -450.0), (0.0, -850.0), next_junction="JUNCTION_13")
ROAD_NETWORK["LANE_J13_J5_NB"] = _build_lht_lane("LANE_J13_J5_NB", "NORTH", (0.0, -850.0), (150.0, -450.0), next_junction="JUNCTION_05", controlled_signal=("JUNCTION_05", "SOUTH"))

ROAD_NETWORK["LANE_J5_J14_SE"] = _build_lht_lane("LANE_J5_J14_SE", "SE", (150.0, -450.0), (700.0, -700.0), next_junction="JUNCTION_14")
ROAD_NETWORK["LANE_J14_J5_NW"] = _build_lht_lane("LANE_J14_J5_NW", "NW", (700.0, -700.0), (150.0, -450.0), next_junction="JUNCTION_05", controlled_signal=("JUNCTION_05", "EAST"))

ROAD_NETWORK["LANE_J2_J15_NE"] = _build_lht_lane("LANE_J2_J15_NE", "NE", (250.0, 250.0), (450.0, 450.0), next_junction="JUNCTION_15")
ROAD_NETWORK["LANE_J15_J2_SW"] = _build_lht_lane("LANE_J15_J2_SW", "SW", (450.0, 450.0), (250.0, 250.0), next_junction="JUNCTION_02", controlled_signal=("JUNCTION_02", "NORTH"))


# Backward Compatibility Lane Aliases for Existing Suite
ROAD_NETWORK["LANE_SCHOOL_01_EB"] = ROAD_NETWORK["LANE_J1_J2_EB"]
ROAD_NETWORK["LANE_SCHOOL_01_WB"] = ROAD_NETWORK["LANE_J2_J1_WB"]
ROAD_NETWORK["LANE_WEST_NORTH"] = Lane(
    lane_id="LANE_WEST_NORTH",
    direction="NORTH",
    start_point=(-46.5, -50.0),
    end_point=(-46.5, 46.5),
    waypoints=[(-46.5, 20.0), (-46.5, 43.0), (-46.5, 46.5)],
    next_junction="J1",
    controlled_signal=("J1", "SOUTH"),
    stop_line=(-46.5, 43.0)
)
ROAD_NETWORK["LANE_NORTH_EAST"] = Lane(
    lane_id="LANE_NORTH_EAST",
    direction="EAST",
    start_point=(-46.5, 46.5),
    end_point=(50.0, 46.5),
    waypoints=[(-46.5, 46.5), (-43.0, 46.5), (50.0, 46.5)],
    next_junction="J2",
    controlled_signal=("J2", "WEST"),
    stop_line=(43.0, 46.5)
)
ROAD_NETWORK["LANE_EAST_SOUTH"] = ROAD_NETWORK["LANE_J2_J3_SB"]



# ==========================================
# EXPLICIT MULTI-VEHICLE ROUTES (PER-VEHICLE)
# ==========================================
VEHICLE_ROUTES: Dict[str, List[str]] = {
    # 10 CARS
    "CAR_001": ["LANE_J1_J2_EB", "LANE_J2_J3_SB", "LANE_J3_J4_WB", "LANE_J4_J1_NB"],
    "CAR_002": ["LANE_J1_J4_SB", "LANE_J4_J3_EB", "LANE_J3_J2_NB", "LANE_J2_J1_WB"],
    "CAR_003": ["LANE_J4_J5_SE", "LANE_J5_J6_WB", "LANE_J6_J4_NE"],
    "CAR_004": ["LANE_J1_J7_NW", "LANE_J7_J1_SE", "LANE_J1_J8_NE", "LANE_J8_J1_SW"],
    "CAR_005": ["LANE_J2_J15_NE", "LANE_J15_J2_SW", "LANE_J2_J9_NE", "LANE_J9_J2_SW"],
    "CAR_006": ["LANE_J3_J11_EB", "LANE_J11_J3_WB", "LANE_J3_J5_SB", "LANE_J5_J3_NB"],
    "CAR_007": ["LANE_J4_J10_NW", "LANE_J10_J4_SE", "LANE_J4_J1_NB", "LANE_J1_J4_SB"],
    "CAR_008": ["LANE_J5_J13_SB", "LANE_J13_J5_NB", "LANE_J5_J14_SE", "LANE_J14_J5_NW"],
    "CAR_009": ["LANE_J1_J2_EB", "LANE_J2_J3_SB", "LANE_J3_J5_SB", "LANE_J5_J6_WB", "LANE_J6_J4_NE", "LANE_J4_J1_NB"],
    "CAR_010": ["LANE_J4_J3_EB", "LANE_J3_J2_NB", "LANE_J2_J1_WB", "LANE_J1_J4_SB"],

    # 5 BIKES
    "BIKE_001": ["LANE_J1_J2_EB", "LANE_J2_J3_SB", "LANE_J3_J4_WB", "LANE_J4_J1_NB"],
    "BIKE_002": ["LANE_J1_J4_SB", "LANE_J4_J3_EB", "LANE_J3_J2_NB", "LANE_J2_J1_WB"],
    "BIKE_003": ["LANE_J4_J5_SE", "LANE_J5_J6_WB", "LANE_J6_J4_NE"],
    "BIKE_004": ["LANE_J2_J3_SB", "LANE_J3_J5_SB", "LANE_J5_J6_WB", "LANE_J6_J4_NE"],
    "BIKE_005": ["LANE_J1_J2_EB", "LANE_J2_J15_NE", "LANE_J15_J2_SW", "LANE_J2_J1_WB"],

    # AMBULANCE
    "AMBULANCE_001": ["LANE_J4_J5_SE", "LANE_J5_J3_NB", "LANE_J3_J2_NB", "LANE_J2_J1_WB"],
}


def calculate_deterministic_spawns() -> Dict[str, Dict[str, float]]:
    """
    Calculates exact LHT lane centerline spawn coordinates for all vehicles,
    ensuring minimum safe longitudinal separation (zero visual overlap at spawn).
    """
    lane_vehicle_map: Dict[str, List[str]] = {}
    for v_id, route in VEHICLE_ROUTES.items():
        if route:
            start_lane_id = route[0]
            if start_lane_id not in lane_vehicle_map:
                lane_vehicle_map[start_lane_id] = []
            lane_vehicle_map[start_lane_id].append(v_id)

    spawns = {}
    for lane_id, v_list in lane_vehicle_map.items():
        if lane_id in ROAD_NETWORK:
            lane = ROAD_NETWORK[lane_id]
            for idx, v_id in enumerate(v_list):
                s_dist = 15.0 + idx * 40.0
                sx = round(lane.start_point[0] + s_dist * lane.unit_vector[0], 2)
                sy = round(lane.start_point[1] + s_dist * lane.unit_vector[1], 2)
                spawns[v_id] = {
                    "x": sx,
                    "y": sy,
                    "heading": round(lane.target_heading, 4)
                }
    return spawns


DETERMINISTIC_VEHICLE_SPAWNS: Dict[str, Dict[str, float]] = calculate_deterministic_spawns()


CLOCKWISE_LANE_LOOP: List[str] = [
    "LANE_J1_J2_EB",
    "LANE_J2_J3_SB",
    "LANE_J3_J4_WB",
    "LANE_J4_J1_NB",
]


def validate_road_corridor(x: float, y: float) -> bool:
    """Validates if (x, y) coordinate is within playable terrain and city boundaries."""
    return -1350.0 <= x <= 1350.0 and -1350.0 <= y <= 1350.0


def get_lateral_distance_to_lane(x: float, y: float, lane: Lane) -> float:
    """Calculates true lateral distance from point (x, y) to the continuous lane line segment."""
    sl_x, sl_y = lane.start_point
    el_x, el_y = lane.end_point
    dx = el_x - sl_x
    dy = el_y - sl_y
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return math.hypot(x - sl_x, y - sl_y)
    t = max(0.0, min(1.0, ((x - sl_x) * dx + (y - sl_y) * dy) / (length * length)))
    proj_x = sl_x + t * dx
    proj_y = sl_y + t * dy
    return math.hypot(x - proj_x, y - proj_y)


def get_distance_to_stop_line(x: float, y: float, lane: Lane) -> Optional[float]:
    """Calculate forward distance along lane direction from (x, y) to the stop line."""
    if not lane.stop_line:
        return None
    sl_x, sl_y = lane.stop_line
    dx = sl_x - x
    dy = sl_y - y
    return dx * lane.unit_vector[0] + dy * lane.unit_vector[1]


def get_nearest_lane_waypoint(x: float, y: float, lane: Lane) -> Tuple[int, Tuple[float, float]]:
    """Find index and coordinates of nearest waypoint in lane."""
    min_dist = float("inf")
    best_idx = 0
    best_wp = lane.waypoints[0]
    for idx, wp in enumerate(lane.waypoints):
        dist = math.hypot(wp[0] - x, wp[1] - y)
        if dist < min_dist:
            min_dist = dist
            best_idx = idx
            best_wp = wp
    return best_idx, best_wp


def get_next_forward_waypoint_idx(x: float, y: float, heading: float, lane: Lane) -> int:
    """Find index of nearest forward waypoint in lane relative to vehicle position and heading."""
    min_dist = float("inf")
    best_idx = 0
    for idx, wp in enumerate(lane.waypoints):
        dx = wp[0] - x
        dy = wp[1] - y
        dist = math.hypot(dx, dy)
        dot = dx * lane.unit_vector[0] + dy * lane.unit_vector[1]
        if dot >= -2.0 and dist < min_dist:
            min_dist = dist
            best_idx = idx
    return best_idx


def snap_to_nearest_lane(x: float, y: float, route: Optional[List[str]] = None) -> Tuple[Lane, int, Tuple[float, float]]:
    """
    Finds the closest valid LHT lane and waypoint to snap/recover a vehicle if off road tolerance.
    """
    candidate_lanes = [ROAD_NETWORK[lname] for lname in route if lname in ROAD_NETWORK] if route else list(ROAD_NETWORK.values())
    best_lane = candidate_lanes[0]
    best_idx = 0
    best_wp = best_lane.waypoints[0]
    min_dist = float("inf")

    for lane in candidate_lanes:
        dist = get_lateral_distance_to_lane(x, y, lane)
        if dist < min_dist:
            min_dist = dist
            best_lane = lane
            idx, wp = get_nearest_lane_waypoint(x, y, lane)
            best_idx = idx
            best_wp = wp

    return best_lane, best_idx, best_wp


def is_inside_road_boundary(x: float, y: float, lane: Optional[Lane], max_deviation: float = MAX_ROAD_DEVIATION) -> bool:
    """Checks if point (x, y) is strictly inside valid road lane boundaries."""
    if lane is None:
        return False
    if not validate_road_corridor(x, y):
        return False
    dist = get_lateral_distance_to_lane(x, y, lane)
    return dist <= max_deviation


def get_lane_projection_and_offset(x: float, y: float, lane: Lane) -> Tuple[Tuple[float, float], float]:
    """
    Returns (projected_point_on_lane_centerline, signed_lateral_offset).
    Signed lateral offset is positive if vehicle is to the left of travel vector, negative if right.
    """
    sl_x, sl_y = lane.start_point
    el_x, el_y = lane.end_point
    dx = el_x - sl_x
    dy = el_y - sl_y
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return (sl_x, sl_y), 0.0
    ux, uy = dx / length, dy / length
    t = max(0.0, min(1.0, ((x - sl_x) * ux + (y - sl_y) * uy) / length))
    proj_x = sl_x + t * dx
    proj_y = sl_y + t * dy
    # Signed cross product (vehicle_vec x unit_vector)
    signed_offset = (x - sl_x) * uy - (y - sl_y) * ux
    return (proj_x, proj_y), signed_offset


def calculate_lookahead_target(x: float, y: float, lane: Lane, lookahead_dist: float = 6.0) -> Tuple[float, float]:
    """
    Calculates a continuous look-ahead point along the assigned lane centerline.
    """
    sl_x, sl_y = lane.start_point
    el_x, el_y = lane.end_point
    dx = el_x - sl_x
    dy = el_y - sl_y
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return (el_x, el_y)
    ux, uy = dx / length, dy / length
    
    # Forward distance of vehicle along lane segment
    t = ((x - sl_x) * ux + (y - sl_y) * uy)
    target_dist = max(0.0, min(length, t + lookahead_dist))
    
    tx = sl_x + ux * target_dist
    ty = sl_y + uy * target_dist
    return (tx, ty)


def calculate_lane_centering_heading(x: float, y: float, lane: Lane, lookahead_dist: float = 6.0, k_p: float = 0.25) -> float:
    """
    Calculates target heading with active lane-centering steering correction.
    Combines look-ahead direction with proportional lateral error correction to pull vehicle to centerline.
    """
    (proj_x, proj_y), signed_offset = get_lane_projection_and_offset(x, y, lane)
    tx, ty = calculate_lookahead_target(x, y, lane, lookahead_dist)
    
    dx = tx - x
    dy = ty - y
    if math.hypot(dx, dy) < 0.1:
        base_heading = lane.target_heading
    else:
        base_heading = math.atan2(dy, dx)
        
    # Proportional correction: steer right (negative angle) if offset > 0 (vehicle left of line), and vice-versa
    max_corr = math.radians(25.0)  # max 25 degree correction bias
    corr_angle = max(-max_corr, min(max_corr, -signed_offset * k_p))
    
    return lane.target_heading if math.hypot(dx, dy) < 0.1 else math.atan2(math.sin(base_heading + corr_angle), math.cos(base_heading + corr_angle))


