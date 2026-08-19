"""Legacy Streamlit cloud-routing prototype.

The production application now uses ``backend/main.py`` as the MQTT
orchestrator and the React dashboard as its only user-facing interface. Do not
run this file alongside FastAPI: it would create a second independent routing
brain listening to the same simulator topic.

It remains in the repository only as a development/reference prototype.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import numpy as np
import paho.mqtt.client as mqtt
import streamlit as st
import torch
from pyvis.network import Network

BROKER_HOST = os.getenv("MQTT_BROKER", "test.mosquitto.org").strip()
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883").strip())
MQTT_TRANSPORT = os.getenv("MQTT_TRANSPORT", "tcp").strip().lower()
MQTT_WS_PATH = os.getenv("MQTT_WS_PATH", "/mqtt").strip()
TRAFFIC_TOPIC = "city/intersections/update"
REQUEST_TOPIC = "city/ev/request"
ROUTE_TOPIC_PREFIX = "city/ev/route/"
GRID_SIZE = 5
NODE_COUNT = GRID_SIZE * GRID_SIZE
GREEN_DURATION_TICKS = 15
YELLOW_DURATION_TICKS = 3
MAX_TRAFFIC_AGE_SECONDS = 8.0

# False uses a deterministic scalar for the hackathon live demo; True loads the
# optimized PyTorch .pt file from the production pipeline.
USE_REAL_MODEL = False


def movement_axis(source: int, destination: int) -> str:
    """Return the movement axis for one directed grid road segment."""
    source_row, source_column = divmod(source, GRID_SIZE)
    destination_row, destination_column = divmod(destination, GRID_SIZE)
    if source_column == destination_column and abs(source_row - destination_row) == 1:
        return "NS"
    if source_row == destination_row and abs(source_column - destination_column) == 1:
        return "EW"
    raise ValueError(f"{source} and {destination} are not adjacent intersections")


def make_city_graph() -> nx.DiGraph:
    """Build directed city roads so source-signal delays affect each movement."""
    undirected_grid = nx.grid_2d_graph(GRID_SIZE, GRID_SIZE)
    grid = nx.convert_node_labels_to_integers(undirected_grid, ordering="sorted")
    graph = nx.DiGraph()
    graph.add_nodes_from(grid.nodes)
    for source, destination in grid.edges:
        for left, right in ((source, destination), (destination, source)):
            graph.add_edge(
                left,
                right,
                movement_axis=movement_axis(left, right),
                signal_delay_seconds=0.0,
                traffic_delay_seconds=6.0,
                weight=6.0,
            )
    return graph


def grid_distance(node_a: int, node_b: int) -> int:
    """Admissible Manhattan-distance heuristic for A* on the grid."""
    row_a, col_a = divmod(node_a, GRID_SIZE)
    row_b, col_b = divmod(node_b, GRID_SIZE)
    return abs(row_a - row_b) + abs(col_a - col_b)


def compute_normalized_adjacency(graph: nx.DiGraph) -> np.ndarray:
    """Return D^(-1/2) (A + I) D^(-1/2) for spectral graph convolution."""
    nodes = list(graph.nodes)
    adjacency = nx.to_numpy_array(graph, nodelist=nodes, dtype=float)
    adjacency_with_self_loops = adjacency + np.eye(len(nodes), dtype=float)
    degrees = adjacency_with_self_loops.sum(axis=1)
    inverse_sqrt_degrees = np.zeros_like(degrees)
    nonzero_degrees = degrees > 0
    inverse_sqrt_degrees[nonzero_degrees] = 1.0 / np.sqrt(degrees[nonzero_degrees])
    return (
        inverse_sqrt_degrees[:, np.newaxis]
        * adjacency_with_self_loops
        * inverse_sqrt_degrees[np.newaxis, :]
    )


@dataclass
class TrafficState:
    """Validated network state received from the 25-intersection simulator."""

    graph: nx.DiGraph = field(default_factory=make_city_graph)
    queue_lengths: dict[int, int] = field(
        default_factory=lambda: {node: 0 for node in range(NODE_COUNT)}
    )
    observed_flush_times: dict[int, float] = field(
        default_factory=lambda: {node: 5.0 for node in range(NODE_COUNT)}
    )
    flush_times: dict[int, int] = field(
        default_factory=lambda: {node: 5 for node in range(NODE_COUNT)}
    )
    light_phases: dict[int, str] = field(
        default_factory=lambda: {node: "NS_GREEN" for node in range(NODE_COUNT)}
    )
    active_directions: dict[int, str] = field(
        default_factory=lambda: {node: "NS" for node in range(NODE_COUNT)}
    )
    phase_remaining_ticks: dict[int, int] = field(
        default_factory=lambda: {node: GREEN_DURATION_TICKS for node in range(NODE_COUNT)}
    )
    last_update: float | None = None
    source_generated_at: float | None = None
    traffic_tick: int | None = None
    traffic_version: int = 0
    last_route: dict[str, Any] | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)
    A_hat: np.ndarray = field(init=False)
    W: Any = field(init=False)

    def __post_init__(self) -> None:
        self.A_hat = compute_normalized_adjacency(self.graph)
        if USE_REAL_MODEL:
            try:
                model_weights = torch.load("ML_Pipeline/stgnn_weights.pt", map_location="cpu")
                self.W = model_weights["weight_matrix"].numpy()
            except FileNotFoundError:
                self.W = 1.2
        else:
            self.W = 1.2

    @staticmethod
    def _fallback_queue_length(flush_time: float) -> int:
        """Estimate a queue for legacy publishers that omit queue_length."""
        return max(0, min(40, round((flush_time - 2.0) / 0.8)))

    def _parse_light_state(self, record: dict[str, Any], node: int) -> tuple[str, str, int]:
        phase = str(record.get("light_phase", self.light_phases[node]))
        if phase not in {"NS_GREEN", "EW_GREEN", "YELLOW"}:
            raise ValueError(f"node {node} has an invalid light_phase: {phase!r}")

        active_direction = str(record.get("active_direction", self.active_directions[node]))
        if phase == "NS_GREEN":
            active_direction = "NS"
        elif phase == "EW_GREEN":
            active_direction = "EW"
        elif active_direction not in {"NS", "EW"}:
            raise ValueError(f"node {node} yellow phase needs active_direction NS or EW")

        phase_duration = YELLOW_DURATION_TICKS if phase == "YELLOW" else GREEN_DURATION_TICKS
        raw_remaining = record.get("phase_remaining_ticks", phase_duration)
        try:
            remaining = int(raw_remaining)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"node {node} has invalid phase_remaining_ticks") from exc
        if not 0 <= remaining <= phase_duration:
            raise ValueError(f"node {node} phase_remaining_ticks must be 0..{phase_duration}")
        return phase, active_direction, remaining

    @staticmethod
    def _signal_wait_seconds(
        phase: str,
        active_direction: str,
        remaining_ticks: int,
        requested_axis: str,
    ) -> float:
        """Estimate the wait at a source signal for one requested movement.

        The edge simulator permits the active direction during yellow at a
        lower discharge rate. A movement on the opposing axis must wait for
        the current phase to finish; an opposing green also has its yellow
        clearance before the desired green begins.
        """
        if requested_axis == active_direction:
            return 2.0 if phase == "YELLOW" else 0.0
        if phase == "YELLOW":
            return float(remaining_ticks)
        return float(remaining_ticks + YELLOW_DURATION_TICKS)

    def _refresh_directed_costs(self) -> None:
        """Apply live queue and signal costs to every directed road segment."""
        for source, destination, edge in self.graph.edges(data=True):
            axis = str(edge["movement_axis"])
            source_queue_delay = min(
                12.0,
                (0.30 * self.queue_lengths[source]) + (0.20 * self.flush_times[source]),
            )
            receiving_penalty = min(
                5.0,
                (0.12 * self.queue_lengths[destination]) + (0.08 * self.flush_times[destination]),
            )
            signal_delay = self._signal_wait_seconds(
                self.light_phases[source],
                self.active_directions[source],
                self.phase_remaining_ticks[source],
                axis,
            )
            traffic_delay = 6.0 + source_queue_delay + receiving_penalty
            edge["signal_delay_seconds"] = round(signal_delay, 1)
            edge["traffic_delay_seconds"] = round(traffic_delay, 1)
            edge["weight"] = round(traffic_delay + signal_delay, 1)

    def update_traffic(self, records: list[dict[str, Any]]) -> None:
        """Atomically apply one complete live snapshot from the edge simulator."""
        if len(records) != NODE_COUNT:
            raise ValueError(f"traffic snapshot must contain exactly {NODE_COUNT} records")

        incoming_nodes: set[int] = set()
        parsed_records: dict[int, tuple[int, float, str, str, int]] = {}
        source_ticks: set[int] = set()
        source_times: set[float] = set()

        for record in records:
            if not isinstance(record, dict):
                raise ValueError("traffic snapshot records must be JSON objects")
            try:
                node = int(record["node"])
                flush_time = float(record["flush_time"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("traffic record requires numeric node and flush_time") from exc
            if node not in self.graph or node in incoming_nodes:
                raise ValueError(f"traffic snapshot contains an invalid or duplicate node: {node}")
            if not np.isfinite(flush_time) or not 1.0 <= flush_time <= 40.0:
                raise ValueError(f"node {node} flush_time must be finite and within 1..40")
            try:
                queue_length = int(record.get("queue_length", self._fallback_queue_length(flush_time)))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"node {node} has invalid queue_length") from exc
            if not 0 <= queue_length <= 40:
                raise ValueError(f"node {node} queue_length must be within 0..40")

            phase, active_direction, remaining = self._parse_light_state(record, node)
            incoming_nodes.add(node)
            parsed_records[node] = (queue_length, flush_time, phase, active_direction, remaining)
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

        if incoming_nodes != set(range(NODE_COUNT)):
            raise ValueError("traffic snapshot must contain every node from 0 through 24")
        if len(source_ticks) > 1 or len(source_times) > 1:
            raise ValueError("all traffic records must belong to the same simulation snapshot")

        with self.lock:
            incoming_generated_at = next(iter(source_times), None)
            if (
                incoming_generated_at is not None
                and self.source_generated_at is not None
                and incoming_generated_at < self.source_generated_at
            ):
                raise ValueError("received an out-of-order traffic snapshot")
            if (
                incoming_generated_at is not None
                and incoming_generated_at == self.source_generated_at
            ):
                # MQTT QoS 1 can redeliver a retained snapshot. It carries no
                # new state, so acknowledge it by leaving the current state.
                return
            for node, (queue_length, flush_time, phase, active_direction, remaining) in parsed_records.items():
                self.queue_lengths[node] = queue_length
                self.observed_flush_times[node] = flush_time
                self.light_phases[node] = phase
                self.active_directions[node] = active_direction
                self.phase_remaining_ticks[node] = remaining

            H_0 = np.asarray(
                [self.observed_flush_times[node] for node in range(NODE_COUNT)], dtype=float
            )
            if isinstance(self.W, np.ndarray):
                H_1 = np.maximum(0, (self.A_hat @ H_0) @ self.W)
                self.flush_times = {
                    node: max(1, min(40, int(round(float(H_1[node])))))
                    for node in self.graph.nodes
                }
            else:
                # The default demo must route on the simulator's real measured
                # queue/flush state, rather than a second synthetic multiplier.
                self.flush_times = {
                    node: max(1, min(40, int(round(self.observed_flush_times[node]))))
                    for node in self.graph.nodes
                }

            self._refresh_directed_costs()
            self.last_update = time.time()
            self.source_generated_at = incoming_generated_at or self.last_update
            self.traffic_tick = next(iter(source_ticks), self.traffic_tick)
            self.traffic_version += 1

    def traffic_age_seconds(self) -> float | None:
        timestamp = self.source_generated_at or self.last_update
        return None if timestamp is None else max(0.0, time.time() - timestamp)

    def route_for(
        self,
        ev_id: str,
        start: int,
        end: int,
        request_id: str | None,
        excluded_nodes: list[int] | None = None,
    ) -> dict[str, Any]:
        """Return A* data while honouring FCFS-rejected intersection exclusions.

        An EV sends ``excluded_nodes`` after an edge reservation conflict.  The
        normal graph stays untouched; A* runs against a temporary copy with
        those nodes removed, so another vehicle's conflict never corrupts the
        shared city model.
        """
        if start not in self.graph or end not in self.graph:
            raise ValueError("start and end must be intersection IDs from 0 to 24")
        if excluded_nodes is None:
            excluded_nodes = []
        if not isinstance(excluded_nodes, list):
            raise ValueError("excluded_nodes must be a list of intersection IDs")
        try:
            excluded = {int(node) for node in excluded_nodes}
        except (TypeError, ValueError) as exc:
            raise ValueError("excluded_nodes must contain integer intersection IDs") from exc
        if not excluded.issubset(self.graph.nodes):
            raise ValueError("excluded_nodes must contain intersection IDs from 0 to 24")
        # The EV cannot route around its physical position or its destination.
        # Keep them valid so a conflict at the destination is handled as a
        # later reservation slot rather than a malformed A* request.
        excluded.discard(start)
        excluded.discard(end)
        with self.lock:
            traffic_age = self.traffic_age_seconds()
            if traffic_age is None or traffic_age > MAX_TRAFFIC_AGE_SECONDS:
                raise ValueError("Live traffic telemetry is unavailable or stale; waiting for a fresh 25-node snapshot.")
            routing_graph = self.graph.copy()
            routing_graph.remove_nodes_from(excluded)
            route = nx.astar_path(
                routing_graph,
                start,
                end,
                heuristic=grid_distance,
                weight="weight",
            )
            eta_seconds = sum(
                self.graph[left][right]["weight"] for left, right in zip(route, route[1:])
            )
            # The EV agent uses the first segment cost to account for each
            # simulated hop before requesting a fresh route from its new node.
            segment_eta_seconds = [
                round(self.graph[left][right]["weight"], 1)
                for left, right in zip(route, route[1:])
            ]
            segments = [
                {
                    "from": left,
                    "to": right,
                    "movement_axis": self.graph[left][right]["movement_axis"],
                    "source_light_phase": self.light_phases[left],
                    "source_active_direction": self.active_directions[left],
                    "phase_remaining_ticks": self.phase_remaining_ticks[left],
                    "signal_delay_seconds": self.graph[left][right]["signal_delay_seconds"],
                    "traffic_delay_seconds": self.graph[left][right]["traffic_delay_seconds"],
                    "eta_seconds": self.graph[left][right]["weight"],
                }
                for left, right in zip(route, route[1:])
            ]
            result = {
                "ev_id": ev_id,
                "request_id": request_id,
                "route": route,
                "eta_seconds": round(eta_seconds, 1),
                "segment_eta_seconds": segment_eta_seconds,
                "segments": segments,
                "traffic_version": self.traffic_version,
                "traffic_tick": self.traffic_tick,
                "traffic_age_seconds": round(traffic_age, 2),
                "excluded_nodes": sorted(excluded),
                "generated_at": time.time(),
            }
            self.last_route = result
            return result

    def snapshot(self) -> tuple[
        nx.DiGraph,
        dict[int, int],
        dict[int, str],
        dict[int, str],
        dict[int, int],
        float | None,
        int,
        int | None,
        dict[str, Any] | None,
    ]:
        """Return display data without exposing mutable worker-thread state."""
        with self.lock:
            return (
                self.graph.copy(),
                self.flush_times.copy(),
                self.light_phases.copy(),
                self.active_directions.copy(),
                self.phase_remaining_ticks.copy(),
                self.last_update,
                self.traffic_version,
                self.traffic_tick,
                self.last_route.copy() if self.last_route else None,
            )


class OrchestratorMqttWorker:
    """MQTT callbacks run on Paho's thread and never call Streamlit APIs."""

    def __init__(self) -> None:
        if MQTT_TRANSPORT not in {"tcp", "websockets"}:
            raise ValueError("MQTT_TRANSPORT must be 'tcp' or 'websockets'")
        self.state = TrafficState()
        self.connected = False
        self.error: str | None = None
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"orchestrator-{uuid.uuid4().hex[:8]}",
            protocol=mqtt.MQTTv311,
            transport=MQTT_TRANSPORT,
        )
        if MQTT_TRANSPORT == "websockets":
            self.client.ws_set_options(path=MQTT_WS_PATH)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=20)
        self.client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=60)
        # This Paho-owned background thread keeps the Streamlit script responsive.
        self.client.loop_start()

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        self.connected = not reason_code.is_failure
        if self.connected:
            client.subscribe([(TRAFFIC_TOPIC, 1), (REQUEST_TOPIC, 1)])
            self.error = None
        else:
            self.error = f"MQTT connection failed: {reason_code}"

    def _on_disconnect(self, _client, _userdata, _disconnect_flags, reason_code, _properties) -> None:
        self.connected = False
        if reason_code != mqtt.MQTT_ERR_SUCCESS:
            self.error = f"MQTT disconnected: {reason_code}"

    def _on_message(self, client, _userdata, message) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            if message.topic == TRAFFIC_TOPIC:
                if not isinstance(payload, list):
                    raise ValueError("traffic payload must be a JSON array")
                self.state.update_traffic(payload)
            elif message.topic == REQUEST_TOPIC:
                ev_id = str(payload["ev_id"])
                request_id = payload.get("request_id")
                try:
                    result = self.state.route_for(
                        ev_id=ev_id,
                        start=int(payload["start"]),
                        end=int(payload["end"]),
                        request_id=request_id,
                        excluded_nodes=payload.get("excluded_nodes", payload.get("avoid_nodes")),
                    )
                except (TypeError, ValueError, nx.NetworkXNoPath) as exc:
                    result = {
                        "ev_id": ev_id,
                        "request_id": request_id,
                        "error": str(exc),
                        "generated_at": time.time(),
                    }
                client.publish(f"{ROUTE_TOPIC_PREFIX}{ev_id}", json.dumps(result), qos=1)
        except (KeyError, TypeError, ValueError, nx.NetworkXNoPath) as exc:
            self.error = f"Ignored invalid MQTT message on {message.topic}: {exc}"


@st.cache_resource(show_spinner=False)
def get_mqtt_worker() -> OrchestratorMqttWorker:
    return OrchestratorMqttWorker()


def congestion_color(flush_time: int) -> str:
    if flush_time >= 18:
        return "#e74c3c"  # red: heavy congestion
    if flush_time >= 10:
        return "#f39c12"  # amber: moderate congestion
    return "#2ecc71"  # green: clear


def render_network(
    graph: nx.DiGraph,
    flush_times: dict[int, int],
    light_phases: dict[int, str],
    active_directions: dict[int, str],
    phase_remaining_ticks: dict[int, int],
) -> None:
    network = Network(height="610px", width="100%", bgcolor="#101820", font_color="white")
    network.toggle_physics(False)
    for node in graph.nodes:
        row, col = divmod(node, GRID_SIZE)
        flush_time = flush_times[node]
        phase = light_phases[node]
        active_direction = active_directions[node]
        remaining = phase_remaining_ticks[node]
        network.add_node(
            node,
            label=str(node),
            title=(
                f"Intersection {node}<br>Predicted flush time: {flush_time}s"
                f"<br>Signal: {phase} ({active_direction})"
                f"<br>Phase remaining: {remaining}s"
            ),
            color=congestion_color(flush_time),
            x=col * 140,
            y=row * 140,
            physics=False,
        )
    displayed_roads: set[tuple[int, int]] = set()
    for source, destination in graph.edges:
        road = tuple(sorted((source, destination)))
        if road in displayed_roads:
            continue
        displayed_roads.add(road)
        forward = graph[source][destination]
        reverse = graph[destination][source]
        network.add_edge(
            source,
            destination,
            title=(
                f"{source} → {destination}: {forward['weight']:.1f}s "
                f"(signal wait {forward['signal_delay_seconds']:.1f}s)"
                f"<br>{destination} → {source}: {reverse['weight']:.1f}s "
                f"(signal wait {reverse['signal_delay_seconds']:.1f}s)"
            ),
        )
    # Streamlit 1.56+ accepts trusted raw HTML directly and renders it in an
    # iframe. This replaces the deprecated st.components.v1.html API.
    st.iframe(network.generate_html(notebook=False), height=625)


def dashboard_body(worker: OrchestratorMqttWorker) -> None:
    (
        graph,
        flush_times,
        light_phases,
        active_directions,
        phase_remaining_ticks,
        last_update,
        traffic_version,
        traffic_tick,
        last_route,
    ) = worker.state.snapshot()
    status = "connected" if worker.connected else "connecting / reconnecting"
    st.caption(f"MQTT: {status} · broker: {BROKER_HOST}:{BROKER_PORT}")
    if worker.error:
        st.warning(worker.error)
    if last_update:
        tick_label = f" · simulator tick: {traffic_tick}" if traffic_tick is not None else ""
        st.caption(
            f"Traffic snapshot v{traffic_version}{tick_label} · "
            f"received: {time.strftime('%H:%M:%S', time.localtime(last_update))}"
        )
    else:
        st.info("Waiting for a complete, fresh 25-node traffic snapshot from intersection_agent.py.")

    render_network(graph, flush_times, light_phases, active_directions, phase_remaining_ticks)
    st.markdown(
        "Green = clear, amber = moderate traffic, red = heavy congestion. "
        "Road costs include each source intersection's current signal wait."
    )
    if last_route:
        st.info(
            f"Latest route for {last_route['ev_id']}: {last_route['route']} "
            f"(estimated {last_route['eta_seconds']} seconds, "
            f"traffic snapshot v{last_route.get('traffic_version', '—')})"
        )


def main() -> None:
    st.set_page_config(page_title="City Orchestrator", layout="wide")
    st.title("City Traffic Orchestrator")
    worker = get_mqtt_worker()

    # Modern Streamlit fragments rerun only this display every two seconds.  The
    # MQTT worker remains independent, so no background thread needs a
    # Streamlit script context (and it never calls st.* APIs).
    if hasattr(st, "fragment"):
        @st.fragment(run_every="2s")
        def live_dashboard() -> None:
            dashboard_body(worker)

        live_dashboard()
    else:
        dashboard_body(worker)
        st.caption("Upgrade to Streamlit 1.37+ for automatic refresh, or refresh this page.")


if __name__ == "__main__":
    main()
