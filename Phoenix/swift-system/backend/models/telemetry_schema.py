"""
SWIFT SYSTEM - Telemetry & Decision Schema Definitions
Strict Pydantic models for 25-node intersection telemetry and central server decisions.
Enforces contractual field names, types, and value constraints.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
import time


class IntersectionTelemetry(BaseModel):
    """
    Contractual 16-field telemetry model for a single traffic intersection node.
    Field names and capitalization must strictly match the contract.
    """
    node: int = Field(..., ge=0, le=24, description="Intersection node ID (0-24)")
    queue_length: int = Field(..., ge=0, description="Vehicles queued at intersection")
    flush_time: float = Field(..., ge=0.0, description="Estimated clearance time in seconds")
    light_phase: Literal["NS_GREEN", "EW_GREEN", "YELLOW"] = Field(..., description="Current signal light phase")
    active_direction: Literal["NS", "EW"] = Field(..., description="Active green/transitioning direction")
    phase_remaining_ticks: int = Field(..., ge=0, description="Remaining ticks in phase")
    preemption_active: bool = Field(False, description="Emergency vehicle signal priority active")
    reserved_axis: Optional[Literal["NS", "EW"]] = Field(None, description="Reserved axis for EV priority")
    reservation_ev_id: Optional[str] = Field(None, description="Emergency vehicle ID reserving signal")
    reservation_remaining_ticks: int = Field(0, ge=0, description="Remaining priority reservation ticks")
    reservation_end_time: Optional[float] = Field(None, description="Timestamp when reservation expires")
    preempted_from_phase: Optional[str] = Field(None, description="Phase interrupted by preemption")
    preempted_from_direction: Optional[str] = Field(None, description="Direction interrupted by preemption")
    reservation_control_ready: bool = Field(True, description="Controller supports preemption commands")
    simulation_tick: int = Field(..., ge=0, description="Current simulation tick")
    generated_at: float = Field(..., description="Unix epoch timestamp")

    @field_validator('active_direction', mode='before')
    @classmethod
    def validate_direction(cls, v, info):
        if isinstance(v, str):
            v_upper = v.upper()
            if v_upper in ["NS", "EW"]:
                return v_upper
        return v

    @field_validator('light_phase', mode='before')
    @classmethod
    def validate_phase(cls, v, info):
        if isinstance(v, str):
            v_upper = v.upper()
            if v_upper in ["NS_GREEN", "EW_GREEN", "YELLOW"]:
                return v_upper
        return v


class TelemetryPayload(BaseModel):
    """
    25-node complete telemetry array payload sent to central server.
    """
    nodes: List[IntersectionTelemetry] = Field(..., min_length=25, max_length=25)


class EmergencyRequest(BaseModel):
    """
    Emergency priority request payload emitted when ambulance requests route authorization.
    """
    event: Literal["EMERGENCY_REQUEST"] = "EMERGENCY_REQUEST"
    ambulance_id: str = "AMB_01"
    emergency_level: Literal["CRITICAL", "HIGH", "MEDIUM"] = "CRITICAL"
    current_node: int = Field(..., ge=0, le=24)


class HospitalInfo(BaseModel):
    """
    Government Hospital details structure.
    """
    id: str
    name: str
    type: Literal["Government"] = "Government"
    node: int
    latitude: float
    longitude: float
    distance_km: float


class SignalAction(BaseModel):
    """
    Signal control action for a specific intersection along emergency corridor.
    """
    node: int = Field(..., ge=0, le=24)
    axis: Literal["NS", "EW"]
    action: Literal["GREEN_PRIORITY"] = "GREEN_PRIORITY"


class CentralDecision(BaseModel):
    """
    Output decision structure returned by central server.
    """
    status: Literal["ROUTE_AUTHORIZED", "NO_ROUTE_AVAILABLE", "NORMAL_OPERATION"] = "ROUTE_AUTHORIZED"
    ambulance_id: str = "AMB_01"
    selected_hospital: HospitalInfo
    route: List[int]
    estimated_time_minutes: int
    signal_actions: List[SignalAction]


class RouteApiRequest(BaseModel):
    source: Optional[Any] = None
    destination: Optional[Any] = None
    start: Optional[int] = None
    end: Optional[int] = None
    vehicle_type: Optional[str] = "ambulance"


class RouteSegmentResponse(BaseModel):
    from_node: int = Field(..., alias="from")
    to_node: int = Field(..., alias="to")
    direction: Optional[str] = "NS"
    road_travel_seconds: float = 6.0
    signal_wait_seconds: float = 0.0
    travel_cost: float = 6.0
    congestion_cost: float = 6.0

    class Config:
        populate_by_name = True


class RouteApiResponse(BaseModel):
    success: bool = True
    source: str
    destination: str
    recommended_route: List[str]
    path: List[int]
    eta_minutes: float
    eta_seconds: float
    traffic_level: str
    traffic_score: Optional[float] = 0.35
    reason: str
    simulation_status: str = "completed"
    traffic_version: int = 1
    traffic_age_seconds: float = 0.5
    traffic_source: str = "webots_simulation"
    segments: Optional[List[RouteSegmentResponse]] = None
