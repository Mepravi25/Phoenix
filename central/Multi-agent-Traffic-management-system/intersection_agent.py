"""Edge-side traffic simulator for the 5x5 city grid.

Install dependencies with: pip install paho-mqtt scikit-learn numpy
Run with: python intersection_agent.py

Set MQTT_BROKER (and optionally MQTT_PORT) to use a local broker.  The
defaults use the public test.mosquitto.org broker, which is suitable for demos.

Console stream logging is enabled by default so the generated grid can be
inspected without subscribing to MQTT:

* ``SIMULATION_LOG_INTERVAL_TICKS`` controls the interval in simulation ticks
  (default: ``5``; use ``0`` to disable the snapshot logs).
* ``SIMULATION_LOG_JSON=1`` additionally prints the complete JSON snapshot in
  the same shape sent to MQTT.  It is deliberately opt-in because it is noisy.
"""

from __future__ import annotations

import json
import math
import os
import random
import signal
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestRegressor

load_dotenv()

# .strip() makes CMD commands such as `set "MQTT_BROKER=127.0.0.1" && ...`
# robust if a trailing space is accidentally included before `&&`.
BROKER_HOST = os.getenv("MQTT_BROKER", "127.0.0.1").strip()
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883").strip())
MQTT_TRANSPORT = os.getenv("MQTT_TRANSPORT", "tcp").strip().lower()
MQTT_WS_PATH = os.getenv("MQTT_WS_PATH", "/mqtt").strip()
UPDATE_TOPIC = "city/intersections/update"
# The intersection process owns these topics.  Route planners request a short
# time slot, this edge process arbitrates it, and planners listen for the
# acknowledgement before committing an EV to the route.
RESERVATION_TOPIC = "city/intersections/reserve"
RESERVATION_RESPONSE_TOPIC = "city/intersections/reserve/response"
RESERVATION_CANCEL_TOPIC = "city/intersections/reserve/cancel"
GRID_SIZE = 5
NODE_COUNT = GRID_SIZE * GRID_SIZE


def read_non_negative_int_env(name: str, default: int) -> int:
    """Read a non-negative integer configuration value with a clear error."""
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be a non-negative integer, got {raw_value!r}.") from error
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {raw_value!r}.")
    return value


def read_bool_env(name: str, default: bool = False) -> bool:
    """Read common CMD-friendly true/false environment variable values."""
    raw_value = os.getenv(name, str(default)).strip().lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of 1/0, true/false, yes/no, or on/off.")


# The agent still simulates once a second and publishes every two seconds.  A
# five-tick console interval gives a useful, readable trace without flooding a
# terminal.  The first tick is always logged when this is non-zero.
SIMULATION_LOG_INTERVAL_TICKS = read_non_negative_int_env(
    "SIMULATION_LOG_INTERVAL_TICKS", 5
)
SIMULATION_LOG_JSON = read_bool_env("SIMULATION_LOG_JSON")

# A simulation iteration represents one second.  Green phases release a small
# platoon of vehicles; yellow permits only one final vehicle to clear.
GREEN_DURATION_TICKS = 15
YELLOW_DURATION_TICKS = 3
DISCHARGE_RATE = 3
YELLOW_DISCHARGE_RATE = 1
MAX_QUEUE_LENGTH = 40

# The slot map is deliberately short.  A two-minute horizon is long enough to
# form a useful green wave across this 5x5 demo city without allowing a route
# planner to lock a junction far into the future.
RESERVATION_HORIZON_SECONDS = 120
# A direction change must leave one yellow interval between reservations.  It
# prevents an FCFS-adjacent N/S and E/W slot from forcing an unsafe instant
# green swap at the same junction.
RESERVATION_CLEARANCE_TICKS = YELLOW_DURATION_TICKS
# A cancelled request ID is remembered for the whole reservation horizon.  It
# closes the QoS-1 race where a cancel reaches the broker before its delayed
# reserve message.
CANCELLED_REQUEST_TTL_SECONDS = RESERVATION_HORIZON_SECONDS

PHASE_SEQUENCE = ("NS_GREEN", "YELLOW", "EW_GREEN", "YELLOW")
PHASE_DURATIONS = (
    GREEN_DURATION_TICKS,
    YELLOW_DURATION_TICKS,
    GREEN_DURATION_TICKS,
    YELLOW_DURATION_TICKS,
)

RUNNING = True
CONNECTED = threading.Event()
# Traffic telemetry is useful only after the edge process can also receive
# reservation commands.  The retained traffic snapshot advertises this flag
# so FastAPI never mistakes an older, traffic-only agent for a controller.
CONTROL_SUBSCRIPTIONS_READY = threading.Event()
CONTROL_SUBSCRIBE_MIDS: set[int] = set()
CONTROL_SUBSCRIBE_LOCK = threading.Lock()


@dataclass(frozen=True)
class Reservation:
    """An exclusive EV time slot at one intersection.

    ``start_time`` and ``end_time`` are Unix epoch seconds.  The direction is
    the outbound axis the EV needs while it is in the junction, which lets the
    signal controller create the correct temporary green wave.
    """

    node: int
    ev_id: str
    start_time: int
    duration: int
    axis: str
    request_id: str | None = None
    reservation_id: str | None = None

    @property
    def end_time(self) -> int:
        return self.start_time + self.duration


@dataclass(frozen=True)
class ReservationDecision:
    """A testable result for a reservation request or cancellation."""

    granted: bool
    reason: str
    reservation: Reservation | None = None
    cancelled: bool = False


class ReservationManager:
    """FCFS bitwise reservation timelines for every city intersection.

    Each node owns a 120-bit integer.  Bit ``k`` represents the second
    ``base_time + k``.  The fast integer collision check keeps high-rate MQTT
    reservation arbitration deterministic, while a small reservation metadata
    list supplies the EV ID and requested signal axis to the controller.

    The public :meth:`reserve` method intentionally returns a bool to match
    the stated protocol contract.  :meth:`reserve_with_details` is used by the
    MQTT callback so it can give an actionable rejection reason to a planner.
    """

    def __init__(
        self,
        horizon_seconds: int = RESERVATION_HORIZON_SECONDS,
        *,
        initial_time: int | None = None,
    ) -> None:
        if horizon_seconds <= 0:
            raise ValueError("horizon_seconds must be positive")
        self.horizon_seconds = horizon_seconds
        self._base_time = int(time.time()) if initial_time is None else int(initial_time)
        self._timelines = {node: 0 for node in range(NODE_COUNT)}
        self._reservations: dict[int, list[Reservation]] = {
            node: [] for node in range(NODE_COUNT)
        }
        # IDs are used only to suppress a delayed reserve after its route was
        # abandoned.  Values are expiry timestamps, so the set cannot grow
        # forever in a long-running edge process.
        self._cancelled_identifiers: dict[str, int] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _normalise_axis(axis: str | None) -> str | None:
        if axis is None:
            return None
        normalised = axis.strip().upper()
        return normalised if normalised in {"NS", "EW"} else None

    @staticmethod
    def _identifier_values(
        request_id: str | None, reservation_id: str | None
    ) -> tuple[str, ...]:
        return tuple(
            value.strip()
            for value in (request_id, reservation_id)
            if isinstance(value, str) and value.strip()
        )

    def _prune_cancelled_locked(self, current_time: int) -> None:
        self._cancelled_identifiers = {
            identifier: expiry
            for identifier, expiry in self._cancelled_identifiers.items()
            if expiry > current_time
        }

    def _rebuild_node_timeline_locked(self, node: int) -> None:
        """Rebuild one bitmask from absolute-time metadata after a mutation."""
        timeline = 0
        retained: list[Reservation] = []
        horizon_end = self._base_time + self.horizon_seconds
        for reservation in self._reservations[node]:
            if reservation.end_time <= self._base_time:
                continue
            retained.append(reservation)
            window_start = max(reservation.start_time, self._base_time)
            window_end = min(reservation.end_time, horizon_end)
            if window_end <= window_start:
                continue
            offset = window_start - self._base_time
            duration = window_end - window_start
            window_mask = ((1 << duration) - 1) << offset
            timeline |= window_mask
        self._reservations[node] = retained
        self._timelines[node] = timeline

    def _shift_time(self, current_time: int) -> None:
        """Right-shift all timelines as real time advances.

        This method is intentionally public-ish (single underscore) because it
        is a useful focused unit-test target for the bitmask behaviour required
        by the architecture.  Callers should normally use the other methods,
        which hold the lock for them.
        """
        now = int(current_time)
        with self._lock:
            if now <= self._base_time:
                self._prune_cancelled_locked(now)
                return
            elapsed = now - self._base_time
            if elapsed >= self.horizon_seconds:
                for node in range(NODE_COUNT):
                    self._timelines[node] = 0
                    self._reservations[node] = [
                        reservation
                        for reservation in self._reservations[node]
                        if reservation.end_time > now
                    ]
                    self._rebuild_node_timeline_locked(node)
            else:
                for node in range(NODE_COUNT):
                    self._timelines[node] >>= elapsed
                    self._reservations[node] = [
                        reservation
                        for reservation in self._reservations[node]
                        if reservation.end_time > now
                    ]
            self._base_time = now
            # The metadata list is the source of truth.  Rebuild after a shift
            # so a reservation that began before this second remains correctly
            # represented at bit zero for its remaining duration.
            for node in range(NODE_COUNT):
                self._rebuild_node_timeline_locked(node)
            self._prune_cancelled_locked(now)

    def reserve(
        self,
        node: int,
        start_time: int,
        duration: int,
        ev_id: str,
        *,
        axis: str | None = None,
        request_id: str | None = None,
        reservation_id: str | None = None,
        current_time: int | None = None,
    ) -> bool:
        """Reserve an unoccupied bit window using FCFS arbitration.

        The boolean return value is the protocol's minimal contract.  Use
        :meth:`reserve_with_details` when an MQTT response needs the reason.
        """
        return self.reserve_with_details(
            node,
            start_time,
            duration,
            ev_id,
            axis=axis,
            request_id=request_id,
            reservation_id=reservation_id,
            current_time=current_time,
        ).granted

    def reserve_with_details(
        self,
        node: int,
        start_time: int,
        duration: int,
        ev_id: str,
        *,
        axis: str | None = None,
        request_id: str | None = None,
        reservation_id: str | None = None,
        current_time: int | None = None,
    ) -> ReservationDecision:
        """Attempt an FCFS reservation and return a diagnostic decision."""
        now = int(time.time()) if current_time is None else int(current_time)
        normalised_axis = self._normalise_axis(axis)
        try:
            node = int(node)
            start_time = int(start_time)
            duration = int(duration)
        except (TypeError, ValueError):
            return ReservationDecision(False, "invalid_numeric_field")
        if node not in self._timelines:
            return ReservationDecision(False, "invalid_node")
        if not isinstance(ev_id, str) or not ev_id.strip():
            return ReservationDecision(False, "invalid_ev_id")
        if normalised_axis is None:
            # The required minimal payload predates signal pre-emption.  Axis
            # is intentionally required by this implementation because forcing
            # an unknown movement green would be unsafe.
            return ReservationDecision(False, "axis_required")
        if duration <= 0:
            return ReservationDecision(False, "invalid_duration")

        reservation = Reservation(
            node=node,
            ev_id=ev_id.strip(),
            start_time=start_time,
            duration=duration,
            axis=normalised_axis,
            request_id=request_id.strip() if isinstance(request_id, str) and request_id.strip() else None,
            reservation_id=(
                reservation_id.strip()
                if isinstance(reservation_id, str) and reservation_id.strip()
                else None
            ),
        )
        with self._lock:
            self._shift_time(now)
            identifiers = self._identifier_values(
                reservation.request_id, reservation.reservation_id
            )
            if any(identifier in self._cancelled_identifiers for identifier in identifiers):
                return ReservationDecision(False, "cancelled_before_grant", reservation)

            # MQTT QoS 1 may redeliver the same message.  Treat an exact
            # duplicate as success rather than falsely reporting a conflict.
            for existing in self._reservations[node]:
                same_identifier = bool(
                    reservation.reservation_id
                    and reservation.reservation_id == existing.reservation_id
                ) or bool(
                    reservation.request_id and reservation.request_id == existing.request_id
                )
                same_window = (
                    reservation.ev_id == existing.ev_id
                    and reservation.start_time == existing.start_time
                    and reservation.duration == existing.duration
                    and reservation.axis == existing.axis
                )
                if same_identifier or same_window:
                    if same_window:
                        return ReservationDecision(True, "already_granted", existing)
                    return ReservationDecision(False, "identifier_conflict", reservation)

            # The requested window must lie entirely in the next horizon.
            offset = reservation.start_time - self._base_time
            if offset < 0:
                return ReservationDecision(False, "start_time_in_past", reservation)
            if offset + reservation.duration > self.horizon_seconds:
                return ReservationDecision(False, "outside_horizon", reservation)

            # FCFS collision test: any occupied bit denies the later request.
            window_mask = ((1 << reservation.duration) - 1) << offset
            if self._timelines[node] & window_mask:
                return ReservationDecision(False, "conflict", reservation)

            # The bitwise contract protects exact overlap.  A different axis
            # immediately before/after an accepted window also needs yellow
            # clearance, otherwise two non-overlapping reservations could
            # still force an unsafe instantaneous green swap.
            for existing in self._reservations[node]:
                if existing.axis == reservation.axis:
                    continue
                has_clearance_before = (
                    reservation.end_time
                    <= existing.start_time - RESERVATION_CLEARANCE_TICKS
                )
                has_clearance_after = (
                    reservation.start_time
                    >= existing.end_time + RESERVATION_CLEARANCE_TICKS
                )
                if not (has_clearance_before or has_clearance_after):
                    return ReservationDecision(
                        False, "signal_clearance_required", reservation
                    )

            self._timelines[node] |= window_mask
            self._reservations[node].append(reservation)
            self._reservations[node].sort(key=lambda item: (item.start_time, item.ev_id))
            return ReservationDecision(True, "granted", reservation)

    def cancel_with_details(
        self,
        node: int,
        ev_id: str,
        *,
        start_time: int | None = None,
        duration: int | None = None,
        axis: str | None = None,
        request_id: str | None = None,
        reservation_id: str | None = None,
        current_time: int | None = None,
    ) -> ReservationDecision:
        """Release a prior slot and suppress a delayed matching reserve.

        A caller normally supplies a request or reservation ID.  The fallback
        full-window match keeps the method usable with the minimal protocol.
        Cancellation is deliberately idempotent: cancelling an already absent
        reservation is still a successful lifecycle action.
        """
        now = int(time.time()) if current_time is None else int(current_time)
        try:
            node = int(node)
        except (TypeError, ValueError):
            return ReservationDecision(False, "invalid_node", cancelled=False)
        if node not in self._timelines:
            return ReservationDecision(False, "invalid_node", cancelled=False)
        if not isinstance(ev_id, str) or not ev_id.strip():
            return ReservationDecision(False, "invalid_ev_id", cancelled=False)

        normalised_axis = self._normalise_axis(axis)
        try:
            normalised_start_time = int(start_time) if start_time is not None else None
            normalised_duration = int(duration) if duration is not None else None
        except (TypeError, ValueError):
            return ReservationDecision(False, "invalid_numeric_field", cancelled=False)
        clean_request_id = request_id.strip() if isinstance(request_id, str) and request_id.strip() else None
        clean_reservation_id = (
            reservation_id.strip()
            if isinstance(reservation_id, str) and reservation_id.strip()
            else None
        )
        with self._lock:
            self._shift_time(now)
            identifiers = self._identifier_values(clean_request_id, clean_reservation_id)
            expiry = now + max(CANCELLED_REQUEST_TTL_SECONDS, self.horizon_seconds)
            for identifier in identifiers:
                self._cancelled_identifiers[identifier] = expiry

            removed: Reservation | None = None
            retained: list[Reservation] = []
            for existing in self._reservations[node]:
                matches_identifier = bool(
                    clean_reservation_id
                    and existing.reservation_id == clean_reservation_id
                    and existing.ev_id == ev_id.strip()
                ) or bool(
                    clean_request_id
                    and existing.request_id == clean_request_id
                    and existing.ev_id == ev_id.strip()
                )
                matches_window = (
                    not identifiers
                    and existing.ev_id == ev_id.strip()
                    and (
                        normalised_start_time is None
                        or existing.start_time == normalised_start_time
                    )
                    and (
                        normalised_duration is None
                        or existing.duration == normalised_duration
                    )
                    and (normalised_axis is None or existing.axis == normalised_axis)
                )
                if matches_identifier or matches_window:
                    if removed is None:
                        removed = existing
                    continue
                retained.append(existing)
            self._reservations[node] = retained
            self._rebuild_node_timeline_locked(node)

            # Return the actual removed reservation when available so the
            # acknowledgement can accurately echo the committed window.
            requested = removed or Reservation(
                node=node,
                ev_id=ev_id.strip(),
                start_time=normalised_start_time if normalised_start_time is not None else now,
                duration=normalised_duration if normalised_duration is not None else 0,
                axis=normalised_axis or "NS",
                request_id=clean_request_id,
                reservation_id=clean_reservation_id,
            )
            return ReservationDecision(True, "cancelled", requested, cancelled=True)

    def active_reservations(self, current_time: int | None = None) -> dict[int, Reservation]:
        """Return the one active slot (if any) for each node at this second."""
        now = int(time.time()) if current_time is None else int(current_time)
        with self._lock:
            self._shift_time(now)
            return {
                node: next(
                    reservation
                    for reservation in reservations
                    if reservation.start_time <= now < reservation.end_time
                )
                for node, reservations in self._reservations.items()
                if any(
                    reservation.start_time <= now < reservation.end_time
                    for reservation in reservations
                )
            }

    def summary(self, current_time: int | None = None) -> dict[str, int]:
        """Small telemetry/logging summary without exposing every future slot."""
        now = int(time.time()) if current_time is None else int(current_time)
        with self._lock:
            self._shift_time(now)
            active = 0
            scheduled = 0
            for reservations in self._reservations.values():
                for reservation in reservations:
                    if reservation.start_time <= now < reservation.end_time:
                        active += 1
                    elif reservation.start_time > now:
                        scheduled += 1
            return {"active": active, "scheduled": scheduled}


@dataclass
class TrafficLight:
    """One independently phased signal controller for a grid intersection.

    ``phase_index`` distinguishes the two outwardly identical yellow phases:
    index 1 clears N/S movements and index 3 clears E/W movements.  MQTT only
    publishes the requested public phase name, ``YELLOW``.  A reservation
    temporarily takes priority over this normal controller, then releases
    through a yellow-clearance stage before normal cycling resumes.
    """

    phase_index: int = 0
    ticks_in_phase: int = 0
    _override_axis: str | None = None
    _override_end_time: int | None = None
    _last_clock_time: int | None = None
    _recovery_axis: str | None = None
    _recovery_ticks_remaining: int = 0

    @property
    def phase(self) -> str:
        if self._override_axis is not None:
            return f"{self._override_axis}_GREEN"
        if self._recovery_axis is not None:
            return "YELLOW"
        return PHASE_SEQUENCE[self.phase_index]

    @property
    def normal_phase(self) -> str:
        """Return the paused ordinary phase, even during an EV override."""
        return PHASE_SEQUENCE[self.phase_index]

    @property
    def permitted_direction(self) -> str | None:
        if self._override_axis is not None:
            return self._override_axis
        if self._recovery_axis is not None:
            return self._recovery_axis
        if self.phase_index in (0, 1):
            return "NS"
        if self.phase_index in (2, 3):
            return "EW"
        return None

    @property
    def normal_permitted_direction(self) -> str | None:
        """Return the movement the ordinary controller would currently allow."""
        if self.phase_index in (0, 1):
            return "NS"
        if self.phase_index in (2, 3):
            return "EW"
        return None

    @property
    def discharge_rate(self) -> int:
        return YELLOW_DISCHARGE_RATE if self.phase == "YELLOW" else DISCHARGE_RATE

    @property
    def phase_remaining_ticks(self) -> int:
        """Return the number of whole simulation ticks left in this phase."""
        if self._override_axis is not None:
            # Existing dashboard/API consumers validate normal green values as
            # 0..15.  The exact longer reservation duration is published in a
            # separate field; this compatibility value remains bounded.
            remaining = max(
                1,
                (self._override_end_time or 0) - (self._last_clock_time or 0),
            )
            return min(GREEN_DURATION_TICKS, remaining)
        if self._recovery_axis is not None:
            return self._recovery_ticks_remaining
        return PHASE_DURATIONS[self.phase_index] - self.ticks_in_phase

    @property
    def reservation_remaining_ticks(self) -> int:
        """Return the exact remaining pre-emption window, if one is active."""
        if self._override_axis is None:
            return 0
        return max(
            0,
            (self._override_end_time or 0) - (self._last_clock_time or 0),
        )

    @property
    def preemption_active(self) -> bool:
        return self._override_axis is not None

    def _advance_normal_cycle(self) -> None:
        """Advance the ordinary NS/yellow/EW/yellow state machine once."""
        self.ticks_in_phase += 1
        if self.ticks_in_phase >= PHASE_DURATIONS[self.phase_index]:
            self.phase_index = (self.phase_index + 1) % len(PHASE_SEQUENCE)
            self.ticks_in_phase = 0

    def advance(
        self,
        active_reservation: Reservation | None = None,
        *,
        current_time: int | None = None,
    ) -> None:
        """Advance the controller, honouring a current reservation if present.

        While a reservation is active the ordinary cycle is paused and the
        requested axis is held green.  Once it clears, three yellow ticks on
        that same axis act as a safe clearance interval.  The paused regular
        phase then continues, avoiding a sudden contradictory green.
        """
        now = int(time.time()) if current_time is None else int(current_time)
        self._last_clock_time = now

        if active_reservation is not None:
            self._override_axis = active_reservation.axis
            self._override_end_time = active_reservation.end_time
            # A contiguous same-axis extension is safe.  A newly active slot
            # supersedes a pending recovery because it owns this exact second.
            self._recovery_axis = None
            self._recovery_ticks_remaining = 0
            return

        if self._override_axis is not None:
            # The slot ended between simulation ticks: leave the forced green
            # through yellow rather than snapping to a potentially conflicting
            # normal green movement.
            self._recovery_axis = self._override_axis
            self._recovery_ticks_remaining = YELLOW_DURATION_TICKS
            self._override_axis = None
            self._override_end_time = None
            return

        if self._recovery_axis is not None:
            self._recovery_ticks_remaining -= 1
            if self._recovery_ticks_remaining <= 0:
                self._recovery_axis = None
                self._recovery_ticks_remaining = 0
            return

        self._advance_normal_cycle()


def build_adjacency_map() -> dict[int, dict[str, list[int]]]:
    """Return 5x5-grid neighbours grouped by permitted movement direction."""
    adjacency: dict[int, dict[str, list[int]]] = {}
    for node in range(NODE_COUNT):
        row, column = divmod(node, GRID_SIZE)
        north_south: list[int] = []
        east_west: list[int] = []
        if row > 0:
            north_south.append(node - GRID_SIZE)
        if row < GRID_SIZE - 1:
            north_south.append(node + GRID_SIZE)
        if column > 0:
            east_west.append(node - 1)
        if column < GRID_SIZE - 1:
            east_west.append(node + 1)
        adjacency[node] = {"NS": north_south, "EW": east_west}
    return adjacency


def build_traffic_lights(rng: random.Random) -> dict[int, TrafficLight]:
    """Create desynchronised signals by placing each controller on its cycle."""
    cycle_length = sum(PHASE_DURATIONS)
    lights: dict[int, TrafficLight] = {}
    for node in range(NODE_COUNT):
        controller = TrafficLight()
        for _ in range(rng.randrange(cycle_length)):
            controller.advance()
        lights[node] = controller
    return lights


def simulate_network_step(
    queues: list[int],
    adjacency: dict[int, dict[str, list[int]]],
    traffic_lights: dict[int, TrafficLight],
    rng: random.Random,
    reservation_manager: ReservationManager | None = None,
    *,
    current_time: int | None = None,
) -> list[int]:
    """Move one second of traffic through the signal-controlled city grid.

    Transfers are accumulated into a fresh queue vector, so a vehicle that
    reaches a neighbour this tick cannot be discharged a second time until the
    following tick.  Local baseline noise is deliberately applied last.  An
    active reservation only affects its *own* immediate intersection signal;
    vehicles on other nodes continue under their normal local controllers.
    """
    if len(queues) != NODE_COUNT:
        raise ValueError(f"Expected {NODE_COUNT} queues, got {len(queues)}.")

    now = int(time.time()) if current_time is None else int(current_time)
    active_reservations = (
        reservation_manager.active_reservations(now)
        if reservation_manager is not None
        else {}
    )

    # Every controller advances before a movement decision is made.  A
    # currently reserved node pauses its ordinary cycle and holds the requested
    # direction green for the reservation's exact active seconds.
    for node, light in traffic_lights.items():
        light.advance(active_reservations.get(node), current_time=now)

    next_queues = queues.copy()
    for node, queue_length in enumerate(queues):
        light = traffic_lights[node]
        direction = light.permitted_direction
        allowed_neighbours = adjacency[node][direction] if direction else []
        if queue_length <= 0 or not allowed_neighbours:
            continue

        discharged = min(queue_length, light.discharge_rate)
        next_queues[node] -= discharged
        vehicles_per_neighbour, remainder = divmod(discharged, len(allowed_neighbours))
        for position, neighbour in enumerate(allowed_neighbours):
            next_queues[neighbour] += vehicles_per_neighbour + (position < remainder)

    # Preserve the original local stochastic source/sink noise exactly: it is
    # applied only after all traffic-light-controlled transfers are complete.
    local_source = [rng.randint(-2, 3) for _ in range(NODE_COUNT)]
    return [
        max(0, min(MAX_QUEUE_LENGTH, queue + local_source[node]))
        for node, queue in enumerate(next_queues)
    ]


def build_mock_model() -> RandomForestRegressor:
    """Create a deterministic stand-in for a pre-trained traffic model.

    Replace this function with ``joblib.load(...)`` when a real trained model is
    available.  The model estimates how many seconds a queue will take to clear.
    """
    rng = np.random.default_rng(42)
    queue_lengths = np.arange(0, 41, dtype=float).reshape(-1, 1)
    flush_times = 2.0 + (queue_lengths.ravel() * 0.8) + rng.normal(0, 0.6, 41)
    model = RandomForestRegressor(n_estimators=80, random_state=42)
    model.fit(queue_lengths, flush_times)
    return model


MODEL = build_mock_model()


def predict_flush_time(queue_length: int) -> int:
    """Predict a positive, whole-number queue clearing time in seconds."""
    prediction = MODEL.predict(np.array([[queue_length]], dtype=float))[0]
    return max(1, math.ceil(float(prediction)))


def build_traffic_payload(
    queues: list[int],
    traffic_lights: dict[int, TrafficLight],
    simulation_tick: int,
    generated_at: float,
    reservation_manager: ReservationManager | None = None,
) -> list[dict[str, object]]:
    """Build the full grid snapshot used for both MQTT and terminal logging."""
    active_reservations = (
        reservation_manager.active_reservations(int(generated_at))
        if reservation_manager is not None
        else {}
    )
    return [
        {
            "node": node,
            "queue_length": queues[node],
            "flush_time": predict_flush_time(queue),
            "light_phase": traffic_lights[node].phase,
            # ``YELLOW`` alone does not identify which movements can still
            # clear, so publish the active axis and remaining time for the
            # phase-aware routing service as well.
            "active_direction": traffic_lights[node].permitted_direction,
            "phase_remaining_ticks": traffic_lights[node].phase_remaining_ticks,
            # Reservation metadata is additive, keeping prior traffic-only
            # consumers compatible while allowing the orchestration API and
            # dashboard to explain an emergency green wave.
            "preemption_active": traffic_lights[node].preemption_active,
            "reserved_axis": (
                active_reservations[node].axis if node in active_reservations else None
            ),
            "reservation_ev_id": (
                active_reservations[node].ev_id if node in active_reservations else None
            ),
            "reservation_remaining_ticks": traffic_lights[node].reservation_remaining_ticks,
            "reservation_end_time": (
                active_reservations[node].end_time if node in active_reservations else None
            ),
            # These fields make the operator UI explain the actual override:
            # for example, normal EW traffic was temporarily held while an EV
            # reservation forced N/S green. They are absent for ordinary rows.
            "preempted_from_phase": (
                traffic_lights[node].normal_phase
                if traffic_lights[node].preemption_active
                else None
            ),
            "preempted_from_direction": (
                traffic_lights[node].normal_permitted_direction
                if traffic_lights[node].preemption_active
                else None
            ),
            "reservation_control_ready": CONTROL_SUBSCRIPTIONS_READY.is_set(),
            "simulation_tick": simulation_tick,
            "generated_at": generated_at,
        }
        for node, queue in enumerate(queues)
    ]


def format_grid(values: list[int]) -> str:
    """Render 25 values as a compact five-row grid for the terminal."""
    return "\n".join(
        "  " + " ".join(f"{value:>3}" for value in values[row : row + GRID_SIZE])
        for row in range(0, NODE_COUNT, GRID_SIZE)
    )


def summarize_light_phases(traffic_lights: dict[int, TrafficLight]) -> str:
    """Summarise green axes and the two direction-specific yellow phases."""
    counts = {
        "NS_GREEN": 0,
        "YELLOW(NS)": 0,
        "EW_GREEN": 0,
        "YELLOW(EW)": 0,
    }
    for light in traffic_lights.values():
        if light.phase == "YELLOW":
            counts[f"YELLOW({light.permitted_direction})"] += 1
        else:
            counts[light.phase] += 1
    return " | ".join(f"{phase}={count}" for phase, count in counts.items())


def should_log_stream(simulation_tick: int) -> bool:
    """Log an initial snapshot, then only at the configured tick interval."""
    return SIMULATION_LOG_INTERVAL_TICKS > 0 and (
        simulation_tick == 1 or simulation_tick % SIMULATION_LOG_INTERVAL_TICKS == 0
    )


def log_traffic_stream(
    payload: list[dict[str, object]],
    traffic_lights: dict[int, TrafficLight],
    mqtt_connected: bool,
    publish_due: bool,
    reservation_manager: ReservationManager | None = None,
) -> None:
    """Print a human-readable view of the same 25-node snapshot sent to MQTT."""
    simulation_tick = int(payload[0]["simulation_tick"])
    queue_lengths = [int(item["queue_length"]) for item in payload]
    flush_times = [int(item["flush_time"]) for item in payload]
    stream_action = "publish due" if publish_due else "snapshot only"

    print(
        "[traffic stream] "
        f"tick={simulation_tick} | mqtt={'connected' if mqtt_connected else 'disconnected'} "
        f"| {stream_action} | total_queue={sum(queue_lengths)} "
        f"| max_queue={max(queue_lengths)}",
        flush=True,
    )
    print(f"[traffic stream] phases: {summarize_light_phases(traffic_lights)}", flush=True)
    if reservation_manager is not None:
        summary = reservation_manager.summary(int(float(payload[0]["generated_at"])))
        print(
            "[traffic stream] EV reservations: "
            f"active={summary['active']} | scheduled={summary['scheduled']}",
            flush=True,
        )
        active_nodes = [
            (
                f"#{item['node']}:{item['reserved_axis']}"
                f"/{item['reservation_ev_id']}"
                f" ({item['reservation_remaining_ticks']}s)"
            )
            for item in payload
            if item.get("preemption_active")
        ]
        if active_nodes:
            print(
                "[traffic stream] active green waves: " + ", ".join(active_nodes),
                flush=True,
            )
    print(f"[traffic stream] queues (nodes 0-24):\n{format_grid(queue_lengths)}", flush=True)
    print(f"[traffic stream] flush seconds (nodes 0-24):\n{format_grid(flush_times)}", flush=True)
    if SIMULATION_LOG_JSON:
        print(
            "[traffic stream] MQTT JSON payload:\n"
            + json.dumps(payload, indent=2, separators=(",", ": ")),
            flush=True,
        )


def _optional_text(value: object) -> str | None:
    """Return a non-empty string for correlation fields, otherwise ``None``."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def _response_value(
    reservation: Reservation | None,
    request: dict[str, object],
    name: str,
    default: object = None,
) -> object:
    """Prefer committed metadata, then echo the caller's request value."""
    if reservation is not None:
        if name == "node":
            return reservation.node
        if name == "ev_id":
            return reservation.ev_id
        if name == "start_time":
            return reservation.start_time
        if name == "duration":
            return reservation.duration
        if name == "axis":
            return reservation.axis
        if name == "request_id":
            return reservation.request_id
        if name == "reservation_id":
            return reservation.reservation_id
    return request.get(name, default)


def reservation_response_payload(
    decision: ReservationDecision,
    request: dict[str, object],
    *,
    accepted_at: int,
) -> dict[str, object]:
    """Create the stable JSON reply shared by grants, rejections, and cancels."""
    reservation = decision.reservation
    response: dict[str, object] = {
        "node": _response_value(reservation, request, "node"),
        "ev_id": _response_value(reservation, request, "ev_id"),
        "granted": decision.granted,
        "start_time": _response_value(reservation, request, "start_time"),
        "duration": _response_value(reservation, request, "duration"),
        "axis": _response_value(
            reservation,
            request,
            "axis",
            request.get("direction"),
        ),
        "request_id": _response_value(reservation, request, "request_id"),
        "reservation_id": _response_value(reservation, request, "reservation_id"),
        "reason": decision.reason,
        "accepted_at": accepted_at,
    }
    if decision.cancelled:
        response["cancelled"] = True
    return response


def handle_reservation_message(
    raw_payload: bytes | str | dict[str, object],
    reservation_manager: ReservationManager,
    *,
    cancel: bool = False,
    current_time: int | None = None,
) -> dict[str, object]:
    """Parse and arbitrate a reservation MQTT payload without Paho coupling.

    Keeping this helper free of MQTT client state makes the FCFS protocol easy
    to test directly with JSON-like dictionaries.
    """
    now = int(time.time()) if current_time is None else int(current_time)
    request: dict[str, object] = {}
    try:
        if isinstance(raw_payload, bytes):
            decoded = raw_payload.decode("utf-8")
            parsed: object = json.loads(decoded)
        elif isinstance(raw_payload, str):
            parsed = json.loads(raw_payload)
        else:
            parsed = raw_payload
        if not isinstance(parsed, dict):
            raise ValueError("payload must be a JSON object")
        request = dict(parsed)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        return reservation_response_payload(
            ReservationDecision(False, f"invalid_payload: {error}"),
            request,
            accepted_at=now,
        )

    # ``direction`` is accepted as a migration-friendly alias.  Responses use
    # the clearer ``axis`` name, but preserve the prompt's required fields.
    axis = request.get("axis", request.get("direction"))
    if cancel:
        decision = reservation_manager.cancel_with_details(
            request.get("node"),  # type: ignore[arg-type]
            request.get("ev_id"),  # type: ignore[arg-type]
            start_time=request.get("start_time"),  # type: ignore[arg-type]
            duration=request.get("duration"),  # type: ignore[arg-type]
            axis=axis if isinstance(axis, str) else None,
            request_id=_optional_text(request.get("request_id")),
            reservation_id=_optional_text(request.get("reservation_id")),
            current_time=now,
        )
    else:
        decision = reservation_manager.reserve_with_details(
            request.get("node"),  # type: ignore[arg-type]
            request.get("start_time"),  # type: ignore[arg-type]
            request.get("duration"),  # type: ignore[arg-type]
            request.get("ev_id"),  # type: ignore[arg-type]
            axis=axis if isinstance(axis, str) else None,
            request_id=_optional_text(request.get("request_id")),
            reservation_id=_optional_text(request.get("reservation_id")),
            current_time=now,
        )
    return reservation_response_payload(decision, request, accepted_at=now)


def log_reservation_response(response: dict[str, object], *, cancel: bool = False) -> None:
    """Emit a concise, readable audit line for every reservation lifecycle event."""
    action = "CANCELLED" if cancel and response.get("cancelled") else "CANCEL FAILED"
    if not cancel:
        action = "GRANTED" if response.get("granted") else "REJECTED"
    print(
        "[reservation] "
        f"{action} | node={response.get('node')} | ev={response.get('ev_id')} "
        f"| axis={response.get('axis')} | window=[{response.get('start_time')}, "
        f"{response.get('start_time')}+{response.get('duration')}) "
        f"| reason={response.get('reason')}"
        + (
            f" | request_id={response['request_id']}"
            if response.get("request_id")
            else ""
        ),
        flush=True,
    )


def on_connect(client: mqtt.Client, _userdata, _flags, reason_code, _properties) -> None:
    if reason_code.is_failure:
        CONNECTED.clear()
        CONTROL_SUBSCRIPTIONS_READY.clear()
        print(f"MQTT connection failed: {reason_code}")
    else:
        CONNECTED.set()
        CONTROL_SUBSCRIPTIONS_READY.clear()
        with CONTROL_SUBSCRIBE_LOCK:
            CONTROL_SUBSCRIBE_MIDS.clear()
            for topic in (RESERVATION_TOPIC, RESERVATION_CANCEL_TOPIC):
                result, mid = client.subscribe(topic, qos=1)
                if result == mqtt.MQTT_ERR_SUCCESS:
                    CONTROL_SUBSCRIBE_MIDS.add(mid)
                else:
                    print(
                        f"[reservation] Could not subscribe to {topic} (MQTT status {result})",
                        flush=True,
                    )
        print(f"Connected to MQTT broker at {BROKER_HOST}:{BROKER_PORT}")


def on_subscribe(
    _client: mqtt.Client,
    _userdata: object,
    mid: int,
    _reason_codes: Any,
    _properties: Any,
) -> None:
    """Mark the controller ready only after both MQTT subscriptions confirm."""
    with CONTROL_SUBSCRIBE_LOCK:
        if mid not in CONTROL_SUBSCRIBE_MIDS:
            return
        CONTROL_SUBSCRIBE_MIDS.discard(mid)
        ready = not CONTROL_SUBSCRIBE_MIDS
    if ready:
        CONTROL_SUBSCRIPTIONS_READY.set()
        print("[reservation] Controller ready: listening for reserve and cancel commands.", flush=True)


def on_disconnect(_client: mqtt.Client, _userdata, _disconnect_flags, reason_code, _properties) -> None:
    CONNECTED.clear()
    CONTROL_SUBSCRIPTIONS_READY.clear()
    print(f"MQTT disconnected: {reason_code}")


def on_connect_fail(_client: mqtt.Client, _userdata) -> None:
    """Paho calls this after a TCP connection attempt fails."""
    CONNECTED.clear()
    print(
        f"Cannot reach MQTT broker at {BROKER_HOST}:{BROKER_PORT}. "
        "Retrying automatically; check MQTT_BROKER, MQTT_PORT, or your firewall."
    )


def on_message(client: mqtt.Client, userdata: object, message: Any) -> None:
    """Arbitrate incoming EV slots on Paho's network thread and acknowledge."""
    if not isinstance(userdata, ReservationManager):
        print("[reservation] Ignored message: reservation manager is unavailable.", flush=True)
        return
    if message.topic not in {RESERVATION_TOPIC, RESERVATION_CANCEL_TOPIC}:
        return
    is_cancel = message.topic == RESERVATION_CANCEL_TOPIC
    response = handle_reservation_message(
        message.payload,
        userdata,
        cancel=is_cancel,
    )
    log_reservation_response(response, cancel=is_cancel)
    result = client.publish(
        RESERVATION_RESPONSE_TOPIC,
        json.dumps(response),
        qos=1,
        retain=False,
    )
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"[reservation] Could not publish acknowledgement (MQTT status {result.rc})")


def stop(_signum, _frame) -> None:
    global RUNNING
    RUNNING = False


def main() -> None:
    if MQTT_TRANSPORT not in {"tcp", "websockets"}:
        raise ValueError("MQTT_TRANSPORT must be 'tcp' or 'websockets'")

    reservation_manager = ReservationManager()
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"intersection-edge-{uuid.uuid4().hex[:8]}",
        protocol=mqtt.MQTTv311,
        transport=MQTT_TRANSPORT,
    )
    if MQTT_TRANSPORT == "websockets":
        client.ws_set_options(path=MQTT_WS_PATH)
    client.on_connect = on_connect
    client.on_connect_fail = on_connect_fail
    client.on_disconnect = on_disconnect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    # Set before the network loop begins, so a fast retained/message callback
    # cannot observe an uninitialised reservation manager.
    client.user_data_set(reservation_manager)
    # loop_start keeps MQTT reconnects and network I/O off the simulation loop.
    client.reconnect_delay_set(min_delay=1, max_delay=20)
    client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    rng = random.Random()
    adjacency = build_adjacency_map()
    traffic_lights = build_traffic_lights(rng)
    queues = [rng.randint(0, 12) for _ in range(NODE_COUNT)]
    simulation_tick = 0
    last_publish = 0.0
    last_wait_notice = 0.0
    log_schedule = (
        "disabled"
        if SIMULATION_LOG_INTERVAL_TICKS == 0
        else f"tick 1 and every {SIMULATION_LOG_INTERVAL_TICKS} tick(s)"
    )
    print(
        "Starting 5x5 intersection simulation. "
        f"Grid stream logs: {log_schedule}; JSON logging: {'on' if SIMULATION_LOG_JSON else 'off'}. "
        f"EV reservation horizon: {RESERVATION_HORIZON_SECONDS}s. "
        "Press Ctrl+C to stop.",
        flush=True,
    )

    while RUNNING:
        iteration_started = time.monotonic()
        wall_clock_second = int(time.time())
        # One iteration represents one second of signal-controlled traffic.
        queues = simulate_network_step(
            queues,
            adjacency,
            traffic_lights,
            rng,
            reservation_manager,
            current_time=wall_clock_second,
        )
        simulation_tick += 1

        mqtt_connected = CONNECTED.is_set()
        publish_due = mqtt_connected and iteration_started - last_publish >= 2.0
        log_due = should_log_stream(simulation_tick)
        payload: list[dict[str, object]] | None = None

        # One snapshot is reused for terminal inspection and MQTT publication,
        # which guarantees that the user sees the exact data shape downstream
        # consumers receive whenever a publish is due.
        if log_due or publish_due:
            generated_at = time.time()
            payload = build_traffic_payload(
                queues,
                traffic_lights,
                simulation_tick,
                generated_at,
                reservation_manager,
            )

        if log_due:
            # ``payload`` is guaranteed above when ``log_due`` is true.
            assert payload is not None
            log_traffic_stream(
                payload,
                traffic_lights,
                mqtt_connected,
                publish_due,
                reservation_manager,
            )

        if publish_due:
            # ``payload`` is guaranteed above when ``publish_due`` is true.
            assert payload is not None
            # Retaining one complete snapshot lets an orchestrator started
            # later connect immediately, while its freshness check protects
            # against routing on an old retained message.
            result = client.publish(UPDATE_TOPIC, json.dumps(payload), qos=1, retain=True)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"Could not queue traffic update (MQTT status {result.rc})")
            last_publish = iteration_started
        elif not mqtt_connected and iteration_started - last_wait_notice >= 15.0:
            print("Waiting for MQTT connection; traffic updates will publish once connected.")
            last_wait_notice = iteration_started

        # Maintain the one-second simulation cadence despite processing overhead.
        time.sleep(max(0.0, 1.0 - (time.monotonic() - iteration_started)))

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    main()
