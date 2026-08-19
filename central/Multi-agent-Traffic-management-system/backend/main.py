"""FastAPI orchestration service for the live emergency-routing application.

The browser never connects to MQTT directly. Instead, the intersection edge
simulator publishes a retained 25-node snapshot to Mosquitto, this service
validates and stores it, then exposes role-gated HTTP/WebSocket APIs to the
React application.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import os
import random
import threading
import time
import uuid
from dataclasses import dataclass
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Callable

import networkx as nx
import numpy as np
import torch
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from psycopg2 import Error as PsycopgError
from psycopg2.extras import RealDictCursor

try:
    import paho.mqtt.client as mqtt
except ImportError:  # Allows a useful health status before dependencies are set up.
    mqtt = None  # type: ignore[assignment]

from .auth import CurrentUser, decode_access_token, get_current_user, router as auth_router
from .database import get_db

load_dotenv()
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

GRID_SIZE = 5
NODE_COUNT = GRID_SIZE * GRID_SIZE
# Stable human-readable labels for the 5×5 demo city. Numeric IDs remain the
# MQTT/API identity, while the dashboards show these names to operators.
NODE_NAMES = (
    "North Gate", "North Market", "University", "North Park", "East Gate",
    "West Market", "Civic Centre", "Hospital District", "Museum Row", "East Market",
    "River West", "Central Square", "Medical HQ", "City Hall", "River East",
    "South Market", "Stadium", "Tech Park", "Garden Junction", "South East",
    "West Depot", "Old Town", "Transit Hub", "Lakeside Medical Centre", "South Gate",
)
TRAFFIC_TOPIC = "city/intersections/update"
RESERVATION_REQUEST_TOPIC = "city/intersections/reserve"
RESERVATION_RESPONSE_TOPIC = "city/intersections/reserve/response"
# A cancellation topic is intentionally separate from a new reservation
# request.  It lets a replan clear only its own future bookings and makes a
# cancellation that arrives before a delayed QoS-1 request safe to honour.
RESERVATION_CANCEL_TOPIC = "city/intersections/reserve/cancel"
MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1").strip()
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883").strip())
MQTT_TRANSPORT = os.getenv("MQTT_TRANSPORT", "tcp").strip().lower()
MQTT_WS_PATH = os.getenv("MQTT_WS_PATH", "/mqtt").strip()
TRAFFIC_STALE_AFTER_SECONDS = float(os.getenv("TRAFFIC_STALE_AFTER_SECONDS", "8").strip())
UPDATE_INTERVAL_SECONDS = float(os.getenv("TRAFFIC_WS_INTERVAL_SECONDS", "1").strip())


def read_bool_env(name: str, default: bool = False) -> bool:
    """Read a CMD-friendly boolean setting with a clear configuration error."""
    value = os.getenv(name, str(default)).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of 1/0, true/false, yes/no, or on/off.")


def read_positive_int_env(name: str, default: int) -> int:
    """Read a positive integer while keeping CMD configuration errors clear."""
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer, got {raw_value!r}.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {raw_value!r}.")
    return value


def read_positive_float_env(name: str, default: float) -> float:
    """Read a positive finite duration from an environment variable."""
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number, got {raw_value!r}.") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive number, got {raw_value!r}.")
    return value


# The real simulator is the default. Set TRAFFIC_DEMO_MODE=1 only for a local
# visual demo when MQTT is deliberately unavailable.
TRAFFIC_DEMO_MODE = read_bool_env("TRAFFIC_DEMO_MODE")

# Reservations model the short time an ambulance occupies an intersection,
# rather than reserving an entire road link.  The edge agent owns FCFS
# arbitration; these settings only control the backend's forward lookahead.
RESERVATION_HORIZON_SECONDS = read_positive_int_env("RESERVATION_HORIZON_SECONDS", 120)
RESERVATION_WINDOW_SECONDS = read_positive_int_env("RESERVATION_WINDOW_SECONDS", 4)
RESERVATION_LEAD_SECONDS = read_positive_int_env("RESERVATION_LEAD_SECONDS", 2)
RESERVATION_ACK_TIMEOUT_SECONDS = read_positive_float_env(
    "RESERVATION_ACK_TIMEOUT_SECONDS", 2.5
)
# MQTT QoS 1 guarantees broker delivery, but a non-retained command can still
# arrive during the few milliseconds before a reconnecting edge agent receives
# its subscription acknowledgement. Re-publishing the same correlation IDs is
# safe because the edge reservation manager treats it as idempotent.
RESERVATION_ACK_ATTEMPTS = read_positive_int_env("RESERVATION_ACK_ATTEMPTS", 2)
RESERVATION_MAX_REROUTES = read_positive_int_env("RESERVATION_MAX_REROUTES", 3)
RESERVATION_CONFLICT_DELAY_SECONDS = read_positive_int_env(
    "RESERVATION_CONFLICT_DELAY_SECONDS", 4
)
if RESERVATION_WINDOW_SECONDS > RESERVATION_HORIZON_SECONDS:
    raise ValueError("RESERVATION_WINDOW_SECONDS cannot exceed RESERVATION_HORIZON_SECONDS.")
if RESERVATION_LEAD_SECONDS >= RESERVATION_HORIZON_SECONDS:
    raise ValueError("RESERVATION_LEAD_SECONDS must be shorter than RESERVATION_HORIZON_SECONDS.")


def movement_axis(source: int, destination: int) -> str:
    """Return the signal axis required to travel from one grid node to another."""
    source_row, source_column = divmod(source, GRID_SIZE)
    destination_row, destination_column = divmod(destination, GRID_SIZE)
    if source_column == destination_column and abs(source_row - destination_row) == 1:
        return "NS"
    if source_row == destination_row and abs(source_column - destination_column) == 1:
        return "EW"
    raise ValueError(f"Intersections {source} and {destination} are not adjacent.")


def build_city_graph() -> nx.DiGraph:
    """Build directed roads so source-signal delay can affect each movement."""
    coordinate_graph = nx.grid_2d_graph(GRID_SIZE, GRID_SIZE)
    grid = nx.convert_node_labels_to_integers(coordinate_graph, ordering="sorted")
    graph = nx.DiGraph()
    graph.add_nodes_from(grid.nodes)
    for first, second in grid.edges:
        for source, destination in ((first, second), (second, first)):
            graph.add_edge(
                source,
                destination,
                movement_axis=movement_axis(source, destination),
                weight=6.0,
                congestion_cost=6.0,
                signal_delay=0.0,
            )
    return graph


def normalized_adjacency(graph: nx.DiGraph) -> torch.Tensor:
    """Compute D^-1/2 (A + I) D^-1/2 for lightweight STGNN inference."""
    adjacency = nx.to_numpy_array(graph, nodelist=range(NODE_COUNT), dtype=np.float32)
    adjacency += np.eye(NODE_COUNT, dtype=np.float32)
    degrees = adjacency.sum(axis=1)
    inverse_sqrt_degree = np.divide(
        1.0,
        np.sqrt(degrees),
        out=np.zeros_like(degrees),
        where=degrees > 0,
    )
    normalized = inverse_sqrt_degree[:, None] * adjacency * inverse_sqrt_degree[None, :]
    return torch.from_numpy(normalized)


def congestion_color(flush_time: float) -> str:
    """Map the predicted clearing time to the three dashboard legend colours."""
    if flush_time >= 18:
        return "#ef4444"
    if flush_time >= 10:
        return "#f59e0b"
    return "#22c55e"


class SpectralSTGNN(torch.nn.Module):
    """Small spatial-temporal inference layer used to smooth live telemetry."""

    def __init__(self, weight_matrix: torch.Tensor) -> None:
        super().__init__()
        self.register_buffer("weight_matrix", weight_matrix.float())

    def forward(
        self,
        current_observation: torch.Tensor,
        previous_observation: torch.Tensor,
        adjacency_hat: torch.Tensor,
    ) -> torch.Tensor:
        temporal_signal = (0.75 * current_observation) + (0.25 * previous_observation)
        return torch.relu((adjacency_hat @ temporal_signal) @ self.weight_matrix)


def load_stgnn_weights() -> torch.Tensor:
    """Load trained weights when present, with a deterministic safe fallback."""
    default_path = Path(__file__).resolve().parents[1] / "ML_Pipeline" / "stgnn_weights.pt"
    weights_path = Path(os.getenv("STGNN_WEIGHTS_PATH", str(default_path)))
    try:
        checkpoint = torch.load(weights_path, map_location="cpu")
        weight_matrix = checkpoint["weight_matrix"].float()
        if tuple(weight_matrix.shape) != (NODE_COUNT, NODE_COUNT):
            raise ValueError("STGNN weight matrix must have shape (25, 25).")
        return weight_matrix
    except (FileNotFoundError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return torch.eye(NODE_COUNT, dtype=torch.float32)


class TrafficUnavailableError(ValueError):
    """Raised when routing would use missing or stale live telemetry."""


class TrafficGraphService:
    """Thread-safe live traffic state, signal-aware costs, and A* routing."""

    def __init__(self) -> None:
        self.graph = build_city_graph()
        self.adjacency_hat = normalized_adjacency(self.graph)
        self.model = SpectralSTGNN(load_stgnn_weights()).eval()
        self.lock = threading.RLock()
        self.random = random.Random()
        self.observed_flush_times = np.full(NODE_COUNT, 5.0, dtype=np.float32)
        self.previous_observation = torch.from_numpy(self.observed_flush_times.copy())
        self.queue_lengths = {node: 0 for node in range(NODE_COUNT)}
        self.light_phases = {node: "NS_GREEN" for node in range(NODE_COUNT)}
        self.active_directions = {node: "NS" for node in range(NODE_COUNT)}
        self.phase_remaining_ticks = {node: 15 for node in range(NODE_COUNT)}
        # Additive telemetry from the reservation-aware edge controller.
        # Keeping it separate from phase state lets an admin tell a scheduled
        # emergency green wave from an ordinary green signal.
        self.preemption_active = {node: False for node in range(NODE_COUNT)}
        self.reserved_axes: dict[int, str | None] = {node: None for node in range(NODE_COUNT)}
        self.reservation_ev_ids: dict[int, str | None] = {
            node: None for node in range(NODE_COUNT)
        }
        self.reservation_remaining_ticks = {node: 0 for node in range(NODE_COUNT)}
        self.reservation_end_times: dict[int, int | None] = {
            node: None for node in range(NODE_COUNT)
        }
        self.preempted_from_phases: dict[int, str | None] = {
            node: None for node in range(NODE_COUNT)
        }
        self.preempted_from_directions: dict[int, str | None] = {
            node: None for node in range(NODE_COUNT)
        }
        # Per-node heartbeats let the orchestrator isolate one silent
        # intersection instead of treating the entire city as an opaque feed.
        self.DEAD_NODE_TIMEOUT = 10.0
        now = time.time()
        self.last_seen = {node: now for node in range(NODE_COUNT)}
        # The admin dashboard can use this set to exercise the exact same
        # graph-surgery path as a missing edge heartbeat.
        self.manual_offline_nodes: set[int] = set()
        self.reservation_control_ready = False
        self.predicted_flush_times = {node: 5.0 for node in range(NODE_COUNT)}
        self.last_update_at: float | None = None
        self.source_generated_at: float | None = None
        self.simulation_tick: int | None = None
        self.traffic_version = 0
        self.mqtt_connected = False
        self.mqtt_error: str | None = None
        self.ingest_error: str | None = None
        self.source = "awaiting_mqtt"
        self._apply_prediction_locked(torch.from_numpy(self.observed_flush_times.copy()))

    def _dead_nodes_locked(self, now: float | None = None) -> set[int]:
        """Return manually failed and heartbeat-expired intersections."""
        current_time = time.time() if now is None else now
        timed_out_nodes = {
            node
            for node, last_seen in self.last_seen.items()
            if current_time - last_seen > self.DEAD_NODE_TIMEOUT
        }
        return timed_out_nodes | self.manual_offline_nodes

    def _prune_dead_nodes(self) -> None:
        """Make incoming travel into failed intersections impossible.

        The graph remains structurally stable for the simulator and dashboard;
        A* additionally receives a node-filtered view below.  Storing infinity
        on the incoming arcs preserves the failure state for diagnostics and
        any consumer that reads the raw graph weights directly.
        """
        for dead_node in self._dead_nodes_locked():
            for predecessor in self.graph.predecessors(dead_node):
                edge = self.graph[predecessor][dead_node]
                edge["weight"] = float("inf")
                edge["traffic_delay_seconds"] = float("inf")
                edge["congestion_cost"] = float("inf")
                edge["signal_delay"] = float("inf")

    def set_manual_offline(self, node: int, offline: bool) -> dict[str, Any]:
        """Toggle one dashboard-requested black-node simulation safely."""
        if node not in self.graph:
            raise ValueError("Intersection IDs must be integers from 0 through 24.")
        with self.lock:
            if offline:
                self.manual_offline_nodes.add(node)
            else:
                self.manual_offline_nodes.discard(node)
                # A restore represents a recovered local heartbeat; the next
                # MQTT snapshot will subsequently provide its fresh telemetry.
                self.last_seen[node] = time.time()
            self._refresh_directed_costs_locked()
            self._prune_dead_nodes()
            self.traffic_version += 1
            return {
                "node": node,
                "offline": node in self._dead_nodes_locked(),
                "offline_nodes": sorted(self._dead_nodes_locked()),
            }

    @staticmethod
    def _fallback_queue_length(flush_time: float) -> int:
        """Support a legacy publisher that contains only ``flush_time``."""
        return max(0, min(40, round((flush_time - 2.0) / 0.8)))

    @staticmethod
    def _phase_details(
        record: dict[str, Any],
        node: int,
        previous_phase: str,
        previous_direction: str,
        previous_remaining: int,
    ) -> tuple[str, str, int]:
        phase = str(record.get("light_phase", previous_phase))
        if phase not in {"NS_GREEN", "EW_GREEN", "YELLOW"}:
            raise ValueError(f"node {node} has an invalid light_phase: {phase!r}")
        direction = str(record.get("active_direction", previous_direction))
        if phase == "NS_GREEN":
            direction = "NS"
        elif phase == "EW_GREEN":
            direction = "EW"
        elif direction not in {"NS", "EW"}:
            raise ValueError(f"node {node} must provide active_direction during YELLOW")
        phase_duration = 3 if phase == "YELLOW" else 15
        raw_remaining = record.get("phase_remaining_ticks", previous_remaining)
        try:
            remaining = int(raw_remaining)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"node {node} has invalid phase_remaining_ticks") from exc
        if not 0 <= remaining <= phase_duration:
            raise ValueError(
                f"node {node} phase_remaining_ticks must be between 0 and {phase_duration}"
            )
        return phase, direction, remaining

    @staticmethod
    def _signal_wait_seconds(
        phase: str,
        active_direction: str,
        remaining_ticks: int,
        requested_axis: str,
    ) -> float:
        """Estimate the delay at a source intersection for an outbound movement."""
        if requested_axis == active_direction:
            return 2.0 if phase == "YELLOW" else 0.0
        if phase == "YELLOW":
            return float(remaining_ticks)
        return float(remaining_ticks + 3)

    @staticmethod
    def _preemption_details(
        record: dict[str, Any], node: int
    ) -> tuple[bool, str | None, str | None, int, int | None, str | None, str | None]:
        """Validate optional emergency-window fields from the edge agent."""
        active = record.get("preemption_active", False)
        if not isinstance(active, bool):
            raise ValueError(f"node {node} preemption_active must be a boolean")
        if not active:
            return False, None, None, 0, None, None, None
        axis = record.get("reserved_axis")
        ev_id = record.get("reservation_ev_id")
        end_time = record.get("reservation_end_time")
        try:
            remaining = int(record.get("reservation_remaining_ticks", 0))
            parsed_end_time = int(end_time)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"node {node} has invalid reservation timing") from exc
        if axis not in {"NS", "EW"} or not isinstance(ev_id, str) or not ev_id:
            raise ValueError(f"node {node} has incomplete active reservation metadata")
        if remaining < 0 or parsed_end_time < 0:
            raise ValueError(f"node {node} has invalid active reservation timing")
        previous_phase = record.get("preempted_from_phase")
        previous_direction = record.get("preempted_from_direction")
        if previous_phase is not None and previous_phase not in {"NS_GREEN", "EW_GREEN", "YELLOW"}:
            raise ValueError(f"node {node} has invalid preempted_from_phase")
        if previous_direction is not None and previous_direction not in {"NS", "EW"}:
            raise ValueError(f"node {node} has invalid preempted_from_direction")
        return (
            True,
            str(axis),
            ev_id,
            remaining,
            parsed_end_time,
            None if previous_phase is None else str(previous_phase),
            None if previous_direction is None else str(previous_direction),
        )

    @staticmethod
    def _reservation_control_ready(record: dict[str, Any], node: int) -> bool:
        """Validate the edge capability marker without breaking old payload parsing."""
        ready = record.get("reservation_control_ready", False)
        if not isinstance(ready, bool):
            raise ValueError(f"node {node} reservation_control_ready must be a boolean")
        return ready

    def _apply_prediction_locked(self, observation: torch.Tensor) -> None:
        """Run STGNN inference and update directed road costs while holding the lock."""
        with torch.no_grad():
            prediction = self.model(observation, self.previous_observation, self.adjacency_hat)
        flush_times = prediction.clamp(min=1.0, max=40.0).tolist()
        self.previous_observation = observation.clone()
        self.predicted_flush_times = {
            node: round(float(flush_time), 1) for node, flush_time in enumerate(flush_times)
        }
        self._refresh_directed_costs_locked()
        self._prune_dead_nodes()

    def _refresh_directed_costs_locked(self) -> None:
        """Use congestion and current source signal state for every directed road."""
        for source, destination, edge in self.graph.edges(data=True):
            source_queue_delay = min(
                12.0,
                (0.30 * self.queue_lengths[source])
                + (0.20 * self.predicted_flush_times[source]),
            )
            receiving_penalty = min(
                5.0,
                (0.12 * self.queue_lengths[destination])
                + (0.08 * self.predicted_flush_times[destination]),
            )
            signal_delay = self._signal_wait_seconds(
                self.light_phases[source],
                self.active_directions[source],
                self.phase_remaining_ticks[source],
                str(edge["movement_axis"]),
            )
            congestion_cost = 6.0 + source_queue_delay + receiving_penalty
            edge["congestion_cost"] = round(congestion_cost, 1)
            edge["signal_delay"] = round(signal_delay, 1)
            edge["traffic_delay_seconds"] = round(signal_delay, 1)
            edge["weight"] = round(congestion_cost + signal_delay, 1)

    def set_mqtt_status(self, connected: bool, error: str | None = None) -> None:
        """Record MQTT lifecycle state for the health endpoint and dashboard."""
        with self.lock:
            self.mqtt_connected = connected
            self.mqtt_error = error

    def record_ingest_error(self, error: str) -> None:
        """Keep an invalid payload from silently appearing as healthy live data."""
        with self.lock:
            self.ingest_error = error

    def ingest_snapshot(self, records: list[dict[str, Any]], *, source: str = "mqtt") -> bool:
        """Atomically validate and merge one simulator snapshot.

        The normal edge agent publishes all 25 nodes together.  Accepting a
        partial snapshot as well is important for the watchdog: healthy nodes
        can continue refreshing their heartbeats while one failed intersection
        naturally expires from ``last_seen``.

        Returns ``False`` for a retained QoS-1 redelivery of the same snapshot.
        """
        if not records or len(records) > NODE_COUNT:
            raise ValueError(f"traffic snapshot must contain from 1 through {NODE_COUNT} records")
        incoming_nodes: set[int] = set()
        parsed: dict[
            int,
            tuple[
                int, float, str, str, int, bool, str | None, str | None, int, int | None,
                str | None, str | None, bool,
            ],
        ] = {}
        source_ticks: set[int] = set()
        source_times: set[float] = set()
        control_ready_values: set[bool] = set()
        with self.lock:
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError("traffic snapshot records must be JSON objects")
                try:
                    node = int(record["node"])
                    flush_time = float(record["flush_time"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError("each traffic record requires numeric node and flush_time") from exc
                if node not in self.graph or node in incoming_nodes:
                    raise ValueError(f"traffic snapshot contains invalid or duplicate node {node}")
                self.last_seen[node] = time.time()
                if not np.isfinite(flush_time) or not 1.0 <= flush_time <= 40.0:
                    raise ValueError(f"node {node} flush_time must be within 1..40")
                try:
                    queue_length = int(
                        record.get("queue_length", self._fallback_queue_length(flush_time))
                    )
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"node {node} has invalid queue_length") from exc
                if not 0 <= queue_length <= 40:
                    raise ValueError(f"node {node} queue_length must be within 0..40")
                phase, direction, remaining = self._phase_details(
                    record,
                    node,
                    self.light_phases[node],
                    self.active_directions[node],
                    self.phase_remaining_ticks[node],
                )
                (
                    preemption_active,
                    reserved_axis,
                    reservation_ev_id,
                    reservation_remaining_ticks,
                    reservation_end_time,
                    preempted_from_phase,
                    preempted_from_direction,
                ) = self._preemption_details(record, node)
                reservation_control_ready = self._reservation_control_ready(record, node)
                control_ready_values.add(reservation_control_ready)
                incoming_nodes.add(node)
                parsed[node] = (
                    queue_length,
                    flush_time,
                    phase,
                    direction,
                    remaining,
                    preemption_active,
                    reserved_axis,
                    reservation_ev_id,
                    reservation_remaining_ticks,
                    reservation_end_time,
                    preempted_from_phase,
                    preempted_from_direction,
                    reservation_control_ready,
                )
                try:
                    if "simulation_tick" in record:
                        tick = int(record["simulation_tick"])
                        if tick < 0:
                            raise ValueError
                        source_ticks.add(tick)
                    if "generated_at" in record:
                        generated_at = float(record["generated_at"])
                        if not np.isfinite(generated_at):
                            raise ValueError
                        source_times.add(generated_at)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"node {node} has invalid snapshot metadata") from exc
            if len(source_ticks) > 1 or len(source_times) > 1:
                raise ValueError("all records must have matching simulation_tick and generated_at")
            if len(control_ready_values) > 1:
                raise ValueError("all records must have matching reservation_control_ready")
            incoming_generated_at = next(iter(source_times), time.time())
            if (
                self.source_generated_at is not None
                and incoming_generated_at < self.source_generated_at
            ):
                raise ValueError("received an out-of-order traffic snapshot")
            if self.source_generated_at is not None and incoming_generated_at == self.source_generated_at:
                return False
            for (
                node,
                (
                    queue_length,
                    flush_time,
                    phase,
                    direction,
                    remaining,
                    preemption_active,
                    reserved_axis,
                    reservation_ev_id,
                    reservation_remaining_ticks,
                    reservation_end_time,
                    preempted_from_phase,
                    preempted_from_direction,
                    reservation_control_ready,
                ),
            ) in parsed.items():
                self.queue_lengths[node] = queue_length
                self.observed_flush_times[node] = flush_time
                self.light_phases[node] = phase
                self.active_directions[node] = direction
                self.phase_remaining_ticks[node] = remaining
                self.preemption_active[node] = preemption_active
                self.reserved_axes[node] = reserved_axis
                self.reservation_ev_ids[node] = reservation_ev_id
                self.reservation_remaining_ticks[node] = reservation_remaining_ticks
                self.reservation_end_times[node] = reservation_end_time
                self.preempted_from_phases[node] = preempted_from_phase
                self.preempted_from_directions[node] = preempted_from_direction
            self.reservation_control_ready = next(
                iter(control_ready_values), self.reservation_control_ready
            )
            self._apply_prediction_locked(torch.from_numpy(self.observed_flush_times.copy()))
            self.last_update_at = time.time()
            self.source_generated_at = incoming_generated_at
            self.simulation_tick = next(iter(source_ticks), self.simulation_tick)
            self.traffic_version += 1
            self.source = source
            self.ingest_error = None
            return True

    def simulate_tick(self) -> None:
        """Optional development-only source, never enabled in normal operation."""
        with self.lock:
            queues = [
                max(0, min(40, queue + self.random.randint(-2, 3)))
                for queue in self.queue_lengths.values()
            ]
            timestamp = time.time()
            tick = (self.simulation_tick or 0) + 1
        records = [
            {
                "node": node,
                "queue_length": queue,
                "flush_time": max(1, min(40, round(2.0 + (queue * 0.8)))),
                "light_phase": "NS_GREEN",
                "active_direction": "NS",
                "phase_remaining_ticks": 15,
                "simulation_tick": tick,
                "generated_at": timestamp,
            }
            for node, queue in enumerate(queues)
        ]
        self.ingest_snapshot(records, source="demo")

    def _traffic_age_locked(self) -> float | None:
        timestamp = self.source_generated_at or self.last_update_at
        return None if timestamp is None else max(0.0, time.time() - timestamp)

    @staticmethod
    def _iso_timestamp(timestamp: float | None) -> str | None:
        if timestamp is None:
            return None
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()

    def status(self) -> dict[str, Any]:
        """Return non-sensitive liveness information for any authenticated user."""
        with self.lock:
            self._prune_dead_nodes()
            offline_nodes = self._dead_nodes_locked()
            age = self._traffic_age_locked()
            available = self.last_update_at is not None
            stale = not available or age is None or age > TRAFFIC_STALE_AFTER_SECONDS
            return {
                "mqtt_connected": self.mqtt_connected,
                "mqtt_error": self.mqtt_error,
                "traffic_available": available,
                "traffic_stale": stale,
                "traffic_age_seconds": None if age is None else round(age, 2),
                "traffic_version": self.traffic_version,
                "offline_nodes": sorted(offline_nodes),
                "offline_node_count": len(offline_nodes),
                "simulation_tick": self.simulation_tick,
                "active_preemptions": sum(self.preemption_active.values()),
                "reservation_control_ready": self.reservation_control_ready,
                "source": self.source,
                "generated_at": self._iso_timestamp(self.source_generated_at),
                "updated_at": self._iso_timestamp(self.last_update_at),
                "ingest_error": self.ingest_error,
            }

    def snapshot(self) -> dict[str, Any]:
        """Return JSON-safe graph data for the admin WebSocket and fallback API."""
        with self.lock:
            self._prune_dead_nodes()
            offline_nodes = self._dead_nodes_locked()
            age = self._traffic_age_locked()
            available = self.last_update_at is not None
            stale = not available or age is None or age > TRAFFIC_STALE_AFTER_SECONDS
            nodes = [
                {
                    "id": node,
                    "label": NODE_NAMES[node],
                    "queue_length": self.queue_lengths[node],
                    "observed_flush_time": round(float(self.observed_flush_times[node]), 1),
                    "flush_time": self.predicted_flush_times[node],
                    "light_phase": self.light_phases[node],
                    "active_direction": self.active_directions[node],
                    "phase_remaining_ticks": self.phase_remaining_ticks[node],
                    "preemption_active": self.preemption_active[node],
                    "reserved_axis": self.reserved_axes[node],
                    "reservation_ev_id": self.reservation_ev_ids[node],
                    "reservation_remaining_ticks": self.reservation_remaining_ticks[node],
                    "reservation_end_time": self.reservation_end_times[node],
                    "preempted_from_phase": self.preempted_from_phases[node],
                    "preempted_from_direction": self.preempted_from_directions[node],
                    "offline": node in offline_nodes,
                    # A neutral node is more honest than a green one before
                    # the first simulator snapshot has arrived.
                    "color": (
                        "#020617"
                        if node in offline_nodes
                        else congestion_color(self.predicted_flush_times[node])
                        if available
                        else "#94a3b8"
                    ),
                }
                for node in range(NODE_COUNT)
            ]
            edges: list[dict[str, Any]] = []
            for source, destination in self.graph.edges:
                if source > destination:
                    continue
                if source in offline_nodes or destination in offline_nodes:
                    continue
                forward = self.graph[source][destination]
                reverse = self.graph[destination][source]
                edges.append(
                    {
                        "source": source,
                        "target": destination,
                        "direction": forward["movement_axis"],
                        "weight": round((forward["weight"] + reverse["weight"]) / 2.0, 1),
                        "signal_delay": round(
                            (forward["signal_delay"] + reverse["signal_delay"]) / 2.0,
                            1,
                        ),
                        "congestion_cost": round(
                            (forward["congestion_cost"] + reverse["congestion_cost"]) / 2.0,
                            1,
                        ),
                    }
                )
            return {
                "nodes": nodes,
                "edges": edges,
                "source": self.source,
                "mqtt_connected": self.mqtt_connected,
                "mqtt_error": self.mqtt_error,
                "traffic_available": available,
                "traffic_stale": stale,
                "traffic_age_seconds": None if age is None else round(age, 2),
                "updated_at": self._iso_timestamp(self.last_update_at),
                "generated_at": self._iso_timestamp(self.source_generated_at),
                "simulation_tick": self.simulation_tick,
                "traffic_version": self.traffic_version,
                "offline_nodes": sorted(offline_nodes),
                "active_preemptions": sum(self.preemption_active.values()),
                "reservation_control_ready": self.reservation_control_ready,
                "ingest_error": self.ingest_error,
            }

    def find_route(
        self,
        start: int,
        end: int,
        *,
        excluded_nodes: set[int] | None = None,
    ) -> dict[str, Any]:
        """Run phase-aware A* against the newest valid MQTT telemetry.

        ``excluded_nodes`` is used only after an FCFS reservation denial.  It
        allows the orchestrator to try a genuinely different route without
        mutating the shared live graph or hiding a driver's current/destination
        node from A*.
        """
        if start not in self.graph or end not in self.graph:
            raise ValueError("Intersection IDs must be integers from 0 through 24.")
        with self.lock:
            age = self._traffic_age_locked()
            if self.last_update_at is None or age is None or age > TRAFFIC_STALE_AFTER_SECONDS:
                raise TrafficUnavailableError(
                    "Live traffic telemetry is unavailable or stale; start intersection_agent.py "
                    "and wait for a fresh 25-node MQTT snapshot."
                )
            if not self.reservation_control_ready:
                raise ReservationUnavailableError(
                    "The active traffic publisher is not ready for reservation commands. "
                    "Restart the updated intersection_agent.py and wait for its "
                    "'[reservation] Controller ready' message."
                )

            # Dynamic graph surgery occurs immediately before A*: dead nodes
            # receive infinite incoming costs and are removed from this route's
            # graph view so an all-infinite fallback path is never returned.
            self._prune_dead_nodes()
            offline_nodes = self._dead_nodes_locked()
            if start in offline_nodes or end in offline_nodes:
                raise ValueError("Current location or destination intersection is offline.")

            def manhattan_distance(left: int, right: int) -> float:
                left_row, left_column = divmod(left, GRID_SIZE)
                right_row, right_column = divmod(right, GRID_SIZE)
                return 6.0 * (abs(left_row - right_row) + abs(left_column - right_column))

            blocked_nodes = {
                node
                for node in (excluded_nodes or set())
                if node in self.graph and node not in {start, end}
            }
            blocked_nodes |= offline_nodes
            if blocked_nodes:
                routing_graph = nx.subgraph_view(
                    self.graph,
                    filter_node=lambda node: node not in blocked_nodes,
                )
            else:
                routing_graph = self.graph

            try:
                path = nx.astar_path(
                    routing_graph,
                    start,
                    end,
                    heuristic=manhattan_distance,
                    weight="weight",
                )
            except nx.NetworkXNoPath as exc:
                raise nx.NetworkXNoPath(
                    "No valid path exists (network partitioned)."
                ) from exc
            segments = [
                {
                    "from": source,
                    "to": destination,
                    "direction": self.graph[source][destination]["movement_axis"],
                    # Keep the two components explicit for the driver
                    # simulation: an EV waits at the source signal first,
                    # then spends this congestion-adjusted time on the road.
                    "road_travel_seconds": self.graph[source][destination]["congestion_cost"],
                    "signal_wait_seconds": self.graph[source][destination]["signal_delay"],
                    "travel_cost": self.graph[source][destination]["weight"],
                    "congestion_cost": self.graph[source][destination]["congestion_cost"],
                    "signal_delay": self.graph[source][destination]["signal_delay"],
                    "source_light_phase": self.light_phases[source],
                    "source_active_direction": self.active_directions[source],
                    "phase_remaining_ticks": self.phase_remaining_ticks[source],
                }
                for source, destination in zip(path, path[1:])
            ]
            eta_seconds = sum(float(segment["travel_cost"]) for segment in segments)
            return {
                "path": path,
                "eta_seconds": round(eta_seconds, 1),
                "segments": segments,
                "traffic_version": self.traffic_version,
                "traffic_age_seconds": round(age, 2),
                "traffic_source": self.source,
                "excluded_nodes": sorted(blocked_nodes),
                "generated_at": self._iso_timestamp(time.time()),
            }


class ReservationError(RuntimeError):
    """Base class for a reservation failure that must not move an EV blindly."""


class ReservationUnavailableError(ReservationError):
    """The MQTT control plane cannot safely accept a reservation."""


class ReservationTimeoutError(ReservationError):
    """The edge controller did not acknowledge a reservation in time."""


class ReservationCleanupError(ReservationError):
    """A prior booking could not be cancelled before a replacement route."""


class ReservationConflictError(ReservationError):
    """No FCFS-compatible route could be booked inside the retry budget."""


@dataclass(frozen=True)
class ReservationRequest:
    """One correlation-safe reservation sent to a single edge controller."""

    node: int
    ev_id: str
    axis: str
    start_time: int
    duration: int
    request_id: str
    reservation_id: str
    segment_index: int

    @property
    def response_key(self) -> tuple[str, int, int, int]:
        return (self.ev_id, self.node, self.start_time, self.duration)

    def payload(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "ev_id": self.ev_id,
            "axis": self.axis,
            "start_time": self.start_time,
            "duration": self.duration,
            "request_id": self.request_id,
            "reservation_id": self.reservation_id,
        }


@dataclass(frozen=True)
class ReservationAcknowledgement:
    """Validated MQTT response from the edge-side reservation manager."""

    node: int
    ev_id: str
    granted: bool
    start_time: int
    duration: int
    axis: str | None
    request_id: str | None
    reservation_id: str | None
    reason: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ReservationAcknowledgement":
        try:
            node = int(payload["node"])
            ev_id = str(payload["ev_id"])
            start_time = int(payload["start_time"])
            duration = int(payload["duration"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("reservation response is missing node, ev_id, start_time, or duration") from exc
        granted = payload.get("granted")
        if not isinstance(granted, bool):
            raise ValueError("reservation response granted must be a boolean")
        if node not in range(NODE_COUNT) or not ev_id or start_time < 0 or duration <= 0:
            raise ValueError("reservation response has invalid identifiers or timing")
        raw_axis = payload.get("axis", payload.get("direction"))
        axis = None if raw_axis is None else str(raw_axis)
        if axis not in {None, "NS", "EW"}:
            raise ValueError("reservation response axis must be NS or EW when present")
        return cls(
            node=node,
            ev_id=ev_id,
            granted=granted,
            start_time=start_time,
            duration=duration,
            axis=axis,
            request_id=(None if payload.get("request_id") is None else str(payload["request_id"])),
            reservation_id=(
                None if payload.get("reservation_id") is None else str(payload["reservation_id"])
            ),
            reason=None if payload.get("reason") is None else str(payload["reason"]),
        )


@dataclass(frozen=True)
class ReservationGrant:
    """A granted request retained so a later replan can cancel it exactly."""

    request: ReservationRequest
    acknowledgement: ReservationAcknowledgement

    def api_payload(self) -> dict[str, Any]:
        return {
            "node": self.request.node,
            "ev_id": self.request.ev_id,
            "axis": self.request.axis,
            "start_time": self.acknowledgement.start_time,
            "duration": self.acknowledgement.duration,
            "granted": True,
            "request_id": self.request.request_id,
            "reservation_id": (
                self.acknowledgement.reservation_id or self.request.reservation_id
            ),
        }


@dataclass
class _ReservationWaiter:
    request: ReservationRequest
    event: threading.Event
    acknowledgement: ReservationAcknowledgement | None = None
    error: str | None = None


class ReservationCoordinator:
    """Correlate MQTT acks without ever blocking Paho's callback thread.

    FCFS itself intentionally remains at the intersection agent: it is the
    single authority for a node's time line.  This coordinator serializes one
    driver's own replans and turns its MQTT acknowledgements into bounded
    asynchronous FastAPI work.
    """

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self._waiters: dict[str, _ReservationWaiter] = {}
        self._correlation_index: dict[str, str] = {}
        self._key_index: dict[tuple[str, int, int, int], set[str]] = {}
        self._active_by_ev: dict[str, list[ReservationGrant]] = {}
        self._ev_locks: dict[str, asyncio.Lock] = {}
        self.last_error: str | None = None
        self.last_response_at: float | None = None

    def ev_lock(self, ev_id: str) -> asyncio.Lock:
        """Return the in-process lock that prevents a driver's self-conflicts."""
        with self.lock:
            return self._ev_locks.setdefault(ev_id, asyncio.Lock())

    def _register(self, request: ReservationRequest) -> _ReservationWaiter:
        waiter = _ReservationWaiter(request=request, event=threading.Event())
        with self.lock:
            self._waiters[request.request_id] = waiter
            self._correlation_index[request.request_id] = request.request_id
            self._correlation_index[request.reservation_id] = request.request_id
            self._key_index.setdefault(request.response_key, set()).add(request.request_id)
        return waiter

    def _remove(self, waiter: _ReservationWaiter) -> None:
        request = waiter.request
        with self.lock:
            if self._waiters.get(request.request_id) is waiter:
                self._waiters.pop(request.request_id, None)
            for correlation in (request.request_id, request.reservation_id):
                if self._correlation_index.get(correlation) == request.request_id:
                    self._correlation_index.pop(correlation, None)
            request_ids = self._key_index.get(request.response_key)
            if request_ids is not None:
                request_ids.discard(request.request_id)
                if not request_ids:
                    self._key_index.pop(request.response_key, None)

    async def request(
        self,
        request: ReservationRequest,
        publish: Callable[[str, dict[str, Any]], None],
    ) -> ReservationAcknowledgement:
        """Publish a booking and await its matching ack for a finite time.

        The same request/reservation IDs are deliberately retried once by
        default.  This bridges the short MQTT reconnect window in which the
        broker accepts a QoS-1 command just before an edge client completes
        its subscription.  The edge manager treats the repeat as
        ``already_granted``, so it cannot create a second booking.
        """
        waiter = self._register(request)
        try:
            for attempt in range(1, RESERVATION_ACK_ATTEMPTS + 1):
                with self.lock:
                    acknowledgement = waiter.acknowledgement
                    error = waiter.error
                if error:
                    raise ReservationUnavailableError(error)
                if acknowledgement is not None:
                    return acknowledgement
                try:
                    publish(RESERVATION_REQUEST_TOPIC, request.payload())
                except ReservationError:
                    raise
                except Exception as exc:
                    raise ReservationUnavailableError(
                        f"Unable to publish reservation: {exc}"
                    ) from exc

                await asyncio.to_thread(waiter.event.wait, RESERVATION_ACK_TIMEOUT_SECONDS)
                with self.lock:
                    acknowledgement = waiter.acknowledgement
                    error = waiter.error
                if error:
                    raise ReservationUnavailableError(error)
                if acknowledgement is not None:
                    return acknowledgement

            timeout_message = (
                f"Intersection {request.node} did not acknowledge the reservation after "
                f"{RESERVATION_ACK_ATTEMPTS} attempt(s) of "
                f"{RESERVATION_ACK_TIMEOUT_SECONDS:.1f} seconds each."
            )
            with self.lock:
                self.last_error = timeout_message
            raise ReservationTimeoutError(timeout_message)
        finally:
            self._remove(waiter)

    def handle_response(self, payload: dict[str, Any]) -> bool:
        """Wake exactly one waiting HTTP request; unknown retained acks are ignored."""
        try:
            acknowledgement = ReservationAcknowledgement.from_payload(payload)
        except ValueError as exc:
            with self.lock:
                self.last_error = f"Invalid reservation response: {exc}"
            return False

        with self.lock:
            request_id: str | None = None
            for correlation in (acknowledgement.request_id, acknowledgement.reservation_id):
                if correlation and correlation in self._correlation_index:
                    request_id = self._correlation_index[correlation]
                    break
            if request_id is None:
                candidates = self._key_index.get(
                    (
                        acknowledgement.ev_id,
                        acknowledgement.node,
                        acknowledgement.start_time,
                        acknowledgement.duration,
                    ),
                    set(),
                )
                # The specified base protocol has no correlation ID.  Only use
                # that compatibility path when it is unambiguous.
                if len(candidates) == 1:
                    request_id = next(iter(candidates))
            waiter = self._waiters.get(request_id) if request_id else None
            if waiter is None:
                return False
            expected = waiter.request
            if (
                acknowledgement.ev_id != expected.ev_id
                or acknowledgement.node != expected.node
                or acknowledgement.start_time != expected.start_time
                or acknowledgement.duration != expected.duration
                or (acknowledgement.axis is not None and acknowledgement.axis != expected.axis)
                or (
                    acknowledgement.request_id is not None
                    and acknowledgement.request_id != expected.request_id
                )
                or (
                    acknowledgement.reservation_id is not None
                    and acknowledgement.reservation_id != expected.reservation_id
                )
            ):
                self.last_error = "Ignored reservation response with mismatched request fields."
                return False
            waiter.acknowledgement = acknowledgement
            self.last_response_at = time.time()
            self.last_error = None
            waiter.event.set()
            return True

    def fail_pending(self, reason: str) -> None:
        """Fail waiters promptly after an MQTT disconnect; never leave HTTP hanging."""
        with self.lock:
            self.last_error = reason
            for waiter in self._waiters.values():
                waiter.error = reason
                waiter.event.set()

    def record_error(self, error: str) -> None:
        """Store a non-fatal MQTT-control diagnostic under the same lock."""
        with self.lock:
            self.last_error = error

    def take_active(self, ev_id: str) -> list[ReservationGrant]:
        with self.lock:
            return self._active_by_ev.pop(ev_id, [])

    def store_active(self, ev_id: str, grants: list[ReservationGrant]) -> None:
        with self.lock:
            self._active_by_ev[ev_id] = grants

    def status(self) -> dict[str, Any]:
        with self.lock:
            return {
                "pending": len(self._waiters),
                "active": sum(len(grants) for grants in self._active_by_ev.values()),
                "last_error": self.last_error,
                "last_response_at": (
                    None
                    if self.last_response_at is None
                    else datetime.fromtimestamp(self.last_response_at, tz=UTC).isoformat()
                ),
            }


class MqttTrafficConsumer:
    """Owns the Paho network thread; callbacks only update locked backend state."""

    def __init__(
        self,
        traffic_service: TrafficGraphService,
        reservation_coordinator: ReservationCoordinator,
    ) -> None:
        self.traffic_service = traffic_service
        self.reservation_coordinator = reservation_coordinator
        self.client: Any | None = None
        self.started = False
        self._cancel_lock = threading.RLock()
        self._pending_cancellations: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _connection_failed(reason_code: Any) -> bool:
        return bool(getattr(reason_code, "is_failure", False))

    def start(self) -> None:
        if self.started:
            return
        if mqtt is None:
            self.traffic_service.set_mqtt_status(
                False, "paho-mqtt is not installed; run pip install -r requirements.txt"
            )
            return
        if MQTT_TRANSPORT not in {"tcp", "websockets"}:
            self.traffic_service.set_mqtt_status(
                False, "MQTT_TRANSPORT must be tcp or websockets"
            )
            return
        try:
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"traffic-api-{uuid.uuid4().hex[:8]}",
                protocol=mqtt.MQTTv311,
                transport=MQTT_TRANSPORT,
            )
            if MQTT_TRANSPORT == "websockets":
                client.ws_set_options(path=MQTT_WS_PATH)
            client.on_connect = self._on_connect
            client.on_connect_fail = self._on_connect_fail
            client.on_disconnect = self._on_disconnect
            client.on_message = self._on_message
            client.reconnect_delay_set(min_delay=1, max_delay=20)
            client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_start()
            self.client = client
            self.started = True
            self.traffic_service.set_mqtt_status(False, "Connecting to MQTT broker…")
        except Exception as exc:  # MQTT failure must not crash HTTP startup.
            self.traffic_service.set_mqtt_status(False, f"MQTT startup failed: {exc}")

    def stop(self) -> None:
        client = self.client
        self.client = None
        self.started = False
        if client is None:
            return
        with contextlib.suppress(Exception):
            client.loop_stop()
        with contextlib.suppress(Exception):
            client.disconnect()
        self.reservation_coordinator.fail_pending("MQTT consumer stopped before reservation ack.")
        self.traffic_service.set_mqtt_status(False)

    def _on_connect(
        self, client: Any, _userdata: Any, _flags: Any, reason_code: Any, _properties: Any
    ) -> None:
        if self._connection_failed(reason_code):
            error = f"MQTT connection failed: {reason_code}"
            self.reservation_coordinator.fail_pending(error)
            self.traffic_service.set_mqtt_status(False, error)
            return
        client.subscribe([(TRAFFIC_TOPIC, 1), (RESERVATION_RESPONSE_TOPIC, 1)])
        self.traffic_service.set_mqtt_status(True)
        self._flush_pending_cancellations()

    def _on_connect_fail(self, _client: Any, _userdata: Any) -> None:
        error = f"Cannot reach MQTT broker at {MQTT_BROKER}:{MQTT_PORT}; retrying automatically."
        self.reservation_coordinator.fail_pending(error)
        self.traffic_service.set_mqtt_status(
            False, error
        )

    def _on_disconnect(
        self,
        _client: Any,
        _userdata: Any,
        _disconnect_flags: Any,
        reason_code: Any,
        _properties: Any,
    ) -> None:
        if self._connection_failed(reason_code):
            error = f"MQTT disconnected: {reason_code}"
            self.reservation_coordinator.fail_pending(error)
            self.traffic_service.set_mqtt_status(False, error)
        else:
            self.reservation_coordinator.fail_pending("MQTT disconnected before reservation ack.")
            self.traffic_service.set_mqtt_status(False)

    def _on_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            if message.topic == TRAFFIC_TOPIC:
                if not isinstance(payload, list):
                    raise ValueError("traffic payload must be a JSON array")
                self.traffic_service.ingest_snapshot(payload)
            elif message.topic == RESERVATION_RESPONSE_TOPIC:
                if not isinstance(payload, dict):
                    raise ValueError("reservation response must be a JSON object")
                self.reservation_coordinator.handle_response(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            if message.topic == TRAFFIC_TOPIC:
                self.traffic_service.record_ingest_error(f"Invalid MQTT traffic snapshot: {exc}")
            else:
                self.reservation_coordinator.record_error(
                    f"Invalid MQTT reservation message: {exc}"
                )

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Queue a control message only when this client has a broker session."""
        client = self.client
        if mqtt is None or client is None or not self.started:
            raise ReservationUnavailableError("MQTT reservation client is not running.")
        try:
            connected = bool(client.is_connected())
        except Exception:
            connected = self.traffic_service.status()["mqtt_connected"]
        if not connected:
            raise ReservationUnavailableError("MQTT reservation client is disconnected.")
        try:
            result = client.publish(topic, json.dumps(payload), qos=1)
        except Exception as exc:
            raise ReservationUnavailableError(f"MQTT publish failed: {exc}") from exc
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ReservationUnavailableError(
                f"MQTT could not queue reservation message (status {result.rc})."
            )

    def publish_reservation(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish a request. Kept as a small callable for ReservationCoordinator."""
        self._publish(topic, payload)

    def cancel_reservation(self, reservation: ReservationGrant | ReservationRequest) -> bool:
        """Best-effort, idempotent cleanup for a replan or failed batch.

        If MQTT drops after a request, preserve the cancellation locally and
        send it first after reconnect.  The edge agent records cancelled IDs,
        so a delayed QoS-1 request cannot recreate a stale reservation.
        """
        request = reservation.request if isinstance(reservation, ReservationGrant) else reservation
        payload = request.payload()
        cancellation_key = request.reservation_id
        try:
            self._publish(RESERVATION_CANCEL_TOPIC, payload)
            return True
        except ReservationUnavailableError:
            with self._cancel_lock:
                self._pending_cancellations[cancellation_key] = payload
            return False

    def cancel_reservations(
        self, reservations: list[ReservationGrant | ReservationRequest]
    ) -> bool:
        """Attempt every cleanup so one failure does not strand other slots."""
        successful = True
        for reservation in reservations:
            successful = self.cancel_reservation(reservation) and successful
        return successful

    def _flush_pending_cancellations(self) -> None:
        with self._cancel_lock:
            pending = list(self._pending_cancellations.items())
        for cancellation_key, payload in pending:
            try:
                self._publish(RESERVATION_CANCEL_TOPIC, payload)
            except ReservationUnavailableError:
                return
            with self._cancel_lock:
                self._pending_cancellations.pop(cancellation_key, None)


traffic_graph = TrafficGraphService()
reservation_coordinator = ReservationCoordinator()
traffic_consumer = MqttTrafficConsumer(traffic_graph, reservation_coordinator)


class GridCoordinate(BaseModel):
    row: int = Field(ge=0, lt=GRID_SIZE)
    column: int = Field(ge=0, lt=GRID_SIZE)


class RouteRequest(BaseModel):
    # Integer IDs power the dashboard dropdown; coordinates also remain supported.
    start: int | GridCoordinate
    end: int | GridCoordinate


class RouteSegment(BaseModel):
    from_: int = Field(alias="from")
    to: int
    direction: str
    road_travel_seconds: float
    signal_wait_seconds: float
    travel_cost: float
    congestion_cost: float
    signal_delay: float
    source_light_phase: str
    source_active_direction: str
    phase_remaining_ticks: int
    # Present only when the segment is inside the active reservation horizon.
    reservation_start_time: int | None = None
    reservation_duration_seconds: int | None = None
    reservation_id: str | None = None
    reservation_status: str | None = None


class ReservationWindow(BaseModel):
    node: int = Field(ge=0, lt=NODE_COUNT)
    ev_id: str
    axis: str
    start_time: int
    duration: int = Field(gt=0)
    granted: bool
    request_id: str
    reservation_id: str


class RouteResponse(BaseModel):
    path: list[int]
    eta_seconds: float
    segments: list[RouteSegment]
    traffic_version: int
    traffic_age_seconds: float
    traffic_source: str
    generated_at: str
    ev_id: str | None = None
    reservation_status: str | None = None
    reservations: list[ReservationWindow] = Field(default_factory=list)
    reservation_attempts: int = 0
    reservation_horizon_limited: bool = False
    excluded_nodes: list[int] = Field(default_factory=list)


class RouteCancellationResponse(BaseModel):
    """Result of explicitly ending an EV trip from the driver dashboard."""

    ev_id: str
    cancelled_reservations: int = Field(ge=0)
    status: str


class EnvironmentalHeatmapPoint(BaseModel):
    """One physical intersection enriched with its live traffic queue."""

    node_id: int = Field(ge=0, lt=NODE_COUNT)
    lat: float
    lon: float
    queue_length: int = Field(ge=0)
    uhi_index: float = Field(ge=0)
    emission_index: float = Field(ge=0)


def as_node_id(location: int | GridCoordinate) -> int:
    if isinstance(location, int):
        return location
    return (location.row * GRID_SIZE) + location.column


def build_reservation_plan(
    route: dict[str, Any],
    *,
    ev_id: str,
    departure_delay_seconds: int = 0,
) -> tuple[list[ReservationRequest], bool]:
    """Turn route segments into source-intersection green-wave windows.

    A segment ``A -> B`` reserves A's outbound axis, because that is the
    signal the EV must pass before entering the road.  The next segment starts
    after the previous road travel time, which produces a forward-looking green
    wave.  Reservations outside the edge agent's fixed horizon are deliberately
    left for the normal hop-by-hop replan when the EV gets closer.
    """
    segments = route.get("segments", [])
    if not segments:
        return [], False

    now_second = int(time.time())
    horizon_end = now_second + RESERVATION_HORIZON_SECONDS
    cursor = float(now_second + RESERVATION_LEAD_SECONDS + departure_delay_seconds)
    plan: list[ReservationRequest] = []
    horizon_limited = False

    for segment_index, segment in enumerate(segments):
        try:
            node = int(segment["from"])
            axis = str(segment["direction"])
            road_seconds = max(0.0, float(segment["road_travel_seconds"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("route contains an invalid segment for reservation planning") from exc
        if node not in range(NODE_COUNT) or axis not in {"NS", "EW"}:
            raise ValueError("route contains an invalid reservation node or axis")

        # The bit-mask timeline is expressed in whole seconds. Round forward,
        # never backward, so the EV cannot arrive before its green window.
        start_time = max(now_second + RESERVATION_LEAD_SECONDS, math.ceil(cursor))
        if start_time + RESERVATION_WINDOW_SECONDS > horizon_end:
            horizon_limited = True
            break
        identifier = uuid.uuid4().hex
        plan.append(
            ReservationRequest(
                node=node,
                ev_id=ev_id,
                axis=axis,
                start_time=start_time,
                duration=RESERVATION_WINDOW_SECONDS,
                request_id=f"reservation-request-{identifier}",
                reservation_id=f"reservation-{identifier}",
                segment_index=segment_index,
            )
        )
        # A later node receives its window at the EV's predicted road-arrival
        # time.  Signal waits are intentionally not carried forward: a granted
        # reservation is the signal permission for that downstream movement.
        cursor = float(start_time) + road_seconds

    return plan, horizon_limited


def apply_reservation_schedule(
    route: dict[str, Any],
    *,
    ev_id: str,
    grants: list[ReservationGrant],
    attempts: int,
    horizon_limited: bool,
) -> dict[str, Any]:
    """Return the existing route shape with booked signal waits made explicit."""
    result = dict(route)
    segments = [dict(segment) for segment in route.get("segments", [])]
    grants_by_segment = {grant.request.segment_index: grant for grant in grants}
    simulated_clock = time.time()

    for segment_index, segment in enumerate(segments):
        road_seconds = max(0.0, float(segment["road_travel_seconds"]))
        grant = grants_by_segment.get(segment_index)
        if grant is None:
            # Outside the 120-second planning horizon, retain the latest live
            # signal estimate. The browser will ask again at the next node.
            signal_wait = max(0.0, float(segment.get("signal_wait_seconds", 0.0)))
        else:
            reservation_start = grant.acknowledgement.start_time
            signal_wait = max(0.0, float(reservation_start) - simulated_clock)
            segment["reservation_start_time"] = reservation_start
            segment["reservation_duration_seconds"] = grant.acknowledgement.duration
            segment["reservation_id"] = (
                grant.acknowledgement.reservation_id or grant.request.reservation_id
            )
            segment["reservation_status"] = "granted"
        total_seconds = road_seconds + signal_wait
        segment["signal_wait_seconds"] = round(signal_wait, 1)
        segment["signal_delay"] = round(signal_wait, 1)
        segment["road_travel_seconds"] = round(road_seconds, 1)
        segment["congestion_cost"] = round(road_seconds, 1)
        segment["travel_cost"] = round(total_seconds, 1)
        simulated_clock += total_seconds

    result["segments"] = segments
    result["eta_seconds"] = round(sum(float(segment["travel_cost"]) for segment in segments), 1)
    result["ev_id"] = ev_id
    result["reservation_status"] = (
        "not_required"
        if not segments
        else "granted_with_horizon_limit" if horizon_limited else "granted"
    )
    result["reservations"] = [grant.api_payload() for grant in grants]
    result["reservation_attempts"] = attempts
    result["reservation_horizon_limited"] = horizon_limited
    result["generated_at"] = datetime.now(UTC).isoformat()
    return result


async def reserve_route_for_ev(ev_id: str, start: int, end: int) -> dict[str, Any]:
    """Find, FCFS-book, and if necessary reroute one connected EV.

    A denied downstream reservation causes the already granted slots from that
    attempt to be cancelled before A* is retried with the conflicting node
    removed. A denial at the current node cannot be bypassed, so it uses a
    bounded later departure window instead. Every MQTT wait is time-bounded.
    """
    ev_lock = reservation_coordinator.ev_lock(ev_id)
    async with ev_lock:
        blocked_nodes: set[int] = set()
        departure_delay_seconds = 0
        prior_reservations: list[ReservationGrant] | None = None

        for attempt in range(1, RESERVATION_MAX_REROUTES + 2):
            route = traffic_graph.find_route(start, end, excluded_nodes=blocked_nodes)
            if prior_reservations is None:
                # Do not cancel a working route until A* has successfully read
                # fresh telemetry. This is important when MQTT traffic is stale.
                prior_reservations = reservation_coordinator.take_active(ev_id)
                if prior_reservations and not traffic_consumer.cancel_reservations(prior_reservations):
                    raise ReservationCleanupError(
                        "The prior route could not be cancelled while MQTT is disconnected; "
                        "the EV will not create overlapping reservations."
                    )

            plan, horizon_limited = build_reservation_plan(
                route,
                ev_id=ev_id,
                departure_delay_seconds=departure_delay_seconds,
            )
            if not plan:
                reservation_coordinator.store_active(ev_id, [])
                return apply_reservation_schedule(
                    route,
                    ev_id=ev_id,
                    grants=[],
                    attempts=attempt,
                    horizon_limited=horizon_limited,
                )

            grants: list[ReservationGrant] = []
            rejected: ReservationAcknowledgement | None = None
            uncertain: ReservationRequest | None = None
            try:
                for request in plan:
                    acknowledgement = await reservation_coordinator.request(
                        request, traffic_consumer.publish_reservation
                    )
                    if not acknowledgement.granted:
                        rejected = acknowledgement
                        break
                    grants.append(ReservationGrant(request, acknowledgement))
            except (ReservationTimeoutError, ReservationUnavailableError) as exc:
                # The edge may have received the request but lost its response.
                # Cancel both confirmed and uncertain windows; cancellation IDs
                # make this safe even when it reaches the edge first.
                uncertain = request
                cleanup_targets: list[ReservationGrant | ReservationRequest] = [*grants, uncertain]
                traffic_consumer.cancel_reservations(cleanup_targets)
                raise exc

            if rejected is None:
                reservation_coordinator.store_active(ev_id, grants)
                return apply_reservation_schedule(
                    route,
                    ev_id=ev_id,
                    grants=grants,
                    attempts=attempt,
                    horizon_limited=horizon_limited,
                )

            if not traffic_consumer.cancel_reservations(grants):
                raise ReservationCleanupError(
                    "A rejected reservation left prior route slots awaiting MQTT cleanup; "
                    "the EV will not replan until that control message is delivered."
                )

            # A downstream intersection can be avoided in the next A* graph.
            # The EV is itself at ``start``, so a collision there becomes a
            # short FCFS delay rather than an impossible attempt to remove it.
            if rejected.node not in {start, end} and rejected.node not in blocked_nodes:
                blocked_nodes.add(rejected.node)
            else:
                departure_delay_seconds += max(
                    RESERVATION_CONFLICT_DELAY_SECONDS,
                    rejected.duration,
                )

        raise ReservationConflictError(
            "No conflict-free emergency reservation could be secured after "
            f"{RESERVATION_MAX_REROUTES + 1} FCFS routing attempts."
        )


async def traffic_simulation_loop() -> None:
    """Run only when a developer explicitly enables the synthetic fallback."""
    while True:
        traffic_graph.simulate_tick()
        await asyncio.sleep(UPDATE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    traffic_consumer.start()
    simulation_task: asyncio.Task[None] | None = None
    if TRAFFIC_DEMO_MODE:
        simulation_task = asyncio.create_task(traffic_simulation_loop())
    try:
        yield
    finally:
        if simulation_task is not None:
            simulation_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await simulation_task
        traffic_consumer.stop()


app = FastAPI(title="Traffic Orchestration API", version="2.0.0", lifespan=lifespan)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)


def require_admin(current_user: CurrentUser) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required.")


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Liveness plus traffic-source diagnostics for deployment monitoring."""
    return {
        "status": "ok",
        "traffic": traffic_graph.status(),
        "reservations": reservation_coordinator.status(),
    }


@app.get("/api/me", response_model=CurrentUser)
async def current_user_profile(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    return current_user


@app.get("/api/traffic/status")
async def traffic_status(
    _current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """Let signed-in drivers show the freshness of routing telemetry."""
    return traffic_graph.status()


@app.get("/api/traffic")
async def traffic_snapshot(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """HTTP fallback for the administrator monitor."""
    require_admin(current_user)
    return traffic_graph.snapshot()


@app.get(
    "/api/environment/heatmap",
    response_model=list[EnvironmentalHeatmapPoint],
)
async def environmental_heatmap(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db=Depends(get_db),
) -> list[dict[str, float | int]]:
    """Return PostGIS locations enriched with the latest live queue telemetry.

    Coordinates remain database-owned because they describe the physical city,
    while queue lengths remain orchestrator-owned because they arrive through
    MQTT.  The endpoint deliberately performs no routing or reservation work.
    """
    require_admin(current_user)

    # Copy the live values under the existing traffic lock, then release it
    # before the database request so a slow spatial query cannot delay routing.
    with traffic_graph.lock:
        queue_lengths = dict(traffic_graph.queue_lengths)

    try:
        with db.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    node_id,
                    ST_Y(geom) AS lat,
                    ST_X(geom) AS lon
                FROM spatial_intersections
                WHERE node_id BETWEEN 0 AND %s
                ORDER BY node_id;
                """,
                (NODE_COUNT - 1,),
            )
            coordinate_rows = cursor.fetchall()
    except PsycopgError as exc:
        # Missing PostGIS, a missing table, or a temporary spatial-database
        # outage should not appear as a generic internal server error.
        raise HTTPException(
            status_code=503,
            detail=(
                "Environmental heatmap is unavailable: the PostGIS "
                "spatial_intersections table could not be queried."
            ),
        ) from exc

    coordinates: dict[int, tuple[float, float]] = {}
    try:
        for row in coordinate_rows:
            node_id = int(row["node_id"])
            lat = float(row["lat"])
            lon = float(row["lon"])
            if (
                node_id not in range(NODE_COUNT)
                or not math.isfinite(lat)
                or not math.isfinite(lon)
            ):
                raise ValueError
            coordinates[node_id] = (lat, lon)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Environmental heatmap is unavailable: spatial_intersections "
                "contains invalid GPS coordinate data."
            ),
        ) from exc

    missing_nodes = sorted(set(range(NODE_COUNT)) - set(coordinates))
    if missing_nodes:
        raise HTTPException(
            status_code=503,
            detail=(
                "Environmental heatmap is unavailable: spatial_intersections "
                f"is missing GPS coordinates for node IDs {missing_nodes}."
            ),
        )

    return [
        {
            "node_id": node,
            "lat": coordinates[node][0],
            "lon": coordinates[node][1],
            "queue_length": queue_lengths[node],
            "uhi_index": round(queue_lengths[node] * 2.5, 1),
            "emission_index": round(queue_lengths[node] * 1.8, 1),
        }
        for node in range(NODE_COUNT)
    ]


@app.post("/api/traffic/nodes/{node}/blackout")
async def simulate_node_blackout(
    node: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """Admin-only watchdog exercise: make one intersection unavailable."""
    require_admin(current_user)
    try:
        return traffic_graph.set_manual_offline(node, offline=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/api/traffic/nodes/{node}/blackout")
async def restore_node_from_blackout(
    node: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """Restore a manually blacked-out intersection to normal routing."""
    require_admin(current_user)
    try:
        return traffic_graph.set_manual_offline(node, offline=False)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.websocket("/ws/traffic")
async def traffic_websocket(websocket: WebSocket) -> None:
    """Push MQTT-fed graph snapshots only to signed-in administrators."""
    token = websocket.query_params.get("token", "")
    try:
        current_user = decode_access_token(token)
    except HTTPException:
        await websocket.close(code=1008, reason="Authentication required")
        return
    if current_user.role != "admin":
        await websocket.close(code=1008, reason="Administrator role required")
        return
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(traffic_graph.snapshot())
            await asyncio.sleep(UPDATE_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        return


@app.post("/api/route", response_model=RouteResponse)
async def route_emergency_vehicle(
    route_request: RouteRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """Return a fresh, FCFS-booked route for an authenticated EV driver."""
    if current_user.role != "ev_driver":
        raise HTTPException(
            status_code=403,
            detail="Only EV-driver accounts can request priority routes.",
        )
    try:
        # The database identity, not a browser-provided label, is the stable
        # reservation owner. Different EV accounts therefore participate in
        # FCFS independently while repeat requests by one driver cannot create
        # overlapping self-reservations.
        return await reserve_route_for_ev(
            f"ev-{current_user.id}",
            as_node_id(route_request.start),
            as_node_id(route_request.end),
        )
    except TrafficUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ReservationUnavailableError, ReservationTimeoutError, ReservationCleanupError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ReservationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, nx.NetworkXNoPath) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/route/cancel", response_model=RouteCancellationResponse)
async def cancel_emergency_route(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """Release this driver's remaining future signal windows immediately.

    The endpoint is idempotent so the React driver's "End active trip" action
    may be repeated safely. If MQTT is momentarily offline, the cancellation is
    queued and the edge agent's cancel-before-reserve guard prevents a delayed
    original request from recreating a stale booking.
    """
    if current_user.role != "ev_driver":
        raise HTTPException(
            status_code=403,
            detail="Only EV-driver accounts can cancel priority routes.",
        )
    ev_id = f"ev-{current_user.id}"
    ev_lock = reservation_coordinator.ev_lock(ev_id)
    async with ev_lock:
        grants = reservation_coordinator.take_active(ev_id)
        delivered = traffic_consumer.cancel_reservations(grants)
    return {
        "ev_id": ev_id,
        "cancelled_reservations": len(grants),
        "status": "cancelled" if delivered else "cancellation_queued",
    }
