"""
SWIFT SYSTEM - 25-Node Webots Telemetry Generator
Collects REAL Webots simulation state across a 5x5 intersection grid (25 nodes).
Generates ML-ready JSON telemetry matching the contractual 16-field schema.
Validates payload before network transmission.
"""

import os
import json
import math
import time
import tempfile
import logging
from typing import Dict, List, Any, Optional, Tuple
from backend.models.telemetry_schema import IntersectionTelemetry, TelemetryPayload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (TelemetryGen) %(message)s")
logger = logging.getLogger("TelemetryGen")

# File persistence paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TELEMETRY_DIR = os.path.join(PROJECT_ROOT, "data", "telemetry")
HISTORY_DIR = os.path.join(TELEMETRY_DIR, "history")
LATEST_TELEMETRY_FILE = os.path.join(TELEMETRY_DIR, "telemetry_latest.json")

_last_history_save_tick: int = -1
_last_history_save_time: float = 0.0


def save_telemetry_to_disk(
    payload_dicts: List[Dict[str, Any]],
    enable_history: Optional[bool] = None,
    history_interval_sec: float = 10.0
) -> None:
    """
    Atomically writes the 25-node telemetry payload array to disk as telemetry_latest.json.
    Optionally saves historical snapshots at configurable intervals.
    """
    global _last_history_save_tick, _last_history_save_time

    try:
        os.makedirs(TELEMETRY_DIR, exist_ok=True)

        # Atomic write to telemetry_latest.json
        temp_fd, temp_path = tempfile.mkstemp(dir=TELEMETRY_DIR, prefix="telemetry_", suffix=".tmp")
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(payload_dicts, f, indent=2)
            try:
                os.replace(temp_path, LATEST_TELEMETRY_FILE)
            except OSError:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

        # Historical recording (configurable & OFF by default)
        if enable_history is None:
            enable_history = os.getenv("ENABLE_HISTORICAL_TELEMETRY", "false").lower() in ("true", "1", "yes")

        if enable_history and len(payload_dicts) > 0:
            now = time.time()
            tick = payload_dicts[0].get("simulation_tick", 0)

            if now - _last_history_save_time >= history_interval_sec:
                os.makedirs(HISTORY_DIR, exist_ok=True)
                hist_filename = f"telemetry_{tick:06d}.json"
                hist_filepath = os.path.join(HISTORY_DIR, hist_filename)

                h_temp_fd, h_temp_path = tempfile.mkstemp(dir=HISTORY_DIR, prefix="hist_", suffix=".tmp")
                try:
                    with os.fdopen(h_temp_fd, 'w', encoding='utf-8') as f:
                        json.dump(payload_dicts, f, indent=2)
                    os.replace(h_temp_path, hist_filepath)
                    _last_history_save_time = now
                    _last_history_save_tick = tick
                except Exception:
                    if os.path.exists(h_temp_path):
                        os.remove(h_temp_path)
                    raise
    except Exception as err:
        logger.error(f"[TELEMETRY DISK PERSISTENCE FAILURE] Failed to write telemetry to disk: {err}")


# 5x5 Grid geometry constants
GRID_ROWS = 5
GRID_COLS = 5
TOTAL_NODES = GRID_ROWS * GRID_COLS  # 25 nodes (0..24)

GRID_SPACING = 300.0  # meters between adjacent grid intersections
GRID_START_X = -600.0
GRID_START_Y = 600.0
INFLUENCE_RADIUS = 50.0  # meters detection range for junction queue calculation
QUEUE_SPEED_THRESHOLD = 1.0  # m/s below which a vehicle is counted in queue


class NodeState:
    """Internal state tracking for a single 5x5 grid intersection node."""
    def __init__(self, node_id: int):
        self.node_id = node_id
        self.row = node_id // GRID_COLS
        self.col = node_id % GRID_COLS
        self.pos_x = GRID_START_X + self.col * GRID_SPACING
        self.pos_y = GRID_START_Y - self.row * GRID_SPACING

        # Signal state
        self.light_phase: str = "NS_GREEN" if (self.row + self.col) % 2 == 0 else "EW_GREEN"
        self.active_direction: str = "NS" if "NS" in self.light_phase else "EW"
        self.phase_remaining_ticks: int = 15
        self.phase_duration: int = 15

        # Queue tracking
        self.queue_length: int = 0
        self.flush_time: float = 0.0

        # Preemption state
        self.preemption_active: bool = False
        self.reserved_axis: Optional[str] = None
        self.reservation_ev_id: Optional[str] = None
        self.reservation_remaining_ticks: int = 0
        self.reservation_end_time: Optional[float] = None
        self.preempted_from_phase: Optional[str] = None
        self.preempted_from_direction: Optional[str] = None
        self.reservation_control_ready: bool = True

    def step_signal(self):
        """Advances signal phase timer by 1 tick if not preempted."""
        if self.preemption_active:
            if self.reservation_remaining_ticks > 0:
                self.reservation_remaining_ticks -= 1
                if self.reservation_remaining_ticks <= 0:
                    self.clear_preemption()
            return

        self.phase_remaining_ticks -= 1
        if self.phase_remaining_ticks <= 0:
            if self.light_phase == "NS_GREEN":
                self.light_phase = "YELLOW"
                self.active_direction = "NS"
                self.phase_remaining_ticks = 3
            elif self.light_phase == "YELLOW" and self.active_direction == "NS":
                self.light_phase = "EW_GREEN"
                self.active_direction = "EW"
                self.phase_remaining_ticks = 15
            elif self.light_phase == "EW_GREEN":
                self.light_phase = "YELLOW"
                self.active_direction = "EW"
                self.phase_remaining_ticks = 3
            elif self.light_phase == "YELLOW" and self.active_direction == "EW":
                self.light_phase = "NS_GREEN"
                self.active_direction = "NS"
                self.phase_remaining_ticks = 15

    def apply_preemption(self, ev_id: str, axis: str, duration_ticks: int = 20):
        """Applies emergency vehicle signal priority override."""
        if not self.preemption_active:
            self.preempted_from_phase = self.light_phase
            self.preempted_from_direction = self.active_direction

        self.preemption_active = True
        self.reserved_axis = axis.upper()
        self.reservation_ev_id = ev_id
        self.reservation_remaining_ticks = duration_ticks
        self.reservation_end_time = round(time.time() + duration_ticks * 0.5, 2)

        # Immediate priority phase
        self.light_phase = f"{self.reserved_axis}_GREEN"
        self.active_direction = self.reserved_axis
        self.phase_remaining_ticks = duration_ticks

    def clear_preemption(self):
        """Restores normal signal cycling post emergency clearance."""
        self.preemption_active = False
        self.reserved_axis = None
        self.reservation_ev_id = None
        self.reservation_remaining_ticks = 0
        self.reservation_end_time = None
        
        # Restore pre-interruption direction/phase
        restored_phase = self.preempted_from_phase or "NS_GREEN"
        restored_dir = self.preempted_from_direction or "NS"
        self.light_phase = restored_phase
        self.active_direction = restored_dir
        self.phase_remaining_ticks = 10
        self.preempted_from_phase = None
        self.preempted_from_direction = None


class TelemetryEngine:
    """
    Webots 25-Node Telemetry Engine.
    Collects physical vehicle states, tracks signal phases, detects queues, builds and validates payload.
    """
    def __init__(self):
        self.nodes: Dict[int, NodeState] = {i: NodeState(i) for i in range(TOTAL_NODES)}
        self.simulation_tick: int = 0
        self.last_generated_at: float = time.time()

    def get_node_id_for_position(self, x: float, y: float) -> int:
        """Finds nearest grid node (0..24) for a given (x,y) simulation coordinate."""
        col = max(0, min(GRID_COLS - 1, int(round((x - GRID_START_X) / GRID_SPACING))))
        row = max(0, min(GRID_ROWS - 1, int(round((GRID_START_Y - y) / GRID_SPACING))))
        return row * GRID_COLS + col

    def step(self, vehicle_states: Optional[List[Dict[str, Any]]] = None):
        """Advances simulation tick and updates all 25 node states from vehicle metrics."""
        self.simulation_tick += 1
        now = time.time()

        # Reset queues
        for node in self.nodes.values():
            node.queue_length = 0
            node.step_signal()

        # Dynamic queue calculation from actual vehicle positions
        if vehicle_states:
            for v in vehicle_states:
                vx = v.get("x", 0.0)
                vy = v.get("y", 0.0)
                v_speed = v.get("speed", 0.0)

                # Check proximity to all 25 nodes
                for node_id, node in self.nodes.items():
                    dist = math.hypot(vx - node.pos_x, vy - node.pos_y)
                    if dist <= INFLUENCE_RADIUS:
                        if v_speed <= QUEUE_SPEED_THRESHOLD or dist <= 25.0:
                            node.queue_length += 1

        # Calculate explainable clearance flush_time per node
        for node in self.nodes.values():
            # Baseline discharge rate: ~2.5 seconds per queued vehicle + phase penalty if waiting on red
            phase_delay = 0.0 if node.light_phase in ["NS_GREEN", "EW_GREEN"] else 3.0
            node.flush_time = round(node.queue_length * 2.5 + phase_delay, 1)

    def apply_signal_priority(self, node_id: int, ev_id: str, axis: str, duration_ticks: int = 20):
        """Applies preemption command to target node."""
        if node_id in self.nodes:
            self.nodes[node_id].apply_preemption(ev_id, axis, duration_ticks)
            logger.info(f"[TELEMETRY] Node {node_id} preempted for EV '{ev_id}' on axis '{axis.upper()}'")

    def generate_payload(self, save_to_disk: bool = True) -> List[Dict[str, Any]]:
        """
        Generates and validates the complete 25-node telemetry payload array.
        Returns validated JSON-serializable list of 25 node dictionaries.
        Optionally persists to disk as telemetry_latest.json atomically.
        """
        now = time.time()
        raw_nodes = []

        for node_id in range(TOTAL_NODES):
            n = self.nodes[node_id]
            record = {
                "node": n.node_id,
                "queue_length": n.queue_length,
                "flush_time": float(n.flush_time),
                "light_phase": n.light_phase,
                "active_direction": n.active_direction,
                "phase_remaining_ticks": n.phase_remaining_ticks,
                "preemption_active": n.preemption_active,
                "reserved_axis": n.reserved_axis,
                "reservation_ev_id": n.reservation_ev_id,
                "reservation_remaining_ticks": n.reservation_remaining_ticks,
                "reservation_end_time": n.reservation_end_time,
                "preempted_from_phase": n.preempted_from_phase,
                "preempted_from_direction": n.preempted_from_direction,
                "reservation_control_ready": n.reservation_control_ready,
                "simulation_tick": self.simulation_tick,
                "generated_at": round(now, 2)
            }
            raw_nodes.append(record)

        # STRICT SCHEMA VALIDATION
        try:
            payload = TelemetryPayload(nodes=[IntersectionTelemetry(**r) for r in raw_nodes])
            validated_dicts = [node.model_dump() for node in payload.nodes]
            if save_to_disk:
                save_telemetry_to_disk(validated_dicts)
            return validated_dicts
        except Exception as err:
            logger.error(f"[TELEMETRY VALIDATION FAILURE] Payload rejected: {err}")
            raise ValueError(f"Telemetry schema validation failed: {err}")


# Global Telemetry Engine Instance
telemetry_engine = TelemetryEngine()
