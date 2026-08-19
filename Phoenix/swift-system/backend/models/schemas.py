"""
SWIFT SYSTEM - Data Schemas & Models
Pydantic schemas for data validation across REST, WebSocket, Agents, Predictor, Optimizer, and Safety Engine.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class EmergencyLevel(str, Enum):
    LEVEL_1 = "LEVEL_1"  # Normal emergency
    LEVEL_2 = "LEVEL_2"  # Serious
    LEVEL_3 = "LEVEL_3"  # Critical


class SignalPhase(str, Enum):
    GREEN_NS = "GREEN_NS"
    GREEN_EW = "GREEN_EW"
    YELLOW = "YELLOW"
    RED_ALL = "RED_ALL"
    PRIORITY = "PRIORITY"


class CongestionLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Position(BaseModel):
    x: float
    y: float
    z: Optional[float] = 0.0


class JunctionState(BaseModel):
    id: str
    pos: Position
    signal_state: str
    queue_length: int = Field(ge=0)
    vehicle_count: int = Field(ge=0)
    avg_speed: float = Field(ge=0.0)
    lane_occupancy: float = Field(ge=0.0, le=1.0)
    traffic_density: float = Field(ge=0.0, le=1.0)
    congestion_level: CongestionLevel
    priority_active: bool = False
    remaining_green: float = Field(ge=0.0)


class AmbulanceState(BaseModel):
    id: str = "AMB_01"
    urgency_level: EmergencyLevel = EmergencyLevel.LEVEL_3
    start_junction: str
    destination: str
    dest_junction: str
    current_junction: str
    current_road: str
    position: Position
    speed: float = Field(ge=0.0)
    target_speed: float = Field(ge=0.0)
    heading: float = 0.0
    route: List[str]
    route_progress: float = Field(ge=0.0, le=1.0)
    current_segment_index: int = Field(ge=0)
    stopped_in_traffic: bool = False
    cumulative_waiting_time: float = Field(ge=0.0)
    stops_count: int = Field(ge=0)
    eta_seconds: float = Field(ge=0.0)
    remaining_distance_m: float = Field(ge=0.0)
    active: bool = True
    has_arrived: bool = False


class Incident(BaseModel):
    road_id: str
    type: str = "ACCIDENT"
    severity: str = "HIGH"
    timestamp: float


class SignalCommand(BaseModel):
    junction_id: str
    signal_state: str
    green_duration: float = Field(gt=0.0)
    priority: bool = False
    release_priority: bool = False

    @field_validator("green_duration")
    def validate_min_duration(cls, v):
        if v < 3.0:
            raise ValueError("Green duration must be at least 3.0 seconds for safety")
        return v


class CandidateRoute(BaseModel):
    route_id: str
    path: List[str]
    distance_meters: float
    est_free_flow_time_sec: float
    est_congestion_delay_sec: float
    est_total_eta_sec: float
    score: float


class OptimizationResult(BaseModel):
    selected_route: List[str]
    selected_strategy_id: str
    estimated_eta: float
    congestion_cost: float
    disruption_cost: float
    signal_delay: float
    safety_passed: bool
    corridor_plan: Dict[str, str]  # e.g., {"J1": "PRIORITY", "J2": "PREPARE", "J3": "NORMAL"}


class MetricSnapshot(BaseModel):
    timestamp: float
    mode: str
    emergency_travel_time: float
    emergency_waiting_time: float
    number_of_stops: int
    avg_emergency_speed: float
    normal_traffic_delay: float
    max_queue_length: int
    avg_queue_length: float
    time_saved_sec: float
