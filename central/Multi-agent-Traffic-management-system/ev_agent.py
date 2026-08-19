"""Legacy Streamlit ambulance prototype.

The production EV experience is now the authenticated React driver dashboard.
It performs the same move-one-hop, request-a-fresh-route behaviour through the
FastAPI orchestration API. This file uses the old MQTT request/response
contract and is retained only as a development/reference prototype.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
import uuid
from typing import Any

import paho.mqtt.client as mqtt
import streamlit as st

BROKER_HOST = os.getenv("MQTT_BROKER", "test.mosquitto.org").strip()
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883").strip())
MQTT_TRANSPORT = os.getenv("MQTT_TRANSPORT", "tcp").strip().lower()
MQTT_WS_PATH = os.getenv("MQTT_WS_PATH", "/mqtt").strip()
EV_ID = "Ambulance1"
REQUEST_TOPIC = "city/ev/request"
RESPONSE_TOPIC = f"city/ev/route/{EV_ID}"
# A route reply remains on the EV-specific topic above.  Reservation replies
# use one shared topic and are correlated by ``ev_id`` plus ``reservation_id``.
RESERVATION_REQUEST_TOPIC = "city/intersections/reserve"
RESERVATION_RESPONSE_TOPIC = "city/intersections/reserve/response"
RESERVATION_CANCEL_TOPIC = "city/intersections/reserve/cancel"
INTERSECTIONS = list(range(25))
# The UI runs faster than the traffic model's estimated road travel time, but
# never moves sooner than one MQTT traffic-publish interval. This guarantees a
# hop has an opportunity to receive a newer signal/queue snapshot first.
EV_SECONDS_PER_ETA_SECOND = float(os.getenv("EV_SECONDS_PER_ETA_SECOND", "0.15"))
MIN_HOP_DISPLAY_SECONDS = float(os.getenv("EV_MIN_HOP_SECONDS", "2.2"))
MAX_HOP_DISPLAY_SECONDS = float(os.getenv("EV_MAX_HOP_SECONDS", "8.0"))
REQUEST_RETRY_SECONDS = 2.0
# The edge reservation manager owns a 120-second rolling window.  The EV does
# not reserve a slot beyond that horizon; it will obtain a fresh route after
# its next hop and reserve the next visible portion of its journey instead.
RESERVATION_HORIZON_SECONDS = int(os.getenv("EV_RESERVATION_HORIZON_SECONDS", "120"))
RESERVATION_DURATION_SECONDS = int(os.getenv("EV_RESERVATION_DURATION_SECONDS", "4"))
RESERVATION_RESPONSE_TIMEOUT_SECONDS = float(
    os.getenv("EV_RESERVATION_RESPONSE_TIMEOUT_SECONDS", "4.0")
)


class AmbulanceMqttWorker:
    """A Paho worker whose callbacks only update locked Python state.

    Paho's loop_start thread is deliberately not given add_script_run_ctx:
    background callbacks must not render Streamlit UI.  The main Streamlit
    script reads this state safely on each rerun instead.
    """

    def __init__(self) -> None:
        if MQTT_TRANSPORT not in {"tcp", "websockets"}:
            raise ValueError("MQTT_TRANSPORT must be 'tcp' or 'websockets'")
        self.lock = threading.RLock()
        self.connected = False
        self.error: str | None = None
        self.latest_route: dict[str, Any] | None = None
        self.last_request_id: str | None = None
        # Responses are queued because a Streamlit rerun can happen less often
        # than the MQTT callback.  Only the main thread consumes this list.
        self.reservation_responses: list[dict[str, Any]] = []
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"ambulance-ui-{uuid.uuid4().hex[:8]}",
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
        self.client.loop_start()

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        with self.lock:
            self.connected = not reason_code.is_failure
            if self.connected:
                client.subscribe(
                    [(RESPONSE_TOPIC, 1), (RESERVATION_RESPONSE_TOPIC, 1)]
                )
                self.error = None
            else:
                self.error = f"MQTT connection failed: {reason_code}"

    def _on_disconnect(self, _client, _userdata, _disconnect_flags, reason_code, _properties) -> None:
        with self.lock:
            self.connected = False
            if reason_code != mqtt.MQTT_ERR_SUCCESS:
                self.error = f"MQTT disconnected: {reason_code}"

    def _on_message(self, _client, _userdata, message) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            if not isinstance(payload, dict) or payload.get("ev_id") != EV_ID:
                return
            if message.topic == RESPONSE_TOPIC:
                with self.lock:
                    # A delayed MQTT response must never move this ambulance
                    # after a newer route request has already been sent.
                    if payload.get("request_id") != self.last_request_id:
                        return
                    if "error" in payload:
                        self.latest_route = payload
                        self.error = str(payload["error"])
                        return
                    if not isinstance(payload.get("route"), list):
                        return
                    self.latest_route = payload
                    self.error = None
            elif message.topic == RESERVATION_RESPONSE_TOPIC:
                # The edge agent echoes the reservation ID.  Queue every
                # acknowledgement so requests can be dispatched one at a time
                # without losing a fast MQTT response between Streamlit runs.
                if not isinstance(payload.get("granted"), bool):
                    raise ValueError("reservation response requires boolean granted")
                with self.lock:
                    self.reservation_responses.append(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            with self.lock:
                self.error = f"Invalid MQTT response: {exc}"

    def request_route(
        self, start: int, end: int, excluded_nodes: list[int] | None = None
    ) -> bool:
        """Request a route, optionally avoiding FCFS-conflicted intersections."""
        request_id = uuid.uuid4().hex
        request = {
            "ev_id": EV_ID,
            "start": start,
            "end": end,
            "request_id": request_id,
            # The legacy orchestrator understands this optional field.  An
            # older one may ignore it, but the reservation rejection still
            # remains visible to the driver instead of moving through a clash.
            "excluded_nodes": sorted(set(excluded_nodes or [])),
        }
        with self.lock:
            if not self.connected:
                self.error = "Waiting for MQTT connection before requesting a route."
                return False
            self.last_request_id = request_id
            self.latest_route = None
        result = self.client.publish(REQUEST_TOPIC, json.dumps(request), qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            with self.lock:
                self.error = f"Could not publish request (MQTT status {result.rc})"
            return False
        with self.lock:
            self.error = None
        return True

    def request_reservation(self, reservation: dict[str, Any]) -> bool:
        """Publish one FCFS reservation request to the responsible edge node."""
        with self.lock:
            if not self.connected:
                self.error = "Waiting for MQTT connection before reserving an intersection."
                return False
        result = self.client.publish(
            RESERVATION_REQUEST_TOPIC, json.dumps(reservation), qos=1
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            with self.lock:
                self.error = f"Could not publish reservation (MQTT status {result.rc})"
            return False
        return True

    def cancel_reservations(self, reservations: list[dict[str, Any]]) -> None:
        """Release unused grants so a reroute does not block another EV.

        Cancellation is best-effort: reservations also expire naturally as the
        edge agent's 120-second rolling timeline advances.
        """
        with self.lock:
            connected = self.connected
        if not connected:
            return
        for reservation in reservations:
            payload = {
                key: reservation[key]
                for key in (
                    "node",
                    "ev_id",
                    "start_time",
                    "duration",
                    "axis",
                    "request_id",
                    "reservation_id",
                )
                if key in reservation
            }
            self.client.publish(RESERVATION_CANCEL_TOPIC, json.dumps(payload), qos=1)

    def take_reservation_responses(self) -> list[dict[str, Any]]:
        """Return and clear reservation acknowledgements received by Paho."""
        with self.lock:
            responses = [response.copy() for response in self.reservation_responses]
            self.reservation_responses.clear()
            return responses

    def clear_reservation_responses(self) -> None:
        """Discard acknowledgements from a route that has been superseded."""
        with self.lock:
            self.reservation_responses.clear()

    def snapshot(self) -> tuple[bool, str | None, dict[str, Any] | None]:
        with self.lock:
            return self.connected, self.error, self.latest_route.copy() if self.latest_route else None


@st.cache_resource(show_spinner=False)
def get_mqtt_worker() -> AmbulanceMqttWorker:
    return AmbulanceMqttWorker()


def initialize_trip_state() -> None:
    """Initialize state used by the main Streamlit run and its live fragment."""
    defaults: dict[str, Any] = {
        "simulation_running": False,
        "trip_completed": False,
        "current_node": None,
        "destination_node": None,
        "route_history": [],
        "total_travel_seconds": 0.0,
        "awaiting_route": False,
        "pending_route": None,
        "next_move_at": 0.0,
        "last_request_attempt_at": 0.0,
        "last_consumed_route_key": None,
        # Reservation dispatch is deliberately sequential: FCFS is decided by
        # the edge node before the next downstream slot is requested.
        "reservation_plan": [],
        "reservation_index": 0,
        "reservation_pending": None,
        "reservation_wait_started_at": 0.0,
        "reservation_grants": [],
        "reservation_results": [],
        "reservation_status": None,
        "reservation_deferred_count": 0,
        "reservation_rejection": None,
        "route_exclusions": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def request_from_current_location(
    worker: AmbulanceMqttWorker, excluded_nodes: list[int] | None = None
) -> bool:
    """Ask the cloud brain for a route from the ambulance's live position."""
    st.session_state.last_request_attempt_at = time.monotonic()
    if excluded_nodes is not None:
        st.session_state.route_exclusions = sorted(set(excluded_nodes))
    sent = worker.request_route(
        int(st.session_state.current_node),
        int(st.session_state.destination_node),
        list(st.session_state.route_exclusions),
    )
    st.session_state.awaiting_route = sent
    return sent


def begin_trip(worker: AmbulanceMqttWorker, start: int, destination: int) -> None:
    """Reset prior trip data and send the first routing request."""
    st.session_state.simulation_running = True
    st.session_state.trip_completed = False
    st.session_state.current_node = start
    st.session_state.destination_node = destination
    st.session_state.route_history = []
    st.session_state.total_travel_seconds = 0.0
    st.session_state.awaiting_route = False
    st.session_state.pending_route = None
    st.session_state.next_move_at = 0.0
    st.session_state.last_consumed_route_key = None
    st.session_state.reservation_plan = []
    st.session_state.reservation_index = 0
    st.session_state.reservation_pending = None
    st.session_state.reservation_wait_started_at = 0.0
    st.session_state.reservation_grants = []
    st.session_state.reservation_results = []
    st.session_state.reservation_status = None
    st.session_state.reservation_deferred_count = 0
    st.session_state.reservation_rejection = None
    st.session_state.route_exclusions = []
    worker.clear_reservation_responses()
    request_from_current_location(worker)


def route_key(route_message: dict[str, Any]) -> str:
    """Identify a response so the one-second UI fragment consumes it only once."""
    return str(route_message.get("request_id") or route_message.get("generated_at"))


def segment_eta_seconds(route_message: dict[str, Any]) -> list[float]:
    """Return one route ETA per hop, with an older-message fallback.

    The reservation timeline must use every segment's cumulative arrival time,
    not just the first segment.  Older orchestrators only publish a total ETA,
    so split it equally in that compatibility case.
    """
    route = route_message["route"]
    hop_count = max(0, len(route) - 1)
    raw_times = route_message.get("segment_eta_seconds")
    if isinstance(raw_times, list) and len(raw_times) == hop_count:
        try:
            return [max(0.0, float(value)) for value in raw_times]
        except (TypeError, ValueError):
            pass
    segments = route_message.get("segments")
    if isinstance(segments, list) and len(segments) == hop_count:
        try:
            return [max(0.0, float(segment["eta_seconds"])) for segment in segments]
        except (KeyError, TypeError, ValueError):
            pass
    total_eta = max(0.0, float(route_message.get("eta_seconds", 0.0)))
    return [total_eta / max(1, hop_count)] * hop_count


def first_segment_eta(route_message: dict[str, Any]) -> float:
    """Return the ETA for the next road segment."""
    segment_times = segment_eta_seconds(route_message)
    return segment_times[0] if segment_times else 0.0


def segment_details(route_message: dict[str, Any], index: int) -> dict[str, Any]:
    """Return phase-aware metadata for one segment, if the route supplied it."""
    segments = route_message.get("segments")
    if (
        isinstance(segments, list)
        and 0 <= index < len(segments)
        and isinstance(segments[index], dict)
    ):
        return segments[index]
    return {}


def first_segment_details(route_message: dict[str, Any]) -> dict[str, Any]:
    """Return phase-aware metadata for the imminent road segment, if present."""
    return segment_details(route_message, 0)


def hop_display_seconds_for_eta(eta_seconds: float) -> float:
    """Map a simulated ETA to the legacy UI's wall-clock movement cadence."""
    scaled_seconds = max(0.0, eta_seconds) * EV_SECONDS_PER_ETA_SECOND
    return max(MIN_HOP_DISPLAY_SECONDS, min(MAX_HOP_DISPLAY_SECONDS, scaled_seconds))


def hop_display_seconds(route_message: dict[str, Any]) -> float:
    """Return the wall-clock delay for the current route's next hop."""
    return hop_display_seconds_for_eta(first_segment_eta(route_message))


def route_segment_axis(segment: dict[str, Any], source: int, destination: int) -> str:
    """Get the incoming axis that the downstream intersection must hold green."""
    axis = segment.get("movement_axis", segment.get("direction"))
    if axis in {"NS", "EW"}:
        return str(axis)
    source_row, source_column = divmod(source, 5)
    destination_row, destination_column = divmod(destination, 5)
    if source_column == destination_column and abs(source_row - destination_row) == 1:
        return "NS"
    if source_row == destination_row and abs(source_column - destination_column) == 1:
        return "EW"
    raise ValueError(f"Route contains non-adjacent intersections {source} and {destination}")


def build_reservation_plan(route_message: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Build ordered FCFS requests from cumulative route arrival estimates.

    Each reservation targets the *downstream* node of a segment.  The request
    includes the entry axis because the edge signal controller needs it to hold
    the correct N/S or E/W green.  Only windows inside the edge agent's rolling
    horizon are sent; later nodes will be recalculated after the next hop.
    """
    route = [int(node) for node in route_message["route"]]
    route_request_id = str(route_message.get("request_id") or uuid.uuid4().hex)
    start_epoch = time.time()
    cumulative_wall_seconds = 0.0
    plan: list[dict[str, Any]] = []
    deferred_count = 0

    for index, eta_seconds in enumerate(segment_eta_seconds(route_message)):
        source, destination = route[index], route[index + 1]
        segment = segment_details(route_message, index)
        # The simulator's reservation timeline advances in real seconds.  Use
        # the same acceleration/clamp as the legacy visual movement so the
        # reserved slot and displayed ambulance position remain aligned.
        cumulative_wall_seconds += hop_display_seconds_for_eta(eta_seconds)
        start_time = int(math.ceil(start_epoch + cumulative_wall_seconds))
        if start_time - start_epoch + RESERVATION_DURATION_SECONDS > RESERVATION_HORIZON_SECONDS:
            deferred_count += 1
            continue
        reservation_id = f"{route_request_id}:{index}:{destination}:{start_time}"
        plan.append(
            {
                "node": destination,
                "ev_id": EV_ID,
                "start_time": start_time,
                "duration": RESERVATION_DURATION_SECONDS,
                "axis": route_segment_axis(segment, source, destination),
                "request_id": route_request_id,
                "reservation_id": reservation_id,
            }
        )
    return plan, deferred_count


def dispatch_next_reservation(worker: AmbulanceMqttWorker, now: float) -> None:
    """Publish the next FCFS request only after the previous reply arrives."""
    if st.session_state.reservation_pending is not None:
        return
    plan = st.session_state.reservation_plan
    index = int(st.session_state.reservation_index)
    if index >= len(plan):
        # Every visible downstream slot was granted.  It is now safe to move
        # the ambulance's first hop while the edge controller holds its slot.
        pending_route = st.session_state.pending_route
        if pending_route is not None:
            st.session_state.next_move_at = now + hop_display_seconds(pending_route)
            deferred = int(st.session_state.reservation_deferred_count)
            suffix = f"; {deferred} later slot(s) will be refreshed next hop" if deferred else ""
            st.session_state.reservation_status = (
                f"FCFS grants confirmed for {len(st.session_state.reservation_grants)} intersection(s){suffix}."
            )
        return

    reservation = dict(plan[index])
    if worker.request_reservation(reservation):
        st.session_state.reservation_pending = reservation
        st.session_state.reservation_wait_started_at = now
        st.session_state.reservation_status = (
            f"Requesting FCFS slot at intersection {reservation['node']} "
            f"for {reservation['start_time']} ({reservation['axis']})."
        )


def start_reservation_dispatch(
    worker: AmbulanceMqttWorker, route_message: dict[str, Any], now: float
) -> None:
    """Create and begin the sequential reservation batch for a new A* route."""
    plan, deferred_count = build_reservation_plan(route_message)
    st.session_state.reservation_plan = plan
    st.session_state.reservation_index = 0
    st.session_state.reservation_pending = None
    st.session_state.reservation_wait_started_at = 0.0
    st.session_state.reservation_grants = []
    st.session_state.reservation_deferred_count = deferred_count
    st.session_state.reservation_rejection = None
    worker.clear_reservation_responses()
    dispatch_next_reservation(worker, now)


def reservation_response_matches(
    response: dict[str, Any], expected: dict[str, Any]
) -> bool:
    """Match a response robustly, including older edge agents without IDs."""
    response_id = response.get("reservation_id")
    if response_id is not None:
        return response_id == expected.get("reservation_id")
    if response.get("request_id") is not None and response.get("request_id") != expected.get("request_id"):
        return False
    try:
        return (
            int(response.get("node")) == int(expected["node"])
            and int(response.get("start_time")) == int(expected["start_time"])
        )
    except (TypeError, ValueError):
        return False


def reject_reservation(
    worker: AmbulanceMqttWorker, reservation: dict[str, Any], reason: str
) -> None:
    """Cancel prior grants and immediately request an A* route around the clash."""
    rejected_node = int(reservation["node"])
    grants = [dict(grant) for grant in st.session_state.reservation_grants]
    worker.cancel_reservations(grants)
    worker.clear_reservation_responses()
    results = list(st.session_state.reservation_results)
    results.append(
        {
            "node": rejected_node,
            "axis": reservation.get("axis", "—"),
            "start_time": reservation.get("start_time"),
            "granted": False,
            "reason": reason,
        }
    )
    st.session_state.reservation_results = results
    st.session_state.reservation_rejection = rejected_node
    st.session_state.reservation_plan = []
    st.session_state.reservation_index = 0
    st.session_state.reservation_pending = None
    st.session_state.reservation_grants = []
    st.session_state.pending_route = None
    st.session_state.next_move_at = 0.0

    current_node = int(st.session_state.current_node)
    destination_node = int(st.session_state.destination_node)
    exclusions = list(st.session_state.route_exclusions)
    if rejected_node not in {current_node, destination_node}:
        exclusions.append(rejected_node)
        st.session_state.reservation_status = (
            f"FCFS rejected intersection {rejected_node} ({reason}); rerouting around it."
        )
    else:
        # A destination cannot be removed from A*.  A fresh request moves the
        # planned arrival window forward, modelling the later EV waiting rather
        # than illegally crossing an occupied intersection.
        st.session_state.reservation_status = (
            f"FCFS rejected required intersection {rejected_node} ({reason}); requesting a later slot."
        )
    request_from_current_location(worker, exclusions)


def process_reservation_responses(worker: AmbulanceMqttWorker, now: float) -> None:
    """Apply acknowledgements, advancing only when FCFS grants the current slot."""
    pending = st.session_state.reservation_pending
    for response in worker.take_reservation_responses():
        # Cancellation replies share the response topic but must not be
        # interpreted as a route reservation rejection.
        if response.get("cancelled"):
            continue
        if pending is None or not reservation_response_matches(response, pending):
            continue

        if bool(response.get("granted")):
            granted = dict(pending)
            granted["accepted_at"] = response.get("accepted_at")
            grants = list(st.session_state.reservation_grants)
            grants.append(granted)
            st.session_state.reservation_grants = grants
            results = list(st.session_state.reservation_results)
            results.append(
                {
                    "node": granted["node"],
                    "axis": granted["axis"],
                    "start_time": granted["start_time"],
                    "granted": True,
                    "reason": response.get("reason", "FCFS grant"),
                }
            )
            st.session_state.reservation_results = results
            st.session_state.reservation_index = int(st.session_state.reservation_index) + 1
            st.session_state.reservation_pending = None
            st.session_state.reservation_wait_started_at = 0.0
            dispatch_next_reservation(worker, now)
            pending = st.session_state.reservation_pending
        else:
            reject_reservation(worker, pending, str(response.get("reason", "conflict")))
            return


def check_reservation_timeout(worker: AmbulanceMqttWorker, now: float) -> None:
    """Treat a missing acknowledgement as unsafe instead of moving unreserved."""
    pending = st.session_state.reservation_pending
    wait_started = float(st.session_state.reservation_wait_started_at)
    if (
        pending is not None
        and wait_started > 0
        and now - wait_started >= RESERVATION_RESPONSE_TIMEOUT_SECONDS
    ):
        reject_reservation(worker, pending, "reservation response timeout")


def receive_route_if_ready(worker: AmbulanceMqttWorker, now: float) -> None:
    """Store a new A* route, then reserve its downstream intersection slots."""
    if not st.session_state.awaiting_route:
        return
    _connected, _error, route_message = worker.snapshot()
    if not route_message:
        return

    message_key = route_key(route_message)
    if message_key == st.session_state.last_consumed_route_key:
        return

    if route_message.get("error"):
        st.session_state.awaiting_route = False
        st.session_state.last_consumed_route_key = message_key
        return

    route = route_message.get("route")
    current_node = st.session_state.current_node
    destination_node = st.session_state.destination_node
    if (
        not isinstance(route, list)
        or not route
        or route[0] != current_node
        or route[-1] != destination_node
    ):
        return

    st.session_state.pending_route = route_message
    st.session_state.awaiting_route = False
    st.session_state.last_consumed_route_key = message_key
    start_reservation_dispatch(worker, route_message, now)


def move_one_hop(worker: AmbulanceMqttWorker, now: float) -> None:
    """Advance to the closest intersection on the latest route, then reroute."""
    route_message = st.session_state.pending_route
    # A route is not permission to move.  The first hop starts only after every
    # in-horizon downstream reservation has received an explicit FCFS grant.
    if (
        not route_message
        or st.session_state.reservation_pending is not None
        or int(st.session_state.reservation_index) < len(st.session_state.reservation_plan)
        or st.session_state.next_move_at <= 0
        or now < st.session_state.next_move_at
    ):
        return

    route = route_message["route"]
    current_node = int(st.session_state.current_node)
    if len(route) < 2:
        # This handles a response when the destination has already been reached.
        st.session_state.simulation_running = False
        st.session_state.trip_completed = True
        st.session_state.pending_route = None
        return

    next_node = int(route[1])
    leg_seconds = first_segment_eta(route_message)
    segment = first_segment_details(route_message)
    total_seconds = float(st.session_state.total_travel_seconds) + leg_seconds
    history = list(st.session_state.route_history)
    history.append(
        {
            "update": len(history) + 1,
            "from": current_node,
            "route": route,
            "moved_to": next_node,
            "leg_seconds": round(leg_seconds, 1),
            "total_seconds": round(total_seconds, 1),
            "traffic_version": route_message.get("traffic_version"),
            "light_phase": segment.get("source_light_phase", "—"),
            "signal_wait_seconds": segment.get("signal_delay_seconds", 0.0),
            "fcfs_grants": len(st.session_state.reservation_grants),
        }
    )
    st.session_state.route_history = history
    st.session_state.current_node = next_node
    st.session_state.total_travel_seconds = total_seconds
    st.session_state.pending_route = None
    st.session_state.next_move_at = 0.0

    # The arrival node's own reservation is being consumed now.  Future slots
    # from the old route must be released before the fresh A* calculation;
    # otherwise an abandoned route could unfairly block another ambulance.
    future_grants = [
        grant
        for grant in st.session_state.reservation_grants
        if int(grant.get("node", -1)) != next_node
        and int(grant.get("start_time", 0)) > int(time.time())
    ]
    worker.cancel_reservations(future_grants)
    st.session_state.reservation_plan = []
    st.session_state.reservation_index = 0
    st.session_state.reservation_pending = None
    st.session_state.reservation_grants = []
    st.session_state.reservation_deferred_count = 0

    if next_node == st.session_state.destination_node:
        st.session_state.simulation_running = False
        st.session_state.trip_completed = True
    else:
        request_from_current_location(worker)


def advance_trip(worker: AmbulanceMqttWorker) -> None:
    """Run the asynchronous request → route → move → reroute state machine."""
    if not st.session_state.simulation_running:
        return

    now = time.monotonic()
    process_reservation_responses(worker, now)
    receive_route_if_ready(worker, now)
    check_reservation_timeout(worker, now)
    move_one_hop(worker, now)
    if (
        st.session_state.simulation_running
        and not st.session_state.awaiting_route
        and not st.session_state.pending_route
        and now - st.session_state.last_request_attempt_at >= REQUEST_RETRY_SECONDS
    ):
        request_from_current_location(worker)


def route_panel(worker: AmbulanceMqttWorker) -> None:
    connected, error, route_message = worker.snapshot()
    st.caption(
        f"MQTT: {'connected' if connected else 'connecting / reconnecting'} · "
        f"broker: {BROKER_HOST}:{BROKER_PORT}"
    )
    if error:
        st.warning(error)
    current_node = st.session_state.current_node
    destination_node = st.session_state.destination_node
    history = st.session_state.route_history
    reservation_status = st.session_state.reservation_status

    if st.session_state.simulation_running:
        st.caption(
            f"Live position: intersection {current_node} · destination: {destination_node} · "
            "the ambulance reroutes after each hop."
        )
        pending_route = st.session_state.pending_route
        if pending_route:
            route = pending_route["route"]
            if len(route) >= 2:
                segment = first_segment_details(pending_route)
                signal_note = (
                    f" Source signal: {segment.get('source_light_phase', 'unknown')} "
                    f"({segment.get('source_active_direction', '—')}); "
                    f"signal wait: {float(segment.get('signal_delay_seconds', 0.0)):.1f}s."
                )
                reservation_pending = st.session_state.reservation_pending
                if reservation_pending:
                    movement_note = (
                        f"Waiting for FCFS approval at intersection "
                        f"{reservation_pending['node']} ({reservation_pending['axis']})."
                    )
                elif int(st.session_state.reservation_index) < len(st.session_state.reservation_plan):
                    movement_note = "Preparing the next downstream FCFS reservation."
                else:
                    seconds_to_move = max(0.0, st.session_state.next_move_at - time.monotonic())
                    movement_note = (
                        f"Moving next to intersection {route[1]} in {seconds_to_move:.1f}s."
                    )
                st.info(
                    f"Current shortest path: {' → '.join(str(node) for node in route)}. "
                    f"{movement_note} Traffic snapshot v{pending_route.get('traffic_version', '—')}."
                    f"{signal_note}"
                )
            else:
                st.info("The destination is the current intersection; completing the trip.")
        elif st.session_state.awaiting_route:
            st.info("Fetching the next shortest path from the ambulance's current location…")
        if reservation_status:
            st.caption(f"Reservation status: {reservation_status}")
    elif st.session_state.trip_completed:
        st.success(
            f"Destination {destination_node} reached. Simulation stopped — total estimated "
            f"emergency-vehicle travel time: {st.session_state.total_travel_seconds:.1f} seconds."
        )
    else:
        st.info("Choose intersections, then start the mobile route simulation.")

    if history:
        st.subheader("Updated shortest routes traveled")
        st.dataframe(
            [
                {
                    "Route update": entry["update"],
                    "Current node": entry["from"],
                    "Shortest path at this node": " → ".join(str(node) for node in entry["route"]),
                    "Moved to": entry["moved_to"],
                    "Leg ETA (s)": entry["leg_seconds"],
                    "Signal phase": entry["light_phase"],
                    "Signal wait (s)": entry["signal_wait_seconds"],
                    "FCFS grants": entry["fcfs_grants"],
                    "Traffic snapshot": entry["traffic_version"],
                    "Cumulative ETA (s)": entry["total_seconds"],
                }
                for entry in history
            ],
            hide_index=True,
            width="stretch",
        )
        st.metric("Accumulated estimated travel time", f"{st.session_state.total_travel_seconds:.1f} s")

    reservation_results = st.session_state.reservation_results
    if reservation_results:
        st.subheader("Spatio-temporal reservation audit")
        st.dataframe(
            [
                {
                    "Intersection": item["node"],
                    "Axis": item["axis"],
                    "Window starts (epoch s)": item["start_time"],
                    "FCFS result": "Granted" if item["granted"] else "Rejected",
                    "Reason": item["reason"],
                }
                for item in reservation_results[-20:]
            ],
            hide_index=True,
            width="stretch",
        )


def main() -> None:
    st.set_page_config(page_title="Ambulance Priority Route", page_icon="🚑")
    st.title("🚑 Ambulance Priority Route")
    st.caption(f"Vehicle ID: {EV_ID}")
    st.caption(
        "Signal-aware, FCFS-reserved routing: the ambulance reserves downstream "
        "intersection time windows, then reroutes after every hop."
    )
    worker = get_mqtt_worker()
    initialize_trip_state()
    simulation_running = st.session_state.simulation_running

    left, right = st.columns(2)
    with left:
        start = st.selectbox(
            "Starting Intersection",
            INTERSECTIONS,
            index=0,
            disabled=simulation_running,
        )
    with right:
        end = st.selectbox(
            "Destination Intersection",
            INTERSECTIONS,
            index=24,
            disabled=simulation_running,
        )

    start_column, stop_column = st.columns(2)
    with start_column:
        start_clicked = st.button(
            "Start Mobile Route Simulation",
            type="primary",
            width="stretch",
            disabled=simulation_running,
        )
    with stop_column:
        stop_clicked = st.button(
            "Stop Simulation",
            width="stretch",
            disabled=not simulation_running,
        )

    if start_clicked:
        if start == end:
            st.error("Starting intersection and destination must be different.")
        else:
            begin_trip(worker, start, end)
            st.toast("Mobile route simulation started. The ambulance will reroute after each hop.")

    if stop_clicked:
        worker.cancel_reservations(
            [dict(grant) for grant in st.session_state.reservation_grants]
        )
        worker.clear_reservation_responses()
        st.session_state.simulation_running = False
        st.session_state.awaiting_route = False
        st.session_state.pending_route = None
        st.session_state.reservation_plan = []
        st.session_state.reservation_pending = None
        st.session_state.reservation_grants = []
        st.session_state.reservation_status = "Trip stopped; unused reservations were cancelled."
        st.toast("Simulation stopped. You can now change the intersections.")

    # See the corresponding comment in AmbulanceMqttWorker: only the main
    # Streamlit run renders UI, which keeps the MQTT worker non-blocking.
    if hasattr(st, "fragment"):
        @st.fragment(run_every="1s")
        def live_route_panel() -> None:
            advance_trip(worker)
            route_panel(worker)

        live_route_panel()
    else:
        route_panel(worker)
        st.caption("Upgrade to Streamlit 1.37+ for automatic route updates, or refresh this page.")


if __name__ == "__main__":
    main()
